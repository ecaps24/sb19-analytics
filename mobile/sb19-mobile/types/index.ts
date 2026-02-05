// Stream data from selenium_results.csv
export interface StreamData {
  song_title: string;
  artist_name: string;
  total_streams: number;
  daily_streams?: number;
  year: number;
  album: string;
  collaborators?: string;
  data_date: string;
  spotify_url?: string;
}

// Monthly listeners data from monthly_listeners.csv
export interface ListenerData {
  artist_name: string;
  monthly_listeners: number;
  data_date: string;
  timestamp: string;
}

// Track metadata from tracks.csv
export interface TrackMetadata {
  title: string;
  artist: string;
  year: number;
  album: string;
  collaborators: string;
  spotify_url: string;
}

// Song detail metadata from song_metadata.json
export interface SongMetadata {
  lyrics?: string;
  credits?: string;
  history?: string;
  milestones?: Milestone[];
}

export interface Milestone {
  date: string;
  streams: number;
  label: string;
}

// Processed data for display
export interface ProcessedTrack extends StreamData {
  rank: number;
  change: number;
  rankChange: number | null;
  previousRank: number | null;
  streakDays?: number;
  metadata?: TrackMetadata;
}

// Album statistics
export interface AlbumStats {
  name: string;
  totalStreams: number;
  trackCount: number;
  change: number;
  tracks: ProcessedTrack[];
  color: string;
}

// Member statistics
export interface MemberStats {
  name: string;
  displayName: string;
  dataName: string;
  totalStreams: number;
  trackCount: number;
  change: number;
  monthlyListeners?: number;
  listenerChange?: number;
  color: string;
  borderColor: string;
  spotifyUrl: string;
}

// Dashboard statistics
export interface DashboardStats {
  currentListeners: number;
  listenerChange: number;
  allTimeHigh: number;
  totalTracks: number;
  totalStreams: number;
  streamChange: number;
  topTrack: ProcessedTrack | null;
  lastUpdated: string;
}

// Date range preset options
export type RangePreset = 'last1' | 'last7' | 'last30' | 'mtd' | 'custom' | 'all';

// Sort options
export type SortColumn = 'rank' | 'song' | 'streams' | 'change' | 'album';
export type SortDirection = 'asc' | 'desc';

// Filter options
export interface FilterOptions {
  album: string | null;
  track: string | null;
  member: string | null;
  showAllKickoff: boolean;
}

// Notification types
export interface StreamNotification {
  id: string;
  type: 'milestone' | 'rank_change' | 'listener_change' | 'new_track';
  title: string;
  body: string;
  data?: Record<string, unknown>;
  timestamp: string;
  read: boolean;
}

// Notification preferences
export interface NotificationPreferences {
  enabled: boolean;
  milestones: boolean;
  rankChanges: boolean;
  listenerChanges: boolean;
  newTracks: boolean;
}

// App settings
export interface AppSettings {
  theme: 'light' | 'dark' | 'system';
  notifications: NotificationPreferences;
  syncInterval: number; // in hours
  offlineMode: boolean;
}

// Network status
export interface NetworkStatus {
  isConnected: boolean;
  type: string | null;
}
