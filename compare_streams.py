import csv
from collections import defaultdict

# Read verified data and dedupe (keep first per date+track)
verified = {}
with open('selenium_results_verified.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter=';')
    for row in reader:
        date = row['timestamp'][:10]
        key = (date, row['song_title'], row['artist'])
        if key not in verified:
            verified[key] = int(row['streams'])

# Read current selenium_results.csv
current = {}
with open('selenium_results.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter=';')
    for row in reader:
        date = row['timestamp'][:10]
        key = (date, row['song_title'], row['artist'])
        try:
            current[key] = int(row['streams'])
        except:
            pass

print(f'Verified records (deduped): {len(verified)}')
print(f'Current records: {len(current)}')
print()

# Find mismatches
mismatches = []
for key, verified_streams in verified.items():
    if key in current:
        current_streams = current[key]
        if verified_streams != current_streams:
            diff = current_streams - verified_streams
            pct = (diff / verified_streams * 100) if verified_streams else 0
            mismatches.append((key, verified_streams, current_streams, diff, pct))

print(f'Mismatches found: {len(mismatches)}')
if mismatches:
    print()
    print('Top mismatches (by absolute difference):')
    mismatches.sort(key=lambda x: abs(x[3]), reverse=True)
    for m in mismatches[:15]:
        date, track, artist = m[0]
        print(f'  {date} | {track} - {artist}')
        print(f'    Verified: {m[1]:,} | Current: {m[2]:,} | Diff: {m[3]:+,}')
