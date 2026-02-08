import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { colors } from '../theme/colors';

interface StatCardProps {
  label: string;
  value: string;
  color?: string;
  accentColor?: string;
}

export default function StatCard({ label, value, color, accentColor }: StatCardProps) {
  return (
    <View style={styles.card}>
      {accentColor && (
        <View style={[styles.accentBar, { backgroundColor: accentColor }]} />
      )}
      <Text style={styles.label}>{label}</Text>
      <Text style={[styles.value, color ? { color } : null]}>{value}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.surface,
    borderRadius: 12,
    padding: 14,
    flex: 1,
    minWidth: '30%',
    overflow: 'hidden',
  },
  accentBar: {
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    height: 3,
    borderTopLeftRadius: 12,
    borderTopRightRadius: 12,
  },
  label: {
    color: colors.textMuted,
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 4,
  },
  value: {
    color: colors.textPrimary,
    fontSize: 18,
    fontWeight: '700',
  },
});
