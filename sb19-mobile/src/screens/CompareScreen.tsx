import React, { useMemo, useState } from 'react';
import { View, Text, StyleSheet, ScrollView } from 'react-native';
import { useDataStore } from '../store/useDataStore';
import { useFilterStore } from '../store/useFilterStore';
import { DateRange } from '../types/data';
import ArtistSelector from '../components/ArtistSelector';
import ArtistChip from '../components/ArtistChip';
import ListenerHistoryChart from '../components/ListenerHistoryChart';
import GlassCard from '../components/GlassCard';
import StatCard from '../components/StatCard';
import { colors, getArtistColor } from '../theme/colors';
import { formatNumber, formatPercent } from '../utils/formatters';

export default function CompareScreen() {
  const { getArtistSummaries, getArtistDetail } = useDataStore();
  const {
    compareArtists,
    addCompareArtist,
    removeCompareArtist,
  } = useFilterStore();
  const [chartRange, setChartRange] = useState<DateRange>('30');

  const allSummaries = useMemo(
    () => getArtistSummaries('All'),
    [getArtistSummaries],
  );

  const selectedDetails = useMemo(
    () =>
      compareArtists
        .map(name => getArtistDetail(name))
        .filter(Boolean) as NonNullable<ReturnType<typeof getArtistDetail>>[],
    [compareArtists, getArtistDetail],
  );

  const chartDatasets = useMemo(
    () =>
      selectedDetails.map(a => ({
        name: a.name,
        history: a.history,
      })),
    [selectedDetails],
  );

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Compare Artists</Text>
      <Text style={styles.subtitle}>
        Select up to 4 artists to compare
      </Text>

      {/* Selector */}
      <ArtistSelector
        summaries={allSummaries}
        selectedNames={compareArtists}
        onSelect={addCompareArtist}
      />

      {/* Selected chips */}
      {compareArtists.length > 0 && (
        <View style={styles.chips}>
          {compareArtists.map((name, i) => (
            <ArtistChip
              key={name}
              name={name}
              index={i}
              onRemove={() => removeCompareArtist(name)}
            />
          ))}
        </View>
      )}

      {/* Chart */}
      {selectedDetails.length >= 2 ? (
        <>
          <GlassCard style={styles.section}>
            <ListenerHistoryChart
              datasets={chartDatasets}
              range={chartRange}
              onRangeChange={setChartRange}
            />
          </GlassCard>

          {/* Stats comparison table */}
          <GlassCard style={styles.section}>
            <Text style={styles.sectionTitle}>Stats Comparison</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View>
                {/* Header row */}
                <View style={styles.tableRow}>
                  <View style={styles.tableLabel} />
                  {selectedDetails.map((a, i) => (
                    <View key={a.name} style={styles.tableCell}>
                      <View
                        style={[
                          styles.dot,
                          { backgroundColor: getArtistColor(a.name, i) },
                        ]}
                      />
                      <Text style={styles.tableName} numberOfLines={1}>
                        {a.name}
                      </Text>
                    </View>
                  ))}
                </View>

                {/* Data rows */}
                {[
                  {
                    label: 'Listeners',
                    getValue: (a: typeof selectedDetails[0]) =>
                      formatNumber(a.currentListeners),
                  },
                  {
                    label: '7D Growth',
                    getValue: (a: typeof selectedDetails[0]) =>
                      formatPercent(a.growthPercent7d),
                  },
                  {
                    label: '30D Growth',
                    getValue: (a: typeof selectedDetails[0]) =>
                      formatPercent(a.growthPercent30d),
                  },
                  {
                    label: 'Followers',
                    getValue: (a: typeof selectedDetails[0]) =>
                      formatNumber(a.followers),
                  },
                  {
                    label: 'ATH',
                    getValue: (a: typeof selectedDetails[0]) =>
                      formatNumber(a.allTimeHigh),
                  },
                  {
                    label: 'Days',
                    getValue: (a: typeof selectedDetails[0]) =>
                      String(a.daysTracked),
                  },
                ].map(row => (
                  <View key={row.label} style={styles.tableRow}>
                    <View style={styles.tableLabel}>
                      <Text style={styles.tableLabelText}>{row.label}</Text>
                    </View>
                    {selectedDetails.map(a => (
                      <View key={a.name} style={styles.tableCell}>
                        <Text style={styles.tableValue}>
                          {row.getValue(a)}
                        </Text>
                      </View>
                    ))}
                  </View>
                ))}
              </View>
            </ScrollView>
          </GlassCard>
        </>
      ) : compareArtists.length === 1 ? (
        <View style={styles.hint}>
          <Text style={styles.hintText}>
            Select at least one more artist to compare
          </Text>
        </View>
      ) : (
        <View style={styles.hint}>
          <Text style={styles.hintText}>
            Search and select artists above to start comparing
          </Text>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  title: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: '700',
    marginBottom: 4,
  },
  subtitle: {
    color: colors.textMuted,
    fontSize: 14,
    marginBottom: 16,
  },
  chips: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 12,
    marginBottom: 4,
  },
  section: {
    marginTop: 16,
  },
  sectionTitle: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 12,
  },
  tableRow: {
    flexDirection: 'row',
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  tableLabel: {
    width: 80,
    paddingVertical: 10,
    justifyContent: 'center',
  },
  tableLabelText: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: '500',
  },
  tableCell: {
    width: 90,
    paddingVertical: 10,
    alignItems: 'center',
  },
  dot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    marginBottom: 4,
  },
  tableName: {
    color: colors.textPrimary,
    fontSize: 11,
    fontWeight: '600',
    textAlign: 'center',
  },
  tableValue: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: '500',
  },
  hint: {
    alignItems: 'center',
    paddingTop: 60,
  },
  hintText: {
    color: colors.textMuted,
    fontSize: 15,
    textAlign: 'center',
  },
});
