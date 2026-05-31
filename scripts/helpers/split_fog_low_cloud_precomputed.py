#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import sys
import tempfile

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from webapp.backend import main as backend

FAMILIES = {
    "monthly": "monthly",
    "hourly": "hourly",
    "dewpoint": "dewpoint",
    "wind": "wind",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Split fog/low-cloud combined airport shards into per-family shards.")
    parser.add_argument("--icao", action="append", default=[], help="Only split this ICAO (repeat for multiple)")
    parser.add_argument(
        "--source-dir",
        default=backend.FOG_LOW_CLOUD_PRECOMPUTED_DIR,
        help="Directory containing legacy combined airport shards",
    )
    return parser.parse_args()


def read_json(path: str) -> object | None:
    if not os.path.exists(path):
        return None
    try:
        if path.endswith(".gz"):
            with gzip.open(path, "rt", encoding="utf-8") as handle:
                return json.load(handle)
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def write_json_gz_atomic(path: str, payload: object) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(prefix="fog_split_", suffix=".json.gz", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", compresslevel=6, mtime=0) as gz:
                gz.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8"))
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def split_airport(icao: str, source_dir: str) -> bool:
    legacy_path = os.path.join(source_dir, f"{icao}.json.gz")
    if not os.path.exists(legacy_path):
        legacy_path = os.path.join(source_dir, f"{icao}.json")
    raw = read_json(legacy_path)
    if not isinstance(raw, dict):
        return False

    airport_dir = os.path.join(source_dir, icao)
    os.makedirs(airport_dir, exist_ok=True)

    for family_key, source_key in FAMILIES.items():
        rows = raw.get(source_key, [])
        if not isinstance(rows, list):
            rows = []
        write_json_gz_atomic(os.path.join(airport_dir, f"{family_key}.json.gz"), rows)

    if os.path.isdir(airport_dir):
        pass
    return True


def main() -> int:
    args = parse_args()
    airports = tuple(sorted(set(args.icao))) if args.icao else backend.available_airports()
    if not airports:
        print("No airports found; no artifact created.")
        return 1

    written = 0
    for idx, icao in enumerate(airports, start=1):
        ok = split_airport(icao, args.source_dir)
        print(f"[{idx}/{len(airports)}] {icao}: {'ok' if ok else 'missing'}")
        if ok:
            written += 1
        legacy_path = os.path.join(args.source_dir, f"{icao}.json.gz")
        legacy_path_uncompressed = os.path.join(args.source_dir, f"{icao}.json")
        for path in (legacy_path, legacy_path_uncompressed):
            if os.path.exists(path):
                os.remove(path)

    print(f"Split {written} airports into {args.source_dir}/<ICAO>/<family>.json.gz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
