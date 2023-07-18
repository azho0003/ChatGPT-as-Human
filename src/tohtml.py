"""Generate vis.html for easier verification
On vis.html, each row would be the GPT's interaction trace, and the final image would be the GT final UI (highlighted by the green box)
"""

from glob import glob
import os

######## ONLY NEED TO MODIFY HERE
path2GTdir = "Datasets"
path2OutputDir = "output_winter"
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
    curr_file = all_pngs[-1]
    print(all_pngs, curr_file)
    folder2gtFilePath[os.path.basename(gtFolder).lower()] = curr_file
    # break

# iterate each persona
allPersonaFolder = glob(os.path.join(path2OutputDir, "**"))
allPersonaFolder.sort()

for personaFolder in allPersonaFolder:  # [:1]:
    curr_persona = os.path.basename(personaFolder)
    # iterate all inner use case folders
    allUseCaseFolder = glob(os.path.join(personaFolder, "**"))
    allUseCaseFolder.sort()
    for useCaseFolder in allUseCaseFolder:
        html += f"<tr><td><b>{curr_persona}</b></td>"
        html += f"<td><b>{os.path.basename(useCaseFolder)}</b></td>"

        all_pngs = glob(os.path.join(useCaseFolder, "**.png"))
        if len(all_pngs) == 0:
            continue
        all_pngs = list(sorted(all_pngs, key=lambda x: int(os.path.basename(x).split(".")[0])))

        gtFilePath = folder2gtFilePath[os.path.basename(useCaseFolder).lower()]
        print(len(all_pngs))
        for pngPath in all_pngs:
            html += f"""<td><img style="width:300px;height:600px" src="{pngPath}"></td>"""

        html += f"""<td style="background-color:green;border: 5px solid green;"><img style="width:350px;height:600px" src="{gtFilePath}"></td>"""
        html += "</tr>"

html += """
    </table>
</body>
</html>
"""


# Write the string to file
with open("vis.html", "w") as file:
    file.write(html)
