import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState, type Ref } from 'react';
import { BookOpen, RefreshCw, SearchX } from 'lucide-react';
import * as m from 'motion/react-m';
import { fetchPapers, toApiError, type ApiError } from '../api/client';
import type { PapersPayload, ReviewQueueJob } from '../api/types';
import { EmptyState } from '../components/EmptyState';
import { ErrorNotice } from '../components/ErrorNotice';
import { ScreenHeader } from '../components/ScreenHeader';
import { Skeleton } from '../components/Skeleton';
import { useToast } from '../components/Toast';
import { formatCount } from '../format';
import { DUR_FAST, EASE_STANDARD } from '../motion/tokens';
import { useStatus } from '../status';
import { BarChart } from './library/BarChart';
import { LibraryFilters } from './library/LibraryFilters';
import { LibraryStats } from './library/LibraryStats';
import { PaperCard } from './library/PaperCard';
import {
  EMPTY_FILTER,
  countByCategory,
  countByYear,
  filterOptions,
  filterPapers,
  libraryStats,
  readingStatusLabel,
  type LibraryFilter,
} from './library/stats';
import { useReviewStart } from './library/useReviewStart';

interface LoadState {
  data: PapersPayload | null;
  error: ApiError | null;
  loading: boolean;
}

function LibrarySkeleton() {
  return (
    <div className="library-skeleton" aria-hidden="true">
      <div className="stat-grid">
        {Array.from({ length: 5 }, (_, index) => (
          <Skeleton key={index} height="6.5rem" />
        ))}
      </div>
      <div className="chart-grid">
        <Skeleton height="12rem" />
        <Skeleton height="12rem" />
      </div>
      {Array.from({ length: 3 }, (_, index) => (
        <Skeleton key={index} height="9rem" />
      ))}
    </div>
  );
}

/** `#/` 논문 라이브러리: stats, charts, filters and the paper cards (the former 논문 list and static library merged). */
export function LibraryScreen({ headingRef, reloadToken }: { headingRef: Ref<HTMLHeadingElement>; reloadToken: number }) {
  const [state, setState] = useState<LoadState>({ data: null, error: null, loading: true });
  const [filter, setFilter] = useState<LibraryFilter>(EMPTY_FILTER);
  const deferredFilter = useDeferredValue(filter);
  const controllerRef = useRef<AbortController | null>(null);
  const status = useStatus();
  const toast = useToast();

  /** `quiet` reloads (after a review finished) keep the refresh button idle. */
  const load = useCallback((quiet = false) => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    if (!quiet) setState((previous) => ({ ...previous, loading: true }));
    fetchPapers(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ data, error: null, loading: false });
      },
      (error: unknown) => {
        if (!controller.signal.aborted) setState((previous) => ({ ...previous, error: toApiError(error), loading: false }));
      },
    );
  }, []);

  useEffect(() => {
    load();
    return () => controllerRef.current?.abort();
  }, [load, reloadToken]);

  const titles = useRef(new Map<string, string>());
  useEffect(() => {
    titles.current = new Map(state.data?.papers.map((paper) => [paper.slug, paper.display_title]));
  }, [state.data]);

  const onFinished = useCallback(
    (job: ReviewQueueJob) => {
      load(true);
      const title = titles.current.get(job.slug) ?? job.slug;
      if (job.status === 'completed') toast({ tone: 'success', title: '리뷰를 마쳤습니다', text: title });
      else if (job.status === 'failed') {
        toast({ tone: 'danger', title: '리뷰가 실패했습니다', text: job.message ? `${title} · ${job.message.slice(0, 160)}` : title });
      } else toast({ title: '리뷰가 끝났습니다', text: title });
    },
    [load, toast],
  );
  const review = useReviewStart({ queue: status.data?.queue.jobs, onFinished, onStale: () => load(true) });

  // First render of the card list rises in with a stagger; later mounts (filter changes) only fade.
  const listEntered = useRef(false);
  const { data, error, loading } = state;
  useEffect(() => {
    if (data) listEntered.current = true;
  }, [data]);

  const derived = useMemo(() => {
    if (!data) return null;
    return {
      stats: libraryStats(data.papers, data.queued_statuses),
      years: countByYear(data.papers),
      categories: countByCategory(data.papers, data.labels),
      options: filterOptions(data.papers, data.labels),
      queued: new Set(data.queued_statuses),
      queuedHint: data.queued_statuses.map((status) => readingStatusLabel(status, data.labels)).join(' · ') || null,
    };
  }, [data]);
  const shown = useMemo(() => (data ? filterPapers(data.papers, deferredFilter) : []), [data, deferredFilter]);

  const blocked =
    status.data && !status.data.ready ? (status.data.reason || '리뷰 에이전트가 준비되지 않았습니다.') : null;

  return (
    <div className="screen library">
      <ScreenHeader
        eyebrow="01-Papers/library"
        title="논문 라이브러리"
        description="논문 기록을 분야와 읽기 상태별로 살펴보고, PDF를 열어 리뷰 근거를 원문 위에서 확인하거나 새 리뷰를 시작합니다."
        headingRef={headingRef}
      >
        <button type="button" className="btn btn-secondary" onClick={() => load()} disabled={loading} aria-busy={loading}>
          <RefreshCw />
          {loading ? '불러오는 중…' : '새로 고침'}
        </button>
      </ScreenHeader>

      {error && error.code !== 'offline' ? (
        <ErrorNotice
          error={error}
          title={data ? '논문 목록을 다시 불러오지 못했습니다. 아래는 이전 결과입니다.' : '논문 목록을 불러오지 못했습니다.'}
          onRetry={() => load()}
        />
      ) : null}

      {data && data.errors.length > 0 ? (
        <details className="notice" data-tone="warning">
          <summary>
            읽지 못한 라이브러리 레코드 <span className="num">{formatCount(data.errors.length)}</span>개
          </summary>
          <ul>
            {data.errors.map((item) => (
              <li key={item.file}>
                <code translate="no">{item.file}</code> {item.error}
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {data && derived ? (
        data.papers.length === 0 ? (
          <EmptyState icon={BookOpen} title="라이브러리에 논문이 없습니다">
            <p>
              <code translate="no">paper-search</code>로 논문을 찾고 <code translate="no">paper-review</code>로 리뷰하면{' '}
              <code translate="no">01-Papers/library/</code>에 기록이 생기고 여기에 표시됩니다.
            </p>
          </EmptyState>
        ) : (
          <m.div
            className="library-content"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: DUR_FAST, ease: EASE_STANDARD }}
          >
            <LibraryStats stats={derived.stats} queuedHint={derived.queuedHint} />
            <div className="chart-grid">
              <BarChart title="연도별 논문" data={derived.years} />
              <BarChart title="분야별 논문" data={derived.categories} />
            </div>

            <section className="library-list" aria-labelledby="library-list-title">
              <h2 id="library-list-title" className="section-title">
                논문 목록
              </h2>
              <LibraryFilters
                filter={filter}
                onChange={setFilter}
                options={derived.options}
                shown={shown.length}
                total={data.papers.length}
                onReset={() => setFilter(EMPTY_FILTER)}
              />
              {shown.length === 0 ? (
                <EmptyState
                  icon={SearchX}
                  title="조건에 맞는 논문이 없습니다"
                  action={
                    <button type="button" className="btn btn-secondary" onClick={() => setFilter(EMPTY_FILTER)}>
                      필터 초기화
                    </button>
                  }
                >
                  <p>검색어를 줄이거나 분야·읽기 상태·연도 조건을 바꿔 보세요.</p>
                </EmptyState>
              ) : (
                <ul className="paper-list">
                  {shown.map((paper, index) => (
                    <PaperCard
                      key={paper.slug}
                      paper={paper}
                      labels={data.labels}
                      queued={derived.queued}
                      index={index}
                      entrance={listEntered.current ? 'fade' : 'stagger'}
                      review={{
                        job: review.jobs.get(paper.slug) ?? null,
                        pending: review.pending.has(paper.slug),
                        error: review.errors.get(paper.slug) ?? null,
                        blocked,
                        onStart: () => review.start(paper.slug),
                      }}
                    />
                  ))}
                </ul>
              )}
            </section>
          </m.div>
        )
      ) : loading ? (
        <div role="status">
          <span className="visually-hidden">논문 목록을 불러오는 중…</span>
          <LibrarySkeleton />
        </div>
      ) : error?.code === 'offline' ? (
        <p className="empty">서버를 실행하고 ‘다시 연결’을 누르면 논문 목록을 다시 불러옵니다.</p>
      ) : null}
    </div>
  );
}
