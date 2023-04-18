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


def set_working_directory():
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    os.chdir(dname)


# TODO : Change the role name with whatever you want
role_name = "children"


def input_text(text):
    text = text.replace(" ", "%s")
    os.system(f"""adb shell input text \"{text}\"""")
    time.sleep(2)
    os.system(f"""adb shell input keyevent 66""")
    time.sleep(2)
    os.system(f"""adb shell input keyevent 66""")


def print_json(json_obj):
    formatted_json = json.dumps(json_obj, indent=4)
    colorful_json = highlight(formatted_json, lexers.JsonLexer(), formatters.TerminalFormatter())
    print(Style.RESET_ALL + colorful_json)


def setup():
    set_working_directory()
    config = dotenv.dotenv_values(".env")
    print(config["OPENAI_API_KEY"])
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


def get_view_hierarchy(filename):
    tree = ET.parse(filename)
    root = tree.getroot()

    remove_attribs = [
        "index",
        "text",
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


def is_valid_action(content):
    try:
        action = json.loads(content.replace("`", ""))
        if "action" in action and action["action"] in {"click", "send_keys"}:
            if action["action"] == "click" and "resource-id" in action:
                return True
            elif action["action"] == "send_keys" and "text" in action:
                return True
    except json.JSONDecodeError:
        pass

    return False


def ask_gpt(view, history):

    role = f"""
            You are a {role_name} using this app. Given the view hierarchy in XML format and you will
            respond with a single action to perform.
            The supported actions are "click","send_keys". For example
            ```
            {"action": "click", "resource-id": "com.sec.android.app.popupcalculator:id/calc_keypad_btn_03"},
            ```
            Only respond with the action, do not provide any explanation. Do not repeat any actions in the provided history.
            """

    history_str = json.dumps(history, indent=4)

    prompt = f"""
               The view hierarchy is currently:
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
        {"role": "user", "content": "What actions have you performed so far?"},
        {"role": "assistant", "content": json.dumps(history)},
        {"role": "user", "content": dedent(prompt)},
    ]

    while True:
        print(Fore.GREEN + "Messages")
        print_json(messages)
        response = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages, top_p=0.8)

        content = response["choices"][0]["message"]["content"]
        if is_valid_action(content):
            print(response)
            return response
        else:
            # Add a message to the conversation indicating the format was wrong
            messages.append(
                {
                    "role": "user",
                    "content": "The response format was incorrect. Please provide a valid action in the specified JSON format.",
                }
            )

            time.sleep(1)  # Avoid rate limiting


def get_action(response):
    content = response["choices"][0]["message"]["content"]
    content = content.replace("`", "")
    return json.loads(content)


def perform_actions(action, view):
    success = False

    match action["action"]:
        case "click":
            success = click_element(action["resource-id"], view)
        case "send_keys":
            input_text(action["text"])
            success = True
        case "back":
            get_back()
            success = True

    return success


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


def get_current_app_info():
    result = os.popen("adb shell dumpsys window displays").read()
    match = re.search(r"mCurrentFocus=.*?{.*?(\S+)\/(\S+)}", result)

    if match:
        package_name = match.group(1)
        activity_name = match.group(2)
        print(package_name, activity_name)
        return package_name, activity_name
    else:
        raise ValueError("Unable to find package and activity names. Make sure the app is running and in focus.")


def go_to_app_home_screen(package_name, activity_name):
    os.system(f"adb shell am force-stop {package_name}")
    os.system(f"adb shell am start -n {package_name}/{activity_name}")
    time.sleep(2)


if __name__ == "__main__":
    setup()
    app_package_name, app_activity_name = get_current_app_info()

    # TODO : Change this rounds number with whatever you want
    rounds = 3

    page_counter = Counter()

    for round_num in range(1, rounds + 1):
        folder_name = f"{role_name}_{round_num}"
        create_folder(folder_name)

        timer = 0
        history = []

        # TODO : Change this timer number with whatever you want
        while timer < 5:
            filename = download_view_hierarchy()
            (view, stripped_view) = get_view_hierarchy(filename)
            response = ask_gpt(stripped_view, history)
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

            screenshot_filename = f"{folder_name}/action_{action['action']}_{len(history)}.png"
            capture_screenshot(screenshot_filename)

            history.append(action)
            timer += 1
            time.sleep(2)

        go_to_app_home_screen(app_package_name, app_activity_name)

    # Print the top 5 resource-id the script will click
    print("\nTop 5 app pages the script wants to go to:")
    for resource_id, count in page_counter.most_common(5):
        print(f"{resource_id}: {count} times")
