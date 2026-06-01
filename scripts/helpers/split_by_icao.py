"""
Split ADAM_full.parquet into one parquet partition per aerodrome.

Output: data/by_icao/TARGET_ICAO={ICAO}/part-0.parquet

This version streams the source parquet in batches and writes directly to the
per-ICAO files, avoiding a full-table unique scan on the 77M-row dataset.
"""
import os

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


SOURCE = "ADAM_full.parquet"
OUT_DIR = os.path.join("data", "by_icao")
BATCH_SIZE = 250_000


def partition_dir(icao: str) -> str:
    return os.path.join(OUT_DIR, f"TARGET_ICAO={icao}")


def partition_file(icao: str) -> str:
    return os.path.join(partition_dir(icao), "part-0.parquet")


def partition_tmp_file(icao: str) -> str:
    return os.path.join(partition_dir(icao), "part-0.tmp.parquet")


def open_writer(icao: str, schema: pa.Schema, writers: dict[str, pq.ParquetWriter]) -> pq.ParquetWriter:
    writer = writers.get(icao)
    if writer is None:
        out_dir = partition_dir(icao)
        os.makedirs(out_dir, exist_ok=True)
        tmp_path = partition_tmp_file(icao)
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        writer = pq.ParquetWriter(tmp_path, schema, compression="snappy")
        writers[icao] = writer
    return writer


def main() -> None:
    if not os.path.exists(SOURCE):
        print(f"❌  {SOURCE} not found. Run scripts/helpers/finalize_full.py first.")
        return

    os.makedirs(OUT_DIR, exist_ok=True)

    parquet_file = pq.ParquetFile(SOURCE)
    writers: dict[str, pq.ParquetWriter] = {}
    row_counts: dict[str, int] = {}
    batch_count = 0

    print("🔍  Splitting parquet by TARGET_ICAO in batches...")
    try:
        for batch in parquet_file.iter_batches(batch_size=BATCH_SIZE):
            batch_count += 1
            icao_values = batch.column("TARGET_ICAO")
            for icao in pc.unique(icao_values).to_pylist():
                if icao is None:
                    continue

                icao_scalar = pa.scalar(icao, type=icao_values.type)
                mask = pc.equal(icao_values, icao_scalar)
                subset = batch.filter(mask)
                if subset.num_rows == 0:
                    continue

                writer = open_writer(str(icao), subset.schema, writers)
                writer.write_table(pa.Table.from_batches([subset]))
                row_counts[icao] = row_counts.get(icao, 0) + subset.num_rows

            if batch_count % 20 == 0:
                print(f"    Processed {batch_count} batches")
    finally:
        for writer in writers.values():
            writer.close()

    total_files = 0
    for icao in list(writers.keys()):
        tmp_path = partition_tmp_file(icao)
        final_path = partition_file(icao)
        if os.path.exists(tmp_path):
            os.replace(tmp_path, final_path)
            total_files += 1

    print(f"\n✅  Split complete — {total_files} files in {OUT_DIR}/")

    if row_counts:
        total_rows = sum(row_counts.values())
        avg_rows = total_rows / len(row_counts)
        print(f"    ICAOs: {len(row_counts)}  |  Rows: {total_rows:,}  |  Avg rows/ICAO: {avg_rows:,.0f}")


if __name__ == "__main__":
    main()
