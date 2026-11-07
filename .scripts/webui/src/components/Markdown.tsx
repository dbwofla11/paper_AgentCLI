import { memo, useId, useMemo, type ComponentPropsWithoutRef, type MouseEvent } from 'react';
import ReactMarkdown, { type Components, type ExtraProps, type Options } from 'react-markdown';
import rehypeKatex from 'rehype-katex';
import rehypeSlug from 'rehype-slug';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import 'katex/dist/katex.min.css';
import { remarkCallouts } from '../markdown/callouts';
import { Flowchart } from './Flowchart';

type HastNode = NonNullable<ExtraProps['node']>['children'][number];

function hastText(node: HastNode): string {
  if (node.type === 'text') return node.value;
  return 'children' in node ? node.children.map(hastText).join('') : '';
}

/**
 * Every id a Markdown block generates (headings, footnotes, the footnote label) starts with
 * `user-content-<block>-`: the GitHub prefix keeps a heading such as "Main content" clear of the
 * app's own ids, and the per-block part keeps two blocks on one page (a review and its answers)
 * from sharing ids. Authored links keep the bare slug; the block's container carries its prefix in
 * `data-id-prefix` so in-page links can resolve them.
 */
const ID_PREFIX = 'user-content-';

/** The id mdast-util-to-hast gives every footnote label, unaffected by `clobberPrefix`. */
const FOOTNOTE_LABEL_ID = 'footnote-label';

/** The element an in-page link names, looked up only inside its own Markdown block. */
function inPageTarget(container: HTMLElement, href: string): HTMLElement | null {
  const raw = href.slice(1);
  if (!raw) return null;
  let decoded = raw;
  try {
    decoded = decodeURIComponent(raw);
  } catch {
    // Malformed escapes: the raw id is the only candidate.
  }
  const prefix = container.dataset.idPrefix ?? '';
  // Generated links already carry the block's prefix; authored ones use the bare slug or GitHub's
  // `user-content-` form of it.
  const bare = decoded.startsWith(ID_PREFIX) ? decoded.slice(ID_PREFIX.length) : decoded;
  for (const id of [raw, decoded, prefix + decoded, prefix + bare]) {
    const target = container.querySelector<HTMLElement>(`[id="${CSS.escape(id)}"]`);
    if (target) return target;
  }
  return null;
}

/**
 * Opens every folded callout (closed `<details>`) that hides the target, outermost included. A
 * closed details still shows its summary, so a target inside that summary leaves it closed.
 */
function revealTarget(target: HTMLElement, container: HTMLElement) {
  for (let node = target.parentElement; node && node !== container; node = node.parentElement) {
    if (!(node instanceof HTMLDetailsElement) || node.open) continue;
    const summary = Array.from(node.children).find((child) => child.tagName === 'SUMMARY');
    if (!summary?.contains(target)) node.open = true;
  }
}

/**
 * Section and footnote links scroll inside their Markdown block instead of changing the URL hash,
 * which the hash router owns. Folded callouts around the target open first; focus follows, as with
 * native fragment navigation.
 */
function followInPageLink(event: MouseEvent<HTMLAnchorElement>) {
  event.preventDefault();
  const container = event.currentTarget.closest<HTMLElement>('.md');
  const target = container ? inPageTarget(container, event.currentTarget.getAttribute('href') ?? '') : null;
  if (!container || !target) return;
  revealTarget(target, container);
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  target.scrollIntoView({ block: /^H[1-6]$/.test(target.tagName) ? 'start' : 'center', behavior: reduced ? 'auto' : 'smooth' });
  if (target.tabIndex < 0 && !target.hasAttribute('tabindex')) target.setAttribute('tabindex', '-1');
  target.focus({ preventScroll: true });
}

/**
 * External links open in a new tab; `#` links (sections, footnotes) scroll within the document.
 * Other relative links would fight the hash router, so only their text is kept. Exported so
 * overrides (the reader's page links) can fall back to it.
 */
export function MarkdownLink({ node, href, children, ...rest }: ComponentPropsWithoutRef<'a'> & ExtraProps) {
  if (href?.startsWith('#')) {
    return (
      <a {...rest} href={href} onClick={followInPageLink}>
        {children}
      </a>
    );
  }
  if (href && /^(https?:|mailto:)/i.test(href)) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    );
  }
  return <span className="md-link-text">{children}</span>;
}

function MarkdownTable({ children }: ComponentPropsWithoutRef<'table'> & ExtraProps) {
  return (
    <div className="md-table" tabIndex={0} role="region" aria-label="표 (가로로 스크롤)">
      <table>{children}</table>
    </div>
  );
}

/** Images would load from arbitrary paths (and remote ones are blocked by the CSP): show the alt text. */
export function MarkdownImage({ alt }: ComponentPropsWithoutRef<'img'> & ExtraProps) {
  return alt ? <span className="md-image-alt">[그림: {alt}]</span> : null;
}

/** ```mermaid fences render as a Flowchart; other code blocks stay preformatted. */
function MarkdownPre({ node, children, ...rest }: ComponentPropsWithoutRef<'pre'> & ExtraProps) {
  const code = node?.children[0];
  if (code?.type === 'element' && code.tagName === 'code') {
    const classes = code.properties.className;
    if (Array.isArray(classes) && classes.includes('language-mermaid')) return <Flowchart source={hastText(code).trimEnd()} />;
  }
  return <pre {...rest}>{children}</pre>;
}

const DEFAULT_COMPONENTS: Components = {
  a: MarkdownLink,
  table: MarkdownTable,
  img: MarkdownImage,
  pre: MarkdownPre,
};

/** Minimal mdast shape the math plugin touches (avoids depending on @types/mdast directly). */
interface MdNode {
  type: string;
  value?: string;
  children?: MdNode[];
  position?: { start: { offset?: number }; end: { offset?: number } };
  data?: { hProperties?: { className?: string[] } };
}

/** Text math with nothing but spaces or tabs between it and the line breaks around it. */
function ownsLine(source: string, node: MdNode): boolean {
  const start = node.position?.start.offset;
  const end = node.position?.end.offset;
  if (start === undefined || end === undefined) return false;
  const lineEnd = source.indexOf('\n', end);
  const before = source.slice(source.lastIndexOf('\n', start - 1) + 1, start);
  const after = source.slice(end, lineEnd < 0 ? source.length : lineEnd);
  return /^[ \t]*$/.test(before) && /^[ \t]*\r?$/.test(after);
}

/** Drops the line break and spaces a split leaves at the edges of a paragraph's inline run. */
function trimRun(run: MdNode[]): MdNode[] {
  const first = run[0];
  if (first?.type === 'text' && first.value !== undefined) first.value = first.value.trimStart();
  const last = run[run.length - 1];
  if (last?.type === 'text' && last.value !== undefined) last.value = last.value.trimEnd();
  return run.filter((node, index) => {
    if (node.type === 'text') return node.value !== '';
    return node.type !== 'break' || (index !== 0 && index !== run.length - 1);
  });
}

/**
 * remark-math parses `$$…$$` as text math unless both fences sit on their own lines, so a one-line
 * `$$…$$` would render inline. When it fills its source line (or its whole paragraph), this splits
 * the paragraph around it and marks it `math-display`, which rehype-katex renders in display mode.
 * `$…$` and `$$…$$` inside a sentence stay inline.
 */
function remarkDisplayMathLines() {
  return (tree: MdNode, file: { value: unknown }) => {
    const source = String(file.value);
    const split = (paragraph: MdNode): MdNode[] => {
      const children = paragraph.children ?? [];
      const out: MdNode[] = [];
      let run: MdNode[] = [];
      const flush = () => {
        const kept = trimRun(run);
        if (kept.length) out.push({ ...paragraph, children: kept });
        run = [];
      };
      for (const child of children) {
        const display =
          child.type === 'inlineMath' &&
          child.data?.hProperties &&
          source.startsWith('$$', child.position?.start.offset ?? -1) &&
          (children.length === 1 || ownsLine(source, child));
        if (!display || !child.data?.hProperties) {
          run.push(child);
          continue;
        }
        flush();
        child.data.hProperties.className = ['language-math', 'math-display'];
        out.push(child);
      }
      if (out.length === 0) return [paragraph];
      flush();
      return out;
    };
    const visit = (node: MdNode): void => {
      if (!node.children) return;
      node.children = node.children.flatMap((child) => {
        if (child.type === 'paragraph') return split(child);
        visit(child);
        return [child];
      });
    };
    visit(tree);
  };
}

const GFM: NonNullable<Options['remarkPlugins']> = [remarkGfm, remarkCallouts];
const GFM_MATH: NonNullable<Options['remarkPlugins']> = [remarkGfm, remarkCallouts, remarkMath, remarkDisplayMathLines];

/** Minimal hast shape the footnote-label plugin touches. */
interface HNode {
  type: string;
  properties?: Record<string, unknown>;
  children?: HNode[];
}

/**
 * mdast-util-to-hast names every footnote label `footnote-label` whatever the `clobberPrefix`, and
 * points each footnote reference's `aria-describedby` at it: this renames both to `id`.
 */
function rehypeFootnoteLabelId({ id }: { id: string }) {
  const rename = (node: HNode): void => {
    const properties = node.properties;
    if (properties) {
      if (properties.id === FOOTNOTE_LABEL_ID) properties.id = id;
      const describedBy = properties.ariaDescribedBy;
      if (Array.isArray(describedBy)) properties.ariaDescribedBy = describedBy.map((ref: unknown) => (ref === FOOTNOTE_LABEL_ID ? id : ref));
    }
    node.children?.forEach(rename);
  };
  return (tree: HNode) => {
    rename(tree);
  };
}

/** Footnotes end the document under a visible Korean label; back links say where they return to. */
const REMARK_REHYPE: NonNullable<Options['remarkRehypeOptions']> = {
  footnoteLabel: '각주',
  footnoteLabelTagName: 'p',
  footnoteLabelProperties: { className: ['md-footnotes-label'] },
  footnoteBackLabel: (referenceIndex, rereferenceIndex) =>
    `각주 ${referenceIndex + 1}${rereferenceIndex > 1 ? `-${rereferenceIndex}` : ''} 참조 위치로 돌아가기`,
};

/** Drops a leading YAML front matter block (`---` … `---`), which plain Markdown would render as a heading. */
export function stripFrontMatter(markdown: string): string {
  const match = /^---\r?\n[\s\S]*?\r?\n---[ \t]*(?:\r?\n|$)/.exec(markdown);
  return match ? markdown.slice(match[0].length) : markdown;
}

export interface MarkdownProps {
  markdown: string;
  /** Added to `md` on the wrapper. */
  className?: string;
  /**
   * Remark plugins applied after GFM, e.g. the reader's page-reference plugin. Pass a module-level
   * constant: a new array on every render re-parses the document.
   */
  remarkPlugins?: NonNullable<Options['remarkPlugins']>;
  /** Element overrides merged over the defaults (a, table, img, pre). Also a module-level constant. */
  components?: Components;
  /**
   * Draws `$…$` (inline) and `$$…$$` (display) TeX with KaTeX. Only for text written with TeX in
   * mind (reviews, answers): a literal dollar must then be escaped as `\$`.
   */
  math?: boolean;
}

/**
 * GFM Markdown without raw HTML: front matter stripped, `> [!type]` callouts, heading ids for `#`
 * links, footnotes, ```mermaid flowcharts drawn by Flowchart, TeX drawn by KaTeX when `math`.
 */
export const Markdown = memo(function Markdown({ markdown, className, remarkPlugins, components, math = false }: MarkdownProps) {
  const base = math ? GFM_MATH : GFM;
  const block = useId().replace(/[^A-Za-z0-9]/g, '');
  const idPrefix = `${ID_PREFIX}${block}-`;
  const rehypePlugins = useMemo<NonNullable<Options['rehypePlugins']>>(() => {
    const ids: NonNullable<Options['rehypePlugins']> = [
      [rehypeSlug, { prefix: idPrefix }],
      [rehypeFootnoteLabelId, { id: idPrefix + FOOTNOTE_LABEL_ID }],
    ];
    return math ? [...ids, rehypeKatex] : ids;
  }, [idPrefix, math]);
  const remarkRehypeOptions = useMemo(() => ({ ...REMARK_REHYPE, clobberPrefix: idPrefix }), [idPrefix]);
  return (
    <div className={className ? `md ${className}` : 'md'} data-id-prefix={idPrefix}>
      <ReactMarkdown
        remarkPlugins={remarkPlugins ? [...base, ...remarkPlugins] : base}
        rehypePlugins={rehypePlugins}
        remarkRehypeOptions={remarkRehypeOptions}
        components={components ? { ...DEFAULT_COMPONENTS, ...components } : DEFAULT_COMPONENTS}
        skipHtml
      >
        {stripFrontMatter(markdown)}
      </ReactMarkdown>
    </div>
  );
});
