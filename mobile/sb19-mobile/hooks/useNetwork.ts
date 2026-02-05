import { useEffect } from 'react';
import * as Network from 'expo-network';
import { useAppStore } from '../services/store';

export function useNetwork() {
  const setNetwork = useAppStore((state) => state.setNetwork);
  const network = useAppStore((state) => state.network);

  useEffect(() => {
    let mounted = true;

    const checkNetwork = async () => {
      try {
        const state = await Network.getNetworkStateAsync();
        if (mounted) {
          setNetwork({
            isConnected: state.isConnected ?? false,
            type: state.type ?? null,
          });
        }
      } catch (error) {
        console.error('Network check failed:', error);
        if (mounted) {
          setNetwork({ isConnected: false, type: null });
        }
      }
    };

    checkNetwork();

    // Check network every 30 seconds
    const interval = setInterval(checkNetwork, 30000);

    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [setNetwork]);

  return network;
}
