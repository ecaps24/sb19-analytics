import React, { useMemo } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { ArtistSummary } from '../types/data';
import { colors, genreColors } from '../theme/colors';
import { formatNumber } from '../utils/formatters';

interface GenreBarChartProps {
  summaries: ArtistSummary[];
}

export default function GenreBarChart({ summaries }: GenreBarChartProps) {
  const genreData = useMemo(() => {
    const genreMap = new Map<string, { total: number; count: number }>();
    for (const s of summaries) {
      if (!s.genre) continue;
      const existing = genreMap.get(s.genre) || { total: 0, count: 0 };
      existing.total += s.currentListeners;
      existing.count += 1;
      genreMap.set(s.genre, existing);
    }

    const result = Array.from(genreMap.entries())
      .map(([genre, { total, count }]) => ({
        genre,
        average: Math.round(total / count),
        count,
      }))
      .sort((a, b) => b.average - a.average);

    return result;
  }, [summaries]);

  if (genreData.length === 0) return null;

  const maxAvg = genreData[0]?.average || 1;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Average Listeners by Genre</Text>
      {genreData.map(({ genre, average, count }) => {
        const barWidth = (average / maxAvg) * 100;
        const color = genreColors[genre] || colors.primary;
        return (
          <View key={genre} style={styles.row}>
            <View style={styles.labelContainer}>
              <Text style={styles.genreName}>{genre}</Text>
              <Text style={styles.count}>({count})</Text>
            </View>
            <View style={styles.barContainer}>
              <View style={styles.barBg}>
                <View
                  style={[styles.barFill, { width: `${barWidth}%`, backgroundColor: color }]}
                />
              </View>
              <Text style={styles.value}>{formatNumber(average)}</Text>
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginTop: 8,
  },
  title: {
    color: colors.textPrimary,
    fontSize: 17,
    fontWeight: '700',
    marginBottom: 16,
  },
  row: {
    marginBottom: 14,
  },
  labelContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 4,
  },
  genreName: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: '600',
  },
  count: {
    color: colors.textMuted,
    fontSize: 11,
  },
  barContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  barBg: {
    flex: 1,
    height: 18,
    backgroundColor: colors.surfaceLight,
    borderRadius: 9,
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    borderRadius: 9,
  },
  value: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: '600',
    width: 55,
    textAlign: 'right',
  },
});
