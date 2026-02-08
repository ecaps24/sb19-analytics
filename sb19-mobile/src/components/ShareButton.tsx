import React, { useState, RefObject } from 'react';
import { TouchableOpacity, ActivityIndicator, StyleSheet } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import ViewShot from 'react-native-view-shot';
import { captureAndShare } from '../utils/shareUtils';
import { colors } from '../theme/colors';

interface ShareButtonProps {
  viewShotRef: RefObject<ViewShot | null>;
}

export default function ShareButton({ viewShotRef }: ShareButtonProps) {
  const [capturing, setCapturing] = useState(false);

  const handlePress = async () => {
    setCapturing(true);
    try {
      await captureAndShare(viewShotRef);
    } finally {
      setCapturing(false);
    }
  };

  return (
    <TouchableOpacity
      style={styles.button}
      onPress={handlePress}
      disabled={capturing}
    >
      {capturing ? (
        <ActivityIndicator size="small" color={colors.primary} />
      ) : (
        <Ionicons name="share-outline" size={20} color={colors.primary} />
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: {
    padding: 8,
    borderRadius: 10,
    backgroundColor: colors.primaryGlow,
    width: 38,
    height: 38,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
