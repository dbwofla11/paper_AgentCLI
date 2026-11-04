import { useCallback, useEffect, useRef, useSyncExternalStore } from 'react';
import { fetchReviewDetail, requestVerification, toApiError, type ApiError } from '../api/client';
import type { ReviewQueueJob } from '../api/types';
import { useStatus } from '../status';
import { ROLE_ERROR_CODES } from '../verification';

/** GET /api/reviews/{slug} interval while the paper's verification is queued or running (never /api/status). */
const POLL_MS = 3_000;

function isActive(job: ReviewQueueJob): boolean {
  return job.status === 'queued' || job.status === 'running';
}

// Module store per slug, shared by every reader mount so state survives leaving and re-entering
// the reader: the latest known verify job, whether a POST is in flight, and the last start
// failure. `announced` keeps one completion toast per job.
let jobsBySlug: ReadonlyMap<string, ReviewQueueJob> = new Map();
let errorsBySlug: ReadonlyMap<string, ApiError> = new Map();
const inFlight = new Set<string>();
const announced = new Set<string>();
const listeners = new Set<() => void>();

function notify(): void {
  for (const listener of listeners) listener();
}

function putJob(job: ReviewQueueJob): void {
  jobsBySlug = new Map(jobsBySlug).set(job.slug, job);
  notify();
}

function setError(slug: string, error: ApiError | null): void {
  const next = new Map(errorsBySlug);
  if (error) next.set(slug, error);
  else next.delete(slug);
  errorsBySlug = next;
  notify();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/**
 * POST /api/reviews/{slug}/verify at most once at a time per paper: synchronously refused while a
 * POST for the slug is in flight or its known verify job is queued or running.
 */
function startVerification(slug: string, onRoleError: () => void): void {
  const known = jobsBySlug.get(slug);
  if (inFlight.has(slug) || (known && isActive(known))) return;
  inFlight.add(slug);
  setError(slug, null);
  requestVerification(slug)
    .then(
      (job) => putJob(job),
      (failure: unknown) => {
        const apiError = toApiError(failure);
        setError(slug, apiError);
        // The role changed since the last status check: reload it once so the reason shows.
        if (ROLE_ERROR_CODES[apiError.code]) onRoleError();
      },
    )
    .finally(() => {
      inFlight.delete(slug);
      notify();
    });
}

export interface Verification {
  /** Latest known verify job of the paper in this session (seeded from the status queue). */
  job: ReviewQueueJob | null;
  /** POST /api/reviews/{slug}/verify is in flight (from any reader mount). */
  pending: boolean;
  /** Last start failure. */
  error: ApiError | null;
  start: () => void;
}

/**
 * "검증 실행" in the reader: POST /api/reviews/{slug}/verify, then follow the queue job every 3 s
 * until it ends. `onFinished` runs once per job that reaches a terminal status while followed.
 */
export function useVerification(slug: string, onFinished: (job: ReviewQueueJob) => void): Verification {
  const job = useSyncExternalStore(subscribe, () => jobsBySlug.get(slug) ?? null);
  const pending = useSyncExternalStore(subscribe, () => inFlight.has(slug));
  const error = useSyncExternalStore(subscribe, () => errorsBySlug.get(slug) ?? null);
  const { data, refresh } = useStatus();
  const finished = useRef(onFinished);

  useEffect(() => {
    finished.current = onFinished;
  });

  // Seed an active verify job the status queue reported; a job this session already follows wins.
  useEffect(() => {
    const queued = data?.queue.jobs.find((item) => item.slug === slug && item.kind === 'verify' && isActive(item));
    if (queued && !jobsBySlug.has(slug)) putJob(queued);
  }, [data, slug]);

  const jobId = job && isActive(job) ? job.job_id : null;
  useEffect(() => {
    if (!jobId) return;
    const controller = new AbortController();
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      fetchReviewDetail(slug, controller.signal).then(
        (detail) => {
          const next = detail.jobs.find((item) => item.job_id === jobId);
          if (!next || controller.signal.aborted) return;
          putJob(next);
          if (!isActive(next) && !announced.has(next.job_id)) {
            announced.add(next.job_id);
            finished.current(next);
          }
        },
        // A failed poll keeps the last known state; the next tick asks again and the toolbar reports offline.
        () => undefined,
      );
    }, POLL_MS);
    return () => {
      window.clearInterval(timer);
      controller.abort();
    };
  }, [slug, jobId]);

  const start = useCallback(() => startVerification(slug, refresh), [slug, refresh]);

  return { job, pending, error, start };
}
