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

WIND_COLUMNS = (
    "year",
    "month",
    "TM_FULL",
    "WND_DIR",
    "WND_SPD",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Precompute overview wind rose aggregates by airport and climate state.")
    parser.add_argument(
        "--icao",
        action="append",
        default=[],
        help="Only precompute this ICAO (repeat flag for multiple airports). Default: all available airports.",
    )
    parser.add_argument(
        "--output-dir",
        default=backend.OVERVIEW_WIND_ROSE_DIR,
        help="Output directory for per-airport JSON artifacts (default: statistics/precomputed/overview_wind_rose)",
    )
    return parser.parse_args()


def write_json_atomic(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="overview_wind_rose_", suffix=".json", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _group_counts(obs: pd.DataFrame) -> list[dict[str, object]]:
    if obs.empty:
        return []

    work = obs.copy()
    work["dir_bin"] = ((work["WND_DIR"] + 11.25) % 360 // 22.5 * 22.5).astype(float)
    work["Speed Range"] = work["WND_SPD"].apply(backend.categorize_speed)

    grouped = (
        work.groupby(
            ["bom_year", "bom_month", "enso_norm", "iod_norm", "sam_norm", "mjo_norm", "dir_bin", "Speed Range"],
            as_index=False,
        )
        .size()
        .rename(columns={"size": "Count"})
        .sort_values(["bom_year", "bom_month", "enso_norm", "iod_norm", "sam_norm", "mjo_norm", "dir_bin", "Speed Range"])
    )

    records: list[dict[str, object]] = []
    for row in grouped.to_dict(orient="records"):
        records.append(
            {
                "bom_year": int(row["bom_year"]),
                "bom_month": int(row["bom_month"]),
                "enso_norm": str(row["enso_norm"]),
                "iod_norm": str(row["iod_norm"]),
                "sam_norm": str(row["sam_norm"]),
                "mjo_norm": str(row["mjo_norm"]),
                "dir_bin": float(row["dir_bin"]),
                "Speed Range": str(row["Speed Range"]),
                "Count": float(row["Count"]),
            }
        )
    return records


def monthly_records_for_airport(icao: str) -> list[dict[str, object]]:
    airport_df = backend.load_airport_df(icao, WIND_COLUMNS)
    if airport_df.is_empty():
        return []

    obs = airport_df.select(list(WIND_COLUMNS)).to_pandas()
    if obs.empty:
        return []

    obs["year"] = pd.to_numeric(obs["year"], errors="coerce")
    obs["month"] = pd.to_numeric(obs["month"], errors="coerce")
    obs["WND_DIR"] = pd.to_numeric(obs["WND_DIR"], errors="coerce")
    obs["WND_SPD"] = pd.to_numeric(obs["WND_SPD"], errors="coerce")
    obs["TM_FULL"] = pd.to_datetime(obs["TM_FULL"], utc=True, errors="coerce")
    obs = obs.dropna(subset=["year", "month", "TM_FULL", "WND_DIR", "WND_SPD"])
    if obs.empty:
        return []

    obs[["year", "month"]] = obs[["year", "month"]].astype(int)
    obs["bom_year"] = obs["year"]
    obs["bom_month"] = obs["month"]
    obs["day"] = obs["TM_FULL"].dt.day.astype(int)

    all_state = obs.copy()
    all_state["enso_norm"] = "all"
    all_state["iod_norm"] = "all"
    all_state["sam_norm"] = "all"
    all_state["mjo_norm"] = "all"
    records = _group_counts(all_state)

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

    records.extend(_group_counts(merged))
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
