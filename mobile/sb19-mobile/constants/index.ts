// SB19 All-Time High (Historical Peak)
export const SB19_ATH = 2828289;

// Member configuration
export const MEMBERS = [
  {
    name: 'Pablo',
    displayName: 'Pablo',
    dataName: 'Pablo',
    color: 'rgba(251, 146, 60, 0.8)',
    borderColor: '#fb923c',
    spotifyUrl: 'https://open.spotify.com/artist/4bavIt9eD9RR7V6BQCW6Me',
  },
  {
    name: 'Josh',
    displayName: 'Josh Cullen',
    dataName: 'Josh Cullen',
    color: 'rgba(52, 211, 153, 0.8)',
    borderColor: '#34d399',
    spotifyUrl: 'https://open.spotify.com/artist/3b3DYR8gKc53bvP3bTW2jT',
  },
  {
    name: 'Stell',
    displayName: 'STELL',
    dataName: 'STELL',
    color: 'rgba(248, 113, 113, 0.8)',
    borderColor: '#f87171',
    spotifyUrl: 'https://open.spotify.com/artist/0GWmH00GDvMCSBk5ybghD4',
  },
  {
    name: 'Felip',
    displayName: 'FELIP',
    dataName: 'felip',
    color: 'rgba(251, 191, 36, 0.8)',
    borderColor: '#fbbf24',
    spotifyUrl: 'https://open.spotify.com/artist/3fVNhpt0u1mAH0BjMtWo2j',
  },
  {
    name: 'Justin',
    displayName: 'Justin',
    dataName: 'Justin',
    color: 'rgba(45, 212, 191, 0.8)',
    borderColor: '#2dd4bf',
    spotifyUrl: 'https://open.spotify.com/artist/4SfQqPGrJMYOvMaD6Z88T1',
  },
] as const;

// Listener name mapping (CSV names to member dataNames)
export const LISTENER_NAME_MAP: Record<string, string> = {
  'pablo': 'Pablo',
  'josh cullen': 'Josh Cullen',
  'stell': 'STELL',
  'felip': 'felip',
  'justin': 'Justin',
};

// Album colors for charts
export const ALBUM_COLORS: Record<string, string> = {
  'Simula at Wakas Tour Kickoff': 'rgba(147, 51, 234, 0.8)', // purple
  'Pagtatag!': 'rgba(96, 165, 250, 0.8)', // blue
  'Simula at Wakas': 'rgba(52, 211, 153, 0.8)', // green
  'Pagsibol': 'rgba(251, 146, 60, 0.8)', // orange
  'Single': 'rgba(248, 113, 113, 0.8)', // red
  'Promotional': 'rgba(156, 163, 175, 0.8)', // gray
  'Collaboration': 'rgba(251, 191, 36, 0.8)', // yellow
};

// Album order for sorting
export const ALBUM_ORDER = [
  'Simula at Wakas Tour Kickoff',
  'Pagtatag!',
  'Simula at Wakas',
  'Pagsibol',
];

// Data source URLs (Replace with your actual GitHub raw URL)
export const DATA_SOURCES = {
  BASE_URL: 'https://raw.githubusercontent.com/ecaps24/sb19-analytics/main',
  STREAMS: 'https://raw.githubusercontent.com/ecaps24/sb19-analytics/main/selenium_results.csv',
  LISTENERS: 'https://raw.githubusercontent.com/ecaps24/sb19-analytics/main/monthly_listeners.csv',
  TRACKS: 'https://raw.githubusercontent.com/ecaps24/sb19-analytics/main/tracks.csv',
  METADATA: 'https://raw.githubusercontent.com/ecaps24/sb19-analytics/main/song_metadata.json',
};

// Default sync interval (4 hours in milliseconds)
export const DEFAULT_SYNC_INTERVAL = 4 * 60 * 60 * 1000;

// Number formatting thresholds
export const FORMAT_THRESHOLDS = {
  BILLION: 1_000_000_000,
  MILLION: 1_000_000,
  THOUSAND: 1_000,
};

// Chart color palette
export const CHART_COLORS = {
  SB19: { bg: 'rgba(96, 165, 250, 0.8)', border: '#60a5fa' },
  BINI: { bg: 'rgba(167, 139, 250, 0.8)', border: '#a78bfa' },
  Pablo: { bg: 'rgba(251, 146, 60, 0.8)', border: '#fb923c' },
  'Josh Cullen': { bg: 'rgba(52, 211, 153, 0.8)', border: '#34d399' },
  STELL: { bg: 'rgba(248, 113, 113, 0.8)', border: '#f87171' },
  felip: { bg: 'rgba(251, 191, 36, 0.8)', border: '#fbbf24' },
  Justin: { bg: 'rgba(45, 212, 191, 0.8)', border: '#2dd4bf' },
};

// Range presets
export const RANGE_PRESETS = [
  { value: 'last1', label: '24h' },
  { value: 'last7', label: '7d' },
  { value: 'last30', label: '30d' },
  { value: 'mtd', label: 'MTD' },
  { value: 'custom', label: 'Custom' },
  { value: 'all', label: 'All' },
] as const;
