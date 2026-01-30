import csv
from collections import OrderedDict

# Read verified data and dedupe (keep first per date+track)
verified = OrderedDict()
with open('selenium_results_verified.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter=';')
    for row in reader:
        date = row['timestamp'][:10]
        key = (date, row['song_title'], row['artist'])
        if key not in verified:
            verified[key] = row

# Write clean file
with open('selenium_results_rebuilt.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f, delimiter=';')
    writer.writerow(['timestamp', 'song_title', 'artist', 'streams', 'source_file'])
    for key, row in verified.items():
        writer.writerow([row['timestamp'], row['song_title'], row['artist'], row['streams'], row['source_file']])

print(f'Created selenium_results_rebuilt.csv with {len(verified)} records')

# Show date counts
from collections import Counter
date_counts = Counter()
for (date, _, _) in verified.keys():
    date_counts[date] += 1

print()
print('Records per date:')
for date in sorted(date_counts.keys()):
    print(f'  {date}: {date_counts[date]}')

# Calculate totals per date
date_totals = {}
for (date, _, _), row in verified.items():
    if date not in date_totals:
        date_totals[date] = 0
    date_totals[date] += int(row['streams'])

print()
print('Total streams per date:')
prev = None
for date in sorted(date_totals.keys()):
    total = date_totals[date]
    if prev:
        change = total - prev
        print(f'  {date}: {total:,} ({change:+,})')
    else:
        print(f'  {date}: {total:,}')
    prev = total
