import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { History as HistoryIcon, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { deleteSearch, toApiError, type ApiError } from '../../api/client';
import type { DiscoverySessionList, DiscoverySessionSummary } from '../../api/types';
import { StatusBadge } from '../../components/Badges';
import { ErrorNotice } from '../../components/ErrorNotice';
import { useToast } from '../../components/Toast';
import { formatCount, formatDateTime } from '../../format';
import { DISCOVER_HREF, discoverSearchHref } from '../../hooks/useHashRoute';
import { RELATED_KIND_LABELS } from '../../hooks/useRelatedLookup';
import { isActiveSearch, type Polled } from './useDiscovery';

type TitleFields = Pick<DiscoverySessionSummary, 'mode' | 'query' | 'kind' | 'paper_title'>;

/** History row title: the query, or which related list it is and whose (`피인용 목록 · {title}`). */
export function sessionTitle(summary: TitleFields): string {
  if (summary.mode !== 'related') return summary.query ?? '검색어 없음';
  const label = summary.kind ? `${RELATED_KIND_LABELS[summary.kind]} 목록` : '인용 목록';
  return summary.paper_title ? `${label} · ${summary.paper_title}` : label;
}

const DELETE_ERRORS: Record<string, string> = {
  search_active: '진행 중인 검색은 지울 수 없습니다. 끝나거나 취소된 뒤 지우세요.',
  not_found: '이미 지워진 검색 기록입니다.',
};

interface HistoryRowProps {
  search: DiscoverySessionSummary;
  current: boolean;
  onDeleted: (search: DiscoverySessionSummary) => void;
  onFailed: (error: ApiError, search: DiscoverySessionSummary) => void;
}

function HistoryRow({ search, current, onDeleted, onFailed }: HistoryRowProps) {
  const titleId = useId();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const deleteRef = useRef<HTMLButtonElement>(null);
  const keepRef = useRef<HTMLButtonElement>(null);
  const wasConfirming = useRef(false);
  const active = isActiveSearch(search.status);
  const title = sessionTitle(search);

  // Opening the question moves focus to the safe choice; closing it returns focus to the trash button.
  useEffect(() => {
    if (confirming) keepRef.current?.focus();
    else if (wasConfirming.current) deleteRef.current?.focus();
    wasConfirming.current = confirming;
  }, [confirming]);

  const remove = async () => {
    setDeleting(true);
    try {
      await deleteSearch(search.search_id);
      onDeleted(search);
    } catch (caught) {
      setConfirming(false);
      onFailed(toApiError(caught), search);
    } finally {
      setDeleting(false);
    }
  };

  const dismissOnEscape = (event: KeyboardEvent<HTMLSpanElement>) => {
    if (event.key === 'Escape') setConfirming(false);
  };

  return (
    <li className="discover-history-item" data-current={current ? 'true' : undefined}>
      <a className="discover-history-row" href={discoverSearchHref(search.search_id)} aria-current={current ? 'page' : undefined}>
        <span className="discover-history-title" id={titleId}>
          {search.mode === 'related' ? (
            <>
              <span className="discover-history-kind">
                {search.kind ? `${RELATED_KIND_LABELS[search.kind]} 목록` : '인용 목록'}
              </span>{' '}
              {search.paper_title ?? ''}
            </>
          ) : (
            title
          )}
        </span>
        <span className="discover-history-meta">
          {/* One search runs at a time; its row announces queued → running (§3). */}
          <span role={active ? 'status' : undefined}>
            <StatusBadge status={search.status} />
          </span>
          {search.status === 'completed' ? (
            <span className="caption">
              후보&nbsp;<span className="num">{formatCount(search.candidate_count)}</span>편
            </span>
          ) : null}
          <span className="caption num">{formatDateTime(search.created_at)}</span>
        </span>
      </a>
      {active ? null : confirming ? (
        <span className="discover-history-confirm" role="group" aria-labelledby={titleId} onKeyDown={dismissOnEscape}>
          <span className="caption">이 기록을 지울까요?</span>
          <button
            type="button"
            className="btn btn-danger btn-small"
            onClick={() => void remove()}
            disabled={deleting}
            aria-busy={deleting}
          >
            {deleting ? '지우는 중…' : '지우기'}
          </button>
          <button type="button" className="btn btn-secondary btn-small" ref={keepRef} onClick={() => setConfirming(false)}>
            그대로 두기
          </button>
        </span>
      ) : (
        <button
          type="button"
          className="icon-btn discover-history-delete"
          ref={deleteRef}
          aria-label="검색 기록 지우기"
          aria-describedby={titleId}
          title="검색 기록 지우기"
          onClick={() => setConfirming(true)}
        >
          <Trash2 />
        </button>
      )}
    </li>
  );
}

interface SearchHistoryProps {
  list: Polled<DiscoverySessionList>;
  /** Session shown beside the history (`#/discover/searches/{id}`); null on the form. */
  currentId: string | null;
}

/** 검색 기록 (Q8): every stored session, newest first, with live status and delete after confirmation. */
export function SearchHistory({ list, currentId }: SearchHistoryProps) {
  const showToast = useToast();
  const [deleteError, setDeleteError] = useState<{ error: ApiError; title: string } | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  const { data, error, loading, reload, update } = list;

  const onDeleted = (search: DiscoverySessionSummary) => {
    setDeleteError(null);
    update((current) => ({ ...current, searches: current.searches.filter((item) => item.search_id !== search.search_id) }));
    showToast({ title: '검색 기록을 지웠습니다.', text: sessionTitle(search), tone: 'success' });
    // The deleted row took focus with it: land on the list heading, or on the form when its result was open.
    if (search.search_id === currentId) window.location.hash = DISCOVER_HREF;
    else headingRef.current?.focus();
  };

  const onFailed = (failure: ApiError, search: DiscoverySessionSummary) => {
    setDeleteError({ error: failure, title: DELETE_ERRORS[failure.code] ?? `‘${sessionTitle(search)}’ 기록을 지우지 못했습니다.` });
    // 404: already gone; 409: it became active again elsewhere. Either way the list is stale.
    if (failure.code === 'not_found' || failure.code === 'search_active') reload();
  };

  return (
    <section className="panel discover-history" aria-labelledby="discover-history-title" aria-busy={loading}>
      <div className="panel-head">
        <h2 id="discover-history-title" ref={headingRef} tabIndex={-1}>
          검색 기록
        </h2>
        <button type="button" className="btn btn-secondary btn-small" onClick={reload} disabled={loading} aria-busy={loading}>
          <RefreshCw />
          {loading ? '불러오는 중…' : '새로 고침'}
        </button>
      </div>
      {currentId ? (
        <a className="btn btn-tonal btn-small discover-new-search" href={DISCOVER_HREF}>
          <Plus />새 검색
        </a>
      ) : null}
      <p className="field-hint">
        검색 1회나 인용·피인용 목록 1개가 <code translate="no">00-Inbox/discovery/searches/</code>의 JSON 1개입니다.
        자동으로 지우지 않습니다.
      </p>

      {error && error.code !== 'offline' ? (
        <ErrorNotice
          error={error}
          title={data ? '검색 기록을 다시 불러오지 못했습니다. 아래는 이전 결과입니다.' : '검색 기록을 불러오지 못했습니다.'}
          onRetry={reload}
        />
      ) : null}
      {deleteError ? <ErrorNotice error={deleteError.error} title={deleteError.title} /> : null}
      {data && data.errors.length > 0 ? (
        <div className="notice" data-tone="warning" role="status">
          <p className="notice-title">일부 검색 기록 파일을 읽지 못했습니다. 읽은 기록만 표시합니다.</p>
          <ul>
            {data.errors.map((item, index) => (
              <li key={`${index}:${item.file}`}>
                <code translate="no">{item.file}</code>: {item.error}
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {data ? (
        data.searches.length === 0 ? (
          <div className="empty empty-compact discover-history-empty">
            <HistoryIcon aria-hidden="true" />
            <p>아직 검색 기록이 없습니다. 새 검색을 시작하면 여기에 쌓입니다.</p>
          </div>
        ) : (
          <ul className="discover-history-list" role="list">
            {data.searches.map((search) => (
              <HistoryRow
                key={search.search_id}
                search={search}
                current={search.search_id === currentId}
                onDeleted={onDeleted}
                onFailed={onFailed}
              />
            ))}
          </ul>
        )
      ) : loading ? (
        <p className="loading-text" role="status">
          검색 기록을 불러오는 중…
        </p>
      ) : error?.code === 'offline' ? (
        <p className="empty empty-compact">서버를 실행하고 ‘다시 연결’을 누르면 검색 기록을 다시 불러옵니다.</p>
      ) : null}
    </section>
  );
}
