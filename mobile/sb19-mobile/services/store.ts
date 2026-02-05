import { create } from 'zustand';
import {
  StreamData,
  ListenerData,
  TrackMetadata,
  SongMetadata,
  RangePreset,
  SortColumn,
  SortDirection,
  FilterOptions,
  AppSettings,
  NetworkStatus,
  ProcessedTrack,
  DashboardStats,
  AlbumStats,
  MemberStats,
} from '../types';
import { dataService } from './dataService';
import { MEMBERS, SB19_ATH, ALBUM_COLORS, ALBUM_ORDER, DATA_SOURCES } from '../constants';

interface AppState {
  // Data
  streamsData: StreamData[];
  listenersData: ListenerData[];
  tracksMetadata: TrackMetadata[];
  songMetadata: Record<string, SongMetadata>;

  // UI State
  isLoading: boolean;
  error: string | null;
  rangePreset: RangePreset;
  selectedDate: string | null;
  availableDates: string[];
  sortColumn: SortColumn;
  sortDirection: SortDirection;
  filters: FilterOptions;

  // Network
  network: NetworkStatus;
  lastSync: string | null;

  // Settings
  settings: AppSettings;

  // Actions
  loadData: (baseUrl?: string) => Promise<void>;
  setRangePreset: (preset: RangePreset) => void;
  setSelectedDate: (date: string | null) => void;
  setSort: (column: SortColumn, direction?: SortDirection) => void;
  setFilters: (filters: Partial<FilterOptions>) => void;
  setNetwork: (status: NetworkStatus) => void;
  updateSettings: (settings: Partial<AppSettings>) => void;

  // Computed data
  getLatestStreams: () => ProcessedTrack[];
  getStreamsByDate: () => Record<string, Record<string, StreamData>>;
  getPeriodChange: () => { changes: Record<string, number>; label: string };
  getDashboardStats: () => DashboardStats;
  getAlbumStats: () => AlbumStats[];
  getMemberStats: () => MemberStats[];
  getFilteredTracks: () => ProcessedTrack[];
}

const defaultSettings: AppSettings = {
  theme: 'system',
  notifications: {
    enabled: true,
    milestones: true,
    rankChanges: true,
    listenerChanges: true,
    newTracks: true,
  },
  syncInterval: 4,
  offlineMode: false,
};

const defaultFilters: FilterOptions = {
  album: null,
  track: null,
  member: null,
  showAllKickoff: false,
};

export const useAppStore = create<AppState>((set, get) => ({
  // Initial state
  streamsData: [],
  listenersData: [],
  tracksMetadata: [],
  songMetadata: {},
  isLoading: true,
  error: null,
  rangePreset: 'last1',
  selectedDate: null,
  availableDates: [],
  sortColumn: 'change',
  sortDirection: 'desc',
  filters: defaultFilters,
  network: { isConnected: true, type: null },
  lastSync: null,
  settings: defaultSettings,

  // Actions
  loadData: async (baseUrl = DATA_SOURCES.BASE_URL) => {
    set({ isLoading: true, error: null });

    try {
      // First try to load cached data
      await dataService.loadCachedData();

      const cachedStreams = dataService.getStreamsData();
      const cachedListeners = dataService.getListenersData();
      const cachedTracks = dataService.getTracksMetadata();
      const cachedMetadata = dataService.getSongMetadata();

      if (cachedStreams.length > 0) {
        const streamsByDate = groupStreamsByDate(cachedStreams);
        const dates = Object.keys(streamsByDate).sort();

        set({
          streamsData: cachedStreams,
          listenersData: cachedListeners,
          tracksMetadata: cachedTracks,
          songMetadata: cachedMetadata,
          availableDates: dates,
          selectedDate: dates[dates.length - 1] || null,
        });
      } else {
        // Load sample data as fallback for development
        dataService.loadSampleData();
        const streams = dataService.getStreamsData();
        const listeners = dataService.getListenersData();
        const tracks = dataService.getTracksMetadata();

        const streamsByDate = groupStreamsByDate(streams);
        const dates = Object.keys(streamsByDate).sort();

        set({
          streamsData: streams,
          listenersData: listeners,
          tracksMetadata: tracks,
          songMetadata: {},
          availableDates: dates,
          selectedDate: dates[dates.length - 1] || null,
        });
      }

      // Then try to sync from remote
      const { network } = get();
      if (network.isConnected) {
        const success = await dataService.syncFromRemote(baseUrl);
        if (success) {
          const streams = dataService.getStreamsData();
          const listeners = dataService.getListenersData();
          const tracks = dataService.getTracksMetadata();
          const metadata = dataService.getSongMetadata();

          const streamsByDate = groupStreamsByDate(streams);
          const dates = Object.keys(streamsByDate).sort();

          set({
            streamsData: streams,
            listenersData: listeners,
            tracksMetadata: tracks,
            songMetadata: metadata,
            availableDates: dates,
            selectedDate: dates[dates.length - 1] || null,
            lastSync: new Date().toISOString(),
          });
        }
      }

      set({ isLoading: false });
    } catch (error) {
      set({
        isLoading: false,
        error: error instanceof Error ? error.message : 'Failed to load data'
      });
    }
  },

  setRangePreset: (preset) => set({ rangePreset: preset }),

  setSelectedDate: (date) => set({ selectedDate: date }),

  setSort: (column, direction) => {
    const { sortColumn, sortDirection } = get();
    if (column === sortColumn && !direction) {
      set({ sortDirection: sortDirection === 'asc' ? 'desc' : 'asc' });
    } else {
      set({ sortColumn: column, sortDirection: direction || 'desc' });
    }
  },

  setFilters: (filters) => set((state) => ({
    filters: { ...state.filters, ...filters }
  })),

  setNetwork: (status) => set({ network: status }),

  updateSettings: (settings) => set((state) => ({
    settings: { ...state.settings, ...settings }
  })),

  // Computed data
  getLatestStreams: () => {
    const { streamsData } = get();
    const sb19Streams = streamsData.filter(d =>
      d.artist_name === 'SB19' || d.artist_name.includes('SB19')
    );

    const latestByTrack: Record<string, StreamData> = {};
    sb19Streams.forEach(d => {
      const key = d.song_title;
      if (!latestByTrack[key] || d.total_streams > latestByTrack[key].total_streams) {
        latestByTrack[key] = d;
      }
    });

    const sorted = Object.values(latestByTrack).sort((a, b) => b.total_streams - a.total_streams);
    const { changes } = get().getPeriodChange();

    return sorted.map((track, index) => ({
      ...track,
      rank: index + 1,
      change: changes[track.song_title] || 0,
      rankChange: null,
      previousRank: null,
    }));
  },

  getStreamsByDate: () => {
    const { streamsData } = get();
    return groupStreamsByDate(streamsData);
  },

  getPeriodChange: () => {
    const { streamsData, rangePreset, selectedDate } = get();
    const streamsByDate = groupStreamsByDate(streamsData);
    const allDates = Object.keys(streamsByDate).sort();

    if (allDates.length < 2) return { changes: {}, label: 'Change' };

    let startDate: string, endDate: string, label: string;

    switch (rangePreset) {
      case 'last1': {
        const recentDates = allDates.slice(-2);
        startDate = recentDates[0];
        endDate = recentDates[recentDates.length - 1];
        label = '24h +/-';
        break;
      }
      case 'last7': {
        const recentDates = allDates.slice(-7);
        startDate = recentDates[0];
        endDate = recentDates[recentDates.length - 1];
        label = '7d +/-';
        break;
      }
      case 'last30': {
        const recentDates = allDates.slice(-30);
        startDate = recentDates[0];
        endDate = recentDates[recentDates.length - 1];
        label = '30d +/-';
        break;
      }
      case 'mtd': {
        const latestDate = allDates[allDates.length - 1];
        const year = latestDate.substring(0, 4);
        const month = latestDate.substring(4, 6);
        const startOfMonth = `${year}${month}01`;
        const mtdDates = allDates.filter(d => d >= startOfMonth);
        startDate = mtdDates[0];
        endDate = mtdDates[mtdDates.length - 1];
        label = 'MTD +/-';
        break;
      }
      case 'custom': {
        if (selectedDate) {
          endDate = selectedDate;
          const endIdx = allDates.indexOf(endDate);
          startDate = endIdx > 0 ? allDates[endIdx - 1] : endDate;
        } else {
          startDate = allDates[allDates.length - 2];
          endDate = allDates[allDates.length - 1];
        }
        const month = endDate.substring(4, 6);
        const day = endDate.substring(6, 8);
        label = `${month}/${day} +/-`;
        break;
      }
      default:
        startDate = allDates[0];
        endDate = allDates[allDates.length - 1];
        label = 'Total +/-';
    }

    const startData = streamsByDate[startDate] || {};
    const endData = streamsByDate[endDate] || {};

    const changes: Record<string, number> = {};
    const allTracks = new Set([...Object.keys(startData), ...Object.keys(endData)]);

    allTracks.forEach(track => {
      const endStreams = endData[track]?.total_streams || 0;
      const startStreams = startData[track]?.total_streams || 0;

      if (startData[track] && endData[track]) {
        const rawChange = endStreams - startStreams;
        const isEstablishedTrack = endStreams > 1000000;
        if (isEstablishedTrack && endStreams > 0 && Math.abs(rawChange) / endStreams > 0.1) {
          changes[track] = 0;
        } else {
          changes[track] = rawChange;
        }
      } else {
        changes[track] = 0;
      }
    });

    return { changes, label };
  },

  getDashboardStats: () => {
    const { listenersData } = get();
    const latestStreams = get().getLatestStreams();
    const { changes, label } = get().getPeriodChange();

    const sb19Data = listenersData
      .filter(d => d.artist_name === 'SB19')
      .sort((a, b) => new Date(b.data_date).getTime() - new Date(a.data_date).getTime());

    const latest = sb19Data[0];
    const previous = sb19Data[1];

    const totalStreams = latestStreams.reduce((sum, t) => sum + t.total_streams, 0);
    const totalChange = latestStreams.reduce((sum, t) => sum + (changes[t.song_title] || 0), 0);

    const latestStreamDate = latestStreams.length > 0
      ? latestStreams.reduce((max, curr) => {
          const currDate = new Date(curr.data_date);
          const maxDate = new Date(max);
          return currDate > maxDate ? curr.data_date : max;
        }, latestStreams[0].data_date)
      : '';

    return {
      currentListeners: latest?.monthly_listeners || 0,
      listenerChange: latest && previous ? latest.monthly_listeners - previous.monthly_listeners : 0,
      allTimeHigh: SB19_ATH,
      totalTracks: get().tracksMetadata.length,
      totalStreams,
      streamChange: totalChange,
      topTrack: latestStreams[0] || null,
      lastUpdated: latestStreamDate,
    };
  },

  getAlbumStats: () => {
    const latestStreams = get().getLatestStreams();
    const { changes } = get().getPeriodChange();

    const albumMap: Record<string, AlbumStats> = {};

    latestStreams.forEach(track => {
      let album = track.album || 'Single';
      if (album.startsWith('Promotional')) album = 'Promotional';

      if (!albumMap[album]) {
        albumMap[album] = {
          name: album,
          totalStreams: 0,
          trackCount: 0,
          change: 0,
          tracks: [],
          color: ALBUM_COLORS[album] || 'rgba(156, 163, 175, 0.8)',
        };
      }

      albumMap[album].totalStreams += track.total_streams;
      albumMap[album].trackCount += 1;
      albumMap[album].change += changes[track.song_title] || 0;
      albumMap[album].tracks.push(track);
    });

    return Object.values(albumMap).sort((a, b) => {
      const aIdx = ALBUM_ORDER.indexOf(a.name);
      const bIdx = ALBUM_ORDER.indexOf(b.name);
      if (aIdx !== -1 && bIdx !== -1) return aIdx - bIdx;
      if (aIdx !== -1) return -1;
      if (bIdx !== -1) return 1;
      return b.totalStreams - a.totalStreams;
    });
  },

  getMemberStats: () => {
    const { streamsData, listenersData } = get();
    const { changes } = get().getPeriodChange();

    return MEMBERS.map(member => {
      const memberStreams = streamsData.filter(d =>
        d.artist_name.toLowerCase() === member.dataName.toLowerCase()
      );

      const latestByTrack: Record<string, StreamData> = {};
      memberStreams.forEach(d => {
        const key = d.song_title;
        if (!latestByTrack[key] || d.total_streams > latestByTrack[key].total_streams) {
          latestByTrack[key] = d;
        }
      });

      const tracks = Object.values(latestByTrack);
      const totalStreams = tracks.reduce((sum, t) => sum + t.total_streams, 0);
      const totalChange = tracks.reduce((sum, t) => sum + (changes[t.song_title] || 0), 0);

      const memberListeners = listenersData
        .filter(d => d.artist_name.toLowerCase() === member.dataName.toLowerCase())
        .sort((a, b) => new Date(b.data_date).getTime() - new Date(a.data_date).getTime());

      const latestListeners = memberListeners[0];
      const prevListeners = memberListeners[1];

      return {
        name: member.name,
        displayName: member.displayName,
        dataName: member.dataName,
        totalStreams,
        trackCount: tracks.length,
        change: totalChange,
        monthlyListeners: latestListeners?.monthly_listeners || 0,
        listenerChange: latestListeners && prevListeners
          ? latestListeners.monthly_listeners - prevListeners.monthly_listeners
          : 0,
        color: member.color,
        borderColor: member.borderColor,
        spotifyUrl: member.spotifyUrl,
      };
    });
  },

  getFilteredTracks: () => {
    const { filters, sortColumn, sortDirection } = get();
    let tracks = get().getLatestStreams();

    // Apply album filter
    if (filters.album) {
      tracks = tracks.filter(t => {
        let album = t.album || 'Single';
        if (album.startsWith('Promotional')) album = 'Promotional';
        return album === filters.album;
      });
    }

    // Apply track filter
    if (filters.track) {
      tracks = tracks.filter(t => t.song_title === filters.track);
    }

    // Sort
    tracks.sort((a, b) => {
      let aVal: number | string = 0;
      let bVal: number | string = 0;

      switch (sortColumn) {
        case 'rank':
          aVal = a.rank;
          bVal = b.rank;
          break;
        case 'song':
          aVal = a.song_title.toLowerCase();
          bVal = b.song_title.toLowerCase();
          break;
        case 'streams':
          aVal = a.total_streams;
          bVal = b.total_streams;
          break;
        case 'change':
          aVal = a.change;
          bVal = b.change;
          break;
        case 'album':
          aVal = a.album.toLowerCase();
          bVal = b.album.toLowerCase();
          break;
      }

      if (typeof aVal === 'string' && typeof bVal === 'string') {
        return sortDirection === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      return sortDirection === 'asc' ? (aVal as number) - (bVal as number) : (bVal as number) - (aVal as number);
    });

    return tracks;
  },
}));

// Helper function
function groupStreamsByDate(streams: StreamData[]): Record<string, Record<string, StreamData>> {
  const sb19Streams = streams.filter(d =>
    d.artist_name === 'SB19' || d.artist_name.includes('SB19')
  );

  const byDate: Record<string, Record<string, StreamData>> = {};

  sb19Streams.forEach(d => {
    const dateKey = d.data_date ? d.data_date.substring(0, 10).replace(/-/g, '') : '';
    if (!dateKey) return;

    if (!byDate[dateKey]) byDate[dateKey] = {};
    const key = d.song_title;

    if (!byDate[dateKey][key] || d.total_streams > byDate[dateKey][key].total_streams) {
      byDate[dateKey][key] = d;
    }
  });

  return byDate;
}
