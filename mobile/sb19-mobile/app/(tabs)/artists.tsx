import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useAppStore } from '../../services/store';
import { MemberChart } from '../../components/charts/MemberChart';
import { ListenersChart } from '../../components/charts/ListenersChart';
import { GlassCard } from '../../components/ui/GlassCard';
import { formatNumber } from '../../hooks/useFormatters';

export default function ArtistsScreen() {
  const loadData = useAppStore((state) => state.loadData);
  const getMemberStats = useAppStore((state) => state.getMemberStats);
  const getDashboardStats = useAppStore((state) => state.getDashboardStats);

  const [refreshing, setRefreshing] = React.useState(false);

  const memberStats = getMemberStats();
  const dashboardStats = getDashboardStats();

  const onRefresh = React.useCallback(async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  }, [loadData]);

  // Calculate totals
  const totalMemberStreams = memberStats.reduce((sum, m) => sum + m.totalStreams, 0);
  const totalMemberTracks = memberStats.reduce((sum, m) => sum + m.trackCount, 0);

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
          <Text style={styles.title}>Artists</Text>
          <Text style={styles.subtitle}>
            SB19 & Solo Projects Comparison
          </Text>
        </View>

        {/* SB19 Overview Card */}
        <GlassCard style={styles.overviewCard}>
          <View style={styles.overviewHeader}>
            <Text style={styles.overviewTitle}>SB19</Text>
            <View style={[styles.statusBadge]}>
              <Text style={styles.statusText}>Group</Text>
            </View>
          </View>

          <View style={styles.overviewStats}>
            <View style={styles.overviewStat}>
              <Text style={styles.overviewValue}>
                {formatNumber(dashboardStats.currentListeners)}
              </Text>
              <Text style={styles.overviewLabel}>Monthly Listeners</Text>
            </View>
            <View style={styles.divider} />
            <View style={styles.overviewStat}>
              <Text style={styles.overviewValue}>
                {formatNumber(dashboardStats.totalStreams)}
              </Text>
              <Text style={styles.overviewLabel}>Total Streams</Text>
            </View>
            <View style={styles.divider} />
            <View style={styles.overviewStat}>
              <Text style={styles.overviewValue}>{dashboardStats.totalTracks}</Text>
              <Text style={styles.overviewLabel}>Tracks</Text>
            </View>
          </View>
        </GlassCard>

        {/* Solo Projects Overview */}
        <GlassCard style={styles.overviewCard}>
          <View style={styles.overviewHeader}>
            <Text style={styles.overviewTitle}>Solo Projects</Text>
            <View style={[styles.statusBadge, styles.statusBadgeSolo]}>
              <Text style={styles.statusText}>5 Artists</Text>
            </View>
          </View>

          <View style={styles.overviewStats}>
            <View style={styles.overviewStat}>
              <Text style={styles.overviewValue}>
                {formatNumber(totalMemberStreams)}
              </Text>
              <Text style={styles.overviewLabel}>Combined Streams</Text>
            </View>
            <View style={styles.divider} />
            <View style={styles.overviewStat}>
              <Text style={styles.overviewValue}>{totalMemberTracks}</Text>
              <Text style={styles.overviewLabel}>Total Tracks</Text>
            </View>
          </View>
        </GlassCard>

        {/* Member Streams Chart */}
        <View style={styles.section}>
          <MemberChart />
        </View>

        {/* Listeners Comparison Chart */}
        <View style={styles.section}>
          <ListenersChart />
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
  subtitle: {
    fontSize: 13,
    color: '#9ca3af',
  },
  overviewCard: {
    marginHorizontal: 16,
    marginBottom: 16,
  },
  overviewHeader: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  overviewTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: '#ffffff',
  },
  statusBadge: {
    paddingVertical: 4,
    paddingHorizontal: 10,
    borderRadius: 12,
    backgroundColor: 'rgba(96, 165, 250, 0.2)',
  },
  statusBadgeSolo: {
    backgroundColor: 'rgba(167, 139, 250, 0.2)',
  },
  statusText: {
    color: '#60a5fa',
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  overviewStats: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  overviewStat: {
    flex: 1,
    alignItems: 'center',
  },
  overviewValue: {
    fontSize: 18,
    fontWeight: '700',
    color: '#ffffff',
    marginBottom: 4,
  },
  overviewLabel: {
    fontSize: 11,
    color: '#9ca3af',
    textAlign: 'center',
  },
  divider: {
    width: 1,
    height: 40,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    marginHorizontal: 8,
  },
  section: {
    paddingHorizontal: 16,
  },
});
