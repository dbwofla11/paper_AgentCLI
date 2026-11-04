import { useSyncExternalStore } from 'react';
import { getConnectionSnapshot, subscribeConnection, type ConnectionSnapshot } from '../api/client';

export function useConnection(): ConnectionSnapshot {
  return useSyncExternalStore(subscribeConnection, getConnectionSnapshot);
}
