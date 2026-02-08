import React, { useMemo, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Linking,
} from 'react-native';
import { useRoute, RouteProp } from '@react-navigation/native';
import { Ionicons } from '@expo/vector-icons';
import { useDataStore } from '../store/useDataStore';
import { useFavoritesStore } from '../store/useFavoritesStore';
import { DateRange } from '../types/data';
import { colors, genreColors } from '../theme/colors';
import { formatNumberFull, formatNumber, formatPercent } from '../utils/formatters';
import GlassCard from '../components/GlassCard';
import StatCard from '../components/StatCard';
import CityList from '../components/CityList';
import ListenerHistoryChart from '../components/ListenerHistoryChart';
import TrackList from '../components/TrackList';

type ParamList = {
  ArtistDetail: { artistName: string };
};

export default function ArtistDetailScreen() {
  const route = useRoute<RouteProp<ParamList, 'ArtistDetail'>>();
  const { artistName } = route.params;
  const { getArtistDetail, getArtistTracks } = useDataStore();
  const isFavorite = useFavoritesStore(s => s.favorites.includes(artistName));
  const toggleFavorite = useFavoritesStore(s => s.toggleFavorite);
  const [chartRange, setChartRange] = useState<DateRange>('30');

  const artist = useMemo(
    () => getArtistDetail(artistName),
    [getArtistDetail, artistName],
  );

  const tracks = useMemo(
    () => getArtistTracks(artistName),
    [getArtistTracks, artistName],
  );

  const totalStreams = useMemo(
    () => tracks.reduce((sum, t) => sum + t.currentStreams, 0),
    [tracks],
  );
  const totalStreamChange = useMemo(
    () => tracks.reduce((sum, t) => sum + t.change, 0),
    [tracks],
  );

  if (!artist) {
    return (
      <View style={styles.container}>
        <Text style={styles.errorText}>Artist not found</Text>
      </View>
    );
  }

  const genreColor = genreColors[artist.genre] || colors.primary;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {/* Header */}
      <View style={styles.header}>
        <View>
          <Text style={styles.artistName}>{artist.name}</Text>
          <View style={[styles.genreBadge, { backgroundColor: genreColor + '30' }]}>
            <Text style={[styles.genreText, { color: genreColor }]}>
              {artist.genre}
            </Text>
          </View>
        </View>
        <View style={styles.headerActions}>
          <TouchableOpacity
            style={styles.favBtn}
            onPress={() => toggleFavorite(artistName)}
          >
            <Ionicons
              name={isFavorite ? 'heart' : 'heart-outline'}
              size={22}
              color={isFavorite ? '#f43f5e' : colors.textMuted}
            />
          </TouchableOpacity>
          {artist.spotifyUrl ? (
            <TouchableOpacity
              style={styles.spotifyBtn}
              onPress={() => Linking.openURL(artist.spotifyUrl)}
            >
              <Ionicons name="musical-note" size={16} color="#1DB954" />
              <Text style={styles.spotifyText}>Spotify</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      </View>

      {/* Main stats */}
      <GlassCard style={styles.mainStats}>
        <Text style={styles.listenersLabel}>Monthly Listeners</Text>
        <Text style={styles.listenersValue}>
          {formatNumberFull(artist.currentListeners)}
        </Text>
        {artist.followers > 0 && (
          <Text style={styles.followersText}>
            {formatNumberFull(artist.followers)} followers
          </Text>
        )}
      </GlassCard>

      {/* Stats grid */}
      <View style={styles.statsGrid}>
        <View style={styles.statsRow}>
          <StatCard
            label="ATH"
            value={formatNumber(artist.allTimeHigh)}
            color={colors.success}
          />
          <StatCard
            label="7D Change"
            value={formatPercent(artist.growthPercent7d)}
            color={artist.growthPercent7d >= 0 ? colors.success : colors.error}
          />
        </View>
        <View style={styles.statsRow}>
          <StatCard
            label="ATL"
            value={formatNumber(artist.allTimeLow)}
            color={colors.error}
          />
          <StatCard
            label="30D Change"
            value={formatPercent(artist.growthPercent30d)}
            color={artist.growthPercent30d >= 0 ? colors.success : colors.error}
          />
        </View>
        <View style={styles.statsRow}>
          <StatCard label="Days Tracked" value={String(artist.daysTracked)} />
          <StatCard
            label="Average"
            value={formatNumber(artist.averageListeners)}
          />
        </View>
      </View>

      {/* Total Streams */}
      {tracks.length > 0 && totalStreams > 0 && (
        <GlassCard style={styles.totalStreamsCard}>
          <Text style={styles.listenersLabel}>Total Streams</Text>
          <Text style={styles.listenersValue}>
            {formatNumberFull(totalStreams)}
          </Text>
          <View style={styles.streamChangeRow}>
            {totalStreamChange !== 0 && (
              <>
                <Ionicons
                  name={totalStreamChange >= 0 ? 'trending-up' : 'trending-down'}
                  size={16}
                  color={totalStreamChange >= 0 ? colors.success : colors.error}
                />
                <Text
                  style={[
                    styles.streamChangeText,
                    { color: totalStreamChange >= 0 ? colors.success : colors.error },
                  ]}
                >
                  {totalStreamChange >= 0 ? '+' : ''}
                  {formatNumber(totalStreamChange)} today
                </Text>
              </>
            )}
          </View>
          <Text style={styles.trackCountText}>
            across {tracks.length} track{tracks.length !== 1 ? 's' : ''}
          </Text>
        </GlassCard>
      )}

      {/* Cities */}
      <GlassCard style={styles.section}>
        <CityList cities={artist.cities} />
      </GlassCard>

      {/* Listener History Chart */}
      <GlassCard style={styles.section}>
        <ListenerHistoryChart
          history={artist.history}
          range={chartRange}
          onRangeChange={setChartRange}
        />
      </GlassCard>

      {/* Tracks (conditional) */}
      {tracks.length > 0 && (
        <GlassCard style={styles.section}>
          <TrackList tracks={tracks} />
        </GlassCard>
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
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    marginBottom: 16,
  },
  artistName: {
    color: colors.textPrimary,
    fontSize: 28,
    fontWeight: '700',
    marginBottom: 8,
  },
  genreBadge: {
    alignSelf: 'flex-start',
    paddingHorizontal: 12,
    paddingVertical: 4,
    borderRadius: 12,
  },
  genreText: {
    fontSize: 13,
    fontWeight: '600',
  },
  headerActions: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
  },
  favBtn: {
    padding: 8,
    borderRadius: 10,
    backgroundColor: 'rgba(244, 63, 94, 0.1)',
  },
  spotifyBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    backgroundColor: 'rgba(29, 185, 84, 0.15)',
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: 'rgba(29, 185, 84, 0.3)',
  },
  spotifyText: {
    color: '#1DB954',
    fontSize: 13,
    fontWeight: '600',
  },
  mainStats: {
    marginBottom: 16,
    alignItems: 'center',
  },
  listenersLabel: {
    color: colors.textMuted,
    fontSize: 12,
    fontWeight: '500',
    textTransform: 'uppercase',
    letterSpacing: 1,
    marginBottom: 4,
  },
  listenersValue: {
    color: colors.textPrimary,
    fontSize: 32,
    fontWeight: '700',
  },
  followersText: {
    color: colors.textSecondary,
    fontSize: 14,
    marginTop: 4,
  },
  statsGrid: {
    gap: 8,
    marginBottom: 16,
  },
  statsRow: {
    flexDirection: 'row',
    gap: 8,
  },
  totalStreamsCard: {
    marginBottom: 16,
    alignItems: 'center',
  },
  streamChangeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginTop: 6,
  },
  streamChangeText: {
    fontSize: 14,
    fontWeight: '600',
  },
  trackCountText: {
    color: colors.textMuted,
    fontSize: 13,
    marginTop: 4,
  },
  section: {
    marginBottom: 16,
  },
  errorText: {
    color: colors.textMuted,
    fontSize: 16,
    textAlign: 'center',
    marginTop: 60,
  },
});
