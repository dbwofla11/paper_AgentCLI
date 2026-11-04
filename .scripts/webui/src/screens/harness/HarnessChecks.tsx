import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ArrowRight, Play, Square } from 'lucide-react';
import { cancelJob, fetchJobs, isAbortError, startHarnessCheck, toApiError, type ApiError } from '../../api/client';
import {
  HARNESS_CHECK_KINDS,
  type HarnessCheck,
  type HarnessCheckName,
  type JobRecord,
  type JobStatus,
  type TerminalEvent,
} from '../../api/types';
import { CopyButton } from '../../components/CopyButton';
import { ErrorNotice } from '../../components/ErrorNotice';
import { formatDateTime, formatDuration } from '../../format';
import { jobHref } from '../../hooks/useHashRoute';
import { useJobStream } from '../../hooks/useJobStream';

type CheckStatus = 'idle' | JobStatus;

const TERMINAL_STATUS: Record<TerminalEvent['type'], JobStatus> = {
  result: 'completed',
  error: 'failed',
  cancelled: 'cancelled',
};

const STATUS_BADGES: Record<CheckStatus, { label: string; tone: string }> = {
  idle: { label: '실행 전', tone: 'neutral' },
  queued: { label: '대기 중', tone: 'waiting' },
  running: { label: '실행 중', tone: 'active' },
  completed: { label: '통과', tone: 'success' },
  failed: { label: '실패', tone: 'danger' },
  cancelled: { label: '취소됨', tone: 'neutral' },
};

const CHECK_NOTES: Record<HarnessCheckName, string> = {
  verify: '정본 파일·스킬 연결·라우팅 참조를 검사합니다. 보통 몇 초 안에 끝납니다.',
  tests: '하네스 테스트 전체를 실행합니다. 몇 분 걸리고 CPU를 많이 쓰며, 실행 중에는 작업 자리 하나를 차지합니다.',
};

const START_ERRORS: Record<string, string> = {
  check_active: '다른 하네스 검사가 이미 실행 중입니다. 끝난 뒤 다시 실행하세요.',
  shutting_down: '서버가 종료되는 중이라 검사를 시작하지 않았습니다.',
  bad_request: '서버가 이 검사를 알지 못합니다. 서버와 화면이 같은 버전인지 확인하세요.',
};

/** Distance from the bottom (px) within which new output keeps the transcript pinned to the end. */
const STICK_TO_BOTTOM_PX = 48;

function isActive(status: CheckStatus): boolean {
  return status === 'queued' || status === 'running';
}

function TerminalLine({ terminal }: { terminal: TerminalEvent }) {
  switch (terminal.type) {
    case 'result': {
      const duration = formatDuration(terminal.duration_ms);
      return <p className="check-terminal" data-tone="success">검사를 통과했습니다.{duration ? ` 소요 ${duration}` : ''}</p>;
    }
    case 'error':
      return (
        <div className="check-terminal" data-tone="danger">
          <p>{terminal.kind === 'timeout' ? '시간 제한을 넘어 검사를 멈췄습니다.' : '검사가 실패했습니다.'}</p>
          {terminal.message ? <pre className="check-message">{terminal.message}</pre> : null}
        </div>
      );
    case 'cancelled':
      return <p className="check-terminal" data-tone="neutral">검사를 중지했습니다. 그때까지의 출력만 남아 있습니다.</p>;
  }
}

interface CheckCardProps {
  check: HarnessCheck;
  job: JobRecord | null;
  /** Another harness check is queued or running (the server runs one at a time). */
  otherActive: boolean;
  onStarted: (job: JobRecord) => void;
  onStatus: (check: HarnessCheckName, status: CheckStatus) => void;
  /** Re-read the job list (e.g. after 409 check_active) so the running check is shown. */
  onStale: () => void;
}

function CheckCard({ check, job, otherActive, onStarted, onStatus, onStale }: CheckCardProps) {
  const [starting, setStarting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const boxRef = useRef<HTMLPreElement>(null);
  const stickRef = useRef(true);
  const stream = useJobStream(job?.job_id ?? null);
  const status: CheckStatus = !job ? 'idle' : stream.terminal ? TERMINAL_STATUS[stream.terminal.type] : job.status;
  const active = isActive(status);
  const badge = STATUS_BADGES[status];
  const output = stream.items.map((item) => (item.kind === 'text' ? item.text : '')).join('');
  const gaps = stream.items.some((item) => item.kind === 'gap');

  useEffect(() => onStatus(check.check, status), [check.check, status, onStatus]);

  useLayoutEffect(() => {
    const box = boxRef.current;
    if (box && stickRef.current) box.scrollTop = box.scrollHeight;
  }, [output]);

  const run = async () => {
    setStarting(true);
    setError(null);
    try {
      onStarted(await startHarnessCheck(check.check));
    } catch (failure) {
      const apiError = toApiError(failure);
      setError(apiError);
      if (apiError.code === 'check_active') onStale();
    } finally {
      setStarting(false);
    }
  };

  const stop = async () => {
    if (!job) return;
    setStopping(true);
    try {
      await cancelJob(job.job_id);
    } catch (failure) {
      const apiError = toApiError(failure);
      if (apiError.code !== 'already_finished') setError(apiError);
    } finally {
      setStopping(false);
    }
  };

  const blocked = otherActive && !active ? '다른 검사가 실행 중입니다.' : null;
  const titleId = `check-${check.check}-title`;
  return (
    <article className="check-card card" data-check={check.check} aria-labelledby={titleId}>
      <div className="check-head">
        <h3 id={titleId}>{check.label}</h3>
        <span className="badge" data-tone={badge.tone} data-state={status}>
          {badge.label}
        </span>
      </div>
      <p className="field-hint">{CHECK_NOTES[check.check] ?? null}</p>
      <div className="command-row">
        <code className="command" translate="no">
          {check.command}
        </code>
        <CopyButton text={check.command} label={`${check.label} 명령 복사`} />
      </div>
      <div className="check-actions">
        {active ? (
          <button type="button" className="btn btn-secondary btn-small" onClick={stop} disabled={stopping} aria-busy={stopping}>
            <Square />
            {stopping ? '중지 요청 중…' : '중지'}
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-primary btn-small check-run"
            onClick={run}
            disabled={starting || blocked !== null}
            aria-busy={starting}
            aria-describedby={blocked ? `${titleId}-blocked` : undefined}
          >
            <Play />
            {starting ? '요청하는 중…' : '실행'}
          </button>
        )}
        {job ? (
          <a className="btn btn-text btn-small" href={jobHref(job.job_id)}>
            작업 화면에서 보기
            <ArrowRight />
          </a>
        ) : null}
        {blocked ? (
          <span className="meta" id={`${titleId}-blocked`}>
            {blocked}
          </span>
        ) : null}
      </div>
      {error ? <ErrorNotice error={error} title={START_ERRORS[error.code] ?? '검사를 시작하지 못했습니다.'} /> : null}
      {active ? <span className="ai-progress" aria-hidden="true" /> : null}
      {job ? (
        <>
          <p className="caption">
            {active ? '실행 중' : '마지막 실행'} · {formatDateTime(job.started_at ?? job.created_at)}
          </p>
          <pre
            className="check-transcript"
            ref={boxRef}
            tabIndex={0}
            role="log"
            aria-label={`${check.label} 출력`}
            aria-live={active ? 'polite' : 'off'}
            onScroll={() => {
              const box = boxRef.current;
              if (box) stickRef.current = box.scrollHeight - box.scrollTop - box.clientHeight < STICK_TO_BOTTOM_PX;
            }}
          >
            {output || (active ? '출력을 기다리는 중…' : stream.terminal ? '출력 없음' : '출력을 불러오는 중…')}
          </pre>
          {gaps ? <p className="caption">연결이 늦어 일부 출력이 빠졌습니다. 끝나면 전체 출력을 보여 줍니다.</p> : null}
          <div role="status">{stream.terminal ? <TerminalLine terminal={stream.terminal} /> : null}</div>
          {stream.phase === 'failed' ? (
            <p className="caption check-stream-failed">
              출력 스트림에 연결하지 못했습니다.{' '}
              <button type="button" className="btn btn-text btn-small" onClick={stream.reconnect}>
                다시 연결
              </button>
            </p>
          ) : null}
        </>
      ) : null}
    </article>
  );
}

/** 검사: the two fixed server-side checks. The last job of each kind is restored from GET /api/jobs. */
export function HarnessChecks({ checks, reloadToken }: { checks: HarnessCheck[]; reloadToken: number }) {
  const [jobs, setJobs] = useState<Partial<Record<HarnessCheckName, JobRecord>>>({});
  const [statuses, setStatuses] = useState<Partial<Record<HarnessCheckName, CheckStatus>>>({});
  const [restoreError, setRestoreError] = useState<ApiError | null>(null);
  // Bumped by every restore request and every started check: a restore answer applies only while
  // its generation is current, so a slow GET /api/jobs never replaces a job started after it was sent.
  const generation = useRef(0);

  const restore = useCallback(async (signal?: AbortSignal) => {
    generation.current += 1;
    const requested = generation.current;
    try {
      const list = await fetchJobs(signal); // newest first
      if (requested !== generation.current) return;
      const latest: Partial<Record<HarnessCheckName, JobRecord>> = {};
      for (const name of Object.keys(HARNESS_CHECK_KINDS) as HarnessCheckName[]) {
        const job = list.find((record) => record.kind === HARNESS_CHECK_KINDS[name]);
        if (job) latest[name] = job;
      }
      setJobs(latest);
      setRestoreError(null);
    } catch (error) {
      if (!isAbortError(error) && requested === generation.current) setRestoreError(toApiError(error));
    }
  }, []);

  const onStarted = useCallback((check: HarnessCheckName, job: JobRecord) => {
    generation.current += 1;
    setJobs((current) => ({ ...current, [check]: job }));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void restore(controller.signal);
    return () => controller.abort();
  }, [restore, reloadToken]);

  const onStatus = useCallback((check: HarnessCheckName, status: CheckStatus) => {
    setStatuses((current) => (current[check] === status ? current : { ...current, [check]: status }));
  }, []);

  return (
    <div className="check-grid">
      {restoreError && restoreError.code !== 'offline' ? (
        <ErrorNotice error={restoreError} title="이전 검사 기록을 불러오지 못했습니다." onRetry={() => void restore()} />
      ) : null}
      {checks.map((check) => (
        <CheckCard
          key={check.check}
          check={check}
          job={jobs[check.check] ?? null}
          otherActive={checks.some((other) => other.check !== check.check && isActive(statuses[other.check] ?? 'idle'))}
          onStarted={(job) => onStarted(check.check, job)}
          onStatus={onStatus}
          onStale={() => void restore()}
        />
      ))}
    </div>
  );
}
