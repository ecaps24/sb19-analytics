import React from 'react';
import { View, StyleSheet, ViewStyle } from 'react-native';
import { colors } from '../theme/colors';

interface GlassCardProps {
  children: React.ReactNode;
  style?: ViewStyle;
  solid?: boolean;
}

export default function GlassCard({ children, style, solid }: GlassCardProps) {
  return (
    <View style={[styles.card, solid && styles.solidCard, style]}>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.card,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: 16,
  },
  solidCard: {
    backgroundColor: colors.surface,
    borderColor: 'transparent',
  },
});
