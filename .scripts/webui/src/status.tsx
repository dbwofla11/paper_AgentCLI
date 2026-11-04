import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { fetchStatus, toApiError, type ApiError } from './api/client';
import type { StatusPayload } from './api/types';

interface StatusState {
  data: StatusPayload | null;
  /** Last failure; `data` keeps the previous successful result. */
  error: ApiError | null;
  loading: boolean;
  checkedAt: Date | null;
}

export interface StatusContextValue extends StatusState {
  refresh: () => void;
}

const StatusContext = createContext<StatusContextValue | null>(null);

/** Shares one GET /api/status result between the 상태 and 작업 screens. */
export function StatusProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<StatusState>({ data: null, error: null, loading: true, checkedAt: null });
  const controllerRef = useRef<AbortController | null>(null);

  const refresh = useCallback(() => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setState((previous) => ({ ...previous, loading: true }));
    fetchStatus(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ data, error: null, loading: false, checkedAt: new Date() });
      },
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setState((previous) => ({ ...previous, error: toApiError(error), loading: false }));
        }
      },
    );
  }, []);

  useEffect(() => {
    refresh();
    return () => controllerRef.current?.abort();
  }, [refresh]);

  const value = useMemo(() => ({ ...state, refresh }), [state, refresh]);
  return <StatusContext value={value}>{children}</StatusContext>;
}

export function useStatus(): StatusContextValue {
  const value = useContext(StatusContext);
  if (!value) throw new Error('useStatus must be used inside <StatusProvider>');
  return value;
}
