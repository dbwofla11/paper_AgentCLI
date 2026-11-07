/**
 * Callouts: the GitHub alert and Obsidian fold syntax shared by the review template.
 *
 *   > [!TYPE] Title     always open      → <div class="callout callout-TYPE" data-callout="TYPE">
 *   > [!TYPE]- Title    collapsed        → <details …><summary>
 *   > [!TYPE]+ Title    open, foldable   → <details open …><summary>
 *
 * TYPE is case-insensitive. The marker counts only at the start of the first text of the
 * blockquote's first paragraph; the rest of that source line is the title (inline Markdown
 * allowed), the following lines and blocks are the body. Emphasis or a link running past the line
 * end is cut there, its two halves keeping the same markup. Unknown types keep their name as a
 * label in note style, so nothing written is lost. Other blockquotes stay blockquotes.
 */

/** Known types and the label shown when the marker has no title. */
const CALLOUT_LABELS: Record<string, string> = {
  note: '참고',
  tip: '팁',
  important: '중요',
  warning: '경고',
  caution: '주의',
  abstract: '요약',
  question: '질문',
  example: '예시',
};

const MARKER = /^\[!([A-Za-z]+)\]([+-]?)[ \t]*/;

/** Minimal mdast shape the plugin touches (avoids depending on @types/mdast directly). */
interface MdNode {
  type: string;
  value?: string;
  children?: MdNode[];
  position?: { start: { line: number } };
  data?: { hName?: string; hProperties?: Record<string, unknown> };
}

function text(value: string): MdNode {
  return { type: 'text', value };
}

/** `node` with other content, or nothing when that content is empty. */
function part(node: MdNode, content: { value: string } | { children: MdNode[] }): MdNode[] {
  const empty = 'value' in content ? content.value === '' : content.children.length === 0;
  return empty ? [] : [{ ...node, ...content }];
}

/**
 * Cuts inline nodes where source line `line` ends: at a newline in text, at a hard break, or before
 * a node that starts on a later line. An inline parent (emphasis, strong, a link) the cut runs
 * through splits into two of the same kind; literals that cannot be cut (code, math, an image) stay
 * on the line they start on. Null when the nodes never leave that line.
 */
function cutAtLineEnd(nodes: MdNode[], line: number | undefined): { head: MdNode[]; tail: MdNode[] } | null {
  for (let index = 0; index < nodes.length; index += 1) {
    const node = nodes[index];
    const before = nodes.slice(0, index);
    const after = nodes.slice(index + 1);
    const start = node.position?.start.line;
    if (line !== undefined && start !== undefined && start > line) return { head: before, tail: nodes.slice(index) };
    if (node.type === 'break') return { head: before, tail: after };
    if (node.type === 'text') {
      const value = node.value ?? '';
      const lineEnd = value.indexOf('\n');
      if (lineEnd >= 0) {
        return {
          head: [...before, ...part(node, { value: value.slice(0, lineEnd) })],
          tail: [...part(node, { value: value.slice(lineEnd + 1) }), ...after],
        };
      }
    } else if (node.children) {
      const inner = cutAtLineEnd(node.children, line);
      if (inner) {
        return {
          head: [...before, ...part(node, { children: inner.head })],
          tail: [...part(node, { children: inner.tail }), ...after],
        };
      }
    }
  }
  return null;
}

/** Title inline nodes up to the end of the marker's source line; the rest of the paragraph is body. */
function splitTitle(children: MdNode[], line: number | undefined): { title: MdNode[]; rest: MdNode[] } {
  const cut = cutAtLineEnd(children, line);
  const title = cut ? cut.head : children;
  const last = title[title.length - 1];
  const trimmed = last?.type === 'text' ? [...title.slice(0, -1), ...part(last, { value: (last.value ?? '').trimEnd() })] : title;
  return { title: trimmed, rest: cut ? cut.tail : [] };
}

function toCallout(quote: MdNode): void {
  const [paragraph, ...blocks] = quote.children ?? [];
  const lead = paragraph?.type === 'paragraph' ? paragraph.children?.[0] : undefined;
  const marker = lead?.type === 'text' && lead.value ? MARKER.exec(lead.value) : null;
  if (!paragraph || !lead?.value || !marker) return;

  const type = marker[1].toLowerCase();
  const known = Object.hasOwn(CALLOUT_LABELS, type);
  const fold = marker[2];
  const inline = [{ ...lead, value: lead.value.slice(marker[0].length) }, ...(paragraph.children ?? []).slice(1)];
  const { title, rest } = splitTitle(inline, lead.position?.start.line);
  const label = known
    ? title.length > 0
      ? title
      : [text(CALLOUT_LABELS[type])]
    : [
        { type: 'calloutKind', data: { hName: 'span', hProperties: { className: ['callout-kind'] } }, children: [text(marker[1])] },
        ...(title.length > 0 ? [text(' '), ...title] : []),
      ];
  const body = rest.length > 0 ? [{ ...paragraph, children: rest }, ...blocks] : blocks;

  quote.data = {
    hName: fold ? 'details' : 'div',
    hProperties: {
      className: ['callout', `callout-${known ? type : 'note'}`],
      dataCallout: type,
      ...(fold === '+' ? { open: true } : {}),
    },
  };
  quote.children = [
    { type: 'calloutTitle', data: { hName: fold ? 'summary' : 'p', hProperties: { className: ['callout-title'] } }, children: label },
    ...(body.length > 0 ? [{ type: 'calloutBody', data: { hName: 'div', hProperties: { className: ['callout-body'] } }, children: body }] : []),
  ];
}

function visit(node: MdNode): void {
  if (node.type === 'blockquote') toCallout(node);
  node.children?.forEach(visit);
}

/** remark plugin: `> [!type]` blockquotes become callouts (see the module comment). */
export function remarkCallouts() {
  return (tree: MdNode) => {
    visit(tree);
  };
}
