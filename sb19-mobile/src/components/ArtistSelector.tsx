import React, { useState, useMemo } from 'react';
import { View, Text, StyleSheet, TouchableOpacity, FlatList } from 'react-native';
import SearchBar from './SearchBar';
import { ArtistSummary } from '../types/data';
import { colors } from '../theme/colors';
import { formatNumber } from '../utils/formatters';

interface ArtistSelectorProps {
  summaries: ArtistSummary[];
  selectedNames: string[];
  onSelect: (name: string) => void;
  maxSelection?: number;
}

export default function ArtistSelector({
  summaries,
  selectedNames,
  onSelect,
  maxSelection = 4,
}: ArtistSelectorProps) {
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    if (!query.trim()) return [];
    return summaries
      .filter(
        s =>
          s.name.toLowerCase().includes(query.toLowerCase()) &&
          !selectedNames.includes(s.name),
      )
      .slice(0, 8);
  }, [query, summaries, selectedNames]);

  return (
    <View style={styles.container}>
      <SearchBar
        value={query}
        onChangeText={setQuery}
        placeholder={
          selectedNames.length >= maxSelection
            ? `Max ${maxSelection} artists selected`
            : 'Search to add artist...'
        }
      />
      {filtered.length > 0 && (
        <View style={styles.dropdown}>
          {filtered.map(artist => (
            <TouchableOpacity
              key={artist.name}
              style={styles.option}
              onPress={() => {
                onSelect(artist.name);
                setQuery('');
              }}
              disabled={selectedNames.length >= maxSelection}
            >
              <Text style={styles.optionName}>{artist.name}</Text>
              <Text style={styles.optionListeners}>
                {formatNumber(artist.currentListeners)}
              </Text>
            </TouchableOpacity>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    zIndex: 10,
  },
  dropdown: {
    marginTop: 4,
    backgroundColor: colors.surface,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    overflow: 'hidden',
  },
  option: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  optionName: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: '500',
  },
  optionListeners: {
    color: colors.textMuted,
    fontSize: 13,
  },
});
