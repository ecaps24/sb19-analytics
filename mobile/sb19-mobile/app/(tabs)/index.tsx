import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  Pressable,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useAppStore } from '../../services/store';
import { StatCard } from '../../components/cards/StatCard';
import { TrackCard } from '../../components/cards/TrackCard';
import { AlbumChart } from '../../components/charts/AlbumChart';
import { MemberChart } from '../../components/charts/MemberChart';
import { LoadingSpinner } from '../../components/ui/LoadingSpinner';
import { formatNumber, formatDateTime } from '../../hooks/useFormatters';
import { RANGE_PRESETS } from '../../constants';
import { router } from 'expo-router';

export default function DashboardScreen() {
  const isLoading = useAppStore((state) => state.isLoading);
  const error = useAppStore((state) => state.error);
  const network = useAppStore((state) => state.network);
  const rangePreset = useAppStore((state) => state.rangePreset);
  const setRangePreset = useAppStore((state) => state.setRangePreset);
  const loadData = useAppStore((state) => state.loadData);
  const getDashboardStats = useAppStore((state) => state.getDashboardStats);
  const getFilteredTracks = useAppStore((state) => state.getFilteredTracks);
  const { changes, label } = useAppStore((state) => state.getPeriodChange());

  const [refreshing, setRefreshing] = React.useState(false);

  const stats = getDashboardStats();
  const topTracks = getFilteredTracks().slice(0, 10);

  const onRefresh = React.useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, [loadData]);

  if (isLoading && !refreshing) {
    return (
      <SafeAreaView style={styles.container}>
        <LoadingSpinner message="Loading SB19 Analytics..." />
      </SafeAreaView>
    );
  }

  if (error) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={48} color="#ef4444" />
          <Text style={styles.errorTitle}>Failed to load data</Text>
          <Text style={styles.errorMessage}>{error}</Text>
          <Pressable style={styles.retryButton} onPress={onRefresh}>
            <Text style={styles.retryButtonText}>Retry</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={refreshing}
            onRefresh={onRefresh}
            tintColor="#60a5fa"
            colors={['#60a5fa']}
          />
        }
      >
        {/* Header */}
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>SB19 Analytics</Text>
            <View style={styles.statusRow}>
              <View style={[
                styles.statusDot,
                { backgroundColor: network.isConnected ? '#34d399' : '#fbbf24' }
              ]} />
              <Text style={styles.lastUpdated}>
                {network.isConnected ? 'Online' : 'Offline'} • Updated {formatDateTime(stats.lastUpdated)}
              </Text>
            </View>
          </View>
          <Pressable onPress={onRefresh} style={styles.refreshButton}>
            <Ionicons name="refresh" size={22} color="#60a5fa" />
          </Pressable>
        </View>

        {/* Range Selector */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.rangeSelector}
          contentContainerStyle={styles.rangeSelectorContent}
        >
          {RANGE_PRESETS.map((preset) => (
            <Pressable
              key={preset.value}
              style={[
                styles.rangeChip,
                rangePreset === preset.value && styles.rangeChipActive,
              ]}
              onPress={() => setRangePreset(preset.value)}
            >
              <Text style={[
                styles.rangeChipText,
                rangePreset === preset.value && styles.rangeChipTextActive,
              ]}>
                {preset.label}
              </Text>
            </Pressable>
          ))}
        </ScrollView>

        {/* Stats Cards */}
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.statsScroll}
          contentContainerStyle={styles.statsContent}
        >
          <StatCard
            title="Monthly Listeners"
            value={formatNumber(stats.currentListeners)}
            change={stats.listenerChange}
            changeLabel="from previous"
            icon="people"
            iconColor="#60a5fa"
          />
          <StatCard
            title="Total Streams"
            value={formatNumber(stats.totalStreams)}
            change={stats.streamChange}
            changeLabel={label.replace(' +/-', '')}
            icon="play-circle"
            iconColor="#34d399"
          />
          <StatCard
            title="All-Time High"
            value={formatNumber(stats.allTimeHigh)}
            subtitle="Historical Peak"
            icon="trophy"
            iconColor="#fbbf24"
          />
          <StatCard
            title="Total Tracks"
            value={stats.totalTracks}
            subtitle="Across all releases"
            icon="musical-notes"
            iconColor="#a78bfa"
          />
        </ScrollView>

        {/* Top Track */}
        {stats.topTrack && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Top Track</Text>
            <TrackCard
              track={stats.topTrack}
              onPress={() => router.push(`/track/${encodeURIComponent(stats.topTrack!.song_title)}`)}
            />
          </View>
        )}

        {/* Album Chart */}
        <View style={styles.section}>
          <AlbumChart />
        </View>

        {/* Member Chart */}
        <View style={styles.section}>
          <MemberChart />
        </View>

        {/* Top 10 Tracks */}
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text style={styles.sectionTitle}>Top 10 Tracks</Text>
            <Pressable onPress={() => router.push('/tracks')}>
              <Text style={styles.seeAllText}>See All</Text>
            </Pressable>
          </View>
          {topTracks.map((track) => (
            <TrackCard
              key={track.song_title}
              track={track}
              onPress={() => router.push(`/track/${encodeURIComponent(track.song_title)}`)}
            />
          ))}
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0c29',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 24,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 16,
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    color: '#ffffff',
    marginBottom: 4,
  },
  statusRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  lastUpdated: {
    fontSize: 12,
    color: '#9ca3af',
  },
  refreshButton: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: 'rgba(96, 165, 250, 0.1)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  rangeSelector: {
    marginBottom: 16,
  },
  rangeSelectorContent: {
    paddingHorizontal: 16,
    gap: 8,
  },
  rangeChip: {
    paddingVertical: 8,
    paddingHorizontal: 16,
    borderRadius: 20,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    marginRight: 8,
  },
  rangeChipActive: {
    backgroundColor: '#60a5fa',
    borderColor: '#60a5fa',
  },
  rangeChipText: {
    fontSize: 13,
    fontWeight: '500',
    color: '#9ca3af',
  },
  rangeChipTextActive: {
    color: '#ffffff',
  },
  statsScroll: {
    marginBottom: 20,
  },
  statsContent: {
    paddingHorizontal: 16,
  },
  section: {
    paddingHorizontal: 16,
    marginBottom: 8,
  },
  sectionHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: '#ffffff',
    marginBottom: 12,
  },
  seeAllText: {
    fontSize: 14,
    color: '#60a5fa',
    fontWeight: '500',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorTitle: {
    fontSize: 18,
    fontWeight: '600',
    color: '#ffffff',
    marginTop: 16,
    marginBottom: 8,
  },
  errorMessage: {
    fontSize: 14,
    color: '#9ca3af',
    textAlign: 'center',
    marginBottom: 24,
  },
  retryButton: {
    backgroundColor: '#60a5fa',
    paddingVertical: 12,
    paddingHorizontal: 32,
    borderRadius: 8,
  },
  retryButtonText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '600',
  },
});
