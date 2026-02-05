import React from 'react';
import { View, ViewProps } from 'react-native';

interface GlassCardProps extends ViewProps {
  children: React.ReactNode;
  variant?: 'default' | 'dark' | 'light';
}

export function GlassCard({
  children,
  variant = 'default',
  style,
  ...props
}: GlassCardProps) {
  const bgColors = {
    default: 'rgba(255, 255, 255, 0.1)',
    dark: 'rgba(0, 0, 0, 0.3)',
    light: 'rgba(255, 255, 255, 0.2)',
  };

  const borderColors = {
    default: 'rgba(255, 255, 255, 0.15)',
    dark: 'rgba(255, 255, 255, 0.1)',
    light: 'rgba(255, 255, 255, 0.25)',
  };

  return (
    <View
      style={[
        {
          backgroundColor: bgColors[variant],
          borderRadius: 16,
          borderWidth: 1,
          borderColor: borderColors[variant],
          padding: 16,
          // Note: backdrop-filter blur requires native module (expo-blur)
          // For now using solid semi-transparent background
        },
        style,
      ]}
      {...props}
    >
      {children}
    </View>
  );
}
