import type { Ref } from 'react';
import { RefreshCw } from 'lucide-react';
import type { ConnectionSnapshot } from '../api/client';
import type { AgentCandidate, ReviewQueueJob, RoleResolution, StatusPayload } from '../api/types';
import { ReadyBadge, RoleStateBadge, StatusBadge, VerificationBadge } from '../components/Badges';
import { ErrorNotice } from '../components/ErrorNotice';
import { ScreenHeader } from '../components/ScreenHeader';
import { QueueMessage, VerificationLine } from '../components/ReviewQueueParts';
import { Skeleton } from '../components/Skeleton';
import { formatCount, formatDateTime, formatTime, statusLabel } from '../format';
import { PAPERS_HREF } from '../hooks/useHashRoute';
import {
  READER_ROLE_SLOT,
  REVIEW_ROLE_SLOTS,
  SEARCHER_ROLE_SLOT,
  VISUAL_ROLE_SLOT,
  roleState,
  selectedCandidate,
  type RoleCardSlot,
} from '../roles';
import { useStatus } from '../status';

const QUEUE_STATUSES = ['queued', 'running', 'completed', 'failed'] as const;
const RECENT_REVIEW_LIMIT = 5;

function yesNo(value: boolean): string {
  return value ? '예' : '아니요';
}

function AgentPanel({ data }: { data: StatusPayload }) {
  return (
    <section className="panel" aria-labelledby="agent-title">
      <div className="panel-head">
        <h2 id="agent-title">선택된 에이전트</h2>
        <ReadyBadge ready={data.ready} readyLabel="리뷰 실행 준비됨" notReadyLabel="리뷰 실행 준비 안 됨" />
      </div>
      <p className="agent-name" translate="no">
        {data.agent ?? '없음'}
      </p>
      <dl className="facts">
        <dt>실행기</dt>
        <dd>{data.runner ? <code translate="no">{data.runner}</code> : '—'}</dd>
        <dt>상태</dt>
        <dd>{data.reason ?? (data.ready ? '연결 준비 완료' : '—')}</dd>
      </dl>
    </section>
  );
}

function RuntimePanel({ data }: { data: StatusPayload }) {
  const pdfReady = data.pdf_reader_ready === true;
  return (
    <section className="panel" aria-labelledby="runtime-title">
      <div className="panel-head">
        <h2 id="runtime-title">실행 환경</h2>
      </div>
      <dl className="facts">
        <dt>PDF 읽기</dt>
        <dd className="fact-inline">
          <code translate="no">{data.pdf_reader}</code>
          <ReadyBadge ready={pdfReady} readyLabel="설치됨" notReadyLabel="설치 필요" />
        </dd>
        <dt>동시 리뷰</dt>
        <dd>
          최대 <span className="num">{formatCount(data.max_parallel)}</span>개
        </dd>
      </dl>
    </section>
  );
}

function RoleStateDetail({ slot, resolution }: { slot: RoleCardSlot; resolution: RoleResolution }) {
  const candidate = selectedCandidate(resolution);
  if (candidate) return <>{slot.readyText}</>;
  if (resolution.candidates.length === 0) return <>역할에 연결된 모델이 없습니다.</>;
  if (resolution.candidates.length > 1) return <>준비된 후보가 없습니다. 아래 후보별 안내를 확인하세요.</>;
  const only = resolution.candidates[0];
  return <>{only.reason || `${only.runner} CLI가 준비되지 않았습니다.`}</>;
}

function RoleSection({ slot, resolution, data }: { slot: RoleCardSlot; resolution: RoleResolution; data: StatusPayload }) {
  const state = roleState(resolution);
  // With several unready candidates no single model is "the" model; the candidate list shows them.
  const shown = selectedCandidate(resolution) ?? (resolution.candidates.length === 1 ? resolution.candidates[0] : null);
  const titleId = `role-${slot.key}-title`;
  return (
    <section className="role-section" aria-labelledby={titleId}>
      <div className="role-head">
        <h3 id={titleId}>{slot.title}</h3>
        <RoleStateBadge state={state} />
      </div>
      <dl className="facts">
        <dt>에이전트</dt>
        <dd>
          <code translate="no">{resolution.agent_name}</code>
        </dd>
        {state === 'config_error' ? (
          <>
            <dt>구성</dt>
            <dd>설정을 읽지 못해 알 수 없음 — 위 오류를 확인하세요.</dd>
          </>
        ) : state === 'unconfigured' ? (
          <>
            <dt>구성</dt>
            <dd>{slot.unconfigured}</dd>
          </>
        ) : (
          <>
            <dt>모델 역할</dt>
            <dd>
              {resolution.role ? <code translate="no">@{resolution.role}</code> : '역할 없이 모델을 직접 지정'}
            </dd>
            <dt>모델</dt>
            <dd>{shown ? <code translate="no">{shown.selector}</code> : '없음'}</dd>
            <dt>실행기</dt>
            <dd>
              {shown ? (
                <>
                  <code translate="no">{shown.runner}</code> CLI
                </>
              ) : (
                '—'
              )}
            </dd>
            <dt>상태</dt>
            <dd>
              <RoleStateDetail slot={slot} resolution={resolution} />
            </dd>
          </>
        )}
      </dl>

      {state === 'unavailable' ? <p className="role-hint">{slot.blockedText}</p> : null}
      {state === 'unconfigured' ? (
        <p className="role-hint">
          {slot.connectedUse ? (
            <>
              {slot.connectedUse.subject} 연결된 에이전트
              {data.agent ? (
                <>
                  {' '}
                  <code translate="no">{data.agent}</code>
                </>
              ) : null}
              {slot.connectedUse.predicate}
            </>
          ) : (
            '리뷰를 원문 PDF와 대조하는 독립 검증을 실행하지 않습니다.'
          )}{' '}
          <code translate="no">task.agentModelOverrides</code>에 <code translate="no">{resolution.agent_name}</code>
          를 추가하면 이 역할을 씁니다.
        </p>
      ) : null}

      {resolution.candidates.length > 1 ? (
        <>
          <h4 className="role-subheading">후보 순서</h4>
          <ol className="role-candidates">
            {resolution.candidates.map((candidate, index) => (
              <li key={`${index}:${candidate.selector}`}>
                <span className="role-candidate-main">
                  <code translate="no">{candidate.selector}</code>
                  <span className="meta" translate="no">
                    {candidate.runner}
                  </span>
                  <ReadyBadge ready={candidate.ready} />
                  {index === resolution.selected ? <span className="meta">(사용 중)</span> : null}
                </span>
                {!candidate.ready && candidate.reason ? (
                  <span className="role-candidate-reason">{candidate.reason}</span>
                ) : null}
              </li>
            ))}
          </ol>
          <p className="field-hint">사용량 한도로 응답 없이 실패하면 다음 후보로 넘어갑니다.</p>
        </>
      ) : null}

      {resolution.notes.length > 0 ? (
        <>
          <h4 className="role-subheading">참고</h4>
          <ul className="role-notes">
            {resolution.notes.map((note, index) => (
              <li key={`${index}:${note}`}>{note}</li>
            ))}
          </ul>
        </>
      ) : null}
    </section>
  );
}

function ReviewRolesPanel({ data }: { data: StatusPayload }) {
  const roles = data.review_roles;
  const source = roles?.generation.source;
  const cards: { slot: RoleCardSlot; resolution: RoleResolution }[] = roles
    ? REVIEW_ROLE_SLOTS.map((slot) => ({ slot, resolution: roles[slot.key] }))
    : [];
  // Harness agents outside the review pipeline; a server that predates one omits its resolution.
  const extraSlots = [
    { slot: READER_ROLE_SLOT, resolution: data.reader_role },
    { slot: SEARCHER_ROLE_SLOT, resolution: data.searcher_role },
    { slot: VISUAL_ROLE_SLOT, resolution: data.visual_role },
  ];
  if (roles) {
    for (const { slot, resolution } of extraSlots) if (resolution) cards.push({ slot, resolution });
  }
  const missingSlots = extraSlots.filter(({ resolution }) => resolution === null).map(({ slot }) => slot);
  // The roles share one config read, so they usually carry the same error; show each text once.
  const configErrors = [...new Set(cards.map(({ resolution }) => resolution.error).filter((error) => error !== null))];
  return (
    <section className="panel" aria-labelledby="roles-title">
      <div className="panel-head">
        <h2 id="roles-title">논문 역할 구성</h2>
        {source ? (
          <span className="meta">
            출처{' '}
            {source === 'omp-config' ? (
              <>
                <code translate="no">.omp/config.yml</code> (omp 설정)
              </>
            ) : (
              <code translate="no">{source}</code>
            )}
          </span>
        ) : null}
      </div>
      {roles ? (
        <>
          <p className="field-hint role-intro">
            하네스의 리뷰·리더·탐색·시각 요약 에이전트 설정을 omp에서 읽어 그대로 따릅니다. 설정된 역할이 연결된
            에이전트보다 우선합니다.
          </p>
          {configErrors.length > 0 ? (
            <div className="notice role-config-error" data-tone="danger">
              <p className="notice-title">omp 설정을 읽지 못했습니다.</p>
              {configErrors.map((error) => (
                <p className="notice-detail role-config-error-text" key={error}>
                  {error}
                </p>
              ))}
              <p>
                설정을 읽지 못한 역할은 미설정으로 간주하지 않습니다. 설정을 다시 읽을 때까지 논문 리뷰, 리뷰 검증, 리더
                질문, 논문 탐색 검색, 시각 요약 만들기를 시작하지 않습니다. 터미널에서{' '}
                <code translate="no">omp config get task.agentModelOverrides --json</code>이 동작하는지 확인한 뒤 ‘새로
                고침’을 누르세요.
              </p>
            </div>
          ) : null}
          <div className="role-grid">
            {cards.map(({ slot, resolution }) => (
              <RoleSection key={slot.key} slot={slot} resolution={resolution} data={data} />
            ))}
            {missingSlots.map((slot) => (
              <section className="role-section" aria-labelledby={`role-${slot.key}-title`} key={slot.key}>
                <div className="role-head">
                  <h3 id={`role-${slot.key}-title`}>{slot.title}</h3>
                </div>
                <p className="role-hint">
                  서버가 <code translate="no">{slot.agent}</code> 구성을 보내지 않았습니다. WebUI 서버를 다시 시작하세요.
                </p>
              </section>
            ))}
          </div>
        </>
      ) : (
        <p className="empty empty-compact">서버가 논문 리뷰 구성을 보내지 않았습니다. WebUI 서버를 다시 시작하세요.</p>
      )}
    </section>
  );
}

function CandidateGuide({ candidate }: { candidate: AgentCandidate }) {
  const needsLogin = candidate.installed && !candidate.authenticated && candidate.login_command;
  return (
    <>
      {candidate.reason ? <span>{candidate.reason}</span> : null}
      {needsLogin ? (
        <span className="login-hint">
          로그인 명령 <code translate="no">{candidate.login_command}</code>
        </span>
      ) : null}
    </>
  );
}

function CandidatesPanel({ data }: { data: StatusPayload }) {
  return (
    <section className="panel" aria-labelledby="candidates-title">
      <div className="panel-head">
        <h2 id="candidates-title">에이전트 후보</h2>
        <span className="meta">
          준비됨 <span className="num">{formatCount(data.candidates.filter((c) => c.ready).length)}</span> /{' '}
          <span className="num">{formatCount(data.candidates.length)}</span>
        </span>
      </div>
      {data.candidates.length === 0 ? (
        <p className="empty empty-compact">확인할 에이전트 후보가 없습니다. {data.reason}</p>
      ) : (
        <div className="table-scroll" tabIndex={0} role="region" aria-labelledby="candidates-title">
          <table>
            <caption className="visually-hidden">에이전트 CLI별 설치·로그인·호환 상태</caption>
            <thead>
              <tr>
                <th scope="col">에이전트</th>
                <th scope="col">설치</th>
                <th scope="col">로그인</th>
                <th scope="col">호환</th>
                <th scope="col">상태</th>
                <th scope="col">안내</th>
              </tr>
            </thead>
            <tbody>
              {data.candidates.map((candidate) => (
                <tr key={candidate.agent}>
                  <th scope="row">
                    <span translate="no">{candidate.agent}</span>
                    {candidate.agent === data.agent ? <span className="meta"> (선택됨)</span> : null}
                  </th>
                  <td>{yesNo(candidate.installed)}</td>
                  <td>{yesNo(candidate.authenticated)}</td>
                  <td>{yesNo(candidate.compatible)}</td>
                  <td>
                    <ReadyBadge ready={candidate.ready} />
                  </td>
                  <td className="candidate-guide">
                    <CandidateGuide candidate={candidate} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function QueuePanel({ data }: { data: StatusPayload }) {
  const jobs = data.queue.jobs;
  const counts = new Map<string, number>();
  for (const job of jobs) counts.set(job.status, (counts.get(job.status) ?? 0) + 1);
  const otherCount = jobs.filter((job) => !(QUEUE_STATUSES as readonly string[]).includes(job.status)).length;
  // Queue entries are appended in order; created_at (ISO-8601) breaks ties after edits.
  const recent: ReviewQueueJob[] = jobs
    .map((job, index) => ({ job, index }))
    .sort((a, b) => (b.job.created_at ?? '').localeCompare(a.job.created_at ?? '') || b.index - a.index)
    .slice(0, RECENT_REVIEW_LIMIT)
    .map(({ job }) => job);

  return (
    <section className="panel" aria-labelledby="queue-title">
      <div className="panel-head">
        <h2 id="queue-title">리뷰 대기열</h2>
        <span className="meta">
          전체 <span className="num">{formatCount(jobs.length)}</span>건
        </span>
      </div>
      <ul className="stats queue-stats">
        {QUEUE_STATUSES.map((status) => (
          <li className="stat" key={status}>
            <span>{statusLabel(status)}</span>
            <strong className="num">{formatCount(counts.get(status) ?? 0)}</strong>
          </li>
        ))}
        {otherCount > 0 ? (
          <li className="stat">
            <span>기타</span>
            <strong className="num">{formatCount(otherCount)}</strong>
          </li>
        ) : null}
      </ul>
      <h3 className="subheading">최근 리뷰 작업</h3>
      {recent.length === 0 ? (
        <p className="empty empty-compact">
          리뷰 작업 기록이 없습니다. <a href={PAPERS_HREF}>논문 라이브러리</a>에서 리뷰를 시작하면
          여기에 표시됩니다.
        </p>
      ) : (
        <ol className="queue-list">
          {recent.map((job) => {
            const model = job.generation ? (job.generation.selector ?? job.generation.runner) : job.agent;
            return (
              <li className="queue-item" key={job.job_id}>
                <code translate="no">{job.slug}</code>
                <span className="queue-badges">
                  <StatusBadge status={job.status} />
                  {job.verification ? <VerificationBadge verification={job.verification} /> : null}
                </span>
                <span className="queue-time meta">
                  {job.kind === 'verify' ? '검증만 실행 · ' : null}
                  {job.kind !== 'verify' && model ? (
                    <>
                      {job.generation ? '생성 ' : null}
                      <span translate="no">{model}</span>
                      {' · '}
                    </>
                  ) : null}
                  {formatDateTime(job.completed_at ?? job.updated_at ?? job.started_at ?? job.created_at)}
                </span>
                {job.verification ? <VerificationLine verification={job.verification} /> : null}
                {job.message ? <QueueMessage message={job.message} /> : null}
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

/** Workspace and port of the server this page talks to (moved here from the global header). */
function SessionFacts({ connection }: { connection: ConnectionSnapshot }) {
  const { session, sessionError, state } = connection;
  return (
    <dl className="session-facts">
      <div>
        <dt>작업 공간</dt>
        <dd>
          {session ? (
            <code translate="no">{session.workspace_id || '—'}</code>
          ) : sessionError && state !== 'offline' ? (
            <span>세션을 열지 못했습니다 ({sessionError.message})</span>
          ) : (
            '확인 중…'
          )}
        </dd>
      </div>
      {session?.port ? (
        <div>
          <dt>포트</dt>
          <dd className="num">{session.port}</dd>
        </div>
      ) : null}
      {session?.version ? (
        <div>
          <dt>버전</dt>
          <dd>
            <code translate="no">{session.version}</code>
          </dd>
        </div>
      ) : null}
    </dl>
  );
}

export function StatusScreen({ headingRef, connection }: { headingRef: Ref<HTMLHeadingElement>; connection: ConnectionSnapshot }) {
  const { data, error, loading, checkedAt, refresh } = useStatus();
  return (
    <div className="screen">
      <ScreenHeader
        eyebrow="research_webui.py serve"
        title="상태"
        description="에이전트 CLI 연결, 논문 리뷰 구성, PDF 도구, 리뷰 대기열을 한 화면에서 확인합니다."
        headingRef={headingRef}
        meta={<SessionFacts connection={connection} />}
      >
        <button type="button" className="btn btn-primary" onClick={refresh} disabled={loading} aria-busy={loading}>
          <RefreshCw />
          {loading ? '확인하는 중…' : '새로 고침'}
        </button>
      </ScreenHeader>

      <p className="screen-meta" role="status">
        {loading
          ? '에이전트 CLI 상태를 확인하는 중… 몇 초 걸릴 수 있습니다.'
          : checkedAt
            ? `마지막 확인 ${formatTime(checkedAt)}`
            : ''}
      </p>
      {loading ? <span className="ai-progress screen-progress" aria-hidden="true" /> : null}

      {error && error.code !== 'offline' ? (
        <ErrorNotice
          error={error}
          title={data ? '상태를 다시 확인하지 못했습니다. 아래는 이전 결과입니다.' : '상태를 확인하지 못했습니다.'}
          onRetry={refresh}
        />
      ) : null}

      {data ? (
        <div className="stack">
          <div className="status-grid">
            <AgentPanel data={data} />
            <RuntimePanel data={data} />
          </div>
          <ReviewRolesPanel data={data} />
          <CandidatesPanel data={data} />
          <QueuePanel data={data} />
        </div>
      ) : loading ? (
        <div className="stack" aria-hidden="true">
          <div className="status-grid">
            <Skeleton height="11rem" radius="var(--radius-md)" />
            <Skeleton height="11rem" radius="var(--radius-md)" />
          </div>
          <Skeleton height="16rem" radius="var(--radius-md)" />
        </div>
      ) : error?.code === 'offline' ? (
        <p className="empty">서버를 실행하고 ‘다시 연결’을 누르면 상태를 다시 확인합니다.</p>
      ) : null}
    </div>
  );
}
