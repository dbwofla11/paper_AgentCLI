import {
  useDeferredValue,
  useEffect,
  useId,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
  type ReactNode,
} from 'react';
import { askPaper, cancelJob, deleteThread, toApiError, type ApiError } from '../api/client';
import type { AskResponse, EvidenceItem, ReaderAnchor, ReaderStatus, ReaderThread, ThreadTurn } from '../api/types';
import { StatusBadge } from '../components/Badges';
import { formatCost, formatCount, formatDateTime, formatDuration } from '../format';
import { STATUS_HREF } from '../hooks/useHashRoute';
import { useJobStream } from '../hooks/useJobStream';
import { useReader } from './context';
import { shorten } from './evidence';
import {
  ArrowLeft as IconBack,
  MessageSquareText as IconAsk,
  RefreshCw as IconRefresh,
  Trash2 as IconTrash,
  X as IconClose,
} from 'lucide-react';
import { ReaderMarkdown } from './RichText';
import { turnBusy, type ThreadsState } from './useThreads';

/** Contract limit for questions. */
const MAX_QUESTION_CHARS = 4000;
/** Distance from the end (px) within which streamed text keeps the thread scrolled to the end. */
const STICK_TO_END_PX = 48;

export interface DraftAnchor {
  anchor: ReaderAnchor;
  /** blob: URL of a region crop, owned by the reader screen. */
  preview: string | null;
}

/** Korean guidance for `POST …/ask` and thread errors (reader design §3.1). */
const ASK_ERRORS: Record<string, string> = {
  thread_busy: '이 스레드의 이전 답변이 아직 끝나지 않았습니다. 끝난 뒤 다시 보내세요.',
  thread_full: '질문을 더 받을 수 없습니다(스레드당 50개, 논문당 스레드 200개). 새 스레드를 만들거나 오래된 스레드를 지우세요.',
  thread_not_found: '스레드를 찾을 수 없습니다. 목록을 새로 고친 뒤 다시 시도하세요.',
  reader_unavailable: '답변할 에이전트가 준비되지 않았습니다. 상태 화면에서 paper-reader 역할과 에이전트 연결을 확인하세요.',
  role_config_error: 'omp 설정을 읽지 못해 질문을 보낼 수 없습니다. 상태 화면의 안내를 확인하세요.',
  pdf_tools_missing: 'PDF 도구(pdftotext, 영역 질문은 pdftoppm·pdfinfo)가 없어 질문을 보낼 수 없습니다.',
  pdf_missing: 'PDF 파일을 찾을 수 없어 질문을 보낼 수 없습니다.',
  not_found: '논문 기록을 찾을 수 없습니다.',
};

function errorText(error: ApiError): string {
  const hint = ASK_ERRORS[error.code];
  return hint ? `${hint} (${error.message})` : error.message;
}

/** Why region questions cannot be sent; null when they can (or readiness is still unknown). */
export function regionBlockedReason(status: ReaderStatus | null): string | null {
  if (!status || status.region_ready) return null;
  if (!status.pdf_tools.pdftoppm || !status.pdf_tools.pdfinfo) {
    return 'pdftoppm·pdfinfo가 없어 영역 질문을 보낼 수 없습니다. poppler를 설치하세요.';
  }
  return status.reason ?? '지금 답변 에이전트로는 영역 질문을 보낼 수 없습니다.';
}

function anchorLabel(anchor: ReaderAnchor, claims: ReadonlyMap<string, EvidenceItem>): string {
  switch (anchor.kind) {
    case 'text':
      return `p.${anchor.page} · “${shorten(anchor.text, 44)}”`;
    case 'region':
      return `p.${anchor.page} 영역`;
    case 'page':
      return `p.${anchor.page} 전체`;
    case 'claim': {
      const claim = claims.get(anchor.claim_id);
      return `리뷰 근거 · ${claim ? shorten(claim.statement, 40) : anchor.claim_id}`;
    }
  }
}

function AnchorChip({
  anchor,
  claims,
  preview = null,
  onRemove,
}: {
  anchor: ReaderAnchor;
  claims: ReadonlyMap<string, EvidenceItem>;
  preview?: string | null;
  onRemove?: () => void;
}) {
  const { showAnchor, pageCount } = useReader();
  const label = anchorLabel(anchor, claims);
  const page = anchor.page;
  const canShow = pageCount > 0 && (page === null ? anchor.kind === 'claim' : page <= pageCount);
  return (
    <span className="anchor-chip" data-kind={anchor.kind}>
      <button
        type="button"
        className="anchor-chip-main"
        onClick={() => showAnchor(anchor)}
        disabled={!canShow}
        title={`${label} — PDF에서 보기`}
      >
        {preview ? <img className="anchor-thumb" src={preview} alt="" width="40" height="28" /> : null}
        <span className="anchor-chip-label">{label}</span>
      </button>
      {onRemove ? (
        <button type="button" className="anchor-chip-remove" onClick={onRemove} aria-label={`${label} 기준 빼기`}>
          <IconClose />
        </button>
      ) : null}
    </span>
  );
}

export function ReaderRoleBadge({
  status,
  error,
  loading,
  onRefresh,
}: {
  status: ReaderStatus | null;
  error: ApiError | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  let tone: 'success' | 'danger' | 'neutral' | 'waiting' = 'waiting';
  let label = '답변 모델 확인 중…';
  let detail: string | null = null;
  if (status) {
    if (status.configured === null) {
      tone = 'danger';
      label = '설정 읽기 실패';
      detail = status.reason ?? 'omp 설정을 읽지 못했습니다.';
    } else if (status.ready) {
      tone = 'success';
      label = '답변 준비됨';
      detail = status.selector ?? (status.agent ? `${status.agent} 기본 모델` : null);
    } else {
      tone = 'danger';
      label = '답변 불가';
      detail = status.reason ?? '답변할 에이전트가 준비되지 않았습니다.';
    }
  } else if (error && !loading) {
    tone = 'neutral';
    label = '상태 확인 실패';
    detail = error.message;
  }
  return (
    <div className="role-strip" role="status">
      <span className="badge" data-tone={tone}>
        {label}
      </span>
      {detail ? (
        <span className="role-strip-detail" translate={status?.ready ? 'no' : undefined}>
          {detail}
        </span>
      ) : null}
      {status && status.configured === false ? <span className="role-strip-note meta">paper-reader 미설정</span> : null}
      {status && !status.ready ? (
        <a className="role-strip-link" href={STATUS_HREF}>
          상태 확인
        </a>
      ) : null}
      <button
        type="button"
        className="icon-btn icon-btn-small"
        onClick={onRefresh}
        disabled={loading}
        aria-busy={loading}
        aria-label="답변 모델 다시 확인"
        title="답변 모델 다시 확인"
      >
        <IconRefresh />
      </button>
    </div>
  );
}

function Composer({
  slug,
  threadId,
  draft,
  onClearDraft,
  currentPage,
  pdfAvailable,
  status,
  busy,
  claims,
  focusRequest,
  onFocused,
  onSent,
}: {
  slug: string;
  threadId: string | null;
  draft: DraftAnchor | null;
  onClearDraft: () => void;
  currentPage: number;
  pdfAvailable: boolean;
  status: ReaderStatus | null;
  busy: boolean;
  claims: ReadonlyMap<string, EvidenceItem>;
  /** Focus the input once (after 질문하기 from the PDF or a claim card). */
  focusRequest: boolean;
  onFocused: () => void;
  onSent: (response: AskResponse) => void;
}) {
  const [text, setText] = useState('');
  // New threads default to the current page as context; follow-ups continue the thread's own context.
  const [pageContext, setPageContext] = useState(threadId === null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const hintId = useId();
  const inputId = useId();

  useEffect(() => {
    if (!focusRequest) return;
    textareaRef.current?.focus();
    onFocused();
  }, [focusRequest, onFocused]);

  const anchor: ReaderAnchor | null =
    draft?.anchor ?? (pageContext && pdfAvailable ? { kind: 'page', page: currentPage } : null);
  const trimmed = text.trim();
  const tooLong = text.length > MAX_QUESTION_CHARS;
  const regionBlocked = anchor?.kind === 'region' ? regionBlockedReason(status) : null;
  const blocked = busy
    ? '이전 답변이 끝나면 이어서 물을 수 있습니다.'
    : status && !status.ready
      ? (status.reason ?? '답변할 에이전트가 준비되지 않았습니다.')
      : regionBlocked;
  const canSend = trimmed.length > 0 && !tooLong && !sending && blocked === null;

  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    if (!canSend) return;
    setSending(true);
    setError(null);
    try {
      const response = await askPaper(slug, { thread_id: threadId, question: trimmed, anchor });
      setText('');
      onSent(response);
    } catch (caught) {
      setError(toApiError(caught));
    } finally {
      setSending(false);
    }
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      void submit();
    }
  };

  const placeholder =
    anchor?.kind === 'text'
      ? '선택한 문장에 대해 물어보세요…'
      : anchor?.kind === 'region'
        ? '이 표·그림에서 궁금한 점을 적으세요…'
        : anchor?.kind === 'claim'
          ? '이 리뷰 근거에 대해 물어보세요…'
          : anchor?.kind === 'page'
            ? `${anchor.page}쪽에 대해 물어보세요…`
            : threadId
              ? '이어서 물어보세요…'
              : '논문에 대해 물어보세요…';

  return (
    <form className="composer" onSubmit={(event) => void submit(event)}>
      <div className="composer-context">
        {draft ? (
          <AnchorChip anchor={draft.anchor} preview={draft.preview} claims={claims} onRemove={onClearDraft} />
        ) : pdfAvailable ? (
          <button
            type="button"
            className="context-toggle"
            aria-pressed={pageContext}
            onClick={() => setPageContext((value) => !value)}
            title={pageContext ? '현재 쪽을 질문의 기준으로 보냅니다' : '쪽 기준 없이 논문 전체에 대해 묻습니다'}
          >
            {pageContext ? `p.${currentPage} 기준` : '쪽 기준 없음'}
          </button>
        ) : null}
      </div>
      <label className="visually-hidden" htmlFor={inputId}>
        {threadId ? '이어서 질문' : '새 질문'}
      </label>
      <textarea
        id={inputId}
        ref={textareaRef}
        name="question"
        className="composer-input"
        rows={3}
        value={text}
        placeholder={placeholder}
        aria-describedby={hintId}
        aria-invalid={tooLong ? true : undefined}
        onChange={(event) => setText(event.target.value)}
        onKeyDown={onKeyDown}
      />
      <div className="composer-foot">
        <p id={hintId} className="composer-hint">
          {blocked ?? (
            <>
              <kbd>⌘</kbd>/<kbd>Ctrl</kbd>&nbsp;+&nbsp;<kbd>Enter</kbd>로 보내기
            </>
          )}
        </p>
        <span className="composer-count num" data-over={tooLong ? 'true' : undefined}>
          {formatCount(text.length)}/{formatCount(MAX_QUESTION_CHARS)}
        </span>
        <button type="submit" className="btn btn-primary btn-small" disabled={!canSend} aria-busy={sending}>
          <IconAsk />
          {sending ? '보내는 중…' : threadId ? '이어서 묻기' : '질문하기'}
        </button>
      </div>
      {error ? (
        <p className="composer-error" role="alert">
          {errorText(error)}
        </p>
      ) : null}
    </form>
  );
}

function turnMeta(turn: ThreadTurn): string | null {
  const parts = [
    turn.agent,
    turn.selector ?? turn.model,
    formatDuration(turn.duration_ms),
    formatCost(turn.cost_usd),
  ].filter((part): part is string => Boolean(part));
  return parts.length > 0 ? parts.join(' · ') : null;
}

const TERMINAL_STATUS = { result: 'completed', error: 'failed', cancelled: 'cancelled' } as const;

function TurnView({
  turn,
  claims,
  pdfSha,
  canRetry,
  onRetry,
  onSettle,
  onAnnounce,
}: {
  turn: ThreadTurn;
  claims: ReadonlyMap<string, EvidenceItem>;
  pdfSha: string | null;
  canRetry: boolean;
  onRetry: (turn: ThreadTurn) => void;
  onSettle: (turnId: string) => void;
  onAnnounce: (text: string) => void;
}) {
  const live = turnBusy(turn.status);
  const stream = useJobStream(live ? turn.job_id : null, {
    onTerminal: () => onSettle(turn.turn_id),
    onMissing: () => onSettle(turn.turn_id),
  });
  const [cancel, setCancel] = useState<'idle' | 'pending' | 'failed'>('idle');
  const streamed = stream.items
    .filter((item) => item.kind === 'text')
    .map((item) => item.text)
    .join('\n\n');
  const lastTool = [...stream.items].reverse().find((item) => item.kind === 'tool');
  const status = live && stream.terminal ? TERMINAL_STATUS[stream.terminal.type] : turn.status;
  const answer = live ? streamed : (turn.answer ?? '');
  const deferred = useDeferredValue(answer);

  useEffect(() => {
    const terminal = stream.terminal;
    if (!terminal) return;
    if (terminal.type === 'result') onAnnounce(`답변 완료. ${shorten(terminal.text, 600)}`);
    else if (terminal.type === 'error') onAnnounce(`답변 실패. ${terminal.message}`);
    else onAnnounce('답변을 취소했습니다.');
  }, [stream.terminal, onAnnounce]);

  const requestCancel = async () => {
    setCancel('pending');
    try {
      await cancelJob(turn.job_id);
      setCancel('idle');
    } catch (caught) {
      const apiError = toApiError(caught);
      setCancel(apiError.code === 'already_finished' ? 'idle' : 'failed');
      onSettle(turn.turn_id);
    }
  };

  const waiting = live && !stream.terminal;
  const meta = turnMeta(turn);
  return (
    <li className="turn">
      <div className="turn-question">
        {turn.anchor ? <AnchorChip anchor={turn.anchor} claims={claims} /> : null}
        <p className="turn-question-text">{turn.question}</p>
      </div>
      <div className="turn-answer" data-status={status} aria-busy={waiting}>
        {waiting ? (
          <p className="turn-progress">
            <span className="turn-progress-dot" aria-hidden="true" />
            {stream.phase === 'waiting' || stream.phase === 'reconnecting'
              ? '연결이 끊겨 다시 연결하는 중…'
              : stream.phase === 'failed'
                ? '답변 스트림에 연결하지 못했습니다.'
                : turn.status === 'queued' && !stream.start
                  ? '다른 작업이 끝나기를 기다리는 중…'
                  : lastTool && lastTool.kind === 'tool'
                    ? `읽는 중: ${shorten(lastTool.summary || lastTool.name, 60)}`
                    : '답변을 준비하는 중…'}
          </p>
        ) : status !== 'completed' ? (
          <div className="turn-state">
            <StatusBadge status={status} />
            <span>
              {status === 'failed'
                ? (turn.error?.message ??
                  (stream.terminal?.type === 'error' ? stream.terminal.message : '답변하지 못했습니다.'))
                : status === 'cancelled'
                  ? '답변을 취소했습니다.'
                  : status === 'interrupted'
                    ? '서버가 다시 시작되어 답변이 중단되었습니다.'
                    : null}
            </span>
          </div>
        ) : null}
        {deferred ? (
          <>
            {turn.partial && !live ? <p className="turn-partial meta">부분 답변 (끝까지 받지 못함)</p> : null}
            <ReaderMarkdown markdown={deferred} className="answer-md" />
          </>
        ) : status === 'completed' && !live ? (
          <p className="meta">빈 답변을 받았습니다.</p>
        ) : null}
        <div className="turn-foot">
          {meta && !live ? (
            <span className="meta" translate="no">
              {meta}
            </span>
          ) : null}
          {!live && pdfSha && turn.pdf_sha256 && turn.pdf_sha256 !== pdfSha ? (
            <span className="meta turn-stale">질문한 뒤 PDF가 바뀌었습니다</span>
          ) : null}
          {waiting ? (
            <button type="button" className="text-btn" onClick={() => void requestCancel()} disabled={cancel === 'pending'}>
              {cancel === 'pending' ? '취소하는 중…' : '답변 취소'}
            </button>
          ) : null}
          {cancel === 'failed' ? <span className="meta">취소하지 못했습니다.</span> : null}
          {canRetry && !live ? (
            <button type="button" className="text-btn" onClick={() => onRetry(turn)}>
              다시 묻기
            </button>
          ) : null}
        </div>
      </div>
    </li>
  );
}

function ThreadView({
  slug,
  thread,
  claims,
  pdfSha,
  composer,
  threadsState,
  onBack,
  onAnnounce,
}: {
  slug: string;
  thread: ReaderThread;
  claims: ReadonlyMap<string, EvidenceItem>;
  pdfSha: string | null;
  composer: (busy: boolean) => ReactNode;
  threadsState: ThreadsState;
  onBack: () => void;
  onAnnounce: (text: string) => void;
}) {
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [actionError, setActionError] = useState<ApiError | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLOListElement>(null);
  /** Whether the reader is at the end of the thread; streamed text then keeps it there. */
  const pinnedRef = useRef(true);
  const last = thread.turns.at(-1);
  const busy = last ? turnBusy(last.status) : false;

  // Opening a thread or adding a turn jumps to the newest turn.
  useEffect(() => {
    const scroller = scrollRef.current;
    if (!scroller) return;
    scroller.scrollTop = scroller.scrollHeight;
    pinnedRef.current = true;
  }, [thread.thread_id, thread.turns.length]);

  // Streaming answers grow the list: follow them unless the reader scrolled up.
  useEffect(() => {
    const scroller = scrollRef.current;
    const list = listRef.current;
    if (!scroller || !list) return;
    const observer = new ResizeObserver(() => {
      if (pinnedRef.current) scroller.scrollTop = scroller.scrollHeight;
    });
    observer.observe(list);
    return () => observer.disconnect();
  }, []);

  const onScroll = () => {
    const scroller = scrollRef.current;
    if (scroller) pinnedRef.current = scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < STICK_TO_END_PX;
  };

  const retry = async (turn: ThreadTurn) => {
    setActionError(null);
    try {
      const response = await askPaper(slug, { thread_id: thread.thread_id, question: turn.question, anchor: turn.anchor });
      threadsState.upsert(response.thread);
    } catch (caught) {
      setActionError(toApiError(caught));
    }
  };

  const remove = async () => {
    setDeleting(true);
    setActionError(null);
    try {
      await deleteThread(slug, thread.thread_id);
      threadsState.remove(thread.thread_id);
      onBack();
    } catch (caught) {
      setActionError(toApiError(caught));
      setConfirming(false);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="thread-view">
      <div className="thread-scroll" ref={scrollRef} onScroll={onScroll}>
        <div className="thread-head">
          <button type="button" className="text-btn" onClick={onBack}>
            <IconBack />
            질문 목록
          </button>
          {confirming ? (
            <span className="thread-confirm" role="group" aria-label="스레드 삭제 확인">
              <span>스레드를 지울까요?</span>
              <button type="button" className="btn btn-danger btn-small" onClick={() => void remove()} disabled={deleting}>
                {deleting ? '지우는 중…' : '지우기'}
              </button>
              <button type="button" className="btn btn-secondary btn-small" onClick={() => setConfirming(false)}>
                그대로 두기
              </button>
            </span>
          ) : (
            <button
              type="button"
              className="icon-btn"
              onClick={() => setConfirming(true)}
              disabled={busy}
              aria-label="스레드 지우기"
              title={busy ? '답변이 끝난 뒤 지울 수 있습니다' : '스레드 지우기'}
            >
              <IconTrash />
            </button>
          )}
        </div>
        <h3 className="thread-title">{thread.title}</h3>
        {actionError ? (
          <p className="composer-error" role="alert">
            {errorText(actionError)}
          </p>
        ) : null}
        <ol className="turn-list" ref={listRef}>
          {thread.turns.map((turn) => (
            <TurnView
              key={turn.turn_id}
              turn={turn}
              claims={claims}
              pdfSha={pdfSha}
              canRetry={turn === last && !busy}
              onRetry={(item) => void retry(item)}
              onSettle={threadsState.settle}
              onAnnounce={onAnnounce}
            />
          ))}
        </ol>
      </div>
      <div className="thread-composer">{composer(busy)}</div>
    </div>
  );
}

function ThreadList({
  threads,
  claims,
  onOpen,
}: {
  threads: ReaderThread[];
  claims: ReadonlyMap<string, EvidenceItem>;
  onOpen: (thread: ReaderThread) => void;
}) {
  const sorted = [...threads].sort((a, b) => (b.updated_at ?? '').localeCompare(a.updated_at ?? ''));
  return (
    <ul className="thread-list">
      {sorted.map((thread) => {
        const last = thread.turns.at(-1);
        const anchor = thread.anchor ?? thread.turns[0]?.anchor ?? null;
        return (
          <li key={thread.thread_id}>
            <button type="button" className="thread-item" onClick={() => onOpen(thread)}>
              <span className="thread-item-title">{thread.title || '제목 없는 질문'}</span>
              <span className="thread-item-meta meta">
                {anchor ? <span>{anchorLabel(anchor, claims)}</span> : <span>논문 전체</span>}
                <span>
                  질문 <span className="num">{formatCount(thread.turns.length)}</span>
                </span>
                <span className="num">{formatDateTime(thread.updated_at)}</span>
              </span>
              {last && last.status !== 'completed' ? <StatusBadge status={last.status} /> : null}
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export function QuestionsPanel({
  slug,
  status,
  threadsState,
  activeThreadId,
  onOpenThread,
  draft,
  onClearDraft,
  composerFocusRequest,
  onComposerFocused,
  currentPage,
  pdfAvailable,
  pdfSha,
  claims,
}: {
  slug: string;
  status: ReaderStatus | null;
  threadsState: ThreadsState;
  activeThreadId: string | null;
  /** Opens a thread (null = back to the list); `reveal` scrolls the PDF to the thread's anchor. */
  onOpenThread: (thread: ReaderThread | null, reveal?: boolean) => void;
  draft: DraftAnchor | null;
  onClearDraft: () => void;
  composerFocusRequest: boolean;
  onComposerFocused: () => void;
  currentPage: number;
  pdfAvailable: boolean;
  pdfSha: string | null;
  claims: ReadonlyMap<string, EvidenceItem>;
}) {
  const [announcement, setAnnouncement] = useState('');
  const { threads, error, loading, reload } = threadsState;
  const active = activeThreadId ? (threads?.find((thread) => thread.thread_id === activeThreadId) ?? null) : null;

  const onSent = (response: AskResponse) => {
    threadsState.upsert(response.thread);
    onClearDraft();
    if (response.thread.thread_id !== activeThreadId) onOpenThread(response.thread, false);
    setAnnouncement('질문을 보냈습니다. 답변을 기다리는 중입니다.');
  };

  const composer = (threadId: string | null, busy: boolean) => (
    <Composer
      key={threadId ?? 'new'}
      slug={slug}
      threadId={threadId}
      draft={threadId ? null : draft}
      onClearDraft={onClearDraft}
      currentPage={currentPage}
      pdfAvailable={pdfAvailable}
      status={status}
      busy={busy}
      claims={claims}
      focusRequest={threadId ? false : composerFocusRequest}
      onFocused={onComposerFocused}
      onSent={onSent}
    />
  );

  return (
    <div className="questions-panel">
      <p className="visually-hidden" aria-live="polite">
        {announcement}
      </p>
      {active ? (
        <ThreadView
          slug={slug}
          thread={active}
          claims={claims}
          pdfSha={pdfSha}
          composer={(busy) => composer(active.thread_id, busy)}
          threadsState={threadsState}
          onBack={() => onOpenThread(null)}
          onAnnounce={setAnnouncement}
        />
      ) : (
        <>
          {composer(null, false)}
          <div className="thread-list-head">
            <h3 className="panel-subheading">
              질문 기록
              {threads ? <span className="num"> {formatCount(threads.length)}</span> : null}
            </h3>
            <button
              type="button"
              className="icon-btn icon-btn-small"
              onClick={reload}
              disabled={loading}
              aria-label="질문 기록 새로 고침"
              title="질문 기록 새로 고침"
            >
              <IconRefresh />
            </button>
          </div>
          {error ? (
            <p className="composer-error" role="alert">
              질문 기록을 불러오지 못했습니다. {error.message}
            </p>
          ) : null}
          {threads === null ? (
            loading ? (
              <p className="panel-empty" role="status">
                질문 기록을 불러오는 중…
              </p>
            ) : null
          ) : threads.length === 0 ? (
            <p className="panel-empty">
              아직 질문이 없습니다. PDF에서 문장을 선택하거나 <kbd>R</kbd>로 표·그림 영역을 잡아 질문해 보세요. 답변과 질문은
              이 논문에 저장되어 다시 열어도 남습니다.
            </p>
          ) : (
            <ThreadList threads={threads} claims={claims} onOpen={(thread) => onOpenThread(thread)} />
          )}
        </>
      )}
    </div>
  );
}
