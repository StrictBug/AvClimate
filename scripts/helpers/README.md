# Helper Scripts

Utility/data-prep scripts have been consolidated into this directory.

## Scripts

- `finalize_full.py`: convert ADAM CSV to `ADAM_full.parquet`
- `split_by_icao.py`: split `ADAM_full.parquet` into `data/by_icao/TARGET_ICAO=...`
- `split_full_dataset.py`: wrapper to run the ICAO split flow
- `split_lightning_by_icao.py`: convert/split lightning CSV into parquet partitions
- `consolidate_by_icao.py`: rewrite each ICAO partition to a single `part-0.parquet`
- `scan_data_gaps.py`: detailed gap/incomplete-day report
- `summarize_data_gaps.py`: coverage band summary report
- `finalize_data.py`: legacy CSV->parquet conversion flow for `TAF3.csv`

## Usage

From the repository root:

```bash
python scripts/helpers/finalize_full.py
python scripts/helpers/split_by_icao.py
python scripts/helpers/split_lightning_by_icao.py
```
