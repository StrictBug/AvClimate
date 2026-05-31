#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time

import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from webapp.backend import main as backend

RAIN_COLUMNS = (
    "year",
    "month",
    "TM_FULL",
    "PRCP_FM_09",
    "PRST_WX_DSC_1",
    "PRST_WX_PHENOM_1",
    "PRST_WX_DSC_2",
    "PRST_WX_PHENOM_2",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Precompute overview rain/thunder monthly aggregates by airport and climate state.")
    parser.add_argument(
        "--icao",
        action="append",
        default=[],
        help="Only precompute this ICAO (repeat flag for multiple airports). Default: all available airports.",
    )
    parser.add_argument(
        "--output-dir",
        default=backend.OVERVIEW_RAIN_THUNDER_MONTHLY_DIR,
        help="Output directory for per-airport JSON artifacts (default: statistics/precomputed/overview_rain_thunder_monthly)",
    )
    return parser.parse_args()


def write_json_atomic(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="overview_rain_thunder_monthly_", suffix=".json", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def monthly_records_for_airport(icao: str) -> list[dict[str, object]]:
    airport_df = backend.load_airport_df(icao, RAIN_COLUMNS)
    if airport_df.is_empty():
        return []

    rain_df = airport_df.select(list(RAIN_COLUMNS)).to_pandas()
    if rain_df.empty:
        return []

    _, daily_flags = backend.compute_daily_weather_flags(rain_df, icao)
    if daily_flags.empty:
        return []

    records: list[dict[str, object]] = []

    monthly_all = (
        daily_flags.groupby(["bom_year", "bom_month"], as_index=False)
        .agg(
            Rain=("Rain", "sum"),
            Thunderstorm=("Thunderstorm", "sum"),
        )
        .sort_values(["bom_year", "bom_month"])
    )
    for row in monthly_all.to_dict(orient="records"):
        records.append(
            {
                "bom_year": int(row["bom_year"]),
                "bom_month": int(row["bom_month"]),
                "enso_norm": "all",
                "iod_norm": "all",
                "sam_norm": "all",
                "mjo_norm": "all",
                "Rain": float(row["Rain"]),
                "Thunderstorm": float(row["Thunderstorm"]),
            }
        )

    climate_df = backend.get_climate_df().to_pandas()
    if climate_df.empty:
        return records

    daily = daily_flags.copy()
    daily["bom_day"] = pd.to_datetime(daily["bom_day"], errors="coerce")
    daily = daily.dropna(subset=["bom_day"])
    if daily.empty:
        return []
    daily["day"] = daily["bom_day"].dt.day.astype(int)

    climate = climate_df[["year", "month", "day", "enso_norm", "iod_norm", "sam_norm", "mjo_norm"]].copy()
    climate["year"] = pd.to_numeric(climate["year"], errors="coerce")
    climate["month"] = pd.to_numeric(climate["month"], errors="coerce")
    climate["day"] = pd.to_numeric(climate["day"], errors="coerce")
    climate = climate.dropna(subset=["year", "month", "day"])
    climate[["year", "month", "day"]] = climate[["year", "month", "day"]].astype(int)

    merged = daily.merge(
        climate,
        left_on=["bom_year", "bom_month", "day"],
        right_on=["year", "month", "day"],
        how="inner",
    )
    if merged.empty:
        return records

    for col in ("enso_norm", "iod_norm", "sam_norm", "mjo_norm"):
        merged[col] = merged[col].fillna("").astype(str).str.strip().str.lower()

    monthly_counts = (
        merged.groupby(["bom_year", "bom_month", "enso_norm", "iod_norm", "sam_norm", "mjo_norm"], as_index=False)
        .agg(
            Rain=("Rain", "sum"),
            Thunderstorm=("Thunderstorm", "sum"),
        )
        .sort_values(["bom_year", "bom_month", "enso_norm", "iod_norm", "sam_norm", "mjo_norm"])
    )

    for row in monthly_counts.to_dict(orient="records"):
        records.append(
            {
                "bom_year": int(row["bom_year"]),
                "bom_month": int(row["bom_month"]),
                "enso_norm": str(row["enso_norm"]),
                "iod_norm": str(row["iod_norm"]),
                "sam_norm": str(row["sam_norm"]),
                "mjo_norm": str(row["mjo_norm"]),
                "Rain": float(row["Rain"]),
                "Thunderstorm": float(row["Thunderstorm"]),
            }
        )
    return records


def main() -> int:
    args = parse_args()
    if args.icao:
        airports = tuple(sorted(set(args.icao)))
    else:
        airports = backend.available_airports()

    total = len(airports)
    if total == 0:
        print("No airports found; no artifact created.")
        return 1

    started = time.perf_counter()
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    written = 0

    for idx, icao in enumerate(airports, start=1):
        t0 = time.perf_counter()
        records = monthly_records_for_airport(icao)
        if records:
            write_json_atomic(os.path.join(output_dir, f"{icao}.json"), records)
            written += 1
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        print(f"[{idx}/{total}] {icao}: monthly_rows={len(records)} elapsed_ms={elapsed_ms}")

    total_elapsed = int((time.perf_counter() - started) * 1000)
    print(f"Wrote {written} airports to {output_dir} in {total_elapsed} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
