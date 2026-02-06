import React from 'react';
import { View, Text, StyleSheet, Dimensions, Platform } from 'react-native';
import { useAppStore } from '../../services/store';
import { formatNumber } from '../../hooks/useFormatters';
import { GlassCard } from '../ui/GlassCard';
import { ALBUM_COLORS } from '../../constants';

const { width } = Dimensions.get('window');

// Conditionally import BarChart only on native
let BarChart: any = null;
if (Platform.OS !== 'web') {
  BarChart = require('react-native-gifted-charts').BarChart;
}

export function AlbumChart() {
  const getAlbumStats = useAppStore((state) => state.getAlbumStats);
  const setFilters = useAppStore((state) => state.setFilters);

  const albumStats = getAlbumStats();

  if (albumStats.length === 0) {
    return (
      <GlassCard style={styles.container}>
        <Text style={styles.title}>Streams by Album</Text>
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyText}>No data available</Text>
        </View>
      </GlassCard>
    );
  }

  // Web fallback - show simple list
  if (Platform.OS === 'web' || !BarChart) {
    return (
      <GlassCard style={styles.container}>
        <Text style={styles.title}>Streams by Album</Text>
        <View style={styles.webFallback}>
          {albumStats.map((album) => (
            <View key={album.name} style={styles.albumRow}>
              <View
                style={[
                  styles.albumBar,
                  {
                    backgroundColor: ALBUM_COLORS[album.name] || '#9ca3af',
                    width: `${(album.totalStreams / albumStats[0].totalStreams) * 100}%`,
                  },
                ]}
              />
              <View style={styles.albumInfo}>
                <Text style={styles.albumName} numberOfLines={1}>{album.name}</Text>
                <Text style={styles.albumStreams}>{formatNumber(album.totalStreams)}</Text>
              </View>
            </View>
          ))}
        </View>
      </GlassCard>
    );
  }

  const barData = albumStats.map((album) => ({
    value: album.totalStreams / 1_000_000,
    label: album.name.length > 10 ? album.name.substring(0, 10) + '...' : album.name,
    frontColor: ALBUM_COLORS[album.name] || 'rgba(156, 163, 175, 0.8)',
    topLabelComponent: () => (
      <Text style={styles.barLabel}>
        {formatNumber(album.totalStreams)}
      </Text>
    ),
    onPress: () => setFilters({ album: album.name }),
  }));

  return (
    <GlassCard style={styles.container}>
      <Text style={styles.title}>Streams by Album</Text>

      <View style={styles.chartContainer}>
        <BarChart
          data={barData}
          barWidth={32}
          spacing={16}
          roundedTop
          roundedBottom
          hideRules
          xAxisThickness={1}
          yAxisThickness={0}
          xAxisColor="rgba(255, 255, 255, 0.1)"
          yAxisColor="rgba(255, 255, 255, 0.1)"
          yAxisTextStyle={styles.axisText}
          xAxisLabelTextStyle={styles.xAxisLabel}
          noOfSections={4}
          maxValue={Math.max(...barData.map(d => d.value)) * 1.2}
          width={width - 80}
          height={180}
          isAnimated
          animationDuration={500}
          barBorderRadius={4}
          yAxisLabelSuffix="M"
        />
      </View>

      <View style={styles.legend}>
        {albumStats.slice(0, 4).map((album) => (
          <View key={album.name} style={styles.legendItem}>
            <View
              style={[
                styles.legendDot,
                { backgroundColor: ALBUM_COLORS[album.name] || '#9ca3af' },
              ]}
            />
            <Text style={styles.legendText} numberOfLines={1}>
              {album.name}
            </Text>
            <Text style={styles.legendValue}>
              {album.trackCount} tracks
            </Text>
          </View>
        ))}
      </View>
    </GlassCard>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: 16,
  },
  title: {
    fontSize: 18,
    fontWeight: '700',
    color: '#ffffff',
    marginBottom: 16,
  },
  chartContainer: {
    alignItems: 'center',
    marginBottom: 16,
  },
  axisText: {
    color: '#9ca3af',
    fontSize: 10,
  },
  xAxisLabel: {
    color: '#9ca3af',
    fontSize: 9,
    width: 50,
    textAlign: 'center',
  },
  barLabel: {
    color: '#ffffff',
    fontSize: 10,
    fontWeight: '600',
    marginBottom: 4,
  },
  legend: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
  },
  legendItem: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    minWidth: '45%',
  },
  legendDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  legendText: {
    color: '#d1d5db',
    fontSize: 12,
    flex: 1,
  },
  legendValue: {
    color: '#6b7280',
    fontSize: 11,
  },
  emptyContainer: {
    height: 200,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyText: {
    color: '#6b7280',
    fontSize: 14,
  },
  webFallback: {
    gap: 12,
  },
  albumRow: {
    position: 'relative',
    height: 40,
    justifyContent: 'center',
  },
  albumBar: {
    position: 'absolute',
    left: 0,
    top: 0,
    bottom: 0,
    borderRadius: 6,
    opacity: 0.3,
  },
  albumInfo: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 12,
  },
  albumName: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '500',
    flex: 1,
  },
  albumStreams: {
    color: '#60a5fa',
    fontSize: 14,
    fontWeight: '600',
  },
});
