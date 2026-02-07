import React, { useMemo, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';
import { useDataStore } from '../store/useDataStore';
import { useFilterStore } from '../store/useFilterStore';
import { useFavoritesStore } from '../store/useFavoritesStore';
import { ArtistSummary, SortBy } from '../types/data';
import SearchBar from '../components/SearchBar';
import GenreTabs from '../components/GenreTabs';
import ArtistCard from '../components/ArtistCard';
import AnimatedListItem from '../components/AnimatedListItem';
import LoadingScreen from '../components/LoadingScreen';
import { colors } from '../theme/colors';
import { timeAgo, formatNumberFull, formatPercent } from '../utils/formatters';

const SORT_OPTIONS: { key: SortBy; label: string; icon: string }[] = [
  { key: 'listeners', label: 'Listeners', icon: 'people' },
  { key: 'growth', label: 'Growth', icon: 'trending-up' },
  { key: 'alphabetical', label: 'A-Z', icon: 'text' },
];

export default function RankingsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<any>>();
  const { loading, lastUpdated, fetchData, getArtistSummaries } =
    useDataStore();
  const {
    selectedGenre,
    searchQuery,
    sortBy,
    setGenre,
    setSearchQuery,
    setSortBy,
  } = useFilterStore();
  const favorites = useFavoritesStore(s => s.favorites);

  const allSummaries = useMemo(
    () => getArtistSummaries('All'),
    [getArtistSummaries],
  );

  const sb19 = useMemo(
    () => allSummaries.find(s => s.name === 'SB19'),
    [allSummaries],
  );

  const summaries = useMemo(
    () => getArtistSummaries(selectedGenre),
    [getArtistSummaries, selectedGenre],
  );

  const filtered = useMemo(() => {
    let result = summaries;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(s => s.name.toLowerCase().includes(q));
    }

    if (sortBy === 'growth') {
      result = [...result].sort((a, b) => b.growthPercent - a.growthPercent);
    } else if (sortBy === 'alphabetical') {
      result = [...result].sort((a, b) =>
        a.name.localeCompare(b.name),
      );
    }

    return result;
  }, [summaries, searchQuery, sortBy]);

  // Favorites that exist in current data
  const favoriteSummaries = useMemo(() => {
    if (favorites.length === 0 || searchQuery.trim()) return [];
    return favorites
      .map(name => allSummaries.find(s => s.name === name))
      .filter(Boolean) as ArtistSummary[];
  }, [favorites, allSummaries, searchQuery]);

  const handleRefresh = useCallback(() => {
    fetchData(true);
  }, [fetchData]);

  const renderItem = useCallback(
    ({ item, index }: { item: ArtistSummary; index: number }) => (
      <AnimatedListItem index={index}>
        <ArtistCard
          artist={item}
          onPress={() =>
            navigation.navigate('ArtistDetail', { artistName: item.name })
          }
        />
      </AnimatedListItem>
    ),
    [navigation],
  );

  const keyExtractor = useCallback(
    (item: ArtistSummary) => item.name,
    [],
  );

  if (loading && summaries.length === 0) {
    return <LoadingScreen />;
  }

  return (
    <View style={styles.container}>
      <FlatList
        data={filtered}
        renderItem={renderItem}
        keyExtractor={keyExtractor}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl
            refreshing={loading}
            onRefresh={handleRefresh}
            tintColor={colors.primary}
            colors={[colors.primary]}
            progressBackgroundColor={colors.surface}
          />
        }
        ListHeaderComponent={
          <View>
            {/* Search */}
            <SearchBar value={searchQuery} onChangeText={setSearchQuery} />

            {/* Featured SB19 */}
            {sb19 && !searchQuery.trim() && (
              <TouchableOpacity
                style={styles.featured}
                activeOpacity={0.7}
                onPress={() => navigation.navigate('ArtistDetail', { artistName: 'SB19' })}
              >
                <View style={styles.featuredBadge}>
                  <Ionicons name="star" size={10} color="#fbbf24" />
                  <Text style={styles.featuredBadgeText}>FEATURED</Text>
                </View>
                <Text style={styles.featuredName}>SB19</Text>
                <Text style={styles.featuredListeners}>
                  {formatNumberFull(sb19.currentListeners)} monthly listeners
                </Text>
                <View style={styles.featuredStats}>
                  <View style={styles.featuredStat}>
                    <Text style={styles.featuredStatLabel}>Rank</Text>
                    <Text style={styles.featuredStatValue}>#{sb19.rank}</Text>
                  </View>
                  <View style={styles.featuredStatDivider} />
                  <View style={styles.featuredStat}>
                    <Text style={styles.featuredStatLabel}>7D</Text>
                    <Text style={[styles.featuredStatValue, { color: sb19.growthPercent7d >= 0 ? colors.success : colors.error }]}>
                      {formatPercent(sb19.growthPercent7d)}
                    </Text>
                  </View>
                  <View style={styles.featuredStatDivider} />
                  <View style={styles.featuredStat}>
                    <Text style={styles.featuredStatLabel}>30D</Text>
                    <Text style={[styles.featuredStatValue, { color: sb19.growthPercent30d >= 0 ? colors.success : colors.error }]}>
                      {formatPercent(sb19.growthPercent30d)}
                    </Text>
                  </View>
                  <View style={styles.featuredStatDivider} />
                  <View style={styles.featuredStat}>
                    <Text style={styles.featuredStatLabel}>Followers</Text>
                    <Text style={styles.featuredStatValue}>
                      {formatNumberFull(sb19.followers)}
                    </Text>
                  </View>
                </View>
              </TouchableOpacity>
            )}

            {/* Favorites section */}
            {favoriteSummaries.length > 0 && (
              <View style={styles.favSection}>
                <View style={styles.favHeader}>
                  <Ionicons name="heart" size={14} color="#f43f5e" />
                  <Text style={styles.favTitle}>Favorites</Text>
                </View>
                {favoriteSummaries.map(artist => (
                  <ArtistCard
                    key={`fav-${artist.name}`}
                    artist={artist}
                    onPress={() =>
                      navigation.navigate('ArtistDetail', { artistName: artist.name })
                    }
                  />
                ))}
              </View>
            )}

            {/* Genre Tabs */}
            <GenreTabs selected={selectedGenre} onSelect={setGenre} />

            {/* Sort + summary row */}
            <View style={styles.summaryRow}>
              <Text style={styles.summaryText}>
                {filtered.length} artists
                {lastUpdated ? ` | Updated ${timeAgo(lastUpdated)}` : ''}
              </Text>
              <View style={styles.sortRow}>
                {SORT_OPTIONS.map(opt => (
                  <TouchableOpacity
                    key={opt.key}
                    style={[
                      styles.sortBtn,
                      sortBy === opt.key && styles.sortBtnActive,
                    ]}
                    onPress={() => setSortBy(opt.key)}
                  >
                    <Ionicons
                      name={opt.icon as any}
                      size={12}
                      color={
                        sortBy === opt.key
                          ? '#fff'
                          : colors.textMuted
                      }
                    />
                    <Text
                      style={[
                        styles.sortBtnText,
                        sortBy === opt.key && styles.sortBtnTextActive,
                      ]}
                    >
                      {opt.label}
                    </Text>
                  </TouchableOpacity>
                ))}
              </View>
            </View>
          </View>
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="search" size={40} color={colors.textMuted} />
            <Text style={styles.emptyText}>No artists found</Text>
          </View>
        }
        windowSize={15}
        maxToRenderPerBatch={20}
        removeClippedSubviews
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  list: {
    padding: 16,
    paddingBottom: 32,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  summaryText: {
    color: colors.textMuted,
    fontSize: 12,
  },
  sortRow: {
    flexDirection: 'row',
    gap: 4,
  },
  sortBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 8,
    backgroundColor: colors.surface,
  },
  sortBtnActive: {
    backgroundColor: colors.primary,
  },
  sortBtnText: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: '500',
  },
  sortBtnTextActive: {
    color: '#fff',
  },
  featured: {
    backgroundColor: 'rgba(59, 130, 246, 0.1)',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: 'rgba(59, 130, 246, 0.25)',
    padding: 16,
    marginTop: 12,
    marginBottom: 4,
  },
  featuredBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    alignSelf: 'flex-start',
    backgroundColor: 'rgba(251, 191, 36, 0.15)',
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: 8,
    marginBottom: 8,
  },
  featuredBadgeText: {
    color: '#fbbf24',
    fontSize: 10,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  featuredName: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: '700',
    marginBottom: 4,
  },
  featuredListeners: {
    color: colors.textSecondary,
    fontSize: 14,
    marginBottom: 12,
  },
  featuredStats: {
    flexDirection: 'row',
    alignItems: 'center',
  },
  featuredStat: {
    flex: 1,
    alignItems: 'center',
  },
  featuredStatLabel: {
    color: colors.textMuted,
    fontSize: 11,
    marginBottom: 2,
  },
  featuredStatValue: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: '700',
  },
  featuredStatDivider: {
    width: 1,
    height: 28,
    backgroundColor: colors.border,
  },
  favSection: {
    marginTop: 12,
    marginBottom: 4,
  },
  favHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    marginBottom: 10,
  },
  favTitle: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: '600',
  },
  empty: {
    alignItems: 'center',
    paddingTop: 60,
    gap: 12,
  },
  emptyText: {
    color: colors.textMuted,
    fontSize: 15,
  },
});
