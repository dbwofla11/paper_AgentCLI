import { memo, type ComponentPropsWithoutRef } from 'react';
import ReactMarkdown, { type Components, type ExtraProps, type Options } from 'react-markdown';
import remarkGfm from 'remark-gfm';
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

const GFM: NonNullable<Options['remarkPlugins']> = [remarkGfm];

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
}

/** GFM Markdown without raw HTML, front matter stripped, ```mermaid flowcharts drawn by Flowchart. */
export const Markdown = memo(function Markdown({ markdown, className, remarkPlugins, components }: MarkdownProps) {
  return (
    <div className={className ? `md ${className}` : 'md'}>
      <ReactMarkdown
        remarkPlugins={remarkPlugins ? [...GFM, ...remarkPlugins] : GFM}
        components={components ? { ...DEFAULT_COMPONENTS, ...components } : DEFAULT_COMPONENTS}
        skipHtml
      >
        {stripFrontMatter(markdown)}
      </ReactMarkdown>
    </div>
  );
});
