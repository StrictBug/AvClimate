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

WIND_GALE_COLUMNS = (
    "year",
    "month",
    "TM_FULL",
    "WND_SPD",
    "MAX_WND_GUST_10",
    "PRCP_10",
    "PRST_WX_DSC_1",
    "PRST_WX_PHENOM_1",
    "PRST_WX_DSC_2",
    "PRST_WX_PHENOM_2",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Precompute wind-tab monthly gale split aggregates by airport and climate state.")
    parser.add_argument(
        "--icao",
        action="append",
        default=[],
        help="Only precompute this ICAO (repeat flag for multiple airports). Default: all available airports.",
    )
    parser.add_argument(
        "--output-dir",
        default=backend.WIND_GALE_MONTHLY_DIR,
        help="Output directory for per-airport JSON artifacts (default: statistics/precomputed/wind_gale_monthly)",
    )
    return parser.parse_args()


def write_json_atomic(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="wind_gale_monthly_", suffix=".json", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _normalize_climate_df() -> pd.DataFrame:
    climate_df = backend.get_climate_df().to_pandas()
    if climate_df.empty:
        return pd.DataFrame(columns=["year", "month", "day", "enso_norm", "iod_norm", "sam_norm", "mjo_norm"])

    climate = climate_df[["year", "month", "day", "enso_norm", "iod_norm", "sam_norm", "mjo_norm"]].copy()
    climate["year"] = pd.to_numeric(climate["year"], errors="coerce")
    climate["month"] = pd.to_numeric(climate["month"], errors="coerce")
    climate["day"] = pd.to_numeric(climate["day"], errors="coerce")
    climate = climate.dropna(subset=["year", "month", "day"])
    if climate.empty:
        return pd.DataFrame(columns=["year", "month", "day", "enso_norm", "iod_norm", "sam_norm", "mjo_norm"])

    climate[["year", "month", "day"]] = climate[["year", "month", "day"]].astype(int)
    for col in ("enso_norm", "iod_norm", "sam_norm", "mjo_norm"):
        climate[col] = climate[col].fillna("").astype(str).str.strip().str.lower()
    return climate


def _gale_obs_with_category(obs_df: pd.DataFrame, icao: str) -> pd.DataFrame:
    gale_mask = (obs_df["WND_SPD"].fillna(-9999) > 17.49) | (obs_df["MAX_WND_GUST_10"].fillna(-9999) > 21.09)
    gale_obs = obs_df[gale_mask].copy()
    if gale_obs.empty:
        return gale_obs

    dsc = (gale_obs["PRST_WX_DSC_1"].fillna("").astype(str) + " " + gale_obs["PRST_WX_DSC_2"].fillna("").astype(str)).str.upper()
    phenom = (gale_obs["PRST_WX_PHENOM_1"].fillna("").astype(str) + " " + gale_obs["PRST_WX_PHENOM_2"].fillna("").astype(str)).str.upper()
    prcp_10 = pd.to_numeric(gale_obs["PRCP_10"], errors="coerce").fillna(0.0)

    is_ts = backend.lightning_proximity_mask(gale_obs, icao, time_field="TM_FULL")
    is_shra = (dsc.str.contains("SH", regex=False) & phenom.str.contains("RA", regex=False)) | (prcp_10 > 0.2)

    gale_obs["Category"] = "No wx"
    gale_obs.loc[is_shra, "Category"] = "SHRA"
    gale_obs.loc[is_ts, "Category"] = "TS"
    return gale_obs


def _year_month_category_rows(
    gale_obs: pd.DataFrame,
    years: list[int],
    months: list[int],
) -> pd.DataFrame:
    non_ts_cats = ["No wx", "SHRA"]

    if gale_obs.empty:
        monthly_counts = pd.DataFrame(columns=["year", "month", "Category", "Count"])
    else:
        monthly_counts = (
            gale_obs.groupby(["year", "month", "Category"]).size().reset_index(name="Count")
        )

    full_non_ts = pd.MultiIndex.from_product([sorted(years), months, non_ts_cats], names=["year", "month", "Category"])
    non_ts = (
        monthly_counts[monthly_counts["Category"].isin(non_ts_cats)]
        .set_index(["year", "month", "Category"])
        .reindex(full_non_ts, fill_value=0)
        .reset_index()
    )

    ts_years = sorted([y for y in years if y >= backend.LIGHTNING_STATS_MIN_YEAR])
    if ts_years:
        full_ts = pd.MultiIndex.from_product([ts_years, months, ["TS"]], names=["year", "month", "Category"])
        ts = (
            monthly_counts[monthly_counts["Category"] == "TS"]
            .set_index(["year", "month", "Category"])
            .reindex(full_ts, fill_value=0)
            .reset_index()
        )
        combined = pd.concat([non_ts, ts], ignore_index=True)
    else:
        combined = non_ts

    combined["Count"] = pd.to_numeric(combined["Count"], errors="coerce").fillna(0.0)
    return combined


def monthly_records_for_airport(icao: str, climate: pd.DataFrame) -> list[dict[str, object]]:
    airport_df = backend.load_airport_df(icao, WIND_GALE_COLUMNS)
    if airport_df.is_empty():
        return []

    obs = airport_df.select(list(WIND_GALE_COLUMNS)).to_pandas()
    if obs.empty:
        return []

    obs["year"] = pd.to_numeric(obs["year"], errors="coerce")
    obs["month"] = pd.to_numeric(obs["month"], errors="coerce")
    obs["WND_SPD"] = pd.to_numeric(obs["WND_SPD"], errors="coerce")
    obs["MAX_WND_GUST_10"] = pd.to_numeric(obs["MAX_WND_GUST_10"], errors="coerce")
    obs["TM_FULL"] = pd.to_datetime(obs["TM_FULL"], utc=True, errors="coerce")
    obs = obs.dropna(subset=["year", "month", "TM_FULL"])
    if obs.empty:
        return []

    obs[["year", "month"]] = obs[["year", "month"]].astype(int)
    obs["day"] = obs["TM_FULL"].dt.day.astype(int)

    months = list(range(1, 13))
    records: list[dict[str, object]] = []

    all_years = sorted(obs["year"].unique().tolist())
    all_gale_obs = _gale_obs_with_category(obs, icao)
    all_rows = _year_month_category_rows(all_gale_obs, all_years, months)
    all_rows["enso_norm"] = "all"
    all_rows["iod_norm"] = "all"
    all_rows["sam_norm"] = "all"
    all_rows["mjo_norm"] = "all"
    records.extend(all_rows.to_dict(orient="records"))

    if climate.empty:
        return [
            {
                "year": int(row["year"]),
                "month": int(row["month"]),
                "enso_norm": str(row["enso_norm"]),
                "iod_norm": str(row["iod_norm"]),
                "sam_norm": str(row["sam_norm"]),
                "mjo_norm": str(row["mjo_norm"]),
                "Category": str(row["Category"]),
                "Count": float(row["Count"]),
            }
            for row in records
        ]

    merged = obs.merge(climate, on=["year", "month", "day"], how="inner")
    if merged.empty:
        return [
            {
                "year": int(row["year"]),
                "month": int(row["month"]),
                "enso_norm": str(row["enso_norm"]),
                "iod_norm": str(row["iod_norm"]),
                "sam_norm": str(row["sam_norm"]),
                "mjo_norm": str(row["mjo_norm"]),
                "Category": str(row["Category"]),
                "Count": float(row["Count"]),
            }
            for row in records
        ]

    state_cols = ["enso_norm", "iod_norm", "sam_norm", "mjo_norm"]
    grouped_states = merged.groupby(state_cols, dropna=False)
    for state_key, state_obs in grouped_states:
        state_df = state_obs.copy()
        state_years = sorted(state_df["year"].unique().tolist())
        if not state_years:
            continue

        gale_obs = _gale_obs_with_category(state_df, icao)
        state_rows = _year_month_category_rows(gale_obs, state_years, months)
        state_rows["enso_norm"] = str(state_key[0])
        state_rows["iod_norm"] = str(state_key[1])
        state_rows["sam_norm"] = str(state_key[2])
        state_rows["mjo_norm"] = str(state_key[3])
        records.extend(state_rows.to_dict(orient="records"))

    payload: list[dict[str, object]] = []
    for row in records:
        payload.append(
            {
                "year": int(row["year"]),
                "month": int(row["month"]),
                "enso_norm": str(row["enso_norm"]),
                "iod_norm": str(row["iod_norm"]),
                "sam_norm": str(row["sam_norm"]),
                "mjo_norm": str(row["mjo_norm"]),
                "Category": str(row["Category"]),
                "Count": float(row["Count"]),
            }
        )
    return payload


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

    climate = _normalize_climate_df()

    written = 0
    for idx, icao in enumerate(airports, start=1):
        t0 = time.perf_counter()
        rows = monthly_records_for_airport(icao, climate)
        if rows:
            write_json_atomic(os.path.join(output_dir, f"{icao}.json"), rows)
            written += 1
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        print(f"[{idx}/{total}] {icao}: rows={len(rows)} elapsed_ms={elapsed_ms}")

    total_elapsed = int((time.perf_counter() - started) * 1000)
    print(f"Wrote {written} airports to {output_dir} in {total_elapsed} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
