import dotenv
import openai
import subprocess

config = dotenv.dotenv_values(".env")
openai.api_key = config["OPENAI_API_KEY"]

subprocess.run("adb shell uiautomator dump")
view = subprocess.run("adb shell cat /sdcard/window_dump.xml", shell=True, capture_output=True, text=True).stdout

role = "I want you to act as a UI tester. I will provide the view hierarchy for an android app in XML format and it will be your job to determine which elements to select to pass the test. This will involve reading the attributes within the view hierarchy."
prompt = f"""
The view hierarchy for the app being tested is
```
{view}
```
"""
question = "How to search for a new video?"

print(view)

response = openai.ChatCompletion.create(
    model="gpt-3.5-turbo",
    messages=[
        {"role": "system", "content": role},
        {"role": "assistant", "content": prompt},
        {"role": "user", "content": question},
    ],
)

print(response)
