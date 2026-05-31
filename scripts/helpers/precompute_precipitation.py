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

PRECIP_COLUMNS = (
    "year",
    "month",
    "TM_FULL",
    "WND_DIR",
    "VSBY",
    "AWS_VSBY",
    "PRCP_10",
    "PRCP_FM_09",
    "PRST_WX_DSC_1",
    "PRST_WX_PHENOM_1",
    "PRST_WX_DSC_2",
    "PRST_WX_PHENOM_2",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Precompute precipitation section monthly and split figures by airport and climate state.")
    parser.add_argument(
        "--icao",
        action="append",
        default=[],
        help="Only precompute this ICAO (repeat flag for multiple airports). Default: all available airports.",
    )
    parser.add_argument(
        "--output-dir",
        default=backend.PRECIPITATION_PRECOMPUTED_DIR,
        help="Output directory for per-airport JSON artifacts (default: statistics/precomputed/precipitation)",
    )
    return parser.parse_args()


def write_json_atomic(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="precipitation_", suffix=".json", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _prepare_climate_df() -> pd.DataFrame:
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


def _monthly_rows_for_state(df_state: pd.DataFrame, icao: str, state: dict[str, str]) -> list[dict[str, object]]:
    _, daily_flags = backend.compute_daily_weather_flags(df_state, icao)
    if daily_flags.empty:
        return []

    monthly_counts = (
        daily_flags.groupby(["bom_year", "bom_month"], as_index=False)
        .agg(
            Rain=("Rain", "sum"),
            Thunderstorm=("Thunderstorm", "sum"),
        )
        .sort_values(["bom_year", "bom_month"])
    )

    rows: list[dict[str, object]] = []
    for row in monthly_counts.to_dict(orient="records"):
        rows.append(
            {
                "bom_year": int(row["bom_year"]),
                "bom_month": int(row["bom_month"]),
                "enso_norm": state["enso_norm"],
                "iod_norm": state["iod_norm"],
                "sam_norm": state["sam_norm"],
                "mjo_norm": state["mjo_norm"],
                "Rain": float(row["Rain"]),
                "Thunderstorm": float(row["Thunderstorm"]),
            }
        )
    return rows


def build_airport_payload(icao: str, climate: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    airport_df = backend.load_airport_df(icao, PRECIP_COLUMNS)
    if airport_df.is_empty():
        return {}

    precip_df = airport_df.select(list(PRECIP_COLUMNS)).to_pandas()
    if precip_df.empty:
        return {}

    precip_df["year"] = pd.to_numeric(precip_df["year"], errors="coerce")
    precip_df["month"] = pd.to_numeric(precip_df["month"], errors="coerce")
    precip_df["TM_FULL"] = pd.to_datetime(precip_df["TM_FULL"], utc=True, errors="coerce")
    precip_df = precip_df.dropna(subset=["year", "month", "TM_FULL"])
    if precip_df.empty:
        return {}

    precip_df[["year", "month"]] = precip_df[["year", "month"]].astype(int)
    precip_df["day"] = precip_df["TM_FULL"].dt.day.astype(int)

    monthly_rows: list[dict[str, object]] = []
    all_state = {
        "enso_norm": "all",
        "iod_norm": "all",
        "sam_norm": "all",
        "mjo_norm": "all",
    }
    monthly_rows.extend(_monthly_rows_for_state(precip_df, icao, all_state))

    split_rows: list[dict[str, object]] = []
    vis_df = precip_df.copy()
    vis_df["chart_vsby"] = vis_df[["VSBY", "AWS_VSBY"]].apply(pd.to_numeric, errors="coerce").min(axis=1)
    vis_df = vis_df.dropna(subset=["WND_DIR", "chart_vsby"]).copy()
    if vis_df.empty:
        return {"monthly": monthly_rows, "split": split_rows}

    precip_tokens = ["RA", "DZ", "SN", "GS", "GR", "PL", "SH", "TS"]
    precip_fields = ["PRST_WX_DSC_1", "PRST_WX_PHENOM_1", "PRST_WX_DSC_2", "PRST_WX_PHENOM_2"]
    is_precip = backend.token_mask_from_fields(vis_df, precip_fields, precip_tokens)
    if "PRCP_10" in vis_df.columns:
        is_precip = is_precip | (pd.to_numeric(vis_df["PRCP_10"], errors="coerce").fillna(0.0) > 0.2)
    precip_obs = vis_df[is_precip].copy()
    if precip_obs.empty:
        return {"monthly": monthly_rows, "split": split_rows}

    precip_obs["dir_bin_10"] = (((precip_obs["WND_DIR"] + 5) % 360) // 10 * 10).astype(int)

    # All-state split rows
    all_split = (
        precip_obs.groupby(["year", "month", "dir_bin_10"], as_index=False)
        .agg(
            denom=("chart_vsby", "size"),
            lt3=("chart_vsby", lambda s: float((s < 3.0).sum())),
            lt5=("chart_vsby", lambda s: float((s < 5.0).sum())),
            lt7=("chart_vsby", lambda s: float((s < 7.0).sum())),
            lt9=("chart_vsby", lambda s: float((s < 9.0).sum())),
        )
    )
    for row in all_split.to_dict(orient="records"):
        split_rows.append(
            {
                "year": int(row["year"]),
                "month": int(row["month"]),
                "enso_norm": "all",
                "iod_norm": "all",
                "sam_norm": "all",
                "mjo_norm": "all",
                "dir_bin_10": int(row["dir_bin_10"]),
                "denom": float(row["denom"]),
                "lt3": float(row["lt3"]),
                "lt5": float(row["lt5"]),
                "lt7": float(row["lt7"]),
                "lt9": float(row["lt9"]),
            }
        )

    if climate.empty:
        return {"monthly": monthly_rows, "split": split_rows}

    merged = precip_df.merge(climate, on=["year", "month", "day"], how="inner")
    if not merged.empty:
        # Monthly rows for each climate state.
        for state_vals, state_df in merged.groupby(["enso_norm", "iod_norm", "sam_norm", "mjo_norm"], as_index=False):
            state = {
                "enso_norm": str(state_vals[0]),
                "iod_norm": str(state_vals[1]),
                "sam_norm": str(state_vals[2]),
                "mjo_norm": str(state_vals[3]),
            }
            monthly_rows.extend(_monthly_rows_for_state(state_df, icao, state))

    merged_split = precip_obs.merge(climate, on=["year", "month", "day"], how="inner")
    if not merged_split.empty:
        grouped = (
            merged_split.groupby(
                ["year", "month", "enso_norm", "iod_norm", "sam_norm", "mjo_norm", "dir_bin_10"],
                as_index=False,
            )
            .agg(
                denom=("chart_vsby", "size"),
                lt3=("chart_vsby", lambda s: float((s < 3.0).sum())),
                lt5=("chart_vsby", lambda s: float((s < 5.0).sum())),
                lt7=("chart_vsby", lambda s: float((s < 7.0).sum())),
                lt9=("chart_vsby", lambda s: float((s < 9.0).sum())),
            )
        )
        for row in grouped.to_dict(orient="records"):
            split_rows.append(
                {
                    "year": int(row["year"]),
                    "month": int(row["month"]),
                    "enso_norm": str(row["enso_norm"]),
                    "iod_norm": str(row["iod_norm"]),
                    "sam_norm": str(row["sam_norm"]),
                    "mjo_norm": str(row["mjo_norm"]),
                    "dir_bin_10": int(row["dir_bin_10"]),
                    "denom": float(row["denom"]),
                    "lt3": float(row["lt3"]),
                    "lt5": float(row["lt5"]),
                    "lt7": float(row["lt7"]),
                    "lt9": float(row["lt9"]),
                }
            )

    return {"monthly": monthly_rows, "split": split_rows}


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

    climate = _prepare_climate_df()
    started = time.perf_counter()
    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    written = 0

    for idx, icao in enumerate(airports, start=1):
        t0 = time.perf_counter()
        payload = build_airport_payload(icao, climate)
        if payload.get("monthly") or payload.get("split"):
            write_json_atomic(os.path.join(output_dir, f"{icao}.json"), payload)
            written += 1
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        print(
            f"[{idx}/{total}] {icao}: monthly_rows={len(payload.get('monthly', []))} "
            f"split_rows={len(payload.get('split', []))} elapsed_ms={elapsed_ms}"
        )

    total_elapsed = int((time.perf_counter() - started) * 1000)
    print(f"Wrote {written} airports to {output_dir} in {total_elapsed} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
