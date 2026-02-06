import React from 'react';
import { View, Text, StyleSheet, Dimensions, Pressable, Platform } from 'react-native';
import { useAppStore } from '../../services/store';
import { formatNumber } from '../../hooks/useFormatters';
import { GlassCard } from '../ui/GlassCard';

const { width } = Dimensions.get('window');

// Conditionally import BarChart only on native
let BarChart: any = null;
if (Platform.OS !== 'web') {
  BarChart = require('react-native-gifted-charts').BarChart;
}

export function MemberChart() {
  const getMemberStats = useAppStore((state) => state.getMemberStats);
  const memberStats = getMemberStats();

  const totalStreams = memberStats.reduce((sum, m) => sum + m.totalStreams, 0);

  // Web fallback or native chart
  const renderChart = () => {
    if (Platform.OS === 'web' || !BarChart) {
      return (
        <View style={styles.webFallback}>
          {memberStats.map((member) => (
            <View key={member.name} style={styles.memberBarRow}>
              <View
                style={[
                  styles.memberBarBg,
                  {
                    backgroundColor: member.color,
                    width: totalStreams > 0 ? `${(member.totalStreams / totalStreams) * 100}%` : '0%',
                  },
                ]}
              />
              <Text style={styles.memberBarName}>{member.name}</Text>
              <Text style={styles.memberBarValue}>{formatNumber(member.totalStreams)}</Text>
            </View>
          ))}
        </View>
      );
    }

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

    return (
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
    );
  };

  return (
    <GlassCard style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>Member Solo Streams</Text>
        <Text style={styles.subtitle}>
          Total: {formatNumber(totalStreams)}
        </Text>
      </View>

      {renderChart()}

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
  webFallback: {
    gap: 8,
    marginBottom: 16,
  },
  memberBarRow: {
    flexDirection: 'row',
    alignItems: 'center',
    height: 36,
    backgroundColor: 'rgba(255, 255, 255, 0.05)',
    borderRadius: 8,
    overflow: 'hidden',
  },
  memberBarBg: {
    position: 'absolute',
    left: 0,
    top: 0,
    bottom: 0,
    opacity: 0.3,
  },
  memberBarName: {
    color: '#ffffff',
    fontSize: 13,
    fontWeight: '500',
    paddingLeft: 12,
    flex: 1,
  },
  memberBarValue: {
    color: '#60a5fa',
    fontSize: 13,
    fontWeight: '600',
    paddingRight: 12,
  },
});
