import React, { useMemo, useState } from 'react';
import { View, Text, StyleSheet, Dimensions, Pressable, ScrollView } from 'react-native';
import { LineChart } from 'react-native-gifted-charts';
import { useAppStore } from '../../services/store';
import { formatNumber } from '../../hooks/useFormatters';
import { GlassCard } from '../ui/GlassCard';
import { CHART_COLORS } from '../../constants';

const { width } = Dimensions.get('window');

const COMPARE_ARTISTS = [
  { name: 'SB19', color: CHART_COLORS.SB19.border },
  { name: 'BINI', color: '#a78bfa' },
  { name: 'Pablo', color: CHART_COLORS.Pablo.border },
  { name: 'Josh Cullen', color: CHART_COLORS['Josh Cullen'].border },
  { name: 'STELL', color: CHART_COLORS.STELL.border },
  { name: 'felip', color: CHART_COLORS.felip.border },
  { name: 'Justin', color: CHART_COLORS.Justin.border },
];

export function ListenersChart() {
  const listenersData = useAppStore((state) => state.listenersData);
  const [selectedArtists, setSelectedArtists] = useState<string[]>(['SB19']);

  const chartData = useMemo(() => {
    // Get all unique dates
    const dateSet = new Set<string>();
    listenersData.forEach(d => {
      const date = d.data_date.split(' ')[0];
      dateSet.add(date);
    });
    const dates = Array.from(dateSet).sort().slice(-30); // Last 30 data points

    // Create data series for each selected artist
    const series: { data: { value: number; label: string }[]; color: string }[] = [];

    selectedArtists.forEach((artistName) => {
      const artistData = listenersData.filter(d =>
        d.artist_name.toLowerCase() === artistName.toLowerCase()
      );

      const artistColor = COMPARE_ARTISTS.find(a =>
        a.name.toLowerCase() === artistName.toLowerCase()
      )?.color || '#60a5fa';

      const points = dates.map((date, i) => {
        const dataPoint = artistData.find(d => d.data_date.split(' ')[0] === date);
        return {
          value: dataPoint ? dataPoint.monthly_listeners / 1_000_000 : 0,
          label: i % 5 === 0 ? new Date(date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '',
        };
      });

      series.push({ data: points, color: artistColor });
    });

    return series;
  }, [listenersData, selectedArtists]);

  const toggleArtist = (name: string) => {
    if (name === 'SB19') return; // SB19 is always selected

    setSelectedArtists((prev) => {
      if (prev.includes(name)) {
        return prev.filter(a => a !== name);
      }
      return [...prev, name];
    });
  };

  // Get latest values for display
  const latestValues = useMemo(() => {
    const result: Record<string, number> = {};
    selectedArtists.forEach(artist => {
      const artistData = listenersData
        .filter(d => d.artist_name.toLowerCase() === artist.toLowerCase())
        .sort((a, b) => new Date(b.data_date).getTime() - new Date(a.data_date).getTime());
      result[artist] = artistData[0]?.monthly_listeners || 0;
    });
    return result;
  }, [listenersData, selectedArtists]);

  return (
    <GlassCard style={styles.container}>
      <Text style={styles.title}>Monthly Listeners Trend</Text>

      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.artistSelector}>
        {COMPARE_ARTISTS.map((artist) => {
          const isSelected = selectedArtists.includes(artist.name);
          const isRequired = artist.name === 'SB19';

          return (
            <Pressable
              key={artist.name}
              onPress={() => toggleArtist(artist.name)}
              style={[
                styles.artistChip,
                isSelected && styles.artistChipSelected,
                { borderColor: artist.color },
              ]}
            >
              <View style={[styles.artistDot, { backgroundColor: artist.color }]} />
              <Text style={[
                styles.artistChipText,
                isSelected && styles.artistChipTextSelected,
              ]}>
                {artist.name}
              </Text>
              {isRequired && <Text style={styles.requiredBadge}>✓</Text>}
            </Pressable>
          );
        })}
      </ScrollView>

      {chartData.length > 0 && chartData[0].data.length > 0 ? (
        <View style={styles.chartContainer}>
          <LineChart
            data={chartData[0].data}
            data2={chartData[1]?.data}
            data3={chartData[2]?.data}
            color={chartData[0].color}
            color2={chartData[1]?.color}
            color3={chartData[2]?.color}
            thickness={2}
            thickness2={2}
            thickness3={2}
            hideDataPoints
            curved
            hideRules
            yAxisThickness={0}
            xAxisThickness={1}
            xAxisColor="rgba(255, 255, 255, 0.1)"
            yAxisTextStyle={styles.axisText}
            xAxisLabelTextStyle={styles.xAxisLabel}
            width={width - 80}
            height={160}
            noOfSections={4}
            yAxisLabelSuffix="M"
            isAnimated
            animationDuration={800}
            adjustToWidth
            initialSpacing={10}
            endSpacing={10}
          />
        </View>
      ) : (
        <View style={styles.emptyContainer}>
          <Text style={styles.emptyText}>No listener data available</Text>
        </View>
      )}

      <View style={styles.latestValues}>
        {selectedArtists.map((artist) => {
          const color = COMPARE_ARTISTS.find(a =>
            a.name.toLowerCase() === artist.toLowerCase()
          )?.color || '#60a5fa';

          return (
            <View key={artist} style={styles.valueRow}>
              <View style={[styles.valueDot, { backgroundColor: color }]} />
              <Text style={styles.artistName}>{artist}</Text>
              <Text style={styles.valueText}>
                {formatNumber(latestValues[artist])}
              </Text>
            </View>
          );
        })}
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
    marginBottom: 12,
  },
  artistSelector: {
    flexDirection: 'row',
    marginBottom: 16,
  },
  artistChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 16,
    borderWidth: 1,
    marginRight: 8,
    gap: 6,
  },
  artistChipSelected: {
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
  },
  artistDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  artistChipText: {
    color: '#9ca3af',
    fontSize: 12,
    fontWeight: '500',
  },
  artistChipTextSelected: {
    color: '#ffffff',
  },
  requiredBadge: {
    color: '#34d399',
    fontSize: 10,
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
  },
  emptyContainer: {
    height: 160,
    justifyContent: 'center',
    alignItems: 'center',
  },
  emptyText: {
    color: '#6b7280',
    fontSize: 14,
  },
  latestValues: {
    gap: 8,
  },
  valueRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  valueDot: {
    width: 10,
    height: 10,
    borderRadius: 5,
  },
  artistName: {
    color: '#d1d5db',
    fontSize: 13,
    flex: 1,
  },
  valueText: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '600',
  },
});
