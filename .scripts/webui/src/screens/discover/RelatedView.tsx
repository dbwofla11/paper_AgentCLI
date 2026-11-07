import type { Ref } from 'react';
import { ArrowLeftRight, ArrowRight, ExternalLink, LoaderCircle } from 'lucide-react';
import type { ApiError } from '../../api/client';
import type { DiscoverySession, RelatedKind, RelatedPaperRef } from '../../api/types';
import { ErrorNotice } from '../../components/ErrorNotice';
import { RelatedNotice } from '../../components/RelatedMenu';
import { formatCount, formatDateTime } from '../../format';
import { paperHref } from '../../hooks/useHashRoute';
import {
  RELATED_KIND_DESCRIPTIONS,
  RELATED_KIND_LABELS,
  hasRelatedIdentifier,
  useRelatedLookup,
} from '../../hooks/useRelatedLookup';
import type { CandidateActionHandlers } from './CandidateActions';
import { idLinks } from './CandidateCard';
import { CandidateList } from './CandidateList';
import { ReportList } from './DailyDay';

export type RelatedSession = Extract<DiscoverySession, { mode: 'related' }>;

const OTHER_KIND: Record<RelatedKind, RelatedKind> = { refs: 'cites', cites: 'refs' };

/** The paper's other list asks the server the same way this one did: by library slug, else by IDs. */
function paperRef(paper: RelatedSession['request']['paper']): RelatedPaperRef {
  if (paper.slug) return { slug: paper.slug };
  const { arXiv = null, DOI = null, S2 = null, OpenAlex = null } = paper.ids;
  return { title: paper.title, ids: { arXiv, DOI, S2, OpenAlex } };
}

interface RelatedViewProps {
  session: RelatedSession;
  /** SearchResult's heading id (it labels the section) and ref (focus target after status changes). */
  headingId: string;
  headingRef: Ref<HTMLHeadingElement>;
  /** Last failed re-read of the session; the shown list is the previous answer. */
  error: ApiError | null;
  onRetry: () => void;
  /** Card actions with this session as their source. */
  actions: Omit<CandidateActionHandlers, 'onSkipped'>;
}

/**
 * Body of `#/discover/searches/{id}` for a related session (Q7, Q23), inside SearchResult's section:
 * the paper the list belongs to (title, library link, IDs), which list it is, the switch to the other
 * list, Semantic Scholar's coverage notes, then the papers as candidate cards with the same actions as
 * search results.
 */
export function RelatedView({ session, headingId, headingRef, error, onRetry, actions }: RelatedViewProps) {
  const { kind, paper, limit } = session.request;
  const other = OTHER_KIND[kind];
  const anchor = paperRef(paper);
  const lookup = useRelatedLookup(anchor);
  const switchBlocked = 'ids' in anchor && !hasRelatedIdentifier(anchor.ids);
  const switching = lookup.pending !== null;
  const links = idLinks(paper.ids);
  const report = session.report;
  const { candidates } = session;

  return (
    <>
      <div className="discover-result-head">
        <div className="discover-result-title">
          <p className="eyebrow" translate="no">
            {session.search_id}
          </p>
          <p className="discover-related-kind">
            <span className="badge" data-tone="active">
              {RELATED_KIND_LABELS[kind]}
            </span>
            <span>
              {RELATED_KIND_DESCRIPTIONS[kind]} <span className="num">{formatCount(candidates.length)}</span>편 ·{' '}
              <span translate="no">Semantic&nbsp;Scholar</span>
            </span>
          </p>
          <h2 id={headingId} ref={headingRef} tabIndex={-1}>
            <span className="visually-hidden">{RELATED_KIND_LABELS[kind]} 목록: </span>
            {paper.title}
          </h2>
        </div>
      </div>

      {error && error.code !== 'offline' ? (
        <ErrorNotice error={error} title="목록을 다시 불러오지 못했습니다. 아래는 이전 결과입니다." onRetry={onRetry} />
      ) : null}

      <dl className="session-facts discover-request-facts">
        <div>
          <dt>라이브러리</dt>
          <dd>
            {paper.slug ? (
              <a href={paperHref(paper.slug)}>
                <code translate="no">{paper.slug}</code>
              </a>
            ) : (
              '라이브러리 밖 논문'
            )}
          </dd>
        </div>
        <div>
          <dt>식별자</dt>
          <dd>
            {links.length === 0 ? (
              '없음'
            ) : (
              <ul className="candidate-ids" role="list" aria-label="기준 논문 출처 ID">
                {links.map((link) => (
                  <li key={link.key}>
                    <a href={link.href} target="_blank" rel="noopener noreferrer">
                      <span translate="no">{link.label}</span>
                      <ExternalLink />
                      <span className="visually-hidden"> (새 탭)</span>
                    </a>
                  </li>
                ))}
              </ul>
            )}
          </dd>
        </div>
        <div>
          <dt>조회 시각</dt>
          <dd className="num">{formatDateTime(session.created_at)}</dd>
        </div>
        <div>
          <dt>편수</dt>
          <dd>
            최대&nbsp;<span className="num">{formatCount(limit)}</span>편
          </dd>
        </div>
      </dl>

      <div className="discover-related-actions">
        {/* One button for both states, so focus stays on it while the other list is fetched. */}
        <button
          type="button"
          className="btn btn-secondary btn-small"
          onClick={() => {
            if (!switching) lookup.open(other);
          }}
          disabled={switchBlocked}
          aria-disabled={switching || undefined}
          aria-busy={switching}
          aria-describedby={headingId}
        >
          {switching ? <LoaderCircle className="related-spinner" aria-hidden="true" /> : <ArrowLeftRight aria-hidden="true" />}
          {switching ? `${RELATED_KIND_LABELS[other]} 가져오는 중…` : `${RELATED_KIND_LABELS[other]} 목록 보기`}
        </button>
        {paper.slug ? (
          <a className="btn btn-text btn-small" href={paperHref(paper.slug)}>
            리더에서 열기
            <ArrowRight aria-hidden="true" />
          </a>
        ) : null}
        <span className="visually-hidden" role="status">
          {switching ? `Semantic Scholar에서 ${RELATED_KIND_LABELS[other]} 목록을 가져오는 중입니다.` : ''}
        </span>
      </div>
      <RelatedNotice lookup={lookup} />

      {report && (report.coverage_gaps.length > 0 || report.notes || report.excluded_count) ? (
        <details className="discover-report">
          <summary>
            조회 보고{' '}
            <span className="caption">
              누락 범위 <span className="num">{formatCount(report.coverage_gaps.length)}</span>
            </span>
          </summary>
          <dl className="facts">
            <dt>요청</dt>
            <dd>
              <ReportList items={report.queries} mono />
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
      ) : null}

      <CandidateList
        candidates={candidates}
        actions={actions}
        storedOrder="Semantic Scholar 순서"
        emptyText={`Semantic Scholar에 ${RELATED_KIND_DESCRIPTIONS[kind]}이 등록되어 있지 않습니다.`}
      />
    </>
  );
}
