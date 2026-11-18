import csv
from pathlib import Path

def check_processed_data(name: str):
    """Check the processed data files for consistency and completeness."""
    DATA_DIR = Path(f"data/processed/{name}")

    files = [
        "movies.csv",
        "people.csv",
        "movie_people.csv"
    ]

    for filename in files:

        path = DATA_DIR / filename

        print(f"\n========== {filename} ==========")

        with open(path, "r", encoding="utf-8") as file:

            reader = csv.DictReader(file)

            print("Columns:", reader.fieldnames)

            count = 0

            for row in reader:
                if count < 3:
                    print(row)

                count += 1

            print("Total records:", count)

if __name__ == "__main__":
    check_processed_data("imdb")
    check_processed_data("india")