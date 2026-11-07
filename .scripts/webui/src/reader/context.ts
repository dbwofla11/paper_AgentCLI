import { createContext, useContext } from 'react';
import type { ReaderAnchor } from '../api/types';

/** Cross-panel actions of one open paper (PDF ⇄ review ⇄ questions). */
export interface ReaderActions {
  /** PDF pages; 0 while the PDF is loading or missing (page links are then disabled). */
  pageCount: number;
  /** Scrolls the PDF to `page`; `targetKeys` flash those claim highlights on it. */
  goToPage: (page: number, targetKeys?: readonly string[]) => void;
  /** Opens the review tab and focuses the claim card. */
  focusClaim: (claimId: string) => void;
  /** Shows an anchor (selection rects or region box) on the PDF and scrolls to it. */
  showAnchor: (anchor: ReaderAnchor) => void;
  /** Starts a new question about `anchor` in the 질문 tab; `preview` is a blob: URL of a region crop. */
  askAbout: (anchor: ReaderAnchor, preview?: string | null) => void;
  /**
   * Figure API URL for an image path in the review: `figures/{slug}-….svg` (optionally `./`) beside
   * the review file. Null for any other path, which then shows only its alt text.
   */
  figureUrl: (src: string) => string | null;
}

export const ReaderContext = createContext<ReaderActions | null>(null);

export function useReader(): ReaderActions {
  const value = useContext(ReaderContext);
  if (!value) throw new Error('useReader must be used inside <ReaderContext>');
  return value;
}
