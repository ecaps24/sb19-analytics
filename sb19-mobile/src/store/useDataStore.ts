import { create } from 'zustand';
import {
  ListenerEntry,
  StreamEntry,
  TrackMetadata,
  ArtistInfo,
  ArtistSummary,
  HistoryPoint,
  TrackSummary,
  Genre,
} from '../types/data';
import { fetchAllData } from '../services/dataService';
import {
  parseListenersCSV,
  parseStreamsCSV,
  parseTracksMetadataCSV,
  parseArtistsCSV,
} from '../services/csvParser';
import {
  buildArtistHistory,
  computeGrowthPercent,
  computeATH,
  computeATL,
  computeAverage,
  computeGrowthForPeriod,
} from '../utils/calculations';
import { getCacheTimestamp } from '../services/cacheService';

interface DataState {
  listenersData: ListenerEntry[];
  streamsData: StreamEntry[];
  tracksMetadata: TrackMetadata[];
  artistInfoMap: Map<string, ArtistInfo>;
  loading: boolean;
  error: string | null;
  lastUpdated: string | null;

  fetchData: (forceRefresh?: boolean) => Promise<void>;
  getArtistSummaries: (genre?: Genre) => ArtistSummary[];
  getArtistDetail: (name: string) => ArtistSummary | null;
  getArtistTracks: (name: string) => TrackSummary[];
  getArtistInfo: (name: string) => ArtistInfo | undefined;
}

export const useDataStore = create<DataState>((set, get) => ({
  listenersData: [],
  streamsData: [],
  tracksMetadata: [],
  artistInfoMap: new Map(),
  loading: false,
  error: null,
  lastUpdated: null,

  fetchData: async (forceRefresh = false) => {
    set({ loading: true, error: null });
    try {
      const { listenersCSV, streamsCSV, tracksCSV, artistsCSV, streams2CSV } =
        await fetchAllData(forceRefresh);

      const tracksMetadata = parseTracksMetadataCSV(tracksCSV);
      const listenersData = parseListenersCSV(listenersCSV);
      const streamsData = parseStreamsCSV(streamsCSV, tracksMetadata);
      // Parse additional streams (BINI, Cup of Joe, etc.) and merge
      if (streams2CSV) {
        const extraStreams = parseStreamsCSV(streams2CSV, tracksMetadata);
        streamsData.push(...extraStreams);
      }
      const artistInfoMap = parseArtistsCSV(artistsCSV);

      // Get cache timestamp for last updated display
      const cacheTs = await getCacheTimestamp('listeners');
      const lastUpdated = cacheTs
        ? new Date(cacheTs).toISOString()
        : new Date().toISOString();

      set({
        listenersData,
        streamsData,
        tracksMetadata,
        artistInfoMap,
        loading: false,
        lastUpdated,
      });
    } catch (e: any) {
      set({ loading: false, error: e.message || 'Failed to load data' });
    }
  },

  getArtistInfo: (name: string) => {
    const { artistInfoMap } = get();
    return artistInfoMap.get(name.toLowerCase());
  },

  getArtistSummaries: (genre?: Genre): ArtistSummary[] => {
    const { listenersData, artistInfoMap } = get();
    if (listenersData.length === 0) return [];

    // Group entries by artist
    const artistMap = new Map<string, ListenerEntry[]>();
    for (const entry of listenersData) {
      const key = entry.artist_name.toLowerCase();
      if (!artistMap.has(key)) artistMap.set(key, []);
      artistMap.get(key)!.push(entry);
    }

    const summaries: ArtistSummary[] = [];

    for (const [key, entries] of artistMap) {
      const info = artistInfoMap.get(key);
      if (!info) continue; // Only include artists we know about

      // Filter by genre
      if (genre && genre !== 'All' && info.genre !== genre) continue;

      const history = buildArtistHistory(listenersData, info.name);
      if (history.length === 0) continue;

      const latest = entries[entries.length - 1];
      const current = history[history.length - 1]?.listeners || 0;
      const previous =
        history.length >= 2
          ? history[history.length - 2]?.listeners || 0
          : current;

      summaries.push({
        name: info.name,
        genre: info.genre,
        spotifyUrl: info.spotifyUrl,
        currentListeners: current,
        previousListeners: previous,
        followers: latest.followers || 0,
        cities: latest.cities || [],
        rank: 0, // Will be set after sorting
        rankChange: 0,
        growthPercent: computeGrowthPercent(current, previous),
        growthPercent7d: computeGrowthForPeriod(history, 7),
        growthPercent30d: computeGrowthForPeriod(history, 30),
        allTimeHigh: computeATH(history),
        allTimeLow: computeATL(history),
        daysTracked: history.length,
        averageListeners: computeAverage(history),
        history,
        latestDate: history[history.length - 1]?.date || '',
      });
    }

    // Sort by listeners and assign ranks
    summaries.sort((a, b) => b.currentListeners - a.currentListeners);
    summaries.forEach((s, i) => {
      s.rank = i + 1;
    });

    // Compute rank changes based on previous listeners
    const prevSorted = [...summaries].sort(
      (a, b) => b.previousListeners - a.previousListeners,
    );
    const prevRankMap = new Map<string, number>();
    prevSorted.forEach((s, i) => prevRankMap.set(s.name, i + 1));
    summaries.forEach(s => {
      const prevRank = prevRankMap.get(s.name) || s.rank;
      s.rankChange = prevRank - s.rank; // positive = moved up
    });

    return summaries;
  },

  getArtistDetail: (name: string): ArtistSummary | null => {
    const summaries = get().getArtistSummaries();
    return summaries.find(
      s => s.name.toLowerCase() === name.toLowerCase(),
    ) || null;
  },

  getArtistTracks: (name: string): TrackSummary[] => {
    const { streamsData, tracksMetadata } = get();

    // Get all stream entries for this artist (or SB19 for the group)
    const artistStreams = streamsData.filter(
      s => s.artist_name.toLowerCase() === name.toLowerCase() ||
        (name.toLowerCase() === 'sb19' && s.artist_name === 'SB19'),
    );

    if (artistStreams.length === 0) {
      // Fall back to track metadata if no stream data exists
      const metaTracks = tracksMetadata.filter(
        t => t.artist.toLowerCase() === name.toLowerCase(),
      );
      return metaTracks.map(t => ({
        title: t.title,
        artist: t.artist,
        currentStreams: 0,
        previousStreams: 0,
        change: 0,
        changePercent: 0,
        year: t.year,
        album: t.album,
        collaborators: t.collaborators,
        spotifyUrl: t.spotify_url,
      }));
    }

    // Group by song title, get latest and previous
    const songMap = new Map<
      string,
      { latest: StreamEntry; previous?: StreamEntry }
    >();

    // Sort by date
    const sorted = [...artistStreams].sort((a, b) =>
      a.data_date.localeCompare(b.data_date),
    );

    for (const entry of sorted) {
      const key = entry.song_title.toLowerCase();
      const existing = songMap.get(key);
      if (!existing) {
        songMap.set(key, { latest: entry });
      } else {
        songMap.set(key, { latest: entry, previous: existing.latest });
      }
    }

    const tracks: TrackSummary[] = [];
    for (const [, { latest, previous }] of songMap) {
      const prevStreams = previous?.total_streams || 0;
      const change = prevStreams > 0 ? latest.total_streams - prevStreams : 0;
      const changePercent =
        prevStreams > 0 ? (change / prevStreams) * 100 : 0;

      tracks.push({
        title: latest.song_title,
        artist: latest.artist_name,
        currentStreams: latest.total_streams,
        previousStreams: prevStreams,
        change,
        changePercent,
        year: latest.year,
        album: latest.album,
        collaborators: latest.collaborators,
        spotifyUrl: latest.spotify_url,
      });
    }

    // Sort by current streams descending
    tracks.sort((a, b) => b.currentStreams - a.currentStreams);
    return tracks;
  },
}));
