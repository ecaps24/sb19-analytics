import React, { memo } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { ArtistSummary } from '../types/data';
import { colors, genreColors } from '../theme/colors';
import { formatNumberFull } from '../utils/formatters';
import { useFavoritesStore } from '../store/useFavoritesStore';

interface ArtistCardProps {
  artist: ArtistSummary;
  onPress: () => void;
  showGrowthHighlight?: 'gain' | 'decline' | null;
}

function ArtistCard({ artist, onPress, showGrowthHighlight }: ArtistCardProps) {
  const isFavorite = useFavoritesStore(s => s.favorites.includes(artist.name));
  const toggleFavorite = useFavoritesStore(s => s.toggleFavorite);

  const growth = artist.growthPercent;
  const isPositive = growth >= 0;
  const growthColor = isPositive ? colors.success : colors.error;
  const rankChangeIcon = artist.rankChange > 0
    ? 'caret-up'
    : artist.rankChange < 0
      ? 'caret-down'
      : 'remove';
  const rankChangeColor = artist.rankChange > 0
    ? colors.success
    : artist.rankChange < 0
      ? colors.error
      : colors.textMuted;

  const highlightBorder = showGrowthHighlight === 'gain'
    ? colors.success
    : showGrowthHighlight === 'decline'
      ? colors.error
      : undefined;

  return (
    <TouchableOpacity
      style={[
        styles.card,
        highlightBorder ? { borderLeftWidth: 3, borderLeftColor: highlightBorder } : null,
      ]}
      onPress={onPress}
      activeOpacity={0.7}
    >
      {/* Rank badge */}
      <View style={styles.rankContainer}>
        <Text style={styles.rankNumber}>#{artist.rank}</Text>
        <View style={styles.rankChange}>
          <Ionicons name={rankChangeIcon} size={10} color={rankChangeColor} />
          {artist.rankChange !== 0 && (
            <Text style={[styles.rankChangeText, { color: rankChangeColor }]}>
              {Math.abs(artist.rankChange)}
            </Text>
          )}
        </View>
      </View>

      {/* Artist info */}
      <View style={styles.info}>
        <View style={styles.nameRow}>
          <Text style={styles.name} numberOfLines={1}>{artist.name}</Text>
          <View style={[styles.genreBadge, { backgroundColor: (genreColors[artist.genre] || colors.primary) + '30' }]}>
            <Text style={[styles.genreText, { color: genreColors[artist.genre] || colors.primary }]}>
              {artist.genre}
            </Text>
          </View>
        </View>
        <Text style={styles.listeners}>
          {formatNumberFull(artist.currentListeners)} listeners
        </Text>
      </View>

      {/* Growth */}
      <View style={styles.growthContainer}>
        <Ionicons
          name={isPositive ? 'trending-up' : 'trending-down'}
          size={14}
          color={growthColor}
        />
        <Text style={[styles.growthText, { color: growthColor }]}>
          {isPositive ? '+' : ''}{growth.toFixed(1)}%
        </Text>
      </View>

      {/* Favorite heart */}
      <Pressable
        onPress={(e) => {
          e.stopPropagation?.();
          toggleFavorite(artist.name);
        }}
        hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
        style={styles.heartBtn}
      >
        <Ionicons
          name={isFavorite ? 'heart' : 'heart-outline'}
          size={18}
          color={isFavorite ? '#f43f5e' : colors.textMuted}
        />
      </Pressable>
    </TouchableOpacity>
  );
}

export default memo(ArtistCard);

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 14,
    marginBottom: 8,
  },
  rankContainer: {
    alignItems: 'center',
    width: 36,
    marginRight: 12,
  },
  rankNumber: {
    color: colors.textPrimary,
    fontSize: 15,
    fontWeight: '700',
  },
  rankChange: {
    flexDirection: 'row',
    alignItems: 'center',
    marginTop: 2,
  },
  rankChangeText: {
    fontSize: 10,
    fontWeight: '600',
    marginLeft: 1,
  },
  info: {
    flex: 1,
  },
  nameRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 3,
  },
  name: {
    color: colors.textPrimary,
    fontSize: 15,
    fontWeight: '600',
    flexShrink: 1,
  },
  genreBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 10,
  },
  genreText: {
    fontSize: 10,
    fontWeight: '600',
  },
  listeners: {
    color: colors.textSecondary,
    fontSize: 13,
  },
  growthContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginLeft: 8,
  },
  growthText: {
    fontSize: 13,
    fontWeight: '600',
  },
  heartBtn: {
    marginLeft: 10,
    padding: 2,
  },
});
