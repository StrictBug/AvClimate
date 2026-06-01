#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import os
import tempfile
import time
from typing import Any

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FOG_DIR = os.path.join(REPO_ROOT, "statistics", "precomputed", "fog_low_cloud")

MODES = ("all", "rain", "non_rain")
FAMILIES = ("hourly", "dewpoint", "wind")
STATE_KEYS = ("enso_norm", "iod_norm", "sam_norm", "mjo_norm")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split fog precomputed shards into mode and all-state files.")
    parser.add_argument("--output-dir", default=FOG_DIR, help="Fog precomputed directory")
    parser.add_argument("--icao", action="append", default=[], help="Only process this ICAO (repeatable)")
    return parser.parse_args()


def read_json_gz(path: str) -> Any:
    if not os.path.exists(path):
        return None
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def write_json_gz_atomic(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="fog_wind_mode_", suffix=".json.gz", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=6, mtime=0) as gz:
                gz.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def discover_icaos(output_dir: str) -> list[str]:
    items: list[str] = []
    for name in sorted(os.listdir(output_dir)):
        path = os.path.join(output_dir, name)
        if not os.path.isdir(path):
            continue
        has_family = any(os.path.exists(os.path.join(path, f"{family}.json.gz")) for family in FAMILIES)
        if has_family:
            items.append(name)
    return items


def split_rows(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets = {mode: [] for mode in MODES}
    for row in rows:
        if not isinstance(row, dict):
            continue
        mode = str(row.get("mode", "")).strip().lower()
        if mode in buckets:
            buckets[mode].append(row)
    return buckets


def is_all_state_row(row: dict[str, Any]) -> bool:
    return all(str(row.get(key, "")).strip().lower() == "all" for key in STATE_KEYS)


def main() -> int:
    args = parse_args()
    output_dir = os.path.abspath(args.output_dir)
    if not os.path.isdir(output_dir):
        print(f"Missing fog directory: {output_dir}")
        return 1

    icaos = sorted(set(args.icao)) if args.icao else discover_icaos(output_dir)
    if not icaos:
        print("No ICAO directories with wind shards found.")
        return 0

    started = time.perf_counter()
    processed = 0

    for idx, icao in enumerate(icaos, start=1):
        t0 = time.perf_counter()
        base_dir = os.path.join(output_dir, icao)
        total_rows = 0
        written = 0

        for family in FAMILIES:
            family_path = os.path.join(base_dir, f"{family}.json.gz")
            rows = read_json_gz(family_path)
            if not isinstance(rows, list) or not rows:
                continue

            total_rows += len(rows)
            buckets = split_rows(rows)
            for mode in MODES:
                mode_rows = buckets.get(mode, [])
                out_mode_path = os.path.join(base_dir, f"{family}_{mode}.json.gz")
                write_json_gz_atomic(out_mode_path, mode_rows)
                written += 1

                all_state_rows = [row for row in mode_rows if isinstance(row, dict) and is_all_state_row(row)]
                out_mode_allstate_path = os.path.join(base_dir, f"{family}_{mode}_allstate.json.gz")
                write_json_gz_atomic(out_mode_allstate_path, all_state_rows)
                written += 1

        if written == 0:
            print(f"[{idx}/{len(icaos)}] {icao}: skipped (missing or empty fog family shards)")
            continue

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        print(f"[{idx}/{len(icaos)}] {icao}: rows={total_rows} files={written} elapsed_ms={elapsed_ms}")
        processed += 1

    total_ms = int((time.perf_counter() - started) * 1000)
    print(f"Processed {processed}/{len(icaos)} airports in {total_ms} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
