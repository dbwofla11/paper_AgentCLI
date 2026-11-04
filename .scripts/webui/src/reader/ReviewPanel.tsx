import { memo, useEffect, useId, useState } from 'react';
import { MessageSquareText as IconAsk, RotateCw, ShieldCheck } from 'lucide-react';
import type { ApiError } from '../api/client';
import type { ClaimVerdict, EvidenceItem, PaperBundle, ReviewQueueJob, VerificationReport } from '../api/types';
import { VerificationBadge } from '../components/Badges';
import { ErrorNotice } from '../components/ErrorNotice';
import { formatCount, formatDateTime, type Tone } from '../format';
import { STATUS_HREF } from '../hooks/useHashRoute';
import { VERIFY_ERRORS } from '../verification';
import { useReader } from './context';
import { AXES, CLAIM_KIND_LABELS, locatorChips, untargetedEvidence, type LocatorChip } from './evidence';
import { LinkedText, ReaderMarkdown } from './RichText';

export type ReviewView = 'evidence' | 'review' | 'verification';

/** State of the reader's 검증 실행 control (owned by ReaderScreen so polling survives tab switches). */
export interface VerifyControl {
  /** Latest known verify job of this paper. */
  job: ReviewQueueJob | null;
  pending: boolean;
  error: ApiError | null;
  /** Why a run cannot start (paper files or verifier role); null when it can. */
  blocked: string | null;
  /**
   * What the hint offers: `recheck` when the status check failed (one manual GET /api/status; it is
   * never polled), `status` when the verifier role itself is not ready, null for paper-file reasons.
   */
  blockedFix: 'recheck' | 'status' | null;
  onStart: () => void;
  onRecheck: () => void;
}

const VERDICTS: Record<ClaimVerdict, { label: string; tone: Tone }> = {
  supported: { label: '일치', tone: 'success' },
  mismatch: { label: '불일치', tone: 'danger' },
  unsupported: { label: '근거 없음', tone: 'warning' },
  unverifiable: { label: '확인 불가', tone: 'neutral' },
};

const STATUS_NOTES: Record<string, string> = {
  page_only: '쪽만 확인',
  unresolved: '위치 미확인',
};

function chipTitle(chip: LocatorChip, pageCount: number): string {
  const parts = [`리뷰 근거 위치: ${chip.locator || chip.label}`];
  if (chip.relocatedFrom.length > 0) {
    parts.push(`적힌 쪽(p.${chip.relocatedFrom.join(', ')})에서 찾지 못해 다른 쪽으로 옮겼습니다.`);
  }
  if (chip.pages.length === 0) parts.push('PDF에서 위치를 찾지 못했습니다.');
  else if (pageCount > 0 && chip.pages[0] > pageCount) parts.push(`PDF는 ${pageCount}쪽까지 있습니다.`);
  return parts.join(' ');
}

function ClaimCard({
  item,
  focused,
  pulse,
  onAsk,
}: {
  item: EvidenceItem;
  focused: boolean;
  pulse: number;
  onAsk: (item: EvidenceItem) => void;
}) {
  const { pageCount, goToPage } = useReader();
  const chips = locatorChips(item);
  const loose = untargetedEvidence(item);
  const note = STATUS_NOTES[item.status];
  return (
    <article
      id={`claim-${item.claim_id}`}
      className="claim-card"
      tabIndex={-1}
      data-active={focused ? 'true' : undefined}
      data-pulse={pulse > 0 ? String(pulse % 2) : undefined}
      aria-label={`리뷰 근거: ${item.statement}`}
    >
      <div className="claim-head">
        <span className="claim-kind" data-kind={item.kind}>
          {CLAIM_KIND_LABELS[item.kind] ?? item.kind}
        </span>
        {note ? (
          <span className="claim-status" data-status={item.status}>
            {note}
          </span>
        ) : null}
      </div>
      <p className="claim-statement">
        <LinkedText text={item.statement} />
      </p>
      {chips.length > 0 || loose.length > 0 ? (
        <div className="claim-chips">
          {chips.map((chip) => {
            const page = chip.pages[0];
            const available = page !== undefined && page <= pageCount;
            return (
              <button
                key={chip.keys.join(' ')}
                type="button"
                className="locator-chip"
                data-confidence={chip.confidence}
                data-relocated={chip.relocatedFrom.length > 0 ? 'true' : undefined}
                disabled={!available}
                title={chipTitle(chip, pageCount)}
                onClick={() => goToPage(page, chip.keys)}
              >
                {chip.label}
              </button>
            );
          })}
          {loose.map((locator, index) => (
            <span key={`${index}:${locator}`} className="locator-text">
              <LinkedText text={locator} />
            </span>
          ))}
        </div>
      ) : null}
      <div className="claim-actions">
        <button type="button" className="text-btn" onClick={() => onAsk(item)}>
          <IconAsk />이 근거 질문하기
        </button>
      </div>
    </article>
  );
}

const EvidenceList = memo(function EvidenceList({
  bundle,
  activeClaimId,
  focusRequest,
  onFocusHandled,
  onAskClaim,
}: {
  bundle: PaperBundle;
  activeClaimId: string | null;
  /** Claim to scroll to and focus once (a highlight click); cleared through `onFocusHandled`. */
  focusRequest: string | null;
  onFocusHandled: () => void;
  onAskClaim: (item: EvidenceItem) => void;
}) {
  const items = bundle.evidence.items;
  const [pulse, setPulse] = useState<{ claimId: string; count: number } | null>(null);

  useEffect(() => {
    if (!focusRequest) return;
    onFocusHandled();
    const card = document.getElementById(`claim-${focusRequest}`);
    if (!card) return;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    card.scrollIntoView({ block: 'center', behavior: reduced ? 'auto' : 'smooth' });
    card.focus({ preventScroll: true });
    setPulse((previous) => ({
      claimId: focusRequest,
      count: previous?.claimId === focusRequest ? previous.count + 1 : 1,
    }));
  }, [focusRequest, onFocusHandled]);

  if (items.length === 0) {
    return <p className="panel-empty">이 리뷰에는 근거 위치가 적힌 주장이 없습니다.</p>;
  }
  const { matched, page_only: pageOnly, unresolved } = bundle.evidence.summary;
  const known = new Set(AXES.map((axis) => axis.key));
  const groups = [
    ...AXES.map((axis) => ({ ...axis, items: items.filter((item) => item.axis === axis.key) })),
    { key: 'other', title: '기타', items: items.filter((item) => !known.has(item.axis)) },
  ].filter((group) => group.items.length > 0);
  const review = bundle.paper.review ?? {};

  return (
    <div className="evidence-list">
      <p className="evidence-summary meta">
        근거 <span className="num">{formatCount(items.length)}</span>개 · 위치 찾음{' '}
        <span className="num">{formatCount(matched)}</span> · 쪽만 <span className="num">{formatCount(pageOnly)}</span> ·
        미확인 <span className="num">{formatCount(unresolved)}</span>
      </p>
      {groups.map((group, index) => {
        const summary = (review as Record<string, { summary?: string } | undefined>)[group.key]?.summary;
        return (
          <section key={group.key} className="axis-section" aria-labelledby={`axis-${group.key}`}>
            <h3 id={`axis-${group.key}`} className="axis-title">
              <span className="axis-number num" aria-hidden="true">
                {group.key === 'other' ? '·' : index + 1}
              </span>
              {group.title}
              <span className="axis-count num">{formatCount(group.items.length)}</span>
            </h3>
            {summary ? (
              <p className="axis-summary">
                <LinkedText text={summary} />
              </p>
            ) : null}
            <div className="claim-stack">
              {group.items.map((item) => (
                <ClaimCard
                  key={item.claim_id}
                  item={item}
                  focused={activeClaimId === item.claim_id}
                  pulse={pulse?.claimId === item.claim_id ? pulse.count : 0}
                  onAsk={onAskClaim}
                />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
});

function VerificationView({ report }: { report: VerificationReport | null }) {
  if (!report) {
    return (
      <p className="panel-empty">
        이 리뷰는 아직 원문과 대조 검증하지 않았습니다. 위의 ‘검증 실행’을 누르면 검증 역할(paper-verifier)이 리뷰의
        주장을 원문 PDF와 대조합니다. 리뷰 문서는 바꾸지 않고 검증 보고서만 새로 씁니다.
      </p>
    );
  }
  const result = report.result;
  return (
    <div className="verification-view">
      {report.verifier.selector || report.verifier.runner ? (
        <p className="meta verification-by">
          검증 모델 <span translate="no">{report.verifier.selector ?? report.verifier.runner}</span>
        </p>
      ) : null}
      {report.summary.stale ? (
        <p className="verification-note">검증한 뒤 리뷰나 PDF가 바뀌었습니다. 아래 결과는 이전 버전 기준입니다.</p>
      ) : null}
      {report.error ? <p className="verification-error">{report.error}</p> : null}
      {result ? (
        <>
          {result.summary ? (
            <p className="verification-summary">
              <LinkedText text={result.summary} />
            </p>
          ) : null}
          {result.blocking_issues.length > 0 ? (
            <>
              <h3 className="panel-subheading">수정이 필요한 문제</h3>
              <ul className="verification-issues">
                {result.blocking_issues.map((issue, index) => (
                  <li key={`${index}:${issue}`}>
                    <LinkedText text={issue} />
                  </li>
                ))}
              </ul>
            </>
          ) : null}
          <h3 className="panel-subheading">
            대조한 주장 <span className="num">{formatCount(result.checked_claims.length)}</span>개
          </h3>
          <ol className="verdict-list">
            {result.checked_claims.map((claim, index) => {
              const verdict = VERDICTS[claim.verdict] ?? { label: claim.verdict, tone: 'neutral' as Tone };
              return (
                <li key={`${index}:${claim.claim}`} className="verdict-item">
                  <div className="verdict-head">
                    <span className="badge" data-tone={verdict.tone}>
                      {verdict.label}
                    </span>
                    <span className="verdict-locator">
                      <LinkedText text={claim.locator} />
                    </span>
                  </div>
                  <p className="verdict-claim">
                    <LinkedText text={claim.claim} />
                  </p>
                  {claim.note ? (
                    <p className="verdict-note">
                      <LinkedText text={claim.note} />
                    </p>
                  ) : null}
                </li>
              );
            })}
          </ol>
        </>
      ) : null}
    </div>
  );
}

const VIEWS: ReadonlyArray<{ key: ReviewView; label: string }> = [
  { key: 'evidence', label: '근거' },
  { key: 'review', label: '리뷰 전문' },
  { key: 'verification', label: '검증' },
];

function VerifyProgress({ job }: { job: ReviewQueueJob }) {
  const running = job.status === 'running';
  return (
    <div className="review-verify-progress" role="status">
      <span className="ai-progress" aria-hidden="true" />
      <p className="meta">
        {running ? '리뷰를 원문 PDF와 대조하는 중…' : '리뷰 대기열에서 검증 순서를 기다리는 중…'}
        {running && job.started_at ? ` 시작 ${formatDateTime(job.started_at)}` : ''}
      </p>
    </div>
  );
}

/** Verification state of the review and its 검증 실행 control, always visible at the top of the 리뷰 tab. */
function ReviewHeader({
  report,
  view,
  onViewChange,
  verify,
}: {
  report: VerificationReport | null;
  view: ReviewView;
  onViewChange: (view: ReviewView) => void;
  verify: VerifyControl;
}) {
  const hintId = useId();
  const summary = report?.summary ?? null;
  const { job, blocked, error } = verify;
  const running = job !== null && (job.status === 'queued' || job.status === 'running');
  const failed = job !== null && job.status === 'failed';
  const label = verify.pending ? '요청하는 중…' : running ? '검증 중…' : report ? '다시 검증' : '검증 실행';
  return (
    <div className="review-header">
      <div className="review-header-row">
        <span className="review-header-badges">
          {summary ? (
            <VerificationBadge verification={summary} />
          ) : (
            <span className="badge" data-tone="neutral">
              검증 기록 없음
            </span>
          )}
          {summary?.stale ? (
            <span className="badge" data-tone="warning">
              검증 이후 변경됨
            </span>
          ) : null}
        </span>
        <span className="review-header-actions">
          {view === 'verification' ? (
            report ? (
              <span className="meta review-header-meta">{formatDateTime(report.verified_at)} 검증</span>
            ) : null
          ) : (
            <button type="button" className="text-btn review-header-link" onClick={() => onViewChange('verification')}>
              {summary ? '검증 결과 보기' : '검증 안내'}
            </button>
          )}
          <button
            type="button"
            className="btn btn-tonal btn-small"
            onClick={verify.onStart}
            disabled={blocked !== null || verify.pending || running}
            aria-busy={verify.pending || running}
            aria-describedby={blocked && !running ? hintId : undefined}
          >
            <ShieldCheck />
            {label}
          </button>
        </span>
      </div>
      {running ? <VerifyProgress job={job} /> : null}
      {blocked && !running ? (
        <p className="field-hint review-verify-hint" id={hintId}>
          {blocked}
          {verify.blockedFix === 'recheck' ? (
            <>
              {' '}
              <button type="button" className="text-btn" onClick={verify.onRecheck}>
                <RotateCw aria-hidden="true" />
                다시 확인
              </button>
            </>
          ) : verify.blockedFix === 'status' ? (
            <>
              {' '}
              <a href={STATUS_HREF}>상태 화면에서 확인</a>
            </>
          ) : null}
        </p>
      ) : null}
      {failed && !error ? (
        <p className="field-error review-verify-hint" role="status">
          마지막 검증이 실패했습니다.{job.message ? ` ${job.message.slice(0, 240)}` : ''}{' '}
          <a href={STATUS_HREF}>상태 화면의 리뷰 대기열</a>
        </p>
      ) : null}
      {error ? <ErrorNotice error={error} title={VERIFY_ERRORS[error.code] ?? '검증을 시작하지 못했습니다.'} /> : null}
    </div>
  );
}

export function ReviewPanel({
  bundle,
  view,
  onViewChange,
  activeClaimId,
  focusRequest,
  onFocusHandled,
  onAskClaim,
  verify,
}: {
  bundle: PaperBundle;
  view: ReviewView;
  onViewChange: (view: ReviewView) => void;
  activeClaimId: string | null;
  focusRequest: string | null;
  onFocusHandled: () => void;
  onAskClaim: (item: EvidenceItem) => void;
  verify: VerifyControl;
}) {
  const markdown = bundle.review.markdown;
  return (
    <div className="review-panel">
      <ReviewHeader report={bundle.verification} view={view} onViewChange={onViewChange} verify={verify} />
      <div className="segmented" role="group" aria-label="리뷰 보기">
        {VIEWS.map((item) => (
          <button
            key={item.key}
            type="button"
            className="segmented-btn"
            aria-pressed={view === item.key}
            onClick={() => onViewChange(item.key)}
          >
            {item.label}
            {item.key === 'evidence' ? (
              <span className="segmented-count num">{formatCount(bundle.evidence.items.length)}</span>
            ) : null}
          </button>
        ))}
      </div>
      {view === 'evidence' ? (
        <EvidenceList
          bundle={bundle}
          activeClaimId={activeClaimId}
          focusRequest={focusRequest}
          onFocusHandled={onFocusHandled}
          onAskClaim={onAskClaim}
        />
      ) : null}
      {view === 'review' ? (
        markdown ? (
          <ReaderMarkdown markdown={markdown} className="review-md" />
        ) : (
          <p className="panel-empty">
            심층 리뷰 파일이 없습니다.
            {bundle.review.path ? (
              <>
                {' '}
                <code translate="no">{bundle.review.path}</code>
              </>
            ) : null}
          </p>
        )
      ) : null}
      {view === 'verification' ? <VerificationView report={bundle.verification} /> : null}
    </div>
  );
}
