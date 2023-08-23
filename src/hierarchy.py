import xml.etree.ElementTree as ET
import subprocess
import re


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
        "focusable",
        "password",
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
    tap_id_position_map = {}

    scroll_index = 0
    scroll_id_position_map = {}

    focused_bounds = {"x1": 0, "y1": 0}

    bounds_map = {"tap": tap_id_position_map, "scroll": scroll_id_position_map, "focus": focused_bounds}

    for elem in root.iter():
        bounds = elem.attrib.get("bounds")

        class_val = elem.attrib.get("class")
        if class_val:
            short_class = re.sub("\W+", "", class_val.split(".")[-1])
            elem.tag = short_class
        else:
            short_class = None

        if bounds:
            matches = re.findall("\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds)[0]
            x1 = int(matches[0])
            y1 = int(matches[1])
            x2 = int(matches[2])
            y2 = int(matches[3])
            x = (x1 + x2) / 2
            y = (y1 + y2) / 2

            clickable = (short_class == "TextView") or elem.attrib.get("clickable")
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
            if not value or key in remove_attribs:
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

    return stripped, bounds_map
