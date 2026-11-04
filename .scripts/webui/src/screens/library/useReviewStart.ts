import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { fetchReviewDetail, startReview, toApiError, type ApiError } from '../../api/client';
import type { ReviewQueueJob } from '../../api/types';

/** GET /api/reviews/{slug} interval while a review of that paper is queued or running (never /api/status). */
const POLL_MS = 3_000;

function isActive(job: ReviewQueueJob): boolean {
  return job.status === 'queued' || job.status === 'running';
}

// Module store (latest known queue job per slug) so a running review keeps its progress line
// across route changes; `announced` keeps one completion toast per job.
let jobsBySlug: ReadonlyMap<string, ReviewQueueJob> = new Map();
const announced = new Set<string>();
const listeners = new Set<() => void>();

function putJob(job: ReviewQueueJob): void {
  jobsBySlug = new Map(jobsBySlug).set(job.slug, job);
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Newest job of the paper; the one with `jobId` when it is listed. */
function pickJob(jobs: ReviewQueueJob[], jobId: string): ReviewQueueJob | null {
  const exact = jobs.find((job) => job.job_id === jobId);
  if (exact) return exact;
  return jobs.reduce<ReviewQueueJob | null>(
    (newest, job) => (!newest || (job.created_at ?? '') > (newest.created_at ?? '') ? job : newest),
    null,
  );
}

export interface ReviewStart {
  /** Latest known queue job of the paper in this session (seeded from the status queue). */
  jobs: ReadonlyMap<string, ReviewQueueJob>;
  /** Slugs whose POST /api/reviews is in flight. */
  pending: ReadonlySet<string>;
  /** Last start failure per slug. */
  errors: ReadonlyMap<string, ApiError>;
  start: (slug: string) => void;
}

interface Options {
  /** Review-queue entries from the shared GET /api/status result (fetched once, not polled). */
  queue: ReviewQueueJob[] | undefined;
  /** A followed job reached a terminal status; called once per job. */
  onFinished: (job: ReviewQueueJob) => void;
  /** The server answered 409 review_complete: the list is stale. */
  onStale: () => void;
}

/** "리뷰 시작" on library cards: POST /api/reviews, then follow the queue job until it ends. */
export function useReviewStart({ queue, onFinished, onStale }: Options): ReviewStart {
  const jobs = useSyncExternalStore(subscribe, () => jobsBySlug);
  const [pending, setPending] = useState<ReadonlySet<string>>(new Set());
  const [errors, setErrors] = useState<ReadonlyMap<string, ApiError>>(new Map());
  const handlers = useRef({ onFinished, onStale });

  useEffect(() => {
    handlers.current = { onFinished, onStale };
  });

  // Seed active jobs the status queue reported; a job this session already follows wins.
  useEffect(() => {
    for (const job of queue ?? []) {
      if (isActive(job) && job.kind !== 'verify' && !jobsBySlug.has(job.slug)) putJob(job);
    }
  }, [queue]);

  const activeKey = [...jobs.values()]
    .filter(isActive)
    .map((job) => `${job.slug}\u0000${job.job_id}`)
    .sort()
    .join('\u0001');

  useEffect(() => {
    if (!activeKey) return;
    const followed = activeKey.split('\u0001').map((entry) => entry.split('\u0000') as [string, string]);
    const controller = new AbortController();
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'visible') return;
      for (const [slug, jobId] of followed) {
        fetchReviewDetail(slug, controller.signal).then(
          (detail) => {
            const job = pickJob(detail.jobs, jobId);
            if (!job || controller.signal.aborted) return;
            putJob(job);
            if (!isActive(job) && !announced.has(job.job_id)) {
              announced.add(job.job_id);
              handlers.current.onFinished(job);
            }
          },
          // A failed poll keeps the last known state; the next tick asks again and the header reports offline.
          () => undefined,
        );
      }
    }, POLL_MS);
    return () => {
      window.clearInterval(timer);
      controller.abort();
    };
  }, [activeKey]);

  const start = useCallback((slug: string) => {
    setPending((current) => new Set(current).add(slug));
    setErrors((current) => {
      const next = new Map(current);
      next.delete(slug);
      return next;
    });
    startReview(slug).then(
      (job) => putJob(job),
      (error: unknown) => {
        const apiError = toApiError(error);
        setErrors((current) => new Map(current).set(slug, apiError));
        if (apiError.code === 'review_complete') handlers.current.onStale();
      },
    ).finally(() => {
      setPending((current) => {
        const next = new Set(current);
        next.delete(slug);
        return next;
      });
    });
  }, []);

  return { jobs, pending, errors, start };
}
