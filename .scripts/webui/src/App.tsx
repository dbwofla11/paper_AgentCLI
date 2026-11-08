import { Suspense, lazy, useCallback, useEffect, useRef, useState, type MouseEvent } from 'react';
import * as m from 'motion/react-m';
import { loadSession } from './api/client';
import { AppHeader } from './components/AppHeader';
import { ServerDown } from './components/ServerDown';
import { Skeleton } from './components/Skeleton';
import { useConnection } from './hooks/useConnection';
import { useHashRoute, type Route } from './hooks/useHashRoute';
import { DUR_FAST, EASE_STANDARD } from './motion/tokens';
import { JobsScreen } from './screens/JobsScreen';
import { LibraryScreen } from './screens/LibraryScreen';
import { NotFoundScreen } from './screens/NotFoundScreen';
import { StatusScreen } from './screens/StatusScreen';
import { useStatus } from './status';

// pdf.js (~1.7 MB with its worker) is fetched only when a reader route opens (decision D14).
const ReaderScreen = lazy(() => import('./screens/ReaderScreen'));
const HarnessScreen = lazy(() => import('./screens/HarnessScreen'));
const IdeasScreen = lazy(() => import('./screens/IdeasScreen'));
const DiscoverScreen = lazy(() => import('./screens/DiscoverScreen'));

const ROUTE_TITLES: Record<Route['name'], string> = {
  papers: '논문 라이브러리',
  reader: '논문 리더',
  discover: '논문 탐색',
  ideas: '사고실험',
  harness: '하네스',
  status: '상태',
  jobs: '작업',
  not_found: '화면 없음',
};

function ReaderLoading() {
  return (
    <p className="reader-boot" role="status">
      리더를 불러오는 중…
    </p>
  );
}

function ScreenLoading({ label }: { label: string }) {
  return (
    <div className="screen" role="status">
      <span className="visually-hidden">{label}</span>
      <div className="screen-loading" aria-hidden="true">
        <Skeleton height="1rem" width="8rem" />
        <Skeleton height="2.5rem" width="min(24rem, 80%)" />
        <Skeleton height="12rem" radius="var(--radius-md)" />
      </div>
    </div>
  );
}

export function App() {
  const route = useHashRoute();
  const connection = useConnection();
  const { refresh: refreshStatus } = useStatus();
  const [reloadToken, setReloadToken] = useState(0);
  const mainRef = useRef<HTMLElement>(null);
  const headingElement = useRef<HTMLHeadingElement | null>(null);
  // Set when a route change found no heading yet (lazy screens): the heading takes focus when it
  // mounts. Also set when a focused heading is replaced (the reader's loading toolbar → loaded toolbar).
  const focusPending = useRef(false);
  const headingRef = useCallback((node: HTMLHeadingElement | null) => {
    const previous = headingElement.current;
    if (!node && previous && (document.activeElement === previous || document.activeElement === document.body)) {
      focusPending.current = focusPending.current || previous.dataset.routeFocus === 'true';
    }
    headingElement.current = node;
    if (node && focusPending.current) {
      focusPending.current = false;
      node.dataset.routeFocus = 'true';
      node.focus();
    }
  }, []);
  const previousRoute = useRef(route.name);
  // The landing screen appears without the route fade (nothing to transition from).
  const landingRoute = useRef<Route['name'] | null>(route.name);

  useEffect(() => {
    loadSession().catch(() => undefined); // failures surface through the connection snapshot
  }, []);

  useEffect(() => {
    // The reader sets its own title with the paper name.
    if (route.name !== 'reader') document.title = `${ROUTE_TITLES[route.name]} · 연구 하네스 WebUI`;
    // Announce the new screen; the first load keeps the browser's default focus.
    if (previousRoute.current === route.name) return;
    previousRoute.current = route.name;
    landingRoute.current = null;
    const heading = headingElement.current;
    focusPending.current = heading === null;
    if (heading) {
      heading.dataset.routeFocus = 'true';
      heading.focus();
    }
  }, [route.name]);

  const reconnect = useCallback(async () => {
    try {
      await loadSession(true);
    } catch {
      return false;
    }
    refreshStatus();
    setReloadToken((token) => token + 1);
    return true;
  }, [refreshStatus]);

  // Hash routing owns the fragment, so the skip link moves focus instead of navigating.
  const skipToMain = (event: MouseEvent<HTMLAnchorElement>) => {
    event.preventDefault();
    mainRef.current?.focus();
  };

  // The reader has no global header: its 48px toolbar is the only top bar (design §3).
  const reader = route.name === 'reader';
  return (
    <>
      <a className="skip-link" href="#main-content" onClick={skipToMain}>
        본문으로 건너뛰기
      </a>
      {reader ? null : <AppHeader route={route} connection={connection} />}
      <main
        id="main-content"
        className={reader ? 'app-main app-main-reader' : 'app-main'}
        ref={mainRef}
        tabIndex={-1}
      >
        {connection.state === 'offline' ? <ServerDown onRetry={reconnect} /> : null}
        {/* Fade in only, no exit: AnimatePresence would delay mounting and break the heading focus above. */}
        <m.div
          key={route.name}
          className="route-view"
          initial={landingRoute.current === route.name ? false : { opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: DUR_FAST, ease: EASE_STANDARD }}
        >
          {route.name === 'papers' ? <LibraryScreen headingRef={headingRef} reloadToken={reloadToken} /> : null}
          {route.name === 'reader' ? (
            <Suspense fallback={<ReaderLoading />}>
              <ReaderScreen
                key={route.slug}
                slug={route.slug}
                view={route.view}
                headingRef={headingRef}
                reloadToken={reloadToken}
              />
            </Suspense>
          ) : null}
          {route.name === 'discover' ? (
            <Suspense fallback={<ScreenLoading label="탐색 화면을 불러오는 중…" />}>
              <DiscoverScreen
                headingRef={headingRef}
                reloadToken={reloadToken}
                view={route.view}
                id={route.id}
                prefill={route.prefill}
              />
            </Suspense>
          ) : null}
          {route.name === 'ideas' ? (
            <Suspense fallback={<ScreenLoading label="사고실험 화면을 불러오는 중…" />}>
              <IdeasScreen headingRef={headingRef} reloadToken={reloadToken} />
            </Suspense>
          ) : null}
          {route.name === 'harness' ? (
            <Suspense fallback={<ScreenLoading label="하네스 화면을 불러오는 중…" />}>
              <HarnessScreen headingRef={headingRef} reloadToken={reloadToken} />
            </Suspense>
          ) : null}
          {route.name === 'status' ? <StatusScreen headingRef={headingRef} connection={connection} /> : null}
          {route.name === 'jobs' ? (
            <JobsScreen headingRef={headingRef} jobId={route.jobId} reloadToken={reloadToken} />
          ) : null}
          {route.name === 'not_found' ? <NotFoundScreen headingRef={headingRef} path={route.path} /> : null}
        </m.div>
      </main>
    </>
  );
}
