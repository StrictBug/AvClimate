# AvClimate HF Speed Optimization Handover

Last updated: 2026-06-03

## 0. Execution Status (2026-06-03)
- Phase 2 completed:
	- Frontend chart batch requests are now sent concurrently in `fetchCharts`.
	- Figures are still merged in deterministic batch order.
	- Warning/metrics behavior is preserved (first non-empty warning, first metrics payload).
- Phase 3 completed:
	- GZip middleware enabled in backend (`minimum_size=1000`).
- Remaining highest-priority work:
	- Phase 1 baseline/perf measurement table.
	- Phase 4 HF worker tuning and comparative benchmark.

## 1. Goal
Improve graph load time on Hugging Face Spaces while keeping the same frontend and backend behavior, chart logic, data streams, and API semantics.

## 2. Current Observations
- App is stable on HF with higher RAM, but slower than local Codespace.
- Likely constraints are CPU throughput, cold-start effects, and request/serialization overhead, not memory.
- Frontend chart batch fetching has been parallelized to reduce wall time on slower CPUs.

## 3. Non-Negotiables
- Do not change chart outputs, filter behavior, or interpretation logic.
- Keep existing API contract (`/api/options`, `/api/charts`) and figure IDs unchanged.
- Keep same frontend/backend data pathways and resulting visual behavior.

## 4. Recommended Plan (Priority Order)

### Phase 1: Measure Before Optimizing
1. Add per-request timing logs in backend for key phases:
	 - request parse
	 - data load/filter
	 - figure build
	 - serialization
	 - total response time
2. Record frontend timings:
	 - first chart request start/end
	 - total section load time
	 - per-batch latency
3. Capture baseline on:
	 - local Codespace
	 - HF Space warm run
	 - HF Space cold run

Deliverable:
- Baseline table with section load times (overview, wind, precipitation, fog_low_cloud, smoke_dust).

### Phase 2: Frontend Parallel Batch Fetch (Highest Impact, Low Risk)
1. Keep the same batch definitions and params, but send batch requests concurrently.
2. Merge returned figure arrays in deterministic order to preserve display behavior.
3. Keep existing warning/metrics behavior:
	 - first non-empty warning shown
	 - metrics from first batch that returns them

Primary file:
- `webapp/frontend/app.js` (`fetchCharts` flow)

Expected impact:
- Large reduction in wall time for multi-batch sections, especially on slower CPU instances.

### Phase 3: API Compression (Low Risk)
1. Enable gzip compression for JSON responses.
2. Confirm compressed transfer for `/api/charts` and `/api/options`.

Primary file:
- `webapp/backend/main.py` (middleware setup)

Expected impact:
- Smaller payload transfer and faster browser parse for large figure JSON.

### Phase 4: Worker Tuning on HF
1. Test `WEB_CONCURRENCY=2` on HF (current baseline typically single worker).
2. If stable, test `WEB_CONCURRENCY=3`.
3. Compare latency and restart risk.

Operational knobs:
- `WEB_CONCURRENCY`
- `GUNICORN_MAX_REQUESTS`
- `GUNICORN_MAX_REQUESTS_JITTER`
- `GUNICORN_TIMEOUT`

Primary files:
- `scripts/helpers/start_render.sh`
- HF Space runtime env configuration

Expected impact:
- Better parallel request handling when frontend issues concurrent calls.

### Phase 5: Short-TTL Query Response Cache
1. Add server-side cache keyed by full chart query parameters.
2. TTL target: 30-120 seconds (start at 60s).
3. Cache only successful responses and bound memory footprint (size limit).

Primary file:
- `webapp/backend/main.py` (`/api/charts` endpoint)

Expected impact:
- Much faster repeated airport/filter combinations and tab revisits.

### Phase 6: Optional Serializer Optimization
1. Consider faster JSON serializer for figure payload responses.
2. Keep payload structure identical.

Primary file:
- `webapp/backend/main.py`

Expected impact:
- Lower backend CPU time for large Plotly payload encoding.

## 5. Validation Criteria
- Functional parity:
	- same number/order of figures per section
	- same figure IDs
	- same values for equivalent inputs
- Performance targets:
	- meaningful reduction in median and p95 section load time on HF
	- improved first-interaction latency after warm start
- Stability:
	- no worker restart loops
	- no increase in error responses

## 6. Suggested Benchmark Matrix
- Airports: `YMML`, `YMMB`, one high-volume tropical station.
- Sections: overview, wind, precipitation, fog_low_cloud, smoke_dust.
- Modes: all days, rain days, non-rain days (where applicable).
- Runs:
	- HF cold start (first load)
	- HF warm run (repeat load)
	- local baseline

Record for each run:
- total section load time
- per-request backend elapsed time
- payload size (compressed and uncompressed if possible)

## 7. Rollout Strategy
1. Implement Phase 2 (frontend parallelization) first.
2. Add Phase 3 (gzip compression).
3. Deploy and benchmark.
4. Apply Phase 4 worker tuning and benchmark again.
5. If still needed, add Phase 5 short-TTL cache.
6. Keep Phase 6 serializer optimization as optional final step.

## 8. Rollback Guidance
- Keep each phase in separate commits.
- If regression appears:
	1. revert latest phase only
	2. re-run benchmark matrix
	3. proceed with next safest phase

## 9. Notes
- This plan intentionally avoids changing chart math or API shape.
- Main leverage is reducing wall time (parallel requests), transfer/parse cost (compression), and repeated compute cost (short cache).

## 10. Benchmark + Verification Update (2026-06-03)

### 10.1 Compression verification (local updated runtime)
- Verified on a fresh local runtime instance (`uvicorn` on port `8001`) with `Accept-Encoding: gzip`.
- `/api/options` response headers include:
	- `content-encoding: gzip`
	- `vary: Accept-Encoding`
- `/api/charts?section=overview&icao=YMML` response headers include:
	- `content-encoding: gzip`
	- `vary: Accept-Encoding`

### 10.2 Local baseline matrix (3 runs each)
Method:
- Endpoint: `/api/charts?section={section}&icao={airport}`
- Airports: `YMML`, `YMMB`, `YPDN` (tropical)
- Sections: overview, wind, precipitation, fog_low_cloud, smoke_dust
- Runs: 3 sequential runs per airport/section with gzip accepted

Summary (seconds, median/p95):

| Airport | Section | Median (s) | p95 (s) |
|---|---:|---:|---:|
| YMML | overview | 0.509 | 0.602 |
| YMML | wind | 0.426 | 0.440 |
| YMML | precipitation | 0.291 | 0.359 |
| YMML | fog_low_cloud | 1.890 | 2.218 |
| YMML | smoke_dust | 0.396 | 0.445 |
| YMMB | overview | 0.422 | 1.895 |
| YMMB | wind | 0.663 | 0.744 |
| YMMB | precipitation | 0.290 | 0.347 |
| YMMB | fog_low_cloud | 1.746 | 1.812 |
| YMMB | smoke_dust | 0.316 | 0.384 |
| YPDN | overview | 0.500 | 2.241 |
| YPDN | wind | 0.387 | 0.910 |
| YPDN | precipitation | 0.227 | 0.596 |
| YPDN | fog_low_cloud | 0.941 | 0.953 |
| YPDN | smoke_dust | 0.388 | 0.410 |

Observations:
- `fog_low_cloud` is consistently the slowest section on local baseline.
- Some sections show high first-request spikes (visible in p95), consistent with cache/cold-path effects.
- Typical warm-path medians for non-fog sections are generally sub-second.

### 10.3 Hugging Face benchmark snapshot (live Space)
Target:
- `https://strictbug-avclimate.hf.space`

Method used:
- Endpoint: `/api/charts?section={section}&icao={airport}`
- Airports: `YMML`, `YMMB`, `YPDN`
- Sections: overview, wind, precipitation, fog_low_cloud, smoke_dust
- Passes:
	- first pass: one request per airport/section pair
	- warm pass: immediate repeat of same matrix
- All requests returned status `0` (curl success).

Section-level comparison (seconds):

| Section | Local median (baseline) | HF first pass avg | HF warm pass avg |
|---|---:|---:|---:|
| overview | 0.467 | 14.895 | 16.459 |
| wind | 0.426 | 3.036 | 3.168 |
| precipitation | 0.290 | 6.413 | 6.766 |
| fog_low_cloud | 1.746 | 18.085 | 20.135 |
| smoke_dust | 0.384 | 4.157 | 4.608 |

Key observation:
- HF response times are currently much higher than local baseline across all sections.
- Warm-pass timings are not materially better than first-pass timings in this sample.

### 10.4 Deployed compression/header check (HF)
- Header check against the live HF Space currently does **not** show `content-encoding: gzip` for:
	- `/api/options`
	- `/api/charts?section=overview&icao=YMML`
- This suggests the deployed Space may still be running pre-gzip code and/or proxy behavior is stripping/overriding compression headers.

### 10.5 Remaining work to close Phase 1
- Run a true cold-start benchmark by restarting the HF Space immediately before first pass.
- Re-run the same first/warm matrix after confirming latest deployment is live.
- Re-check headers to confirm compression behavior on deployed endpoint.
