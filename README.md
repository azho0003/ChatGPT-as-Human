# ChatGPT Usability Testing Automation

![Example Trace](example.png)

This project explores the automation of usability testing for Android applications using ChatGPT. By connecting to an Android device or emulator via ADB and defining tests in a CSV file, this tool streamlines the testing process. It leverages the power of ChatGPT to provide actions for testing scenarios, making usability testing efficient and systematic.

## Features

- **ADB Integration:** Connects to an Android device or emulator via ADB (ADB path set in `main.py`).

- **Test Definition:** Tests are defined in a `tests.csv` file, following the format: `Package, Use Case ID, Task`.

- **Test Execution:** The tests involve launching the app, processing the view hierarchy, sending it to ChatGPT, performing the action, and repeating until the task is done or the action limit is reached (default limit: 20).

- **Supported Actions:** The supported actions include `tap`, `type`, `scroll`, `back`, `enter`, and `stop`.

- **Easy Execution:** Execute the script using the command: `python src/main.py`.

- **API Key Setup:** To use the OpenAI API, create a `.env` file with `OPENAI_API_KEY` set (refer to `.env.example`).

- **Personas:** The tool includes four default personas (teen, young adult, middle-aged, older adult) that can be altered in `main.py`.

- **Model Selection:** The model can switch between GPT-3.5 and GPT-4 in `model.py`.

- **Result Storage:** Results are stored in a variable defined by `OUTPUT_FOLDER` (in `main.py`). For each persona and each test, it stores the list of actions and a sequence of screenshots annotated by the action at that step.

## Installation

1. Create a Python virtual environment:
   `python -m venv venv`

2. Activate the virtual environment:

- **Windows:**
  ```
  venv\Scripts\activate
  ```
- **Unix or Linux:**
  ```
  source venv/bin/activate
  ```

3. Install dependencies using `pip`: `pip install -r requirements.txt`

## Usage

1. Set up the ADB path in `main.py`.

2. Define tests in `tests.csv` following the specified format.

3. Create a `.env` file with your OpenAI API key.

4. Run the script: `python src/main.py`

---

**Note:** This project is powered by OpenAI's ChatGPT. For more information on OpenAI and its usage policies, visit [OpenAI's official website](https://www.openai.com/).
