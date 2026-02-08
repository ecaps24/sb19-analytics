import { Alert } from 'react-native';
import * as Sharing from 'expo-sharing';
import { RefObject } from 'react';
import ViewShot from 'react-native-view-shot';

export async function captureAndShare(viewShotRef: RefObject<ViewShot | null>) {
  try {
    if (!viewShotRef.current?.capture) {
      Alert.alert('Error', 'Unable to capture screenshot');
      return;
    }

    const uri = await viewShotRef.current.capture();

    const isAvailable = await Sharing.isAvailableAsync();
    if (!isAvailable) {
      Alert.alert('Sharing not available', 'Sharing is not supported on this device');
      return;
    }

    await Sharing.shareAsync(uri, {
      mimeType: 'image/png',
      dialogTitle: 'Share OPM Insights',
    });
  } catch (error) {
    Alert.alert('Error', 'Failed to capture and share. Please try again.');
  }
}
