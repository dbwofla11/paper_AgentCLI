import { memo, useState, type ComponentPropsWithoutRef, type HTMLAttributes, type ReactNode } from 'react';
import type { Components, ExtraProps } from 'react-markdown';
import { Markdown, MarkdownImage, MarkdownLink } from '../components/Markdown';
import { useReader } from './context';
import { pageFromLink, remarkPageRefs, splitPageRefs } from './pageRefs';

/** Scrolls the PDF to a page; disabled when the PDF has fewer pages (or is not loaded). */
export function PageLink({ page, children }: { page: number; children: ReactNode }) {
  const { pageCount, goToPage } = useReader();
  const available = page >= 1 && page <= pageCount;
  return (
    <button
      type="button"
      className="page-link"
      disabled={!available}
      title={available ? `PDF ${page}쪽으로 이동` : pageCount > 0 ? `PDF에 ${page}쪽이 없습니다 (전체 ${pageCount}쪽)` : 'PDF를 열면 이동할 수 있습니다'}
      onClick={() => goToPage(page)}
    >
      {children}
    </button>
  );
}

/** Plain text with `p.N` references as page links. */
export function LinkedText({ text }: { text: string }) {
  return (
    <>
      {splitPageRefs(text).map((piece, index) =>
        typeof piece === 'string' ? (
          piece
        ) : (
          <PageLink key={index} page={piece.page}>
            {piece.text}
          </PageLink>
        ),
      )}
    </>
  );
}

/** `p.N` links (from remarkPageRefs) scroll the PDF; other links behave like the shared Markdown's. */
function ReaderLink(props: ComponentPropsWithoutRef<'a'> & ExtraProps) {
  const page = pageFromLink(props.href);
  if (page !== null) return <PageLink page={page}>{props.children}</PageLink>;
  return <MarkdownLink {...props} />;
}

/**
 * The review's own figures (`figures/{slug}-….svg`) load through the figure API; any other image,
 * an unknown path, or one that fails to load keeps the shared alt-text fallback.
 */
function ReaderImage({ src, alt }: ComponentPropsWithoutRef<'img'> & ExtraProps) {
  const { figureUrl } = useReader();
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const url = typeof src === 'string' ? figureUrl(src) : null;
  if (url === null || failedUrl === url) return <MarkdownImage alt={alt} />;
  return (
    <figure className="md-figure">
      <div className="md-figure-scroll" tabIndex={0} role="region" aria-label="그림 (가로로 스크롤)">
        <img src={url} alt={alt ?? ''} loading="lazy" decoding="async" onError={() => setFailedUrl(url)} />
      </div>
      {alt ? <figcaption>{alt}</figcaption> : null}
    </figure>
  );
}

/**
 * A paragraph holding an image becomes a block `div`: a `<figure>` may not sit inside `<p>`. Every
 * other attribute (the footnote label's `id`, `aria-*`, `data-*`) passes through; Markdown props
 * carry no handlers, so one `HTMLElement` attribute type serves both tags.
 */
function ReaderParagraph({ node, className, children, ...rest }: HTMLAttributes<HTMLElement> & ExtraProps) {
  const holdsImage = node?.children.some((child) => child.type === 'element' && child.tagName === 'img');
  if (!holdsImage) {
    return (
      <p {...rest} className={className}>
        {children}
      </p>
    );
  }
  return (
    <div {...rest} className={className ? `md-figure-block ${className}` : 'md-figure-block'}>
      {children}
    </div>
  );
}

const READER_COMPONENTS: Components = { a: ReaderLink, img: ReaderImage, p: ReaderParagraph };
const READER_PLUGINS = [remarkPageRefs];

/** Review or answer Markdown: the shared Markdown (GFM, callouts, flowcharts, TeX) with page references linked to the PDF and the review's figures shown. */
export const ReaderMarkdown = memo(function ReaderMarkdown({ markdown, className }: { markdown: string; className?: string }) {
  return <Markdown markdown={markdown} className={className} remarkPlugins={READER_PLUGINS} components={READER_COMPONENTS} math />;
});
