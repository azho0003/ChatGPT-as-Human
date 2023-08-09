import dotenv
import openai
import subprocess
import xml.etree.ElementTree as ET
import json
import re
import time
from textwrap import dedent
import os
import traceback
import re
import tiktoken
from PIL import Image, ImageDraw, ImageFont

DATASET_PATH = r"G:\Shared drives\ChatGPT - Winter Research\Norbert\Datasets"
TASK_NAMES = os.path.join(DATASET_PATH, "tasknames.csv")
EMULATOR_PATH = os.path.expandvars(r"%localappdata%\Android\Sdk\emulator")

OUTPUT_FOLDER = "output_winter_6"

MAX_TOKENS = 4097
OUTPUT_TOKENS = 300

# Screenshot Annotation Constants
ARROW_SIZE = 20
FONT_SIZE = 48
COLOR = "#7FFF7F"  # Light green color
THICKNESS = 10

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
    {{"action": "tap", "id": <The id of the element to tap>, "reason": <An explanation of how this action works towards the goal>}}
    {{"action": "type", "text": <The text to type into the focused element>, "reason": <An explanation of how this action works towards the goal>}}
    {{"action": "scroll", "scroll-reference": <The scroll reference of the element to scroll>, "direction": <The direction to scroll, can be up/down/left/right>, "reason": <An explanation of how this action works towards the goal>}}
    {{"action": "back", "reason": <An explanation of how this action works towards the goal>}}
    {{"action": "enter", "reason": <An explanation of how this action works towards the goal>}}
    {{"action": "stop", "reason": <Why the testing should be stopped, this could be if the goal has been achieved>}}

    Do not "scroll" more than 3 times in a row.
    Once the goal is achieved, you will respond with a "stop" action.
    If there is a sign up screen, skip it or close it.
    If the hierarchy does not show a related element, open the menu, settings or navigation drawer.
    This is an example of an input and output:

    ###
    Goal:
    View Top Stories

    Previous Actions:
    None

    Hierarchy:
    <hierarchy><node text="Top Stories" id="4" /></hierarchy>

    Next Action:
    {{"action": "tap", "id": "4", "reason": "By tapping on the top stories element, the top stories become visible which is the goal"}}

    ###
    Goal:
    View Top Stories

    Previous Actions:
    {{"action": "tap", "id": "4", "reason": "By tapping on the top stories element, the top stories become visible which is the goal"}}

    Hierarchy:
    <hierarchy><node text="Top Story: New battery innovation" id="7" /></hierarchy>

    Next Action:
    {{"action": "stop", "reason": "The top story, 'New battery innovation' is visible. This means the goal has been achieved and the testing can be stopped"}}
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
        "checkable",
        # "checked",
        "focusable",
        # "focused",
        "password",
        # "selected",
        "enabled",
        "scrollable",
        "resource-id",
        "NAF",
        "bounds",
        "clickable",
        "rotation",
        "long-clickable",
        "class",
        "content-desc",
    ]

    tap_index = 0
    global tap_id_position_map  # TODO: Don't have global
    tap_id_position_map = {}

    scroll_index = 0
    global scroll_id_position_map  # TODO: Don't have global
    scroll_id_position_map = {}

    global focused_bounds
    focused_bounds = {"x1": 0, "y1": 0}  # TODO: Don't have global

    for elem in root.iter():
        bounds = elem.attrib.get("bounds")

        if bounds:
            matches = re.findall("\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)[0]
            x1 = int(matches[0])
            y1 = int(matches[1])
            x2 = int(matches[2])
            y2 = int(matches[3])
            x = (x1 + x2) / 2
            y = (y1 + y2) / 2

            clickable = elem.attrib.get("clickable")
            if clickable == "true":
                elem.attrib["id"] = str(tap_index)
                tap_id_position_map[str(tap_index)] = {"x": x, "y": y, "x1": x1, "y1": y1, "x2": x2, "y2": y2}
                tap_index += 1

            scrollable = elem.attrib.get("scrollable")
            if scrollable == "true":
                elem.attrib["scroll-reference"] = str(scroll_index)
                scroll_id_position_map[str(scroll_index)] = {"x": x, "y": y}
                scroll_index += 1

            focused = elem.attrib.get("focused")
            if focused == "true":
                focused_bounds = {"x1": x1, "y1": y1}

        class_val = elem.attrib.get("class")
        if class_val:
            elem.tag = re.sub("\W+", "", class_val.split(".")[-1])

        content_desc = elem.attrib.get("content-desc")
        if content_desc:
            elem.attrib["description"] = content_desc

        resource_id = elem.attrib.get("resource-id")
        if resource_id:
            elem.attrib["resource"] = resource_id.split("/")[-1]

        checkable = elem.attrib.get("checkable")
        if checkable == "false":
            elem.attrib.pop("checked", None)

        for attrib in ["focused", "selected"]:
            if elem.attrib.get(attrib) == "false":
                elem.attrib.pop(attrib)

        for key, value in elem.attrib.copy().items():
            if not value or key in remove_attribs:  # or value == "false"
                elem.attrib.pop(key)

    # Remove unnecessary elements
    parent_map = {c: p for p in tree.iter() for c in p}

    def clean(root):
        for elem in root.iter():
            if len(elem.attrib) == 0:
                if len(elem) == 1:
                    parent = parent_map.get(elem)
                    if parent:
                        print("Removing elem (1 child)", elem)
                        for i, child in enumerate(parent):
                            if child == elem:
                                parent[i] = elem[0]
                                return True
                elif len(elem) == 0:
                    parent = parent_map.get(elem)
                    if parent:
                        print("Removing elem (no child)", elem)
                        try:
                            parent.remove(elem)
                        except ValueError:
                            print("Failed to remove elem")
                        return True
        return False

    i = 0
    while clean(root) and i < 10:
        i += 1

    stripped = ET.tostring(root, encoding="utf-8", method="xml").decode("utf-8").replace("\n", "").replace("\r", "")

    # Format only the saved view, not the string representation
    with open(filename.replace(".xml", ".stripped.xml"), "wb") as f:
        ET.indent(tree)
        tree.write(f)

    return stripped


def num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613"):
    """Return the number of tokens used by a list of messages."""
    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        print("Warning: model not found. Using cl100k_base encoding.")
        encoding = tiktoken.get_encoding("cl100k_base")
    if model in {
        "gpt-3.5-turbo-0613",
        "gpt-3.5-turbo-16k-0613",
        "gpt-4-0314",
        "gpt-4-32k-0314",
        "gpt-4-0613",
        "gpt-4-32k-0613",
    }:
        tokens_per_message = 3
        tokens_per_name = 1
    elif model == "gpt-3.5-turbo-0301":
        tokens_per_message = 4  # every message follows <|start|>{role/name}\n{content}<|end|>\n
        tokens_per_name = -1  # if there's a name, the role is omitted
    elif "gpt-3.5-turbo" in model:
        print("Warning: gpt-3.5-turbo may update over time. Returning num tokens assuming gpt-3.5-turbo-0613.")
        return num_tokens_from_messages(messages, model="gpt-3.5-turbo-0613")
    elif "gpt-4" in model:
        print("Warning: gpt-4 may update over time. Returning num tokens assuming gpt-4-0613.")
        return num_tokens_from_messages(messages, model="gpt-4-0613")
    else:
        raise NotImplementedError(
            f"""num_tokens_from_messages() is not implemented for model {model}. See https://github.com/openai/openai-python/blob/main/chatml.md for information on how messages are converted to tokens."""
        )
    num_tokens = 0
    for message in messages:
        num_tokens += tokens_per_message
        for key, value in message.items():
            num_tokens += len(encoding.encode(value))
            if key == "name":
                num_tokens += tokens_per_name
    num_tokens += 3  # every reply is primed with <|start|>assistant<|message|>
    return num_tokens


def get_model(messages):
    tokens = num_tokens_from_messages(messages)
    if tokens < MAX_TOKENS - OUTPUT_TOKENS:
        model = "gpt-3.5-turbo"
    else:
        print("Using 16k model")
        model = "gpt-3.5-turbo-16k"

    return model


def ask_gpt(history, view, task, persona):
    formatted_history = "\n".join(json.dumps(h) for h in history) if len(history) > 0 else "None"

    if "scroll-reference" not in view:
        print("Removing scroll action")
        role_template = "\n".join(line for line in ROLE.split("\n") if "scroll" not in line)
    else:
        role_template = ROLE

    messages = [
        {"role": "system", "content": role_template.format(persona["name"], persona["age"])},
        {"role": "user", "content": PROMPT.format(task, formatted_history, view)},
    ]
    # print(messages)

    model = get_model(messages)

    print("Getting ChatGPT response")
    response = get_chat_completion(model=model, messages=messages)
    # print(response)

    return response


def get_chat_completion(**kwargs):
    while True:
        try:
            return openai.ChatCompletion.create(**kwargs)
        except (openai.error.RateLimitError, openai.error.ServiceUnavailableError) as e:
            print(e)
            # Waiting 1 minute as that is how long it takes the rate limit to reset
            print("Rate limit reached, waiting 1 minute")
            time.sleep(60)


def perform_action(action):
    print("Performing action")
    success = True
    match action["action"]:
        case "tap":
            click_element_by_id(action["id"])
        case "type":
            input_text(action["text"])
        case "scroll":
            scroll(action["scroll-reference"], action["direction"])
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


def scroll(scroll_id, direction):
    if direction not in {"up", "down", "left", "right"}:
        print(f"Invalid scroll direction: {direction}")
        return False

    pos = scroll_id_position_map[scroll_id]
    x = pos["x"]
    y = pos["y"]

    dx = {
        "up": 0,
        "down": 0,
        "left": 300,
        "right": -300,
    }

    dy = {
        "up": 300,
        "down": -300,
        "left": 0,
        "right": 0,
    }

    os.system(f"adb shell input swipe {x} {y} {x+dx[direction]} {y+dy[direction]} 100")
    return True


def back_action():
    os.system("adb shell input keyevent 4")


def enter_action():
    os.system(f"""adb shell input keyevent 66""")


def click_element_by_id(id):
    pos = tap_id_position_map.get(id)
    if pos:
        return click_location(pos["x"], pos["y"])
    return False


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
    actions_file = os.path.join(folder, "actions.json")

    while index < 10:
        time.sleep(3)
        capture_screenshot(folder, index)
        hierarchy_filename = os.path.join(folder, f"{index}.xml")
        download_view_hierarchy(hierarchy_filename)
        stripped_view = get_view_hierarchy(hierarchy_filename)
        response = ask_gpt(history, stripped_view, task, persona)

        try:
            action = get_action(response)
        except Exception as e:
            print("Failed to parse action. Trying again.", e)
            continue

        print("Action", action)

        if action["action"] == "stop":
            history.append(action)
            save_actions(actions_file, task, history)
            break

        try:
            perform_action(action)
        except Exception as e:
            print("Failed to perform action. Trying again.", e)
            continue

        history.append(action)
        save_actions(actions_file, task, history)

        try:
            annotate_screenshot(folder, index, action)
        except Exception as e:
            print("Failed to annotate screenshot", e)

        index += 1

    time.sleep(3)


def stop_app(package):
    subprocess.run(f"adb shell am force-stop {package}", shell=True)


def launch_app(package):
    stop_app(package)
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


def annotate_screenshot(folder, index, action):
    print("Annotating screenshot")
    filename = os.path.join(folder, f"{index}.png")
    image = Image.open(filename)
    draw = ImageDraw.Draw(image)

    if action["action"] == "tap" and action["id"] in tap_id_position_map:
        annotate_tap_action(draw, action, index, folder, image)
    elif action["action"] == "scroll" and action["scroll-reference"] in scroll_id_position_map:
        annotate_scroll_action(draw, action, index, folder, image)
    elif action["action"] in ["type", "enter", "back"]:
        annotate_text_action(draw, action, index, folder, image)
    else:
        print("Invalid action:", action["action"])


def annotate_tap_action(draw, action, index, folder, image):
    bounds = tap_id_position_map[action["id"]]
    draw.rectangle([bounds["x1"], bounds["y1"], bounds["x2"], bounds["y2"]], outline=COLOR, width=THICKNESS)
    save_annotated_screenshot(image, index, folder)


def annotate_scroll_action(draw, action, index, folder, image):
    bounds = scroll_id_position_map[action["scroll-reference"]]
    direction = action["direction"]
    start_point = (bounds["x"], bounds["y"])
    end_point = calculate_end_point(start_point, direction)

    draw.line([start_point, end_point], fill=COLOR, width=THICKNESS)
    draw_arrow(draw, end_point, direction)
    save_annotated_screenshot(image, index, folder)


def annotate_text_action(draw, action, index, folder, image):
    text = get_annotation_symbol(action)

    if action["action"] in ["enter", "back"]:
        # Use font that support the required unicode characters
        font = ImageFont.truetype("cambria.ttc", FONT_SIZE * 3)
    else:
        font = ImageFont.truetype("arial.ttf", FONT_SIZE)

    draw.text((focused_bounds["x1"], focused_bounds["y1"]), text, fill=COLOR, font=font)
    save_annotated_screenshot(image, index, folder)


def calculate_end_point(start_point, direction):
    line_length = 300
    if direction == "up":
        return (start_point[0], start_point[1] - line_length)
    elif direction == "down":
        return (start_point[0], start_point[1] + line_length)
    elif direction == "left":
        return (start_point[0] - line_length, start_point[1])
    elif direction == "right":
        return (start_point[0] + line_length, start_point[1])


def draw_arrow(draw, end_point, direction):
    arrow_points = []
    if direction == "up":
        arrow_points = [
            (end_point[0] - ARROW_SIZE, end_point[1] + ARROW_SIZE),
            (end_point[0] + ARROW_SIZE, end_point[1] + ARROW_SIZE),
            end_point,
        ]
    elif direction == "down":
        arrow_points = [
            (end_point[0] - ARROW_SIZE, end_point[1] - ARROW_SIZE),
            (end_point[0] + ARROW_SIZE, end_point[1] - ARROW_SIZE),
            end_point,
        ]
    elif direction == "left":
        arrow_points = [
            (end_point[0] + ARROW_SIZE, end_point[1] - ARROW_SIZE),
            (end_point[0] + ARROW_SIZE, end_point[1] + ARROW_SIZE),
            end_point,
        ]
    elif direction == "right":
        arrow_points = [
            (end_point[0] - ARROW_SIZE, end_point[1] - ARROW_SIZE),
            (end_point[0] - ARROW_SIZE, end_point[1] + ARROW_SIZE),
            end_point,
        ]

    draw.polygon(arrow_points, fill=COLOR)


def get_annotation_symbol(action):
    symbols = {
        "type": action.get("text", ""),
        "enter": "\u23CE",  # Unicode for Enter symbol
        "back": "\u21A9",  # Unicode for Back symbol
    }
    return symbols.get(action["action"], "")


def save_annotated_screenshot(image, index, folder):
    annotated_filename = os.path.join(folder, f"{index}_annotated.png")
    image.save(annotated_filename)
    print("Annotated screenshot saved as", annotated_filename)


def save_actions(filename, task, actions):
    with open(filename, "w") as f:
        out = {"goal": task, "actions": actions}
        f.write(json.dumps(out, indent=2))


def run_test(dir, persona, task_names):
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
    time.sleep(2)  # Wait for app to launch

    task = task_names[case_id]
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


def test_all_apps(persona, task_names):
    for dir in sorted(os.listdir(DATASET_PATH), key=str.casefold):
        print(persona, dir)
        try:
            run_test(dir, persona, task_names)
        except Exception:
            print(traceback.format_exc())
            print("Error, skipping")

        # Avoiding leaving app running the background
        stop_app(dir.split(" ")[0])


def get_task_names():
    map = {}
    with open(TASK_NAMES, "r") as f:
        for line in f.readlines():
            id, *rest = line.split(" ")
            task = " ".join(rest)
            map[id] = task

    return map


def wait_for_device_to_boot():
    is_running = lambda: subprocess.run(
        "adb shell getprop sys.boot_completed", shell=True, capture_output=True, text=True
    )
    while is_running().stdout.strip() != "1":
        time.sleep(5)
    time.sleep(10)
    print("Device booted")


def start_emulator():
    emulators = subprocess.run("emulator -list-avds", shell=True, capture_output=True, text=True, cwd=EMULATOR_PATH)
    emulator = emulators.stdout.split("\n")[0]
    subprocess.Popen(
        f"emulator -avd {emulator} -netdelay none -netspeed full",
        shell=True,
        cwd=EMULATOR_PATH,
        text=True,
    )
    wait_for_device_to_boot()


def restart():
    print("Restarting device")
    subprocess.run(f"adb -e reboot", shell=True)
    wait_for_device_to_boot()


if __name__ == "__main__":
    setup()
    start_emulator()

    task_names = get_task_names()

    for persona in PERSONAS:
        print("Using persona", persona)
        test_all_apps(persona, task_names)
