import { useEffect, useId, useRef, useState, type KeyboardEvent, type Ref } from 'react';
import { ArrowRight, CircleAlert, RotateCcw, Square } from 'lucide-react';
import { cancelJob, toApiError, type ApiError } from '../../api/client';
import type { DiscoveryCandidate, DiscoverySession, DiscoverySessionReport } from '../../api/types';
import { StatusBadge } from '../../components/Badges';
import { ErrorNotice } from '../../components/ErrorNotice';
import { Skeleton } from '../../components/Skeleton';
import { formatCount, formatDateTime, formatDuration } from '../../format';
import { STATUS_HREF, discoverPrefillHref, jobHref, paperHref } from '../../hooks/useHashRoute';
import { useJobStream } from '../../hooks/useJobStream';
import { PHASE_LABELS, StreamNotice, Transcript } from '../JobDetail';
import type { CandidateActionHandlers } from './CandidateActions';
import { CandidateList } from './CandidateList';
import { ReportList } from './DailyDay';
import { RelatedView } from './RelatedView';
import { isActiveSearch, useSearchSession } from './useDiscovery';

type SearchSession = Extract<DiscoverySession, { mode: 'search' }>;

/** Headline per `error.kind` of a failed session; the server message follows it. */
const FAILURE_TITLES: Record<string, string> = {
  interrupted: '서버가 재시작되어 검색이 중단되었습니다. 같은 검색어로 다시 실행하세요.',
  invalid_output: '에이전트 답변이 결과 형식에 맞지 않아 후보를 저장하지 못했습니다.',
  timeout: '제한 시간 15분을 넘겨 검색을 멈췄습니다.',
  usage_limit: '사용량 한도에 도달해 검색이 멈췄습니다. 한도가 풀린 뒤 다시 검색하세요.',
  auth: '에이전트 로그인이 필요합니다. 상태 화면에서 로그인 명령을 확인하세요.',
  process: '에이전트 실행이 비정상 종료되었습니다.',
};

/** Headline per error code of GET /api/discovery/searches/{id}; codes without retry cannot change by retrying. */
function loadErrorTitle(error: ApiError, stale: boolean): { title: string; retry: boolean } {
  if (stale) return { title: '검색 기록을 다시 불러오지 못했습니다. 아래는 이전 결과입니다.', retry: true };
  if (error.code === 'not_found') return { title: '검색 기록이 없습니다. 지워졌거나 주소가 잘못되었습니다.', retry: false };
  if (error.code === 'bad_request') return { title: '검색 기록 주소가 올바르지 않습니다. 기록에서 고르세요.', retry: false };
  if (error.code === 'cache_corrupt') return { title: '검색 기록 파일을 읽지 못했습니다.', retry: true };
  return { title: '검색 기록을 불러오지 못했습니다.', retry: true };
}

function yearRange(from: number | null, to: number | null): string {
  if (from !== null && to !== null) return from === to ? `${from}년` : `${from}–${to}년`;
  if (from !== null) return `${from}년 이후`;
  if (to !== null) return `${to}년까지`;
  return '제한 없음';
}

function RequestFacts({ session }: { session: SearchSession }) {
  const agent = session.agent;
  // The selector (`provider/model[:effort]`) when a role ran; the CLI's model name otherwise.
  const model = agent?.selector ?? agent?.model ?? null;
  const duration = formatDuration(session.duration_ms);
  return (
    <dl className="session-facts discover-request-facts">
      <div>
        <dt>요청 시각</dt>
        <dd className="num">{formatDateTime(session.created_at)}</dd>
      </div>
      <div>
        <dt>연도</dt>
        <dd className="num">{yearRange(session.request.year_from, session.request.year_to)}</dd>
      </div>
      <div>
        <dt>편수</dt>
        <dd>
          최대&nbsp;<span className="num">{formatCount(session.request.limit)}</span>편
        </dd>
      </div>
      <div>
        <dt>분야 힌트</dt>
        <dd>{session.request.category_hint ? <code translate="no">{session.request.category_hint}</code> : '없음'}</dd>
      </div>
      <div>
        <dt>학회 게재 확인된 것만</dt>
        <dd>{session.request.verified_only ? '예' : '아니요'}</dd>
      </div>
      <div>
        <dt>기준 논문</dt>
        <dd>
          {session.request.anchors.length === 0 ? (
            '없음'
          ) : (
            <ul className="discover-anchor-links" role="list">
              {session.request.anchors.map((slug) => (
                <li key={slug}>
                  <a href={paperHref(slug)}>
                    <code translate="no">{slug}</code>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </dd>
      </div>
      {agent?.agent ? (
        <div>
          <dt>에이전트</dt>
          <dd translate="no">
            {agent.agent}
            {model ? ` · ${model}` : ''}
          </dd>
        </div>
      ) : null}
      {duration ? (
        <div>
          <dt>소요 시간</dt>
          <dd className="num">{duration}</dd>
        </div>
      ) : null}
    </dl>
  );
}

/** The searching agent's report, folded: queries, sources, anchors, coverage gaps, exclusions, notes. */
function SearchReportDetails({ report, open }: { report: DiscoverySessionReport; open: boolean }) {
  return (
    <details className="discover-report" open={open}>
      <summary>
        검색 보고{' '}
        <span className="caption">
          질의 <span className="num">{formatCount(report.queries.length)}</span> · 소스{' '}
          <span className="num">{formatCount(report.sources.length)}</span> · 누락 범위{' '}
          <span className="num">{formatCount(report.coverage_gaps.length)}</span>
        </span>
      </summary>
      <dl className="facts">
        <dt>질의</dt>
        <dd>
          <ReportList items={report.queries} mono />
        </dd>
        <dt>소스</dt>
        <dd>{report.sources.length > 0 ? <span translate="no">{report.sources.join(' · ')}</span> : '없음'}</dd>
        <dt>기준 논문</dt>
        <dd>
          {report.anchors.length === 0 ? (
            '없음'
          ) : (
            <ul className="discover-report-list">
              {report.anchors.map((anchor, index) => {
                const ids = [
                  anchor.ids.arXiv ? `arXiv:${anchor.ids.arXiv}` : null,
                  anchor.ids.DOI ? `DOI ${anchor.ids.DOI}` : null,
                ].filter(Boolean);
                return (
                  <li key={`${index}:${anchor.title}`}>
                    {anchor.title}
                    {ids.length > 0 ? (
                      <>
                        {' '}
                        <span className="caption" translate="no">
                          ({ids.join(', ')})
                        </span>
                      </>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          )}
        </dd>
        <dt>누락 범위</dt>
        <dd>
          <ReportList items={report.coverage_gaps} />
        </dd>
        <dt>제외한 결과</dt>
        <dd>
          {report.excluded_count === null ? (
            '집계 안 됨'
          ) : (
            <>
              <span className="num">{formatCount(report.excluded_count)}</span>편
            </>
          )}
        </dd>
        <dt>메모</dt>
        <dd className="discover-report-notes">{report.notes || '없음'}</dd>
      </dl>
    </details>
  );
}

type CancelState = 'idle' | 'confirm' | 'pending';

/** A queued or running search: the job's live transcript (JobDetail pattern) and 검색 취소. */
function LiveSearch({ session, onSettle }: { session: DiscoverySession; onSettle: () => void }) {
  const headingId = useId();
  const jobId = session.job_id;
  const stream = useJobStream(jobId, { onTerminal: () => onSettle(), onMissing: () => onSettle() });
  const [cancelState, setCancelState] = useState<CancelState>('idle');
  const [cancelMessage, setCancelMessage] = useState<string | null>(null);
  const keepRef = useRef<HTMLButtonElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const previousCancel = useRef<CancelState>('idle');

  // The question takes focus on its safe choice; closing it (or the request ending) returns focus to 검색 취소.
  useEffect(() => {
    const previous = previousCancel.current;
    previousCancel.current = cancelState;
    if (cancelState === 'confirm') keepRef.current?.focus();
    else if (cancelState === 'idle' && previous !== 'idle') cancelRef.current?.focus();
  }, [cancelState]);

  const running = session.status === 'running' || stream.start !== null;
  const settling = stream.terminal !== null;
  const streaming = !settling && (stream.phase === 'open' || stream.phase === 'connecting');

  const confirmCancel = async () => {
    if (!jobId) return;
    setCancelState('pending');
    setCancelMessage(null);
    try {
      await cancelJob(jobId);
      setCancelMessage('취소를 요청했습니다. 에이전트가 멈추면 검색 기록에 반영됩니다.');
    } catch (caught) {
      const apiError = toApiError(caught);
      setCancelMessage(
        apiError.code === 'already_finished' ? '이미 끝난 검색이라 취소하지 않았습니다.' : `취소하지 못했습니다: ${apiError.message}`,
      );
    } finally {
      setCancelState('idle');
      onSettle();
    }
  };

  const dismissOnEscape = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Escape') setCancelState('idle');
  };

  const placeholder =
    stream.items.length > 0 || settling
      ? null
      : stream.phase === 'waiting'
        ? '다시 연결되면 진행 기록을 이어서 보여 줍니다.'
        : stream.phase === 'failed'
          ? '스트림에 연결되지 않아 아직 받은 기록이 없습니다.'
          : !running
            ? '실행 순서를 기다리는 중입니다…'
            : stream.phase === 'open'
              ? '에이전트 출력을 기다리는 중…'
              : '스트림에 연결하는 중…';

  return (
    <section className="discover-live" aria-labelledby={headingId}>
      <div className="discover-live-head">
        <h3 id={headingId}>진행 기록</h3>
        {jobId ? (
          <a className="btn btn-text btn-small" href={jobHref(jobId)}>
            작업 화면에서 보기
            <ArrowRight />
          </a>
        ) : null}
      </div>
      <p className="field-hint">
        에이전트가 <code translate="no">paper.py</code>로 학술 DB 두 곳 이상을 조회합니다. 최대 15분 걸리며, 끝나면 이
        자리에 후보가 표시됩니다.
      </p>
      {settling ? null : <span className="ai-progress" aria-hidden="true" />}

      {jobId && !settling ? (
        cancelState === 'confirm' ? (
          <div className="cancel-control" role="group" aria-labelledby={`${headingId}-cancel`} onKeyDown={dismissOnEscape}>
            <p id={`${headingId}-cancel`}>검색을 멈출까요? 지금까지 찾은 결과는 저장하지 않습니다.</p>
            <button type="button" className="btn btn-danger btn-small" onClick={() => void confirmCancel()}>
              검색 취소
            </button>
            <button type="button" className="btn btn-secondary btn-small" ref={keepRef} onClick={() => setCancelState('idle')}>
              계속 검색
            </button>
          </div>
        ) : (
          <div className="cancel-control">
            <button
              type="button"
              ref={cancelRef}
              className="btn btn-secondary btn-small"
              onClick={() => setCancelState('confirm')}
              disabled={cancelState === 'pending'}
              aria-busy={cancelState === 'pending'}
            >
              <Square />
              {cancelState === 'pending' ? '취소 요청 중…' : '검색 취소'}
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
          {jobId ? PHASE_LABELS[stream.phase] : '작업 정보를 기다리는 중…'}
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
      {settling ? (
        <p className="loading-text discover-settling" role="status">
          에이전트가 끝났습니다. 결과를 확인해 저장하는 중…
        </p>
      ) : null}
    </section>
  );
}

interface SearchResultProps {
  searchId: string;
  reloadToken: number;
  /** Session POST /api/discovery/searches just returned for this id; shown until the GET answers. */
  initial: DiscoverySession | null;
  sectionRef: Ref<HTMLElement>;
  /** The session's status changed: the history re-reads. */
  onChanged: () => void;
}

/**
 * `#/discover/searches/{id}`: the request, the live job while queued/running, then the report and the
 * candidate cards (completed) or why it ended (failed, interrupted, cancelled). A related session
 * (인용·피인용) is shown by RelatedView instead.
 */
export function SearchResult({ searchId, reloadToken, initial, sectionRef, onChanged }: SearchResultProps) {
  const headingId = useId();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const { data: session, error, loading, reload, settle, update } = useSearchSession(searchId, reloadToken, initial);
  // Card actions: the server's copy of a candidate replaces the shown one; a refresh re-reads quietly.
  const onCandidate = (candidate: DiscoveryCandidate) =>
    update((current) => ({
      ...current,
      candidates: current.candidates.map((item) => (item.candidate_id === candidate.candidate_id ? candidate : item)),
    }));
  const onRefresh = (candidateId: string, until?: (candidate: DiscoveryCandidate | undefined) => boolean) =>
    settle(
      until && ((current) => until(current.candidates.find((candidate) => candidate.candidate_id === candidateId))),
    );
  const [announcement, setAnnouncement] = useState('');
  const previousStatus = useRef(session?.status ?? null);

  // A status change also reaches the history; the end of a live search is announced once, and focus
  // left on the removed live controls (검색 취소) moves to the heading.
  useEffect(() => {
    const status = session?.status ?? null;
    const previous = previousStatus.current;
    previousStatus.current = status;
    if (session === null || status === null || previous === null || previous === status) return;
    onChanged();
    if (!isActiveSearch(previous) || isActiveSearch(status)) return;
    setAnnouncement(
      status === 'completed'
        ? `검색이 끝났습니다. 후보 ${formatCount(session.candidates.length)}편.`
        : status === 'cancelled'
          ? '검색을 취소했습니다.'
          : '검색이 실패했습니다.',
    );
    if (document.activeElement === null || document.activeElement === document.body) headingRef.current?.focus();
  }, [session, onChanged]);

  const actions: Omit<CandidateActionHandlers, 'onSkipped'> = {
    source: { kind: 'search', id: searchId },
    onCandidate,
    onRefresh,
  };
  // A related session (인용·피인용) keeps this section, so focus on it survives the first GET.
  const related = session?.mode === 'related' ? session : null;
  const search = session?.mode === 'search' ? session : null;
  const notice = error ? loadErrorTitle(error, session !== null) : null;
  const active = search !== null && isActiveSearch(search.status);
  const failure = search?.status === 'failed' ? search.error : null;
  const kind = failure?.kind ?? null;
  const query = search?.request.query ?? null;
  const title = search === null ? '검색 결과' : query || '검색어 없음';
  const badge = search === null ? null : kind === 'interrupted' ? 'interrupted' : search.status;
  const rerun = query ? (
    <a className="btn btn-secondary btn-small" href={discoverPrefillHref(query)}>
      <RotateCcw />
      같은 검색어로 다시 검색
    </a>
  ) : null;

  return (
    <section
      className={related ? 'panel discover-result discover-related' : 'panel discover-result'}
      ref={sectionRef}
      tabIndex={-1}
      aria-labelledby={headingId}
      aria-busy={loading && session === null}
    >
      <p className="visually-hidden" role="status">
        {announcement}
      </p>
      {related ? (
        <RelatedView
          session={related}
          headingId={headingId}
          headingRef={headingRef}
          error={error}
          onRetry={reload}
          actions={actions}
        />
      ) : (
        <>
          <div className="discover-result-head">
            <div className="discover-result-title">
              <p className="eyebrow" translate="no">
                {searchId}
              </p>
              <h2 id={headingId} ref={headingRef} tabIndex={-1}>
                {title}
              </h2>
            </div>
            {badge ? <StatusBadge status={badge} /> : null}
          </div>

          {error && notice && error.code !== 'offline' ? (
            <ErrorNotice error={error} title={notice.title} onRetry={notice.retry ? reload : undefined} />
          ) : null}

          {search ? (
            <>
              <RequestFacts session={search} />

              {active ? <LiveSearch session={search} onSettle={settle} /> : null}

              {search.status === 'failed' ? (
                <div className="notice" data-tone={kind === 'interrupted' ? 'warning' : 'danger'}>
                  <p className="notice-title">
                    <CircleAlert />
                    {(kind ? FAILURE_TITLES[kind] : undefined) ?? '검색이 실패했습니다.'}
                  </p>
                  {failure?.message && kind !== 'interrupted' ? (
                    <p className="notice-detail discover-error-message">{failure.message}</p>
                  ) : null}
                  {kind === 'invalid_output' && search.report?.notes ? (
                    <p>아래 검색 보고의 메모에 에이전트 답변 앞부분이 남아 있습니다.</p>
                  ) : null}
                  <div className="notice-actions">
                    {rerun}
                    {kind === 'auth' || kind === 'usage_limit' ? (
                      <a className="btn btn-text btn-small" href={STATUS_HREF}>
                        상태 화면에서 확인
                        <ArrowRight />
                      </a>
                    ) : null}
                  </div>
                </div>
              ) : null}

              {search.status === 'cancelled' ? (
                <div className="notice">
                  <p className="notice-title">검색을 취소했습니다. 저장한 후보가 없습니다.</p>
                  {rerun ? <div className="notice-actions">{rerun}</div> : null}
                </div>
              ) : null}

              {search.report && !active ? (
                <SearchReportDetails report={search.report} open={kind === 'invalid_output'} />
              ) : null}

              {search.status === 'completed' ? (
                <CandidateList
                  candidates={search.candidates}
                  actions={actions}
                  storedOrder="관련도 (에이전트 순서)"
                  emptyText="에이전트가 조건에 맞는 후보를 찾지 못했습니다. 검색 보고의 누락 범위를 확인하세요."
                />
              ) : null}
            </>
          ) : loading ? (
            <div className="discover-day-skeleton" role="status">
              <span className="visually-hidden">검색 기록을 불러오는 중…</span>
              <Skeleton height="4rem" />
              <Skeleton height="11rem" />
              <Skeleton height="11rem" />
            </div>
          ) : error?.code === 'offline' ? (
            <p className="empty empty-compact">서버를 실행하고 ‘다시 연결’을 누르면 검색 기록을 다시 불러옵니다.</p>
          ) : null}
        </>
      )}
    </section>
  );
}
