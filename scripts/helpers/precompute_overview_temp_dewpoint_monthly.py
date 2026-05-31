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

TEMP_COLUMNS = (
    "year",
    "month",
    "TM_FULL",
    "AIR_TEMP",
    "DWPT",
    "PRCP_FM_09",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Precompute overview temperature/dewpoint monthly aggregates by airport and climate state.")
    parser.add_argument(
        "--icao",
        action="append",
        default=[],
        help="Only precompute this ICAO (repeat flag for multiple airports). Default: all available airports.",
    )
    parser.add_argument(
        "--output-dir",
        default=backend.OVERVIEW_TEMP_DEWPOINT_DIR,
        help="Output directory for per-airport JSON artifacts (default: statistics/precomputed/overview_temp_dewpoint)",
    )
    return parser.parse_args()


def write_json_atomic(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="overview_temp_dewpoint_", suffix=".json", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _prepare_obs(df: pd.DataFrame, icao: str) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    work = df.copy()
    work["TM_FULL"] = pd.to_datetime(work["TM_FULL"], utc=True, errors="coerce")
    work["AIR_TEMP"] = pd.to_numeric(work["AIR_TEMP"], errors="coerce")
    work["DWPT"] = pd.to_numeric(work["DWPT"], errors="coerce")
    work["PRCP_FM_09"] = pd.to_numeric(work["PRCP_FM_09"], errors="coerce")
    work["year"] = pd.to_numeric(work["year"], errors="coerce")
    work["month"] = pd.to_numeric(work["month"], errors="coerce")
    work = work.dropna(subset=["TM_FULL", "year", "month"])
    if work.empty:
        return pd.DataFrame()

    work[["year", "month"]] = work[["year", "month"]].astype(int)

    tz_name = backend.airport_timezone(icao)
    local_ts = work["TM_FULL"].dt.tz_convert(tz_name)
    bom_day_ts = (local_ts - pd.Timedelta(hours=9)).dt.floor("D")

    work["bom_day"] = bom_day_ts.dt.date
    work["bom_year"] = bom_day_ts.dt.year.astype(int)
    work["bom_month"] = bom_day_ts.dt.month.astype(int)
    work["day"] = work["TM_FULL"].dt.day.astype(int)
    return work


def _monthly_records(obs: pd.DataFrame) -> list[dict[str, object]]:
    if obs.empty:
        return []

    grouped_daily = (
        obs.groupby(
            ["bom_day", "bom_year", "bom_month", "enso_norm", "iod_norm", "sam_norm", "mjo_norm"],
            as_index=False,
        )
        .agg(
            daily_max_t=("AIR_TEMP", "max"),
            daily_min_t=("AIR_TEMP", "min"),
            daily_max_td=("DWPT", "max"),
            daily_min_td=("DWPT", "min"),
            daily_precip_mm=("PRCP_FM_09", "max"),
        )
    )
    if grouped_daily.empty:
        return []

    grouped_daily = grouped_daily.dropna(subset=["daily_max_t", "daily_min_t", "daily_max_td", "daily_min_td", "daily_precip_mm"])
    if grouped_daily.empty:
        return []

    monthly = (
        grouped_daily.groupby(["bom_year", "bom_month", "enso_norm", "iod_norm", "sam_norm", "mjo_norm"], as_index=False)
        .agg(
            **{
                "Avg Daily Max T": ("daily_max_t", "mean"),
                "Avg Daily Min T": ("daily_min_t", "mean"),
                "Avg Daily Max Td": ("daily_max_td", "mean"),
                "Avg Daily Min Td": ("daily_min_td", "mean"),
                "monthly_precip_mm": ("daily_precip_mm", "sum"),
            }
        )
        .sort_values(["bom_year", "bom_month", "enso_norm", "iod_norm", "sam_norm", "mjo_norm"])
    )

    records: list[dict[str, object]] = []
    for row in monthly.to_dict(orient="records"):
        records.append(
            {
                "bom_year": int(row["bom_year"]),
                "bom_month": int(row["bom_month"]),
                "enso_norm": str(row["enso_norm"]),
                "iod_norm": str(row["iod_norm"]),
                "sam_norm": str(row["sam_norm"]),
                "mjo_norm": str(row["mjo_norm"]),
                "Avg Daily Max T": float(row["Avg Daily Max T"]),
                "Avg Daily Min T": float(row["Avg Daily Min T"]),
                "Avg Daily Max Td": float(row["Avg Daily Max Td"]),
                "Avg Daily Min Td": float(row["Avg Daily Min Td"]),
                "monthly_precip_mm": float(row["monthly_precip_mm"]),
            }
        )
    return records


def monthly_records_for_airport(icao: str) -> list[dict[str, object]]:
    airport_df = backend.load_airport_df(icao, TEMP_COLUMNS)
    if airport_df.is_empty():
        return []

    obs = airport_df.select(list(TEMP_COLUMNS)).to_pandas()
    obs = _prepare_obs(obs, icao)
    if obs.empty:
        return []

    all_state = obs.copy()
    all_state["enso_norm"] = "all"
    all_state["iod_norm"] = "all"
    all_state["sam_norm"] = "all"
    all_state["mjo_norm"] = "all"
    records = _monthly_records(all_state)

    climate_df = backend.get_climate_df().to_pandas()
    if climate_df.empty:
        return records

    climate = climate_df[["year", "month", "day", "enso_norm", "iod_norm", "sam_norm", "mjo_norm"]].copy()
    climate["year"] = pd.to_numeric(climate["year"], errors="coerce")
    climate["month"] = pd.to_numeric(climate["month"], errors="coerce")
    climate["day"] = pd.to_numeric(climate["day"], errors="coerce")
    climate = climate.dropna(subset=["year", "month", "day"])
    if climate.empty:
        return records

    climate[["year", "month", "day"]] = climate[["year", "month", "day"]].astype(int)
    for col in ("enso_norm", "iod_norm", "sam_norm", "mjo_norm"):
        climate[col] = climate[col].fillna("").astype(str).str.strip().str.lower()

    merged = obs.merge(climate, on=["year", "month", "day"], how="inner")
    if merged.empty:
        return records

    records.extend(_monthly_records(merged))
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
