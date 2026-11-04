import type { EvidenceItem, EvidenceTarget } from '../api/types';
import type { PageTarget } from './PdfPage';

/** The 5 review axes in record order (paper-record.schema.json), with their review headings. */
export const AXES: ReadonlyArray<{ key: string; title: string }> = [
  { key: 'problem_and_prior_work', title: '문제와 기존 연구' },
  { key: 'core_idea_and_difference', title: '핵심 아이디어와 차이' },
  { key: 'evaluation_and_evidence', title: '성능 지표와 검증' },
  { key: 'limitations_and_future_work', title: '한계와 확장 방향' },
  { key: 'related_work', title: '관련 연구 속 위치' },
];

export const CLAIM_KIND_LABELS: Record<string, string> = {
  paper_fact: '원문 사실',
  analysis: '분석',
  inference: '추론',
  unknown: '확인 필요',
};

export function shorten(text: string, length: number): string {
  const flat = text.replace(/\s+/g, ' ').trim();
  return flat.length > length ? `${flat.slice(0, length - 1)}…` : flat;
}

export function targetKey(claimId: string, targetIndex: number): string {
  return `${claimId}#${targetIndex}`;
}

/** Claim targets per PDF page, for the highlight layers (targets without a page are left out). */
export function targetsByPage(items: readonly EvidenceItem[]): Map<number, PageTarget[]> {
  const pages = new Map<number, PageTarget[]>();
  for (const item of items) {
    const label = shorten(item.statement, 90);
    item.targets.forEach((target, index) => {
      if (target.page === null || target.page < 1) return;
      const list = pages.get(target.page) ?? [];
      list.push({ key: targetKey(item.claim_id, index), claimId: item.claim_id, target, label });
      pages.set(target.page, list);
    });
  }
  return pages;
}

/** One locator chip: targets of one evidence entry with the same anchor label, over their pages. */
export interface LocatorChip {
  label: string;
  pages: number[];
  keys: string[];
  confidence: EvidenceTarget['confidence'];
  /** Locator text as written in the review record. */
  locator: string;
  relocatedFrom: number[];
}

const CONFIDENCE_RANK: Record<EvidenceTarget['confidence'], number> = {
  quote: 4,
  anchor: 3,
  terms: 2,
  page: 1,
  unresolved: 0,
};

function pagesLabel(pages: number[]): string {
  if (pages.length === 1) return `p.${pages[0]}`;
  const consecutive = pages.every((page, index) => index === 0 || page === pages[index - 1] + 1);
  return consecutive ? `pp.${pages[0]}–${pages.at(-1)}` : `pp.${pages.join(', ')}`;
}

export function locatorChips(item: EvidenceItem): LocatorChip[] {
  const chips = new Map<string, LocatorChip>();
  item.targets.forEach((target, index) => {
    const anchorLabel = target.anchor?.label ?? '';
    const id = `${target.evidence_index}|${anchorLabel}|${target.page === null ? 'none' : 'page'}`;
    const chip = chips.get(id) ?? {
      label: anchorLabel,
      pages: [],
      keys: [],
      confidence: target.confidence,
      locator: item.evidence[target.evidence_index]?.locator ?? '',
      relocatedFrom: [],
    };
    if (target.page !== null && !chip.pages.includes(target.page)) chip.pages.push(target.page);
    chip.keys.push(targetKey(item.claim_id, index));
    if (CONFIDENCE_RANK[target.confidence] > CONFIDENCE_RANK[chip.confidence]) chip.confidence = target.confidence;
    if (target.relocated_from !== null) chip.relocatedFrom.push(target.relocated_from);
    chips.set(id, chip);
  });
  return [...chips.values()].map((chip) => {
    const pages = [...chip.pages].sort((a, b) => a - b);
    const where = pages.length > 0 ? pagesLabel(pages) : '위치 미확인';
    return { ...chip, pages, label: chip.label ? `${chip.label}, ${where}` : where };
  });
}

/** Evidence entries the server produced no target for (their locator is shown as linked text). */
export function untargetedEvidence(item: EvidenceItem): string[] {
  const covered = new Set(item.targets.map((target) => target.evidence_index));
  return item.evidence.filter((_, index) => !covered.has(index)).map((entry) => entry.locator);
}
