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
    
    # Find gaps: consecutive date runs
    gaps = []
    if actual_days < expected_days:
        current_date = min_date
        date_set = set(dates)
        
        gap_start = None
        for i in range(expected_days):
            check_date = min_date + timedelta(days=i)
            
            if check_date not in date_set:
                if gap_start is None:
                    gap_start = check_date
            else:
                if gap_start is not None:
                    gap_end = check_date - timedelta(days=1)
                    gaps.append(f"{gap_start.isoformat()} to {gap_end.isoformat()}")
                    gap_start = None
        
        if gap_start is not None:
            gap_end = max_date
            gaps.append(f"{gap_start.isoformat()} to {gap_end.isoformat()}")
    
    # Find days with incomplete observations (< 48)
    incomplete_days = [
        dates[i].isoformat()
        for i in range(len(counts))
        if counts[i] < 48
    ]
    
    total_obs = sum(counts)
    
    results.append({
        'icao': icao,
        'total_obs': total_obs,
        'expected_days': expected_days,
        'actual_days': actual_days,
        'coverage_pct': round(100.0 * actual_days / expected_days, 1),
        'min_date': str(min_date),
        'max_date': str(max_date),
        'gaps': '; '.join(gaps) if gaps else 'none',
        'incomplete_days_count': len(incomplete_days),
        'incomplete_days_sample': ', '.join(incomplete_days[:5]) if incomplete_days else 'none'
    })

# Sort by coverage percentage ascending (worst first)
results.sort(key=lambda x: x['coverage_pct'])

# Output
print("ICAO,Total_Obs,Expected_Days,Actual_Days,Coverage_%,Min_Date,Max_Date,First_Gap_or_Incomplete_Info,Incomplete_Days_Count,Incomplete_Days_Sample")
for r in results:
    gap_info = r['gaps'] if r['gaps'] != 'none' else f"{r['incomplete_days_count']} incomplete days"
    print(f"{r['icao']},{r['total_obs']},{r['expected_days']},{r['actual_days']},{r['coverage_pct']},{r['min_date']},{r['max_date']},\"{gap_info}\",{r['incomplete_days_count']},{r['incomplete_days_sample']}")
