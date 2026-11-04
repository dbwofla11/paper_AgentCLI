import type { EvidenceTarget, PageRect } from '../api/types';
import { clientRectsToPage } from './geometry';

/**
 * Client half of the highlight grammar (reader design §3.6 step 8). The server owns matching rules
 * and sends JS regex sources (`anchor.pattern`) and normalized plain needles (`terms`, `quotes`);
 * this module only finds them in the pdf.js text layer and turns hits into page-fraction rects.
 */

interface SourcePosition {
  node: Text;
  offset: number;
  /** UTF-16 length of the source code point (2 for astral characters). */
  length: number;
}

/** Normalized page text with a map from each normalized UTF-16 code unit back to its text-layer position. */
export interface PageTextIndex {
  text: string;
  /**
   * One entry per UTF-16 code unit of `text`, so `RegExp.exec` indices address it directly (an
   * astral character such as 𝑥 that survives NFKC takes two entries). null = synthetic separator
   * (a line break between text-layer runs).
   */
  map: (SourcePosition | null)[];
}

const WHITESPACE = /\s/;
const LETTER = /\p{L}/u;

/**
 * NFKC, lowercase, `-` + line break rejoined, spaces collapsed to one, line breaks kept as one `\n`
 * so line-start patterns (`(?:^|\s)…` with the `m` flag) still work.
 */
export function buildTextIndex(textLayer: HTMLElement): PageTextIndex {
  const chars: string[] = [];
  const map: (SourcePosition | null)[] = [];
  const last = () => chars.at(-1);

  const lineBreak = () => {
    const end = last();
    if (end === undefined || end === '\n') return;
    // "infor-\nmation" → "information" (only after a letter, so "-1" or "3-" stay).
    if (end === '-' && chars.length > 1 && LETTER.test(chars[chars.length - 2])) {
      chars.pop();
      map.pop();
      return;
    }
    if (end === ' ') {
      chars[chars.length - 1] = '\n';
      map[map.length - 1] = null;
      return;
    }
    chars.push('\n');
    map.push(null);
  };

  const walker = document.createTreeWalker(textLayer, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    if (node.nodeType === Node.ELEMENT_NODE) {
      if ((node as Element).tagName === 'BR') lineBreak();
      continue;
    }
    const text = node as Text;
    let offset = 0;
    for (const raw of text.data) {
      const position: SourcePosition = { node: text, offset, length: raw.length };
      offset += raw.length;
      for (const char of raw.normalize('NFKC').toLowerCase()) {
        let out = char;
        if (WHITESPACE.test(char)) {
          const end = last();
          if (end === undefined || end === ' ' || end === '\n') continue;
          out = ' ';
        }
        chars.push(out);
        // The tail edits in lineBreak() only touch one-unit characters (' ', '-', '\n').
        for (let unit = 0; unit < out.length; unit += 1) map.push(position);
      }
    }
  }
  return { text: chars.join(''), map };
}

/** Escapes RegExp syntax characters only (valid with the `u` flag, unlike escaping `-`). */
function escapeRegExp(value: string): string {
  return value.replace(/[\\^$.*+?()[\]{}|/]/g, '\\$&');
}

const EDGE = /[\p{L}\p{N}]/u;

/** Plain needle → regex: spaces match any whitespace, letter/digit edges need a boundary. */
function needleRegExp(needle: string): RegExp | null {
  const value = needle.normalize('NFKC').toLowerCase().replace(/\s+/g, ' ').trim();
  if (!value) return null;
  // The server writes `1,000` as `1000`; the PDF keeps the separators.
  const body = /^\d{4,}$/.test(value)
    ? value.replace(/\B(?=(\d{3})+$)/g, ',?')
    : escapeRegExp(value).replace(/ /g, '\\s+');
  const before = EDGE.test(value[0]) ? '(?<![\\p{L}\\p{N}])' : '';
  const after = EDGE.test(value.at(-1) ?? '') ? '(?![\\p{L}\\p{N}])' : '';
  try {
    return new RegExp(`${before}${body}${after}`, 'gu');
  } catch {
    return null;
  }
}

function patternRegExp(pattern: string): RegExp | null {
  try {
    return new RegExp(pattern, 'gim');
  } catch {
    return null;
  }
}

interface Hit {
  start: number;
  end: number;
}

function findAll(regex: RegExp, text: string, limit: number): Hit[] {
  const hits: Hit[] = [];
  regex.lastIndex = 0;
  for (let match = regex.exec(text); match && hits.length < limit; match = regex.exec(text)) {
    if (match[0].length === 0) {
      regex.lastIndex += 1;
      continue;
    }
    // `(?:^|\s)` patterns include the leading separator; skip it so the box starts at the word.
    const lead = match[0].length - match[0].trimStart().length;
    hits.push({ start: match.index + lead, end: match.index + match[0].trimEnd().length });
  }
  return hits;
}

/** Caption hits ("Table 3:" / "Figure 4.") are preferred over in-text mentions. */
const CAPTION_KINDS: Record<string, true> = { table: true, figure: true };
const QUOTE_HIT_LIMIT = 4;
/** Numbers are drawn wherever they occur on the page (bounded only against pathological pages). */
const NUMBER_HIT_LIMIT = 16;
/** Word and identifier terms (model names, datasets) recur on every page: at most this many each. */
const WORD_HIT_LIMIT = 2;
const TARGET_HIT_LIMIT = 48;

/**
 * Measured values (`87.9`, `0.38`, `1000`). Years (`2026`) appear in every citation, so they count
 * as word terms rather than values.
 */
function isNumericTerm(term: string): boolean {
  return /^\d+(?:[.,]\d+)*$/.test(term) && !/^(?:19|20)\d{2}$/.test(term);
}

export type HighlightStrength = 'strong' | 'term';

export interface HighlightBox {
  rect: PageRect;
  strength: HighlightStrength;
}

/**
 * Drawing rule per target on its page: every quote match, the first anchor match (a caption when
 * there is one), every numeric term match; word/identifier terms only when neither a quote nor the
 * anchor matched, and then only their first 2 occurrences.
 */
function targetHits(index: PageTextIndex, target: EvidenceTarget): { hit: Hit; strength: HighlightStrength }[] {
  const found: { hit: Hit; strength: HighlightStrength }[] = [];
  for (const quote of target.quotes) {
    const regex = needleRegExp(quote);
    if (regex) for (const hit of findAll(regex, index.text, QUOTE_HIT_LIMIT)) found.push({ hit, strength: 'strong' });
  }
  if (target.anchor) {
    const regex = patternRegExp(target.anchor.pattern);
    if (regex) {
      const hits = findAll(regex, index.text, 50);
      const caption = CAPTION_KINDS[target.anchor.kind]
        ? hits.find((hit) => /^\s*[:.]/.test(index.text.slice(hit.end, hit.end + 3)))
        : undefined;
      const first = caption ?? hits[0];
      if (first) found.push({ hit: first, strength: 'strong' });
    }
  }
  const located = found.length > 0;
  for (const term of target.terms) {
    const numeric = isNumericTerm(term);
    if (!numeric && located) continue;
    const regex = needleRegExp(term);
    if (!regex) continue;
    for (const hit of findAll(regex, index.text, numeric ? NUMBER_HIT_LIMIT : WORD_HIT_LIMIT)) {
      found.push({ hit, strength: 'term' });
    }
  }
  return found.slice(0, TARGET_HIT_LIMIT);
}

function hitRange(index: PageTextIndex, { start, end }: Hit): Range | null {
  let first = start;
  while (first < end && !index.map[first]) first += 1;
  let lastIndex = end - 1;
  while (lastIndex >= first && !index.map[lastIndex]) lastIndex -= 1;
  const from = index.map[first];
  const to = index.map[lastIndex];
  if (!from || !to || first > lastIndex) return null;
  const range = document.createRange();
  try {
    range.setStart(from.node, from.offset);
    range.setEnd(to.node, to.offset + to.length);
  } catch {
    return null;
  }
  return range;
}

/**
 * Page-fraction boxes for one target, or an empty list when none of its needles is in the text
 * layer (the caller then shows a page-margin marker instead).
 */
export function locateTarget(index: PageTextIndex, target: EvidenceTarget, pageBox: DOMRectReadOnly): HighlightBox[] {
  const boxes: HighlightBox[] = [];
  for (const { hit, strength } of targetHits(index, target)) {
    const range = hitRange(index, hit);
    if (!range) continue;
    for (const rect of clientRectsToPage(range.getClientRects(), pageBox)) boxes.push({ rect, strength });
  }
  return boxes;
}
