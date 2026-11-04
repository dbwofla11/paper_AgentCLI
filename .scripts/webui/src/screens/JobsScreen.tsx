import { useCallback, useEffect, useRef, useState, type Ref, type SubmitEventHandler } from 'react';
import { createJob, fetchJobs, isAbortError, toApiError, type ApiError } from '../api/client';
import {
  isAgentName,
  isReviewRoleAgent,
  type AgentName,
  type CreateJobRequest,
  type JobRecord,
  type ReviewRoleAgent,
} from '../api/types';
import { StatusBadge } from '../components/Badges';
import { ErrorNotice } from '../components/ErrorNotice';
import { ScreenHeader } from '../components/ScreenHeader';
import { formatCost, formatCount, formatDateTime, jobKindLabel } from '../format';
import { STATUS_HREF, jobHref } from '../hooks/useHashRoute';
import { REVIEW_ROLE_SLOTS, blockedReason, roleState, selectedCandidate } from '../roles';
import { useStatus } from '../status';
import { JobDetail } from './JobDetail';

const LIST_PAGE_SIZE = 50;
/** List refresh interval while any job is queued or running. */
const ACTIVE_POLL_MS = 4_000;

/** '' = the connected agent's default model. */
type PingTarget = '' | AgentName | ReviewRoleAgent;

function PingForm({ onCreated }: { onCreated: (job: JobRecord) => void }) {
  const { data, error, loading } = useStatus();
  const [target, setTarget] = useState<PingTarget>('');
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<ApiError | null>(null);

  const readyAgents = (data?.candidates ?? [])
    .filter((candidate) => candidate.ready)
    .map((candidate) => candidate.agent)
    .filter(isAgentName);
  // A role is pingable only with a ready selected candidate. `blocked` explains why not;
  // `note` is the short form appended to the disabled option.
  const roleTargets = REVIEW_ROLE_SLOTS.map((slot) => {
    const resolution = data?.review_roles?.[slot.key] ?? null;
    const candidate = resolution ? selectedCandidate(resolution) : null;
    if (!data) return { slot, candidate, blocked: '상태를 확인하는 중…', note: '확인 중…' };
    if (!resolution) return { slot, candidate, blocked: '서버가 논문 리뷰 구성을 보내지 않았습니다.', note: '사용 불가' };
    switch (roleState(resolution)) {
      case 'ready':
        return { slot, candidate, blocked: null, note: null };
      case 'unconfigured':
        return { slot, candidate, blocked: slot.unconfigured, note: slot.unconfigured };
      case 'config_error':
        return { slot, candidate, blocked: blockedReason(resolution) ?? '설정 읽기 실패', note: '설정 읽기 실패' };
      case 'unavailable':
        return { slot, candidate, blocked: blockedReason(resolution) ?? '사용 불가', note: '사용 불가' };
    }
  });
  const roleTarget = roleTargets.find(({ slot, blocked }) => slot.agent === target && blocked === null) ?? null;
  const selected: PingTarget = roleTarget
    ? roleTarget.slot.agent
    : isAgentName(target) && readyAgents.includes(target)
      ? target
      : '';
  const canSubmit = readyAgents.length > 0 || roleTargets.some(({ blocked }) => blocked === null);
  const blockedRoles = data ? roleTargets.filter(({ blocked }) => blocked !== null) : [];
  const unavailable = canSubmit
    ? null
    : data
      ? `준비된 에이전트가 없습니다. ${data.reason ?? ''}`
      : loading
        ? '에이전트 상태를 확인하는 중…'
        : error
          ? '에이전트 상태를 확인하지 못했습니다.'
          : null;

  const submit: SubmitEventHandler<HTMLFormElement> = async (event) => {
    event.preventDefault();
    if (!canSubmit || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    const payload: CreateJobRequest = isReviewRoleAgent(selected)
      ? { kind: 'agent.ping', role: selected }
      : selected
        ? { kind: 'agent.ping', agent: selected }
        : { kind: 'agent.ping' };
    try {
      onCreated(await createJob(payload));
    } catch (failure) {
      setSubmitError(toApiError(failure));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <form className="panel ping-form" onSubmit={submit} aria-labelledby="ping-title" noValidate>
      <h2 id="ping-title">에이전트 연결 확인</h2>
      <p className="field-hint">
        도구 없이 짧은 질문을 보내 에이전트 CLI의 로그인과 응답 스트림을 확인합니다. 리뷰 역할을 고르면 그 역할의
        모델로 확인합니다.
      </p>
      <label htmlFor="ping-agent">확인 대상</label>
      <select
        id="ping-agent"
        name="target"
        value={selected}
        onChange={(event) => {
          const value = event.currentTarget.value;
          setTarget(isAgentName(value) || isReviewRoleAgent(value) ? value : '');
        }}
        disabled={!canSubmit || submitting}
        aria-describedby={blockedRoles.length > 0 ? 'ping-agent-help ping-role-help' : 'ping-agent-help'}
      >
        <optgroup label="논문 리뷰 역할">
          {roleTargets.map(({ slot, blocked, note }) => (
            <option key={slot.agent} value={slot.agent} disabled={blocked !== null}>
              {note === null ? slot.targetLabel : `${slot.targetLabel} · ${note}`}
            </option>
          ))}
        </optgroup>
        <optgroup label="연결된 에이전트">
          <option value="">{`기본 에이전트${data?.agent ? ` (${data.agent})` : ''}`}</option>
          {readyAgents.map((name) => (
            <option key={name} value={name}>
              {name}
            </option>
          ))}
        </optgroup>
      </select>
      <p id="ping-agent-help" className="field-hint">
        {unavailable ??
          (roleTarget?.candidate ? (
            <>
              <code translate="no">{roleTarget.candidate.selector}</code> 모델을{' '}
              <code translate="no">{roleTarget.candidate.runner}</code> CLI로 확인합니다.
            </>
          ) : (
            '준비가 끝난 역할과 에이전트만 고를 수 있습니다.'
          ))}
        {unavailable && !loading ? (
          <>
            {' '}
            <a href={STATUS_HREF}>상태 화면에서 확인</a>
          </>
        ) : null}
      </p>
      {blockedRoles.length > 0 ? (
        <ul id="ping-role-help" className="field-hint ping-role-help">
          {blockedRoles.map(({ slot, blocked }) => (
            <li key={slot.agent}>
              {slot.targetLabel}: {blocked}
            </li>
          ))}
        </ul>
      ) : null}
      <button
        type="submit"
        className="btn btn-primary"
        disabled={!canSubmit || submitting}
        aria-busy={submitting}
      >
        {submitting ? '요청하는 중…' : '에이전트 연결 확인'}
      </button>
      {submitError ? <ErrorNotice error={submitError} title="작업을 시작하지 못했습니다." /> : null}
    </form>
  );
}

interface JobListProps {
  jobs: JobRecord[] | null;
  loading: boolean;
  error: ApiError | null;
  selectedId: string | null;
  onRetry: () => void;
}

function JobList({ jobs, loading, error, selectedId, onRetry }: JobListProps) {
  const [limit, setLimit] = useState(LIST_PAGE_SIZE);
  const visible = jobs?.slice(0, limit) ?? [];
  return (
    <section className="panel job-list-panel" aria-labelledby="job-list-title">
      <div className="panel-head">
        <h2 id="job-list-title">작업 목록</h2>
        {jobs ? (
          <span className="meta">
            <span className="num">{formatCount(jobs.length)}</span>개
          </span>
        ) : null}
      </div>
      <p className="field-hint">작업 기록은 서버 메모리에만 있어 서버를 다시 시작하면 사라집니다.</p>
      {error && error.code !== 'offline' ? (
        <ErrorNotice error={error} title="작업 목록을 불러오지 못했습니다." onRetry={onRetry} />
      ) : null}
      {jobs === null ? (
        loading ? (
          <p className="loading-text" role="status">
            작업 목록을 불러오는 중…
          </p>
        ) : null
      ) : jobs.length === 0 ? (
        <p className="empty empty-compact">아직 작업이 없습니다. 위에서 ‘에이전트 연결 확인’을 실행하세요.</p>
      ) : (
        <>
          <ul className="job-list">
            {visible.map((job) => {
              const cost = formatCost(job.cost_usd);
              return (
                <li key={job.job_id}>
                  <a
                    className="job-row"
                    href={jobHref(job.job_id)}
                    aria-current={job.job_id === selectedId ? 'true' : undefined}
                  >
                    <span className="job-row-title">{jobKindLabel(job.kind)}</span>
                    <StatusBadge status={job.status} />
                    <span className="job-row-meta">
                      {job.role ? <span translate="no">{job.role} · </span> : null}
                      {job.agent ? <span translate="no">{job.agent} · </span> : null}
                      <span className="num">{formatDateTime(job.created_at)}</span>
                      {cost ? <span className="num"> · {cost}</span> : null}
                    </span>
                  </a>
                </li>
              );
            })}
          </ul>
          {jobs.length > limit ? (
            <button
              type="button"
              className="btn btn-secondary btn-small job-list-more"
              onClick={() => setLimit((current) => current + LIST_PAGE_SIZE)}
            >
              이전 작업 더 보기 (<span className="num">{formatCount(jobs.length - limit)}</span>개 남음)
            </button>
          ) : null}
        </>
      )}
    </section>
  );
}

interface JobsScreenProps {
  headingRef: Ref<HTMLHeadingElement>;
  jobId: string | null;
  /** Changes after a manual reconnect so the list and the selected job reload. */
  reloadToken: number;
}

export function JobsScreen({ headingRef, jobId, reloadToken }: JobsScreenProps) {
  const [jobs, setJobs] = useState<JobRecord[] | null>(null);
  const [listError, setListError] = useState<ApiError | null>(null);
  const [listLoading, setListLoading] = useState(true);
  const latestRequest = useRef(0);
  const detailRef = useRef<HTMLElement>(null);
  const previousJobId = useRef(jobId);

  /** `quiet` reloads (polling, after changes) keep the refresh button idle. */
  const loadJobs = useCallback(async ({ signal, quiet = false }: { signal?: AbortSignal; quiet?: boolean } = {}) => {
    const requestId = ++latestRequest.current;
    if (!quiet) setListLoading(true);
    try {
      const next = await fetchJobs(signal);
      if (requestId !== latestRequest.current) return;
      setJobs(next);
      setListError(null);
    } catch (error) {
      if (isAbortError(error) || requestId !== latestRequest.current) return;
      setListError(toApiError(error));
    } finally {
      if (requestId === latestRequest.current) setListLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void loadJobs({ signal: controller.signal });
    return () => controller.abort();
  }, [loadJobs, reloadToken]);

  const hasActiveJob = jobs?.some((job) => job.status === 'queued' || job.status === 'running') ?? false;
  useEffect(() => {
    if (!hasActiveJob) return;
    const timer = window.setInterval(() => {
      if (document.visibilityState === 'visible') void loadJobs({ quiet: true });
    }, ACTIVE_POLL_MS);
    return () => window.clearInterval(timer);
  }, [hasActiveJob, loadJobs]);

  // Move focus to the detail panel when the selection changes, so its content is announced.
  useEffect(() => {
    if (previousJobId.current === jobId) return;
    previousJobId.current = jobId;
    detailRef.current?.focus();
  }, [jobId]);

  const reloadQuietly = useCallback(() => void loadJobs({ quiet: true }), [loadJobs]);

  const showCreatedJob = (job: JobRecord) => {
    setJobs((current) => [job, ...(current ?? []).filter((item) => item.job_id !== job.job_id)]);
    window.location.hash = jobHref(job.job_id);
    reloadQuietly();
  };

  const selectedRecord = jobId ? (jobs?.find((job) => job.job_id === jobId) ?? null) : null;

  return (
    <div className="screen">
      <ScreenHeader
        eyebrow="/api/jobs"
        title="작업"
        description="에이전트 연결을 확인하고, 응답이 들어오는 과정을 실시간으로 확인합니다. 리뷰 검증은 논문 리더의 리뷰 탭에서 실행합니다."
        headingRef={headingRef}
      >
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => void loadJobs()}
          disabled={listLoading}
          aria-busy={listLoading}
        >
          {listLoading ? '불러오는 중…' : '목록 새로 고침'}
        </button>
      </ScreenHeader>

      <div className="jobs-layout">
        <div className="jobs-side">
          <PingForm onCreated={showCreatedJob} />
          <JobList
            jobs={jobs}
            loading={listLoading}
            error={listError}
            selectedId={jobId}
            onRetry={() => void loadJobs()}
          />
        </div>
        {jobId ? (
          <JobDetail
            key={`${jobId}:${reloadToken}`}
            jobId={jobId}
            initialRecord={selectedRecord}
            sectionRef={detailRef}
            onChanged={reloadQuietly}
          />
        ) : (
          <section className="panel job-detail" ref={detailRef} tabIndex={-1} aria-labelledby="job-empty-title">
            <h2 id="job-empty-title">선택한 작업 없음</h2>
            <p className="empty empty-compact">
              목록에서 작업을 고르면 응답 스트림, 사용한 도구, 비용과 소요 시간이 여기에 표시됩니다.
            </p>
          </section>
        )}
      </div>
    </div>
  );
}
