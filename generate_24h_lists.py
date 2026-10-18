#!/usr/bin/env python3
"""Generate 24-hour signal lists for all 7 weekdays — all signals, no filtering."""
import os, sys, json
from datetime import datetime, timezone
from collections import defaultdict

# Load all pattern functions from the v2 script
script_dir = os.path.dirname(os.path.abspath(__file__))
v2_path = os.path.join(script_dir, 'futurequantvexa.py')

# Read the v2 file and extract everything before main()
with open(v2_path, 'r') as f:
    v2_code = f.read()

# Find where main() starts and take everything before it
main_idx = v2_code.find('\ndef main():')
if main_idx > 0:
    exec(v2_code[:main_idx])
else:
    exec(v2_code)

# Settings
DATA_DIR = '/tmp/repo-test2'
OUTPUT_DIR = os.path.join(script_dir, '24h_signals')
WEEKDAY_FULL = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

os.makedirs(OUTPUT_DIR, exist_ok=True)

# Load all 13 pairs
files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith('.json') and f != 'README.md'])
print(f'Loading {len(files)} pairs...')

all_signals = []
for filename in files:
    filepath = os.path.join(DATA_DIR, filename)
    pair_name = get_pair_name(filepath)
    candles = load_candles(filepath)
    signals = generate_signals(candles, pair_name)
    all_signals.extend(signals)
    print(f'  {pair_name}: {len(signals)} signals')

print(f'\nTotal: {len(all_signals)} signals across all pairs')

# Sort by timestamp
all_signals.sort(key=lambda s: s['timestamp'])

# Group by weekday
by_day = defaultdict(list)
for s in all_signals:
    dt = datetime.fromtimestamp(s['timestamp'], tz=timezone.utc)
    weekday = dt.weekday()  # Python: Mon=0, Sun=6
    our_weekday = (weekday + 1) % 7  # Our: Sun=0, Sat=6
    s['dt_utc'] = dt
    s['weekday_full'] = WEEKDAY_FULL[our_weekday]
    s['weekday_short'] = WEEKDAY_NAMES[our_weekday]
    by_day[our_weekday].append(s)

# Create one file per weekday
print(f'\nCreating 7 files (one per weekday)...')
total_all = 0

for day_idx in range(7):
    day_name = WEEKDAY_FULL[day_idx]
    day_short = WEEKDAY_NAMES[day_idx]
    day_signals = by_day.get(day_idx, [])
    day_signals.sort(key=lambda s: s['timestamp'])
    total_all += len(day_signals)
    
    filename = f'{day_short}_{day_name}.txt'
    filepath = os.path.join(OUTPUT_DIR, filename)
    
    with open(filepath, 'w') as f:
        f.write('=' * 60 + '\n')
        f.write(f'  FutureQuantVexa — {day_name} 24-Hour Signal List\n')
        f.write(f'  All signals (00:00 - 23:59 UTC) — No filtering\n')
        f.write(f'  13 pairs × 18 patterns × {day_name}\n')
        f.write('=' * 60 + '\n\n')
        
        f.write('━' * 7 + ' • ' + '━' * 7 + '\n')
        for s in day_signals:
            time_str = s['dt_utc'].strftime('%H:%M')
            pair_str = f"{s['pair']}-OTC"
            direction = 'CALL' if s['direction'] == 'BUY' else 'PUT'
            f.write(f'M1 {pair_str} {time_str} {direction}\n')
        f.write('━' * 7 + ' • ' + '━' * 7 + '\n')
        
        f.write(f'\nTotal: {len(day_signals)} signals\n')
        f.write(f'Day: {day_name}\n')
        f.write(f'Time range: 00:00 - 23:59 UTC\n\n')
        
        # Per pair breakdown
        pair_counts = defaultdict(int)
        for s in day_signals:
            pair_counts[s['pair']] += 1
        f.write(f'Per pair:\n')
        for pair, count in sorted(pair_counts.items(), key=lambda x: -x[1]):
            f.write(f'  {pair:<9}: {count} signals\n')
        
        # Per pattern breakdown
        pattern_counts = defaultdict(int)
        for s in day_signals:
            pattern_counts[s['pattern']] += 1
        f.write(f'\nPer pattern:\n')
        for pattern, count in sorted(pattern_counts.items(), key=lambda x: -x[1]):
            f.write(f'  {pattern:<12}: {count} signals\n')
        
        # Per hour breakdown
        hour_counts = defaultdict(int)
        for s in day_signals:
            hour_counts[s['dt_utc'].hour] += 1
        f.write(f'\nPer hour (UTC):\n')
        for h in range(24):
            count = hour_counts.get(h, 0)
            bar = '█' * (count // max(1, max(hour_counts.values())) * 30)
            f.write(f'  {h:02d}:00 | {count:>5} | {bar}\n')
    
    print(f'  {day_name}: {len(day_signals)} signals → {filename}')

# Create README index
readme_path = os.path.join(OUTPUT_DIR, 'README.md')
with open(readme_path, 'w') as f:
    f.write('# FutureQuantVexa — 24-Hour Signal Lists\n\n')
    f.write('All signals for each day of the week (00:00 - 23:59 UTC).\n')
    f.write('No filtering, no gap, no dedup — all signals as generated.\n')
    f.write('13 pairs × 18 patterns × 7 weekdays\n\n')
    f.write('## Files\n\n')
    f.write('| File | Day | Signals |\n')
    f.write('|------|-----|---------|\n')
    for day_idx in range(7):
        day_name = WEEKDAY_FULL[day_idx]
        day_short = WEEKDAY_NAMES[day_idx]
        count = len(by_day.get(day_idx, []))
        f.write(f'| {day_short}_{day_name}.txt | {day_name} | {count} |\n')
    f.write(f'| **Total** | | **{total_all}** |\n')

print(f'\n✓ Done! Total: {total_all} signals across 7 days')
print(f'Output directory: {OUTPUT_DIR}')
print(f'\nFiles created:')
for fname in sorted(os.listdir(OUTPUT_DIR)):
    fpath = os.path.join(OUTPUT_DIR, fname)
    size = os.path.getsize(fpath)
    print(f'  {fname:<35} {size:>8} bytes')
