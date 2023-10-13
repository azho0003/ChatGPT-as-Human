import subprocess
import platform
import time
import os

# Control if the emulator should keep running after the testing ends
EXTERNAL_EMULATOR = False


def is_emulator_running():
    devices = subprocess.run("adb devices", shell=True, capture_output=True, text=True)
    return "emulator-5554" in devices.stdout


def wait_for_device_to_boot():
    is_running = lambda: subprocess.run(
        "adb shell getprop sys.boot_completed", shell=True, capture_output=True, text=True
    )
    while is_running().stdout.strip() != "1":
        time.sleep(5)
    time.sleep(30)
    print("Device booted")


def start_emulator(emulator_path):
    emulators = subprocess.run("emulator -list-avds", shell=True, capture_output=True, text=True, cwd=emulator_path)
    emulator = emulators.stdout.split("\n")[0]

    prefix = ""
    postfix = ""
    if EXTERNAL_EMULATOR:
        if platform.system() == "Windows":
            prefix = "start"
        else:
            prefix = "nohup"
            postfix = "&"

    subprocess.Popen(
        f"{prefix} emulator -avd {emulator} -netdelay none -netspeed full {postfix}",
        shell=True,
        cwd=emulator_path,
        text=True,
    )


def init_emulator(emulator_path):
    if not is_emulator_running():
        start_emulator(emulator_path)

    wait_for_device_to_boot()


def restart():
    print("Restarting device")
    subprocess.run(f"adb -e reboot", shell=True)
    wait_for_device_to_boot()


def capture_screenshot(folder, index):
    print("Capturing screenshot")
    filename = os.path.join(folder, f"{index}.png")
    subprocess.run(f"adb shell screencap -p /sdcard/screenshot.png", shell=True)
    subprocess.run(f'adb pull /sdcard/screenshot.png "{filename}"', shell=True)
    subprocess.run(f"adb shell rm /sdcard/screenshot.png", shell=True)


def stop_app(package):
    subprocess.run(f"adb shell am force-stop {package}", shell=True)


def launch_app(package):
    stop_app(package)
    time.sleep(0.2)
    start = subprocess.run(f"adb shell monkey -p {package} 1", shell=True, capture_output=True, text=True)
    if "No activities found to run" in start.stdout:
        raise Exception("Package not installed")
