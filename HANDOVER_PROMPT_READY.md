# Prompt-Ready Handover (Paste Into New AI Chat)

I am continuing deployment hardening for AvClimate on Render free tier (512 MB).

Current status:
- Backend now has artifact-first fast paths for overview (rain_thunder, fog_low_cloud, temp_dewpoint, wind_rose), combined overview batch path, and precipitation section (monthly_precip + precip_split).
- Artifacts are now sharded per airport with lazy per-ICAO loading.
- New script added: scripts/helpers/precompute_precipitation.py.
- Rain parity regression check passes (max_abs_diff=0.0).

Measured memory:
- Overview staged peak: ~287.8 MB.
- Precipitation before optimization: ~716.5 MB.
- Precipitation after optimization: ~237.7 MB.

Artifact footprint currently measured:
- statistics/precomputed total: ~392 MB.
- precipitation: ~375 MB.
- overview_wind_rose: ~15 MB.
- other overview categories are small.

Important blocker:
- .gitignore currently ignores *.json, so precomputed artifacts are excluded from git unless specific allow-rules are added.

Next tasks (priority order):
1. Fix .gitignore to allow required statistics/precomputed/**/*.json artifacts while keeping other JSON ignored.
2. Ensure all-airports shards exist for all optimized categories:
   - precompute_y_ceilings.py
   - precompute_overview_fog_monthly.py
   - precompute_overview_rain_thunder_monthly.py
   - precompute_overview_temp_dewpoint_monthly.py
   - precompute_overview_wind_rose.py
   - precompute_precipitation.py (already run, rerun if needed)
3. Set Render env var CHARTS_MEMORY_GUARD_MB=430.
4. Keep single-worker uvicorn start command (no extra workers on free plan).
5. Run pre-deploy smoke checks and verify logs use precomputed paths:
   - charts.overview_precomputed_batch
   - charts.precipitation_precomputed
6. Deploy and verify no restart/OOM loop on Render logs.

Key files:
- webapp/backend/main.py
- scripts/helpers/precompute_*.py
- scripts/helpers/README.md
- render.yaml
- HANDOVER_RENDER_DEPLOY.md (full detailed handover)
