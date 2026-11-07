import { useId, type Ref } from 'react';
import * as m from 'motion/react-m';
import type { ApiError } from '../../api/client';
import type { DailyReport } from '../../api/types';
import { ErrorNotice } from '../../components/ErrorNotice';
import { FileLink } from '../../components/FileLink';
import { Skeleton } from '../../components/Skeleton';
import { formatCount, formatDateTime } from '../../format';
import { DUR_FAST, EASE_STANDARD } from '../../motion/tokens';
import type { CandidateActionHandlers } from './CandidateActions';
import { CandidateCard, isSkipped } from './CandidateCard';
import { useDailyDay } from './useDiscovery';

/** daily-digest-loop slots (Q19), always in this order. */
export const SLOT_LABELS: Record<string, string> = {
  'computer-vision': '컴퓨터 비전',
  multimodal: '멀티모달',
  interest: '관심 분야',
};

const dateFormat = new Intl.DateTimeFormat('ko-KR', { year: 'numeric', month: 'long', day: 'numeric' });
const weekdayFormat = new Intl.DateTimeFormat('ko-KR', { weekday: 'short' });

/** `YYYY-MM-DD` (a KST calendar date) → `2026년 11월 7일 (토)`; anything else is shown as-is. */
export function formatDay(date: string): string {
  const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date);
  if (!parts) return date;
  const day = new Date(Number(parts[1]), Number(parts[2]) - 1, Number(parts[3]));
  return Number.isNaN(day.getTime()) ? date : `${dateFormat.format(day)} (${weekdayFormat.format(day)})`;
}

/** Headline per error code of GET /api/discovery/daily/{date}; codes without retry cannot change by retrying. */
function errorTitle(error: ApiError, day: string, stale: boolean): { title: string; retry: boolean } {
  if (stale) return { title: '일일 후보를 다시 불러오지 못했습니다. 아래는 이전 결과입니다.', retry: true };
  if (error.code === 'not_found') return { title: `${day} 일일 후보 기록이 없습니다.`, retry: false };
  if (error.code === 'bad_request') return { title: '날짜 주소가 올바르지 않습니다. 목록에서 날짜를 고르세요.', retry: false };
  if (error.code === 'cache_corrupt') return { title: `${day} 일일 후보 파일을 읽지 못했습니다.`, retry: true };
  return { title: `${day} 일일 후보를 불러오지 못했습니다.`, retry: true };
}

export function ReportList({ items, mono = false }: { items: string[]; mono?: boolean }) {
  if (items.length === 0) return <>없음</>;
  return (
    <ul className="discover-report-list">
      {items.map((item, index) => (
        <li key={`${index}:${item}`}>{mono ? <code translate="no">{item}</code> : item}</li>
      ))}
    </ul>
  );
}

/** The digest's search report, folded: queries, sources, coverage gaps and notes. */
function DailyReportDetails({ report }: { report: DailyReport }) {
  return (
    <details className="discover-report">
      <summary>
        검색 보고{' '}
        <span className="caption">
          질의 <span className="num">{formatCount(report.queries.length)}</span> · 소스{' '}
          <span className="num">{formatCount(report.sources.length)}</span> · 누락 범위{' '}
          <span className="num">{formatCount(report.coverage_gaps.length)}</span>
        </span>
      </summary>
      <dl className="facts">
        <dt>질의</dt>
        <dd>
          <ReportList items={report.queries} mono />
        </dd>
        <dt>소스</dt>
        <dd>{report.sources.length > 0 ? <span translate="no">{report.sources.join(' · ')}</span> : '없음'}</dd>
        <dt>누락 범위</dt>
        <dd>
          <ReportList items={report.coverage_gaps} />
        </dd>
        <dt>메모</dt>
        <dd className="discover-report-notes">{report.notes || '없음'}</dd>
      </dl>
    </details>
  );
}

interface DailyDayProps {
  date: string;
  /** Changes when the list's 새로 고침 runs or after a reconnect; the shown day reloads in place. */
  refreshToken: number;
  sectionRef: Ref<HTMLElement>;
}

/**
 * One day of `#/discover/daily/{date}`: three slot cards (or why a slot stayed empty), the plan file and
 * the report. Slot cards carry the same actions as search results; a 넘긴 candidate stays in its slot,
 * collapsed to its title and 복원.
 */
export function DailyDay({ date, refreshToken, sectionRef }: DailyDayProps) {
  const headingId = useId();
  const { data, error, loading, reload, settle, update } = useDailyDay(date, refreshToken);
  const day = formatDay(date);
  const daily = data?.daily ?? null;
  const filled = daily ? daily.slots.filter((slot) => slot.candidate !== null).length : 0;
  const notice = error ? errorTitle(error, day, data !== null) : null;

  const actions: CandidateActionHandlers = {
    source: { kind: 'daily', id: date },
    onCandidate: (candidate) =>
      update((current) => ({
        ...current,
        daily: {
          ...current.daily,
          slots: current.daily.slots.map((slot) =>
            slot.candidate?.candidate_id === candidate.candidate_id ? { ...slot, candidate } : slot,
          ),
        },
      })),
    onRefresh: (candidateId, until) =>
      settle(
        until &&
          ((current) =>
            until(current.daily.slots.find((slot) => slot.candidate?.candidate_id === candidateId)?.candidate ?? undefined)),
      ),
  };

  return (
    <section className="panel discover-day" ref={sectionRef} tabIndex={-1} aria-labelledby={headingId} aria-busy={loading}>
      <div className="panel-head">
        <h2 id={headingId}>{day}</h2>
        {daily ? (
          <span className="meta">
            후보 <span className="num">{formatCount(filled)}</span>/<span className="num">{formatCount(daily.slots.length)}</span>
          </span>
        ) : null}
      </div>

      {error && notice && error.code !== 'offline' ? (
        <ErrorNotice error={error} title={notice.title} onRetry={notice.retry ? reload : undefined} />
      ) : null}

      {daily ? (
        <>
          <dl className="session-facts">
            <div>
              <dt>기록 시각</dt>
              <dd className="num">{formatDateTime(daily.created_at)}</dd>
            </div>
            <div>
              <dt>선정 계획</dt>
              <dd>{daily.plan_path ? <FileLink path={daily.plan_path} href={data?.plan_href} /> : '없음'}</dd>
            </div>
          </dl>
          <m.ol
            className="discover-slots"
            role="list"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: DUR_FAST, ease: EASE_STANDARD }}
          >
            {daily.slots.map((slot, index) => (
              <li className="discover-slot" key={`${index}:${slot.slot}`}>
                <div className="discover-slot-head">
                  <h3>{SLOT_LABELS[slot.slot] ?? slot.slot}</h3>
                  {slot.topic ? <p className="caption">주제: {slot.topic}</p> : null}
                </div>
                {slot.candidate ? (
                  <CandidateCard
                    candidate={slot.candidate}
                    titleLevel={4}
                    actions={actions}
                    collapsed={isSkipped(slot.candidate)}
                  />
                ) : (
                  <div className="empty empty-compact discover-unfilled">
                    <p className="discover-unfilled-title">채우지 못한 슬롯</p>
                    <p>{slot.unfilled_reason ?? '사유가 기록되지 않았습니다.'}</p>
                  </div>
                )}
              </li>
            ))}
          </m.ol>
          <DailyReportDetails report={daily.report} />
        </>
      ) : loading ? (
        <div className="discover-day-skeleton" role="status">
          <span className="visually-hidden">{day} 일일 후보를 불러오는 중…</span>
          {Array.from({ length: 3 }, (_, index) => (
            <Skeleton key={index} height="11rem" />
          ))}
        </div>
      ) : error?.code === 'offline' ? (
        <p className="empty empty-compact">서버를 실행하고 ‘다시 연결’을 누르면 일일 후보를 다시 불러옵니다.</p>
      ) : null}
    </section>
  );
}
