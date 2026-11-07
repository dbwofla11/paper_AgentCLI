import { useId, useRef, useState } from 'react';
import type { DiscoveryCandidate } from '../../api/types';
import { formatCount } from '../../format';
import type { CandidateActionHandlers } from './CandidateActions';
import { CandidateCard, isSkipped } from './CandidateCard';

type SortKey = 'stored' | 'year' | 'citations';

/** Sorted copy; missing years or citation counts go last, ties keep the stored order (stable sort). */
function sortCandidates(candidates: DiscoveryCandidate[], key: SortKey): DiscoveryCandidate[] {
  if (key === 'stored') return candidates;
  const value = (candidate: DiscoveryCandidate) => (key === 'year' ? candidate.year : candidate.citations);
  return [...candidates].sort((a, b) => {
    const left = value(a);
    const right = value(b);
    if (left === right) return 0;
    if (left === null) return 1;
    if (right === null) return -1;
    return right - left;
  });
}

interface CandidateListProps {
  candidates: DiscoveryCandidate[];
  /** Card actions with the session as their source; `onSkipped` is added here. */
  actions: Omit<CandidateActionHandlers, 'onSkipped'>;
  /** Name of the stored order in the sort menu: the agent's 관련도, or Semantic Scholar's order. */
  storedOrder: string;
  /** Shown when the session holds no candidates at all. */
  emptyText: string;
}

/**
 * 후보 목록 of a search or related session: sort (stored order, 연도, 인용 수), the 넘김 toggle and each
 * card's Keep/등록/인용·피인용/넘김.
 */
export function CandidateList({ candidates, actions, storedOrder, emptyText }: CandidateListProps) {
  const headingId = useId();
  const sortId = useId();
  const skippedHintId = useId();
  const switchRef = useRef<HTMLInputElement>(null);
  const [sort, setSort] = useState<SortKey>('stored');
  const [showSkipped, setShowSkipped] = useState(false);
  const skipped = candidates.filter(isSkipped).length;
  const visible = showSkipped ? candidates : candidates.filter((candidate) => !isSkipped(candidate));
  const sorted = sortCandidates(visible, sort);
  const sortOptions: ReadonlyArray<{ value: SortKey; label: string }> = [
    { value: 'stored', label: storedOrder },
    { value: 'year', label: '연도 (최신순)' },
    { value: 'citations', label: '인용 수 (많은 순)' },
  ];
  // A card hidden by its own 넘김 takes its focused button with it; the switch that brings it back takes focus.
  const cardActions: CandidateActionHandlers = {
    ...actions,
    onSkipped: () => {
      if (!showSkipped) switchRef.current?.focus();
    },
  };

  return (
    <section className="discover-candidates-section" aria-labelledby={headingId}>
      <div className="discover-candidates-head">
        <h3 id={headingId}>
          후보 <span className="num">{formatCount(candidates.length)}</span>편
        </h3>
        <div className="discover-candidates-controls">
          <div className="field discover-sort">
            <label htmlFor={sortId}>정렬</label>
            <select id={sortId} value={sort} onChange={(event) => setSort(event.currentTarget.value as SortKey)}>
              {sortOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
          <label className="switch">
            <input
              ref={switchRef}
              type="checkbox"
              role="switch"
              checked={showSkipped}
              aria-describedby={skippedHintId}
              onChange={(event) => setShowSkipped(event.currentTarget.checked)}
            />
            <span className="switch-track" aria-hidden="true" />
            넘긴 후보 표시
          </label>
        </div>
      </div>
      <p className="field-hint" id={skippedHintId} role="status">
        {skipped === 0 ? (
          '넘긴 후보가 없습니다.'
        ) : (
          <>
            넘긴 후보 <span className="num">{formatCount(skipped)}</span>편은 {showSkipped ? '함께 보이며 ‘복원’할 수 있습니다.' : '숨겼습니다.'}
          </>
        )}{' '}
        라이브러리에 있는 논문은 ‘등록됨’, 여기서 Keep에 담은 논문은 ‘Keep’으로 표시합니다.
      </p>
      {sorted.length === 0 ? (
        <p className="empty empty-compact">
          {candidates.length === 0 ? emptyText : '보이는 후보가 없습니다. 넘긴 후보 표시를 켜면 모두 보입니다.'}
        </p>
      ) : (
        <ul className="discover-candidates" role="list">
          {sorted.map((candidate) => (
            <li key={candidate.candidate_id || candidate.title}>
              <CandidateCard candidate={candidate} titleLevel={4} actions={cardActions} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
