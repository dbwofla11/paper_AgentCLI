import { InvalidPDFException, PasswordException, ResponseException, type PDFDocumentProxy } from 'pdfjs-dist';
import { useEffect, useState } from 'react';
import { openPdf } from './pdf';

export interface PdfDocumentState {
  doc: PDFDocumentProxy | null;
  error: string | null;
  /** Downloaded fraction 0–1 while loading; null when the size is unknown. */
  progress: number | null;
}

function loadError(error: unknown): string {
  if (error instanceof PasswordException) return '암호가 걸린 PDF는 열 수 없습니다.';
  if (error instanceof InvalidPDFException) return 'PDF 파일이 손상되었거나 PDF 형식이 아닙니다.';
  if (error instanceof ResponseException) {
    return error.status === 409 || error.status === 404
      ? 'PDF 파일을 찾을 수 없습니다. 라이브러리 레코드의 pdf_path를 확인하세요.'
      : `PDF를 받지 못했습니다 (HTTP ${String(error.status)}).`;
  }
  return `PDF를 열지 못했습니다: ${error instanceof Error ? error.message : String(error)}`;
}

/**
 * Opens `url` with pdf.js; the loading task (and its worker) is destroyed on unmount, URL change, or
 * a new `reloadToken` (retry after a failure).
 */
export function usePdfDocument(url: string | null, reloadToken: number): PdfDocumentState {
  const [state, setState] = useState<PdfDocumentState>({ doc: null, error: null, progress: null });

  useEffect(() => {
    if (!url) return;
    let cancelled = false;
    setState({ doc: null, error: null, progress: null });
    const task = openPdf(url);
    task.onProgress = ({ loaded, total }: { loaded: number; total: number }) => {
      if (!cancelled && total > 0) setState((previous) => ({ ...previous, progress: Math.min(1, loaded / total) }));
    };
    task.promise.then(
      (doc) => {
        if (!cancelled) setState({ doc, error: null, progress: 1 });
      },
      (error: unknown) => {
        if (!cancelled) setState({ doc: null, error: loadError(error), progress: null });
      },
    );
    return () => {
      cancelled = true;
      void task.destroy();
    };
  }, [url, reloadToken]);

  return url ? state : { doc: null, error: null, progress: null };
}
