import React, { useState, useMemo } from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  Pressable,
  TextInput,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { router } from 'expo-router';
import { useAppStore } from '../../services/store';
import { TrackCard } from '../../components/cards/TrackCard';
import { GlassCard } from '../../components/ui/GlassCard';
import { SortColumn, SortDirection } from '../../types';

const SORT_OPTIONS: { value: SortColumn; label: string }[] = [
  { value: 'rank', label: 'Rank' },
  { value: 'change', label: 'Daily +/-' },
  { value: 'streams', label: 'Streams' },
  { value: 'song', label: 'Title' },
  { value: 'album', label: 'Album' },
];

export default function TracksScreen() {
  const getFilteredTracks = useAppStore((state) => state.getFilteredTracks);
  const sortColumn = useAppStore((state) => state.sortColumn);
  const sortDirection = useAppStore((state) => state.sortDirection);
  const setSort = useAppStore((state) => state.setSort);
  const filters = useAppStore((state) => state.filters);
  const setFilters = useAppStore((state) => state.setFilters);
  const getAlbumStats = useAppStore((state) => state.getAlbumStats);
  const { label: changeLabel } = useAppStore((state) => state.getPeriodChange());

  const [searchQuery, setSearchQuery] = useState('');
  const [showFilters, setShowFilters] = useState(false);

  const tracks = getFilteredTracks();
  const albumStats = getAlbumStats();

  const filteredTracks = useMemo(() => {
    if (!searchQuery.trim()) return tracks;
    const query = searchQuery.toLowerCase();
    return tracks.filter(
      (t) =>
        t.song_title.toLowerCase().includes(query) ||
        t.album.toLowerCase().includes(query)
    );
  }, [tracks, searchQuery]);

  const handleSort = (column: SortColumn) => {
    if (sortColumn === column) {
      setSort(column, sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSort(column, 'desc');
    }
  };

  const clearFilters = () => {
    setFilters({ album: null, track: null, member: null });
    setSearchQuery('');
  };

  const hasActiveFilters = filters.album || filters.track || searchQuery;

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>All Tracks</Text>
        <Text style={styles.subtitle}>
          {filteredTracks.length} tracks • {changeLabel}
        </Text>
      </View>

      {/* Search Bar */}
      <View style={styles.searchContainer}>
        <View style={styles.searchBar}>
          <Ionicons name="search" size={18} color="#6b7280" />
          <TextInput
            style={styles.searchInput}
            placeholder="Search tracks..."
            placeholderTextColor="#6b7280"
            value={searchQuery}
            onChangeText={setSearchQuery}
          />
          {searchQuery.length > 0 && (
            <Pressable onPress={() => setSearchQuery('')}>
              <Ionicons name="close-circle" size={18} color="#6b7280" />
            </Pressable>
          )}
        </View>
        <Pressable
          style={[styles.filterButton, showFilters && styles.filterButtonActive]}
          onPress={() => setShowFilters(!showFilters)}
        >
          <Ionicons
            name="options"
            size={20}
            color={showFilters ? '#60a5fa' : '#9ca3af'}
          />
        </Pressable>
      </View>

      {/* Sort & Filter Options */}
      {showFilters && (
        <GlassCard style={styles.filtersCard}>
          <Text style={styles.filterLabel}>Sort by</Text>
          <View style={styles.sortOptions}>
            {SORT_OPTIONS.map((option) => (
              <Pressable
                key={option.value}
                style={[
                  styles.sortChip,
                  sortColumn === option.value && styles.sortChipActive,
                ]}
                onPress={() => handleSort(option.value)}
              >
                <Text
                  style={[
                    styles.sortChipText,
                    sortColumn === option.value && styles.sortChipTextActive,
                  ]}
                >
                  {option.label}
                </Text>
                {sortColumn === option.value && (
                  <Ionicons
                    name={sortDirection === 'asc' ? 'arrow-up' : 'arrow-down'}
                    size={12}
                    color="#60a5fa"
                  />
                )}
              </Pressable>
            ))}
          </View>

          <Text style={styles.filterLabel}>Filter by Album</Text>
          <View style={styles.albumFilters}>
            <Pressable
              style={[
                styles.albumChip,
                !filters.album && styles.albumChipActive,
              ]}
              onPress={() => setFilters({ album: null })}
            >
              <Text
                style={[
                  styles.albumChipText,
                  !filters.album && styles.albumChipTextActive,
                ]}
              >
                All
              </Text>
            </Pressable>
            {albumStats.map((album) => (
              <Pressable
                key={album.name}
                style={[
                  styles.albumChip,
                  filters.album === album.name && styles.albumChipActive,
                ]}
                onPress={() => setFilters({ album: album.name })}
              >
                <Text
                  style={[
                    styles.albumChipText,
                    filters.album === album.name && styles.albumChipTextActive,
                  ]}
                  numberOfLines={1}
                >
                  {album.name.length > 15
                    ? album.name.substring(0, 15) + '...'
                    : album.name}
                </Text>
              </Pressable>
            ))}
          </View>

          {hasActiveFilters && (
            <Pressable style={styles.clearButton} onPress={clearFilters}>
              <Text style={styles.clearButtonText}>Clear All Filters</Text>
            </Pressable>
          )}
        </GlassCard>
      )}

      {/* Active Filter Badge */}
      {filters.album && !showFilters && (
        <View style={styles.activeFilterBadge}>
          <Text style={styles.activeFilterText}>
            Filtered: {filters.album}
          </Text>
          <Pressable onPress={() => setFilters({ album: null })}>
            <Ionicons name="close" size={16} color="#60a5fa" />
          </Pressable>
        </View>
      )}

      {/* Tracks List */}
      <FlatList
        data={filteredTracks}
        keyExtractor={(item) => item.song_title}
        renderItem={({ item }) => (
          <TrackCard
            track={item}
            onPress={() =>
              router.push(`/track/${encodeURIComponent(item.song_title)}`)
            }
          />
        )}
        contentContainerStyle={styles.listContent}
        showsVerticalScrollIndicator={false}
        ListEmptyComponent={
          <View style={styles.emptyContainer}>
            <Ionicons name="musical-notes-outline" size={48} color="#6b7280" />
            <Text style={styles.emptyText}>No tracks found</Text>
            {hasActiveFilters && (
              <Pressable style={styles.clearEmptyButton} onPress={clearFilters}>
                <Text style={styles.clearEmptyButtonText}>Clear Filters</Text>
              </Pressable>
            )}
          </View>
        }
      />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0c29',
  },
  header: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 12,
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
  searchContainer: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    marginBottom: 12,
    gap: 8,
  },
  searchBar: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderRadius: 12,
    paddingHorizontal: 12,
    height: 44,
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
    gap: 8,
  },
  searchInput: {
    flex: 1,
    color: '#ffffff',
    fontSize: 15,
  },
  filterButton: {
    width: 44,
    height: 44,
    borderRadius: 12,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    justifyContent: 'center',
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.08)',
  },
  filterButtonActive: {
    backgroundColor: 'rgba(96, 165, 250, 0.15)',
    borderColor: '#60a5fa',
  },
  filtersCard: {
    marginHorizontal: 16,
    marginBottom: 12,
  },
  filterLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: '#9ca3af',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 8,
  },
  sortOptions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 16,
  },
  sortChip: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 16,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
    gap: 4,
  },
  sortChipActive: {
    backgroundColor: 'rgba(96, 165, 250, 0.15)',
    borderColor: '#60a5fa',
  },
  sortChipText: {
    fontSize: 12,
    color: '#9ca3af',
    fontWeight: '500',
  },
  sortChipTextActive: {
    color: '#60a5fa',
  },
  albumFilters: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 12,
  },
  albumChip: {
    paddingVertical: 6,
    paddingHorizontal: 12,
    borderRadius: 16,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderWidth: 1,
    borderColor: 'rgba(255, 255, 255, 0.1)',
  },
  albumChipActive: {
    backgroundColor: 'rgba(96, 165, 250, 0.15)',
    borderColor: '#60a5fa',
  },
  albumChipText: {
    fontSize: 12,
    color: '#9ca3af',
    fontWeight: '500',
  },
  albumChipTextActive: {
    color: '#60a5fa',
  },
  clearButton: {
    alignSelf: 'center',
    paddingVertical: 8,
    paddingHorizontal: 16,
  },
  clearButtonText: {
    color: '#ef4444',
    fontSize: 13,
    fontWeight: '500',
  },
  activeFilterBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    marginHorizontal: 16,
    marginBottom: 12,
    paddingVertical: 8,
    paddingHorizontal: 12,
    backgroundColor: 'rgba(96, 165, 250, 0.1)',
    borderRadius: 8,
    gap: 8,
  },
  activeFilterText: {
    flex: 1,
    color: '#60a5fa',
    fontSize: 13,
    fontWeight: '500',
  },
  listContent: {
    paddingHorizontal: 16,
    paddingBottom: 24,
  },
  emptyContainer: {
    alignItems: 'center',
    paddingTop: 60,
  },
  emptyText: {
    color: '#6b7280',
    fontSize: 16,
    marginTop: 12,
  },
  clearEmptyButton: {
    marginTop: 16,
    paddingVertical: 10,
    paddingHorizontal: 20,
    backgroundColor: '#60a5fa',
    borderRadius: 8,
  },
  clearEmptyButtonText: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '600',
  },
});
