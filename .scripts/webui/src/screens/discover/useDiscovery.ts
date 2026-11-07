import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { fetchDailyDigest, fetchPapers, fetchSearch, fetchSearches, toApiError, type ApiError } from '../../api/client';
import type {
  DailyDigestPayload,
  DiscoveryRegistration,
  DiscoverySession,
  DiscoverySessionList,
  DiscoverySessionStatus,
  DiscoverySource,
  JobRecord,
} from '../../api/types';

/** The server writes the session file in the job's `finally`, shortly after the terminal event. */
const SETTLE_DELAYS_MS = [300, 600, 1_000, 1_500, 2_500, 4_000] as const;
/** While a search is queued or running, its session and the history re-read so statuses update without a stream. */
const BUSY_POLL_MS = 5_000;

/** A queued or running search: its job is still alive, it cannot be deleted, and no other search can start. */
export function isActiveSearch(status: DiscoverySessionStatus): boolean {
  return status === 'queued' || status === 'running';
}

function listBusy(list: DiscoverySessionList): boolean {
  return list.searches.some((search) => isActiveSearch(search.status));
}

function sessionBusy(session: DiscoverySession): boolean {
  return isActiveSearch(session.status);
}

export interface Polled<T> {
  data: T | null;
  /** Last failure; `data` keeps the previous successful result. */
  error: ApiError | null;
  loading: boolean;
  reload: () => void;
  /**
   * Re-reads until the data is no longer busy (a search's job stream just ended) and, when given,
   * `done(data)` holds (a registration wrote its candidate just before its terminal event).
   */
  settle: (done?: (data: T) => boolean) => void;
  /** Replaces the data locally; a GET that started earlier can no longer overwrite it. */
  update: (change: (data: T) => T) => void;
}

/**
 * One GET resource re-read on `reloadToken`, every BUSY_POLL_MS while `busy(data)`, and on `settle()`
 * (useThreads pattern). `fetcher` and `busy` must be stable.
 */
function usePolled<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  busy: (data: T) => boolean,
  reloadToken: number,
  initial: T | null,
): Polled<T> {
  const [data, setData] = useState<T | null>(initial);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const controllerRef = useRef<AbortController | null>(null);
  const timers = useRef(new Set<number>());
  /** Bumped by every load and every local update; only the current generation's response is applied. */
  const generationRef = useRef(0);

  /**
   * Resolves to the applied data, or null when it failed, was aborted, or was superseded. `quiet`
   * (polls and settles) leaves `loading` alone so refresh buttons do not flicker every few seconds.
   */
  const load = useCallback(async (quiet = false): Promise<T | null> => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    const generation = ++generationRef.current;
    if (!quiet) setLoading(true);
    try {
      const next = await fetcher(controller.signal);
      if (controller.signal.aborted || generation !== generationRef.current) return null;
      setData(next);
      setError(null);
      return next;
    } catch (caught) {
      if (controller.signal.aborted || generation !== generationRef.current) return null;
      setError(toApiError(caught));
      return null;
    } finally {
      // A newer load aborted this one and owns the flag; a local update does not start a request.
      if (!controller.signal.aborted) setLoading(false);
    }
  }, [fetcher]);

  useEffect(() => {
    void load();
    const pending = timers.current;
    return () => {
      controllerRef.current?.abort();
      for (const timer of pending) window.clearTimeout(timer);
      pending.clear();
    };
  }, [load, reloadToken]);

  const busyNow = data !== null && busy(data);
  useEffect(() => {
    if (!busyNow) return;
    const timer = window.setInterval(() => void load(true), BUSY_POLL_MS);
    return () => window.clearInterval(timer);
  }, [busyNow, load]);

  const settle = useCallback((done?: (data: T) => boolean) => {
    const attempt = (index: number) => {
      const delay = SETTLE_DELAYS_MS[index];
      if (delay === undefined) return;
      const timer = window.setTimeout(async () => {
        timers.current.delete(timer);
        const next = await load(true);
        if (next === null || busy(next) || (done !== undefined && !done(next))) attempt(index + 1);
      }, delay);
      timers.current.add(timer);
    };
    attempt(0);
  }, [load, busy]);

  const update = useCallback((change: (current: T) => T) => {
    generationRef.current += 1;
    setData((current) => (current === null ? current : change(current)));
  }, []);

  const reload = useCallback(() => void load(), [load]);
  return { data, error, loading, reload, settle, update };
}

/** Search history (GET /api/discovery/searches), newest first. */
export function useSearchList(reloadToken: number): Polled<DiscoverySessionList> {
  return usePolled(fetchSearches, listBusy, reloadToken, null);
}

/** One session (GET /api/discovery/searches/{id}); `initial` is the session POST just returned, if any. */
export function useSearchSession(
  searchId: string,
  reloadToken: number,
  initial: DiscoverySession | null,
): Polled<DiscoverySession> {
  const fetcher = useCallback((signal: AbortSignal) => fetchSearch(searchId, signal), [searchId]);
  return usePolled(fetcher, sessionBusy, reloadToken, initial);
}

function neverBusy(): boolean {
  return false;
}

/** One day of daily candidates (GET /api/discovery/daily/{date}); never polled, re-read on `refreshToken`. */
export function useDailyDay(date: string, refreshToken: number): Polled<DailyDigestPayload> {
  const fetcher = useCallback((signal: AbortSignal) => fetchDailyDigest(date, signal), [date]);
  return usePolled(fetcher, neverBusy, refreshToken, null);
}

// ── 등록 jobs: a module store, so a registration keeps its progress across route changes (useReviewStart pattern) ──

/** How a `discovery.register` job ended. */
export type RegisterOutcome =
  | { status: 'completed'; registration: DiscoveryRegistration | null }
  | { status: 'failed'; message: string }
  /**
   * The job reported `cancelled`. A cancel that arrives after publishing began does not stop it, so
   * the candidate re-read after the terminal event decides: `published` is true when it came back
   * `registered`, false when it did not, and null until that re-read answered (or when it never did).
   */
  | { status: 'cancelled'; published: boolean | null }
  /** The server no longer knows the job (it restarted while the job ran). */
  | { status: 'missing' };

export interface RegisterTrack {
  /** Job record POST /api/discovery/register answered with. */
  job: JobRecord;
  /** Library slug the registration writes; null when the server omitted it. */
  slug: string | null;
  /** Null while the job is queued or running. */
  outcome: RegisterOutcome | null;
}

let registerTracks: ReadonlyMap<string, RegisterTrack> = new Map();
const registerListeners = new Set<() => void>();
/** Jobs whose end was announced (toast + refresh) once; a remounted card replaying the stream stays quiet. */
const announcedJobs = new Set<string>();

function setTracks(next: ReadonlyMap<string, RegisterTrack>): void {
  registerTracks = next;
  for (const listener of registerListeners) listener();
}

function subscribeTracks(listener: () => void): () => void {
  registerListeners.add(listener);
  return () => registerListeners.delete(listener);
}

/** Store key of one candidate in one cache file (a search session or a daily digest). */
export function candidateKey(source: DiscoverySource, candidateId: string): string {
  return `${source.kind}\u0000${source.id}\u0000${candidateId}`;
}

export function trackRegister(key: string, job: JobRecord, slug: string | null): void {
  setTracks(new Map(registerTracks).set(key, { job, slug, outcome: null }));
}

/** Records how the followed job ended; true only the first time for this job, so the caller announces it once. */
export function finishRegister(key: string, jobId: string, outcome: RegisterOutcome): boolean {
  const track = registerTracks.get(key);
  if (track && track.job.job_id === jobId && track.outcome === null) {
    setTracks(new Map(registerTracks).set(key, { ...track, outcome }));
  }
  if (announcedJobs.has(jobId)) return false;
  announcedJobs.add(jobId);
  return true;
}

/** Records what the re-read after `jobId`'s cancel found; only that job's unconfirmed cancel changes. */
export function confirmCancel(key: string, jobId: string, published: boolean): void {
  const track = registerTracks.get(key);
  if (!track || track.job.job_id !== jobId) return;
  const outcome = track.outcome;
  if (outcome === null || outcome.status !== 'cancelled' || outcome.published !== null) return;
  setTracks(new Map(registerTracks).set(key, { ...track, outcome: { status: 'cancelled', published } }));
}

/** The candidate's latest registration in this page session; null when it has none. */
export function useRegisterTrack(key: string): RegisterTrack | null {
  return useSyncExternalStore(subscribeTracks, () => registerTracks.get(key) ?? null);
}

// ── Category labels (GET /api/papers `labels.category`), read once per page load ──

let categoryLabels: Readonly<Record<string, string>> | null = null;
let categoryLabelsRequest: Promise<Readonly<Record<string, string>>> | null = null;

function loadCategoryLabels(): Promise<Readonly<Record<string, string>>> {
  categoryLabelsRequest ??= fetchPapers().then(
    (payload) => {
      categoryLabels = payload.labels.category;
      return categoryLabels;
    },
    () => {
      categoryLabelsRequest = null; // the next dialog asks again
      return {};
    },
  );
  return categoryLabelsRequest;
}

/** Display names of the library categories; empty until they arrive (callers show the category id). */
export function useCategoryLabels(): Readonly<Record<string, string>> {
  const [labels, setLabels] = useState<Readonly<Record<string, string>>>(() => categoryLabels ?? {});
  useEffect(() => {
    if (categoryLabels) return;
    let active = true;
    void loadCategoryLabels().then((loaded) => {
      if (active) setLabels(loaded);
    });
    return () => {
      active = false;
    };
  }, []);
  return labels;
}
