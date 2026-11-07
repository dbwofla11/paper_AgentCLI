import { useMemo, useSyncExternalStore } from 'react';

/** `#/discover` tabs: external search (with its history) and the daily-candidate feed. */
export type DiscoverView = 'search' | 'daily';

export type Route =
  | { name: 'papers' }
  | { name: 'reader'; slug: string }
  | { name: 'discover'; view: DiscoverView; id: string | null; prefill: string | null }
  | { name: 'ideas' }
  | { name: 'harness' }
  | { name: 'status' }
  | { name: 'jobs'; jobId: string | null }
  | { name: 'not_found'; path: string };

export const PAPERS_HREF = '#/';
export const DISCOVER_HREF = '#/discover';
export const IDEAS_HREF = '#/ideas';
export const HARNESS_HREF = '#/harness';
export const STATUS_HREF = '#/status';
export const JOBS_HREF = '#/jobs';

export function jobHref(jobId: string): string {
  return `${JOBS_HREF}/${encodeURIComponent(jobId)}`;
}

export function paperHref(slug: string): string {
  return `#/papers/${encodeURIComponent(slug)}`;
}

/** A stored search session (`00-Inbox/discovery/searches/{id}.json`). */
export function discoverSearchHref(id: string): string {
  return `${DISCOVER_HREF}/searches/${encodeURIComponent(id)}`;
}

/** Search tab with the query prefilled (`?q=`), e.g. from an empty library search. */
export function discoverPrefillHref(query: string): string {
  return `${DISCOVER_HREF}?${new URLSearchParams({ q: query }).toString()}`;
}

/** Daily-candidate list, or one day (`YYYY-MM-DD`). */
export function discoverDailyHref(date?: string): string {
  return date ? `${DISCOVER_HREF}/daily/${encodeURIComponent(date)}` : `${DISCOVER_HREF}/daily`;
}

function decoded(value: string): string | null {
  try {
    return decodeURIComponent(value);
  } catch {
    return null;
  }
}

/**
 * `#/` → 논문 라이브러리, `#/papers/<slug>` → 리더, `#/discover[/searches/<id>|/daily[/<date>]]` → 탐색,
 * `#/ideas` → 사고실험, `#/harness` → 하네스, `#/status` → 상태, `#/jobs[/<id>]` → 작업.
 * A `?query` after the path is read only by 탐색 (`q` prefills the search form).
 */
export function parseHash(hash: string): Route {
  const fragment = hash.replace(/^#/, '');
  const queryStart = fragment.indexOf('?');
  const path = (queryStart === -1 ? fragment : fragment.slice(0, queryStart)) || '/';
  const query = new URLSearchParams(queryStart === -1 ? '' : fragment.slice(queryStart + 1));
  if (path === '/') return { name: 'papers' };
  const discover = /^\/discover(?:\/(searches|daily)(?:\/([^/]+))?)?\/?$/.exec(path);
  if (discover) {
    const view: DiscoverView = discover[1] === 'daily' ? 'daily' : 'search';
    // `#/discover/searches` alone is the search tab itself.
    const id = discover[2] === undefined ? null : decoded(discover[2]);
    if (discover[2] !== undefined && !id) return { name: 'not_found', path };
    return { name: 'discover', view, id, prefill: query.get('q')?.trim() || null };
  }
  if (/^\/ideas\/?$/.test(path)) return { name: 'ideas' };
  if (/^\/harness\/?$/.test(path)) return { name: 'harness' };
  if (/^\/status\/?$/.test(path)) return { name: 'status' };
  const paper = /^\/papers\/([^/]+)\/?$/.exec(path);
  if (paper) {
    const slug = decoded(paper[1]);
    return slug ? { name: 'reader', slug } : { name: 'not_found', path };
  }
  const match = /^\/jobs(?:\/([^/]+))?\/?$/.exec(path);
  if (!match) return { name: 'not_found', path };
  if (!match[1]) return { name: 'jobs', jobId: null };
  const jobId = decoded(match[1]);
  return jobId ? { name: 'jobs', jobId } : { name: 'not_found', path };
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener('hashchange', onChange);
  return () => window.removeEventListener('hashchange', onChange);
}

export function useHashRoute(): Route {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash);
  return useMemo(() => parseHash(hash), [hash]);
}
