import { useId } from 'react';
import { ArrowRight, ExternalLink, Sparkles } from 'lucide-react';
import * as m from 'motion/react-m';
import type { ApiError } from '../../api/client';
import type { PaperLabels, PaperSummary, ReviewQueueJob, VerificationStatus } from '../../api/types';
import { formatCount, formatDateTime, type Tone } from '../../format';
import { STATUS_HREF, paperHref } from '../../hooks/useHashRoute';
import { DUR_ENTER, DUR_FILTER, EASE_OUT, staggerDelay } from '../../motion/tokens';
import { categoryLabel, readingStatusLabel } from './stats';

const AUTHOR_LIMIT = 3;
const TOPIC_LIMIT = 4;
/** First-mount stagger stops growing after this many cards. */
const STAGGER_CAP = 11;

const VERIFICATION_BADGES: Record<VerificationStatus, { label: string; tone: Tone }> = {
  passed: { label: '검증 통과', tone: 'success' },
  issues: { label: '검증 이슈', tone: 'warning' },
  error: { label: '검증 오류', tone: 'danger' },
  skipped: { label: '검증 건너뜀', tone: 'neutral' },
};

/** Korean guidance per POST /api/reviews error code (.scripts/docs/webui-api.md). */
const START_ERRORS: Record<string, string> = {
  review_complete: '이미 리뷰가 끝난 논문입니다. 목록을 새로 고쳤습니다.',
  review_active: '다른 논문 리뷰나 검증이 진행 중입니다. 끝난 뒤 다시 시작하세요.',
  agent_unavailable: '리뷰 에이전트나 리뷰 역할이 준비되지 않았습니다. 상태 화면에서 확인하세요.',
  bad_request: '논문 기록이나 PDF를 확인할 수 없습니다.',
};

function authorLine(authors: string[]): string {
  if (authors.length <= AUTHOR_LIMIT) return authors.join(', ');
  return `${authors.slice(0, AUTHOR_LIMIT).join(', ')} 외 ${formatCount(authors.length - AUTHOR_LIMIT)}명`;
}

function readingTone(status: string | null, queued: ReadonlySet<string>): Tone {
  if (status === 'reviewed') return 'success';
  return status !== null && queued.has(status) ? 'active' : 'neutral';
}

export interface PaperCardReview {
  job: ReviewQueueJob | null;
  pending: boolean;
  error: ApiError | null;
  /** Why 리뷰 시작 is disabled (agent not ready); null when it can run. */
  blocked: string | null;
  onStart: () => void;
}

interface PaperCardProps {
  paper: PaperSummary;
  labels: PaperLabels;
  queued: ReadonlySet<string>;
  index: number;
  /** First render of the list: staggered rise. Later mounts (filter changes): opacity only. */
  entrance: 'stagger' | 'fade';
  review: PaperCardReview;
}

function ReviewProgress({ job }: { job: ReviewQueueJob }) {
  const running = job.status === 'running';
  return (
    <div className="paper-card-progress" role="status">
      <span className="ai-progress" aria-hidden="true" />
      <p className="meta">
        {running ? '리뷰를 작성하는 중…' : '리뷰 대기열에서 순서를 기다리는 중…'}
        {running && job.started_at ? ` 시작 ${formatDateTime(job.started_at)}` : ''} ·{' '}
        <a href={STATUS_HREF}>상태 화면의 리뷰 대기열</a>
      </p>
    </div>
  );
}

/**
 * One library entry. The title is a stretched link to the reader, so the action buttons sit
 * beside it rather than inside a link. The actions column is centered on the card's height.
 */
export function PaperCard({ paper, labels, queued, index, entrance, review }: PaperCardProps) {
  const titleId = useId();
  const reasonId = useId();
  const facts = [paper.year ? String(paper.year) : null, paper.venue].filter(Boolean);
  const verification = paper.verification ? VERIFICATION_BADGES[paper.verification.status] : null;
  const threadCount = paper.threads?.count ?? 0;
  const readingLabel = readingStatusLabel(paper.reading_status, labels);
  const job = review.job;
  const reviewing = job !== null && (job.status === 'queued' || job.status === 'running');
  const failed = job !== null && job.status === 'failed';
  const canStart = paper.has_pdf && paper.review_needed && !reviewing;
  const stagger = entrance === 'stagger';

  return (
    <m.li
      className="paper-card card"
      data-has-pdf={paper.has_pdf ? 'true' : 'false'}
      initial={stagger ? { opacity: 0, y: 16 } : { opacity: 0 }}
      animate={{ opacity: 1, y: 0 }}
      transition={
        stagger
          ? { duration: DUR_ENTER, ease: EASE_OUT, delay: staggerDelay(index, STAGGER_CAP) }
          : { duration: DUR_FILTER, ease: EASE_OUT }
      }
    >
      <div className="paper-card-body">
        <div className="paper-card-main">
          {facts.length > 0 ? (
            <p className="paper-card-facts caption">
              {facts.map((fact, factIndex) => (
                <span key={`${factIndex}:${fact}`} translate={factIndex === 0 ? undefined : 'no'}>
                  {fact}
                </span>
              ))}
            </p>
          ) : null}
          <h3 className="paper-card-title" id={titleId}>
            <a className="paper-card-link" href={paperHref(paper.slug)}>
              {paper.display_title}
            </a>
          </h3>
          {paper.authors.length > 0 ? <p className="paper-card-authors">{authorLine(paper.authors)}</p> : null}
          {paper.one_line_summary ? <p className="paper-card-summary">{paper.one_line_summary}</p> : null}
          {paper.topics.length > 0 ? (
            <p className="paper-card-topics">
              {paper.topics.slice(0, TOPIC_LIMIT).map((topic) => (
                <span className="topic-chip" key={topic}>
                  {topic}
                </span>
              ))}
              {paper.topics.length > TOPIC_LIMIT ? (
                <span className="topic-chip topic-chip-more">+{formatCount(paper.topics.length - TOPIC_LIMIT)}</span>
              ) : null}
            </p>
          ) : null}
          <p className="paper-card-badges">
            <span className="badge" data-tone={paper.has_pdf ? 'success' : 'neutral'}>
              {paper.has_pdf ? 'PDF' : 'PDF 없음'}
            </span>
            <span className="badge" data-tone={paper.has_review ? 'active' : 'neutral'}>
              {paper.has_review ? '리뷰' : '리뷰 없음'}
            </span>
            {verification ? (
              <span className="badge" data-tone={verification.tone}>
                {verification.label}
              </span>
            ) : null}
            {paper.verification?.stale ? (
              <span className="badge" data-tone="warning">
                검증 이후 변경됨
              </span>
            ) : null}
            {threadCount > 0 ? (
              <span className="badge" data-tone="neutral">
                질문&nbsp;<span className="num">{formatCount(threadCount)}</span>
              </span>
            ) : null}
            <span className="badge" data-tone="neutral">
              {categoryLabel(paper.category, labels)}
            </span>
            {readingLabel ? (
              <span className="badge" data-tone={readingTone(paper.reading_status, queued)}>
                {readingLabel}
              </span>
            ) : null}
          </p>
          {paper.threads?.updated_at ? (
            <p className="caption">최근 질문 {formatDateTime(paper.threads.updated_at)}</p>
          ) : null}
        </div>

        {reviewing && job ? <ReviewProgress job={job} /> : null}
        {canStart && review.blocked ? (
          <p className="paper-card-note field-hint" id={reasonId}>
            {review.blocked} <a href={STATUS_HREF}>상태 화면에서 확인</a>
          </p>
        ) : null}
        {failed && job && !reviewing ? (
          <p className="paper-card-note field-error" role="status">
            리뷰가 실패했습니다.{job.message ? ` ${job.message.slice(0, 240)}` : ''}
          </p>
        ) : null}
        {review.error ? (
          <p className="paper-card-note field-error" role="alert">
            {START_ERRORS[review.error.code] ?? `리뷰를 시작하지 못했습니다. ${review.error.message}`}
          </p>
        ) : null}
      </div>

      <div className="paper-card-actions">
        <a className="btn btn-tonal btn-small" href={paperHref(paper.slug)} aria-describedby={titleId}>
          {paper.has_pdf ? '읽기' : '리뷰 보기'}
          <ArrowRight />
        </a>
        {paper.source_url ? (
          <a
            className="btn btn-tonal btn-small"
            href={paper.source_url}
            target="_blank"
            rel="noopener noreferrer"
            aria-describedby={titleId}
          >
            원문
            <ExternalLink />
            <span className="visually-hidden"> (새 탭)</span>
          </a>
        ) : null}
        {canStart ? (
          <button
            type="button"
            className="btn btn-primary btn-small"
            onClick={review.onStart}
            disabled={review.blocked !== null || review.pending}
            aria-busy={review.pending}
            aria-describedby={review.blocked ? `${titleId} ${reasonId}` : titleId}
          >
            <Sparkles />
            {review.pending ? '요청하는 중…' : failed ? '리뷰 다시 시작' : '리뷰 시작'}
          </button>
        ) : null}
      </div>
    </m.li>
  );
}
