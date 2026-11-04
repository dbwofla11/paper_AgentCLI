import type { Idea } from '../../api/types';
import type { Tone } from '../../format';

export const UNRECORDED = '미기록';

export type IdeaSort = 'date' | 'title';

/** Filter keys mirror the static page's selects; each matches one Idea field exactly. */
export interface IdeaFilter {
  query: string;
  validation: string;
  review: string;
  literature: string;
  decision: string;
  experiment: string;
  todoStatus: string;
  sort: IdeaSort;
}

export type IdeaFilterKey = Exclude<keyof IdeaFilter, 'query' | 'sort'>;

export const IDEA_FILTER_FIELDS: ReadonlyArray<{ key: IdeaFilterKey; label: string }> = [
  { key: 'validation', label: '심사 상태' },
  { key: 'review', label: '역할 심사' },
  { key: 'literature', label: '문헌 상태' },
  { key: 'decision', label: '사용자 결정' },
  { key: 'experiment', label: '실험 상태' },
  { key: 'todoStatus', label: '조사 TODO' },
];

export const EMPTY_IDEA_FILTER: IdeaFilter = {
  query: '',
  validation: '',
  review: '',
  literature: '',
  decision: '',
  experiment: '',
  todoStatus: '',
  sort: 'date',
};

export function isIdeaFiltered(filter: IdeaFilter): boolean {
  return Boolean(filter.query.trim()) || IDEA_FILTER_FIELDS.some(({ key }) => filter[key] !== '');
}

/** Distinct values of every filter field, sorted for the selects. */
export function ideaFilterOptions(ideas: readonly Idea[]): Record<IdeaFilterKey, { value: string; label: string }[]> {
  const options = {} as Record<IdeaFilterKey, { value: string; label: string }[]>;
  for (const { key } of IDEA_FILTER_FIELDS) {
    options[key] = [...new Set(ideas.map((idea) => idea[key]))]
      .sort((a, b) => a.localeCompare(b, 'ko'))
      .map((value) => ({ value, label: value }));
  }
  return options;
}

/** Search covers the title and hypothesis (plus topics once recorded); selects match exactly. */
export function filterIdeas(ideas: readonly Idea[], filter: IdeaFilter): Idea[] {
  const query = filter.query.trim().toLocaleLowerCase();
  const rows = ideas.filter((idea) => {
    if (IDEA_FILTER_FIELDS.some(({ key }) => filter[key] !== '' && idea[key] !== filter[key])) return false;
    if (!query) return true;
    const topics = idea.topics === UNRECORDED ? '' : idea.topics;
    return `${idea.title} ${idea.hypothesis} ${topics}`.toLocaleLowerCase().includes(query);
  });
  return rows.sort((a, b) =>
    filter.sort === 'title' ? a.title.localeCompare(b.title, 'ko') : b.updated.localeCompare(a.updated),
  );
}

/** Keyword tones for free-text critique and decision states; anything else recorded reads as active. */
const TONE_KEYWORDS: ReadonlyArray<{ tone: Tone; words: readonly string[] }> = [
  { tone: 'danger', words: ['기각', '반려', '폐기', '중단', 'reject', 'fail', 'drop'] },
  { tone: 'warning', words: ['보류', '수정', '재검토', '대기', '충돌', 'revise', 'hold', 'pending'] },
  { tone: 'success', words: ['통과', '승인', '완료', '채택', '기록 있음', 'pass', 'accept', 'done', 'complete'] },
];

export function stateTone(value: string): Tone {
  if (!value || value === UNRECORDED) return 'neutral';
  const text = value.toLocaleLowerCase();
  return TONE_KEYWORDS.find(({ words }) => words.some((word) => text.includes(word)))?.tone ?? 'active';
}

const ROLE_LABELS: Record<string, string> = { method: '방법', repro: '재현성', novelty: '새로움' };

/** `method: 통과, repro: 수정, novelty: 통과` → labelled parts; null when the text has another shape. */
export function reviewParts(review: string): { role: string; label: string; status: string }[] | null {
  const parts = review.split(/,\s*(?=(?:method|repro|novelty):)/).map((part) => /^(method|repro|novelty):\s*(.*)$/.exec(part.trim()));
  if (parts.length === 0 || parts.some((part) => part === null)) return null;
  return parts.map((part) => {
    const [, role, status] = part as RegExpExecArray;
    return { role, label: ROLE_LABELS[role], status: status || UNRECORDED };
  });
}

/** Library slug of a `01-Papers/library/<slug>.json` record path (the reader route key), else null. */
export function librarySlug(path: string): string | null {
  return /^01-Papers\/library\/([a-z0-9-]+)\.json$/.exec(path)?.[1] ?? null;
}
