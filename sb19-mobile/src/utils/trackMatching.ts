import { TrackMetadata } from '../types/data';

export function normalizeForMatch(title: string): string {
  return title
    .toLowerCase()
    .replace(/[''`\u2018\u2019\u201C\u201D]/g, "'")
    .replace(/\s*-\s*from\s+["']?/g, ' (from ')
    .replace(/\s*-\s*(live|instrumental|stripped|acoustic|remix)/gi, ' ($1)')
    .replace(/\s*-\s*\d+sins.*?\(live\)/gi, ' - live')
    .replace(/\s*-\s*superior sessions?\s*live/gi, ' - live')
    .replace(/["]/g, '')
    .replace(/\s+/g, ' ')
    .trim();
}

export function findTrackMetadata(
  songTitle: string,
  tracksMetadata: TrackMetadata[],
): TrackMetadata | undefined {
  const normalized = normalizeForMatch(songTitle);

  // Try exact match first
  let meta = tracksMetadata.find(
    m => normalizeForMatch(m.title) === normalized,
  );
  if (meta) return meta;

  // Try if one contains the other
  meta = tracksMetadata.find(m => {
    const metaNorm = normalizeForMatch(m.title);
    return normalized.includes(metaNorm) || metaNorm.includes(normalized);
  });
  if (meta) return meta;

  // Try matching just the base title (before any parentheses or dash suffixes)
  const baseTitle = normalized.split(/[(-]/)[0].trim();
  if (baseTitle.length > 3) {
    meta = tracksMetadata.find(m => {
      const metaBase = normalizeForMatch(m.title).split(/[(-]/)[0].trim();
      return baseTitle === metaBase;
    });
  }
  return meta;
}
