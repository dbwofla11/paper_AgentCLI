import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from 'react';
import { startVisual, toApiError, type ApiError } from '../api/client';
import type { JobRecord, TerminalEvent } from '../api/types';
import { useToast } from '../components/Toast';
import { paperHref } from '../hooks/useHashRoute';

/** How the paper's last 시각 요약 job ended without a new summary. */
export type VisualOutcome = { status: 'failed'; message: string } | { status: 'cancelled' } | { status: 'missing' };

/**
 * Start failures about the `visual-designer` role: it changed since the last status check (reload the
 * status once) and the 상태 화면's 논문 역할 구성 explains it.
 */
export const VISUAL_ROLE_ERROR_CODES: Record<string, true> = { designer_unavailable: true, role_config_error: true };

// Session memory shared by every reader mount (design §2.7 "세션 내 메모리"): the last unsuccessful end
// per paper, so leaving and re-entering the reader still shows why the summary is missing, and one
// toast per job, because a remounted stream replays its terminal event.
let outcomes: ReadonlyMap<string, VisualOutcome> = new Map();
const announced = new Set<string>();
const listeners = new Set<() => void>();

function setOutcome(slug: string, outcome: VisualOutcome | null): void {
  const next = new Map(outcomes);
  if (outcome) next.set(slug, outcome);
  else next.delete(slug);
  outcomes = next;
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export interface VisualJob {
  /** The queued or running `review.visual` job this reader follows; null when none. */
  job: JobRecord | null;
  /** A job just ended and the bundle is reloading to show its result. */
  settling: boolean;
  /** POST /api/papers/{slug}/visual is in flight. */
  pending: boolean;
  startError: ApiError | null;
  /** The last job that ended without a new summary in this page session; null after a success. */
  outcome: VisualOutcome | null;
  start: () => void;
  /** Called by the stream that follows `job` when it ends (terminal event, or the job is gone). */
  finish: (job: JobRecord, end: TerminalEvent | 'missing') => void;
}

/**
 * 시각 요약 만들기 in the reader: POST /api/papers/{slug}/visual, then the caller follows the job's
 * event stream and reports its end through `finish`, which reloads the bundle. `bundleJob` (the
 * bundle's `visual.job`) re-attaches a job started earlier or from another tab.
 */
export function useVisualJob(
  slug: string,
  bundleJob: JobRecord | null,
  bundleLoading: boolean,
  reloadBundle: () => void,
  onRoleError: () => void,
): VisualJob {
  const toast = useToast();
  const outcome = useSyncExternalStore(subscribe, () => outcomes.get(slug) ?? null);
  const [started, setStarted] = useState<JobRecord | null>(null);
  const [pending, setPending] = useState(false);
  const [startError, setStartError] = useState<ApiError | null>(null);
  const [settling, setSettling] = useState(false);
  // Jobs whose end this reader has handled: a bundle loaded before the end must not re-attach them.
  const [ended, setEnded] = useState<ReadonlySet<string>>(() => new Set());
  const endedRef = useRef(new Set<string>());
  const sawReload = useRef(false);

  const candidate = started ?? bundleJob;
  const job =
    candidate && (candidate.status === 'queued' || candidate.status === 'running') && !ended.has(candidate.job_id)
      ? candidate
      : null;

  // Settled once the reload that `finish` asked for has come and gone (success or failure).
  useEffect(() => {
    if (!settling) return;
    if (bundleLoading) sawReload.current = true;
    else if (sawReload.current) {
      sawReload.current = false;
      setSettling(false);
    }
  }, [settling, bundleLoading]);

  const finish = useCallback(
    (finished: JobRecord, end: TerminalEvent | 'missing') => {
      const jobId = finished.job_id;
      if (endedRef.current.has(jobId)) return;
      endedRef.current.add(jobId);
      setEnded(new Set(endedRef.current));
      setStarted((current) => (current?.job_id === jobId ? null : current));
      setStartError(null);
      setSettling(true);
      sawReload.current = false;
      reloadBundle();

      const failed = end !== 'missing' && end.type === 'error' ? end.message || '시각 요약 작업이 실패했습니다.' : null;
      if (failed !== null) setOutcome(slug, { status: 'failed', message: failed });
      else if (end === 'missing') setOutcome(slug, { status: 'missing' });
      else if (end.type === 'cancelled') setOutcome(slug, { status: 'cancelled' });
      else setOutcome(slug, null);

      if (announced.has(jobId)) return;
      announced.add(jobId);
      if (failed !== null) {
        toast({ tone: 'danger', title: '시각 요약을 만들지 못했습니다', text: failed.slice(0, 160) });
      } else if (end === 'missing') {
        toast({
          title: '시각 요약 작업을 찾지 못했습니다',
          text: '서버가 다시 시작되어 작업이 끝났는지 알 수 없습니다. 논문 정보를 다시 불러왔습니다.',
        });
      } else if (end.type === 'cancelled') {
        toast({ title: '시각 요약 만들기를 취소했습니다', text: '게시 전에 멈춰 바뀐 파일은 없습니다.' });
      } else {
        toast({
          tone: 'success',
          title: '시각 요약을 만들었습니다',
          action: { label: '시각 요약 보기', href: paperHref(slug, 'visual') },
        });
      }
    },
    [slug, reloadBundle, toast],
  );

  const start = useCallback(() => {
    if (pending || job) return;
    setPending(true);
    setStartError(null);
    startVisual(slug)
      .then(
        (created) => {
          setStarted(created);
          setOutcome(slug, null);
        },
        (failure: unknown) => {
          const apiError = toApiError(failure);
          setStartError(apiError);
          // Another tab started one: the bundle's `visual.job` attaches it.
          if (apiError.code === 'visual_active') reloadBundle();
          if (VISUAL_ROLE_ERROR_CODES[apiError.code]) onRoleError();
        },
      )
      .finally(() => setPending(false));
  }, [slug, pending, job, reloadBundle, onRoleError]);

  return { job, settling, pending, startError, outcome, start, finish };
}
