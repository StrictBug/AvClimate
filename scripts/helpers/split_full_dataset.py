import os

from split_by_icao import main as split_single_file_partitions


HELPERS_DIR = os.path.abspath(os.path.dirname(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HELPERS_DIR, "..", ".."))
SOURCE_PARQUET = os.path.join(PROJECT_ROOT, "ADAM_full.parquet")


def split_by_icao() -> None:
    print("🚀 Starting split of ADAM_full.parquet by ICAO...")

    if not os.path.exists(SOURCE_PARQUET):
        print(f"❌ Missing source parquet: {SOURCE_PARQUET}")
        return

    split_single_file_partitions()


if __name__ == "__main__":
    split_by_icao()
