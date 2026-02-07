import AsyncStorage from '@react-native-async-storage/async-storage';

const CACHE_TTL = 60 * 60 * 1000; // 1 hour in milliseconds
const CACHE_PREFIX = 'opm_cache_';

interface CacheEntry {
  data: string;
  timestamp: number;
}

export async function getCached(key: string): Promise<string | null> {
  try {
    const raw = await AsyncStorage.getItem(CACHE_PREFIX + key);
    if (!raw) return null;

    const entry: CacheEntry = JSON.parse(raw);
    const age = Date.now() - entry.timestamp;

    if (age > CACHE_TTL) {
      // Expired but return stale data (caller can decide to refetch)
      return entry.data;
    }
    return entry.data;
  } catch {
    return null;
  }
}

export async function isCacheFresh(key: string): Promise<boolean> {
  try {
    const raw = await AsyncStorage.getItem(CACHE_PREFIX + key);
    if (!raw) return false;
    const entry: CacheEntry = JSON.parse(raw);
    return Date.now() - entry.timestamp < CACHE_TTL;
  } catch {
    return false;
  }
}

export async function setCache(key: string, data: string): Promise<void> {
  try {
    const entry: CacheEntry = { data, timestamp: Date.now() };
    await AsyncStorage.setItem(CACHE_PREFIX + key, JSON.stringify(entry));
  } catch (e) {
    console.warn('Cache write failed:', e);
  }
}

export async function getCacheTimestamp(key: string): Promise<number | null> {
  try {
    const raw = await AsyncStorage.getItem(CACHE_PREFIX + key);
    if (!raw) return null;
    const entry: CacheEntry = JSON.parse(raw);
    return entry.timestamp;
  } catch {
    return null;
  }
}

export async function clearAllCache(): Promise<void> {
  try {
    const keys = await AsyncStorage.getAllKeys();
    const cacheKeys = keys.filter(k => k.startsWith(CACHE_PREFIX));
    if (cacheKeys.length > 0) {
      await AsyncStorage.multiRemove(cacheKeys);
    }
  } catch (e) {
    console.warn('Cache clear failed:', e);
  }
}

export async function getCacheSize(): Promise<string> {
  try {
    const keys = await AsyncStorage.getAllKeys();
    const cacheKeys = keys.filter(k => k.startsWith(CACHE_PREFIX));
    let totalSize = 0;
    for (const key of cacheKeys) {
      const value = await AsyncStorage.getItem(key);
      if (value) totalSize += value.length;
    }
    if (totalSize > 1_000_000) {
      return `${(totalSize / 1_000_000).toFixed(1)} MB`;
    }
    if (totalSize > 1_000) {
      return `${(totalSize / 1_000).toFixed(1)} KB`;
    }
    return `${totalSize} B`;
  } catch {
    return '0 B';
  }
}
