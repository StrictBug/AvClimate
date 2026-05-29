import os
import sys

import polars as pl


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
    print("🚀 Starting full dataset conversion (Streaming Mode)...")
    if len(sys.argv) > 1:
        source_csv = sys.argv[1]
    else:
        source_csv = "ADAMoutput.csv"
    if not os.path.exists(source_csv):
        print(f"❌ Error: {source_csv} not found!")
        return

    lazy_df = pl.scan_csv(
        source_csv,
        has_header=False,
        skip_rows=1,
        new_columns=CSV_COLUMNS,
        infer_schema=False,
        ignore_errors=True,
    )

    processed_query = (
        lazy_df
        .with_columns([
            pl.col("TM_FULL").str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False)
        ])
        .filter(pl.col("TM_FULL").is_not_null())
        .with_columns([
            pl.col(FLOAT_COLUMNS).cast(pl.Float64, strict=False),
            pl.col(STRING_COLUMNS).cast(pl.String),

            pl.col("TM_FULL").dt.year().alias("year"),
            pl.col("TM_FULL").dt.month().alias("month"),
            pl.col("TM_FULL").dt.hour().alias("hour")
        ])
    )

    output_name = "ADAM_full.parquet"
    print("📦 Processing data in chunks... please wait.")

    processed_query.sink_parquet(
        output_name,
        compression="snappy",
        row_group_size=100_000
    )

    if os.path.exists(output_name):
        size_mb = os.path.getsize(output_name) / (1024 * 1024)
        print("-" * 30)
        print(f"✅ Success! Created {output_name}")
        print(f"📦 File Size: {size_mb:.2f} MB")
        print("-" * 30)
    else:
        print("❌ Sink failed to create the file.")

if __name__ == "__main__":
    finalize_full()
