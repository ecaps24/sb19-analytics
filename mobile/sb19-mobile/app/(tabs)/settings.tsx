import React from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Switch,
  Pressable,
  Linking,
  Alert,
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAppStore } from '../../services/store';
import { GlassCard } from '../../components/ui/GlassCard';
import { formatDateTime } from '../../hooks/useFormatters';

export default function SettingsScreen() {
  const settings = useAppStore((state) => state.settings);
  const updateSettings = useAppStore((state) => state.updateSettings);
  const network = useAppStore((state) => state.network);
  const lastSync = useAppStore((state) => state.lastSync);
  const loadData = useAppStore((state) => state.loadData);

  const handleToggleNotifications = (type: keyof typeof settings.notifications) => {
    updateSettings({
      notifications: {
        ...settings.notifications,
        [type]: !settings.notifications[type],
      },
    });
  };

  const handleClearCache = async () => {
    Alert.alert(
      'Clear Cache',
      'This will clear all cached data. You will need to reload data from the server.',
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear',
          style: 'destructive',
          onPress: async () => {
            try {
              await AsyncStorage.clear();
              Alert.alert('Success', 'Cache cleared. Reloading data...');
              loadData();
            } catch (error) {
              Alert.alert('Error', 'Failed to clear cache');
            }
          },
        },
      ]
    );
  };

  const handleOpenSpotify = () => {
    Linking.openURL('https://open.spotify.com/artist/0rKyLJnmMi6IknuqCZIVvf');
  };

  return (
    <SafeAreaView style={styles.container} edges={['top']}>
      <ScrollView
        style={styles.scrollView}
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
      >
        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>Settings</Text>
          <Text style={styles.subtitle}>App Preferences & Info</Text>
        </View>

        {/* Network Status */}
        <GlassCard style={styles.card}>
          <View style={styles.cardHeader}>
            <Ionicons name="wifi" size={20} color="#60a5fa" />
            <Text style={styles.cardTitle}>Network Status</Text>
          </View>
          <View style={styles.statusRow}>
            <Text style={styles.statusLabel}>Connection</Text>
            <View style={styles.statusValue}>
              <View
                style={[
                  styles.statusDot,
                  { backgroundColor: network.isConnected ? '#34d399' : '#ef4444' },
                ]}
              />
              <Text style={styles.statusText}>
                {network.isConnected ? 'Online' : 'Offline'}
              </Text>
            </View>
          </View>
          <View style={styles.statusRow}>
            <Text style={styles.statusLabel}>Last Sync</Text>
            <Text style={styles.statusText}>
              {lastSync ? formatDateTime(lastSync) : 'Never'}
            </Text>
          </View>
        </GlassCard>

        {/* Notifications */}
        <GlassCard style={styles.card}>
          <View style={styles.cardHeader}>
            <Ionicons name="notifications" size={20} color="#60a5fa" />
            <Text style={styles.cardTitle}>Notifications</Text>
          </View>

          <View style={styles.settingRow}>
            <View style={styles.settingInfo}>
              <Text style={styles.settingLabel}>Enable Notifications</Text>
              <Text style={styles.settingDescription}>
                Receive updates about streaming milestones
              </Text>
            </View>
            <Switch
              value={settings.notifications.enabled}
              onValueChange={() => handleToggleNotifications('enabled')}
              trackColor={{ false: '#374151', true: 'rgba(96, 165, 250, 0.5)' }}
              thumbColor={settings.notifications.enabled ? '#60a5fa' : '#9ca3af'}
            />
          </View>

          {settings.notifications.enabled && (
            <>
              <View style={styles.settingRow}>
                <View style={styles.settingInfo}>
                  <Text style={styles.settingLabel}>Stream Milestones</Text>
                  <Text style={styles.settingDescription}>
                    When tracks reach 1M, 10M, etc.
                  </Text>
                </View>
                <Switch
                  value={settings.notifications.milestones}
                  onValueChange={() => handleToggleNotifications('milestones')}
                  trackColor={{ false: '#374151', true: 'rgba(96, 165, 250, 0.5)' }}
                  thumbColor={settings.notifications.milestones ? '#60a5fa' : '#9ca3af'}
                />
              </View>

              <View style={styles.settingRow}>
                <View style={styles.settingInfo}>
                  <Text style={styles.settingLabel}>Rank Changes</Text>
                  <Text style={styles.settingDescription}>
                    When track rankings change
                  </Text>
                </View>
                <Switch
                  value={settings.notifications.rankChanges}
                  onValueChange={() => handleToggleNotifications('rankChanges')}
                  trackColor={{ false: '#374151', true: 'rgba(96, 165, 250, 0.5)' }}
                  thumbColor={settings.notifications.rankChanges ? '#60a5fa' : '#9ca3af'}
                />
              </View>

              <View style={styles.settingRow}>
                <View style={styles.settingInfo}>
                  <Text style={styles.settingLabel}>Listener Changes</Text>
                  <Text style={styles.settingDescription}>
                    Monthly listener increases/decreases
                  </Text>
                </View>
                <Switch
                  value={settings.notifications.listenerChanges}
                  onValueChange={() => handleToggleNotifications('listenerChanges')}
                  trackColor={{ false: '#374151', true: 'rgba(96, 165, 250, 0.5)' }}
                  thumbColor={settings.notifications.listenerChanges ? '#60a5fa' : '#9ca3af'}
                />
              </View>
            </>
          )}
        </GlassCard>

        {/* Data & Storage */}
        <GlassCard style={styles.card}>
          <View style={styles.cardHeader}>
            <Ionicons name="server" size={20} color="#60a5fa" />
            <Text style={styles.cardTitle}>Data & Storage</Text>
          </View>

          <Pressable style={styles.actionRow} onPress={handleClearCache}>
            <View style={styles.actionInfo}>
              <Text style={styles.actionLabel}>Clear Cache</Text>
              <Text style={styles.actionDescription}>
                Remove cached data and reload from server
              </Text>
            </View>
            <Ionicons name="trash-outline" size={20} color="#ef4444" />
          </Pressable>
        </GlassCard>

        {/* About */}
        <GlassCard style={styles.card}>
          <View style={styles.cardHeader}>
            <Ionicons name="information-circle" size={20} color="#60a5fa" />
            <Text style={styles.cardTitle}>About</Text>
          </View>

          <View style={styles.aboutRow}>
            <Text style={styles.aboutLabel}>Version</Text>
            <Text style={styles.aboutValue}>1.0.0</Text>
          </View>

          <Pressable style={styles.actionRow} onPress={handleOpenSpotify}>
            <View style={styles.actionInfo}>
              <Text style={styles.actionLabel}>SB19 on Spotify</Text>
              <Text style={styles.actionDescription}>
                Open SB19's Spotify profile
              </Text>
            </View>
            <Ionicons name="open-outline" size={20} color="#1DB954" />
          </Pressable>

          <View style={styles.credits}>
            <Text style={styles.creditsText}>
              Made with 💙 for A'TIN
            </Text>
            <Text style={styles.creditsSubtext}>
              This is an unofficial fan app
            </Text>
          </View>
        </GlassCard>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: '#0f0c29',
  },
  scrollView: {
    flex: 1,
  },
  scrollContent: {
    paddingBottom: 24,
  },
  header: {
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 16,
  },
  title: {
    fontSize: 28,
    fontWeight: '800',
    color: '#ffffff',
    marginBottom: 4,
  },
  subtitle: {
    fontSize: 13,
    color: '#9ca3af',
  },
  card: {
    marginHorizontal: 16,
    marginBottom: 16,
  },
  cardHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginBottom: 16,
  },
  cardTitle: {
    fontSize: 16,
    fontWeight: '600',
    color: '#ffffff',
  },
  statusRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  statusLabel: {
    fontSize: 14,
    color: '#9ca3af',
  },
  statusValue: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusText: {
    fontSize: 14,
    color: '#ffffff',
    fontWeight: '500',
  },
  settingRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.05)',
  },
  settingInfo: {
    flex: 1,
    marginRight: 16,
  },
  settingLabel: {
    fontSize: 14,
    color: '#ffffff',
    fontWeight: '500',
    marginBottom: 2,
  },
  settingDescription: {
    fontSize: 12,
    color: '#6b7280',
  },
  actionRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.05)',
  },
  actionInfo: {
    flex: 1,
    marginRight: 16,
  },
  actionLabel: {
    fontSize: 14,
    color: '#ffffff',
    fontWeight: '500',
    marginBottom: 2,
  },
  actionDescription: {
    fontSize: 12,
    color: '#6b7280',
  },
  aboutRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 12,
  },
  aboutLabel: {
    fontSize: 14,
    color: '#9ca3af',
  },
  aboutValue: {
    fontSize: 14,
    color: '#ffffff',
    fontWeight: '500',
  },
  credits: {
    marginTop: 16,
    paddingTop: 16,
    borderTopWidth: 1,
    borderTopColor: 'rgba(255, 255, 255, 0.05)',
    alignItems: 'center',
  },
  creditsText: {
    fontSize: 14,
    color: '#ffffff',
    marginBottom: 4,
  },
  creditsSubtext: {
    fontSize: 12,
    color: '#6b7280',
  },
});
