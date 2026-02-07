import { create } from 'zustand';
import { Genre, SortBy, DateRange } from '../types/data';

interface FilterState {
  // Rankings filters
  selectedGenre: Genre;
  searchQuery: string;
  sortBy: SortBy;

  // Compare selections
  compareArtists: string[];

  // Trends period
  trendsPeriod: '7d' | '30d';

  // Chart range
  chartRange: DateRange;

  // Actions
  setGenre: (genre: Genre) => void;
  setSearchQuery: (query: string) => void;
  setSortBy: (sortBy: SortBy) => void;
  addCompareArtist: (name: string) => void;
  removeCompareArtist: (name: string) => void;
  clearCompareArtists: () => void;
  setTrendsPeriod: (period: '7d' | '30d') => void;
  setChartRange: (range: DateRange) => void;
}

export const useFilterStore = create<FilterState>((set, get) => ({
  selectedGenre: 'All',
  searchQuery: '',
  sortBy: 'listeners',
  compareArtists: [],
  trendsPeriod: '7d',
  chartRange: '30',

  setGenre: (genre) => set({ selectedGenre: genre }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setSortBy: (sortBy) => set({ sortBy }),

  addCompareArtist: (name) => {
    const { compareArtists } = get();
    if (compareArtists.length >= 4) return;
    if (compareArtists.includes(name)) return;
    set({ compareArtists: [...compareArtists, name] });
  },

  removeCompareArtist: (name) => {
    const { compareArtists } = get();
    set({ compareArtists: compareArtists.filter(a => a !== name) });
  },

  clearCompareArtists: () => set({ compareArtists: [] }),
  setTrendsPeriod: (period) => set({ trendsPeriod: period }),
  setChartRange: (range) => set({ chartRange: range }),
}));
