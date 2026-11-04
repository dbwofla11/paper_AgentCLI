/**
 * `p.N`, `pp.N–M`, `pp.2–3, 9–11` page references in review, verification, and answer text.
 * Page numbers are PDF page order (reader design F3), so each reference can scroll the PDF.
 */

export type TextPiece = string | { text: string; page: number };

/** `p.` / `pp.` then a first number or range. */
const REF_START = /\b(pp?)\.\s?(\d{1,4})(?:\s*[-–—]\s*\d{1,4})?/g;
/** A further `, N` or `, N–M` of the same list; not a model size like `, 7B` or a decimal. */
const REF_MORE = /^(\s*,\s*)(\d{1,4})(?:\s*[-–—]\s*\d{1,4})?(?![A-Za-z\d.])/;

/** Splits text into plain strings and page references (each linking to its first page). */
export function splitPageRefs(text: string): TextPiece[] {
  const pieces: TextPiece[] = [];
  let cursor = 0;
  REF_START.lastIndex = 0;
  for (let match = REF_START.exec(text); match; match = REF_START.exec(text)) {
    if (match.index > cursor) pieces.push(text.slice(cursor, match.index));
    pieces.push({ text: match[0], page: Number(match[2]) });
    cursor = match.index + match[0].length;
    if (match[1] === 'pp') {
      for (let more = REF_MORE.exec(text.slice(cursor)); more; more = REF_MORE.exec(text.slice(cursor))) {
        pieces.push(more[1]);
        pieces.push({ text: more[0].slice(more[1].length), page: Number(more[2]) });
        cursor += more[0].length;
      }
    }
    REF_START.lastIndex = cursor;
  }
  if (cursor < text.length) pieces.push(text.slice(cursor));
  return pieces;
}

/** Link URL the remark plugin gives page references; the Markdown `a` renderer turns it into a button. */
export const PAGE_LINK_PREFIX = '#pdf-page-';

export function pageFromLink(href: string | undefined): number | null {
  if (!href?.startsWith(PAGE_LINK_PREFIX)) return null;
  const page = Number(href.slice(PAGE_LINK_PREFIX.length));
  return Number.isInteger(page) && page > 0 ? page : null;
}

/** Minimal mdast shape the plugin touches (avoids depending on @types/mdast directly). */
interface MdNode {
  type: string;
  value?: string;
  url?: string;
  children?: MdNode[];
}

/** Nodes whose text must stay literal. */
const LITERAL_PARENTS: Record<string, true> = {
  link: true,
  linkReference: true,
  inlineCode: true,
  code: true,
  definition: true,
  html: true,
};

function linkPages(node: MdNode): void {
  if (!node.children || LITERAL_PARENTS[node.type]) return;
  const next: MdNode[] = [];
  for (const child of node.children) {
    if (child.type !== 'text' || !child.value) {
      linkPages(child);
      next.push(child);
      continue;
    }
    for (const piece of splitPageRefs(child.value)) {
      if (typeof piece === 'string') next.push({ type: 'text', value: piece });
      else next.push({ type: 'link', url: `${PAGE_LINK_PREFIX}${piece.page}`, children: [{ type: 'text', value: piece.text }] });
    }
  }
  node.children = next;
}

/** remark plugin: page references become links to `#pdf-page-N`. */
export function remarkPageRefs() {
  return (tree: MdNode) => {
    linkPages(tree);
  };
}
