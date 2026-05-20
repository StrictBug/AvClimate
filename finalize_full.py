import polars as pl
import os

def finalize_full():
    print("🚀 Starting full dataset conversion (Streaming Mode)...")

    source_csv = "ADAMoutput.csv"
    if not os.path.exists(source_csv):
        print(f"❌ Error: {source_csv} not found!")
        return

    lazy_df = pl.scan_csv(source_csv, infer_schema_length=10000, ignore_errors=True)

    processed_query = (
        lazy_df
        .with_columns([
            pl.col("TM_FULL").str.to_datetime("%Y-%m-%d %H:%M:%S", strict=False)
        ])
        .filter(pl.col("TM_FULL").is_not_null())
        .with_columns([
            pl.col(["WND_DIR", "WND_SPD", "MAX_WND_GUST_10", "AIR_TEMP",
                    "DWPT", "QNH", "VSBY", "CEIL_CLD_HT_1", "CEIL_CLD_HT_2"]).cast(pl.Float64, strict=False),

            pl.col(["PRST_WX_DSC_1", "PRST_WX_PHENOM_1", "PRST_WX_DSC_2",
                    "PRST_WX_PHENOM_2", "CEIL_CLD_AMT_1", "CEIL_CLD_AMT_2"]).cast(pl.String),

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
