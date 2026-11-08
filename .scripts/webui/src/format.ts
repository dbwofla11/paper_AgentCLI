const LOCALE = 'ko-KR';

const dateTimeFormat = new Intl.DateTimeFormat(LOCALE, { dateStyle: 'medium', timeStyle: 'medium' });
const timeFormat = new Intl.DateTimeFormat(LOCALE, { timeStyle: 'medium' });
const usdFormat = new Intl.NumberFormat(LOCALE, {
  style: 'currency',
  currency: 'USD',
  minimumFractionDigits: 2,
  maximumFractionDigits: 4,
});
const secondsFormat = new Intl.NumberFormat(LOCALE, { style: 'unit', unit: 'second', maximumFractionDigits: 1 });
const minutesFormat = new Intl.NumberFormat(LOCALE, { style: 'unit', unit: 'minute' });
const countFormat = new Intl.NumberFormat(LOCALE);

/** ISO-8601 timestamp → local date and time; unparsable input is shown as-is. */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : dateTimeFormat.format(date);
}

export function formatTime(date: Date): string {
  return timeFormat.format(date);
}

export function formatCost(value: number | null | undefined): string | null {
  return value == null ? null : usdFormat.format(value);
}

export function formatDuration(ms: number | null | undefined): string | null {
  if (ms == null) return null;
  if (ms < 60_000) return secondsFormat.format(ms / 1000);
  const minutes = Math.floor(ms / 60_000);
  return `${minutesFormat.format(minutes)} ${secondsFormat.format(Math.floor((ms % 60_000) / 1000))}`;
}

export function formatCount(value: number): string {
  return countFormat.format(value);
}

/** Job records, review-queue entries, and reader thread turns share these status names. */
const STATUS_LABELS: Record<string, string> = {
  queued: '대기 중',
  running: '실행 중',
  completed: '완료',
  failed: '실패',
  cancelled: '취소됨',
  /** Reader turn whose job the server no longer knows (e.g. the server restarted mid-answer). */
  interrupted: '중단됨',
};

export type Tone = 'neutral' | 'waiting' | 'active' | 'success' | 'warning' | 'danger';

const STATUS_TONES: Record<string, Tone> = {
  queued: 'waiting',
  running: 'active',
  completed: 'success',
  failed: 'danger',
  cancelled: 'neutral',
  interrupted: 'warning',
};

export function statusLabel(status: string): string {
  return STATUS_LABELS[status] ?? status;
}

export function statusTone(status: string): Tone {
  return STATUS_TONES[status] ?? 'neutral';
}

const JOB_KIND_LABELS: Record<string, string> = {
  'agent.ping': '에이전트 연결 확인',
  'paper.ask': '논문 질문',
  'harness.verify': '하네스 구조 검사',
  'harness.tests': '하네스 테스트',
  'discovery.search': '논문 탐색 검색',
  'discovery.register': '논문 등록',
  'review.visual': '시각 요약 생성',
};

export function jobKindLabel(kind: string): string {
  return JOB_KIND_LABELS[kind] ?? kind;
}
