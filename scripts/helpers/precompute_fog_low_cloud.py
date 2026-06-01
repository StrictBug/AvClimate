#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import tempfile
import time

import numpy as np
import pandas as pd

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from webapp.backend import main as backend

FOG_COLUMNS = (
    "year",
    "month",
    "hour",
    "TM_FULL",
    "AIR_TEMP",
    "DWPT",
    "VSBY",
    "AWS_VSBY",
    "PRCP_10",
    "WND_DIR",
    "WND_SPD",
    "PRCP_FM_09",
    "PRST_WX_PHENOM_1",
    "PRST_WX_PHENOM_2",
    "PRST_WX_DSC_1",
    "PRST_WX_DSC_2",
    "CEIL_CLD_AMT_1",
    "CEIL_CLD_AMT_2",
    "CEIL_CLD_HT_1",
    "CEIL_CLD_HT_2",
)

STATE_COLS = ["enso_norm", "iod_norm", "sam_norm", "mjo_norm"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Precompute fog/low-cloud artifacts by airport and climate state.")
    parser.add_argument("--icao", action="append", default=[], help="Only precompute this ICAO (repeat for multiple)")
    parser.add_argument(
        "--output-dir",
        default=backend.FOG_LOW_CLOUD_PRECOMPUTED_DIR,
        help="Output directory for per-airport JSON artifacts",
    )
    return parser.parse_args()


def write_json_atomic(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="fog_low_cloud_", suffix=".json.gz", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=6, mtime=0) as gz:
                data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
                gz.write(data)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def normalize_climate_df() -> pd.DataFrame:
    climate_df = backend.get_climate_df().to_pandas()
    if climate_df.empty:
        return pd.DataFrame(columns=["year", "month", "day", *STATE_COLS])

    climate = climate_df[["year", "month", "day", *STATE_COLS]].copy()
    climate["year"] = pd.to_numeric(climate["year"], errors="coerce")
    climate["month"] = pd.to_numeric(climate["month"], errors="coerce")
    climate["day"] = pd.to_numeric(climate["day"], errors="coerce")
    climate = climate.dropna(subset=["year", "month", "day"])
    if climate.empty:
        return pd.DataFrame(columns=["year", "month", "day", *STATE_COLS])

    climate[["year", "month", "day"]] = climate[["year", "month", "day"]].astype(int)
    for col in STATE_COLS:
        climate[col] = climate[col].fillna("").astype(str).str.strip().str.lower()
    return climate


def sanitize_obs(obs: pd.DataFrame) -> pd.DataFrame:
    work = obs.copy()
    work["year"] = pd.to_numeric(work["year"], errors="coerce")
    work["month"] = pd.to_numeric(work["month"], errors="coerce")
    work["hour"] = pd.to_numeric(work["hour"], errors="coerce")
    work["TM_FULL"] = pd.to_datetime(work["TM_FULL"], utc=True, errors="coerce")
    work["DWPT"] = pd.to_numeric(work["DWPT"], errors="coerce")
    work["WND_DIR"] = pd.to_numeric(work["WND_DIR"], errors="coerce")
    work["WND_SPD"] = pd.to_numeric(work["WND_SPD"], errors="coerce")
    work = work.dropna(subset=["year", "month", "TM_FULL"])
    if work.empty:
        return work

    work[["year", "month"]] = work[["year", "month"]].astype(int)
    work["day"] = work["TM_FULL"].dt.day.astype(int)
    return work


def add_mode_rows(
    rows_monthly: list[dict[str, object]],
    rows_hourly: list[dict[str, object]],
    rows_dewpoint: list[dict[str, object]],
    rows_wind: list[dict[str, object]],
    dataset: pd.DataFrame,
    *,
    icao: str,
    mode: str,
    state: dict[str, str],
) -> None:
    work, daily_flags, _ = backend.compute_fog_low_cloud_day_flags(dataset, icao)

    if not daily_flags.empty:
        monthly_counts = (
            daily_flags.groupby(["bom_year", "bom_month"], as_index=False)
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
        for row in monthly_counts.to_dict(orient="records"):
            rows_monthly.append(
                {
                    "bom_year": int(row["bom_year"]),
                    "bom_month": int(row["bom_month"]),
                    "mode": mode,
                    **state,
                    "Fog": float(row["Fog"]),
                    "below 2000ft": float(row["below 2000ft"]),
                    "below 1500ft": float(row["below 1500ft"]),
                    "below 1000ft": float(row["below 1000ft"]),
                    "below 500ft": float(row["below 500ft"]),
                }
            )

    if work.empty:
        return

    hourly_flags_month = work.groupby(["bom_day", "bom_year", "bom_month", "hour"], as_index=False).agg(
        Fog=("Fog", "any"),
        lowest_low_cloud_ceiling=("lowest_low_cloud_ceiling", "min"),
    )
    lowest_ceiling = pd.to_numeric(hourly_flags_month["lowest_low_cloud_ceiling"], errors="coerce")
    hourly_flags_month["below 2000ft"] = lowest_ceiling.lt(2000) & lowest_ceiling.ge(1500)
    hourly_flags_month["below 1500ft"] = lowest_ceiling.lt(1500) & lowest_ceiling.ge(1000)
    hourly_flags_month["below 1000ft"] = lowest_ceiling.lt(1000) & lowest_ceiling.ge(500)
    hourly_flags_month["below 500ft"] = lowest_ceiling.lt(500)

    hourly_counts = (
        hourly_flags_month.groupby(["bom_year", "bom_month", "hour"], as_index=False)
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
    for row in hourly_counts.to_dict(orient="records"):
        rows_hourly.append(
            {
                "bom_year": int(row["bom_year"]),
                "bom_month": int(row["bom_month"]),
                "hour": int(row["hour"]),
                "mode": mode,
                **state,
                "Fog": float(row["Fog"]),
                "below 2000ft": float(row["below 2000ft"]),
                "below 1500ft": float(row["below 1500ft"]),
                "below 1000ft": float(row["below 1000ft"]),
                "below 500ft": float(row["below 500ft"]),
            }
        )

    dewpoint_df = work.dropna(subset=["DWPT"]).copy()
    if not dewpoint_df.empty:
        dewpoint_df["is_fog"] = backend.fog_observation_mask(dewpoint_df)
        lowest_ceiling = backend.lowest_low_cloud_ceiling(dewpoint_df)
        category_masks = [
            ("Fog", dewpoint_df["is_fog"]),
            ("2000ft - 1500ft cloud", lowest_ceiling.lt(2000) & lowest_ceiling.ge(1500)),
            ("1500ft - 1000ft cloud", lowest_ceiling.lt(1500) & lowest_ceiling.ge(1000)),
            ("1000ft - 500ft cloud", lowest_ceiling.lt(1000) & lowest_ceiling.ge(500)),
            ("< 500ft cloud", lowest_ceiling.lt(500)),
        ]
        for label, mask in category_masks:
            masked = dewpoint_df[mask].copy()
            if masked.empty:
                continue
            grouped = (
                masked.groupby(["bom_year", "bom_month"], as_index=False)
                .agg(dwpt_sum=("DWPT", "sum"), dwpt_count=("DWPT", "count"))
            )
            for row in grouped.to_dict(orient="records"):
                rows_dewpoint.append(
                    {
                        "bom_year": int(row["bom_year"]),
                        "bom_month": int(row["bom_month"]),
                        "mode": mode,
                        **state,
                        "Category": label,
                        "dwpt_sum": float(row["dwpt_sum"]),
                        "dwpt_count": float(row["dwpt_count"]),
                    }
                )

    wind_df = work.dropna(subset=["WND_DIR", "WND_SPD"]).copy()
    if not wind_df.empty:
        wind_df["is_fog"] = backend.fog_observation_mask(wind_df)
        lowest_ceiling = backend.lowest_low_cloud_ceiling(wind_df)
        category_masks = {
            "Fog": wind_df["is_fog"],
            "2000ft - 1500ft cloud": lowest_ceiling.lt(2000) & lowest_ceiling.ge(1500),
            "1500ft - 1000ft cloud": lowest_ceiling.lt(1500) & lowest_ceiling.ge(1000),
            "1000ft - 500ft cloud": lowest_ceiling.lt(1000) & lowest_ceiling.ge(500),
            "< 500ft cloud": lowest_ceiling.lt(500),
        }
        for label, mask in category_masks.items():
            sub = wind_df[mask].copy()
            if sub.empty:
                continue
            sub["dir_bin_10"] = (((sub["WND_DIR"] + 5) % 360) // 10 * 10).astype(int)
            sub["speed_bin"] = np.floor(pd.to_numeric(sub["WND_SPD"], errors="coerce").clip(lower=0.0)).astype(int)
            grouped = sub.groupby(["bom_year", "bom_month", "dir_bin_10", "speed_bin"], as_index=False).size()
            grouped = grouped.rename(columns={"size": "Count"})
            for row in grouped.to_dict(orient="records"):
                rows_wind.append(
                    {
                        "bom_year": int(row["bom_year"]),
                        "bom_month": int(row["bom_month"]),
                        "mode": mode,
                        **state,
                        "Category": label,
                        "dir_bin_10": int(row["dir_bin_10"]),
                        "speed_bin": int(row["speed_bin"]),
                        "Count": float(row["Count"]),
                    }
                )


def payload_for_airport(icao: str, climate: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    airport_df = backend.load_airport_df(icao, FOG_COLUMNS)
    if airport_df.is_empty():
        return {"monthly": [], "hourly": [], "dewpoint": [], "wind": []}

    obs = airport_df.select(list(FOG_COLUMNS)).to_pandas()
    obs = sanitize_obs(obs)
    if obs.empty:
        return {"monthly": [], "hourly": [], "dewpoint": [], "wind": []}

    rows_monthly: list[dict[str, object]] = []
    rows_hourly: list[dict[str, object]] = []
    rows_dewpoint: list[dict[str, object]] = []
    rows_wind: list[dict[str, object]] = []

    all_modes = backend.split_fog_day_type_datasets(obs, icao)
    all_state = {"enso_norm": "all", "iod_norm": "all", "sam_norm": "all", "mjo_norm": "all"}
    for mode, (dataset, _) in all_modes.items():
        add_mode_rows(rows_monthly, rows_hourly, rows_dewpoint, rows_wind, dataset, icao=icao, mode=mode, state=all_state)

    if not climate.empty:
        merged = obs.merge(climate, on=["year", "month", "day"], how="inner")
        if not merged.empty:
            for state_key, state_df in merged.groupby(STATE_COLS, dropna=False):
                state = {
                    "enso_norm": str(state_key[0]),
                    "iod_norm": str(state_key[1]),
                    "sam_norm": str(state_key[2]),
                    "mjo_norm": str(state_key[3]),
                }
                mode_map = backend.split_fog_day_type_datasets(state_df, icao)
                for mode, (dataset, _) in mode_map.items():
                    add_mode_rows(rows_monthly, rows_hourly, rows_dewpoint, rows_wind, dataset, icao=icao, mode=mode, state=state)

    return {
        "monthly": rows_monthly,
        "hourly": rows_hourly,
        "dewpoint": rows_dewpoint,
        "wind": rows_wind,
    }


def main() -> int:
    args = parse_args()
    airports = tuple(sorted(set(args.icao))) if args.icao else backend.available_airports()
    if not airports:
        print("No airports found; no artifact created.")
        return 1

    climate = normalize_climate_df()
    os.makedirs(args.output_dir, exist_ok=True)
    started = time.perf_counter()
    written = 0

    for idx, icao in enumerate(airports, start=1):
        t0 = time.perf_counter()
        payload = payload_for_airport(icao, climate)
        total_rows = sum(len(payload.get(key, [])) for key in ("monthly", "hourly", "dewpoint", "wind"))
        if total_rows > 0:
            write_json_atomic(os.path.join(args.output_dir, f"{icao}.json.gz"), payload)
            written += 1
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        print(f"[{idx}/{len(airports)}] {icao}: rows={total_rows} elapsed_ms={elapsed_ms}")

    total_elapsed = int((time.perf_counter() - started) * 1000)
    print(f"Wrote {written} airports to {args.output_dir} in {total_elapsed} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
