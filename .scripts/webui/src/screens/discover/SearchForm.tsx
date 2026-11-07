import { useEffect, useId, useRef, useState, type FormEvent, type KeyboardEvent, type Ref } from 'react';
import { ArrowRight, Search, X } from 'lucide-react';
import { createSearch, fetchPapers, toApiError, type ApiError } from '../../api/client';
import {
  DISCOVERY_CATEGORIES,
  type CreateSearchResponse,
  type DiscoverySearchRequest,
  type DiscoverySessionSummary,
  type PapersPayload,
} from '../../api/types';
import { ErrorNotice } from '../../components/ErrorNotice';
import { FilterSelect } from '../../components/FilterSelect';
import { formatCount } from '../../format';
import { STATUS_HREF, discoverSearchHref } from '../../hooks/useHashRoute';
import { blockedReason } from '../../roles';
import { useStatus } from '../../status';

// Server bounds of POST /api/discovery/searches (webui/discovery.py, §2.5); mirrored so the form
// explains a rejection before sending it. The server stays authoritative.
const QUERY_MIN = 3;
const QUERY_MAX = 500;
const YEAR_MIN = 1900;
const LIMIT_MIN = 1;
const LIMIT_MAX = 30;
const LIMIT_DEFAULT = 10;
const ANCHOR_MAX = 3;
/** Library rows shown at once in the anchor chooser; the filter narrows the rest. */
const ANCHOR_ROWS = 50;

/** Headline per error code of POST /api/discovery/searches (`search_active` has its own notice). */
const SUBMIT_ERRORS: Record<string, string> = {
  bad_request: '검색 조건이 서버 기준에 맞지 않습니다. 아래 메시지를 확인하세요.',
  role_config_error: 'omp 설정을 읽지 못해 검색을 시작하지 않았습니다. 상태 화면에서 역할 구성을 확인하세요.',
  searcher_unavailable: '검색 역할(paper-searcher)에 준비된 실행기가 없어 검색을 시작하지 않았습니다. 상태 화면에서 확인하세요.',
  shutting_down: '서버가 종료되는 중이라 검색을 시작하지 않았습니다.',
  cache_unsafe: '탐색 캐시 폴더가 안전하지 않아 검색을 기록하지 않았습니다. 00-Inbox/discovery 경로를 확인하세요.',
};

type FieldName = 'query' | 'yearFrom' | 'yearTo' | 'limit';
type FieldErrors = Partial<Record<FieldName, string>>;
const FIELD_ORDER: readonly FieldName[] = ['query', 'yearFrom', 'yearTo', 'limit'];

interface Draft {
  query: string;
  yearFrom: string;
  yearTo: string;
  limit: string;
  /** '' = no hint. */
  category: string;
  anchors: string[];
  verifiedOnly: boolean;
}

/** Field errors, and the request body when there are none. */
function validate(draft: Draft, maxYear: number): { errors: FieldErrors; payload: DiscoverySearchRequest | null } {
  const errors: FieldErrors = {};
  const query = draft.query.replace(/\s+/g, ' ').trim();
  const length = Array.from(query).length;
  if (length === 0) errors.query = '찾을 논문을 문장으로 적으세요.';
  else if (length < QUERY_MIN) errors.query = `검색어는 공백을 정리한 뒤 ${QUERY_MIN}자 이상이어야 합니다 (지금 ${length}자).`;
  else if (length > QUERY_MAX) {
    errors.query = `검색어는 공백을 정리한 뒤 ${QUERY_MAX}자 이하여야 합니다 (지금 ${formatCount(length)}자).`;
  }

  const year = (text: string, field: 'yearFrom' | 'yearTo'): number | null => {
    const value = text.trim();
    if (value === '') return null;
    const parsed = /^\d+$/.test(value) ? Number(value) : Number.NaN;
    if (parsed >= YEAR_MIN && parsed <= maxYear) return parsed;
    errors[field] = `연도는 ${YEAR_MIN}–${maxYear} 사이 네 자리 숫자로 적으세요.`;
    return null;
  };
  const yearFrom = year(draft.yearFrom, 'yearFrom');
  const yearTo = year(draft.yearTo, 'yearTo');
  if (yearFrom !== null && yearTo !== null && yearFrom > yearTo) {
    errors.yearTo = '끝 연도는 시작 연도와 같거나 그 뒤여야 합니다.';
  }

  const limitText = draft.limit.trim();
  const limit = limitText === '' ? LIMIT_DEFAULT : /^\d+$/.test(limitText) ? Number(limitText) : Number.NaN;
  if (!(limit >= LIMIT_MIN && limit <= LIMIT_MAX)) errors.limit = `편수는 ${LIMIT_MIN}–${LIMIT_MAX} 사이 정수로 적으세요.`;

  if (Object.keys(errors).length > 0) return { errors, payload: null };
  return {
    errors,
    payload: {
      query,
      year_from: yearFrom,
      year_to: yearTo,
      limit,
      category_hint: DISCOVERY_CATEGORIES.find((category) => category === draft.category) ?? null,
      anchors: draft.anchors,
      verified_only: draft.verifiedOnly,
    },
  };
}

/** `aria-describedby` of a field: its hint, plus its error while it has one. */
function describedBy(hintId: string, errorId: string, error: string | undefined): string {
  return error ? `${hintId} ${errorId}` : hintId;
}

interface LibraryState {
  data: PapersPayload | null;
  error: ApiError | null;
  loading: boolean;
}

interface AnchorPickerProps {
  selected: string[];
  onChange: (slugs: string[]) => void;
  library: LibraryState;
  onRetry: () => void;
}

/** 기준 논문: a filterable checkbox list of library papers, at most ANCHOR_MAX checked (Q9). */
function AnchorPicker({ selected, onChange, library, onRetry }: AnchorPickerProps) {
  const [filter, setFilter] = useState('');
  const filterId = useId();
  const countId = useId();
  const papers = library.data?.papers ?? [];
  const bySlug = new Map(papers.map((paper) => [paper.slug, paper]));
  const full = selected.length >= ANCHOR_MAX;
  const needle = filter.trim().toLocaleLowerCase('ko-KR');
  const matches = needle
    ? papers.filter((paper) =>
        [paper.display_title, paper.slug, ...paper.authors, ...paper.topics].some((text) =>
          text.toLocaleLowerCase('ko-KR').includes(needle),
        ),
      )
    : papers;
  const shown = matches.slice(0, ANCHOR_ROWS);

  const toggle = (slug: string) =>
    onChange(selected.includes(slug) ? selected.filter((item) => item !== slug) : [...selected, slug].slice(0, ANCHOR_MAX));

  const titleOf = (slug: string): string => bySlug.get(slug)?.display_title ?? slug;

  return (
    <fieldset className="discover-anchors">
      <legend className="field-label">기준 논문 (선택, 최대 {ANCHOR_MAX}편)</legend>
      <p className="field-hint">
        라이브러리 논문을 고르면 에이전트가 그 논문의 참고문헌·피인용과 비슷한 연구를 함께 살핍니다.
      </p>

      {selected.length > 0 ? (
        <ul className="discover-anchor-chips" role="list" aria-label="고른 기준 논문">
          {selected.map((slug) => (
            <li className="discover-anchor-chip" key={slug}>
              <span className="discover-anchor-chip-title">{titleOf(slug)}</span>
              <button
                type="button"
                className="icon-btn"
                aria-label={`기준 논문에서 빼기: ${titleOf(slug)}`}
                onClick={() => toggle(slug)}
              >
                <X />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <p className="field-hint" id={countId} role="status">
        <span className="num">{formatCount(selected.length)}</span>/<span className="num">{ANCHOR_MAX}</span>편 선택
        {full ? ' — 더 고르려면 먼저 하나를 빼세요.' : null}
      </p>

      {library.data === null ? (
        library.loading ? (
          <p className="loading-text" role="status">
            라이브러리 목록을 불러오는 중…
          </p>
        ) : library.error ? (
          <ErrorNotice
            error={library.error}
            title="라이브러리 목록을 불러오지 못해 기준 논문을 고를 수 없습니다. 기준 논문 없이도 검색할 수 있습니다."
            onRetry={onRetry}
          />
        ) : null
      ) : papers.length === 0 ? (
        <p className="empty empty-compact">라이브러리에 논문이 없어 고를 기준 논문이 없습니다.</p>
      ) : (
        <>
          <div className="field">
            <label htmlFor={filterId}>라이브러리에서 찾기</label>
            <span className="search-input">
              <Search />
              {/* Enter filters in place; it must not submit the search form around it. */}
              <input
                id={filterId}
                type="search"
                name="anchor-filter"
                placeholder="제목, 저자, 주제, slug로 찾기…"
                autoComplete="off"
                spellCheck={false}
                value={filter}
                onChange={(event) => setFilter(event.currentTarget.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter') event.preventDefault();
                }}
              />
            </span>
          </div>
          {shown.length === 0 ? (
            <p className="empty empty-compact">찾는 논문이 라이브러리에 없습니다.</p>
          ) : (
            <ul className="discover-anchor-list" role="list" aria-label="라이브러리 논문">
              {shown.map((paper) => {
                const checked = selected.includes(paper.slug);
                const disabled = full && !checked;
                const info = [paper.year === null ? null : String(paper.year), paper.authors[0] ?? null]
                  .filter(Boolean)
                  .join(' · ');
                return (
                  <li key={paper.slug}>
                    <label className="discover-anchor-option" data-disabled={disabled ? 'true' : undefined}>
                      <input
                        type="checkbox"
                        name="anchors"
                        value={paper.slug}
                        checked={checked}
                        disabled={disabled}
                        aria-describedby={disabled ? countId : undefined}
                        onChange={() => toggle(paper.slug)}
                      />
                      <span className="discover-anchor-text">
                        <span className="discover-anchor-title">{paper.display_title}</span>
                        {info ? <span className="caption">{info}</span> : null}
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
          {matches.length > shown.length ? (
            <p className="field-hint">
              <span className="num">{formatCount(matches.length)}</span>편 중{' '}
              <span className="num">{formatCount(shown.length)}</span>편만 보입니다. 검색어로 좁혀 보세요.
            </p>
          ) : null}
        </>
      )}
    </fieldset>
  );
}

interface SearchFormProps {
  /** `?q=` of an entry link (e.g. 라이브러리 "외부에서 찾기"). */
  prefill: string | null;
  /** The queued or running search from the history, if any (one search at a time, Q21). */
  active: DiscoverySessionSummary | null;
  reloadToken: number;
  sectionRef: Ref<HTMLElement>;
  onCreated: (response: CreateSearchResponse) => void;
  /** The server refused with 409 `search_active`: re-read the history so the running search shows. */
  onStale: () => void;
}

/** 새 검색 (Q9): a free sentence plus optional years, count, category hint, anchors and the venue filter. */
export function SearchForm({ prefill, active, reloadToken, sectionRef, onCreated, onStale }: SearchFormProps) {
  const [draft, setDraft] = useState<Draft>(() => ({
    query: prefill ?? '',
    yearFrom: '',
    yearTo: '',
    limit: String(LIMIT_DEFAULT),
    category: '',
    anchors: [],
    verifiedOnly: false,
  }));
  const [errors, setErrors] = useState<FieldErrors>({});
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<ApiError | null>(null);
  const [library, setLibrary] = useState<LibraryState>({ data: null, error: null, loading: true });
  const [libraryToken, setLibraryToken] = useState(0);
  const lastPrefill = useRef(prefill);
  const fieldRefs = useRef<Partial<Record<FieldName, HTMLInputElement | HTMLTextAreaElement | null>>>({});
  const ids = {
    query: useId(),
    queryHint: useId(),
    queryError: useId(),
    yearFrom: useId(),
    yearFromError: useId(),
    yearTo: useId(),
    yearToError: useId(),
    yearHint: useId(),
    limit: useId(),
    limitHint: useId(),
    limitError: useId(),
    verifiedHint: useId(),
    blocked: useId(),
  };
  const maxYear = new Date().getFullYear() + 1;
  const { data: status } = useStatus();
  const searcher = status?.searcher_role ?? null;
  const roleBlocked = searcher ? blockedReason(searcher) : null;

  // A later entry link (another `?q=`) replaces the query; the tab link without `?q=` keeps the draft.
  useEffect(() => {
    if (prefill === lastPrefill.current) return;
    lastPrefill.current = prefill;
    if (!prefill) return;
    setDraft((current) => ({ ...current, query: prefill }));
    setErrors((current) => ({ ...current, query: undefined }));
  }, [prefill]);

  useEffect(() => {
    const controller = new AbortController();
    setLibrary((current) => ({ ...current, loading: true }));
    fetchPapers(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setLibrary({ data, error: null, loading: false });
      },
      (error: unknown) => {
        if (!controller.signal.aborted) setLibrary((current) => ({ ...current, error: toApiError(error), loading: false }));
      },
    );
    return () => controller.abort();
  }, [libraryToken, reloadToken]);

  const set = <K extends keyof Draft>(key: K, value: Draft[K]) => {
    setDraft((current) => ({ ...current, [key]: value }));
    const field = FIELD_ORDER.find((name) => name === key);
    if (field && errors[field]) setErrors((current) => ({ ...current, [field]: undefined }));
  };

  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    if (submitting || active) return;
    const result = validate(draft, maxYear);
    setErrors(result.errors);
    setSubmitError(null);
    if (!result.payload) {
      const first = FIELD_ORDER.find((field) => result.errors[field]);
      if (first) fieldRefs.current[first]?.focus();
      return;
    }
    setSubmitting(true);
    try {
      onCreated(await createSearch(result.payload));
    } catch (caught) {
      const apiError = toApiError(caught);
      setSubmitError(apiError);
      if (apiError.code === 'search_active') onStale();
    } finally {
      setSubmitting(false);
    }
  };

  const onQueryKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && (event.metaKey || event.ctrlKey)) {
      event.preventDefault();
      void submit();
    }
  };

  const categoryLabels = library.data?.labels.category ?? {};
  const categoryOptions = DISCOVERY_CATEGORIES.map((value) => ({ value, label: categoryLabels[value] ?? value }));
  const length = Array.from(draft.query.replace(/\s+/g, ' ').trim()).length;
  const activeNotice = active !== null || submitError?.code === 'search_active';

  return (
    <section className="panel discover-form-panel" ref={sectionRef} tabIndex={-1} aria-labelledby="discover-form-title">
      <div className="panel-head">
        <h2 id="discover-form-title">새 검색</h2>
      </div>
      <p className="field-hint">
        에이전트가 Semantic Scholar·arXiv·OpenAlex 같은 외부 학술 DB에서 라이브러리에 없는 논문을 찾습니다. 검색은 한
        번에 하나만 실행하고 최대 15분 걸립니다. 결과는 Git에서 제외된 로컬 캐시에 남습니다.
      </p>

      {roleBlocked ? (
        <div className="notice" data-tone="warning">
          <p className="notice-title">
            검색 역할(<code translate="no">paper-searcher</code>)이 준비되지 않았습니다.
          </p>
          <p className="notice-detail">{roleBlocked}</p>
          <div className="notice-actions">
            <a className="btn btn-secondary btn-small" href={STATUS_HREF}>
              상태 화면에서 확인
              <ArrowRight />
            </a>
          </div>
        </div>
      ) : null}

      {activeNotice ? (
        <div className="notice" data-tone="warning" id={ids.blocked}>
          <p className="notice-title">다른 검색이 진행 중입니다 — 기록에서 확인하세요.</p>
          <p>검색은 한 번에 하나만 실행합니다. 진행 중인 검색이 끝나거나 취소되면 새 검색을 시작할 수 있습니다.</p>
          {active ? (
            <div className="notice-actions">
              <a className="btn btn-secondary btn-small" href={discoverSearchHref(active.search_id)}>
                진행 중인 검색 보기
                <ArrowRight />
              </a>
            </div>
          ) : null}
        </div>
      ) : null}

      <form className="discover-form" noValidate aria-busy={submitting} onSubmit={(event) => void submit(event)}>
        <div className="field discover-query-field">
          <label htmlFor={ids.query}>찾을 논문</label>
          <textarea
            id={ids.query}
            ref={(node) => {
              fieldRefs.current.query = node;
            }}
            name="query"
            className="input discover-query-input"
            rows={3}
            required
            value={draft.query}
            placeholder="예: WiFi CSI로 사람 자세를 추정하는 최근 연구…"
            aria-invalid={errors.query ? true : undefined}
            aria-describedby={describedBy(ids.queryHint, ids.queryError, errors.query)}
            onChange={(event) => set('query', event.currentTarget.value)}
            onKeyDown={onQueryKeyDown}
          />
          <div className="discover-query-foot">
            <p className="field-hint" id={ids.queryHint}>
              자유 문장으로 적으세요. 공백을 정리한 뒤 {QUERY_MIN}–{QUERY_MAX}자.{' '}
              <kbd>⌘</kbd>/<kbd>Ctrl</kbd>&nbsp;+&nbsp;<kbd>Enter</kbd>로 검색을 시작합니다.
            </p>
            <span className="discover-query-count num" data-over={length > QUERY_MAX ? 'true' : undefined}>
              {formatCount(length)}/{formatCount(QUERY_MAX)}
            </span>
          </div>
          {errors.query ? (
            <p className="field-error" id={ids.queryError}>
              {errors.query}
            </p>
          ) : null}
        </div>

        <div className="discover-form-row">
          <fieldset className="discover-years">
            <legend className="field-label">연도 범위 (선택)</legend>
            <div className="discover-years-fields">
              <div className="field">
                <label htmlFor={ids.yearFrom}>시작 연도</label>
                <input
                  id={ids.yearFrom}
                  ref={(node) => {
                    fieldRefs.current.yearFrom = node;
                  }}
                  type="text"
                  inputMode="numeric"
                  name="year_from"
                  autoComplete="off"
                  maxLength={4}
                  placeholder="예: 2020…"
                  value={draft.yearFrom}
                  aria-invalid={errors.yearFrom ? true : undefined}
                  aria-describedby={describedBy(ids.yearHint, ids.yearFromError, errors.yearFrom)}
                  onChange={(event) => set('yearFrom', event.currentTarget.value)}
                />
                {errors.yearFrom ? (
                  <p className="field-error" id={ids.yearFromError}>
                    {errors.yearFrom}
                  </p>
                ) : null}
              </div>
              <div className="field">
                <label htmlFor={ids.yearTo}>끝 연도</label>
                <input
                  id={ids.yearTo}
                  ref={(node) => {
                    fieldRefs.current.yearTo = node;
                  }}
                  type="text"
                  inputMode="numeric"
                  name="year_to"
                  autoComplete="off"
                  maxLength={4}
                  placeholder={`예: ${maxYear - 1}…`}
                  value={draft.yearTo}
                  aria-invalid={errors.yearTo ? true : undefined}
                  aria-describedby={describedBy(ids.yearHint, ids.yearToError, errors.yearTo)}
                  onChange={(event) => set('yearTo', event.currentTarget.value)}
                />
                {errors.yearTo ? (
                  <p className="field-error" id={ids.yearToError}>
                    {errors.yearTo}
                  </p>
                ) : null}
              </div>
            </div>
            <p className="field-hint" id={ids.yearHint}>
              {YEAR_MIN}–{maxYear} 사이로 적고, 비우면 제한하지 않습니다.
            </p>
          </fieldset>
          <div className="field">
            <label htmlFor={ids.limit}>편수</label>
            <input
              id={ids.limit}
              ref={(node) => {
                fieldRefs.current.limit = node;
              }}
              type="text"
              inputMode="numeric"
              name="limit"
              autoComplete="off"
              maxLength={2}
              value={draft.limit}
              aria-invalid={errors.limit ? true : undefined}
              aria-describedby={describedBy(ids.limitHint, ids.limitError, errors.limit)}
              onChange={(event) => set('limit', event.currentTarget.value)}
            />
            <p className="field-hint" id={ids.limitHint}>
              {LIMIT_MIN}–{LIMIT_MAX}편, 비우면 {LIMIT_DEFAULT}편
            </p>
            {errors.limit ? (
              <p className="field-error" id={ids.limitError}>
                {errors.limit}
              </p>
            ) : null}
          </div>
          <FilterSelect
            label="분야 힌트"
            value={draft.category}
            options={categoryOptions}
            onChange={(category) => set('category', category)}
          />
        </div>

        <AnchorPicker
          selected={draft.anchors}
          onChange={(anchors) => set('anchors', anchors)}
          library={library}
          onRetry={() => setLibraryToken((token) => token + 1)}
        />

        <div className="discover-form-switch">
          <label className="switch">
            <input
              type="checkbox"
              role="switch"
              name="verified_only"
              checked={draft.verifiedOnly}
              aria-describedby={ids.verifiedHint}
              onChange={(event) => set('verifiedOnly', event.currentTarget.checked)}
            />
            <span className="switch-track" aria-hidden="true" />
            학회 게재 확인된 것만
          </label>
          <p className="field-hint" id={ids.verifiedHint}>
            켜면 공식 출처에서 게재·채택을 확인한 논문만 후보로 받습니다. 프리프린트는 빠집니다.
          </p>
        </div>

        <div className="discover-form-actions">
          <button
            type="submit"
            className="btn btn-primary"
            disabled={submitting || active !== null}
            aria-busy={submitting}
            aria-describedby={active ? ids.blocked : undefined}
          >
            <Search />
            {submitting ? '요청하는 중…' : '검색 시작'}
          </button>
        </div>

        {submitError && submitError.code !== 'search_active' ? (
          <ErrorNotice error={submitError} title={SUBMIT_ERRORS[submitError.code] ?? '검색을 시작하지 못했습니다.'} />
        ) : null}
      </form>
    </section>
  );
}
