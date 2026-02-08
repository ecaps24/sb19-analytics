// Learn more https://docs.expo.io/guides/customizing-metro
const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

/** @type {import('expo/metro-config').MetroConfig} */
const config = getDefaultConfig(__dirname);

// Exclude android/ios build artifacts from Metro's file watcher
config.watcher = {
  ...config.watcher,
  additionalExts: config.watcher?.additionalExts || [],
};
config.resolver = {
  ...config.resolver,
  blockList: [
    /android\/.*/,
    /ios\/.*/,
  ],
};

module.exports = config;
