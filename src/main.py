import dotenv
import openai

import json
import time
import os
import traceback
import csv


from annotate import annotate_screenshot
from model import ask_gpt
from action import get_action, perform_action
from emulator import start_emulator, capture_screenshot, stop_app, launch_app
from hierarchy import download_view_hierarchy, get_view_hierarchy

EMULATOR_PATH = os.path.expandvars(r"%localappdata%\Android\Sdk\emulator")

OUTPUT_FOLDER = "output_gpt4_1"


PERSONAS = [
    {"name": "teen", "age": "13-19"},
    {"name": "young adult", "age": "20-35"},
    {"name": "middle aged adult", "age": "36-55"},
    {"name": "older adult", "age": "56-75"},
]


def set_working_directory():
    abspath = os.path.abspath(__file__)
    dname = os.path.dirname(abspath)
    root = os.path.join(dname, "..")
    os.chdir(root)


def setup():
    set_working_directory()
    config = dotenv.dotenv_values(".env")
    openai.api_key = config["OPENAI_API_KEY"]


def perform_task(task, folder, persona):
    index = 0
    history = []
    actions_file = os.path.join(folder, "actions.json")

    while index < 10:
        time.sleep(3)
        capture_screenshot(folder, index)
        hierarchy_filename = os.path.join(folder, f"{index}.xml")
        download_view_hierarchy(hierarchy_filename)
        stripped_view, bounds_map = get_view_hierarchy(hierarchy_filename)
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
            perform_action(action, bounds_map)
        except Exception as e:
            print("Failed to perform action. Trying again.", e)
            continue

        history.append(action)
        save_actions(actions_file, task, history)

        try:
            annotate_screenshot(folder, index, action, bounds_map)
        except Exception as e:
            print("Failed to annotate screenshot", e)

        index += 1

    time.sleep(3)


def save_actions(filename, task, actions):
    with open(filename, "w") as f:
        out = {"goal": task, "actions": actions}
        f.write(json.dumps(out, indent=2))


def run_test(package, task, persona):
    output = os.path.join(OUTPUT_FOLDER, persona["name"], package)
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
    tests = []
    with open("tests.csv", newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            tests.append(row)
    tests.sort(key=lambda test: test["Package"].lower())

    for test in tests:
        package = test["Package"]
        print(persona, package)
        try:
            run_test(package, test["Task"], persona)
        except Exception:
            print(traceback.format_exc())
            print("Error, skipping")

        # Avoiding leaving app running the background
        stop_app(package)


if __name__ == "__main__":
    setup()
    start_emulator(EMULATOR_PATH)

    for persona in PERSONAS:
        print("Using persona", persona)
        test_all_apps(persona)
