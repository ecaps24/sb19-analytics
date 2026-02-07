export const colors = {
  // Background
  background: '#0f172a',
  surface: '#1e293b',
  surfaceLight: '#334155',
  card: 'rgba(30, 41, 59, 0.8)',
  cardBorder: 'rgba(71, 85, 105, 0.3)',

  // Brand
  primary: '#3b82f6',
  primaryDark: '#2563eb',
  primaryLight: '#60a5fa',
  primaryGlow: 'rgba(59, 130, 246, 0.15)',

  // Semantic
  success: '#10b981',
  successBg: 'rgba(16, 185, 129, 0.15)',
  warning: '#f59e0b',
  warningBg: 'rgba(245, 158, 11, 0.15)',
  error: '#ef4444',
  errorBg: 'rgba(239, 68, 68, 0.15)',
  info: '#06b6d4',

  // Text
  textPrimary: '#f1f5f9',
  textSecondary: '#94a3b8',
  textMuted: '#64748b',

  // Border
  border: 'rgba(71, 85, 105, 0.4)',
  borderLight: 'rgba(148, 163, 184, 0.2)',
};

export const genreColors: Record<string, string> = {
  'All': '#3b82f6',
  'P-Pop': '#f43f5e',
  'SB19 Solo': '#a855f7',
  'OPM Pop': '#ec4899',
  'OPM Ballad': '#06b6d4',
  'OPM Rock': '#ef4444',
  'OPM Indie': '#10b981',
  'OPM Classic': '#f59e0b',
  'OPM Hip-Hop': '#8b5cf6',
};

// Consistent artist colors via string hash
export function getArtistColor(name: string, index?: number): string {
  const palette = [
    '#3b82f6', '#ef4444', '#10b981', '#f59e0b',
    '#8b5cf6', '#ec4899', '#06b6d4', '#f97316',
    '#14b8a6', '#a855f7', '#f43f5e', '#84cc16',
    '#6366f1', '#22d3ee', '#fb923c', '#e879f9',
  ];
  if (index !== undefined) return palette[index % palette.length];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return palette[Math.abs(hash) % palette.length];
}
