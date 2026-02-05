import AsyncStorage from '@react-native-async-storage/async-storage';
import { StreamData, ListenerData, TrackMetadata, SongMetadata } from '../types';
import { SAMPLE_STREAMS, SAMPLE_LISTENERS, SAMPLE_TRACKS } from './sampleData';

const STORAGE_KEYS = {
  STREAMS: '@sb19/streams',
  LISTENERS: '@sb19/listeners',
  TRACKS: '@sb19/tracks',
  METADATA: '@sb19/metadata',
  LAST_SYNC: '@sb19/lastSync',
};

// Parse CSV line handling quoted values
function parseCSVLine(line: string, delimiter: string = ','): string[] {
  // Auto-detect delimiter if not specified
  if (line.includes(';') && !line.includes(',')) {
    delimiter = ';';
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
        values.push(current.trim());
        current = '';
      } else {
        current += char;
      }
    }
  }
  values.push(current.trim());
  return values;
}

// Parse streams CSV (selenium_results.csv)
export function parseStreamsCSV(csvText: string): StreamData[] {
  const lines = csvText.split(/\r?\n/).filter(l => l.trim());
  if (lines.length === 0) return [];

  const headers = parseCSVLine(lines[0]);
  const data: StreamData[] = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    const row: Record<string, string> = {};
    headers.forEach((h, idx) => row[h.trim()] = (values[idx] || '').trim());

    const streams = parseInt((row.streams || row.total_streams || '0').replace(/,/g, ''));
    const dailyStreams = parseInt((row.daily_streams || '0').replace(/,/g, ''));
    const songTitle = row.song_title || '';
    let artist = row.artist || row.artist_name || 'SB19';
    const year = parseInt(row.year) || 0;
    const album = row.album || '';
    const collaborators = row.collaborating_artists || '';
    let timestamp = row.timestamp || '';

    // Convert timestamp format 20260124_022608 to 2026-01-24 02:26:08
    if (timestamp && timestamp.includes('_') && timestamp.length >= 15) {
      const y = timestamp.substring(0, 4);
      const m = timestamp.substring(4, 6);
      const d = timestamp.substring(6, 8);
      const h = timestamp.substring(9, 11);
      const min = timestamp.substring(11, 13);
      const sec = timestamp.substring(13, 15);
      timestamp = `${y}-${m}-${d} ${h}:${min}:${sec}`;
    }

    const spotifyUrl = row.url || row['spotify_link'] || row['Spotify Link'] || '';

    if (songTitle && !isNaN(streams) && streams > 0) {
      data.push({
        song_title: songTitle,
        artist_name: artist.replace(' - Spotify Top Songs', ''),
        total_streams: streams,
        daily_streams: dailyStreams,
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

// Parse monthly listeners CSV
export function parseListenersCSV(csvText: string): ListenerData[] {
  const lines = csvText.split(/\r?\n/).filter(l => l.trim());
  if (lines.length === 0) return [];

  const rawHeaders = parseCSVLine(lines[0]);
  const headers = rawHeaders.map(h => h.trim().replace(/^\uFEFF/, ''));
  const data: ListenerData[] = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    const row: Record<string, string> = {};
    headers.forEach((h, idx) => {
      if (h) row[h] = (values[idx] || '').trim();
    });

    const artist = row.artist_name || '';
    const listeners = parseInt((row.monthly_listeners || '0').replace(/,/g, ''));
    let dataDate = row.data_date || row.timestamp || '';

    // Convert timestamp format
    if (dataDate) {
      if (dataDate.includes('_') && dataDate.length >= 8) {
        const year = dataDate.substring(0, 4);
        const month = dataDate.substring(4, 6);
        const day = dataDate.substring(6, 8);
        dataDate = `${year}-${month}-${day}`;
      }
    }

    if (artist && !isNaN(listeners) && listeners > 0 && dataDate &&
        !artist.includes('Unknown') && !artist.includes('Unsupported')) {
      data.push({
        artist_name: artist,
        monthly_listeners: listeners,
        data_date: dataDate,
        timestamp: row.timestamp || row.data_date || dataDate,
      });
    }
  }

  return data.sort((a, b) => new Date(a.data_date).getTime() - new Date(b.data_date).getTime());
}

// Parse tracks metadata CSV
export function parseTracksCSV(csvText: string): TrackMetadata[] {
  const lines = csvText.split(/\r?\n/).filter(l => l.trim());
  if (lines.length === 0) return [];

  const headers = parseCSVLine(lines[0]);
  const data: TrackMetadata[] = [];

  for (let i = 1; i < lines.length; i++) {
    const values = parseCSVLine(lines[i]);
    const row: Record<string, string> = {};
    headers.forEach((h, idx) => row[h.trim()] = (values[idx] || '').trim());

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

// Fetch data from URL
async function fetchData(url: string): Promise<string> {
  const response = await fetch(url + '?t=' + Date.now());
  if (!response.ok) {
    throw new Error(`Failed to fetch ${url}: ${response.status}`);
  }
  return response.text();
}

// Save data to AsyncStorage
async function saveToStorage<T>(key: string, data: T): Promise<void> {
  await AsyncStorage.setItem(key, JSON.stringify(data));
}

// Load data from AsyncStorage
async function loadFromStorage<T>(key: string): Promise<T | null> {
  const data = await AsyncStorage.getItem(key);
  return data ? JSON.parse(data) : null;
}

// Data service class
export class DataService {
  private streamsData: StreamData[] = [];
  private listenersData: ListenerData[] = [];
  private tracksMetadata: TrackMetadata[] = [];
  private songMetadata: Record<string, SongMetadata> = {};

  async loadCachedData(): Promise<void> {
    const [streams, listeners, tracks, metadata] = await Promise.all([
      loadFromStorage<StreamData[]>(STORAGE_KEYS.STREAMS),
      loadFromStorage<ListenerData[]>(STORAGE_KEYS.LISTENERS),
      loadFromStorage<TrackMetadata[]>(STORAGE_KEYS.TRACKS),
      loadFromStorage<Record<string, SongMetadata>>(STORAGE_KEYS.METADATA),
    ]);

    if (streams && streams.length > 0) {
      this.streamsData = streams;
    }
    if (listeners && listeners.length > 0) {
      this.listenersData = listeners;
    }
    if (tracks && tracks.length > 0) {
      this.tracksMetadata = tracks;
    }
    if (metadata) {
      this.songMetadata = metadata;
    }
  }

  // Load sample data for development/fallback
  loadSampleData(): void {
    this.streamsData = parseStreamsCSV(SAMPLE_STREAMS);
    this.listenersData = parseListenersCSV(SAMPLE_LISTENERS);
    this.tracksMetadata = parseTracksCSV(SAMPLE_TRACKS);
    this.songMetadata = {};
    console.log('Loaded sample data:', {
      streams: this.streamsData.length,
      listeners: this.listenersData.length,
      tracks: this.tracksMetadata.length,
    });
  }

  async syncFromRemote(baseUrl: string): Promise<boolean> {
    try {
      const [streamsCSV, listenersCSV, tracksCSV, metadataJSON] = await Promise.all([
        fetchData(`${baseUrl}/selenium_results.csv`),
        fetchData(`${baseUrl}/monthly_listeners.csv`),
        fetchData(`${baseUrl}/tracks.csv`),
        fetchData(`${baseUrl}/song_metadata.json`).catch(() => '{}'),
      ]);

      this.streamsData = parseStreamsCSV(streamsCSV);
      this.listenersData = parseListenersCSV(listenersCSV);
      this.tracksMetadata = parseTracksCSV(tracksCSV);

      try {
        const metadataObj = JSON.parse(metadataJSON);
        this.songMetadata = metadataObj.songs || {};
      } catch {
        this.songMetadata = {};
      }

      // Save to storage
      await Promise.all([
        saveToStorage(STORAGE_KEYS.STREAMS, this.streamsData),
        saveToStorage(STORAGE_KEYS.LISTENERS, this.listenersData),
        saveToStorage(STORAGE_KEYS.TRACKS, this.tracksMetadata),
        saveToStorage(STORAGE_KEYS.METADATA, this.songMetadata),
        saveToStorage(STORAGE_KEYS.LAST_SYNC, new Date().toISOString()),
      ]);

      return true;
    } catch (error) {
      console.error('Sync failed:', error);
      return false;
    }
  }

  async getLastSyncTime(): Promise<string | null> {
    return loadFromStorage<string>(STORAGE_KEYS.LAST_SYNC);
  }

  getStreamsData(): StreamData[] {
    return this.streamsData;
  }

  getListenersData(): ListenerData[] {
    return this.listenersData;
  }

  getTracksMetadata(): TrackMetadata[] {
    return this.tracksMetadata;
  }

  getSongMetadata(): Record<string, SongMetadata> {
    return this.songMetadata;
  }
}

export const dataService = new DataService();
