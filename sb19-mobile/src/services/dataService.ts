import { getCached, setCache, isCacheFresh } from './cacheService';

const BASE_URL = 'https://raw.githubusercontent.com/ecaps24/sb19-analytics/master';

const FILES = {
  listeners: 'monthly_listeners.csv',
  streams: 'selenium_results.csv',
  tracks: 'tracks.csv',
  artists: 'opm_artists_spotify.csv',
} as const;

type FileKey = keyof typeof FILES;

async function fetchWithCache(
  key: FileKey,
  forceRefresh: boolean = false,
): Promise<string> {
  // Check cache first
  if (!forceRefresh) {
    const fresh = await isCacheFresh(key);
    if (fresh) {
      const cached = await getCached(key);
      if (cached) return cached;
    }
  }

  // Fetch from GitHub
  const url = `${BASE_URL}/${FILES[key]}?t=${Date.now()}`;
  const response = await fetch(url);
  if (!response.ok) {
    // Try stale cache on network failure
    const stale = await getCached(key);
    if (stale) return stale;
    throw new Error(`Failed to fetch ${key}: ${response.status}`);
  }

  const text = await response.text();
  await setCache(key, text);
  return text;
}

export async function fetchAllData(forceRefresh: boolean = false): Promise<{
  listenersCSV: string;
  streamsCSV: string;
  tracksCSV: string;
  artistsCSV: string;
}> {
  const [listenersCSV, streamsCSV, tracksCSV, artistsCSV] = await Promise.all([
    fetchWithCache('listeners', forceRefresh),
    fetchWithCache('streams', forceRefresh),
    fetchWithCache('tracks', forceRefresh),
    fetchWithCache('artists', forceRefresh),
  ]);

  return { listenersCSV, streamsCSV, tracksCSV, artistsCSV };
}
