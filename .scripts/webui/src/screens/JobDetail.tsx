import { useCallback, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent, type Ref } from 'react';
import { cancelJob, fetchJob, isAbortError, toApiError, type ApiError } from '../api/client';
import { VISUAL_JOB_KIND, type JobErrorKind, type JobRecord, type TerminalEvent } from '../api/types';
import { StatusBadge } from '../components/Badges';
import { ErrorNotice } from '../components/ErrorNotice';
import { formatCost, formatDateTime, formatDuration, jobKindLabel } from '../format';
import { paperHref } from '../hooks/useHashRoute';
import {
  useJobStream,
  type StreamInterruption,
  type StreamPhase,
  type StreamRefusal,
  type TranscriptItem,
} from '../hooks/useJobStream';

/** Distance from the bottom (px) within which new text keeps the transcript pinned to the end. */
const STICK_TO_BOTTOM_PX = 48;

const TERMINAL_STATUS: Record<TerminalEvent['type'], JobRecord['status']> = {
  result: 'completed',
  error: 'failed',
  cancelled: 'cancelled',
};

export const PHASE_LABELS: Record<StreamPhase, string> = {
  idle: '스트림 대기',
  connecting: '스트림에 연결하는 중…',
  open: '실시간 수신 중',
  reconnecting: '연결이 끊겨 다시 연결하는 중…',
  waiting: '잠시 후 다시 연결합니다',
  failed: '스트림 연결이 끊겼습니다.',
  ended: '스트림 종료',
};

const REFUSAL_HINTS: Record<StreamRefusal, string> = {
  refused:
    '서버가 스트림 연결을 받지 않았습니다. 동시에 열 수 있는 스트림 수를 넘으면 이렇게 됩니다. 다른 탭에서 연 작업 화면을 닫으면 자리가 납니다.',
  offline: '로컬 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인하세요.',
  missing: '서버에 이 작업이 없습니다. 서버를 다시 시작하면 작업 기록이 사라집니다.',
  unknown: '서버가 스트림 연결을 받지 않았습니다.',
};

/** Classified failures with a more specific next step than the generic retryable hint. */
const ERROR_KIND_HINTS: Partial<Record<JobErrorKind, string>> = {
  usage_limit: '사용량 한도에 도달했습니다. 한도가 풀린 뒤 다시 실행하세요.',
  auth: '로그인이 필요합니다. 상태 화면에서 로그인 명령을 확인하세요.',
  timeout: '시간 제한을 넘었습니다. 다시 실행해 볼 수 있습니다.',
};

function gapRange(from: number, to: number): string | null {
  if (from <= 0 || to < from) return null;
  return from === to ? String(from) : `${from}–${to}`;
}

export function Transcript({ items, busy, placeholder }: { items: TranscriptItem[]; busy: boolean; placeholder: string | null }) {
  const boxRef = useRef<HTMLDivElement>(null);
  const stickRef = useRef(true);

  useLayoutEffect(() => {
    const box = boxRef.current;
    if (box && stickRef.current) box.scrollTop = box.scrollHeight;
  }, [items]);

  const trackScroll = () => {
    const box = boxRef.current;
    if (box) stickRef.current = box.scrollHeight - box.scrollTop - box.clientHeight < STICK_TO_BOTTOM_PX;
  };

  return (
    <div
      className="transcript"
      ref={boxRef}
      onScroll={trackScroll}
      tabIndex={0}
      role="region"
      aria-label="에이전트 응답 스트림"
    >
      {placeholder ? <p className="transcript-placeholder">{placeholder}</p> : null}
      <div className="transcript-log" role="log" aria-live="polite" aria-busy={busy}>
        {items.map((item) => {
          switch (item.kind) {
            case 'text':
              return (
                <p className="stream-text" data-open={item.open} key={item.key}>
                  {item.text}
                </p>
              );
            case 'tool':
              return (
                <p className="stream-row" key={item.key}>
                  <span className="badge" data-tone="active">
                    도구
                  </span>
                  <code translate="no">{item.name}</code>
                  {item.summary ? <span className="stream-row-summary">{item.summary}</span> : null}
                </p>
              );
            case 'retry':
              return (
                <p className="stream-row" key={item.key}>
                  <span className="badge" data-tone="waiting">
                    {item.next ? '후보 전환' : '재시도'}
                  </span>
                  {item.next ? (
                    <span>
                      {item.reason === 'usage_limit' ? '사용량 한도 · ' : ''}다음 후보로 전환{' '}
                      <code translate="no">{item.next}</code>
                    </span>
                  ) : (
                    <span>
                      <span className="num">{item.attempt}</span>번째 재시도
                      {item.delayMs != null ? ` · ${formatDuration(item.delayMs)} 뒤` : ''}
                    </span>
                  )}
                </p>
              );
            case 'gap': {
              const range = gapRange(item.missedFrom, item.missedTo);
              return (
                <p className="stream-row" key={item.key}>
                  <span className="badge" data-tone="danger">
                    누락
                  </span>
                  <span>
                    일부 스트림 기록이 누락됨
                    {range ? (
                      <>
                        {' · 이벤트 '}
                        <span className="num">{range}</span>
                      </>
                    ) : null}
                  </span>
                  <span className="stream-row-summary">
                    연결이 늦어 서버가 보관하지 않은 이벤트입니다. 작업이 완료되면 최종 응답 전체를 보여 줍니다.
                  </span>
                </p>
              );
            }
            case 'empty':
              return (
                <p className="stream-row" key={item.key}>
                  <span className="badge" data-tone="neutral">
                    빈 응답
                  </span>
                  <span>응답 본문이 비어 있습니다.</span>
                </p>
              );
          }
        })}
      </div>
    </div>
  );
}

function TerminalSummary({ terminal }: { terminal: TerminalEvent }) {
  switch (terminal.type) {
    case 'result': {
      const cost = formatCost(terminal.cost_usd);
      const duration = formatDuration(terminal.duration_ms);
      return (
        <div className="terminal" data-tone="success">
          <div className="terminal-head">
            <StatusBadge status="completed" />
            <span>응답을 모두 받았습니다.</span>
          </div>
          <dl className="terminal-facts">
            <div>
              <dt>비용</dt>
              <dd className="num">{cost ?? '정보 없음'}</dd>
            </div>
            <div>
              <dt>소요 시간</dt>
              <dd className="num">{duration ?? '정보 없음'}</dd>
            </div>
          </dl>
        </div>
      );
    }
    case 'error':
      return (
        <div className="terminal" data-tone="danger">
          <div className="terminal-head">
            <StatusBadge status="failed" />
            <span>
              {(terminal.kind ? ERROR_KIND_HINTS[terminal.kind] : undefined) ??
                (terminal.retryable
                  ? '일시적인 오류입니다. 다시 실행해 볼 수 있습니다.'
                  : '다시 실행하기 전에 상태 화면에서 에이전트 연결을 확인하세요.')}
            </span>
          </div>
          <pre className="terminal-message">{terminal.message || '오류 메시지가 없습니다.'}</pre>
        </div>
      );
    case 'cancelled':
      return (
        <div className="terminal" data-tone="neutral">
          <div className="terminal-head">
            <StatusBadge status="cancelled" />
            <span>작업을 취소했습니다. 그때까지 받은 응답만 남아 있습니다.</span>
          </div>
        </div>
      );
  }
}

interface StreamNoticeProps {
  phase: StreamPhase;
  interruption: StreamInterruption | null;
  onReconnect: () => void;
}

/** Shown while a refused stream waits for its automatic reconnect, and after the hook gives up. */
export function StreamNotice({ phase, interruption, onReconnect }: StreamNoticeProps) {
  if (phase !== 'waiting' && phase !== 'failed') return null;
  const retryInMs = phase === 'waiting' ? (interruption?.retryInMs ?? null) : null;
  let detail: string | null = null;
  if (retryInMs !== null && interruption) {
    const seconds = Math.max(1, Math.round(retryInMs / 1000));
    detail = `${seconds}초 뒤 자동으로 다시 연결합니다 (자동 재연결 ${interruption.attempt}/${interruption.maxAttempts}).`;
  } else if (interruption && interruption.reason !== 'missing') {
    detail = `자동 재연결 ${interruption.maxAttempts}번을 모두 시도했습니다. 아래 버튼으로 다시 연결하세요.`;
  }
  return (
    <div className="notice" data-tone={retryInMs === null ? 'danger' : undefined}>
      <p className="notice-title">{retryInMs === null ? '스트림에 연결하지 못했습니다.' : '스트림 연결이 거절되었습니다.'}</p>
      <p>{interruption ? REFUSAL_HINTS[interruption.reason] : '서버와의 스트림 연결이 끊겼습니다.'}</p>
      {detail ? <p className="notice-detail">{detail}</p> : null}
      <div className="notice-actions">
        <button type="button" className="btn btn-secondary btn-small" onClick={onReconnect}>
          {retryInMs === null ? '스트림 다시 연결' : '지금 다시 연결'}
        </button>
      </div>
    </div>
  );
}

type CancelState = 'idle' | 'confirm' | 'pending';

interface JobDetailProps {
  jobId: string;
  /** Record already in the list, shown until the fresh GET /api/jobs/{id} arrives. */
  initialRecord: JobRecord | null;
  /** Focus target when the selection changes. */
  sectionRef: Ref<HTMLElement>;
  /** Called when the job's state changed (terminal event, cancel) so the list refreshes. */
  onChanged: () => void;
}

export function JobDetail({ jobId, initialRecord, sectionRef, onChanged }: JobDetailProps) {
  const [record, setRecord] = useState<JobRecord | null>(initialRecord);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [cancelState, setCancelState] = useState<CancelState>('idle');
  const [cancelMessage, setCancelMessage] = useState<string | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const keepRunningRef = useRef<HTMLButtonElement>(null);

  const loadRecord = useCallback(
    async (signal?: AbortSignal) => {
      try {
        setRecord(await fetchJob(jobId, signal));
        setLoadError(null);
      } catch (error) {
        if (!isAbortError(error)) setLoadError(toApiError(error));
      }
    },
    [jobId],
  );

  useEffect(() => {
    const controller = new AbortController();
    void loadRecord(controller.signal);
    return () => controller.abort();
  }, [loadRecord]);

  const notFound = loadError?.status === 404;
  const stream = useJobStream(record && !notFound ? jobId : null, {
    onTerminal: () => {
      void loadRecord();
      onChanged();
    },
    // A 404 here switches this panel to the "not found" view.
    onMissing: () => void loadRecord(),
  });

  useEffect(() => {
    if (cancelState === 'confirm') keepRunningRef.current?.focus();
  }, [cancelState]);

  const status = stream.terminal ? TERMINAL_STATUS[stream.terminal.type] : record?.status;
  const canCancel = !stream.terminal && (status === 'queued' || status === 'running');

  const confirmCancel = async () => {
    setCancelState('pending');
    setCancelMessage(null);
    try {
      setRecord(await cancelJob(jobId));
      setCancelMessage('취소를 요청했습니다. 에이전트가 멈추면 스트림이 끝납니다.');
      onChanged();
    } catch (error) {
      const apiError = toApiError(error);
      setCancelMessage(
        apiError.code === 'already_finished' ? '이미 끝난 작업이라 취소하지 않았습니다.' : `취소하지 못했습니다: ${apiError.message}`,
      );
      void loadRecord();
    } finally {
      setCancelState('idle');
      headingRef.current?.focus();
    }
  };

  const dismissConfirmOnEscape = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') setCancelState('idle');
  };

  if (notFound) {
    return (
      <section className="panel job-detail" ref={sectionRef} tabIndex={-1} aria-labelledby="job-missing-title">
        <h2 id="job-missing-title">작업을 찾을 수 없습니다</h2>
        <p>
          작업 기록은 서버 메모리에만 있어 서버를 다시 시작하면 사라집니다. 목록에서 다른 작업을 고르거나 새 작업을
          실행하세요.
        </p>
        <p className="meta">
          <code translate="no">{jobId}</code>
        </p>
      </section>
    );
  }

  if (!record) {
    return (
      <section className="panel job-detail" ref={sectionRef} tabIndex={-1} aria-label="작업 상세">
        {loadError ? (
          <ErrorNotice error={loadError} title="작업 정보를 불러오지 못했습니다." onRetry={() => void loadRecord()} />
        ) : (
          <p className="loading-text" role="status">
            작업 정보를 불러오는 중…
          </p>
        )}
      </section>
    );
  }

  const placeholder =
    stream.items.length > 0 || stream.terminal
      ? null
      : stream.phase === 'waiting'
        ? '다시 연결되면 응답을 이어서 보여 줍니다.'
        : stream.phase === 'failed'
          ? '스트림에 연결되지 않아 아직 받은 응답이 없습니다.'
          : status === 'queued'
            ? '실행 순서를 기다리는 중입니다…'
            : stream.phase === 'open'
              ? '에이전트 응답을 기다리는 중…'
              : '스트림에 연결하는 중…';
  const streaming = !stream.terminal && (stream.phase === 'open' || stream.phase === 'connecting');
  const agent = stream.start?.agent || record.agent;

  return (
    <section className="panel job-detail" ref={sectionRef} tabIndex={-1} aria-labelledby="job-detail-title">
      <div className="job-detail-head">
        <div className="job-detail-title">
          <p className="eyebrow">
            Job <code translate="no">{jobId}</code>
          </p>
          <h2 id="job-detail-title" ref={headingRef} tabIndex={-1}>
            {jobKindLabel(record.kind)}
          </h2>
        </div>
        {status ? <StatusBadge status={status} /> : null}
      </div>

      <dl className="fact-grid">
        {record.role ? (
          <div>
            <dt>역할</dt>
            <dd translate="no">{record.role}</dd>
          </div>
        ) : null}
        {record.slug ? (
          <div>
            <dt>논문</dt>
            <dd>
              <a href={paperHref(record.slug, record.kind === VISUAL_JOB_KIND ? 'visual' : 'pdf')}>
                <code translate="no">{record.slug}</code>
              </a>
            </dd>
          </div>
        ) : null}
        <div>
          <dt>에이전트</dt>
          <dd translate="no">{agent ?? (record.role ? '없음' : '기본 에이전트')}</dd>
        </div>
        <div>
          <dt>모델</dt>
          <dd translate="no">{stream.start?.model ?? '—'}</dd>
        </div>
        <div>
          <dt>요청</dt>
          <dd className="num">{formatDateTime(record.created_at)}</dd>
        </div>
        <div>
          <dt>시작</dt>
          <dd className="num">{formatDateTime(record.started_at)}</dd>
        </div>
        <div>
          <dt>종료</dt>
          <dd className="num">{formatDateTime(record.ended_at)}</dd>
        </div>
      </dl>

      {canCancel || cancelState === 'pending' ? (
        cancelState === 'confirm' ? (
          <div className="cancel-control" role="group" aria-labelledby="cancel-question" onKeyDown={dismissConfirmOnEscape}>
            <p id="cancel-question">작업을 멈출까요? 지금까지 받은 응답은 남지만 작업은 이어지지 않습니다.</p>
            <button type="button" className="btn btn-danger btn-small" onClick={confirmCancel}>
              작업 취소
            </button>
            <button
              type="button"
              className="btn btn-secondary btn-small"
              ref={keepRunningRef}
              onClick={() => setCancelState('idle')}
            >
              계속 실행
            </button>
          </div>
        ) : (
          <div className="cancel-control">
            <button
              type="button"
              className="btn btn-secondary btn-small"
              onClick={() => setCancelState('confirm')}
              disabled={cancelState === 'pending'}
              aria-busy={cancelState === 'pending'}
            >
              {cancelState === 'pending' ? '취소 요청 중…' : '작업 취소'}
            </button>
          </div>
        )
      ) : null}
      <p className="cancel-feedback" role="status">
        {cancelMessage ?? ''}
      </p>

      <div className="stream-bar">
        <p className="stream-phase" data-phase={stream.phase}>
          <span className="dot" aria-hidden="true" />
          {PHASE_LABELS[stream.phase]}
        </p>
        {stream.lastSeq > 0 ? (
          <span className="meta">
            이벤트 <span className="num">{stream.lastSeq}</span>
          </span>
        ) : null}
      </div>

      <div className="stream-notice-region" role="status">
        <StreamNotice phase={stream.phase} interruption={stream.interruption} onReconnect={stream.reconnect} />
      </div>

      <Transcript items={stream.items} busy={streaming} placeholder={placeholder} />

      <div className="terminal-region" role="status" aria-atomic="true">
        {stream.terminal ? <TerminalSummary terminal={stream.terminal} /> : null}
      </div>

      {stream.phase === 'failed' && record.error ? (
        <p className="notice" data-tone="danger">
          {record.error}
        </p>
      ) : null}
    </section>
  );
}
