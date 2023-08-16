import os
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont

OUTPUT = "output"


def combine_images_horizontally(image_files):
    new_im_path = os.path.join(os.path.dirname(image_files[0]), "combine.png")
    if os.path.exists(new_im_path):
        return

    images = [Image.open(x) for x in image_files]
    widths, heights = zip(*(i.size for i in images))

    total_width = sum(widths)
    max_height = max(heights)

    new_im = Image.new("RGB", (total_width, max_height))

    x_offset = 0
    for im in images:
        new_im.paste(im, (x_offset, 0))
        x_offset += im.size[0]
    new_im.save(new_im_path)


def combine_images_vertically(image_files):
    new_im_path = os.path.join(os.path.join(os.path.dirname(image_files[0]), ".."), "combine.png")
    if os.path.exists(new_im_path):
        return

    images = [Image.open(x) for x in image_files]
    widths, heights = zip(*(i.size for i in images))

    for i, img in enumerate(images):
        name = os.path.basename(os.path.dirname(image_files[i])).replace("_", " ")[:-2]
        font = ImageFont.truetype(r"C:\Windows\Fonts\ARIALBD.ttf", 100)
        draw = ImageDraw.Draw(img)
        draw.text((10, 10), name, font=font, fill=(255, 0, 0))

    max_width = max(widths)
    total_heights = sum(heights)

    new_im = Image.new("RGB", (max_width, total_heights))

    y_offset = 0
    for im in images:
        new_im.paste(im, (0, y_offset))
        y_offset += im.size[1]
    new_im.save(new_im_path)


for root, dirs, files in os.walk(OUTPUT):
    images = list(os.path.join(root, file) for file in files if file.endswith(".png"))
    if len(images) > 0:
        combine_images_horizontally(images)

for app in os.listdir(OUTPUT):
    personas = os.listdir(os.path.join(OUTPUT, app))
    images = list(os.path.join(OUTPUT, app, persona, "combine.png") for persona in personas)
    if len(images) > 0:
        combine_images_vertically(images)
