import dotenv
import openai
import subprocess
import xml.etree.ElementTree as ET
import json
import re
import time
from textwrap import dedent
import os
import shutil
from pick import pick
import traceback

DATASET_PATH = r"G:\Shared drives\ChatGPT - Winter Research\Deliverables\Data Collection\Norbert\Datasets"

OUTPUT_FOLDER = "output_winter"

# ROLE = dedent(
#     """
#     I want you to act as an Android UI tester. You will be provided the XML view hierarchy of an android app and a goal to achieve.
#     You will respond the best action that works towards the goal. This may take multiple actions to achieve.

#     The action must be a JSON object. The valid actions are listed below, with the explanation of any property placed in angle brackets.
#     {"action": "click-resource", "resource-id": <The resource id of the element to click>}
#     {"action": "click-location", "x": <The x coordinate to click>, "y": <The y coordinate to click>}
#     {"action": "scroll", "direction": <The direction to scroll, can be up/down/left/right>}
#     {"action": "send_keys", text: "..."}
#     {"action": "back"}
#     {"action": "enter"}
#     {"action": "stop", "reason": <Why the testing should be stopped, this could be if the goal has been achieved>}

#     This is an example of an input and output:

#     ###
#     Goal:
#     View Top Stories

#     Previous Actions:
#     None

#     Hierarchy:
#     <hierarchy><node text="Top Stories" bounds="[47,244][261,301]" /></hierarchy>

#     Next Action:
#     {"action": "click-location", "x": 154, "y": 272.5}
#     """
# )

PERSONAS = [
    {"name": "teen", "age": "13-19"},
    {"name": "young adult", "age": "20-35"},
    {"name": "middle aged adult", "age": "36-55"},
    {"name": "older adult", "age": "56-75"},
]

ROLE = dedent(
    """
    I want you to act as a {0} that is between {1} years old. You will be using an Android app trying to achieve a specified goal.
    You will be provided the xml view hierarchy of the Android app being tested.
    You will respond with the best action that works towards the goal. This may take multiple actions to achieve.

    The action must be a JSON object. The valid actions are listed below, with the explanation of any property placed in angle brackets.
    {{"action": "tap", "x": <The x coordinate to tap>, "y": <The y coordinate to tap>, "reason": <An explanation of how this action works towards the goal>}}
    {{"action": "send_keys", text: "...", "reason": <An explanation of how this action works towards the goal>}}
    {{"action": "scroll", "direction": <The direction to scroll, can be up/down/left/right>, "reason": <An explanation of how this action works towards the goal>}}
    {{"action": "back", "reason": <An explanation of how this action works towards the goal>}}
    {{"action": "enter", "reason": <An explanation of how this action works towards the goal>}}
    {{"action": "stop", "reason": <Why the testing should be stopped, this could be if the goal has been achieved>}}

    Once the goal is achieved, you will respond with a "stop" action.
    This is an example of an input and output:

    ###
    Goal:
    View Top Stories

    Previous Actions:
    None

    Hierarchy:
    <hierarchy><node text="Top Stories" x="154" y="272" /></hierarchy>

    Next Action:
    {{"action": "tap", "x": 154, "y": 272, "By tapping on the top stories element, the top stories become visible which is the goal"}}
    
    ###
    Goal:
    View Top Stories

    Previous Actions:
    {{"action": "tap", "x": 154, "y": 272, "By tapping on the top stories element, the top stories become visible which is the goal"}}

    Hierarchy:
    <hierarchy><node text="Top Story: New battery innovation" x="3" y="10" /></hierarchy>

    Next Action:
    {{"action": "stop", "The top story, new battery innovation is visible. This means the goal has been achieved and the testing can be stopped"}}
    """
)

PROMPT = dedent(
    """\
    ###
    Goal:
    {0}

    Previous Actions:
    {1}

    Hierarchy:
    {2}

    Next Action:
    """
)


def set_working_directory():
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    root = os.path.join(dname, "..")
    os.chdir(root)


def setup():
    set_working_directory()
    config = dotenv.dotenv_values(".env")
    openai.api_key = config["OPENAI_API_KEY"]


def download_view_hierarchy(filename):
    print("Downloading view hierarchy")
    subprocess.run("adb shell uiautomator dump", shell=True)
    subprocess.run(f'adb pull /sdcard/window_dump.xml "{filename}"', shell=True)


def get_view_hierarchy(filename):
    tree = ET.parse(filename)
    root = tree.getroot()

    remove_attribs = [
        "index",
        "package",
        # "checkable",
        # "checked",
        # "focusable",
        # "focused",
        # "password",
        # "selected",
        # "enabled",
        # "scrollable",
    ]

    for elem in root.iter():
        bounds = elem.attrib.get("bounds")
        if bounds:
            matches = re.findall("\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)[0]
            x = (int(matches[0]) + int(matches[2])) / 2
            y = (int(matches[1]) + int(matches[3])) / 2
            elem.attrib["x"] = str(x)
            elem.attrib["y"] = str(y)
            elem.attrib.pop("bounds")

        for key, value in elem.attrib.copy().items():
            if not value or value == "false" or key in remove_attribs:
                elem.attrib.pop(key)

    stripped = ET.tostring(root, encoding="utf-8", method="xml").decode("utf-8").replace("\n", "").replace("\r", "")

    # Format only the saved view, not the string representation
    with open(filename.replace(".xml", ".stripped.xml"), "wb") as f:
        ET.indent(tree)
        tree.write(f)

    return stripped


def ask_gpt(history, view, task, persona):
    formatted_history = "\n".join(json.dumps(h) for h in history) if len(history) > 0 else "None"
    messages = [
        {"role": "system", "content": ROLE.format(persona["name"], persona["age"])},
        {"role": "user", "content": PROMPT.format(task, formatted_history, view)},
    ]
    # print(messages)

    print("Getting ChatGPT response")
    response = get_chat_completion(model="gpt-3.5-turbo", messages=messages)
    # print(response)

    return response


def get_chat_completion(**kwargs):
    while True:
        try:
            return openai.ChatCompletion.create(**kwargs)
        except openai.error.RateLimitError as e:
            print(e)
            # Waiting 1 minute as that is how long it takes the rate limit to reset
            print("Rate limit reached, waiting 1 minute")
            time.sleep(60)


def perform_action(action):
    print("Performing action")
    success = True
    match action["action"]:
        # case "click-resource":
        #     click_element(action["resource-id"], view)
        case "tap":
            click_location(action["x"], action["y"])
        case "send_keys":
            input_text(action["text"])
        case "scroll":
            scroll(action["direction"])
        case "back":
            back_action()
        case "enter":
            enter_action()
        case _:
            success = False

    return success


def input_text(text):
    text = text.replace(" ", "%s")
    os.system(f"""adb shell input text \"{text}\"""")


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
    return True


def back_action():
    os.system("adb shell input keyevent 4")


def enter_action():
    os.system(f"""adb shell input keyevent 66""")


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
    click_location(x, y)


def click_location(x, y):
    subprocess.run(f"adb shell input tap {x} {y}", shell=True)


def get_action(response):
    content = response["choices"][0]["message"]["content"]
    content = content.replace("`", "")
    try:
        return json.loads(content)
    except Exception as e:
        print("Failed to parse action")
        print(content)
        raise e


def perform_task(task, folder, persona):
    index = 0
    history = []

    while True:
        time.sleep(3)
        capture_screenshot(folder, index)
        hierarchy_filename = os.path.join(folder, f"{index}.xml")
        download_view_hierarchy(hierarchy_filename)
        stripped_view = get_view_hierarchy(hierarchy_filename)
        response = ask_gpt(history, stripped_view, task, persona)
        action = get_action(response)
        print("Action", action)
        history.append(action)
        save_actions(os.path.join(folder, "actions.json"), task, history)

        index += 1
        if action["action"] == "stop" or index >= 10:
            break

        perform_action(action)

    time.sleep(3)


def launch_app(package):
    subprocess.run(f"adb shell am force-stop {package}", shell=True)
    time.sleep(0.2)
    start = subprocess.run(f"adb shell monkey -p {package} 1", shell=True, capture_output=True, text=True)
    if "No activities found to run" in start.stdout:
        raise Exception("Package not installed")


def capture_screenshot(folder, index):
    print("Capturing screenshot")
    filename = os.path.join(folder, f"{index}.png")
    subprocess.run(f"adb shell screencap -p /sdcard/screenshot.png", shell=True)
    subprocess.run(f'adb pull /sdcard/screenshot.png "{filename}"', shell=True)
    subprocess.run(f"adb shell rm /sdcard/screenshot.png", shell=True)


def save_actions(filename, task, actions):
    with open(filename, "w") as f:
        out = {"goal": task, "actions": actions}
        f.write(json.dumps(out, indent=2))


def run_test(dir, persona):
    package, case_id, *steps = dir.split(" ")

    output = os.path.join(OUTPUT_FOLDER, persona["name"], dir)
    if os.path.exists(output) and len(os.listdir(output)) > 0:
        print("Task skipped")
        return

    if not os.path.exists(output):
        os.makedirs(output)

    try:
        launch_app(package)
    except:
        launch_app(package.lower())
    time.sleep(1)  # Wait for app to launch

    task = " ".join(steps)
    print("Starting task", task)

    try:
        perform_task(task, output, persona)
    except Exception:
        error = traceback.format_exc()
        print(error)
        with open(os.path.join(output, "error.log"), "w") as f:
            f.write(error)
        print("Task failed")
    else:
        print("Task completed")


def test_all_apps(persona):
    for dir in sorted(os.listdir(DATASET_PATH)):
        print(persona, dir)
        try:
            run_test(dir, persona)
        except Exception:
            print(traceback.format_exc())
            print("Error, skipping")



if __name__ == "__main__":
    setup()

    for persona in PERSONAS:
        print("Using persona", persona)
        test_all_apps(persona)

    # dir, index = pick(os.listdir(DATASET_PATH), "Select test")
    # run_test(dir)
