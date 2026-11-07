import { useId } from 'react';
import { ArrowRight, ExternalLink } from 'lucide-react';
import type { CandidateStatus, DiscoveryCandidate } from '../../api/types';
import { formatCount, type Tone } from '../../format';
import { paperHref } from '../../hooks/useHashRoute';
import { authorLine } from '../library/PaperCard';
import { CandidateActions, type CandidateActionHandlers } from './CandidateActions';

const TOPIC_LIMIT = 4;
const REF_NOTE = '품질 판정이 아닌 참고 목록';
const scoreFormat = new Intl.NumberFormat('ko-KR', { maximumFractionDigits: 2 });

const STATUS_BADGES: Record<CandidateStatus, { label: string; tone: Tone }> = {
  new: { label: '새 후보', tone: 'active' },
  keep: { label: 'Keep', tone: 'waiting' },
  registered: { label: '등록됨', tone: 'success' },
  skipped: { label: '넘김', tone: 'neutral' },
};

const SOURCE_LABELS: Record<string, string> = {
  s2: 'Semantic Scholar',
  arxiv: 'arXiv',
  openalex: 'OpenAlex',
  web: '웹',
};

/** Each path segment encoded, the slashes kept (DOIs contain them). */
function pathSegments(id: string): string {
  return id.split('/').map(encodeURIComponent).join('/');
}

/** Source-ID links in a fixed order; only the IDs present (a candidate, or a related list's paper). */
export function idLinks(ids: Partial<DiscoveryCandidate['ids']>): { key: string; label: string; href: string }[] {
  const links: { key: string; label: string; href: string }[] = [];
  if (ids.arXiv) links.push({ key: 'arXiv', label: `arXiv:${ids.arXiv}`, href: `https://arxiv.org/abs/${pathSegments(ids.arXiv)}` });
  if (ids.DOI) links.push({ key: 'DOI', label: `DOI ${ids.DOI}`, href: `https://doi.org/${pathSegments(ids.DOI)}` });
  if (ids.S2) {
    links.push({ key: 'S2', label: 'Semantic Scholar', href: `https://www.semanticscholar.org/paper/${pathSegments(ids.S2)}` });
  }
  if (ids.OpenAlex) {
    // OpenAlex IDs are stored bare (`W2741809807`) or as their canonical URL.
    const bare = ids.OpenAlex.replace(/^https:\/\/openalex\.org\//i, '');
    links.push({ key: 'OpenAlex', label: `OpenAlex ${bare}`, href: `https://openalex.org/${pathSegments(bare)}` });
  }
  return links;
}

/** Venue confirmation: a verified published/accepted record, a preprint, or not confirmed. */
function publicationBadge({ status, verified }: DiscoveryCandidate['publication']): { label: string; tone: Tone } {
  if (status === 'preprint') return { label: '프리프린트', tone: 'neutral' };
  if (verified && status === 'published') return { label: '게재 확인', tone: 'success' };
  if (verified && status === 'accepted') return { label: '채택 확인', tone: 'success' };
  return { label: '게재 확인 안 됨', tone: 'warning' };
}

/**
 * 넘긴 후보: hidden by default (Q13). A library match always reads 등록됨 or Keep, so only an unmatched
 * `skipped` candidate counts.
 */
export function isSkipped(candidate: DiscoveryCandidate): boolean {
  return candidate.library === null && candidate.status === 'skipped';
}

interface CandidateCardProps {
  candidate: DiscoveryCandidate;
  /** Heading level of the title: 3 in a plain list, 4 under a slot heading (일일 후보). */
  titleLevel?: 3 | 4;
  /** Keep에 담기 / 등록 / 넘김·복원; omitted, the card is read-only. */
  actions?: CandidateActionHandlers;
  /** Only the head and the actions (a 넘긴 candidate kept in its daily slot). */
  collapsed?: boolean;
}

/**
 * One discovered paper (Q16): title (external link, https only), authors, year, venue with its
 * confirmation, citations, the agent's relevance note, a folded abstract, source-ID links, library
 * ownership and the cs-conferences.csv row shown only as a reference; then its actions (Keep에 담기,
 * 등록, 인용·피인용, 넘김·복원).
 */
export function CandidateCard({ candidate, titleLevel = 3, actions, collapsed = false }: CandidateCardProps) {
  const titleId = useId();
  const Title = titleLevel === 4 ? 'h4' : 'h3';
  // A library match reads 등록됨 (Q13), except a candidate kept here: it reads Keep and can still be registered.
  // The stored status stays in the cache either way.
  const status = STATUS_BADGES[candidate.status === 'keep' ? 'keep' : candidate.library ? 'registered' : candidate.status];
  const publication = publicationBadge(candidate.publication);
  const links = idLinks(candidate.ids);
  const ref = candidate.conference_ref;
  const sources = candidate.sources.map((source) => SOURCE_LABELS[source] ?? source);

  return (
    <article className="candidate-card card" aria-labelledby={titleId} data-collapsed={collapsed ? 'true' : undefined}>
      <div className="candidate-card-head">
        <p className="candidate-facts caption">
          <span className="num">{candidate.year ?? '연도 미상'}</span>
          <span translate={candidate.venue ? 'no' : undefined}>{candidate.venue ?? '출처 미확인'}</span>
          <span>
            {candidate.citations === null ? (
              '인용 수 미확인'
            ) : (
              <>
                인용&nbsp;<span className="num">{formatCount(candidate.citations)}</span>회
              </>
            )}
          </span>
        </p>
        {/* The id sits on the title text alone so the card name and link descriptions skip "(원문, 새 탭)". */}
        <Title className="candidate-title">
          {candidate.url ? (
            <a href={candidate.url} target="_blank" rel="noopener noreferrer">
              <span id={titleId}>{candidate.title}</span>
              <ExternalLink />
              <span className="visually-hidden"> (원문, 새 탭)</span>
            </a>
          ) : (
            <span id={titleId}>{candidate.title}</span>
          )}
        </Title>
        {candidate.authors.length > 0 ? <p className="candidate-authors">{authorLine(candidate.authors)}</p> : null}
        <p className="candidate-badges">
          <span className="badge" data-tone={status.tone}>
            {status.label}
          </span>
          <span className="badge" data-tone={publication.tone}>
            {publication.label}
          </span>
          {candidate.library ? (
            <a
              className="badge candidate-library"
              data-tone="success"
              href={paperHref(candidate.library.slug)}
              aria-describedby={titleId}
            >
              {candidate.library.match === 'title' ? '라이브러리 보유 (제목 일치)' : '라이브러리 보유'}
              <ArrowRight />
            </a>
          ) : null}
        </p>
      </div>

      {/* One child slot whether collapsed or not, so the actions below keep their state (and focus). */}
      {collapsed ? null : (
        <>
          {candidate.relevance ? (
            <div className="candidate-relevance">
              <p className="candidate-label">관련 이유</p>
              <p>{candidate.relevance}</p>
            </div>
          ) : null}

          {candidate.abstract ? (
            <details className="candidate-abstract">
              <summary>초록</summary>
              <p>{candidate.abstract}</p>
            </details>
          ) : null}

          {candidate.topics.length > 0 ? (
            <p className="candidate-topics">
              {candidate.topics.slice(0, TOPIC_LIMIT).map((topic) => (
                <span className="topic-chip" key={topic}>
                  {topic}
                </span>
              ))}
              {candidate.topics.length > TOPIC_LIMIT ? (
                <span className="topic-chip topic-chip-more">+{formatCount(candidate.topics.length - TOPIC_LIMIT)}</span>
              ) : null}
            </p>
          ) : null}

          {links.length > 0 || ref || sources.length > 0 ? (
            <div className="candidate-foot">
              {links.length > 0 ? (
                <ul className="candidate-ids" role="list" aria-label="출처 ID">
                  {links.map((link) => (
                    <li key={link.key}>
                      <a href={link.href} target="_blank" rel="noopener noreferrer" aria-describedby={titleId}>
                        <span translate="no">{link.label}</span>
                        <ExternalLink />
                        <span className="visually-hidden"> (새 탭)</span>
                      </a>
                    </li>
                  ))}
                </ul>
              ) : null}
              {ref ? (
                <p className="candidate-ref caption" title={REF_NOTE}>
                  참고: <span translate="no">{ref.abbr}</span>
                  {ref.score === null ? null : (
                    <>
                      {' '}
                      (정규화 평균 <span className="num">{scoreFormat.format(ref.score)}</span>)
                    </>
                  )}
                  <span className="visually-hidden"> — {REF_NOTE}</span>
                </p>
              ) : null}
              {sources.length > 0 ? (
                <p className="caption">
                  찾은 곳: <span translate="no">{sources.join(' · ')}</span>
                </p>
              ) : null}
            </div>
          ) : null}
        </>
      )}

      {actions && candidate.candidate_id ? (
        <CandidateActions candidate={candidate} titleId={titleId} handlers={actions} />
      ) : null}
    </article>
  );
}
