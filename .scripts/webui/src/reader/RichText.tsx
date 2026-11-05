import { memo, type ComponentPropsWithoutRef, type ReactNode } from 'react';
import type { Components, ExtraProps } from 'react-markdown';
import { Markdown, MarkdownLink } from '../components/Markdown';
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

const READER_COMPONENTS: Components = { a: ReaderLink };
const READER_PLUGINS = [remarkPageRefs];

/** Review or answer Markdown: the shared Markdown (GFM, flowcharts, TeX) with page references linked to the PDF. */
export const ReaderMarkdown = memo(function ReaderMarkdown({ markdown, className }: { markdown: string; className?: string }) {
  return <Markdown markdown={markdown} className={className} remarkPlugins={READER_PLUGINS} components={READER_COMPONENTS} math />;
});
