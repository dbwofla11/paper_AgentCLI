import { memo, type ComponentPropsWithoutRef } from 'react';
import ReactMarkdown, { type Components, type ExtraProps, type Options } from 'react-markdown';
import rehypeKatex from 'rehype-katex';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import 'katex/dist/katex.min.css';
import { Flowchart } from './Flowchart';

type HastNode = NonNullable<ExtraProps['node']>['children'][number];

function hastText(node: HastNode): string {
  if (node.type === 'text') return node.value;
  return 'children' in node ? node.children.map(hastText).join('') : '';
}

/**
 * External links open in a new tab. Relative links and in-page anchors would fight the hash
 * router, so only their text is kept. Exported so overrides (the reader's page links) can fall back to it.
 */
export function MarkdownLink({ href, children }: ComponentPropsWithoutRef<'a'> & ExtraProps) {
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
function MarkdownImage({ alt }: ComponentPropsWithoutRef<'img'> & ExtraProps) {
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

const GFM: NonNullable<Options['remarkPlugins']> = [remarkGfm];
const GFM_MATH: NonNullable<Options['remarkPlugins']> = [remarkGfm, remarkMath, remarkDisplayMathLines];
const KATEX: NonNullable<Options['rehypePlugins']> = [rehypeKatex];

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

/** GFM Markdown without raw HTML, front matter stripped, ```mermaid flowcharts drawn by Flowchart, TeX drawn by KaTeX when `math`. */
export const Markdown = memo(function Markdown({ markdown, className, remarkPlugins, components, math = false }: MarkdownProps) {
  const base = math ? GFM_MATH : GFM;
  return (
    <div className={className ? `md ${className}` : 'md'}>
      <ReactMarkdown
        remarkPlugins={remarkPlugins ? [...base, ...remarkPlugins] : base}
        rehypePlugins={math ? KATEX : undefined}
        components={components ? { ...DEFAULT_COMPONENTS, ...components } : DEFAULT_COMPONENTS}
        skipHtml
      >
        {stripFrontMatter(markdown)}
      </ReactMarkdown>
    </div>
  );
});
