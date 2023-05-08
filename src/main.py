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

OUTPUT_FOLDER = "output"
TEMP_FOLDER = "temp"



persona_prompt = {
  "young_adult_1": "I want you to act as a 22 year old university student. You are male, ethnically White Australian and speak English as a first language. You are very familiar with modern technology and have been using a smartphone since you were 10.",
  "elderly": "I want you to act as an 80 year old retiree. At your age, you are slow to respond to change and navigate through a phone slowly. You prefer to stay away from technology and only use mobile phones for the minimum required tasks.",
}



def set_working_directory():
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    root = os.path.join(dname, "..")
    os.chdir(root)


def detect_text_in_edit_widget(xml_dump):
    root = ET.fromstring(xml_dump)
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
    if not os.path.exists(TEMP_FOLDER):
        os.mkdir(TEMP_FOLDER)

    filename = os.path.join(TEMP_FOLDER, "window_dump.xml")
    if os.path.exists(filename):
        os.remove(filename)

    # sleep for 2 secs in case the page is not fully loaded
    time.sleep(2)

    subprocess.run("adb shell uiautomator dump", shell=True)
    subprocess.run(f"adb pull /sdcard/window_dump.xml {filename}", shell=True)

    return filename


def get_view_hierarchy(filename):
    tree = ET.parse(filename)
    root = tree.getroot()

    remove_attribs = [
        "index",
        "package",
        "checkable",
        "checked",
        "focusable",
        "focused",
        "password",
        "selected",
        "enabled",
        "scrollable",
    ]

    for elem in root.iter():
        # Remove namespace information
        elem.tag = elem.tag.split("}")[-1]

        resource_id = elem.attrib.get("resource-id")

        if not resource_id:
            elem.attrib.clear()

        if "Layout" in elem.attrib.get("class", "") or elem.attrib.get("clickable") != "true":
            elem.attrib.clear()

        for attrib in remove_attribs:
            elem.attrib.pop(attrib, None)

    stripped = ET.tostring(root, encoding="utf-8", method="xml").decode("utf-8").replace("\n", "").replace("\r", "")
    full = ET.parse(filename)

    return full, stripped


def is_valid_action(content,input_boxes_status):
    try:
        action = json.loads(content.replace("`", ""))
        if "action" in action and action["action"] in {"click", "send_keys","scroll","enter"}:
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
            time_taken = time_end-time_start
            return [reply,time_taken]
        except openai.error.RateLimitError:
            # Waiting 1 minute as that is how long it takes the rate limit to reset
            print("Rate limit reached, waiting 1 minute")
            time.sleep(60)


def ask_gpt(persona_prompt,view, history,input_boxes_status):
    role = f"""\
        {persona_prompt}
        I want you to test an android application based on its view hierarchy. I will provide the view hierarchy in XML format and you will respond with a single action to perform. Only respond with the action and do not provide any explanation. Do not provide me the actions in the history list.Only perform the "enter" action to submit the text if there is a filled text box.The response must be valid JSON. The supported actions are as follows
        {{"action": "click", "resource-id": "..."}}
        {{"action": "send_keys", text: "..."}}
        {{action": "back"}}
        {{"action": "enter"}}
        {{"action": "scroll","direction": "..."}}
        """

    prompt = f"""\
        Give me the next action to perform, where the view hierarchy for the application being tested is
        ```
        {view}
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
        if is_valid_action(content,input_boxes_status):
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
                    """
                               ,
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


if __name__ == "__main__":


    setup()
    app_package_name, app_activity_name = get_current_app_info()

    # TODO : Change this rounds number with whatever you want
    rounds = 3


    for persona_name, persona_text in persona_prompt.items():
        page_counter = Counter()

        all_rounds_actions = []

        final_all_rounds_actions = []

        for round_num in range(1, rounds + 1):
            folder_name = os.path.join(OUTPUT_FOLDER, f"{persona_name}_{round_num}")
            create_folder(folder_name)

            timer = 0
            history = []

            round_action = []

            # TODO : Change this timer number with whatever you want
            while timer < 5:
                filename = download_view_hierarchy()
                (view, stripped_view) = get_view_hierarchy(filename)
                input_boxes_status = detect_text_in_edit_widget(stripped_view)
                response = ask_gpt(persona_text, stripped_view, history, input_boxes_status)
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

                screenshot_filename = os.path.join(folder_name, f"action_{action['action']}_{len(history)}.png")
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
            print(f"{persona_name} , {resource_id}: {count} times")

        print(f"{persona_name},{final_all_rounds_actions}")
