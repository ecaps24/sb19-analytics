import { ListenerEntry, StreamEntry, TrackMetadata, ArtistInfo } from '../types/data';
import { normalizeForMatch, findTrackMetadata } from '../utils/trackMatching';

export function parseCSVLine(line: string, delimiter?: string): string[] {
  if (!delimiter) {
    delimiter = line.includes(';') ? ';' : ',';
  }
  const values: string[] = [];
  let current = '';
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (inQuotes) {
      if (char === '"') {
        if (i + 1 < line.length && line[i + 1] === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        current += char;
      }
    } else {
      if (char === '"') {
        inQuotes = true;
      } else if (char === delimiter) {
        values.push(current);
        current = '';
      } else {
        current += char;
      }
    }
  }
  values.push(current);
  return values;
}

export function parseListenersCSV(csvText: string): ListenerEntry[] {
  const lines = csvText.split(/\r?\n/).filter(l => l.trim());
  if (lines.length === 0) return [];

  const rawHeaders = parseCSVLine(lines[0]);
  const headers = rawHeaders.map(h => h.trim().replace(/^\uFEFF/, ''));
  const headerCount = headers.length;
  const data: ListenerEntry[] = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    const row: Record<string, string> = {};

    // Detect old-format rows (3 columns) vs new-format rows (15 columns)
    if (values.length <= 4 && headerCount > 4) {
      row.artist_name = (values[0] || '').trim();
      row.monthly_listeners = (values[1] || '').trim();
      row.timestamp = (values[2] || '').trim();
    } else {
      headers.forEach((h, idx) => {
        if (h) row[h] = (values[idx] || '').trim();
      });
    }

    const artist = row.artist_name || '';
    const listeners = parseInt((row.monthly_listeners || '0').replace(/,/g, ''));
    let dataDate = row.data_date || row.timestamp || '';

    // Convert timestamp format (20251105_042257) to date string
    if (dataDate) {
      if (dataDate.includes('_') && dataDate.length >= 8) {
        const year = dataDate.substring(0, 4);
        const month = dataDate.substring(4, 6);
        const day = dataDate.substring(6, 8);
        dataDate = `${year}-${month}-${day}`;
      }
    }

    if (
      artist &&
      !isNaN(listeners) &&
      listeners > 0 &&
      dataDate &&
      !artist.includes('Unknown') &&
      !artist.includes('Unsupported')
    ) {
      const entry: ListenerEntry = {
        artist_name: artist,
        monthly_listeners: listeners,
        data_date: dataDate,
        timestamp: row.timestamp || row.data_date || dataDate,
        genre: row.genre || '',
        cities: [],
      };

      // Parse followers
      const rawFollowers = (row.followers || '').replace(/,/g, '');
      if (rawFollowers && !isNaN(parseInt(rawFollowers))) {
        entry.followers = parseInt(rawFollowers);
      }

      // Parse city data
      for (let c = 1; c <= 5; c++) {
        const cityName = row[`city_${c}`] || '';
        const cityListeners = (row[`city_${c}_listeners`] || '').replace(/,/g, '');
        if (cityName && cityListeners && !isNaN(parseInt(cityListeners))) {
          entry.cities.push({ name: cityName, listeners: parseInt(cityListeners) });
        }
      }

      data.push(entry);
    }
  }

  return data.sort((a, b) => a.data_date.localeCompare(b.data_date));
}

export function parseTracksMetadataCSV(csvText: string): TrackMetadata[] {
  const lines = csvText.split(/\r?\n/).filter(l => l.trim());
  if (lines.length === 0) return [];
  const headers = parseCSVLine(lines[0]);
  const data: TrackMetadata[] = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    const row: Record<string, string> = {};
    headers.forEach((h, idx) => (row[h.trim()] = (values[idx] || '').trim()));

    data.push({
      title: row['Song Title'] || '',
      artist: row['Artist'] || 'SB19',
      year: parseInt(row['Year']) || 0,
      album: row['Album/EP/Single'] || 'Single',
      collaborators: row['Collaborating Artist(s)'] || '',
      spotify_url: row['Spotify Link'] || '',
    });
  }
  return data;
}

export function parseStreamsCSV(
  csvText: string,
  tracksMetadata: TrackMetadata[],
): StreamEntry[] {
  const lines = csvText.split(/\r?\n/).filter(l => l.trim());
  if (lines.length === 0) return [];
  const headers = parseCSVLine(lines[0]);
  const data: StreamEntry[] = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    const row: Record<string, string> = {};
    headers.forEach((h, idx) => (row[h.trim()] = (values[idx] || '').trim()));

    const streams = parseInt(
      (row.streams || row.total_streams || '0').replace(/,/g, ''),
    );
    const dailyStreams = parseInt(
      (row.daily_streams || '0').replace(/,/g, ''),
    );
    const songTitle = row.song_title || '';
    let artist = row.artist || row.artist_name || 'SB19';
    let year = parseInt(row.year) || 0;
    let album = row.album || '';
    let collaborators = row.collaborating_artists || '';
    let timestamp = row.timestamp || '';
    const spotifyUrl =
      row.url || row['spotify_link'] || row['Spotify Link'] || '';

    // Convert timestamp format 20260124_022608 to 2026-01-24 02:26:08
    if (timestamp && timestamp.includes('_') && timestamp.length >= 15) {
      const y = timestamp.substring(0, 4);
      const mo = timestamp.substring(4, 6);
      const d = timestamp.substring(6, 8);
      const h = timestamp.substring(9, 11);
      const mi = timestamp.substring(11, 13);
      const s = timestamp.substring(13, 15);
      timestamp = `${y}-${mo}-${d} ${h}:${mi}:${s}`;
    }

    // Enrich with metadata
    const meta = findTrackMetadata(songTitle, tracksMetadata);
    if (meta) {
      if (!year) year = meta.year;
      if (!album) album = meta.album;
      if (!collaborators) collaborators = meta.collaborators;
      if (!artist || artist === 'SB19') artist = meta.artist;
    }

    if (songTitle && !isNaN(streams) && streams > 0) {
      data.push({
        song_title: songTitle,
        artist_name: artist.replace(' - Spotify Top Songs', ''),
        total_streams: streams,
        daily_streams: dailyStreams || 0,
        year,
        album,
        collaborators,
        data_date: timestamp,
        spotify_url: spotifyUrl,
      });
    }
  }
  return data;
}

export function parseArtistsCSV(csvText: string): Map<string, ArtistInfo> {
  const map = new Map<string, ArtistInfo>();
  const lines = csvText.trim().split('\n');

  for (let i = 1; i < lines.length; i++) {
    const parts = lines[i].split(',');
    if (parts.length >= 3) {
      const name = parts[0].trim();
      const url = parts[1].trim();
      const genre = parts[parts.length - 1].trim();
      if (name && genre) {
        map.set(name.toLowerCase(), { name, genre, spotifyUrl: url });
      }
    }
  }
  return map;
}
