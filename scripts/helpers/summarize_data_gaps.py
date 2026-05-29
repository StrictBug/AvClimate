import os
import glob
import polars as pl
from datetime import datetime, timedelta

base = 'data/by_icao'
results = []

icao_dirs = sorted([
    d for d in os.listdir(base)
    if d.startswith('TARGET_ICAO=') and os.path.isdir(os.path.join(base, d))
])

for entry in icao_dirs:
    icao = entry.split('=', 1)[1]
    
    # Load all parquet files for this ICAO
    files = glob.glob(os.path.join(base, entry, '*.parquet'))
    if not files:
        continue
    
    df = pl.concat([pl.read_parquet(f) for f in files])
    
    if df.is_empty():
        continue
    
    # Extract date from TM_FULL and count observations per day
    date_counts = (
        df.select(
            pl.col('TM_FULL')
            .cast(pl.Date)
            .alias('date')
        )
        .group_by('date')
        .len()
        .sort('date')
    )
    
    if date_counts.is_empty():
        continue
    
    dates = date_counts['date'].to_list()
    counts = date_counts['len'].to_list()
    
    min_date = dates[0]
    max_date = dates[-1]
    expected_days = (max_date - min_date).days + 1
    actual_days = len(dates)
    coverage_pct = 100.0 * actual_days / expected_days
    
    total_obs = sum(counts)
    incomplete_days = sum(1 for c in counts if c < 48)
    expected_obs = expected_days * 48
    
    results.append({
        'icao': icao,
        'total_obs': total_obs,
        'expected_obs': expected_obs,
        'coverage_pct': coverage_pct,
        'min_date': str(min_date),
        'max_date': str(max_date),
        'days_with_data': actual_days,
        'incomplete_days': incomplete_days,
    })

# Sort by coverage percentage ascending (worst first)
results.sort(key=lambda x: x['coverage_pct'])

# Group by coverage bands
bands = {
    '< 50%': [],
    '50-60%': [],
    '60-70%': [],
    '70-80%': [],
    '80-90%': [],
    '90-95%': [],
    '95%+': [],
}

for r in results:
    pct = r['coverage_pct']
    if pct < 50:
        bands['< 50%'].append(r)
    elif pct < 60:
        bands['50-60%'].append(r)
    elif pct < 70:
        bands['60-70%'].append(r)
    elif pct < 80:
        bands['70-80%'].append(r)
    elif pct < 90:
        bands['80-90%'].append(r)
    elif pct < 95:
        bands['90-95%'].append(r)
    else:
        bands['95%+'].append(r)

# Print summary
print("=== DATA COVERAGE SUMMARY ===\n")
for band, stations in bands.items():
    if stations:
        print(f"\n{band} coverage ({len(stations)} stations):")
        for r in stations:
            print(f"  {r['icao']:6} : {r['coverage_pct']:5.1f}%  |  {r['total_obs']:>8} obs  |  {r['days_with_data']:>4}/{(datetime.fromisoformat(r['max_date']) - datetime.fromisoformat(r['min_date'])).days + 1} days  |  {r['incomplete_days']} incomplete days")

# Print overall stats
print("\n=== OVERALL STATISTICS ===")
print(f"Total stations: {len(results)}")
print(f"Median coverage: {results[len(results)//2]['coverage_pct']:.1f}%")
print(f"Stations >= 438k obs (expected): {sum(1 for r in results if r['total_obs'] >= 438000)}")
print(f"Expected obs per station: ~438,000 (48 obs/day × 365 days × 25 years)")
