import os
import shutil

import polars as pl


OUT_DIR = os.path.join("data", "by_icao")


def partition_dirs() -> list[str]:
    if not os.path.isdir(OUT_DIR):
        return []

    return sorted(
        name for name in os.listdir(OUT_DIR)
        if name.startswith("TARGET_ICAO=") and os.path.isdir(os.path.join(OUT_DIR, name))
    )


def consolidate_partition(partition_name: str) -> bool:
    partition_dir = os.path.join(OUT_DIR, partition_name)
    parquet_files = sorted(
        os.path.join(partition_dir, name)
        for name in os.listdir(partition_dir)
        if name.endswith(".parquet") and not name.endswith(".tmp.parquet")
    )

    if not parquet_files:
        return False

    if len(parquet_files) == 1 and os.path.basename(parquet_files[0]) == "part-0.parquet":
        return False

    tmp_path = os.path.join(partition_dir, "part-0.tmp.parquet")
    out_path = os.path.join(partition_dir, "part-0.parquet")
    if os.path.exists(tmp_path):
        os.remove(tmp_path)

    pl.read_parquet(parquet_files).write_parquet(tmp_path, compression="snappy")
    os.replace(tmp_path, out_path)

    for path in parquet_files:
        if path != out_path:
            os.remove(path)

    for name in os.listdir(partition_dir):
        extra_path = os.path.join(partition_dir, name)
        if name != "part-0.parquet" and os.path.isfile(extra_path):
            os.remove(extra_path)
        if os.path.isdir(extra_path):
            shutil.rmtree(extra_path)

    return True


def main() -> None:
    partitions = partition_dirs()
    if not partitions:
        print(f"❌  No ICAO partitions found in {OUT_DIR}")
        return

    changed = 0
    for idx, partition_name in enumerate(partitions, start=1):
        if consolidate_partition(partition_name):
            changed += 1
        if idx % 20 == 0 or idx == len(partitions):
            print(f"    [{idx}/{len(partitions)}] checked (updated: {changed})")

    print(f"\n✅  Consolidation complete — {changed} ICAO folders rewritten to a single parquet file")


if __name__ == "__main__":
    main()