import { useMemo, useSyncExternalStore } from 'react';

export type Route =
  | { name: 'papers' }
  | { name: 'reader'; slug: string }
  | { name: 'ideas' }
  | { name: 'harness' }
  | { name: 'status' }
  | { name: 'jobs'; jobId: string | null }
  | { name: 'not_found'; path: string };

export const PAPERS_HREF = '#/';
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

function decoded(value: string): string | null {
  try {
    return decodeURIComponent(value);
  } catch {
    return null;
  }
}

/** `#/` → 논문 라이브러리, `#/papers/<slug>` → 리더, `#/ideas` → 사고실험, `#/harness` → 하네스, `#/status` → 상태, `#/jobs[/<id>]` → 작업. */
export function parseHash(hash: string): Route {
  const path = hash.replace(/^#/, '') || '/';
  if (path === '/') return { name: 'papers' };
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
