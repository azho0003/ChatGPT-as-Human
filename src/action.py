import os
import json
import subprocess


def perform_action(action, bounds_map):
    print("Performing action")
    match action["action"]:
        case "tap":
            click_element_by_id(action["id"], bounds_map)
        case "type":
            input_text(action["text"])
        case "scroll":
            scroll(action["scroll-reference"], action["direction"], bounds_map)
        case "back":
            back_action()
        case "enter":
            enter_action()
        case _:
            raise ValueError("Unknown action")


def input_text(text):
    text = text.replace(" ", "%s")
    os.system(f'adb shell input text "{text}"')


def scroll(scroll_id, direction, bounds_map):
    if direction not in {"up", "down", "left", "right"}:
        print(f"Invalid scroll direction: {direction}")
        raise ValueError("Invalid scroll direction")

    pos = bounds_map["scroll"][scroll_id]
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


def back_action():
    os.system("adb shell input keyevent 4")


def enter_action():
    os.system("adb shell input keyevent 66")


def click_element_by_id(id, bounds_map):
    pos = bounds_map["tap"][id]
    click_location(pos["x"], pos["y"])


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
