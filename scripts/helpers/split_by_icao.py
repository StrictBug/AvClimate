"""
Split ADAM_full.parquet into one parquet partition per aerodrome.

Output: data/by_icao/TARGET_ICAO={ICAO}/part-0.parquet

Each partition contains only the rows for that aerodrome and matches the
directory layout expected by the web app backend.
"""
import os
import polars as pl

SOURCE = "ADAM_full.parquet"
OUT_DIR = os.path.join("data", "by_icao")


def partition_dir(icao: str) -> str:
    return os.path.join(OUT_DIR, f"TARGET_ICAO={icao}")


def partition_file(icao: str) -> str:
    return os.path.join(partition_dir(icao), "part-0.parquet")


def partition_complete(icao: str) -> bool:
    out_path = partition_file(icao)
    return os.path.exists(out_path) and os.path.getsize(out_path) > 0


def main() -> None:
    if not os.path.exists(SOURCE):
        print(f"❌  {SOURCE} not found. Run scripts/helpers/finalize_full.py first.")
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

    already_done = {icao for icao in icaos if partition_complete(icao)}
    remaining = [icao for icao in icaos if icao not in already_done]
    if already_done:
        print(f"    {len(already_done)} already split — resuming with {len(remaining)} remaining.")

    for idx, icao in enumerate(remaining, start=1):
        out_dir = partition_dir(icao)
        os.makedirs(out_dir, exist_ok=True)
        out_path = partition_file(icao)
        tmp_path = os.path.join(out_dir, "part-0.tmp.parquet")
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        (
            lazy.filter(pl.col("TARGET_ICAO") == icao)
            .sink_parquet(tmp_path, compression="snappy")
        )
        os.replace(tmp_path, out_path)
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
