import { GlobalWorkerOptions, VerbosityLevel, getDocument, type PDFDocumentLoadingTask } from 'pdfjs-dist';
// Same-origin module worker, so the WebUI CSP (`worker-src 'self'`) needs no change.
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

GlobalWorkerOptions.workerSrc = workerUrl;

/** Copied next to the build output by the `pdfjs-assets` Vite plugin (served from node_modules in dev). */
const ASSETS = `${import.meta.env.BASE_URL}pdfjs/`;

/**
 * Decision D10: no WASM (the worker imports the `*_nowasm_fallback.js` decoders from `wasmUrl` instead),
 * one worker (no worker-side rendering), and one plain GET of the PDF (no range or stream probing).
 */
export function openPdf(url: string): PDFDocumentLoadingTask {
  return getDocument({
    url,
    cMapUrl: `${ASSETS}cmaps/`,
    cMapPacked: true,
    standardFontDataUrl: `${ASSETS}standard_fonts/`,
    wasmUrl: `${ASSETS}wasm/`,
    useWasm: false,
    disableRange: true,
    disableStream: true,
    disableWorkerRendering: true,
    verbosity: VerbosityLevel.ERRORS,
  });
}
