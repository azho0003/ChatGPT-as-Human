import dotenv
import openai
import subprocess
import xml.etree.ElementTree as ET
import json
import re

# def get_app_title_and_genre(package_name: str):
#     from google_play_scraper import app

#     app_title = "This app name is <name>."
#     app_genre = "\nThis app is categorise as a(an) <genre> app."

#     result = app(package_name, lang="en", country="us")
#     if result["title"] != "":
#         app_title = app_title.replace("<name>", result["title"])
#     else:
#         app_title = ""
#     if result["genre"] != "":
#         app_genre = app_genre.replace("<genre>", result["genre"])
#     else:
#         app_genre = ""
#     return app_title + app_genre


# def getAllComponents(jsondata: dict):
#     root = jsondata["hierarchy"]
#     queue = [root]
#     res = []
#     final_res = []
#     while queue:
#         currentNode = queue.pop(0)

#         if "node" in currentNode:
#             if type(currentNode["node"]).__name__ == "dict":
#                 queue.append(currentNode["node"])
#             else:
#                 for e in currentNode["node"]:
#                     queue.append(e)
#         else:
#             if ("com.android.systemui" not in currentNode["@resource-id"]) and (
#                 "com.android.systemui" not in currentNode["@package"]
#             ):
#                 res.append(currentNode)
#     for component in res:
#         if component["@text"] == "" and component["@resource-id"] == "" and component["@content-desc"] == "":
#             res.remove(component)
#         else:
#             tem_component = component
#             del tem_component["@checkable"]
#             del tem_component["@checked"]
#             del tem_component["@clickable"]
#             del tem_component["@enabled"]
#             del tem_component["@focusable"]
#             del tem_component["@focused"]
#             del tem_component["@scrollable"]
#             del tem_component["@long-clickable"]
#             del tem_component["@password"]
#             del tem_component["@selected"]
#             final_res.append(component)

#     return final_res


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
        content_desc = elem.attrib.get("content-desc")
        if not resource_id and not content_desc:
            elem.attrib.clear()

        if "Layout" in elem.attrib.get("class", ""):
            elem.attrib.clear()

        for attrib in remove_attribs:
            elem.attrib.pop(attrib, None)

    stripped = ET.tostring(root).decode("utf-8")
    full = ET.parse(filename)

    return (full, stripped)


def ask_gpt(view, question):
    role = """I want you to act as a UI tester. I will provide the view hierarchy for an android app in
    XML format and you will respond with a list of actions to perform. For example if asked how to calculate
    the sum of 3 and 4, you would provide
    ```
    [
        {"action": "click", "resource-id": "com.sec.android.app.popupcalculator:id/calc_keypad_btn_03"},
        {"action": "click", "resource-id": "com.sec.android.app.popupcalculator:id/calc_keypad_btn_add"},
        {"action": "click", "resource-id": "com.sec.android.app.popupcalculator:id/calc_keypad_btn_04"},
        {"action": "click", "resource-id": "com.sec.android.app.popupcalculator:id/calc_keypad_btn_equal"}
    ]
    ```
    Only respond with the actions, do not provide any explanation. Do not format the response.
    """

    prompt = f"""
    The view hierarchy for the app being tested is
    ```
    {view}
    ```
    """

    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": role},
            {"role": "assistant", "content": prompt},
            {"role": "user", "content": question},
        ],
    )

    return response


def perform_actions(response, view):
    content = response["choices"][0]["message"]["content"]
    actions = json.loads(content)

    # Process response actions
    for action in actions:
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

    filename = download_view_hierarchy()
    (view, stripped_view) = get_view_hierarchy(filename)

    # question = 'How to search for video titled "Framework Laptop"?'
    question = "Calculate the sum of two and three"
    response = ask_gpt(stripped_view, question)
    print(response)

    perform_actions(response, view)
