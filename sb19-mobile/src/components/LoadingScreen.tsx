import React from 'react';
import { View, StyleSheet, Animated } from 'react-native';
import { colors } from '../theme/colors';

const SkeletonLine = ({ width, height = 16, style }: { width: number | string; height?: number; style?: any }) => {
  const animatedValue = React.useRef(new Animated.Value(0.3)).current;

  React.useEffect(() => {
    const animation = Animated.loop(
      Animated.sequence([
        Animated.timing(animatedValue, { toValue: 0.7, duration: 1000, useNativeDriver: true }),
        Animated.timing(animatedValue, { toValue: 0.3, duration: 1000, useNativeDriver: true }),
      ]),
    );
    animation.start();
    return () => animation.stop();
  }, [animatedValue]);

  return (
    <Animated.View
      style={[
        {
          width: width as any,
          height,
          borderRadius: 6,
          backgroundColor: colors.surfaceLight,
          opacity: animatedValue,
        },
        style,
      ]}
    />
  );
};

export default function LoadingScreen() {
  return (
    <View style={styles.container}>
      {/* Search bar skeleton */}
      <SkeletonLine width="100%" height={44} style={{ marginBottom: 16 }} />

      {/* Genre tabs skeleton */}
      <View style={styles.tabsRow}>
        {[60, 70, 50, 80, 60].map((w, i) => (
          <SkeletonLine key={i} width={w} height={32} style={{ marginRight: 8 }} />
        ))}
      </View>

      {/* Card skeletons */}
      {Array.from({ length: 8 }).map((_, i) => (
        <View key={i} style={styles.card}>
          <SkeletonLine width={32} height={32} style={{ borderRadius: 16 }} />
          <View style={{ flex: 1, marginLeft: 12 }}>
            <SkeletonLine width="60%" height={18} style={{ marginBottom: 8 }} />
            <SkeletonLine width="40%" height={14} />
          </View>
          <SkeletonLine width={50} height={14} />
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
    padding: 16,
  },
  tabsRow: {
    flexDirection: 'row',
    marginBottom: 16,
  },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: colors.card,
    borderRadius: 12,
    padding: 16,
    marginBottom: 8,
  },
});
