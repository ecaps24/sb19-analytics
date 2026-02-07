import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Linking,
  Alert,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useDataStore } from '../store/useDataStore';
import { clearAllCache, getCacheSize } from '../services/cacheService';
import { colors } from '../theme/colors';
import { timeAgo } from '../utils/formatters';
import GlassCard from '../components/GlassCard';

export default function SettingsScreen() {
  const { lastUpdated, fetchData, loading } = useDataStore();
  const [cacheSize, setCacheSize] = useState('');

  const loadCacheSize = useCallback(async () => {
    const size = await getCacheSize();
    setCacheSize(size);
  }, []);

  useEffect(() => {
    loadCacheSize();
  }, [loadCacheSize]);

  const handleRefresh = useCallback(async () => {
    await fetchData(true);
    loadCacheSize();
  }, [fetchData, loadCacheSize]);

  const handleClearCache = useCallback(() => {
    Alert.alert(
      'Clear Cache',
      'This will remove all cached data. The app will re-download data on next refresh.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear',
          style: 'destructive',
          onPress: async () => {
            await clearAllCache();
            setCacheSize('0 B');
          },
        },
      ],
    );
  }, []);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>Settings</Text>

      {/* Data section */}
      <GlassCard style={styles.section}>
        <Text style={styles.sectionTitle}>Data</Text>

        <View style={styles.row}>
          <View>
            <Text style={styles.label}>Last Updated</Text>
            <Text style={styles.value}>
              {lastUpdated ? timeAgo(lastUpdated) : 'Never'}
            </Text>
          </View>
          <TouchableOpacity
            style={[styles.btn, loading && styles.btnDisabled]}
            onPress={handleRefresh}
            disabled={loading}
          >
            <Ionicons
              name="refresh"
              size={16}
              color={loading ? colors.textMuted : colors.primary}
            />
            <Text
              style={[
                styles.btnText,
                loading && { color: colors.textMuted },
              ]}
            >
              {loading ? 'Refreshing...' : 'Refresh Now'}
            </Text>
          </TouchableOpacity>
        </View>

        <View style={styles.divider} />

        <View style={styles.row}>
          <View>
            <Text style={styles.label}>Cache Size</Text>
            <Text style={styles.value}>{cacheSize || 'Calculating...'}</Text>
          </View>
          <TouchableOpacity style={styles.btn} onPress={handleClearCache}>
            <Ionicons name="trash-outline" size={16} color={colors.error} />
            <Text style={[styles.btnText, { color: colors.error }]}>
              Clear Cache
            </Text>
          </TouchableOpacity>
        </View>
      </GlassCard>

      {/* About section */}
      <GlassCard style={styles.section}>
        <Text style={styles.sectionTitle}>About</Text>
        <View style={styles.aboutRow}>
          <Text style={styles.label}>App</Text>
          <Text style={styles.value}>OPM Insights v1.0.0</Text>
        </View>
        <View style={styles.aboutRow}>
          <Text style={styles.label}>Data Source</Text>
          <Text style={styles.value}>Spotify via RPA</Text>
        </View>
        <View style={styles.aboutRow}>
          <Text style={styles.label}>Artists Tracked</Text>
          <Text style={styles.value}>144 OPM artists</Text>
        </View>
        <View style={styles.aboutRow}>
          <Text style={styles.label}>Genres</Text>
          <Text style={styles.value}>8 categories</Text>
        </View>
      </GlassCard>

      {/* Support */}
      <GlassCard style={styles.section}>
        <Text style={styles.sectionTitle}>Support</Text>
        <TouchableOpacity
          style={styles.linkRow}
          onPress={() =>
            Linking.openURL('https://github.com/ecaps24/sb19-analytics')
          }
        >
          <Ionicons name="logo-github" size={20} color={colors.textSecondary} />
          <Text style={styles.linkText}>View on GitHub</Text>
          <Ionicons
            name="chevron-forward"
            size={16}
            color={colors.textMuted}
          />
        </TouchableOpacity>
      </GlassCard>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.background,
  },
  content: {
    padding: 16,
    paddingBottom: 40,
  },
  title: {
    color: colors.textPrimary,
    fontSize: 22,
    fontWeight: '700',
    marginBottom: 16,
  },
  section: {
    marginBottom: 16,
  },
  sectionTitle: {
    color: colors.textPrimary,
    fontSize: 16,
    fontWeight: '600',
    marginBottom: 16,
  },
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  label: {
    color: colors.textMuted,
    fontSize: 13,
    marginBottom: 2,
  },
  value: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: '500',
  },
  btn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 10,
    backgroundColor: colors.surface,
  },
  btnDisabled: {
    opacity: 0.6,
  },
  btnText: {
    color: colors.primary,
    fontSize: 13,
    fontWeight: '600',
  },
  divider: {
    height: 1,
    backgroundColor: colors.border,
    marginVertical: 14,
  },
  aboutRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginBottom: 10,
  },
  linkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 6,
  },
  linkText: {
    color: colors.textPrimary,
    fontSize: 14,
    fontWeight: '500',
    flex: 1,
  },
});
