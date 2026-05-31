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

FOG_COLUMNS = (
    "year",
    "month",
    "TM_FULL",
    "AIR_TEMP",
    "DWPT",
    "VSBY",
    "AWS_VSBY",
    "PRCP_10",
    "PRCP_FM_09",
    "PRST_WX_DSC_1",
    "PRST_WX_PHENOM_1",
    "PRST_WX_DSC_2",
    "PRST_WX_PHENOM_2",
    "CEIL_CLD_AMT_1",
    "CEIL_CLD_AMT_2",
    "CEIL_CLD_HT_1",
    "CEIL_CLD_HT_2",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Precompute overview fog monthly aggregates by airport.")
    parser.add_argument(
        "--icao",
        action="append",
        default=[],
        help="Only precompute this ICAO (repeat flag for multiple airports). Default: all available airports.",
    )
    parser.add_argument(
        "--output-dir",
        default=backend.OVERVIEW_FOG_MONTHLY_DIR,
        help="Output directory for per-airport JSON artifacts (default: statistics/precomputed/overview_fog_monthly)",
    )
    return parser.parse_args()


def write_json_atomic(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="overview_fog_monthly_", suffix=".json", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def monthly_records_from_daily_flags(daily_flags):
    if daily_flags.empty:
        return []

    group_cols = ["bom_year", "bom_month"]
    for col in ("enso_norm", "iod_norm", "sam_norm", "mjo_norm"):
        if col in daily_flags.columns:
            group_cols.append(col)

    monthly_counts = (
        daily_flags.groupby(group_cols, as_index=False)
        .agg(
            Fog=("Fog", "sum"),
            **{
                "below 2000ft": ("below 2000ft", "sum"),
                "below 1500ft": ("below 1500ft", "sum"),
                "below 1000ft": ("below 1000ft", "sum"),
                "below 500ft": ("below 500ft", "sum"),
            },
        )
    )

    records = []
    for row in monthly_counts.to_dict(orient="records"):
        records.append(
            {
                "bom_year": int(row["bom_year"]),
                "bom_month": int(row["bom_month"]),
                "enso_norm": str(row.get("enso_norm", "all")),
                "iod_norm": str(row.get("iod_norm", "all")),
                "sam_norm": str(row.get("sam_norm", "all")),
                "mjo_norm": str(row.get("mjo_norm", "all")),
                "Fog": float(row["Fog"]),
                "below 2000ft": float(row["below 2000ft"]),
                "below 1500ft": float(row["below 1500ft"]),
                "below 1000ft": float(row["below 1000ft"]),
                "below 500ft": float(row["below 500ft"]),
            }
        )
    return records


def build_airport_records(icao: str) -> dict[str, list[dict[str, float]]]:
    airport_df = backend.load_airport_df(icao, FOG_COLUMNS)
    if airport_df.is_empty():
        return {}

    fog_df = airport_df.select(list(FOG_COLUMNS)).to_pandas()
    if fog_df.empty:
        return {}

    _, fog_daily, _ = backend.compute_fog_low_cloud_day_flags(fog_df, icao)
    if fog_daily.empty:
        return {}

    _, rain_daily = backend.compute_daily_weather_flags(fog_df, icao)
    if rain_daily.empty:
        fog_daily["is_rain_day"] = False
    else:
        rain_by_day = rain_daily[["bom_day", "Rain"]].rename(columns={"Rain": "is_rain_day"})
        fog_daily = fog_daily.merge(rain_by_day, on="bom_day", how="left")
        fog_daily["is_rain_day"] = fog_daily["is_rain_day"].fillna(False)

    mode_daily_map = {
        "all": fog_daily.copy(),
        "rain": fog_daily[fog_daily["is_rain_day"]].copy(),
        "non_rain": fog_daily[~fog_daily["is_rain_day"]].copy(),
    }

    climate_df = backend.get_climate_df().to_pandas()
    climate_df = climate_df[["year", "month", "day", "enso_norm", "iod_norm", "sam_norm", "mjo_norm"]].copy() if not climate_df.empty else climate_df
    if not climate_df.empty:
        climate_df["year"] = pd.to_numeric(climate_df["year"], errors="coerce")
        climate_df["month"] = pd.to_numeric(climate_df["month"], errors="coerce")
        climate_df["day"] = pd.to_numeric(climate_df["day"], errors="coerce")
        climate_df = climate_df.dropna(subset=["year", "month", "day"])
        climate_df[["year", "month", "day"]] = climate_df[["year", "month", "day"]].astype(int)
        for col in ("enso_norm", "iod_norm", "sam_norm", "mjo_norm"):
            climate_df[col] = climate_df[col].fillna("").astype(str).str.strip().str.lower()

    output: dict[str, list[dict[str, float]]] = {}
    for mode, daily in mode_daily_map.items():
        if daily.empty:
            output[mode] = []
            continue

        daily_all = daily.copy()
        daily_all["enso_norm"] = "all"
        daily_all["iod_norm"] = "all"
        daily_all["sam_norm"] = "all"
        daily_all["mjo_norm"] = "all"
        mode_records = monthly_records_from_daily_flags(daily_all)

        if not climate_df.empty:
            daily_climate = daily.copy()
            daily_climate["bom_day"] = pd.to_datetime(daily_climate["bom_day"], errors="coerce")
            daily_climate = daily_climate.dropna(subset=["bom_day"])
            if not daily_climate.empty:
                daily_climate["day"] = daily_climate["bom_day"].dt.day.astype(int)
                merged = daily_climate.merge(
                    climate_df,
                    left_on=["bom_year", "bom_month", "day"],
                    right_on=["year", "month", "day"],
                    how="inner",
                )
                if not merged.empty:
                    mode_records.extend(monthly_records_from_daily_flags(merged))

        output[mode] = mode_records

    return output


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
        mode_records = build_airport_records(icao)
        if mode_records:
            write_json_atomic(os.path.join(output_dir, f"{icao}.json"), mode_records)
            written += 1
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        all_rows = len(mode_records.get("all", [])) if mode_records else 0
        print(f"[{idx}/{total}] {icao}: monthly_rows={all_rows} elapsed_ms={elapsed_ms}")

    total_elapsed = int((time.perf_counter() - started) * 1000)
    print(f"Wrote {written} airports to {output_dir} in {total_elapsed} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
