import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';

const PUSH_TOKEN_KEY = '@sb19/pushToken';
const NOTIFICATION_HISTORY_KEY = '@sb19/notificationHistory';

// Configure notification behavior
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

export interface PushNotification {
  id: string;
  title: string;
  body: string;
  data?: Record<string, unknown>;
  timestamp: string;
  read: boolean;
}

class NotificationService {
  private expoPushToken: string | null = null;

  async registerForPushNotifications(): Promise<string | null> {
    let token: string | null = null;

    if (Platform.OS === 'android') {
      await Notifications.setNotificationChannelAsync('default', {
        name: 'SB19 Analytics',
        importance: Notifications.AndroidImportance.MAX,
        vibrationPattern: [0, 250, 250, 250],
        lightColor: '#60a5fa',
      });
    }

    if (Device.isDevice) {
      const { status: existingStatus } = await Notifications.getPermissionsAsync();
      let finalStatus = existingStatus;

      if (existingStatus !== 'granted') {
        const { status } = await Notifications.requestPermissionsAsync();
        finalStatus = status;
      }

      if (finalStatus !== 'granted') {
        console.log('Failed to get push notification permission');
        return null;
      }

      try {
        const tokenResponse = await Notifications.getExpoPushTokenAsync({
          projectId: 'your-project-id', // Replace with your Expo project ID
        });
        token = tokenResponse.data;
        this.expoPushToken = token;
        await AsyncStorage.setItem(PUSH_TOKEN_KEY, token);
      } catch (error) {
        console.error('Error getting push token:', error);
      }
    } else {
      console.log('Push notifications require a physical device');
    }

    return token;
  }

  async getStoredToken(): Promise<string | null> {
    if (this.expoPushToken) return this.expoPushToken;
    const token = await AsyncStorage.getItem(PUSH_TOKEN_KEY);
    this.expoPushToken = token;
    return token;
  }

  // Schedule a local notification
  async scheduleLocalNotification(
    title: string,
    body: string,
    data?: Record<string, unknown>,
    trigger?: Notifications.NotificationTriggerInput
  ): Promise<string> {
    const identifier = await Notifications.scheduleNotificationAsync({
      content: {
        title,
        body,
        data,
        sound: true,
      },
      trigger: trigger || null, // null = immediate
    });

    // Save to history
    await this.addToHistory({
      id: identifier,
      title,
      body,
      data,
      timestamp: new Date().toISOString(),
      read: false,
    });

    return identifier;
  }

  // Cancel a scheduled notification
  async cancelNotification(identifier: string): Promise<void> {
    await Notifications.cancelScheduledNotificationAsync(identifier);
  }

  // Cancel all scheduled notifications
  async cancelAllNotifications(): Promise<void> {
    await Notifications.cancelAllScheduledNotificationsAsync();
  }

  // Get notification history
  async getNotificationHistory(): Promise<PushNotification[]> {
    const history = await AsyncStorage.getItem(NOTIFICATION_HISTORY_KEY);
    return history ? JSON.parse(history) : [];
  }

  // Add notification to history
  private async addToHistory(notification: PushNotification): Promise<void> {
    const history = await this.getNotificationHistory();
    history.unshift(notification);
    // Keep only last 50 notifications
    const trimmed = history.slice(0, 50);
    await AsyncStorage.setItem(NOTIFICATION_HISTORY_KEY, JSON.stringify(trimmed));
  }

  // Mark notification as read
  async markAsRead(id: string): Promise<void> {
    const history = await this.getNotificationHistory();
    const updated = history.map(n =>
      n.id === id ? { ...n, read: true } : n
    );
    await AsyncStorage.setItem(NOTIFICATION_HISTORY_KEY, JSON.stringify(updated));
  }

  // Clear notification history
  async clearHistory(): Promise<void> {
    await AsyncStorage.removeItem(NOTIFICATION_HISTORY_KEY);
  }

  // Get badge count (unread notifications)
  async getBadgeCount(): Promise<number> {
    const history = await this.getNotificationHistory();
    return history.filter(n => !n.read).length;
  }

  // Set up notification listeners
  setupListeners(
    onReceived: (notification: Notifications.Notification) => void,
    onResponse: (response: Notifications.NotificationResponse) => void
  ): () => void {
    const receivedSubscription = Notifications.addNotificationReceivedListener(onReceived);
    const responseSubscription = Notifications.addNotificationResponseReceivedListener(onResponse);

    return () => {
      receivedSubscription.remove();
      responseSubscription.remove();
    };
  }

  // Check for streaming milestones
  checkMilestones(
    trackName: string,
    currentStreams: number,
    previousStreams: number
  ): { milestone: number; label: string } | null {
    const milestones = [
      { threshold: 1_000_000_000, label: '1 Billion' },
      { threshold: 500_000_000, label: '500 Million' },
      { threshold: 100_000_000, label: '100 Million' },
      { threshold: 50_000_000, label: '50 Million' },
      { threshold: 10_000_000, label: '10 Million' },
      { threshold: 5_000_000, label: '5 Million' },
      { threshold: 1_000_000, label: '1 Million' },
    ];

    for (const { threshold, label } of milestones) {
      if (currentStreams >= threshold && previousStreams < threshold) {
        return { milestone: threshold, label };
      }
    }

    return null;
  }

  // Send milestone notification
  async sendMilestoneNotification(
    trackName: string,
    milestone: string
  ): Promise<void> {
    await this.scheduleLocalNotification(
      `🎉 ${trackName} reached ${milestone} streams!`,
      `Congratulations A'TIN! Another milestone achieved.`,
      { type: 'milestone', track: trackName, milestone }
    );
  }

  // Send rank change notification
  async sendRankChangeNotification(
    trackName: string,
    oldRank: number,
    newRank: number
  ): Promise<void> {
    const direction = newRank < oldRank ? 'up' : 'down';
    const emoji = direction === 'up' ? '📈' : '📉';

    await this.scheduleLocalNotification(
      `${emoji} ${trackName} moved ${direction}!`,
      `Now at #${newRank} (was #${oldRank})`,
      { type: 'rank_change', track: trackName, oldRank, newRank }
    );
  }
}

export const notificationService = new NotificationService();
