import React from 'react';
import { FlatList, StyleSheet } from 'react-native';
import { ProcessedTrack } from '../../types';
import { TrackCard } from '../cards/TrackCard';

interface TracksTableProps {
  tracks: ProcessedTrack[];
  onTrackPress?: (track: ProcessedTrack) => void;
}

export function TracksTable({ tracks, onTrackPress }: TracksTableProps) {
  return (
    <FlatList
      data={tracks}
      keyExtractor={(item) => item.song_title}
      renderItem={({ item }) => (
        <TrackCard
          track={item}
          onPress={() => onTrackPress?.(item)}
        />
      )}
      style={styles.list}
      contentContainerStyle={styles.content}
      showsVerticalScrollIndicator={false}
    />
  );
}

const styles = StyleSheet.create({
  list: {
    flex: 1,
  },
  content: {
    paddingVertical: 8,
  },
});
