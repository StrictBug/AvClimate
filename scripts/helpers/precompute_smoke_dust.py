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

SMOKE_COLUMNS = (
    "year",
    "month",
    "hour",
    "TM_FULL",
    "PRST_WX_PHENOM_1",
    "PRST_WX_PHENOM_2",
    "WND_SPD",
    "DWPT",
    "WND_DIR",
)

STATE_COLS = ["enso_norm", "iod_norm", "sam_norm", "mjo_norm"]
SMOKE_TOKENS = ["FU", "DU", "SA", "VA"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Precompute smoke/dust artifacts by airport and climate state.")
    parser.add_argument("--icao", action="append", default=[], help="Only precompute this ICAO (repeat for multiple)")
    parser.add_argument(
        "--output-dir",
        default=backend.SMOKE_DUST_PRECOMPUTED_DIR,
        help="Output directory for per-airport JSON artifacts",
    )
    return parser.parse_args()


def write_json_atomic(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="smoke_dust_", suffix=".json.gz", dir=os.path.dirname(path))
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
    work["WND_SPD"] = pd.to_numeric(work["WND_SPD"], errors="coerce")
    work["DWPT"] = pd.to_numeric(work["DWPT"], errors="coerce")
    work["WND_DIR"] = pd.to_numeric(work["WND_DIR"], errors="coerce")
    work = work.dropna(subset=["year", "month", "TM_FULL"])
    if work.empty:
        return work

    work[["year", "month"]] = work[["year", "month"]].astype(int)
    work["day"] = work["TM_FULL"].dt.day.astype(int)
    return work


def classify_phenomenon(df: pd.DataFrame) -> pd.DataFrame:
    mask = backend.token_mask_from_fields(df, ["PRST_WX_PHENOM_1", "PRST_WX_PHENOM_2"], SMOKE_TOKENS)
    dust_df = df[mask].copy()
    if dust_df.empty:
        return dust_df

    def get_phenom(row: pd.Series) -> str:
        p1 = str(row.get("PRST_WX_PHENOM_1", "")).upper()
        p2 = str(row.get("PRST_WX_PHENOM_2", "")).upper()
        for code in SMOKE_TOKENS:
            if code in p1 or code in p2:
                return code
        return "Other"

    dust_df["Phenomenon"] = dust_df.apply(get_phenom, axis=1)
    return dust_df[dust_df["Phenomenon"].isin(SMOKE_TOKENS)].copy()


def add_state_rows(
    rows_monthly: list[dict[str, object]],
    rows_hourly: list[dict[str, object]],
    rows_scatter: list[dict[str, object]],
    rows_radial: list[dict[str, object]],
    dataset: pd.DataFrame,
    *,
    state: dict[str, str],
) -> None:
    dust_df = classify_phenomenon(dataset)
    if dust_df.empty:
        return

    monthly = (
        dust_df.groupby(["year", "month", "Phenomenon"], as_index=False)
        .size()
        .rename(columns={"size": "Count"})
    )
    for row in monthly.to_dict(orient="records"):
        rows_monthly.append(
            {
                "year": int(row["year"]),
                "month": int(row["month"]),
                **state,
                "Phenomenon": str(row["Phenomenon"]),
                "Count": float(row["Count"]),
            }
        )

    hourly = (
        dust_df.groupby(["year", "month", "hour", "Phenomenon"], as_index=False)
        .size()
        .rename(columns={"size": "Count"})
    )
    for row in hourly.to_dict(orient="records"):
        rows_hourly.append(
            {
                "year": int(row["year"]),
                "month": int(row["month"]),
                "hour": int(row["hour"]),
                **state,
                "Phenomenon": str(row["Phenomenon"]),
                "Count": float(row["Count"]),
            }
        )

    scatter = dust_df.dropna(subset=["DWPT", "WND_SPD"]).copy()
    if not scatter.empty:
        for row in scatter[["year", "month", "Phenomenon", "DWPT", "WND_SPD"]].to_dict(orient="records"):
            rows_scatter.append(
                {
                    "year": int(row["year"]),
                    "month": int(row["month"]),
                    **state,
                    "Phenomenon": str(row["Phenomenon"]),
                    "DWPT": float(row["DWPT"]),
                    "WND_SPD": float(row["WND_SPD"]),
                }
            )

    radial = dust_df.dropna(subset=["WND_DIR", "WND_SPD"]).copy()
    if not radial.empty:
        radial["dir_bin_10"] = (((radial["WND_DIR"] + 5) % 360) // 10 * 10).astype(int)
        radial["speed_bin"] = np.floor(pd.to_numeric(radial["WND_SPD"], errors="coerce").clip(lower=0.0)).astype(int)
        grouped = radial.groupby(["year", "month", "Phenomenon", "dir_bin_10", "speed_bin"], as_index=False).size()
        grouped = grouped.rename(columns={"size": "Count"})
        for row in grouped.to_dict(orient="records"):
            rows_radial.append(
                {
                    "year": int(row["year"]),
                    "month": int(row["month"]),
                    **state,
                    "Phenomenon": str(row["Phenomenon"]),
                    "dir_bin_10": int(row["dir_bin_10"]),
                    "speed_bin": int(row["speed_bin"]),
                    "Count": float(row["Count"]),
                }
            )


def payload_for_airport(icao: str, climate: pd.DataFrame) -> dict[str, list[dict[str, object]]]:
    airport_df = backend.load_airport_df(icao, SMOKE_COLUMNS)
    if airport_df.is_empty():
        return {"monthly": [], "hourly": [], "scatter": [], "radial": []}

    obs = airport_df.select(list(SMOKE_COLUMNS)).to_pandas()
    obs = sanitize_obs(obs)
    if obs.empty:
        return {"monthly": [], "hourly": [], "scatter": [], "radial": []}

    rows_monthly: list[dict[str, object]] = []
    rows_hourly: list[dict[str, object]] = []
    rows_scatter: list[dict[str, object]] = []
    rows_radial: list[dict[str, object]] = []

    all_state = {"enso_norm": "all", "iod_norm": "all", "sam_norm": "all", "mjo_norm": "all"}
    add_state_rows(rows_monthly, rows_hourly, rows_scatter, rows_radial, obs, state=all_state)

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
                add_state_rows(rows_monthly, rows_hourly, rows_scatter, rows_radial, state_df, state=state)

    return {
        "monthly": rows_monthly,
        "hourly": rows_hourly,
        "scatter": rows_scatter,
        "radial": rows_radial,
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
        total_rows = sum(len(payload.get(key, [])) for key in ("monthly", "hourly", "scatter", "radial"))
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
