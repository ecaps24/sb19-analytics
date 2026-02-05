import React from 'react';
import { View, StyleSheet, ViewProps } from 'react-native';
import LinearGradient from 'react-native-linear-gradient';

interface GradientBackgroundProps extends ViewProps {
  children: React.ReactNode;
  variant?: 'default' | 'purple' | 'blue';
}

export function GradientBackground({
  children,
  variant = 'default',
  style,
  ...props
}: GradientBackgroundProps) {
  const gradients = {
    default: ['#0f0c29', '#302b63', '#24243e'],
    purple: ['#1e1b4b', '#312e81', '#3730a3'],
    blue: ['#0c1445', '#1e3a5f', '#1e3a8a'],
  };

  return (
    <LinearGradient
      colors={gradients[variant]}
      style={[styles.gradient, style]}
      start={{ x: 0, y: 0 }}
      end={{ x: 1, y: 1 }}
      {...props}
    >
      {children}
    </LinearGradient>
  );
}

// Fallback component if LinearGradient is not working
export function GradientBackgroundFallback({
  children,
  style,
  ...props
}: ViewProps & { children: React.ReactNode }) {
  return (
    <View
      style={[styles.fallbackGradient, style]}
      {...props}
    >
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  gradient: {
    flex: 1,
  },
  fallbackGradient: {
    flex: 1,
    backgroundColor: '#1e1b4b',
  },
});
