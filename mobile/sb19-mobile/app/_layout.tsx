import { useEffect, useState } from 'react';
import { Stack } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { View, StyleSheet, Platform } from 'react-native';
import { GestureHandlerRootView } from 'react-native-gesture-handler';
import { useAppStore } from '../services/store';
import '../global.css';

export default function RootLayout() {
  const loadData = useAppStore((state) => state.loadData);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    // Load data on app start
    loadData();
  }, [loadData]);

  // Prevent hydration mismatch
  if (!mounted && Platform.OS === 'web') {
    return (
      <View style={styles.container}>
        <StatusBar style="light" />
      </View>
    );
  }

  return (
    <GestureHandlerRootView style={styles.container}>
      <View style={styles.container}>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerShown: false,
            contentStyle: { backgroundColor: '#0f0c29' },
            animation: 'slide_from_right',
          }}
        >
          <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
          <Stack.Screen
            name="track/[id]"
            options={{
              presentation: 'modal',
              animation: 'slide_from_bottom',
            }}
          />
        </Stack>
      </View>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0c29',
  },
});
