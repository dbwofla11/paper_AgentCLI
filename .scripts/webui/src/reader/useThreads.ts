import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchThreads, toApiError, type ApiError } from '../api/client';
import type { ReaderThread, TurnStatus } from '../api/types';

/** The server writes the thread file in the job's `finally`, shortly after the terminal event. */
const SETTLE_DELAYS_MS = [300, 600, 1_000, 1_500, 2_500, 4_000] as const;
/** While any turn is queued or running, the list re-reads so statuses update without an open stream. */
const BUSY_POLL_MS = 5_000;

/** A queued or running turn: its thread takes no new question (409 `thread_busy`). */
export function turnBusy(status: TurnStatus): boolean {
  return status === 'queued' || status === 'running';
}

export interface ThreadsState {
  threads: ReaderThread[] | null;
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
  /** Re-reads the threads until `turnId` is no longer queued or running (its stream just ended). */
  settle: (turnId: string) => void;
  upsert: (thread: ReaderThread) => void;
  remove: (threadId: string) => void;
}

function findTurnStatus(threads: ReaderThread[], turnId: string): TurnStatus | null {
  for (const thread of threads) {
    for (const turn of thread.turns) if (turn.turn_id === turnId) return turn.status;
  }
  return null;
}

/** Threads of one paper (GET /api/papers/{slug}/threads), newest activity first. */
export function useThreads(slug: string, reloadToken: number): ThreadsState {
  const [threads, setThreads] = useState<ReaderThread[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const controllerRef = useRef<AbortController | null>(null);
  const timers = useRef(new Set<number>());
  /**
   * Bumped by every load and every local mutation (upsert after an ask, remove after a delete).
   * A load response is applied only while its generation is current, so a GET that started before
   * an ask or delete can never bring back the older list.
   */
  const generationRef = useRef(0);

  /** Resolves to the applied list, or null when it failed, was aborted, or was superseded. */
  const load = useCallback(async (): Promise<ReaderThread[] | null> => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const generation = ++generationRef.current;
    setLoading(true);
    try {
      const next = await fetchThreads(slug, controller.signal);
      if (controller.signal.aborted || generation !== generationRef.current) return null;
      setThreads(next);
      setError(null);
      return next;
    } catch (caught) {
      if (controller.signal.aborted || generation !== generationRef.current) return null;
      setError(toApiError(caught));
      return null;
    } finally {
      // A newer load aborted this one and owns the flag; a mutation does not start a request.
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    void load();
    const pending = timers.current;
    return () => {
      controllerRef.current?.abort();
      for (const timer of pending) window.clearTimeout(timer);
      pending.clear();
    };
  }, [load, reloadToken]);

  const anyBusy = threads?.some((thread) => thread.turns.some((turn) => turnBusy(turn.status))) ?? false;
  useEffect(() => {
    if (!anyBusy) return;
    const timer = window.setInterval(() => void load(), BUSY_POLL_MS);
    return () => window.clearInterval(timer);
  }, [anyBusy, load]);

  const settle = useCallback(
    (turnId: string) => {
      const attempt = (index: number) => {
        const delay = SETTLE_DELAYS_MS[index];
        if (delay === undefined) return;
        const timer = window.setTimeout(async () => {
          timers.current.delete(timer);
          const next = await load();
          const status = next ? findTurnStatus(next, turnId) : null;
          if (status === null || turnBusy(status)) attempt(index + 1);
        }, delay);
        timers.current.add(timer);
      };
      attempt(0);
    },
    [load],
  );

  const upsert = useCallback((thread: ReaderThread) => {
    generationRef.current += 1;
    setThreads((previous) => {
      const list = previous ?? [];
      const index = list.findIndex((item) => item.thread_id === thread.thread_id);
      if (index === -1) return [...list, thread];
      const next = list.slice();
      next[index] = thread;
      return next;
    });
  }, []);

  const remove = useCallback((threadId: string) => {
    generationRef.current += 1;
    setThreads((previous) => previous?.filter((thread) => thread.thread_id !== threadId) ?? previous);
  }, []);

  const reload = useCallback(() => void load(), [load]);
  return { threads, error, loading, reload, settle, upsert, remove };
}
