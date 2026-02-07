import React, { useMemo, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';
import { useDataStore } from '../store/useDataStore';
import { useFilterStore } from '../store/useFilterStore';
import { getTopMovers } from '../utils/calculations';
import ArtistCard from '../components/ArtistCard';
import GenreBarChart from '../components/GenreBarChart';
import GlassCard from '../components/GlassCard';
import { colors } from '../theme/colors';

export default function TrendsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<any>>();
  const { loading, fetchData, getArtistSummaries } = useDataStore();
  const { trendsPeriod, setTrendsPeriod } = useFilterStore();

  const allSummaries = useMemo(
    () => getArtistSummaries('All'),
    [getArtistSummaries],
  );

  const gainers = useMemo(
    () => getTopMovers(allSummaries, 'gainers', 5, trendsPeriod),
    [allSummaries, trendsPeriod],
  );

  const decliners = useMemo(
    () => getTopMovers(allSummaries, 'decliners', 5, trendsPeriod),
    [allSummaries, trendsPeriod],
  );

  const handleRefresh = useCallback(() => {
    fetchData(true);
  }, [fetchData]);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl
          refreshing={loading}
          onRefresh={handleRefresh}
          tintColor={colors.primary}
          colors={[colors.primary]}
          progressBackgroundColor={colors.surface}
        />
      }
    >
      {/* Period toggle */}
      <View style={styles.periodRow}>
        <Text style={styles.sectionTitle}>Trends</Text>
        <View style={styles.periodToggle}>
          {(['7d', '30d'] as const).map(p => (
            <TouchableOpacity
              key={p}
              style={[
                styles.periodBtn,
                trendsPeriod === p && styles.periodBtnActive,
              ]}
              onPress={() => setTrendsPeriod(p)}
            >
              <Text
                style={[
                  styles.periodBtnText,
                  trendsPeriod === p && styles.periodBtnTextActive,
                ]}
              >
                {p.toUpperCase()}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      </View>

      {/* Top Gainers */}
      <GlassCard style={styles.section}>
        <View style={styles.sectionHeader}>
          <Ionicons name="trending-up" size={18} color={colors.success} />
          <Text style={[styles.sectionLabel, { color: colors.success }]}>
            Top Gainers
          </Text>
        </View>
        {gainers.map(artist => (
          <ArtistCard
            key={artist.name}
            artist={{
              ...artist,
              growthPercent:
                trendsPeriod === '7d'
                  ? artist.growthPercent7d
                  : artist.growthPercent30d,
            }}
            onPress={() =>
              navigation.navigate('ArtistDetail', { artistName: artist.name })
            }
            showGrowthHighlight="gain"
          />
        ))}
        {gainers.length === 0 && (
          <Text style={styles.emptyText}>No data available</Text>
        )}
      </GlassCard>

      {/* Top Decliners */}
      <GlassCard style={styles.section}>
        <View style={styles.sectionHeader}>
          <Ionicons name="trending-down" size={18} color={colors.error} />
          <Text style={[styles.sectionLabel, { color: colors.error }]}>
            Top Decliners
          </Text>
        </View>
        {decliners.map(artist => (
          <ArtistCard
            key={artist.name}
            artist={{
              ...artist,
              growthPercent:
                trendsPeriod === '7d'
                  ? artist.growthPercent7d
                  : artist.growthPercent30d,
            }}
            onPress={() =>
              navigation.navigate('ArtistDetail', { artistName: artist.name })
            }
            showGrowthHighlight="decline"
          />
        ))}
        {decliners.length === 0 && (
          <Text style={styles.emptyText}>No data available</Text>
        )}
      </GlassCard>

      {/* Genre Breakdown */}
      <GlassCard style={styles.section}>
        <GenreBarChart summaries={allSummaries} />
      </GlassCard>
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
  periodRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  sectionTitle: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: '700',
  },
  periodToggle: {
    flexDirection: 'row',
    gap: 4,
  },
  periodBtn: {
    paddingHorizontal: 14,
    paddingVertical: 6,
    borderRadius: 8,
    backgroundColor: colors.surface,
  },
  periodBtnActive: {
    backgroundColor: colors.primary,
  },
  periodBtnText: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: '600',
  },
  periodBtnTextActive: {
    color: '#fff',
  },
  section: {
    marginBottom: 16,
  },
  sectionHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  sectionLabel: {
    fontSize: 16,
    fontWeight: '600',
  },
  emptyText: {
    color: colors.textMuted,
    fontSize: 14,
    textAlign: 'center',
    paddingVertical: 20,
  },
});
