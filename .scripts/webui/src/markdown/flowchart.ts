/**
 * Minimal Mermaid `flowchart` reader for the review "방법 구조도" blocks. It extracts nodes, their
 * labels and edges; everything else (subgraph, style, classDef, click, …) is ignored. Text is
 * returned as plain strings and rendered through React, never as HTML.
 */

export type FlowEdgeStyle = 'arrow' | 'line' | 'thick' | 'dotted';

export interface FlowNode {
  id: string;
  /** Lines separated by `\n` (`<br/>` in the source). */
  label: string;
}

export interface FlowEdge {
  from: string;
  to: string;
  label: string | null;
  style: FlowEdgeStyle;
}

export interface Flowchart {
  direction: string;
  nodes: FlowNode[];
  edges: FlowEdge[];
}

/** One node in reading order. `next` links to the following step; other edges are `branches`. */
export interface FlowStep {
  node: FlowNode;
  next: FlowEdge | null;
  branches: { edge: FlowEdge; target: number }[];
}

const HEADER = /^(?:flowchart|graph)\s+(LR|RL|TB|TD|BT)\b\s*;?\s*(.*)$/i;
const IGNORED = /^(?:subgraph|end|style|classDef|class|click|linkStyle|direction)\b/;
const ID = /[\p{L}\p{N}_]+/uy;
const CLASS_SUFFIX = /:::[\w-]+/y;
/** Edge without inline text: `-->`, `---`, `==>`, `===`, `-.->`, `-.-`, `~~~`, `--o`, `--x` (longer runs too). */
const EDGE_PLAIN = /<?(?:-{2,}>|-{3,}|={2,}>|={3,}|-\.+->|-\.+-|~{3,}|--[ox]|==[ox])/y;
/** Edge with text between its halves: `-- text -->`, `== text ==>`, `-. text .->`. */
const EDGE_TEXT = /<?(?:--|==|-\.)\s*(?:"([^"]*)"|([^"]+?))\s*(?:-{2,}>|-{3,}|={2,}>|={3,}|\.+->|\.+-)/y;
const PIPE_LABEL = /\s*\|\s*(?:"([^"]*)"|([^|]*))\|/y;

/** Node shape delimiters, longest opener first; trapezoids accept either slash closer. */
const SHAPES: readonly (readonly [string, readonly string[]])[] = [
  ['(((', [')))']],
  ['((', ['))']],
  ['([', ['])']],
  ['[[', [']]']],
  ['[(', [')]']],
  ['{{', ['}}']],
  ['[/', ['/]', '\\]']],
  ['[\\', ['\\]', '/]']],
  ['[', [']']],
  ['(', [')']],
  ['{', ['}']],
  ['>', [']']],
];

const ENTITIES: Record<string, string> = { quot: '"', amp: '&', lt: '<', gt: '>', nbsp: ' ' };

interface Cursor {
  text: string;
  pos: number;
}

function skipSpace(cursor: Cursor): void {
  while (cursor.pos < cursor.text.length && /\s/.test(cursor.text[cursor.pos])) cursor.pos += 1;
}

function matchSticky(pattern: RegExp, cursor: Cursor): RegExpExecArray | null {
  pattern.lastIndex = cursor.pos;
  const match = pattern.exec(cursor.text);
  if (match) cursor.pos += match[0].length;
  return match;
}

/** `<br/>` → line break, Mermaid `#name;`/`#123;` entities, other tags and markdown-string backticks dropped. */
function cleanText(raw: string): string {
  return raw
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/#(\d+);/g, (whole, code: string) => {
      const value = Number(code);
      return value > 0 && value <= 0x10ffff ? String.fromCodePoint(value) : whole;
    })
    .replace(/#(quot|amp|lt|gt|nbsp);/g, (_whole, name: string) => ENTITIES[name])
    .replace(/<\/?[a-z][^>]*>/gi, '')
    .split('\n')
    .map((line) => line.trim().replace(/^`|`$/g, ''))
    .filter(Boolean)
    .join('\n');
}

/** Reads one shape label after a node id, or returns null (cursor unchanged) when none closes. */
function readShape(cursor: Cursor): string | null {
  const { text } = cursor;
  for (const [opener, closers] of SHAPES) {
    if (!text.startsWith(opener, cursor.pos)) continue;
    let pos = cursor.pos + opener.length;
    let label: string;
    if (text[pos] === '"') {
      const end = text.indexOf('"', pos + 1);
      if (end < 0) continue;
      label = text.slice(pos + 1, end);
      pos = end + 1;
      while (pos < text.length && /\s/.test(text[pos])) pos += 1;
      const closer = closers.find((candidate) => text.startsWith(candidate, pos));
      if (!closer) continue;
      pos += closer.length;
    } else {
      const ends = closers.map((candidate) => [text.indexOf(candidate, pos), candidate.length] as const).filter(([at]) => at >= 0);
      if (ends.length === 0) continue;
      const [at, length] = ends.reduce((first, other) => (other[0] < first[0] ? other : first));
      label = text.slice(pos, at);
      pos = at + length;
    }
    cursor.pos = pos;
    return label;
  }
  return null;
}

function edgeStyle(token: string): FlowEdgeStyle {
  if (token.includes('=')) return 'thick';
  if (token.includes('.')) return 'dotted';
  return token.includes('>') ? 'arrow' : 'line';
}

interface Builder {
  nodes: Map<string, FlowNode>;
  edges: FlowEdge[];
}

function readNode(cursor: Cursor, builder: Builder): string | null {
  const id = matchSticky(ID, cursor)?.[0];
  if (!id) return null;
  const label = readShape(cursor);
  matchSticky(CLASS_SUFFIX, cursor);
  const existing = builder.nodes.get(id);
  const cleaned = label === null ? null : cleanText(label);
  if (!existing) builder.nodes.set(id, { id, label: cleaned || id });
  else if (cleaned) existing.label = cleaned;
  return id;
}

/** `A`, or `A & B & C`. */
function readNodeGroup(cursor: Cursor, builder: Builder): string[] | null {
  const first = readNode(cursor, builder);
  if (!first) return null;
  const ids = [first];
  for (;;) {
    const save = cursor.pos;
    skipSpace(cursor);
    if (cursor.text[cursor.pos] !== '&') {
      cursor.pos = save;
      return ids;
    }
    cursor.pos += 1;
    skipSpace(cursor);
    const next = readNode(cursor, builder);
    if (!next) return ids;
    ids.push(next);
  }
}

function readEdge(cursor: Cursor): { label: string | null; style: FlowEdgeStyle } | null {
  const plain = matchSticky(EDGE_PLAIN, cursor);
  if (plain) {
    const piped = matchSticky(PIPE_LABEL, cursor);
    const raw = piped ? (piped[1] ?? piped[2]) : null;
    return { label: raw ? cleanText(raw) || null : null, style: edgeStyle(plain[0]) };
  }
  const texted = matchSticky(EDGE_TEXT, cursor);
  if (!texted) return null;
  const raw = texted[1] ?? texted[2] ?? '';
  return { label: cleanText(raw) || null, style: edgeStyle(texted[0]) };
}

/** One statement: `group (edge group)*`. A malformed tail is skipped; what parsed before it stays. */
function readStatement(text: string, builder: Builder): void {
  const cursor: Cursor = { text, pos: 0 };
  skipSpace(cursor);
  let left = readNodeGroup(cursor, builder);
  while (left) {
    skipSpace(cursor);
    if (cursor.pos >= text.length) return;
    const edge = readEdge(cursor);
    if (!edge) return;
    skipSpace(cursor);
    const right = readNodeGroup(cursor, builder);
    if (!right) return;
    for (const from of left) for (const to of right) builder.edges.push({ from, to, ...edge });
    left = right;
  }
}

/** Null when the block is not a `flowchart`/`graph` or declares no node. */
export function parseFlowchart(source: string): Flowchart | null {
  const lines = source
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('%%'));
  const header = lines.length > 0 ? HEADER.exec(lines[0]) : null;
  if (!header) return null;
  const builder: Builder = { nodes: new Map(), edges: [] };
  const statements = header[2] ? [header[2], ...lines.slice(1)] : lines.slice(1);
  for (const statement of statements) {
    if (IGNORED.test(statement)) continue;
    readStatement(statement.replace(/;\s*$/, ''), builder);
  }
  if (builder.nodes.size === 0) return null;
  return { direction: header[1].toUpperCase(), nodes: [...builder.nodes.values()], edges: builder.edges };
}

/**
 * Reading order: topological (Kahn) with first appearance breaking ties; a cycle is entered at
 * its earliest-declared node. Each step's edge to the following step becomes `next`.
 */
export function orderFlowchart(chart: Flowchart): FlowStep[] {
  const declared = new Map(chart.nodes.map((node, index) => [node.id, index]));
  const indegree = new Map(chart.nodes.map((node) => [node.id, 0]));
  const outgoing = new Map<string, FlowEdge[]>(chart.nodes.map((node) => [node.id, []]));
  for (const edge of chart.edges) {
    outgoing.get(edge.from)?.push(edge);
    if (edge.from !== edge.to) indegree.set(edge.to, (indegree.get(edge.to) ?? 0) + 1);
  }

  const order: FlowNode[] = [];
  const placed = new Set<string>();
  const ready = chart.nodes.filter((node) => indegree.get(node.id) === 0);
  while (order.length < chart.nodes.length) {
    ready.sort((a, b) => (declared.get(a.id) ?? 0) - (declared.get(b.id) ?? 0));
    const node = ready.shift() ?? chart.nodes.find((candidate) => !placed.has(candidate.id));
    if (!node) break;
    if (placed.has(node.id)) continue;
    placed.add(node.id);
    order.push(node);
    for (const edge of outgoing.get(node.id) ?? []) {
      if (placed.has(edge.to)) continue;
      const remaining = (indegree.get(edge.to) ?? 1) - 1;
      indegree.set(edge.to, remaining);
      const target = chart.nodes[declared.get(edge.to) ?? -1];
      if (remaining === 0 && target) ready.push(target);
    }
  }

  const position = new Map(order.map((node, index) => [node.id, index]));
  return order.map((node, index) => {
    const following = order[index + 1]?.id;
    const edges = outgoing.get(node.id) ?? [];
    const next = following ? (edges.find((edge) => edge.to === following) ?? null) : null;
    const branches = edges
      .filter((edge) => edge !== next)
      .map((edge) => ({ edge, target: position.get(edge.to) ?? index }));
    return { node, next, branches };
  });
}
