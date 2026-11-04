import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState, type Ref } from 'react';
import { FlaskConical, RefreshCw, SearchX } from 'lucide-react';
import * as m from 'motion/react-m';
import { fetchIdeas, toApiError, type ApiError } from '../api/client';
import type { IdeasPayload } from '../api/types';
import { EmptyState } from '../components/EmptyState';
import { ErrorNotice } from '../components/ErrorNotice';
import { ScreenHeader } from '../components/ScreenHeader';
import { Skeleton } from '../components/Skeleton';
import { HARNESS_HREF } from '../hooks/useHashRoute';
import { DUR_FAST, EASE_STANDARD } from '../motion/tokens';
import { IdeaCard } from './ideas/IdeaCard';
import { IdeaFilters } from './ideas/IdeaFilters';
import { EMPTY_IDEA_FILTER, filterIdeas, ideaFilterOptions, type IdeaFilter } from './ideas/ideas';
import '../styles/ideas.css';

interface LoadState {
  data: IdeasPayload | null;
  error: ApiError | null;
  loading: boolean;
}

/** `errors[].section` of GET /api/ideas; `idea:<id>` names one degraded idea. */
const ERROR_SECTIONS: Record<string, string> = {
  ideas: '사고실험 목록',
  registry: '비판 검증 레지스트리',
  library: '논문 라이브러리',
  todo_queue: '조사 TODO 대기열',
  hrefs: '파일 링크',
};

function errorSection(section: string): string {
  if (section.startsWith('idea:')) return `아이디어 ${section.slice('idea:'.length)}`;
  return ERROR_SECTIONS[section] ?? section;
}

/** `#/ideas` 사고실험: the thought-experiment index (the static page's records) with search, filters and sort. */
export default function IdeasScreen({ headingRef, reloadToken }: { headingRef: Ref<HTMLHeadingElement>; reloadToken: number }) {
  const [state, setState] = useState<LoadState>({ data: null, error: null, loading: true });
  const [filter, setFilter] = useState<IdeaFilter>(EMPTY_IDEA_FILTER);
  const deferredFilter = useDeferredValue(filter);
  const controllerRef = useRef<AbortController | null>(null);

  const load = useCallback(() => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setState((previous) => ({ ...previous, loading: true }));
    fetchIdeas(controller.signal).then(
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

  // First render of the card list rises in with a stagger; later mounts (filter changes) only fade.
  const listEntered = useRef(false);
  const { data, error, loading } = state;
  useEffect(() => {
    if (data) listEntered.current = true;
  }, [data]);

  const options = useMemo(() => ideaFilterOptions(data?.ideas ?? []), [data]);
  const shown = useMemo(() => (data ? filterIdeas(data.ideas, deferredFilter) : []), [data, deferredFilter]);
  const resetFilter = () => setFilter({ ...EMPTY_IDEA_FILTER, sort: filter.sort });

  return (
    <div className="screen ideas">
      <ScreenHeader
        eyebrow="05-Ideas/thought-experiments"
        title="사고실험"
        description="아이디어 노트와 비판 검증 레지스트리, 실험 기록을 모아 가설과 반증 조건, 심사·결정 상태를 한곳에서 살펴봅니다."
        headingRef={headingRef}
      >
        <button type="button" className="btn btn-secondary" onClick={load} disabled={loading} aria-busy={loading}>
          <RefreshCw />
          {loading ? '불러오는 중…' : '새로 고침'}
        </button>
      </ScreenHeader>

      {error && error.code !== 'offline' ? (
        <ErrorNotice
          error={error}
          title={data ? '사고실험 목록을 다시 불러오지 못했습니다. 아래는 이전 결과입니다.' : '사고실험 목록을 불러오지 못했습니다.'}
          onRetry={load}
        />
      ) : null}

      {data && data.errors.length > 0 ? (
        <div className="notice" data-tone="warning" role="status">
          <p className="notice-title">일부 기록을 읽지 못했습니다. 읽은 부분만 표시합니다.</p>
          <ul>
            {data.errors.map((item, index) => (
              <li key={`${index}:${item.section}`}>
                {errorSection(item.section)}: <code translate="no">{item.error}</code>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {data ? (
        data.ideas.length === 0 ? (
          <EmptyState
            icon={FlaskConical}
            title="아직 사고실험이 없습니다"
            action={
              <a className="btn btn-secondary" href={HARNESS_HREF}>
                하네스에서 스킬 보기
              </a>
            }
          >
            <p>
              <code translate="no">05-Ideas/thought-experiments/</code>에 아이디어 노트(Markdown)를 두면 여기에 표시됩니다.
            </p>
            <p>
              <code className="ideas-skill-name" translate="no">
                thought-experiment-critique
              </code>{' '}
              스킬로 전제와 반증 조건을 심사하고{' '}
              <code className="ideas-skill-name" translate="no">
                thought-experiment-runner
              </code>
              로 작은 재현 실험을 기록하면 심사·실험 상태가 함께 채워집니다.
            </p>
          </EmptyState>
        ) : (
          <m.section
            className="ideas-list"
            aria-labelledby="ideas-list-title"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: DUR_FAST, ease: EASE_STANDARD }}
          >
            <h2 id="ideas-list-title" className="section-title">
              아이디어 목록
            </h2>
            <IdeaFilters
              filter={filter}
              onChange={setFilter}
              options={options}
              shown={shown.length}
              total={data.ideas.length}
              onReset={resetFilter}
            />
            {shown.length === 0 ? (
              <EmptyState
                icon={SearchX}
                title="조건에 맞는 아이디어가 없습니다"
                action={
                  <button type="button" className="btn btn-secondary" onClick={resetFilter}>
                    필터 초기화
                  </button>
                }
              >
                <p>검색어를 줄이거나 심사·결정·실험 상태 조건을 바꿔 보세요.</p>
              </EmptyState>
            ) : (
              <ul className="idea-list" role="list">
                {shown.map((idea, index) => (
                  <IdeaCard
                    key={idea.id || `${index}:${idea.note}`}
                    idea={idea}
                    hrefs={data.hrefs}
                    index={index}
                    entrance={listEntered.current ? 'fade' : 'stagger'}
                  />
                ))}
              </ul>
            )}
          </m.section>
        )
      ) : loading ? (
        <div className="ideas-skeleton" role="status">
          <span className="visually-hidden">사고실험 목록을 불러오는 중…</span>
          <Skeleton height="10rem" radius="var(--radius-md)" />
          {Array.from({ length: 2 }, (_, index) => (
            <Skeleton key={index} height="16rem" />
          ))}
        </div>
      ) : error?.code === 'offline' ? (
        <p className="empty">서버를 실행하고 ‘다시 연결’을 누르면 사고실험 목록을 다시 불러옵니다.</p>
      ) : null}
    </div>
  );
}
