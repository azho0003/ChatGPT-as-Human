import dotenv
import openai
import subprocess
import xmltodict
from google_play_scraper import app


def get_app_title_and_genre(package_name:str):
    app_title = "This app name is <name>."
    app_genre = "\nThis app is categorise as a(an) <genre> app."

    result  = app(
    package_name,
    lang='en',
    country='us' )
    if (result['title']!=''):
       app_title = app_title.replace("<name>",result['title'])
    else:
        app_title = ""
    if (result['genre']!=''):
        app_genre = app_genre.replace("<genre>", result['genre'])
    else:
        app_genre = ""
    return app_title + app_genre


def getAllComponents(jsondata: dict):

    root = jsondata['hierarchy']

    queue = [root]
    res = []
    final_res = []
    while queue:
        currentNode = queue.pop(0)

        if 'node' in currentNode:
            if type(currentNode['node']).__name__ == 'dict':
                queue.append(currentNode['node'])
            else:
                for e in currentNode['node']:
                    queue.append(e)
        else:
            if ('com.android.systemui' not in currentNode['@resource-id']) and (
                    'com.android.systemui' not in currentNode['@package']):
                res.append(currentNode)
    for component in res:
        if (component['@text'] == "" and component['@resource-id'] == "" and component['@content-desc'] == ""):
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

subprocess.run("adb shell uiautomator dump")
view = subprocess.run("adb shell cat /sdcard/window_dump.xml", shell=True, capture_output=True, text=True).stdout

role = "I want you to act as a UI tester. I will provide the view hierarchy for an android app in XML format and it will be your job to determine which elements to select to pass the test. This will involve reading the attributes within the view hierarchy."
prompt = f"""
The view hierarchy for the app being tested is
```
{view}
```
"""
question = "How to search for a new video?"

print(view)

response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": role},
        {"role": "assistant", "content": prompt},
        {"role": "user", "content": question},
    ],
)

print(response)
