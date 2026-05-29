"""Convert ADAM lightning CSV into partitioned per-ICAO parquet files.

Input:  ADAM_ltgn/ADAM_ltgn.csv
Output: data/lightning_by_icao/TARGET_ICAO={ICAO}/part-*.parquet
"""

import os
import shutil

import polars as pl

SOURCE = os.path.join("ADAM_ltgn", "ADAM_ltgn.csv")
OUT_DIR = os.path.join("data", "lightning_by_icao")


def build_lazy_base() -> pl.LazyFrame:
    raw = pl.scan_csv(SOURCE, ignore_errors=True)

    # TM format example: 26/FEB/08 01:01:24.851000000 AM
    return (
        raw.rename({"long": "LONG"})
        .with_columns(
            [
                pl.col("NEARBY_ICAO").cast(pl.Utf8, strict=False).str.strip_chars().alias("TARGET_ICAO"),
                pl.col("TM")
                .cast(pl.Utf8, strict=False)
                .str.strptime(pl.Datetime(time_zone="UTC"), format="%d/%b/%y %I:%M:%S%.f %p", strict=False)
                .alias("LTGN_TM"),
                pl.col("LAT").cast(pl.Float64, strict=False).alias("LAT"),
                pl.col("LONG").cast(pl.Float64, strict=False).alias("LONG"),
            ]
        )
        .select(["TARGET_ICAO", "LTGN_TM", "LAT", "LONG"])
        .drop_nulls(["TARGET_ICAO", "LTGN_TM", "LAT", "LONG"])
        .filter(pl.col("TARGET_ICAO") != "")
    )


def main() -> None:
    if not os.path.exists(SOURCE):
        print(f"ERROR: {SOURCE} not found.")
        return

    if os.path.isdir(OUT_DIR):
        print(f"Removing existing {OUT_DIR}...")
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR, exist_ok=True)

    print("Converting and partitioning lightning data (one pass)...")
    (
        build_lazy_base().sink_parquet(
            pl.PartitionBy(OUT_DIR, key="TARGET_ICAO", include_key=True),
            compression="snappy",
            mkdir=True,
        )
    )
    print(f"Done. Partitioned parquet written to {OUT_DIR}/")


if __name__ == "__main__":
    main()
