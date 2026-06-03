# Handover: Migrate Data to HF Dataset Repo (Eliminate Cold-Start Download Delay)

## Problem

Every time the HF Space cold-starts (after sleeping or a redeploy), `bootstrap_data_from_release.sh`
downloads both parquet archives from GitHub Releases over the public internet:

- `by_icao.tar.gz`
- `lightning_by_icao.tar.gz`

This takes several minutes (GitHub → HF datacenter, public bandwidth, rate-limited by GitHub).
Users hitting a cold space wait the full duration before the app is ready.

## Proposed Solution: HF Dataset Repository

Create a dedicated public Dataset repo on Hugging Face (`strictbug/AvClimate-data`), upload the
archives there, and replace the GitHub download with a `huggingface_hub` snapshot download.

**Why this is better:**
- HF-to-HF transfer is datacenter-local → much faster (seconds, not minutes)
- No GitHub token needed
- No GitHub rate limits
- Dataset versioning is built-in (commit history on the dataset repo)
- Keeps the Space repo itself small (no LFS bloat)

## Implementation Steps

### 1. Create the HF Dataset repo

```bash
# Via CLI (pip install huggingface_hub first if needed)
huggingface-cli repo create AvClimate-data --type dataset --organization strictbug
```

Or create it at https://huggingface.co/new-dataset → owner: strictbug, name: AvClimate-data, Public.

### 2. Upload the archives

```bash
huggingface-cli upload strictbug/AvClimate-data \
  /path/to/by_icao.tar.gz by_icao.tar.gz --repo-type dataset

huggingface-cli upload strictbug/AvClimate-data \
  /path/to/lightning_by_icao.tar.gz lightning_by_icao.tar.gz --repo-type dataset
```

Note: files > 5GB require `--chunk-size` adjustment or the LFS API.
Check file sizes first: `ls -lh data/*.tar.gz` (or wherever the local archives live).

### 3. Add `huggingface_hub` to requirements

In `requirements.txt` (or equivalent), add:
```
huggingface_hub>=0.23.0
```

### 4. Rewrite `bootstrap_data_from_release.sh`

Replace the curl-based download with a Python one-liner (or a small Python script),
e.g. in the bootstrap script:

```bash
echo "[bootstrap] downloading data from HF dataset repo..."
python3 - <<'PYEOF'
from huggingface_hub import hf_hub_download
import tarfile, os

root = os.environ["ROOT_DIR"]  # set before calling this block

for filename, subdir in [
    ("by_icao.tar.gz",        "data"),
    ("lightning_by_icao.tar.gz", "data"),
]:
    local = hf_hub_download(
        repo_id="strictbug/AvClimate-data",
        filename=filename,
        repo_type="dataset",
        local_dir=f"{root}/tmp_dl",
    )
    with tarfile.open(local) as tf:
        tf.extractall(f"{root}/{subdir}")
    os.remove(local)
PYEOF
```

Alternatively, keep the script as bash but replace the `curl` URL with the HF raw URL:
```
https://huggingface.co/datasets/strictbug/AvClimate-data/resolve/main/by_icao.tar.gz
```
This requires zero code changes beyond swapping the env var values.

### 5. Update HF Space environment variables

Remove or replace these env vars in the Space settings:
- `AVCLIMATE_RELEASE_BASE_URL` → remove
- `AVCLIMATE_BY_ICAO_URL` → set to `https://huggingface.co/datasets/strictbug/AvClimate-data/resolve/main/by_icao.tar.gz`
- `AVCLIMATE_LIGHTNING_URL` → set to `https://huggingface.co/datasets/strictbug/AvClimate-data/resolve/main/lightning_by_icao.tar.gz`
- `GITHUB_TOKEN` → can be removed (no longer needed)
- SHA256 checksums remain valid (same files, different host)

This approach (Option B-simple) requires **zero code changes** to `bootstrap_data_from_release.sh` —
just update the env vars to point at HF instead of GitHub.

## Quick-Win Option (Zero Code Changes)

Just update the two URL env vars on the Space to point at the HF dataset raw URLs above.
The existing curl-based bootstrap works fine with any HTTPS URL.
Only the upload step (Step 2) needs to happen first.

## Current State (as of this handover)

- Data is currently hosted on GitHub Releases at:
  `https://github.com/StrictBug/AvClimate/releases/download/data-v1/`
- Bootstrap script: `scripts/helpers/bootstrap_data_from_release.sh`
- Cold-start download time: several minutes
- SHA256 checksums (still valid after migration, same files):
  - `by_icao`: `ef648c229844040f58bdf257a39c988af78b5c27bc95f3df8ee6e1930cc5159a`
  - `lightning_by_icao`: `9fd05b3f16787cb3b86129e0e6948c5cdc6c3662e7b2f9736cef40f701618130`
