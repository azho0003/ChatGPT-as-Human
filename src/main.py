import dotenv
import openai
import subprocess
import xml.etree.ElementTree as ET
import json
import re
import time
from textwrap import dedent
from pygments import highlight, lexers, formatters
from colorama import Fore, Back, Style
import os
import shutil
from collections import Counter
from pick import pick
import csv

OUTPUT_FOLDER = "output"
TEMP_FOLDER = "temp"

clickable_elements = []


def select_persona():
    personas = {}
    with open("src/personas.csv") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            personas[
                row["Name"]
            ] = f"I want you to act as a {row['Age']} year old {row['Gender']} {row['Ethnicity']}. You work as a {row['Job']} and {row['Traits']}."

    options = list(personas.keys())
    persona_name, index = pick(options, "Select persona")
    persona_prompt = personas[persona_name]
    print("Selected persona:", persona_name)

    return persona_name.replace(" ", "_"), persona_prompt


def set_working_directory():
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    root = os.path.join(dname, "..")
    os.chdir(root)


def detect_text_in_edit_widget(view):
    root = view.getroot()
    input_boxes = root.findall(".//node[@class='android.widget.EditText']")
    status = ""

    if input_boxes:
        for input_box in input_boxes:
            resource_id = input_box.get("resource-id")
            text = input_box.get("text")

            if text:
                status += f"Input box ({resource_id}) has text: {text}\n"
            else:
                status += f"Input box ({resource_id}) is empty.\n"
    else:
        status = "No input boxes found."
    return status.strip()


def input_text(text):
    text = text.replace(" ", "%s")
    os.system(f"""adb shell input text \"{text}\"""")
    time.sleep(2)


def print_json(json_obj):
    formatted_json = json.dumps(json_obj, indent=4)
    colorful_json = highlight(formatted_json, lexers.JsonLexer(), formatters.TerminalFormatter())
    print(Style.RESET_ALL + colorful_json)


def setup():
    set_working_directory()
    config = dotenv.dotenv_values(".env")
    openai.api_key = config["OPENAI_API_KEY"]


def download_view_hierarchy():
    # sleep for 2 secs in case the page is not fully loaded
    time.sleep(2)
    if os.path.exists("window_dump.xml"):
        os.remove("window_dump.xml")
    filename = "window_dump.xml"

    subprocess.run("adb shell uiautomator dump", shell=True)
    subprocess.run(f"adb pull /sdcard/window_dump.xml {filename}", shell=True)
    return filename


def traverse_view_hierarchy(node):
    is_clickable = node.attrib.get("clickable", "").lower() == "true"

    if is_clickable:
        clickable_elements.append(node.attrib)

    for child in node:
        traverse_view_hierarchy(child)


def final_res():
    tree = ET.parse("window_dump.xml")
    root = tree.getroot()
    traverse_view_hierarchy(root)

    print("Clickable elements:")
    final_view = []
    for item in clickable_elements:
        if not item.get("NAF"):
            final_view.append(item)

    for item in final_view:
        del item["clickable"]
        del item["index"]
        del item["long-clickable"]
        del item["package"]
        del item["checkable"]
        del item["checked"]
        del item["focused"]
        del item["focusable"]
        del item["password"]
        del item["selected"]
        del item["enabled"]
        del item["scrollable"]

        if (not item.get("text")) and (not item.get("content-desc")):
            del item["text"]
            del item["content-desc"]

    return tree, final_view


def is_valid_action(content, input_boxes_status):
    try:
        action = json.loads(content.replace("`", ""))
        if "action" in action and action["action"] in {"click", "send_keys", "scroll", "enter"}:
            if action["action"] == "click" and "resource-id" in action:
                return True
            elif action["action"] == "send_keys" and "text" in action and input_boxes_status != "No input boxes found.":
                return True
            elif action["action"] == "scroll" and "direction" in action:
                return True
            elif action["action"] == "back":
                return True
            elif action["action"] == "enter":
                return True
    except json.JSONDecodeError:
        pass

    return False


def get_chat_completion(**kwargs):
    while True:
        try:
            time_start = time.time()
            reply = openai.ChatCompletion.create(**kwargs)
            time_end = time.time()
            time_taken = time_end - time_start
            return [reply, time_taken]
        except openai.error.RateLimitError:
            # Waiting 1 minute as that is how long it takes the rate limit to reset
            print("Rate limit reached, waiting 1 minute")
            time.sleep(60)


def ask_gpt(persona_prompt, view, history, input_boxes_status):
    role = f"""\
        {persona_prompt}
        I want you to test an android application based on its view hierarchy. I will provide the view hierarchy in XML format and you will respond with a single action to perform. Only respond with the action and do not provide any explanation.Only perform the "enter" action to submit the text if there is a filled text box.The response must be valid JSON. The supported actions are as follows
        {{"action": "click", "resource-id": "..."}}
        {{"action": "send_keys", text: "..."}}
        {{action": "back"}}
        {{"action": "enter"}}
        {{"action": "scroll","direction": "..."}}
        """

    history_str = json.dumps(history, indent=4)

    prompt = f"""\
        Give me the next action to perform, where the first part of the view hierarchy for the application being tested is
        ```
        {view}
        ```
        Do not perform any action from the following history:
               ```
               {history_str}
               ```
        """

    messages = [
        {"role": "system", "content": dedent(role)},
        {"role": "user", "content": "What actions have you performed previously within this application?"},
        {"role": "assistant", "content": json.dumps(history)},
        {"role": "assistant", "content": "Input boxes status: " + input_boxes_status},
        {"role": "user", "content": dedent(prompt)},
    ]

    while True:
        print(Fore.GREEN + "Messages")
        print_json(messages)
        response_arr = get_chat_completion(model="gpt-3.5-turbo", messages=messages, top_p=0.8)
        response = response_arr[0]
        time_taken = response_arr[1]

        content = response["choices"][0]["message"]["content"]
        print(content)
        if is_valid_action(content, input_boxes_status):
            print(Fore.GREEN + "Response")
            print_json(response)
            print("Time Taken for Response = " + str(time_taken))
            return response
        else:
            # Add a message to the conversation indicating the format was wrong
            messages.append(
                {
                    "role": "user",
                    "content": f"""\
                    The response format was incorrect. Please give me another action or keep the same action but provide it in the specified JSON format following the examples
                     {{"action": "click", "resource-id": "..."}}
                     {{"action": "send_keys", text: "..."}}
                     {{action": "back"}}
                     {{"action": "enter"}}
                     {{"action": "scroll","direction": "..."}}
                    """,
                }
            )


def get_action(response):
    content = response["choices"][0]["message"]["content"]
    content = content.replace("`", "")
    return json.loads(content)


def perform_actions(action, view):
    success = False

    match action["action"]:
        case "click":
            click_element(action["resource-id"], view)
            success = True
        case "send_keys":
            input_text(action["text"])
            success = True
        case "scroll":
            success = scroll(action["direction"])
        case "back":
            get_back()
            success = True
        case "enter":
            enter_action()
            success = True

    return success


def enter_action():
    os.system(f"""adb shell input keyevent 66""")
    os.system(f"""adb shell input keyevent 66""")
    time.sleep(2)


def scroll(direction):
    if direction not in {"up", "down", "left", "right"}:
        print(f"Invalid scroll direction: {direction}")
        return False

    keyevent_map = {
        "up": "adb shell input swipe 500 500 500 1500 100",
        "down": "adb shell input swipe 500 1500 500 500 100",
        "left": "adb shell input swipe 500 500 1500 500 100",
        "right": "adb shell input swipe 1500 500 500 500 100",
    }

    keyevent = keyevent_map[direction]
    os.system(f"{keyevent}")
    time.sleep(1)
    return True


def get_back():
    # back to previous activity
    os.system("adb shell input keyevent 4")
    time.sleep(1)


def click_element(resource, view):
    root = view.getroot()
    elem = root.find(f'.//node[@resource-id="{resource}"]')

    if elem is None:
        print(f"Element with resource-id '{resource}' not found.")
        return False

    bounds = elem.attrib.get("bounds")
    matches = re.findall("\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)[0]
    x = (int(matches[0]) + int(matches[2])) / 2
    y = (int(matches[1]) + int(matches[3])) / 2
    subprocess.run(f"adb shell input tap {x} {y}", shell=True)
    return True


def create_folder(folder_name):
    if os.path.exists(folder_name):
        shutil.rmtree(folder_name)
    os.makedirs(folder_name)
    return folder_name


def capture_screenshot(filename):
    subprocess.run(f"adb shell screencap -p /sdcard/screenshot.png", shell=True)
    subprocess.run(f"adb pull /sdcard/screenshot.png {filename}", shell=True)
    subprocess.run(f"adb shell rm /sdcard/screenshot.png", shell=True)


def process_app_info(command):
    result = os.popen(command).read()
    match = re.search(r"mCurrentFocus=.*?{.*?(\S+)\/(\S+)}", result)

    if match:
        package_name = match.group(1)
        activity_name = match.group(2)
        print(package_name, activity_name)
        return package_name, activity_name
    else:
        raise ValueError("Unable to find package and activity names. Make sure the app is running and in focus.")


def get_current_app_info():
    try:
        return process_app_info("adb shell dumpsys window displays")
    except ValueError:
        return process_app_info("adb shell dumpsys window windows")


def go_to_app_home_screen(package_name, activity_name):
    os.system(f"adb shell am force-stop {package_name}")
    os.system(f"adb shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1")
    time.sleep(2)


def clickable_elements_to_natural_language(elements):
    sentences = []
    for element in elements:
        if element["class"] == "android.widget.Button":
            if element["text"]:
                sentences.append(f"Click the '{element['text']}' button.")
            else:
                sentences.append("Click the button.")
        elif element["class"] == "android.widget.TextView":
            if element["text"]:
                sentences.append(f"Click the '{element['text']}' text.")
            else:
                sentences.append("Click the text.")
        elif element["class"] == "android.view.View":
            if element["text"]:
                sentences.append(f"Click the '{element['text']}' view.")
            else:
                sentences.append("Click the view.")
    return " ".join(sentences)


if __name__ == "__main__":

    setup()
    app_package_name, app_activity_name = get_current_app_info()

    # TODO : Change this rounds number with whatever you want
    rounds = 2

    persona_name, persona_prompt = select_persona()
    page_counter = Counter()

    all_rounds_actions = []

    final_all_rounds_actions = []

    for round_num in range(1, rounds + 1):
        folder_name = os.path.join(OUTPUT_FOLDER, app_package_name, f"{persona_name}_{round_num}")
        create_folder(folder_name)

        timer = 0
        history = []

        round_action = []

        capture_screenshot(os.path.join(folder_name, f"-1.png"))

        # TODO : Change this timer number with whatever you want
        while timer < 5:
            clickable_elements = []
            filename = download_view_hierarchy()
            (view, stripped_view) = final_res()
            input_boxes_status = detect_text_in_edit_widget(view)
            response = ask_gpt(persona_prompt, stripped_view, history, input_boxes_status)
            action = get_action(response)

            if action["action"] == "click":
                page_counter[action["resource-id"]] += 1

            # Perform the action and check if it was successful
            click_successful = perform_actions(action, view)

            # stop for 2s for screenshot
            time.sleep(2)

            # If the click is unsuccessful, go back and ask GPT for another action
            if not click_successful:
                get_back()
                continue

            screenshot_filename = os.path.join(folder_name, f"{timer}_action_{action['action']}_{len(history)}.png")
            capture_screenshot(screenshot_filename)

            history.append(action)
            round_action.append(action)
            timer += 1
            time.sleep(2)
        final_all_rounds_actions.append(round_action)
        go_to_app_home_screen(app_package_name, app_activity_name)

    # Print the top 5 resource-id the script will click
    print("\nTop 5 resource_id the script performed actions on:")
    for resource_id, count in page_counter.most_common(5):
        print(f"{persona_name}, {resource_id}: {count} times")

    print(f"{persona_name}, {final_all_rounds_actions}")
