import dotenv
import openai
import subprocess
import xmltodict
import xml.etree.ElementTree as ET
import json


def get_app_title_and_genre(package_name: str):
    from google_play_scraper import app

    app_title = "This app name is <name>."
    app_genre = "\nThis app is categorise as a(an) <genre> app."

    result = app(package_name, lang="en", country="us")
    if result["title"] != "":
        app_title = app_title.replace("<name>", result["title"])
    else:
        app_title = ""
    if result["genre"] != "":
        app_genre = app_genre.replace("<genre>", result["genre"])
    else:
        app_genre = ""
    return app_title + app_genre


def getAllComponents(jsondata: dict):

    root = jsondata["hierarchy"]

    queue = [root]
    res = []
    final_res = []
    while queue:
        currentNode = queue.pop(0)

        if "node" in currentNode:
            if type(currentNode["node"]).__name__ == "dict":
                queue.append(currentNode["node"])
            else:
                for e in currentNode["node"]:
                    queue.append(e)
        else:
            if ("com.android.systemui" not in currentNode["@resource-id"]) and (
                "com.android.systemui" not in currentNode["@package"]
            ):
                res.append(currentNode)
    for component in res:
        if component["@text"] == "" and component["@resource-id"] == "" and component["@content-desc"] == "":
            res.remove(component)
        else:
            tem_component = component
            del tem_component["@checkable"]
            del tem_component["@checked"]
            del tem_component["@clickable"]
            del tem_component["@enabled"]
            del tem_component["@focusable"]
            del tem_component["@focused"]
            del tem_component["@scrollable"]
            del tem_component["@long-clickable"]
            del tem_component["@password"]
            del tem_component["@selected"]
            final_res.append(component)

    return final_res


config = dotenv.dotenv_values(".env")
openai.api_key = config["OPENAI_API_KEY"]

# Download view hierarchy
subprocess.run("adb shell uiautomator dump")
subprocess.run("adb pull /sdcard/window_dump.xml")

# Remove unnecessary attributes
tree = ET.parse("window_dump.xml")
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

    # if "Layout" in elem.attrib.get("class", ""):
    #     elem.attrib.clear()

    for attrib in remove_attribs:
        elem.attrib.pop(attrib, None)

view = ET.tostring(root).decode("utf-8")
# print(view)

role = """I want you to act as a UI tester. I will provide the view hierarchy for an android app in
XML format and you will respond with a list of actions to perform. For example if asked how to calculate
the sum of 3 and 4, you would provide
```
[
    {"action": "click", "resource-id": "btn_3"},
    {"action": "click", "resource-id": "add"},
    {"action": "click", "resource-id": "btn_4"},
    {"action": "click", "resource-id": "equal"}
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
question = 'How to search for video titled "Framework Laptop"?'
# question = "Calculate the sum of two and three"


response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": role},
        {"role": "assistant", "content": prompt},
        {"role": "user", "content": question},
    ],
)

content = response["choices"][0]["message"]["content"]
print(content)

# Parse response actions
parsed = json.loads(content)
print(parsed)

# TODO: Process response actions
