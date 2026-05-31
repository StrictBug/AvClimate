#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.parse
import urllib.request
from typing import Any

import numpy as np

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check that overview rain_thunder Rain values match precipitation monthly_precip Rain values."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--icao", default="YMML", help="Airport ICAO")
    parser.add_argument("--year-start", type=int, default=2000)
    parser.add_argument("--year-end", type=int, default=2025)
    parser.add_argument("--month-start", default="Jan")
    parser.add_argument("--month-end", default="Dec")
    parser.add_argument("--season", default="all")
    parser.add_argument("--enso", default="all")
    parser.add_argument("--iod", default="all")
    parser.add_argument("--sam", default="all")
    parser.add_argument("--mjo", default="all")
    parser.add_argument("--tolerance", type=float, default=1e-6)
    return parser.parse_args()


def fetch_json(base_url: str, params: dict[str, str]) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{base_url}/api/charts?{query}") as resp:
        return json.loads(resp.read().decode("utf-8"))


def decode_plotly_y(values: Any) -> list[float]:
    if isinstance(values, list):
        return [float(v) for v in values]
    if isinstance(values, dict) and "bdata" in values:
        dtype = np.dtype(values.get("dtype", "f8"))
        arr = np.frombuffer(base64.b64decode(values["bdata"]), dtype=dtype)
        return arr.astype(float).tolist()
    return []


def extract_rain_values(payload: dict[str, Any], figure_id: str) -> dict[str, float]:
    for item in payload.get("figures", []):
        if item.get("id") != figure_id:
            continue
        fig = item.get("figure", {})
        for trace in fig.get("data", []):
            if trace.get("name") != "Rain":
                continue
            x_vals = trace.get("x", [])
            y_vals = decode_plotly_y(trace.get("y", []))
            return {str(k): float(v) for k, v in zip(x_vals, y_vals)}
    return {}


def main() -> int:
    args = parse_args()

    common = {
        "icao": args.icao,
        "yearStart": str(args.year_start),
        "yearEnd": str(args.year_end),
        "monthStart": args.month_start,
        "monthEnd": args.month_end,
        "hourStart": "0",
        "hourEnd": "23",
        "invertMonth": "false",
        "invertHour": "false",
        "fogMonthlyMode": "all",
        "fogHourlyMode": "all",
        "fogWindMode": "all",
        "fogDewpointMode": "all",
        "season": args.season,
        "enso": args.enso,
        "iod": args.iod,
        "sam": args.sam,
        "mjo": args.mjo,
        "includeMetrics": "false",
    }

    overview = fetch_json(args.base_url, {**common, "section": "overview", "figureIds": "rain_thunder"})
    precip = fetch_json(args.base_url, {**common, "section": "precipitation"})

    rain_overview = extract_rain_values(overview, "rain_thunder")
    rain_precip = extract_rain_values(precip, "monthly_precip")

    if not rain_overview or not rain_precip:
        print("ERROR: missing Rain series in one of the payloads")
        return 2

    max_abs_diff = 0.0
    for month in MONTHS:
        diff = abs(rain_overview.get(month, 0.0) - rain_precip.get(month, 0.0))
        if diff > max_abs_diff:
            max_abs_diff = diff

    print(f"icao={args.icao} max_abs_diff={max_abs_diff:.9f} tolerance={args.tolerance:.9f}")
    print("pairs:")
    for month in MONTHS:
        print(
            f"  {month}: overview={rain_overview.get(month, 0.0):.3f} "
            f"precipitation={rain_precip.get(month, 0.0):.3f}"
        )

    if max_abs_diff > args.tolerance:
        print("FAIL: overview and precipitation rain values diverge")
        return 1

    print("PASS: overview and precipitation rain values match")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
