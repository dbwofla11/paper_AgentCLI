import type { PaperLabels, PaperSummary } from '../../api/types';

/** Filter value meaning "the field is empty" (category or year missing). */
export const NONE = '__none__';

export interface LibraryStats {
  total: number;
  /** structured_review_status === 'complete' */
  reviewed: number;
  /** reading_status ∈ queued_statuses */
  queued: number;
  /** Distinct non-empty categories. */
  categories: number;
  withPdf: number;
}

export function libraryStats(papers: PaperSummary[], queuedStatuses: string[]): LibraryStats {
  const queued = new Set(queuedStatuses);
  return {
    total: papers.length,
    reviewed: papers.filter((paper) => paper.structured_review_status === 'complete').length,
    queued: papers.filter((paper) => paper.reading_status !== null && queued.has(paper.reading_status)).length,
    categories: new Set(papers.map((paper) => paper.category).filter(Boolean)).size,
    withPdf: papers.filter((paper) => paper.has_pdf).length,
  };
}

export interface BarDatum {
  key: string;
  label: string;
  count: number;
}

export function categoryLabel(category: string | null, labels: PaperLabels): string {
  return category ? (labels.category[category] ?? category) : '미분류';
}

export function readingStatusLabel(status: string | null, labels: PaperLabels): string | null {
  return status ? (labels.reading_status[status] ?? status) : null;
}

function tally<K extends string | number>(values: (K | null)[]): Map<K | null, number> {
  const counts = new Map<K | null, number>();
  for (const value of values) counts.set(value, (counts.get(value) ?? 0) + 1);
  return counts;
}

/** Newest year first; papers without a year last. */
export function countByYear(papers: PaperSummary[]): BarDatum[] {
  return [...tally(papers.map((paper) => paper.year))]
    .sort(([a], [b]) => (a === null ? 1 : b === null ? -1 : b - a))
    .map(([year, count]) => ({ key: year === null ? NONE : String(year), label: year === null ? '연도 미상' : String(year), count }));
}

/** Largest category first, then by label. */
export function countByCategory(papers: PaperSummary[], labels: PaperLabels): BarDatum[] {
  return [...tally(papers.map((paper) => paper.category))]
    .map(([category, count]) => ({ key: category ?? NONE, label: categoryLabel(category, labels), count }))
    .sort((a, b) => b.count - a.count || a.label.localeCompare(b.label, 'ko-KR'));
}

export interface LibraryFilter {
  query: string;
  /** '' = all, NONE = no category, else a category key. */
  category: string;
  /** '' = all, else a reading_status. */
  status: string;
  /** '' = all, NONE = no year, else the year. */
  year: string;
  pdfOnly: boolean;
}

export const EMPTY_FILTER: LibraryFilter = { query: '', category: '', status: '', year: '', pdfOnly: false };

export function isFiltered(filter: LibraryFilter): boolean {
  return Boolean(filter.query.trim() || filter.category || filter.status || filter.year || filter.pdfOnly);
}

/** Text the search box matches: titles, slug, authors, topics, abstract, one-line summary, venue. */
function searchText(paper: PaperSummary): string {
  return [
    paper.display_title,
    paper.title,
    paper.slug,
    paper.venue,
    paper.one_line_summary,
    paper.abstract,
    ...paper.authors,
    ...paper.topics,
  ]
    .filter(Boolean)
    .join('\n')
    .toLocaleLowerCase('ko-KR');
}

export function filterPapers(papers: PaperSummary[], filter: LibraryFilter): PaperSummary[] {
  const needle = filter.query.trim().toLocaleLowerCase('ko-KR');
  return papers.filter((paper) => {
    if (filter.pdfOnly && !paper.has_pdf) return false;
    if (filter.category && (paper.category ?? NONE) !== filter.category) return false;
    if (filter.status && paper.reading_status !== filter.status) return false;
    if (filter.year && (paper.year === null ? NONE : String(paper.year)) !== filter.year) return false;
    return !needle || searchText(paper).includes(needle);
  });
}

export interface FilterOption {
  value: string;
  label: string;
}

/** Select options built from the values present in the library. */
export function filterOptions(papers: PaperSummary[], labels: PaperLabels) {
  const statuses = [...new Set(papers.map((paper) => paper.reading_status).filter((status) => status !== null))];
  // Keep the server's label order (candidate → keep → … → rejected); unknown statuses last.
  const statusOrder = Object.keys(labels.reading_status);
  statuses.sort((a, b) => {
    const ia = statusOrder.indexOf(a);
    const ib = statusOrder.indexOf(b);
    return (ia < 0 ? Infinity : ia) - (ib < 0 ? Infinity : ib) || a.localeCompare(b);
  });
  return {
    categories: countByCategory(papers, labels).map(({ key, label }): FilterOption => ({ value: key, label })),
    statuses: statuses.map((status): FilterOption => ({ value: status, label: readingStatusLabel(status, labels) ?? status })),
    years: countByYear(papers).map(({ key, label }): FilterOption => ({ value: key, label })),
  };
}
