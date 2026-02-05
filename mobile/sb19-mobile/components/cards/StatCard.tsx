import React from 'react';
import { View, Text, StyleSheet, Pressable } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { GlassCard } from '../ui/GlassCard';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  change?: number;
  changeLabel?: string;
  icon?: keyof typeof Ionicons.glyphMap;
  iconColor?: string;
  onPress?: () => void;
}

export function StatCard({
  title,
  value,
  subtitle,
  change,
  changeLabel,
  icon,
  iconColor = '#60a5fa',
  onPress,
}: StatCardProps) {
  const formattedValue = typeof value === 'number'
    ? value.toLocaleString()
    : value;

  const isPositiveChange = change !== undefined && change >= 0;

  return (
    <Pressable onPress={onPress} disabled={!onPress}>
      <GlassCard style={styles.card}>
        <View style={styles.header}>
          {icon && (
            <View style={[styles.iconContainer, { backgroundColor: `${iconColor}20` }]}>
              <Ionicons name={icon} size={20} color={iconColor} />
            </View>
          )}
          <Text style={styles.title}>{title}</Text>
        </View>

        <Text style={styles.value}>{formattedValue}</Text>

        {(subtitle || change !== undefined) && (
          <View style={styles.footer}>
            {change !== undefined && (
              <View style={styles.changeContainer}>
                <Ionicons
                  name={isPositiveChange ? 'trending-up' : 'trending-down'}
                  size={14}
                  color={isPositiveChange ? '#34d399' : '#ef4444'}
                />
                <Text style={[
                  styles.change,
                  { color: isPositiveChange ? '#34d399' : '#ef4444' }
                ]}>
                  {isPositiveChange ? '+' : ''}{change.toLocaleString()}
                </Text>
              </View>
            )}
            {subtitle && (
              <Text style={styles.subtitle}>{subtitle}</Text>
            )}
            {changeLabel && (
              <Text style={styles.changeLabel}>{changeLabel}</Text>
            )}
          </View>
        )}
      </GlassCard>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    minWidth: 160,
    marginRight: 12,
  },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 8,
  },
  iconContainer: {
    width: 32,
    height: 32,
    borderRadius: 8,
    justifyContent: 'center',
    alignItems: 'center',
    marginRight: 8,
  },
  title: {
    fontSize: 12,
    fontWeight: '500',
    color: '#9ca3af',
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  value: {
    fontSize: 24,
    fontWeight: '700',
    color: '#ffffff',
    marginBottom: 4,
  },
  footer: {
    flexDirection: 'row',
    alignItems: 'center',
    flexWrap: 'wrap',
    gap: 4,
  },
  changeContainer: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 2,
  },
  change: {
    fontSize: 12,
    fontWeight: '600',
  },
  subtitle: {
    fontSize: 11,
    color: '#9ca3af',
  },
  changeLabel: {
    fontSize: 11,
    color: '#6b7280',
  },
});
