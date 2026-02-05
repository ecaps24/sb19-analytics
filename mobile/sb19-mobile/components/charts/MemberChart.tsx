import React from 'react';
import { View, Text, StyleSheet, Dimensions, Pressable } from 'react-native';
import { BarChart } from 'react-native-gifted-charts';
import { useAppStore } from '../../services/store';
import { formatNumber } from '../../hooks/useFormatters';
import { GlassCard } from '../ui/GlassCard';
import { MEMBERS } from '../../constants';

const { width } = Dimensions.get('window');

export function MemberChart() {
  const getMemberStats = useAppStore((state) => state.getMemberStats);
  const memberStats = getMemberStats();

  const barData = memberStats.map((member) => ({
    value: member.totalStreams / 1_000_000,
    label: member.name,
    frontColor: member.color,
    topLabelComponent: () => (
      <Text style={styles.barLabel}>
        {formatNumber(member.totalStreams)}
      </Text>
    ),
  }));

  const totalStreams = memberStats.reduce((sum, m) => sum + m.totalStreams, 0);

  return (
    <GlassCard style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Member Solo Streams</Text>
        <Text style={styles.subtitle}>
          Total: {formatNumber(totalStreams)}
        </Text>
      </View>

      <View style={styles.chartContainer}>
        <BarChart
          data={barData}
          barWidth={40}
          spacing={20}
          roundedTop
          roundedBottom
          hideRules
          xAxisThickness={1}
          yAxisThickness={0}
          xAxisColor="rgba(255, 255, 255, 0.1)"
          yAxisColor="rgba(255, 255, 255, 0.1)"
          yAxisTextStyle={styles.axisText}
          xAxisLabelTextStyle={styles.xAxisLabel}
          noOfSections={4}
          maxValue={Math.max(...barData.map(d => d.value)) * 1.2}
          width={width - 80}
          height={180}
          isAnimated
          animationDuration={500}
          barBorderRadius={4}
          yAxisLabelSuffix="M"
        />
      </View>

      <View style={styles.memberStats}>
        {memberStats.map((member) => (
          <Pressable key={member.name} style={styles.memberRow}>
            <View style={styles.memberInfo}>
              <View
                style={[styles.memberDot, { backgroundColor: member.borderColor }]}
              />
              <Text style={styles.memberName}>{member.displayName}</Text>
            </View>
            <View style={styles.memberNumbers}>
              <Text style={styles.memberStreams}>
                {formatNumber(member.totalStreams)}
              </Text>
              {(member.monthlyListeners ?? 0) > 0 && (
                <Text style={styles.memberListeners}>
                  {formatNumber(member.monthlyListeners ?? 0)} listeners
                </Text>
              )}
            </View>
            <View style={styles.memberChange}>
              {member.change !== 0 && (
                <Text style={[
                  styles.changeText,
                  { color: member.change >= 0 ? '#34d399' : '#ef4444' }
                ]}>
                  {member.change >= 0 ? '+' : ''}{formatNumber(member.change)}
                </Text>
              )}
            </View>
          </Pressable>
        ))}
      </View>
    </GlassCard>
  );
}

const styles = StyleSheet.create({
  container: {
    marginBottom: 16,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 16,
  },
  title: {
    fontSize: 18,
    fontWeight: '700',
    color: '#ffffff',
  },
  subtitle: {
    fontSize: 12,
    color: '#9ca3af',
  },
  chartContainer: {
    alignItems: 'center',
    marginBottom: 16,
  },
  axisText: {
    color: '#9ca3af',
    fontSize: 10,
  },
  xAxisLabel: {
    color: '#9ca3af',
    fontSize: 11,
    fontWeight: '500',
  },
  barLabel: {
    color: '#ffffff',
    fontSize: 10,
    fontWeight: '600',
    marginBottom: 4,
  },
  memberStats: {
    gap: 8,
  },
  memberRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderRadius: 8,
    padding: 12,
  },
  memberInfo: {
    flexDirection: 'row',
    alignItems: 'center',
    flex: 1,
    gap: 8,
  },
  memberDot: {
    width: 12,
    height: 12,
    borderRadius: 6,
  },
  memberName: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '500',
  },
  memberNumbers: {
    alignItems: 'flex-end',
    marginRight: 12,
  },
  memberStreams: {
    color: '#ffffff',
    fontSize: 14,
    fontWeight: '600',
  },
  memberListeners: {
    color: '#6b7280',
    fontSize: 11,
  },
  memberChange: {
    width: 60,
    alignItems: 'flex-end',
  },
  changeText: {
    fontSize: 12,
    fontWeight: '500',
  },
});
