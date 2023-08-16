from PIL import Image, ImageDraw, ImageFont
import os

ARROW_SIZE = 20
FONT_SIZE = 60
COLOR = "#7FFF7F"  # Light green color
THICKNESS = 10
TEXT_FILL = "#FF0000"  # Red
OUTLINE_WIDTH = 2  # Adjust this value for thicker or thinner outline


def annotate_screenshot(folder, index, action, bounds_map):
    print("Annotating screenshot")
    filename = os.path.join(folder, f"{index}.png")
    image = Image.open(filename)
    draw = ImageDraw.Draw(image)

    if action["action"] == "tap" and action["id"] in bounds_map["tap"]:
        annotate_tap_action(draw, action, index, folder, image, bounds_map)
    elif action["action"] == "scroll" and action["scroll-reference"] in bounds_map["scroll"]:
        annotate_scroll_action(draw, action, index, folder, image, bounds_map)
    elif action["action"] in ["type", "enter", "back"]:
        annotate_text_action(draw, action, index, folder, image, bounds_map)
    else:
        print("Invalid action:", action["action"])


def annotate_tap_action(draw, action, index, folder, image, bounds_map):
    bounds = bounds_map["tap"][action["id"]]
    draw.rectangle([bounds["x1"], bounds["y1"], bounds["x2"], bounds["y2"]], outline=COLOR, width=THICKNESS)
    save_annotated_screenshot(image, index, folder)


def annotate_scroll_action(draw, action, index, folder, image, bounds_map):
    bounds = bounds_map["scroll"][action["scroll-reference"]]
    direction = action["direction"]
    start_point = (bounds["x"], bounds["y"])
    end_point = calculate_end_point(start_point, direction)

    draw.line([start_point, end_point], fill=COLOR, width=THICKNESS)
    draw_arrow(draw, end_point, direction)
    save_annotated_screenshot(image, index, folder)


def annotate_text_action(draw, action, index, folder, image, bounds_map):
    text = get_annotation_symbol(action)

    if action["action"] in ["enter", "back"]:
        # Use font that support the required unicode characters
        font = ImageFont.truetype("cambria.ttc", FONT_SIZE * 3)
    else:
        font = ImageFont.truetype("arial.ttf", FONT_SIZE)

    x = bounds_map["focus"]["x1"]
    y = bounds_map["focus"]["y1"]
    for dx in range(-OUTLINE_WIDTH, OUTLINE_WIDTH + 1):
        for dy in range(-OUTLINE_WIDTH, OUTLINE_WIDTH + 1):
            draw.text((x + dx, y + dy), text, font=font, fill=COLOR)
    draw.text((x, y), text, font=font, fill=TEXT_FILL)

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
