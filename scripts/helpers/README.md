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
- `precompute_y_ceilings.py`: build `statistics/y_ceilings_by_icao.json` for runtime chart axis ceilings
- `precompute_overview_fog_monthly.py`: build `statistics/overview_fog_monthly_by_icao.json` for lightweight overview fog chart rendering
- `precompute_overview_rain_thunder_monthly.py`: build `statistics/overview_rain_thunder_monthly_by_icao.json` for climate-aware overview rain/thunder rendering
- `precompute_overview_temp_dewpoint_monthly.py`: build `statistics/overview_temp_dewpoint_by_icao.json` for climate-aware overview temperature/dewpoint rendering
- `precompute_overview_wind_rose.py`: build `statistics/overview_wind_rose_by_icao.json` for climate-aware overview wind rose rendering
- `precompute_wind_gale_monthly.py`: build `statistics/precomputed/wind_gale_monthly/*.json` for climate-aware wind-tab gale weather split rendering
- `precompute_fog_low_cloud.py`: build `statistics/precomputed/fog_low_cloud/*.json` for climate-aware fog/low-cloud tab rendering
- `precompute_smoke_dust.py`: build `statistics/precomputed/smoke_dust/*.json` for climate-aware smoke/dust tab rendering
- `precompute_precipitation.py`: build `statistics/precomputed/precipitation/*.json` for climate-aware precipitation charts (monthly and directional split)
- `check_overview_precip_rain_consistency.py`: verify overview rain_thunder Rain bars match precipitation monthly_precip Rain bars for a filter set
- `package_data_archives.sh`: package local parquet folders into deployable archives under `artifacts/`
- `bootstrap_data_from_release.sh`: fetch/extract parquet archives for deploy/runtime when local parquet data is absent

## Usage

From the repository root:

```bash
python scripts/helpers/finalize_full.py
python scripts/helpers/split_by_icao.py
python scripts/helpers/split_lightning_by_icao.py
python scripts/helpers/precompute_y_ceilings.py
python scripts/helpers/precompute_overview_fog_monthly.py
python scripts/helpers/precompute_overview_rain_thunder_monthly.py
python scripts/helpers/precompute_overview_temp_dewpoint_monthly.py
python scripts/helpers/precompute_overview_wind_rose.py
python scripts/helpers/precompute_wind_gale_monthly.py
python scripts/helpers/precompute_fog_low_cloud.py
python scripts/helpers/precompute_smoke_dust.py
python scripts/helpers/precompute_precipitation.py
python scripts/helpers/check_overview_precip_rain_consistency.py --base-url http://127.0.0.1:8000 --icao YMML
./scripts/helpers/package_data_archives.sh
```

## Deploy Data Bootstrap (No-LFS)

Render build now runs `scripts/helpers/bootstrap_data_from_release.sh` before dependency install.

Set either:

- `AVCLIMATE_RELEASE_BASE_URL` (for example `https://github.com/<owner>/<repo>/releases/download/<tag>`)

or both explicit URLs:

- `AVCLIMATE_BY_ICAO_URL`
- `AVCLIMATE_LIGHTNING_URL`

Optional integrity vars:

- `AVCLIMATE_BY_ICAO_SHA256`
- `AVCLIMATE_LIGHTNING_SHA256`

Optional auth var (for private release assets):

- `GITHUB_TOKEN`
