"""Generate vis.html for easier verification
On vis.html, each row would be the GPT's interaction trace, and the final image would be the GT final UI (highlighted by the green box)
"""

from glob import glob
import os

######## ONLY NEED TO MODIFY HERE
path2GTdir = r"G:\Shared drives\ChatGPT - Winter Research\Norbert\Datasets"
path2OutputDir = "output_winter_2"
########

html = """
<!DOCTYPE html>
<html>
<head>
    <title>Images in Table</title>
</head>
<body>
    <table style="width:100%" border="1">
"""


### get all folder2gtFilePath
folder2gtFilePath = {}
allGTFolders = glob(os.path.join(path2GTdir, "**"))
for gtFolder in allGTFolders:
    all_pngs = glob(os.path.join(gtFolder, "**.png"))
    all_pngs = list(sorted(all_pngs, key=lambda x: int(os.path.basename(x).split(".")[0])))
    if len(all_pngs) > 0:
        curr_file = all_pngs[-1]
        print(all_pngs, curr_file)
        folder2gtFilePath[os.path.basename(gtFolder).lower()] = curr_file

# iterate each persona
allPersonaFolder = glob(os.path.join(path2OutputDir, "**"))
allPersonaFolder.sort()

WIDTH = 200
HEIGHT = 400

for personaFolder in allPersonaFolder:  # [:1]:
    curr_persona = os.path.basename(personaFolder)
    # iterate all inner use case folders
    allUseCaseFolder = glob(os.path.join(personaFolder, "**"))
    allUseCaseFolder.sort(key=str.casefold)
    for useCaseFolder in allUseCaseFolder:
        html += f"<tr><td><b>{curr_persona}</b></td>"
        html += f"<td><b>{os.path.basename(useCaseFolder)}</b></td>"

        all_pngs = glob(os.path.join(useCaseFolder, "*[!_annotated].png"))
        if len(all_pngs) == 0:
            continue
        all_pngs = list(sorted(all_pngs, key=lambda x: int(os.path.basename(x).split(".")[0])))
        has_error = os.path.exists(os.path.join(useCaseFolder, "error.log"))

        gtFilePath = folder2gtFilePath[os.path.basename(useCaseFolder).lower()]
        print(len(all_pngs))
        for png_path in all_pngs:
            annotated_png = png_path.replace(".png", "_annotated.png")
            if os.path.exists(annotated_png):
                png_path = annotated_png
            html += f"""<td><img style="width:{WIDTH}px;height:{HEIGHT}px" src="{png_path}"></td>"""
        if has_error:
            html += f"""<td style="background-color:red;border: 5px solid red;"><img style="width:{WIDTH}px;height:{HEIGHT}px;"></td>"""

        html += f"""<td style="background-color:green;border: 5px solid green;"><img style="width:{WIDTH}px;height:{HEIGHT}px" src="{gtFilePath}"></td>"""
        html += "</tr>"

html += """
    </table>
</body>
</html>
"""


# Write the string to file
with open(f"vis_{path2OutputDir}.html", "w") as file:
    file.write(html)
