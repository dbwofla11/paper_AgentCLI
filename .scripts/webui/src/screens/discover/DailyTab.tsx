import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowRight, CalendarDays, RefreshCw } from 'lucide-react';
import { fetchDailyDigests, toApiError, type ApiError } from '../../api/client';
import type { DailyDigestList, DailyDigestSummary } from '../../api/types';
import { EmptyState } from '../../components/EmptyState';
import { ErrorNotice } from '../../components/ErrorNotice';
import { formatCount } from '../../format';
import { discoverDailyHref } from '../../hooks/useHashRoute';
import { DailyDay, SLOT_LABELS, formatDay } from './DailyDay';

interface LoadState {
  data: DailyDigestList | null;
  error: ApiError | null;
  loading: boolean;
}

function DayRow({ day, current }: { day: DailyDigestSummary; current: boolean }) {
  const total = day.slots.length || 3;
  return (
    <li>
      <a className="discover-day-row" href={discoverDailyHref(day.date)} aria-current={current ? 'page' : undefined}>
        <span className="discover-day-row-title">{formatDay(day.date)}</span>
        <span className="badge" data-tone={day.filled >= total ? 'success' : day.filled === 0 ? 'neutral' : 'waiting'}>
          후보&nbsp;<span className="num">{formatCount(day.filled)}</span>/<span className="num">{formatCount(total)}</span>
        </span>
        <span className="discover-day-row-slots">
          {day.slots.map((slot, index) => (
            <span className="discover-day-row-slot" key={`${index}:${slot.slot}`}>
              {SLOT_LABELS[slot.slot] ?? slot.slot}: {slot.title ?? '비어 있음'}
            </span>
          ))}
        </span>
      </a>
    </li>
  );
}

function NoDays() {
  return (
    <EmptyState icon={CalendarDays} title="아직 일일 후보가 없습니다">
      <p>
        <code translate="no">daily-digest-loop</code> 자동화가 후보를 채팅으로 보고하면서{' '}
        <code translate="no">00-Inbox/discovery/daily/YYYY-MM-DD.json</code>에 기록하면 여기에 날짜별로 표시됩니다.
      </p>
      <p>일일 후보 실행은 자동화가 맡습니다. 이 화면에서는 기록된 결과만 봅니다.</p>
    </EmptyState>
  );
}

/** `#/discover/daily[/{date}]`: the days daily-digest-loop recorded (newest first) beside one selected day. */
export function DailyTab({ date, reloadToken }: { date: string | null; reloadToken: number }) {
  const [state, setState] = useState<LoadState>({ data: null, error: null, loading: true });
  const [refreshToken, setRefreshToken] = useState(0);
  const controllerRef = useRef<AbortController | null>(null);
  const detailRef = useRef<HTMLElement>(null);
  const previousDate = useRef(date);

  const load = useCallback(() => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setState((previous) => ({ ...previous, loading: true }));
    fetchDailyDigests(controller.signal).then(
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

  // Choosing another day moves focus to its panel so the new content is announced (JobsScreen pattern).
  useEffect(() => {
    if (previousDate.current === date) return;
    previousDate.current = date;
    detailRef.current?.focus();
  }, [date]);

  const refresh = () => {
    load();
    setRefreshToken((token) => token + 1);
  };

  const { data, error, loading } = state;
  const newest = data?.days[0] ?? null;

  const notices = (
    <>
      {error && error.code !== 'offline' ? (
        <ErrorNotice
          error={error}
          title={data ? '날짜 목록을 다시 불러오지 못했습니다. 아래는 이전 결과입니다.' : '날짜 목록을 불러오지 못했습니다.'}
          onRetry={load}
        />
      ) : null}
      {data && data.errors.length > 0 ? (
        <div className="notice" data-tone="warning" role="status">
          <p className="notice-title">일부 일일 후보 파일을 읽지 못했습니다. 읽은 날짜만 표시합니다.</p>
          <ul>
            {data.errors.map((item, index) => (
              <li key={`${index}:${item.file}`}>
                <code translate="no">{item.file}</code>: {item.error}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </>
  );

  // Nothing recorded and no day asked for: one empty state instead of two empty panels.
  if (data && data.days.length === 0 && date === null) {
    return (
      <div className="discover-view">
        {notices}
        <NoDays />
      </div>
    );
  }

  return (
    <div className="discover-daily">
      <section className="panel discover-days" aria-labelledby="discover-days-title" aria-busy={loading}>
        <div className="panel-head">
          <h2 id="discover-days-title">날짜</h2>
          <button type="button" className="btn btn-secondary btn-small" onClick={refresh} disabled={loading} aria-busy={loading}>
            <RefreshCw />
            {loading ? '불러오는 중…' : '새로 고침'}
          </button>
        </div>
        <p className="field-hint">
          <code translate="no">daily-digest-loop</code> 자동화가 기록한 로컬 캐시입니다. 실행은 자동화가 맡습니다.
        </p>
        {notices}
        {data ? (
          data.days.length === 0 ? (
            <p className="empty empty-compact">기록된 날짜가 없습니다.</p>
          ) : (
            <ul className="discover-day-list" role="list">
              {data.days.map((day) => (
                <DayRow key={day.date} day={day} current={day.date === date} />
              ))}
            </ul>
          )
        ) : loading ? (
          <p className="loading-text" role="status">
            날짜 목록을 불러오는 중…
          </p>
        ) : error?.code === 'offline' ? (
          <p className="empty empty-compact">서버를 실행하고 ‘다시 연결’을 누르면 날짜 목록을 다시 불러옵니다.</p>
        ) : null}
      </section>

      {date ? (
        <DailyDay key={date} date={date} refreshToken={refreshToken + reloadToken} sectionRef={detailRef} />
      ) : (
        <section className="panel discover-day" ref={detailRef} tabIndex={-1} aria-labelledby="discover-day-empty-title">
          <div className="panel-head">
            <h2 id="discover-day-empty-title">선택한 날짜 없음</h2>
          </div>
          <p className="empty empty-compact">
            목록에서 날짜를 고르면 그날의 컴퓨터 비전·멀티모달·관심 분야 후보와 검색 보고가 여기에 표시됩니다.
          </p>
          {newest ? (
            <a className="btn btn-tonal btn-small discover-newest" href={discoverDailyHref(newest.date)}>
              최신 {formatDay(newest.date)} 후보 보기
              <ArrowRight />
            </a>
          ) : null}
        </section>
      )}
    </div>
  );
}
