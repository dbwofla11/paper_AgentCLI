import { useEffect, useRef, useState } from 'react';
import { createRelated, toApiError, type ApiError } from '../api/client';
import type { DiscoveryCandidate, DiscoverySession, RelatedKind, RelatedPaperRef } from '../api/types';
import { discoverSearchHref } from './useHashRoute';

/** Short names of the two Semantic Scholar lists (menu items, buttons, history rows). */
export const RELATED_KIND_LABELS: Record<RelatedKind, string> = { refs: '참고문헌', cites: '피인용' };

/** What each list holds, relative to the paper it was asked for. */
export const RELATED_KIND_DESCRIPTIONS: Record<RelatedKind, string> = {
  refs: '이 논문이 인용한 논문',
  cites: '이 논문을 인용한 논문',
};

/** Menu order of the two Semantic Scholar lists. */
export const RELATED_KIND_ORDER: readonly RelatedKind[] = ['refs', 'cites'];

/** The IDs Semantic Scholar can look a paper up by; a candidate without any cannot be asked about. */
export function hasRelatedIdentifier(ids: DiscoveryCandidate['ids']): boolean {
  return Boolean(ids.arXiv || ids.DOI || ids.S2);
}

// ── The session a lookup just created: the result screen shows it before its first GET answers ──

let primed: DiscoverySession | null = null;
const createdListeners = new Set<() => void>();

/** The session POST /api/discovery/related returned for `searchId` in this page session, if any. */
export function primedSession(searchId: string): DiscoverySession | null {
  return primed?.search_id === searchId ? primed : null;
}

/** Calls `listener` (stable) after every related session created anywhere, e.g. to re-read the search history. */
export function useRelatedCreated(listener: () => void): void {
  useEffect(() => {
    createdListeners.add(listener);
    return () => {
      createdListeners.delete(listener);
    };
  }, [listener]);
}

export interface RelatedLookup {
  /** The list being fetched; null when idle. */
  pending: RelatedKind | null;
  /** How the last lookup failed; cleared by the next one. */
  failure: { kind: RelatedKind; error: ApiError } | null;
  /** Asks the server for the list, then opens it at `#/discover/searches/{id}`. Ignored while one runs. */
  open: (kind: RelatedKind) => void;
}

/**
 * 인용·피인용 for one paper (Q23): POST /api/discovery/related, then navigation to the stored session.
 * A lookup still running when its host unmounts finishes on the server (the session lands in the search
 * history) but no longer navigates.
 */
export function useRelatedLookup(paper: RelatedPaperRef): RelatedLookup {
  const [pending, setPending] = useState<RelatedKind | null>(null);
  const [failure, setFailure] = useState<RelatedLookup['failure']>(null);
  const mounted = useRef(true);
  const running = useRef(false);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const open = (kind: RelatedKind) => {
    if (running.current) return;
    running.current = true;
    setPending(kind);
    setFailure(null);
    void createRelated({ kind, paper })
      .then((session) => {
        primed = session;
        for (const listener of createdListeners) listener();
        if (mounted.current) window.location.hash = discoverSearchHref(session.search_id);
      })
      .catch((caught: unknown) => {
        if (mounted.current) setFailure({ kind, error: toApiError(caught) });
      })
      .finally(() => {
        running.current = false;
        if (mounted.current) setPending(null);
      });
  };

  return { pending, failure, open };
}
