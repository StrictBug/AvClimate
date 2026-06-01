# AvClimate Render Deployment Handover

Last updated: 2026-05-30

## 1. Goal
Stabilize deployment on Render free tier (512 MB) while preserving chart functionality and correctness.

## 2. What has already been implemented

### Backend optimization architecture
- Added artifact-first fast paths for overview figures:
  - rain_thunder
  - fog_low_cloud
  - temp_dewpoint
  - wind_rose
- Added combined overview precomputed batch path so non-staged multi-figure overview calls can stay artifact-first.
- Added precipitation artifact-first fast path for both precipitation charts:
  - monthly_precip
  - precip_split

### Memory-safety mechanisms
- Added memory telemetry logging phases ("[mem] phase=...").
- Added configurable memory guard behavior via env var `CHARTS_MEMORY_GUARD_MB`.

### Precompute scripts
- Existing scripts updated to write sharded per-airport JSON artifacts by default under `statistics/precomputed/...`:
  - `scripts/helpers/precompute_y_ceilings.py`
  - `scripts/helpers/precompute_overview_fog_monthly.py`
  - `scripts/helpers/precompute_overview_rain_thunder_monthly.py`
  - `scripts/helpers/precompute_overview_temp_dewpoint_monthly.py`
  - `scripts/helpers/precompute_overview_wind_rose.py`
- New script created:
  - `scripts/helpers/precompute_precipitation.py`

### Correctness validation
- Rain parity regression checker passes:
  - `scripts/helpers/check_overview_precip_rain_consistency.py`
  - Status: PASS (max_abs_diff = 0.0)

## 3. Key code locations
- Main API implementation and fast-paths:
  - `webapp/backend/main.py`
- Precompute scripts:
  - `scripts/helpers/*.py`
- Helper script docs:
  - `scripts/helpers/README.md`
- Render service config:
  - `render.yaml`

## 4. Latest measured memory results

### Overview benchmark (same matrix as earlier)
- Peak observed during staged overview calls: ~287.8 MB

### Precipitation benchmark (same heavy checks as earlier)
- Before precipitation precompute path: ~716.5 MB peak seen in logs
- After precipitation precompute path: ~237.7 MB peak seen in logs
- Log phase confirming path: `charts.precipitation_precomputed`

## 5. Artifact footprint status

### Full all-airports precipitation generated
- Command run: `python scripts/helpers/precompute_precipitation.py`
- Result: 212 airport files
- Directory size: ~375 MB

### Current `statistics/precomputed` total
- ~392 MB total
- Breakdown from latest measurement:
  - `statistics/precomputed/precipitation`: ~375 MB
  - `statistics/precomputed/overview_wind_rose`: ~15 MB
  - `statistics/precomputed/overview_fog_monthly`: ~1.3 MB
  - `statistics/precomputed/overview_temp_dewpoint`: ~580 KB
  - `statistics/precomputed/overview_rain_thunder_monthly`: ~316 KB
  - `statistics/precomputed/y_ceilings`: ~8 KB

## 6. Important blockers before Render deployment

1. `.gitignore` currently ignores all `*.json`, so precomputed artifacts are excluded from git by default.
2. Only precipitation has been generated for all airports in the new sharded structure in this session.
3. Other sharded categories need all-airports generation as full airport coverage is required at deployment time.

## 7. Recommended next steps (in order)

1. Update ignore rules so required `statistics/precomputed/**/*.json` files can be committed.
2. Generate all-airports sharded artifacts for all optimized categories:
   - `precompute_y_ceilings.py`
   - `precompute_overview_fog_monthly.py`
   - `precompute_overview_rain_thunder_monthly.py`
   - `precompute_overview_temp_dewpoint_monthly.py`
   - `precompute_overview_wind_rose.py`
   - `precompute_precipitation.py` (already generated in this session)
3. Set Render env var:
   - `CHARTS_MEMORY_GUARD_MB=430`
4. Keep single-worker startup (do not scale workers on free plan).
5. Deploy and run smoke checks:
   - `/api/options`
   - one overview call (all figures)
   - one precipitation call
   - verify logs show precomputed phases and no restart loop

## 8. Commands likely needed next

```bash
cd /workspaces/AvClimate
source .venv/bin/activate

# all-airports generation for remaining categories
python scripts/helpers/precompute_y_ceilings.py
python scripts/helpers/precompute_overview_fog_monthly.py
python scripts/helpers/precompute_overview_rain_thunder_monthly.py
python scripts/helpers/precompute_overview_temp_dewpoint_monthly.py
python scripts/helpers/precompute_overview_wind_rose.py
# precipitation already run, rerun if needed:
python scripts/helpers/precompute_precipitation.py

# footprint check
find statistics/precomputed -mindepth 1 -maxdepth 1 -type d -print0 | xargs -0 -I{} du -sh {} | sort -h
```

## 9. Notes for next AI assistant
- Prioritize deployment readiness over new features.
- First resolve artifact tracking (`.gitignore` / git strategy), then regenerate full all-airport shards, then do one full pre-deploy memory validation.
- Memory improvements are substantial and already proven in local benchmarks; deployment risk is now mostly packaging/tracking of artifacts plus Render config.
