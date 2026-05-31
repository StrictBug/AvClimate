#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from webapp.backend import main as backend


def all_ceiling_keys() -> tuple[str, ...]:
    keys: set[str] = set()
    for values in backend.SECTION_CEILING_KEYS.values():
        keys.update(values)
    return tuple(sorted(keys))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Precompute per-airport y-axis ceilings for chart rendering.")
    parser.add_argument(
        "--icao",
        action="append",
        default=[],
        help="Only precompute this ICAO (repeat flag for multiple airports). Default: all available airports.",
    )
    parser.add_argument(
        "--output-dir",
        default=backend.Y_CEILINGS_DIR,
        help="Output directory for per-airport JSON artifacts (default: statistics/precomputed/y_ceilings)",
    )
    return parser.parse_args()


def write_json_atomic(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="y_ceilings_", suffix=".json", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main() -> int:
    args = parse_args()
    keys = all_ceiling_keys()

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
        ceilings = backend.compute_airport_y_ceilings(icao, keys, use_precomputed=False)
        if ceilings:
            write_json_atomic(
                os.path.join(output_dir, f"{icao}.json"),
                {k: float(v) for k, v in ceilings.items()},
            )
            written += 1
        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        print(f"[{idx}/{total}] {icao}: keys={len(ceilings)} elapsed_ms={elapsed_ms}")

    total_elapsed = int((time.perf_counter() - started) * 1000)
    print(f"Wrote {written} airports to {output_dir} in {total_elapsed} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
