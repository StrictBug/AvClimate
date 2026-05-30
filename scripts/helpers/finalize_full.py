import os
import sys

import polars as pl
import pyarrow.parquet as pq


CSV_COLUMNS = [
    "TARGET_ICAO",
    "STN_NUM",
    "TM_FULL",
    "WND_DIR",
    "WND_SPD",
    "MAX_WND_GUST_10",
    "VSBY",
    "AWS_VSBY",
    "AIR_TEMP",
    "DWPT",
    "QNH",
    "PRST_WX_DSC_1",
    "PRST_WX_PHENOM_1",
    "PRST_WX_DSC_2",
    "PRST_WX_PHENOM_2",
    "RE_WX_DSC_1",
    "RE_WX_PHENOM_1",
    "RE_WX_DSC_2",
    "RE_WX_PHENOM_2",
    "RE_WX_DSC_3",
    "RE_WX_PHENOM_3",
    "PRCP_10",
    "PRCP_FM_09",
    "CEIL_CLD_AMT_1",
    "CEIL_CLD_HT_1",
    "CEIL_CLD_AMT_2",
    "CEIL_CLD_HT_2",
]

FLOAT_COLUMNS = [
    "WND_DIR",
    "WND_SPD",
    "MAX_WND_GUST_10",
    "AIR_TEMP",
    "DWPT",
    "QNH",
    "VSBY",
    "AWS_VSBY",
    "PRCP_10",
    "PRCP_FM_09",
    "CEIL_CLD_HT_1",
    "CEIL_CLD_HT_2",
]

STRING_COLUMNS = [
    "TARGET_ICAO",
    "STN_NUM",
    "PRST_WX_DSC_1",
    "PRST_WX_PHENOM_1",
    "PRST_WX_DSC_2",
    "PRST_WX_PHENOM_2",
    "RE_WX_DSC_1",
    "RE_WX_PHENOM_1",
    "RE_WX_DSC_2",
    "RE_WX_PHENOM_2",
    "RE_WX_DSC_3",
    "RE_WX_PHENOM_3",
    "CEIL_CLD_AMT_1",
    "CEIL_CLD_AMT_2",
]

def finalize_full():
    print("🚀 Starting full dataset conversion (Batched Mode)...")
    if len(sys.argv) > 1:
        source_csv = sys.argv[1]
    else:
        source_csv = "ADAMoutput_full.csv"
    if not os.path.exists(source_csv):
        print(f"❌ Error: {source_csv} not found!")
        return

    output_name = "ADAM_full.parquet"
    tmp_name = output_name + ".tmp"
    print("📦 Processing data in batches... please wait.")

    reader = (
        pl.scan_csv(
            source_csv,
            has_header=False,
            skip_rows=1,
            new_columns=CSV_COLUMNS,
            infer_schema=False,
            ignore_errors=True,
        )
        .collect_batches()
    )

    parquet_writer = None
    total_rows = 0
    batch_num = 0

    try:
        for raw in reader:
            processed = (
                raw.lazy()
                .with_columns([
                    pl.col("TM_FULL").str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False)
                ])
                .filter(pl.col("TM_FULL").is_not_null())
                .with_columns([
                    pl.col(FLOAT_COLUMNS).cast(pl.Float64, strict=False),
                    pl.col(STRING_COLUMNS).cast(pl.String),
                    pl.col("TM_FULL").dt.year().alias("year"),
                    pl.col("TM_FULL").dt.month().alias("month"),
                    pl.col("TM_FULL").dt.hour().alias("hour"),
                ])
                .collect()
            )

            arrow_table = processed.to_arrow()
            if parquet_writer is None:
                parquet_writer = pq.ParquetWriter(
                    tmp_name,
                    arrow_table.schema,
                    compression="snappy",
                )
            parquet_writer.write_table(arrow_table)
            total_rows += len(processed)
            batch_num += 1
            if batch_num % 200 == 0:
                print(f"    Batch {batch_num}: {len(processed):,} rows written  (total: {total_rows:,})")
    finally:
        if parquet_writer is not None:
            parquet_writer.close()

    if total_rows == 0:
        print("❌ No rows written.")
        return

    os.replace(tmp_name, output_name)
    size_mb = os.path.getsize(output_name) / (1024 * 1024)
    print("-" * 30)
    print(f"✅ Success! Created {output_name}")
    print(f"📦 File Size: {size_mb:.2f} MB  |  Total rows: {total_rows:,}")
    print("-" * 30)

if __name__ == "__main__":
    finalize_full()
