import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { CityEntry } from '../types/data';
import { colors } from '../theme/colors';
import { formatNumberFull } from '../utils/formatters';

interface CityListProps {
  cities: CityEntry[];
}

export default function CityList({ cities }: CityListProps) {
  if (!cities || cities.length === 0) return null;

  const maxListeners = cities[0]?.listeners || 1;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Top Listener Cities</Text>
      {cities.map((city, index) => {
        const barWidth = (city.listeners / maxListeners) * 100;
        return (
          <View key={city.name} style={styles.row}>
            <Text style={styles.rank}>{index + 1}.</Text>
            <View style={styles.barContainer}>
              <View style={styles.labelRow}>
                <Text style={styles.cityName}>{city.name}</Text>
                <Text style={styles.cityListeners}>
                  {formatNumberFull(city.listeners)}
                </Text>
              </View>
              <View style={styles.barBg}>
                <View
                  style={[
                    styles.barFill,
                    { width: `${barWidth}%` },
                  ]}
                />
              </View>
            </View>
          </View>
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
  row: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    marginBottom: 10,
  },
  rank: {
    color: colors.textMuted,
    fontSize: 13,
    fontWeight: '600',
    width: 22,
    marginTop: 2,
  },
  barContainer: {
    flex: 1,
  },
  labelRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 4,
  },
  cityName: {
    color: colors.textPrimary,
    fontSize: 13,
    fontWeight: '500',
  },
  cityListeners: {
    color: colors.textSecondary,
    fontSize: 13,
  },
  barBg: {
    height: 10,
    backgroundColor: colors.surfaceLight,
    borderRadius: 5,
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    backgroundColor: colors.primary,
    borderRadius: 5,
  },
});
