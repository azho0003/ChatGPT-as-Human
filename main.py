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
import os

def input_text(text):
    text = text.replace(" ","%s")
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
    config = dotenv.dotenv_values(".env.example")
    print(config["OPENAI_API_KEY"])
    openai.api_key = config["OPENAI_API_KEY"]



def download_view_hierarchy():
    # sleep for 2 secs in case the page is not fully loaded
    time.sleep(2)
    if os.path.exists("window_dump.xml"):
        os.remove("window_dump.xml")
    filename = "window_dump.xml"
    subprocess.run(["adb shell uiautomator dump"],shell=True)
    subprocess.run([f"adb pull /sdcard/window_dump.xml {filename}"],shell=True)
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


def ask_gpt(view,history,mode):

    match mode:
        case "tryAgain" :
            if len(history) > 1 :
                role = f"""
                            Your last response {history[:-1]} is not working, give me another one.
                            """ + """The supported actions are "click","send_keys". For example
                              
                              {"action": "click", "resource-id": "com.sec.android.app.popupcalculator:id/calc_keypad_btn_03"},
                              
                              Only respond with the action, do not provide any explanation. Do not repeat any actions in the provided history."""
        case _:
            role = """
                  You are a children using this app. Given the view hierarchy in XML format and you will
                  respond with a single action to perform. Do Not click any advertisements or promoted content.Do not play any videos.
                  Do not click any external links.Do not click any video inputs.
                  The supported actions are "click","send_keys". For example
                  ```
                  {"action": "click", "resource-id": "com.sec.android.app.popupcalculator:id/calc_keypad_btn_03"},
                  ```
                  Only respond with the action, do not provide any explanation. Do not repeat any actions in the provided history.
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
        case "send_keys":
            input_text(action["text"])
        case "back":
            get_back()


def get_back():
    # back to previous activity
    os.system("adb shell input keyevent 4")
    time.sleep(1)


def click_element(resource, view):
    root = view.getroot()
    elem = root.find(f'.//node[@resource-id="{resource}"]')
    bounds = elem.attrib.get("bounds")
    matches = re.findall("\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)[0]
    x = (int(matches[0]) + int(matches[2])) / 2
    y = (int(matches[1]) + int(matches[3])) / 2
    subprocess.run([f"adb shell input tap {x} {y}"],shell=True)

if __name__ == "__main__":
    setup()
    flag = True

    history = []
    tryAgainView = 0;
    tryAgainAction = 0;
    while flag:
        filename = download_view_hierarchy()
        (view, stripped_view) = get_view_hierarchy(filename)

        response = ask_gpt(stripped_view, history,"normal")
        try:
            action = get_action(response)

            if action in history:
                response = ask_gpt(stripped_view, history, "tryAgain")
                action = get_action(response)

            print(action)
        except:
            # TODO: Ask ChatGPT to try again. Most likely malformed JSON.
            # When there is an error, go back and ask chatGPT to try again
                get_back()
                filename = download_view_hierarchy()
                (view, stripped_view) = get_view_hierarchy(filename)
                response = ask_gpt(stripped_view, history, "tryAgain")
                action = get_action(response)
                print(action)

        history.append(action)

        print(Fore.GREEN + "Action:")
        print_json(action)
        try:
            perform_actions(action, view)

        except:
            # TODO: Ask ChatGPT to try again. Most likely an invalid resource id.
            get_back()
            filename = download_view_hierarchy()
            (view, stripped_view) = get_view_hierarchy(filename)
            response = ask_gpt(stripped_view, history, "tryAgain")
            action = get_action(response)
            print(action)

        time.sleep(2)
