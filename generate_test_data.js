const fs = require('fs');

// Read the current CSV file
const csvContent = fs.readFileSync('sb19_streams_results.csv', 'utf-8');
const lines = csvContent.split('\n').filter(line => line.trim());

// Parse CSV line, handling quoted fields
function parseCSVLine(line) {
  const result = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (char === '"') {
      inQuotes = !inQuotes;
    } else if (char === ',' && !inQuotes) {
      result.push(current);
      current = '';
    } else {
      current += char;
    }
  }
  result.push(current);
  return result;
}

// Store all original data by song and date
const songDataByDate = new Map(); // key: spotify_link, value: Map of date -> data

// Skip headers (first 2 lines are headers)
for (let i = 2; i < lines.length; i++) {
  const fields = parseCSVLine(lines[i]);
  if (fields.length < 8) continue;

  const [timestamp, song_title, artist, year, album, collaborating_artists, spotify_link, streams] = fields;

  if (!spotify_link || !spotify_link.startsWith('http')) continue;

  const streamCount = parseInt(streams.replace(/[^0-9]/g, ''), 10);
  if (isNaN(streamCount)) continue;

  // Extract date (YYYYMMDD) from timestamp
  const date = timestamp.substring(0, 8);

  if (!songDataByDate.has(spotify_link)) {
    songDataByDate.set(spotify_link, new Map());
  }

  const songDates = songDataByDate.get(spotify_link);
  // Keep the latest entry for each date
  if (!songDates.has(date) || timestamp > songDates.get(date).timestamp) {
    songDates.set(date, {
      timestamp,
      song_title,
      artist,
      year,
      album,
      collaborating_artists,
      spotify_link,
      streams: streamCount
    });
  }
}

console.log(`Found ${songDataByDate.size} unique songs`);

// Target dates for output (Jan 13-18, no dummy data for Jan 19)
const targetDates = ['20260113', '20260114', '20260115', '20260116', '20260117', '20260118'];

// Generate data for all songs
const allData = [];

for (const [spotifyLink, dateMap] of songDataByDate) {
  // Get actual data for Jan 17 and Jan 18
  const jan17Data = dateMap.get('20260117');
  const jan18Data = dateMap.get('20260118');

  if (!jan17Data && !jan18Data) {
    console.log(`Skipping song with no Jan 17/18 data: ${spotifyLink}`);
    continue;
  }

  // Calculate daily addition from actual data
  // Use the higher stream count as the "real" total
  const latestStreams = Math.max(jan17Data?.streams || 0, jan18Data?.streams || 0);

  let baseDailyAdd;
  if (jan17Data && jan18Data && jan17Data.streams > 0 && jan18Data.streams > 0) {
    const rawDiff = Math.abs(jan18Data.streams - jan17Data.streams);
    // If daily change is more than 5% of total, it's likely bad data - use estimate instead
    if (rawDiff > latestStreams * 0.05) {
      baseDailyAdd = Math.round(latestStreams * 0.0005); // 0.05% of total
    } else {
      baseDailyAdd = rawDiff;
    }
  } else {
    // One of the values is 0 or missing - use estimate
    baseDailyAdd = Math.round(latestStreams * 0.0005);
  }
  // Ensure minimum daily addition
  baseDailyAdd = Math.max(baseDailyAdd, 100);

  const template = jan18Data || jan17Data;
  const streamsByDate = {};

  // Use the latest (highest) stream count as Jan 18 value
  // This handles cases where one day has 0 or bad data
  streamsByDate['20260118'] = latestStreams;

  // Work backwards from Jan 18 to generate all historical data
  let currentStreams = latestStreams;
  for (const date of ['20260117', '20260116', '20260115', '20260114', '20260113']) {
    const variation = 1 + (Math.random() * 0.30 - 0.15); // 0.85 to 1.15
    const dailyAdd = Math.round(baseDailyAdd * variation);
    currentStreams = currentStreams - dailyAdd;
    streamsByDate[date] = Math.max(0, currentStreams);
  }

  // Add entries for all target dates
  for (const date of targetDates) {
    allData.push({
      timestamp: date + '_120000',
      song_title: template.song_title,
      artist: template.artist,
      year: template.year,
      album: template.album,
      collaborating_artists: template.collaborating_artists,
      spotify_link: template.spotify_link,
      streams: streamsByDate[date]
    });
  }
}

// Sort by timestamp (oldest first), then by song title
allData.sort((a, b) => {
  if (a.timestamp !== b.timestamp) return a.timestamp.localeCompare(b.timestamp);
  return a.song_title.localeCompare(b.song_title);
});

console.log(`Generated ${allData.length} rows of data`);

// Escape CSV field if needed
function escapeCSV(value) {
  if (value === null || value === undefined) return '';
  const str = String(value);
  if (str.includes(',') || str.includes('"') || str.includes('\n')) {
    return '"' + str.replace(/"/g, '""') + '"';
  }
  return str;
}

// Generate CSV output
const header = '"timestamp","song_title","artist","year","album","collaborating_artists","spotify_link","streams"';
const csvRows = [header];

for (const row of allData) {
  csvRows.push([
    escapeCSV(row.timestamp),
    escapeCSV(row.song_title),
    escapeCSV(row.artist),
    escapeCSV(row.year),
    escapeCSV(row.album),
    escapeCSV(row.collaborating_artists),
    escapeCSV(row.spotify_link),
    row.streams
  ].join(','));
}

// Write to file
fs.writeFileSync('sb19_streams_results.csv', csvRows.join('\n'), 'utf-8');
console.log('Generated sb19_streams_results.csv with 7 days of test data');
console.log(`Total rows: ${csvRows.length - 1} (excluding header)`);
