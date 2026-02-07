import React from 'react';
import { ScrollView, TouchableOpacity, Text, StyleSheet } from 'react-native';
import { Genre } from '../types/data';
import { colors, genreColors } from '../theme/colors';

const GENRES: Genre[] = [
  'All',
  'P-Pop',
  'SB19 Solo',
  'OPM Pop',
  'OPM Ballad',
  'OPM Rock',
  'OPM Indie',
  'OPM Classic',
  'OPM Hip-Hop',
];

interface GenreTabsProps {
  selected: Genre;
  onSelect: (genre: Genre) => void;
}

export default function GenreTabs({ selected, onSelect }: GenreTabsProps) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      contentContainerStyle={styles.container}
    >
      {GENRES.map(genre => {
        const isActive = genre === selected;
        const color = genreColors[genre] || colors.primary;
        return (
          <TouchableOpacity
            key={genre}
            style={[
              styles.tab,
              isActive && { backgroundColor: color, borderColor: color },
            ]}
            onPress={() => onSelect(genre)}
            activeOpacity={0.7}
          >
            <Text
              style={[
                styles.tabText,
                isActive && styles.tabTextActive,
              ]}
            >
              {genre}
            </Text>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    paddingHorizontal: 4,
    paddingVertical: 8,
    gap: 8,
  },
  tab: {
    paddingHorizontal: 16,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  tabText: {
    color: colors.textSecondary,
    fontSize: 13,
    fontWeight: '500',
  },
  tabTextActive: {
    color: '#fff',
    fontWeight: '600',
  },
});
