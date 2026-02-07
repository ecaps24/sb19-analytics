import { ArtistSummary, HistoryPoint, ListenerEntry } from '../types/data';

export function computeGrowthPercent(current: number, previous: number): number {
  if (!previous || previous === 0) return 0;
  return ((current - previous) / previous) * 100;
}

export function computeATH(history: HistoryPoint[]): number {
  if (history.length === 0) return 0;
  return Math.max(...history.map(h => h.listeners));
}

export function computeATL(history: HistoryPoint[]): number {
  if (history.length === 0) return 0;
  return Math.min(...history.map(h => h.listeners));
}

export function computeAverage(history: HistoryPoint[]): number {
  if (history.length === 0) return 0;
  const sum = history.reduce((acc, h) => acc + h.listeners, 0);
  return Math.round(sum / history.length);
}

export function getListenersNDaysAgo(history: HistoryPoint[], days: number): number {
  if (history.length === 0) return 0;
  const targetDate = new Date();
  targetDate.setDate(targetDate.getDate() - days);
  const targetStr = targetDate.toISOString().split('T')[0];

  // Find closest entry to target date
  let closest = history[0];
  let closestDiff = Infinity;
  for (const point of history) {
    const diff = Math.abs(new Date(point.date).getTime() - new Date(targetStr).getTime());
    if (diff < closestDiff) {
      closestDiff = diff;
      closest = point;
    }
  }
  return closest.listeners;
}

export function computeGrowthForPeriod(history: HistoryPoint[], days: number): number {
  if (history.length < 2) return 0;
  const current = history[history.length - 1].listeners;
  const previous = getListenersNDaysAgo(history, days);
  return computeGrowthPercent(current, previous);
}

export function filterHistoryByRange(history: HistoryPoint[], range: string): HistoryPoint[] {
  if (range === 'all' || !range) return history;
  const days = parseInt(range);
  if (isNaN(days)) return history;
  const cutoff = new Date();
  cutoff.setDate(cutoff.getDate() - days);
  const cutoffStr = cutoff.toISOString().split('T')[0];
  return history.filter(h => h.date >= cutoffStr);
}

export function buildArtistHistory(
  entries: ListenerEntry[],
  artistName: string,
): HistoryPoint[] {
  const artistEntries = entries.filter(
    e => e.artist_name.toLowerCase() === artistName.toLowerCase(),
  );

  // Group by date, take latest per date
  const dateMap = new Map<string, number>();
  for (const entry of artistEntries) {
    const date = entry.data_date.split(' ')[0]; // strip time
    const existing = dateMap.get(date);
    if (!existing || entry.monthly_listeners > 0) {
      dateMap.set(date, entry.monthly_listeners);
    }
  }

  return Array.from(dateMap.entries())
    .map(([date, listeners]) => ({ date, listeners }))
    .sort((a, b) => a.date.localeCompare(b.date));
}

export function getTopMovers(
  summaries: ArtistSummary[],
  direction: 'gainers' | 'decliners',
  count: number = 5,
  period: '7d' | '30d' = '7d',
): ArtistSummary[] {
  const field = period === '7d' ? 'growthPercent7d' : 'growthPercent30d';
  const sorted = [...summaries].filter(s => s[field] !== 0);

  if (direction === 'gainers') {
    sorted.sort((a, b) => b[field] - a[field]);
  } else {
    sorted.sort((a, b) => a[field] - b[field]);
  }

  return sorted.slice(0, count);
}
