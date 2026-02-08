import React, { forwardRef } from 'react';
import { View, Text, StyleSheet } from 'react-native';
import ViewShot from 'react-native-view-shot';
import { colors } from '../theme/colors';

interface ShareableCardProps {
  children: React.ReactNode;
  artistName?: string;
  subtitle?: string;
  showHeader?: boolean;
  showFooter?: boolean;
}

const ShareableCard = forwardRef<ViewShot, ShareableCardProps>(
  ({ children, artistName, subtitle, showHeader = true, showFooter = true }, ref) => {
    const today = new Date().toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });

    return (
      <ViewShot
        ref={ref}
        options={{ format: 'png', quality: 1, result: 'tmpfile' }}
        style={styles.container}
      >
        {showHeader && (
          <View style={styles.header}>
            <View>
              <Text style={styles.brandName}>OPM Insights</Text>
              <Text style={styles.dateText}>{today}</Text>
            </View>
            {artistName && (
              <View style={styles.headerRight}>
                <Text style={styles.artistTitle} numberOfLines={1}>
                  {artistName}
                </Text>
                {subtitle && (
                  <Text style={styles.subtitleText}>{subtitle}</Text>
                )}
              </View>
            )}
          </View>
        )}

        <View style={styles.body}>{children}</View>

        {showFooter && (
          <View style={styles.footer}>
            <Text style={styles.footerText}>OPM Insights | Spotify Data</Text>
          </View>
        )}
      </ViewShot>
    );
  },
);

ShareableCard.displayName = 'ShareableCard';

export default ShareableCard;

const styles = StyleSheet.create({
  container: {
    backgroundColor: '#0f172a',
    borderRadius: 16,
    overflow: 'hidden',
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: 'rgba(71, 85, 105, 0.3)',
  },
  brandName: {
    color: colors.primary,
    fontSize: 15,
    fontWeight: '700',
    letterSpacing: 0.3,
  },
  dateText: {
    color: colors.textMuted,
    fontSize: 11,
    marginTop: 2,
  },
  headerRight: {
    alignItems: 'flex-end',
    flexShrink: 1,
    maxWidth: '55%',
  },
  artistTitle: {
    color: colors.textPrimary,
    fontSize: 15,
    fontWeight: '700',
  },
  subtitleText: {
    color: colors.textSecondary,
    fontSize: 11,
    marginTop: 2,
  },
  body: {
    padding: 16,
  },
  footer: {
    alignItems: 'center',
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: 'rgba(71, 85, 105, 0.3)',
  },
  footerText: {
    color: colors.textMuted,
    fontSize: 10,
    letterSpacing: 0.5,
  },
});
