import dotenv
import openai
import subprocess
import xml.etree.ElementTree as ET
import json
import re
import sys
import time
from textwrap import dedent
from pygments import highlight, lexers, formatters
from colorama import Fore, Back, Style


def print_json(json_obj):
    formatted_json = json.dumps(json_obj, indent=4)
    colorful_json = highlight(formatted_json, lexers.JsonLexer(), formatters.TerminalFormatter())
    print(Style.RESET_ALL + colorful_json)


def setup():
    config = dotenv.dotenv_values(".env")
    openai.api_key = config["OPENAI_API_KEY"]


def download_view_hierarchy():
    filename = "window_dump.xml"
    subprocess.run("adb shell uiautomator dump")
    subprocess.run(f"adb pull /sdcard/window_dump.xml {filename}")
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
        resource_id = elem.attrib.get("resource-id")
        if not resource_id:
            elem.attrib.clear()

        if "Layout" in elem.attrib.get("class", "") or elem.attrib.get("clickable") != "true":
            elem.attrib.clear()

        for attrib in remove_attribs:
            elem.attrib.pop(attrib, None)

    stripped = ET.tostring(root).decode("utf-8")
    full = ET.parse(filename)

    return (full, stripped)


def ask_gpt(view, history):
    role = """
    You are an android application UI tester. Given the view hierarchy in XML format and you will
    respond with a single action to perform. The supported actions are "click" and "send_keys". For example
    ```
    {"action": "click", "resource-id": "com.sec.android.app.popupcalculator:id/calc_keypad_btn_03"},
    ```
    Only respond with the action, do not provide any explanation. Do not repeat any actions.
    """

    prompt = f"""
    The view hierarchy is currently:
    ```
    {view}
    ```
    """

    messages = [
        {"role": "system", "content": dedent(role)},
        {"role": "user", "content": "What actions have you performed so far?"},
        {"role": "assistant", "content": json.dumps(history)},
        {"role": "user", "content": dedent(prompt)},
    ]
    print(Fore.GREEN + "Messages")
    print_json(messages)

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=messages,
    )

    return response


def get_action(response):
    content = response["choices"][0]["message"]["content"]
    content = content.replace("`", "")
    return json.loads(content)


def perform_actions(action, view):
    # Process response action
    # TODO: Implement send_keys
    match action["action"]:
        case "click":
            click_element(action["resource-id"], view)


def click_element(resource, view):
    root = view.getroot()
    elem = root.find(f'.//node[@resource-id="{resource}"]')
    bounds = elem.attrib.get("bounds")
    matches = re.findall("\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)[0]
    x = (int(matches[0]) + int(matches[2])) / 2
    y = (int(matches[1]) + int(matches[3])) / 2
    subprocess.run(f"adb shell input tap {x} {y}")


if __name__ == "__main__":
    setup()

    history = []
    for i in range(3):
        filename = download_view_hierarchy()
        (view, stripped_view) = get_view_hierarchy(filename)

        response = ask_gpt(stripped_view, history)
        action = get_action(response)
        history.append(action)

        print(Fore.GREEN + "Action:")
        print_json(action)
        try:
            perform_actions(action, view)
        except:
            # TODO: Ask ChatGPT to try again
            print("Failed to execute actions")
            break
        time.sleep(1)
