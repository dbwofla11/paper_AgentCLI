import { useEffect, useId, useRef, useState, type KeyboardEvent, type Ref, type RefObject } from 'react';
import {
  ArrowRight as IconArrow,
  ChartNoAxesCombined as IconVisual,
  CircleAlert as IconAlert,
  ExternalLink as IconExternal,
  RefreshCw as IconRedo,
  Square as IconStop,
} from 'lucide-react';
import { cancelJob, toApiError, type ApiError } from '../api/client';
import { VISUAL_PAGE_MESSAGE, type JobRecord, type PaperVisual } from '../api/types';
import { formatDateTime } from '../format';
import { STATUS_HREF, jobHref } from '../hooks/useHashRoute';
import { useJobStream, type TranscriptItem } from '../hooks/useJobStream';
import { StreamNotice } from '../screens/JobDetail';
import { readerViewIds } from './ReaderToolbar';
import { VISUAL_ROLE_ERROR_CODES, type VisualJob } from './useVisualJob';

/** Korean guidance per POST /api/papers/{slug}/visual error code (.scripts/docs/webui-api.md). */
const START_ERRORS: Record<string, string> = {
  review_missing: '리뷰 문서가 없어 시각 요약을 만들 수 없습니다. 먼저 논문 리뷰를 실행하세요.',
  visual_active: '이 논문의 시각 요약을 이미 만들고 있습니다. 진행 상황을 다시 불러옵니다.',
  review_active: '이 논문의 리뷰나 검증이 진행 중이라 시작하지 않았습니다. 끝난 뒤 다시 만드세요.',
  not_found: '논문 기록을 찾을 수 없습니다.',
  shutting_down: '서버가 종료되는 중이라 시작하지 않았습니다.',
};

/** Codes whose server message names the specific problem; it follows the Korean headline. */
const DETAILED_ERRORS: Record<string, string> = {
  bad_request: '요청이 서버 기준에 맞지 않습니다.',
  role_config_error: 'omp 설정을 읽지 못해 시각 요약을 시작하지 않았습니다.',
  designer_unavailable: '시각 요약 역할(visual-designer)에 준비된 실행기가 없어 시작하지 않았습니다.',
  visual_unavailable: 'visual-explainer 스킬이나 node를 찾지 못해 시각 요약을 만들 수 없습니다.',
};

const SOURCE_LABELS: Record<NonNullable<PaperVisual['source']>, string> = {
  review: '리뷰와 함께 생성',
  'visual-job': '리더에서 생성',
};

function startErrorText(error: ApiError): string {
  const known = START_ERRORS[error.code];
  if (known) return known;
  const detailed = DETAILED_ERRORS[error.code];
  return detailed ? `${detailed} ${error.message}` : `시각 요약을 시작하지 못했습니다: ${error.message}`;
}

/** Why 시각 요약 만들기 cannot start now; `status` adds a link to the 상태 화면. */
export interface VisualBlock {
  reason: string;
  status: boolean;
}

type CancelState = 'idle' | 'confirm' | 'pending';

interface VisualProgressProps {
  job: JobRecord;
  /** A summary is already shown: canceling keeps it. */
  hasVisual: boolean;
  onEnd: VisualJob['finish'];
  containerRef: Ref<HTMLDivElement>;
}

/** The queued or running `review.visual` job on its event stream, with 만들기 취소 and its 작업 화면 link. */
function VisualProgress({ job, hasVisual, onEnd, containerRef }: VisualProgressProps) {
  const headingId = useId();
  const jobId = job.job_id;
  const stream = useJobStream(jobId, {
    onTerminal: (event) => onEnd(job, event),
    onMissing: () => onEnd(job, 'missing'),
  });
  const [cancelState, setCancelState] = useState<CancelState>('idle');
  const [cancelMessage, setCancelMessage] = useState<string | null>(null);
  /** The server began publishing the result (409 `publishing`): cancel can no longer stop it, the stream still ends it. */
  const [publishing, setPublishing] = useState(false);
  const keepRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const previousCancel = useRef<CancelState>('idle');

  // The question takes focus on its safe choice; closing it (or the request ending) returns focus to 만들기 취소.
  useEffect(() => {
    const previous = previousCancel.current;
    previousCancel.current = cancelState;
    if (cancelState === 'confirm') keepRef.current?.focus();
    else if (cancelState === 'idle' && previous !== 'idle') cancelRef.current?.focus();
  }, [cancelState]);

  const running = stream.start !== null || job.status === 'running';
  // The latest tool call (e.g. `node …/render.mjs`) tells what the agent is doing right now.
  const step = stream.items.findLast((item): item is Extract<TranscriptItem, { kind: 'tool' }> => item.kind === 'tool');

  const confirmCancel = async () => {
    setCancelState('pending');
    setCancelMessage(null);
    try {
      await cancelJob(jobId);
      setCancelMessage('취소를 요청했습니다. 에이전트가 멈추면 이 자리에 반영됩니다.');
    } catch (caught) {
      const apiError = toApiError(caught);
      if (apiError.code === 'publishing') setPublishing(true);
      setCancelMessage(
        apiError.code === 'publishing'
          ? '이미 게시를 시작해 취소할 수 없습니다. 곧 완료됩니다.'
          : apiError.code === 'already_finished'
            ? '이미 끝난 작업이라 취소하지 않았습니다.'
            : `취소하지 못했습니다: ${apiError.message}`,
      );
    } finally {
      setCancelState('idle');
    }
  };

  const dismissOnEscape = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Escape') return;
    event.stopPropagation();
    setCancelState('idle');
  };

  return (
    <div className="visual-progress" ref={containerRef} tabIndex={-1} role="group" aria-labelledby={headingId}>
      <span className="ai-progress" aria-hidden="true" />
      <p className="visual-progress-title" id={headingId} role="status">
        {running ? '시각 요약을 만드는 중…' : '시각 요약 작업이 실행 순서를 기다리는 중…'}
      </p>
      <p className="field-hint">
        에이전트가 리뷰 문서만 읽고 그림을 그린 뒤 렌더 검사를 합니다. 최대 15분 걸리며, 그동안 원문 PDF를 계속 읽을 수
        있습니다.
      </p>
      {step ? (
        <p className="caption visual-progress-step">
          <span translate="no">{step.name}</span> {step.summary}
        </p>
      ) : null}
      <StreamNotice phase={stream.phase} interruption={stream.interruption} onReconnect={stream.reconnect} />
      {cancelState === 'confirm' ? (
        <div className="cancel-control" role="group" aria-labelledby={`${headingId}-cancel`} onKeyDown={dismissOnEscape}>
          <p id={`${headingId}-cancel`}>
            {hasVisual
              ? '시각 요약 만들기를 멈출까요? 지금 보이는 시각 요약은 그대로 남습니다.'
              : '시각 요약 만들기를 멈출까요? 만들던 내용은 저장하지 않습니다.'}
          </p>
          <button type="button" className="btn btn-danger btn-small" onClick={() => void confirmCancel()}>
            만들기 취소
          </button>
          <button type="button" className="btn btn-secondary btn-small" ref={keepRef} onClick={() => setCancelState('idle')}>
            계속 만들기
          </button>
        </div>
      ) : (
        <div className="cancel-control">
          {/* After 409 `publishing`, aria-disabled, not disabled: focus returns here and the reason stays described. */}
          <button
            type="button"
            ref={cancelRef}
            className="btn btn-secondary btn-small"
            onClick={() => {
              if (!publishing) setCancelState('confirm');
            }}
            disabled={cancelState === 'pending'}
            aria-disabled={publishing || undefined}
            aria-describedby={publishing ? `${headingId}-cancel-feedback` : undefined}
            aria-busy={cancelState === 'pending'}
          >
            <IconStop />
            {cancelState === 'pending' ? '취소 요청 중…' : '만들기 취소'}
          </button>
          <a className="btn btn-text btn-small" href={jobHref(jobId)}>
            작업 화면에서 보기
            <IconArrow />
          </a>
        </div>
      )}
      <p className="cancel-feedback" id={`${headingId}-cancel-feedback`} role="status">
        {cancelMessage ?? ''}
      </p>
    </div>
  );
}

interface VisualPaneProps {
  title: string;
  visual: PaperVisual;
  /** The 시각 요약 tab is selected. The pane stays mounted (and its job followed) while the PDF shows. */
  shown: boolean;
  task: VisualJob;
  /** Why 시각 요약 만들기 cannot start now; null when it can. */
  blocked: VisualBlock | null;
  /** PDF pages a `p.N` link may open (0 while the PDF is missing or loading). */
  pageCount: number;
  onOpenPage: (page: number) => void;
  paneRef: RefObject<HTMLDivElement | null>;
}

/**
 * The left pane's 시각 요약 (decisions V8–V15): the server's sandboxed page in a fixed-height iframe that
 * scrolls inside, or why there is none and 시각 요약 만들기. States: absent, generating (the job's stream
 * and 취소), available (+ 새 탭에서 열기), stale (리뷰 이후 변경됨 + 다시 만들기), failed (message + 다시 시도).
 * `p.N` links in the page arrive as `research-webui:visual-page` messages from the iframe itself.
 */
export function VisualPane({ title, visual, shown, task, blocked, pageCount, onOpenPage, paneRef }: VisualPaneProps) {
  const ids = readerViewIds('visual');
  const reasonId = useId();
  const frameRef = useRef<HTMLIFrameElement>(null);
  const progressRef = useRef<HTMLDivElement>(null);
  const focusProgress = useRef(false);
  // The iframe loads the first time the tab is shown, then stays (scroll position survives switching).
  const [frameWanted, setFrameWanted] = useState(shown);
  if (shown && !frameWanted) setFrameWanted(true);
  // A regenerated summary has a new `generated_at`: the new key reloads the frame (responses are no-store).
  const frameKey = visual.generated_at ?? visual.review_sha256 ?? 'visual';
  const [loadedKey, setLoadedKey] = useState<string | null>(null);

  const hasVisual = visual.available;
  const jobId = task.job?.job_id ?? null;
  const busy = jobId !== null || task.settling;
  const canStart = !busy && !task.pending && blocked === null;
  const outcome = task.outcome;
  const failed = outcome?.status === 'failed' ? outcome.message : null;

  // Only the iframe's own window may switch the reader to a PDF page, with a page the PDF has.
  useEffect(() => {
    if (!shown) return;
    const onMessage = (event: MessageEvent) => {
      const frame = frameRef.current;
      if (!frame || event.source !== frame.contentWindow) return;
      const data: unknown = event.data;
      if (typeof data !== 'object' || data === null || !('type' in data) || data.type !== VISUAL_PAGE_MESSAGE) return;
      const page = 'page' in data ? data.page : null;
      if (typeof page !== 'number' || !Number.isInteger(page) || page < 1 || page > pageCount) return;
      onOpenPage(page);
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, [shown, pageCount, onOpenPage]);

  // 시각 요약 만들기 replaced the button with the job: its progress takes focus.
  useEffect(() => {
    if (!jobId || !focusProgress.current) return;
    focusProgress.current = false;
    progressRef.current?.focus();
  }, [jobId]);

  // A control that held focus went away with a state change (만들기 취소 when the job ends, 다시 만들기
  // once it starts): focus stays in the pane instead of falling back to the page. Mount and tab
  // switches are not state changes here (the first load keeps the browser's focus).
  const stateKey = `${jobId}|${task.settling}|${hasVisual}|${outcome?.status ?? ''}`;
  const previousStateKey = useRef(stateKey);
  useEffect(() => {
    if (previousStateKey.current === stateKey) return;
    previousStateKey.current = stateKey;
    if (shown && document.activeElement === document.body) paneRef.current?.focus({ preventScroll: true });
  }, [stateKey, shown, paneRef]);

  const onStart = () => {
    focusProgress.current = true;
    task.start();
  };

  const startButton = (label: string, primary: boolean) => (
    <button
      type="button"
      className={primary ? 'btn btn-primary btn-small' : 'btn btn-secondary btn-small'}
      onClick={onStart}
      disabled={!canStart}
      aria-busy={task.pending}
      aria-describedby={blocked && !busy ? reasonId : undefined}
    >
      {primary ? <IconVisual /> : <IconRedo />}
      {task.pending ? '요청하는 중…' : label}
    </button>
  );

  const blockedNote =
    blocked && !busy ? (
      <p className="field-hint" id={reasonId}>
        {blocked.reason}
        {blocked.status ? (
          <>
            {' '}
            <a href={STATUS_HREF}>상태 화면에서 확인</a>
          </>
        ) : null}
      </p>
    ) : null;

  const startErrorNote =
    task.startError && !busy ? (
      <p className="field-error" role="alert">
        {startErrorText(task.startError)}
        {VISUAL_ROLE_ERROR_CODES[task.startError.code] ? (
          <>
            {' '}
            <a href={STATUS_HREF}>상태 화면에서 확인</a>
          </>
        ) : null}
      </p>
    ) : null;

  const progress = task.job ? (
    <VisualProgress
      key={task.job.job_id}
      job={task.job}
      hasVisual={hasVisual}
      onEnd={task.finish}
      containerRef={progressRef}
    />
  ) : task.settling ? (
    <p className="loading-text" role="status">
      에이전트가 끝났습니다. 결과를 불러오는 중…
    </p>
  ) : null;

  const metaText =
    visual.stale === true
      ? '이 요약을 만든 뒤 리뷰가 바뀌었습니다.'
      : visual.stale === null
        ? '생성 기록이 없어 지금 리뷰와 맞는지 확인할 수 없습니다.'
        : [
            visual.generated_at ? formatDateTime(visual.generated_at) : null,
            visual.source ? SOURCE_LABELS[visual.source] : null,
            visual.check === 'problems' ? '렌더 검사 경고 남음' : null,
          ]
            .filter(Boolean)
            .join(' · ');

  return (
    <div
      ref={paneRef}
      id={ids.panel}
      role="tabpanel"
      aria-labelledby={ids.tab}
      className="reader-view visual-pane"
      data-shown={shown ? 'true' : 'false'}
      inert={!shown}
      tabIndex={-1}
    >
      {hasVisual ? (
        <div className="visual-bar">
          <p className="visual-bar-meta">
            {visual.stale === true ? (
              <span className="badge" data-tone="warning">
                리뷰 이후 변경됨
              </span>
            ) : null}
            {metaText ? <span className="caption">{metaText}</span> : null}
          </p>
          <div className="visual-bar-actions">
            {visual.stale !== false && !busy && failed === null ? startButton('다시 만들기', false) : null}
            <a className="btn btn-text btn-small" href={visual.url} target="_blank" rel="noopener noreferrer">
              새 탭에서 열기
              <IconExternal />
              <span className="visually-hidden"> (새 탭)</span>
            </a>
          </div>
        </div>
      ) : null}

      {hasVisual ? (
        <div className="visual-notices">
          {progress}
          {failed !== null && !busy ? (
            <div className="notice" data-tone="danger">
              <p className="notice-title">
                <IconAlert />
                시각 요약을 다시 만들지 못했습니다
              </p>
              <p className="notice-detail">{failed}</p>
              <p>아래는 이전에 만든 시각 요약입니다.</p>
              <div className="notice-actions">{startButton('다시 시도', false)}</div>
            </div>
          ) : null}
          {outcome?.status === 'missing' && !busy ? (
            <p className="field-hint">서버가 다시 시작되어 시각 요약 작업이 끝났는지 알 수 없습니다.</p>
          ) : null}
          {visual.stale !== false || failed !== null ? blockedNote : null}
          {startErrorNote}
        </div>
      ) : null}

      {hasVisual ? (
        <div className="visual-frame-area">
          {frameWanted ? (
            <iframe
              key={frameKey}
              ref={frameRef}
              className="visual-frame"
              src={visual.url}
              sandbox="allow-scripts"
              referrerPolicy="no-referrer"
              title={`시각 요약: ${title}`}
              onLoad={() => setLoadedKey(frameKey)}
            />
          ) : null}
          {loadedKey === frameKey ? null : (
            <p className="visual-frame-loading" role="status">
              시각 요약을 불러오는 중…
            </p>
          )}
        </div>
      ) : (
        <div className="visual-state">
          {progress ?? (
            <>
              <span className="empty-state-icon" aria-hidden="true">
                <IconVisual />
              </span>
              <h2>{failed !== null ? '시각 요약을 만들지 못했습니다' : '시각 요약 없음'}</h2>
              {failed !== null ? (
                <p className="notice-detail visual-state-error">{failed}</p>
              ) : outcome?.status === 'cancelled' ? (
                <p className="field-hint">시각 요약 만들기를 취소했습니다. 바뀐 파일은 없습니다.</p>
              ) : outcome?.status === 'missing' ? (
                <p className="field-hint">서버가 다시 시작되어 시각 요약 작업이 끝났는지 알 수 없습니다.</p>
              ) : null}
              <p>리뷰를 문제 → 방법 구조 → 핵심 결과 → 한계 순서의 한 페이지 그림으로 정리합니다.</p>
              <p className="field-hint">
                리뷰 문서에 있는 내용만 씁니다. 에이전트 작업으로 최대 15분 걸리며, 그동안 원문 PDF를 계속 읽을 수
                있습니다.
              </p>
              <div className="visual-state-actions">
                {startButton(failed !== null ? '다시 시도' : '시각 요약 만들기', true)}
              </div>
              {blockedNote}
              {startErrorNote}
            </>
          )}
        </div>
      )}
    </div>
  );
}
