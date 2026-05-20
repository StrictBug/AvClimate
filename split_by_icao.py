"""
Split ADAM_full.parquet into one parquet file per aerodrome.

Output: data/by_icao/{ICAO}.parquet

Each file contains only the rows for that aerodrome and is small enough
(~7 MB average) to load on demand in the web app, avoiding the need to
hold the entire 1.5 GB dataset in RAM at startup.
"""
import os
import polars as pl

SOURCE = "ADAM_full.parquet"
OUT_DIR = os.path.join("data", "by_icao")


def main() -> None:
    if not os.path.exists(SOURCE):
        print(f"❌  {SOURCE} not found. Run finalize_full.py first.")
        return

    os.makedirs(OUT_DIR, exist_ok=True)

    print("🔍  Scanning for unique aerodromes...")
    lazy = pl.scan_parquet(SOURCE)
    icaos: list[str] = (
        lazy.select("TARGET_ICAO")
        .unique()
        .collect()["TARGET_ICAO"]
        .drop_nulls()
        .sort()
        .to_list()
    )
    print(f"    Found {len(icaos)} aerodromes.")

    already_done = {
        f[:-8] for f in os.listdir(OUT_DIR) if f.endswith(".parquet")
    }
    remaining = [i for i in icaos if i not in already_done]
    if already_done:
        print(f"    {len(already_done)} already split — resuming with {len(remaining)} remaining.")

    for idx, icao in enumerate(remaining, start=1):
        out_path = os.path.join(OUT_DIR, f"{icao}.parquet")
        (
            lazy.filter(pl.col("TARGET_ICAO") == icao)
            .sink_parquet(out_path, compression="snappy")
        )
        if idx % 20 == 0 or idx == len(remaining):
            print(f"    [{idx}/{len(remaining)}] done (last: {icao})")

    total = len(already_done) + len(remaining)
    print(f"\n✅  Split complete — {total} files in {OUT_DIR}/")

    sizes = [
        os.path.getsize(os.path.join(OUT_DIR, f))
        for f in os.listdir(OUT_DIR)
        if f.endswith(".parquet")
    ]
    if sizes:
        avg_mb = (sum(sizes) / len(sizes)) / (1024 * 1024)
        total_mb = sum(sizes) / (1024 * 1024)
        print(f"    Avg file size: {avg_mb:.1f} MB  |  Total: {total_mb:.0f} MB")


if __name__ == "__main__":
    main()
