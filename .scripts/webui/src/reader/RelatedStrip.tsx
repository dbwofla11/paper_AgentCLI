import { useId } from 'react';
import { RelatedMenu, RelatedNotice } from '../components/RelatedMenu';
import { useRelatedLookup } from '../hooks/useRelatedLookup';

/**
 * Side-panel strip above both tabs (Q23): 인용·피인용 for the open paper. The chosen Semantic Scholar
 * list opens on the 탐색 screen (`#/discover/searches/{id}`); failures stay here, under the button.
 */
export function RelatedStrip({ slug }: { slug: string }) {
  const hintId = useId();
  const lookup = useRelatedLookup({ slug });
  return (
    <div className="related-strip">
      <div className="related-strip-row">
        <p className="related-strip-text">
          <span className="related-strip-label">인용 관계</span>{' '}
          <span className="related-strip-hint" id={hintId}>
            Semantic Scholar 목록을 탐색 화면에서 엽니다
          </span>
        </p>
        <RelatedMenu lookup={lookup} describedBy={hintId} className="btn btn-secondary btn-small" />
      </div>
      <RelatedNotice lookup={lookup} />
    </div>
  );
}
