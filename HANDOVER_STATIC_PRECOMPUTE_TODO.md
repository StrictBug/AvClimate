# AvClimate Static-Only Precompute TODO Handover

Last updated: 2026-05-31

## 1. Objective
Create a future path where AvClimate can run as a static site (for example on GitHub Pages) by serving all charts from precomputed artifacts, without a live backend compute service.

## 2. Current assessment summary
- Static-only architecture is technically feasible.
- Compute risk is moderate and manageable if we precompute compact grouped aggregates (not every UI combination as separate files).
- Primary risk is data packaging, browser memory/load behavior, and parity validation, not raw CPU.
- Existing work already proves the pattern:
  - Artifact-first paths are in place for multiple chart families.
  - Fog and smoke precompute pipelines now generate compressed per-airport shards.

## 3. Non-negotiables
- Preserve current chart functionality and controls.
- Preserve current data fidelity (no hidden downsampling that changes meaning).
- Keep climate driver filtering behavior equivalent to current backend output.
- Keep interactive latency acceptable on normal desktop and mobile connections.

## 4. Recommended target architecture
- Frontend-only app (static hosting).
- Versioned artifact manifest file that maps airport + chart family to compressed shard URLs and checksums.
- Per-airport, per-chart-family compressed shards (json.gz).
- Lazy client fetch by selected airport and active tab only.
- Client-side filtering and rendering from pre-aggregated dimensions.
- Browser cache strategy for recently used airports/chart families.

## 5. Implementation roadmap

### Phase 1: Scope and parity baseline
1. Inventory every chart and list exact input columns, groupings, and filters.
2. Mark each chart as one of:
   - already precomputed with parity confidence
   - precomputed but needs parity verification
   - still backend-compute only
3. Create parity harness that compares precomputed output against current backend output for a fixed airport/filter matrix.

Deliverable:
- Chart coverage matrix + parity test report.

### Phase 2: Precompute completion
1. Finish artifact-first coverage for all remaining backend-compute chart paths.
2. Standardize shard schemas:
   - consistent field names
   - consistent normalization for climate state keys
   - explicit version tag in each payload
3. Ensure all-airport generation scripts exist and are repeatable.
4. Keep compressed output by default and avoid uncompressed intermediates where possible.

Deliverable:
- 100 percent chart family coverage via precomputed artifacts.

### Phase 3: Static data delivery layer
1. Add manifest generation script:
   - artifact path
   - size
   - checksum
   - schema version
2. Add frontend data loader that:
   - reads manifest
   - fetches only required shard
   - caches recent shards
   - handles missing/corrupt shard with clear UI error state
3. Remove hard dependency on live API for chart rendering.

Deliverable:
- Frontend can render all supported charts with static artifacts only.

### Phase 4: Performance and memory hardening
1. Benchmark browser memory and load times for heavy airport toggle scenarios.
2. Add guards:
   - do not fetch inactive tabs
   - cancel stale in-flight requests
   - enforce cache size limits
3. Verify mobile behavior separately.

Deliverable:
- Performance report with pass/fail thresholds.

### Phase 5: Cutover plan
1. Dual-run period:
   - static path primary
   - backend path available for fallback
2. Validate parity in production-like environment.
3. If stable, retire backend runtime requirement for chart compute.

Deliverable:
- Static-only deployment runbook.

## 6. Risk register

### Risk A: Artifact explosion
- Symptom: too many files or oversized shards.
- Mitigation:
  - aggregate once, filter client-side
  - avoid precomputing every UI combination as separate files
  - shard by airport and chart family only

### Risk B: Browser memory spikes
- Symptom: tab crashes or sluggish UI on rapid toggling.
- Mitigation:
  - lazy loading
  - request cancellation
  - bounded cache
  - avoid loading multiple heavy families at once

### Risk C: Functional regressions
- Symptom: precomputed and backend chart values diverge.
- Mitigation:
  - parity harness for representative airport/filter matrix
  - acceptance thresholds per chart
  - block release if parity fails

### Risk D: Operational complexity
- Symptom: hard-to-manage artifact releases.
- Mitigation:
  - manifest + checksum workflow
  - versioned artifact sets
  - scripted publish process

## 7. Acceptance criteria for static-only readiness
- All chart families render from precomputed artifacts without backend compute.
- Parity checks pass for agreed airport/filter matrix.
- Browser memory remains within acceptable limits under stress toggling.
- Initial load and chart-switch latency meet agreed UX thresholds.
- Artifact publish process is documented and repeatable.

## 8. Suggested execution order in a new Copilot conversation
1. Build chart coverage and parity matrix.
2. Close remaining precompute gaps.
3. Implement manifest + frontend loader.
4. Run parity and browser stress tests.
5. Prepare static-only deployment runbook.

## 9. Prompt-ready starter for next conversation
Paste this into a new Copilot chat:

We are planning a static-only AvClimate architecture where all charts are rendered from precomputed artifacts and no live backend compute is required. Use HANDOVER_STATIC_PRECOMPUTE_TODO.md as the source plan. First, produce a chart coverage and parity matrix from current code, then identify and implement missing precompute paths without changing functionality or data meaning. Keep artifacts compressed and shard by airport and chart family. Add manifest-based frontend loading and validate parity plus browser memory performance before proposing cutover.
