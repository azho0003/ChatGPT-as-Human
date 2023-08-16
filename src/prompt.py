import os

PROMPTS_PATH = "src/prompts"


def get_prompt(name):
    with open(os.path.join(PROMPTS_PATH, name + ".txt"), "r") as file:
        return file.read()
