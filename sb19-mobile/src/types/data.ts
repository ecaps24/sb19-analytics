export interface ListenerEntry {
  artist_name: string;
  monthly_listeners: number;
  data_date: string;
  timestamp: string;
  genre: string;
  followers?: number;
  cities: CityEntry[];
}

export interface CityEntry {
  name: string;
  listeners: number;
}

export interface StreamEntry {
  song_title: string;
  artist_name: string;
  total_streams: number;
  daily_streams: number;
  year: number;
  album: string;
  collaborators: string;
  data_date: string;
  spotify_url: string;
}

export interface TrackMetadata {
  title: string;
  artist: string;
  year: number;
  album: string;
  collaborators: string;
  spotify_url: string;
}

export interface ArtistInfo {
  name: string;
  genre: string;
  spotifyUrl: string;
}

export interface ArtistSummary {
  name: string;
  genre: string;
  spotifyUrl: string;
  currentListeners: number;
  previousListeners: number;
  followers: number;
  cities: CityEntry[];
  rank: number;
  rankChange: number;
  growthPercent: number;
  growthPercent7d: number;
  growthPercent30d: number;
  allTimeHigh: number;
  allTimeLow: number;
  daysTracked: number;
  averageListeners: number;
  history: HistoryPoint[];
  latestDate: string;
}

export interface HistoryPoint {
  date: string;
  listeners: number;
}

export interface TrackSummary {
  title: string;
  artist: string;
  currentStreams: number;
  previousStreams: number;
  change: number;
  changePercent: number;
  year: number;
  album: string;
  collaborators: string;
  spotifyUrl: string;
}

export type Genre = 'All' | 'P-Pop' | 'SB19 Solo' | 'OPM Pop' | 'OPM Ballad' | 'OPM Rock' | 'OPM Indie' | 'OPM Classic' | 'OPM Hip-Hop';

export type SortBy = 'listeners' | 'growth' | 'alphabetical';

export type DateRange = '7' | '30' | '90' | 'all';
