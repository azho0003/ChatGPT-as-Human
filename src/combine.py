import os
from PIL import Image


def combine_images(image_files):
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


for root, dirs, files in os.walk("output"):
    images = list(os.path.join(root, file) for file in files if file.endswith(".png"))
    if len(images) > 0:
        combine_images(images)
