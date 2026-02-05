import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { ProcessedTrack } from '../../types';
import { formatNumber } from '../../hooks/useFormatters';

interface TrackCardProps {
  track: ProcessedTrack;
  onPress?: () => void;
  showRank?: boolean;
  showChange?: boolean;
}

export function TrackCard({
  track,
  onPress,
  showRank = true,
  showChange = true,
}: TrackCardProps) {
  const isPositiveChange = track.change >= 0;
  const changeColor = track.change === 0 ? '#6b7280' : isPositiveChange ? '#34d399' : '#ef4444';

  return (
    <Pressable
      onPress={onPress}
      style={({ pressed }) => [
        styles.container,
        pressed && styles.pressed,
      ]}
    >
      {showRank && (
        <View style={styles.rankContainer}>
          <Text style={styles.rank}>#{track.rank}</Text>
          {track.rankChange !== null && track.rankChange !== 0 && (
            <View style={styles.rankChangeContainer}>
              <Ionicons
                name={track.rankChange > 0 ? 'caret-up' : 'caret-down'}
                size={10}
                color={track.rankChange > 0 ? '#34d399' : '#ef4444'}
              />
              <Text style={[
                styles.rankChange,
                { color: track.rankChange > 0 ? '#34d399' : '#ef4444' }
              ]}>
                {Math.abs(track.rankChange)}
              </Text>
            </View>
          )}
        </View>
      )}

      <View style={styles.info}>
        <Text style={styles.title} numberOfLines={1}>{track.song_title}</Text>
        <View style={styles.metaRow}>
          <Text style={styles.album} numberOfLines={1}>{track.album || 'Single'}</Text>
          {track.year > 0 && <Text style={styles.year}>{track.year}</Text>}
        </View>
      </View>

      <View style={styles.stats}>
        <Text style={styles.streams}>{formatNumber(track.total_streams)}</Text>
        {showChange && (
          <View style={styles.changeContainer}>
            <Ionicons
              name={isPositiveChange ? 'trending-up' : 'trending-down'}
              size={12}
              color={changeColor}
            />
            <Text style={[styles.change, { color: changeColor }]}>
              {track.change === 0 ? '-' : `${isPositiveChange ? '+' : ''}${formatNumber(track.change)}`}
            </Text>
          </View>
        )}
      </View>

      <Ionicons name="chevron-forward" size={20} color="#6b7280" />
    </Pressable>
  );
}

const styles = StyleSheet.create({
  container: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderRadius: 12,
    padding: 12,
    marginBottom: 8,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
  },
  pressed: {
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
  },
  rankContainer: {
    width: 44,
    alignItems: 'center',
    marginRight: 12,
  },
  rank: {
    fontSize: 18,
    fontWeight: '700',
    color: '#60a5fa',
  },
  rankChangeContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 2,
  },
  rankChange: {
    fontSize: 10,
    fontWeight: '600',
  },
  info: {
    flex: 1,
    marginRight: 12,
  },
  title: {
    fontSize: 15,
    fontWeight: '600',
    color: '#ffffff',
    marginBottom: 4,
  },
  metaRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
  },
  album: {
    fontSize: 12,
    color: '#9ca3af',
    flex: 1,
  },
  year: {
    fontSize: 11,
    color: '#6b7280',
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
  },
  stats: {
    alignItems: 'flex-end',
    marginRight: 8,
  },
  streams: {
    fontSize: 14,
    fontWeight: '600',
    color: '#ffffff',
    marginBottom: 2,
  },
  changeContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  change: {
    fontSize: 11,
    fontWeight: '500',
  },
});
