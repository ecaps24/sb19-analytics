import React, { useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Pressable,
  Linking,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, router } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { useAppStore } from '../../services/store';
import { GlassCard } from '../../components/ui/GlassCard';
import { formatNumber, formatDateTime } from '../../hooks/useFormatters';

export default function TrackDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const trackTitle = decodeURIComponent(id);

  const getFilteredTracks = useAppStore((state) => state.getFilteredTracks);
  const { changes, label } = useAppStore((state) => state.getPeriodChange());
  const songMetadata = useAppStore((state) => state.songMetadata);
  const tracksMetadata = useAppStore((state) => state.tracksMetadata);

  const track = useMemo(() => {
    const tracks = getFilteredTracks();
    return tracks.find((t) => t.song_title === trackTitle);
  }, [trackTitle, getFilteredTracks]);

  const metadata = useMemo(() => {
    return tracksMetadata.find(
      (m) => m.title.toLowerCase() === trackTitle.toLowerCase()
    );
  }, [trackTitle, tracksMetadata]);

  const songMeta = songMetadata[trackTitle];

  const change = changes[trackTitle] || 0;
  const isPositiveChange = change >= 0;

  const handleOpenSpotify = () => {
    const url = track?.spotify_url || metadata?.spotify_url;
    if (url) {
      Linking.openURL(url);
    }
  };

  if (!track) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} style={styles.backButton}>
            <Ionicons name="arrow-back" size={24} color="#ffffff" />
          </Pressable>
          <Text style={styles.headerTitle}>Track Not Found</Text>
        </View>
        <View style={styles.errorContainer}>
          <Ionicons name="alert-circle" size={48} color="#ef4444" />
          <Text style={styles.errorText}>Track "{trackTitle}" not found</Text>
          <Pressable style={styles.goBackButton} onPress={() => router.back()}>
            <Text style={styles.goBackButtonText}>Go Back</Text>
          </Pressable>
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.backButton}>
          <Ionicons name="arrow-back" size={24} color="#ffffff" />
        </Pressable>
        <Text style={styles.headerTitle} numberOfLines={1}>
          Track Details
        </Text>
        {(track.spotify_url || metadata?.spotify_url) && (
          <Pressable onPress={handleOpenSpotify} style={styles.spotifyButton}>
            <Ionicons name="play-circle" size={28} color="#1DB954" />
          </Pressable>
        )}
      </View>

      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Track Title Card */}
        <GlassCard style={styles.titleCard}>
          <View style={styles.rankBadge}>
            <Text style={styles.rankText}>#{track.rank}</Text>
          </View>
          <Text style={styles.trackTitle}>{track.song_title}</Text>
          <Text style={styles.trackArtist}>{track.artist_name}</Text>

          <View style={styles.metaRow}>
            {track.album && (
              <View style={styles.metaChip}>
                <Ionicons name="disc" size={12} color="#60a5fa" />
                <Text style={styles.metaChipText}>{track.album}</Text>
              </View>
            )}
            {track.year > 0 && (
              <View style={styles.metaChip}>
                <Ionicons name="calendar" size={12} color="#60a5fa" />
                <Text style={styles.metaChipText}>{track.year}</Text>
              </View>
            )}
          </View>
        </GlassCard>

        {/* Stats Card */}
        <GlassCard style={styles.statsCard}>
          <Text style={styles.sectionTitle}>Streaming Stats</Text>

          <View style={styles.statsGrid}>
            <View style={styles.statItem}>
              <Text style={styles.statValue}>
                {formatNumber(track.total_streams)}
              </Text>
              <Text style={styles.statLabel}>Total Streams</Text>
            </View>

            <View style={styles.statItem}>
              <Text
                style={[
                  styles.statValue,
                  { color: change === 0 ? '#6b7280' : isPositiveChange ? '#34d399' : '#ef4444' },
                ]}
              >
                {change === 0 ? '-' : `${isPositiveChange ? '+' : ''}${formatNumber(change)}`}
              </Text>
              <Text style={styles.statLabel}>{label.replace(' +/-', '')}</Text>
            </View>

            {track.rankChange !== null && track.rankChange !== 0 && (
              <View style={styles.statItem}>
                <View style={styles.rankChangeRow}>
                  <Ionicons
                    name={track.rankChange > 0 ? 'caret-up' : 'caret-down'}
                    size={16}
                    color={track.rankChange > 0 ? '#34d399' : '#ef4444'}
                  />
                  <Text
                    style={[
                      styles.statValue,
                      { color: track.rankChange > 0 ? '#34d399' : '#ef4444' },
                    ]}
                  >
                    {Math.abs(track.rankChange)}
                  </Text>
                </View>
                <Text style={styles.statLabel}>Rank Change</Text>
              </View>
            )}
          </View>

          {track.data_date && (
            <View style={styles.lastUpdated}>
              <Ionicons name="time" size={14} color="#6b7280" />
              <Text style={styles.lastUpdatedText}>
                Updated: {formatDateTime(track.data_date)}
              </Text>
            </View>
          )}
        </GlassCard>

        {/* Track Info */}
        {(track.collaborators || metadata?.collaborators) && (
          <GlassCard style={styles.infoCard}>
            <Text style={styles.sectionTitle}>Collaborations</Text>
            <Text style={styles.infoText}>
              {track.collaborators || metadata?.collaborators}
            </Text>
          </GlassCard>
        )}

        {/* Song Metadata (Lyrics, Credits, etc.) */}
        {songMeta && (
          <>
            {songMeta.credits && (
              <GlassCard style={styles.infoCard}>
                <Text style={styles.sectionTitle}>Credits</Text>
                <Text style={styles.infoText}>{songMeta.credits}</Text>
              </GlassCard>
            )}

            {songMeta.history && (
              <GlassCard style={styles.infoCard}>
                <Text style={styles.sectionTitle}>History</Text>
                <Text style={styles.infoText}>{songMeta.history}</Text>
              </GlassCard>
            )}

            {songMeta.milestones && songMeta.milestones.length > 0 && (
              <GlassCard style={styles.infoCard}>
                <Text style={styles.sectionTitle}>Milestones</Text>
                {songMeta.milestones.map((milestone, index) => (
                  <View key={index} style={styles.milestoneRow}>
                    <Ionicons name="trophy" size={16} color="#fbbf24" />
                    <View style={styles.milestoneInfo}>
                      <Text style={styles.milestoneLabel}>{milestone.label}</Text>
                      <Text style={styles.milestoneDate}>{milestone.date}</Text>
                    </View>
                  </View>
                ))}
              </GlassCard>
            )}
          </>
        )}

        {/* Spotify Button */}
        {(track.spotify_url || metadata?.spotify_url) && (
          <Pressable style={styles.spotifyFullButton} onPress={handleOpenSpotify}>
            <Ionicons name="logo-youtube" size={24} color="#ffffff" />
            <Text style={styles.spotifyFullButtonText}>Play on Spotify</Text>
          </Pressable>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0c29',
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: 16,
    paddingVertical: 12,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.1)',
  },
  backButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 12,
  },
  headerTitle: {
    flex: 1,
    fontSize: 18,
    fontWeight: '600',
    color: '#ffffff',
  },
  spotifyButton: {
    width: 40,
    height: 40,
    borderRadius: 20,
    justifyContent: 'center',
    alignItems: 'center',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 40,
  },
  titleCard: {
    alignItems: 'center',
    marginBottom: 16,
  },
  rankBadge: {
    backgroundColor: 'rgba(96, 165, 250, 0.2)',
    paddingVertical: 6,
    paddingHorizontal: 16,
    borderRadius: 16,
    marginBottom: 12,
  },
  rankText: {
    color: '#60a5fa',
    fontSize: 14,
    fontWeight: '700',
  },
  trackTitle: {
    fontSize: 24,
    fontWeight: '800',
    color: '#ffffff',
    textAlign: 'center',
    marginBottom: 8,
  },
  trackArtist: {
    fontSize: 16,
    color: '#9ca3af',
    marginBottom: 12,
  },
  metaRow: {
    flexDirection: 'row',
    gap: 8,
    flexWrap: 'wrap',
    justifyContent: 'center',
  },
  metaChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    paddingVertical: 6,
    paddingHorizontal: 10,
    borderRadius: 12,
  },
  metaChipText: {
    color: '#d1d5db',
    fontSize: 12,
    fontWeight: '500',
  },
  statsCard: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 14,
    fontWeight: '600',
    color: '#9ca3af',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 12,
  },
  statsGrid: {
    flexDirection: 'row',
    justifyContent: 'space-around',
    marginBottom: 12,
  },
  statItem: {
    alignItems: 'center',
  },
  statValue: {
    fontSize: 22,
    fontWeight: '700',
    color: '#ffffff',
    marginBottom: 4,
  },
  statLabel: {
    fontSize: 11,
    color: '#6b7280',
    textTransform: 'uppercase',
  },
  rankChangeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  lastUpdated: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.05)',
  },
  lastUpdatedText: {
    fontSize: 12,
    color: '#6b7280',
  },
  infoCard: {
    marginBottom: 16,
  },
  infoText: {
    fontSize: 14,
    color: '#d1d5db',
    lineHeight: 22,
  },
  milestoneRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(255, 255, 255, 0.05)',
  },
  milestoneInfo: {
    flex: 1,
  },
  milestoneLabel: {
    fontSize: 14,
    color: '#ffffff',
    fontWeight: '500',
    marginBottom: 2,
  },
  milestoneDate: {
    fontSize: 12,
    color: '#6b7280',
  },
  spotifyFullButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    backgroundColor: '#1DB954',
    paddingVertical: 14,
    borderRadius: 12,
    marginTop: 8,
  },
  spotifyFullButtonText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '600',
  },
  errorContainer: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 20,
  },
  errorText: {
    color: '#9ca3af',
    fontSize: 16,
    marginTop: 12,
    textAlign: 'center',
  },
  goBackButton: {
    marginTop: 24,
    backgroundColor: '#60a5fa',
    paddingVertical: 12,
    paddingHorizontal: 32,
    borderRadius: 8,
  },
  goBackButtonText: {
    color: '#ffffff',
    fontSize: 16,
    fontWeight: '600',
  },
});
