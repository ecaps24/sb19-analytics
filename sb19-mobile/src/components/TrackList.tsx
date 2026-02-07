import React from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Linking } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { TrackSummary } from '../types/data';
import { colors } from '../theme/colors';
import { formatNumber, formatNumberFull } from '../utils/formatters';

interface TrackListProps {
  tracks: TrackSummary[];
}

export default function TrackList({ tracks }: TrackListProps) {
  if (tracks.length === 0) return null;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Tracks</Text>
      {tracks.map((track, index) => {
        const isPositive = track.change >= 0;
        const changeColor = isPositive ? colors.success : colors.error;
        return (
          <TouchableOpacity
            key={track.title + index}
            style={styles.track}
            onPress={() => {
              if (track.spotifyUrl) Linking.openURL(track.spotifyUrl);
            }}
            activeOpacity={track.spotifyUrl ? 0.7 : 1}
          >
            <View style={styles.trackInfo}>
              <Text style={styles.trackTitle} numberOfLines={1}>
                {track.title}
              </Text>
              <Text style={styles.trackMeta}>
                {track.album ? `${track.album}` : ''}
                {track.year ? ` (${track.year})` : ''}
              </Text>
            </View>
            <View style={styles.trackStats}>
              <Text style={styles.trackStreams}>
                {formatNumber(track.currentStreams)}
              </Text>
              {track.change !== 0 && (
                <View style={styles.changeRow}>
                  <Ionicons
                    name={isPositive ? 'trending-up' : 'trending-down'}
                    size={10}
                    color={changeColor}
                  />
                  <Text style={[styles.changeText, { color: changeColor }]}>
                    {isPositive ? '+' : ''}{formatNumber(Math.abs(track.change))}
                  </Text>
                </View>
              )}
            </View>
          </TouchableOpacity>
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
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 12,
  },
  track: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.surface,
    borderRadius: 10,
    padding: 12,
    marginBottom: 6,
  },
  trackInfo: {
    flex: 1,
  },
  trackTitle: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: '500',
  },
  trackMeta: {
    color: colors.textMuted,
    fontSize: 11,
    marginTop: 2,
  },
  trackStats: {
    alignItems: 'flex-end',
    marginLeft: 8,
  },
  trackStreams: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: '600',
  },
  changeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 3,
    marginTop: 2,
  },
  changeText: {
    fontSize: 11,
    fontWeight: '500',
  },
});
