import os
import csv

# Define the constant for the input path
DATASET_PATH = r"G:\Shared drives\ChatGPT - Winter Research\Norbert\Datasets"
OUTPUT_CSV = "dataset.csv"


def find_largest_number(files):
    largest_number = 0
    for filename in files:
        try:
            number = int(filename.split(".")[0])
            largest_number = max(largest_number, number)
        except ValueError:
            pass
    return largest_number


def process_directories(root_path):
    data = []

    for dirpath, _, filenames in os.walk(root_path):
        if dirpath != root_path:
            if filenames:
                dirname = os.path.basename(dirpath)
                print("Processing", dirname)
                largest_number = find_largest_number(filenames)
                package, id, *rest = dirname.split(" ")
                goal = " ".join(rest)
                data.append((package, id, goal, largest_number))

    return data


def save_to_csv(data, csv_filename):
    with open(csv_filename, "w", newline="") as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(["Package", "Use Case ID", "Goal", "Steps"])
        csv_writer.writerows(data)


if __name__ == "__main__":
    directory_data = process_directories(DATASET_PATH)
    save_to_csv(directory_data, OUTPUT_CSV)
    print("Data saved to", OUTPUT_CSV)
