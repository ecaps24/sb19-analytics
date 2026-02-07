import { create } from 'zustand';
import AsyncStorage from '@react-native-async-storage/async-storage';

const FAVORITES_KEY = 'opm_favorites';

interface FavoritesState {
  favorites: string[]; // artist names
  loaded: boolean;
  toggleFavorite: (name: string) => void;
  isFavorite: (name: string) => boolean;
  loadFavorites: () => Promise<void>;
}

export const useFavoritesStore = create<FavoritesState>((set, get) => ({
  favorites: [],
  loaded: false,

  toggleFavorite: (name: string) => {
    const { favorites } = get();
    let updated: string[];
    if (favorites.includes(name)) {
      updated = favorites.filter(f => f !== name);
    } else {
      updated = [...favorites, name];
    }
    set({ favorites: updated });
    // Persist async
    AsyncStorage.setItem(FAVORITES_KEY, JSON.stringify(updated)).catch(() => {});
  },

  isFavorite: (name: string) => {
    return get().favorites.includes(name);
  },

  loadFavorites: async () => {
    try {
      const raw = await AsyncStorage.getItem(FAVORITES_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          set({ favorites: parsed, loaded: true });
          return;
        }
      }
    } catch {}
    set({ loaded: true });
  },
}));
