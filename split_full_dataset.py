import os
import shutil
import pyarrow as pa
import pyarrow.dataset as ds

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
SOURCE_PARQUET = os.path.join(ROOT_DIR, "ADAM_full.parquet")
OUTPUT_DIR = os.path.join(ROOT_DIR, "data", "by_icao")


def split_by_icao() -> None:
    print("🚀 Starting split of ADAM_full.parquet by ICAO...")

    if not os.path.exists(SOURCE_PARQUET):
        print(f"❌ Missing source parquet: {SOURCE_PARQUET}")
        return

    if os.path.isdir(OUTPUT_DIR):
        print(f"🧹 Removing existing output directory: {OUTPUT_DIR}")
        shutil.rmtree(OUTPUT_DIR)

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    dataset = ds.dataset(SOURCE_PARQUET, format="parquet")
    partition_schema = pa.schema([("TARGET_ICAO", pa.string())])

    print("📦 Writing partitioned parquet files...")
    ds.write_dataset(
        dataset,
        base_dir=OUTPUT_DIR,
        format="parquet",
        partitioning=ds.partitioning(partition_schema, flavor="hive"),
        existing_data_behavior="overwrite_or_ignore",
        max_open_files=32,
    )

    partitions = [
        name for name in os.listdir(OUTPUT_DIR)
        if name.startswith("TARGET_ICAO=") and os.path.isdir(os.path.join(OUTPUT_DIR, name))
    ]
    print("-" * 30)
    print(f"✅ Split complete: {len(partitions)} ICAO partitions")
    print(f"📁 Output directory: {OUTPUT_DIR}")
    print("-" * 30)


if __name__ == "__main__":
    split_by_icao()
