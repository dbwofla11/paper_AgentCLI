import { PixelsPerInch, type PDFDocumentProxy } from 'pdfjs-dist';
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from 'react';
import type { PageRect, ReaderAnchor } from '../api/types';
import { anchorRects, clientRectsToPage } from './geometry';
import { Copy as IconCopy, MessageSquareText as IconAsk, X as IconClose } from 'lucide-react';
import { PdfPage, type PageHighlight, type PageSize, type PageTarget } from './PdfPage';

/** CSS px per PDF point at 100 % (96/72). */
export const CSS_UNITS = PixelsPerInch.PDF_TO_CSS_UNITS;
export const MIN_ZOOM = 0.25;
export const MAX_ZOOM = 4;
/** Contract limit for selected text. */
const MAX_SELECTION_CHARS = 8000;
/** Pages beyond ±5 of the current page release their canvas (reader design §4 F2). */
const KEEP_PAGES = 5;
/** Horizontal padding around pages; the left gutter also holds the page-margin markers. */
const PAGE_GUTTER_PX = 40;
/** Fit width never draws a page wider than this, so lines stay readable on wide screens (design §7.2). */
const FIT_MAX_PAGE_WIDTH_PX = 1100;
/** The "reading line" (fraction of the viewport height) used for the current page and zoom anchoring. */
const READING_LINE = 0.3;
const EMPTY_TARGETS: readonly PageTarget[] = [];

export interface PdfPaneHandle {
  /** Scrolls to `page`. `y` (page fraction) aims at a spot; `keys` aim at those highlights once located. */
  scrollToPage: (page: number, options?: { y?: number; keys?: readonly string[] }) => void;
  /** Focuses the page scroller without moving it (keyboard scrolling continues from the current spot). */
  focus: () => void;
}

/** Highlights (`keys`) or a whole page (`page`, for plain `p.N` links) briefly flashing after a jump. */
export interface FlashState {
  keys: ReadonlySet<string>;
  page: number | null;
  token: number;
}

interface PdfPaneProps {
  doc: PDFDocumentProxy;
  zoom: number;
  fit: boolean;
  onFitZoom: (zoom: number) => void;
  onCurrentPage: (page: number) => void;
  targetsByPage: ReadonlyMap<number, readonly PageTarget[]>;
  highlightsVisible: boolean;
  activeClaimId: string | null;
  flash: FlashState | null;
  overlay: ReaderAnchor | null;
  captureMode: boolean;
  onCaptureModeChange: (on: boolean) => void;
  /** Why region questions cannot be sent (missing pdftoppm, runner without images); null = they can. */
  regionBlocked: string | null;
  onActivateClaim: (claimId: string) => void;
  onAsk: (anchor: ReaderAnchor, preview?: string | null) => void;
}

type TextAnchor = Extract<ReaderAnchor, { kind: 'text' }>;

interface PendingRegion {
  page: number;
  bbox: PageRect;
  preview: string | null;
}

function sameSet(a: ReadonlySet<number>, b: ReadonlySet<number>): boolean {
  if (a.size !== b.size) return false;
  for (const value of a) if (!b.has(value)) return false;
  return true;
}

/** Top edge (page fraction) of the first located box among `keys`; null when none is located yet. */
function firstBoxY(highlights: PageHighlight[] | undefined, keys: readonly string[]): number | null {
  let y: number | null = null;
  for (const highlight of highlights ?? []) {
    if (!keys.includes(highlight.key)) continue;
    for (const { rect } of highlight.boxes) y = y === null ? rect[1] : Math.min(y, rect[1]);
  }
  return y;
}

/** PNG crop of the rendered page canvas for the region chip (a blob: URL the caller revokes). */
function cropPreview(canvas: HTMLCanvasElement, [x0, y0, x1, y1]: PageRect): Promise<string | null> {
  const sx = x0 * canvas.width;
  const sy = y0 * canvas.height;
  const sw = Math.max(1, (x1 - x0) * canvas.width);
  const sh = Math.max(1, (y1 - y0) * canvas.height);
  const ratio = Math.min(1, 640 / sw, 480 / sh);
  const out = document.createElement('canvas');
  out.width = Math.max(1, Math.round(sw * ratio));
  out.height = Math.max(1, Math.round(sh * ratio));
  out.getContext('2d')?.drawImage(canvas, sx, sy, sw, sh, 0, 0, out.width, out.height);
  return new Promise((resolve) => {
    out.toBlob((blob) => resolve(blob ? URL.createObjectURL(blob) : null), 'image/png');
  });
}

/** Where a popover sits on its page: below the box, or above it near the page bottom. */
function popoverPosition([x0, y0, x1, y1]: PageRect) {
  const center = Math.min(0.9, Math.max(0.1, (x0 + x1) / 2));
  const above = y1 > 0.88;
  return { left: `${center * 100}%`, top: `${(above ? y0 : y1) * 100}%`, above };
}

function SelectionPopover({ anchor, onAsk, onDismiss }: { anchor: TextAnchor; onAsk: () => void; onDismiss: () => void }) {
  const [copied, setCopied] = useState<'idle' | 'copied' | 'failed'>('idle');
  const position = popoverPosition(anchor.rects.at(-1) ?? anchor.rects[0]);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(anchor.text);
      setCopied('copied');
    } catch {
      setCopied('failed');
    }
  };
  return (
    <div
      className="reader-popover"
      data-above={position.above ? 'true' : undefined}
      style={{ left: position.left, top: position.top }}
      role="toolbar"
      aria-label="선택한 텍스트"
      // Keep the text selection alive while a button is pressed.
      onPointerDown={(event) => event.preventDefault()}
      onMouseDown={(event) => event.preventDefault()}
    >
      <button type="button" className="popover-btn popover-btn-primary" onClick={onAsk}>
        <IconAsk />
        질문하기
      </button>
      <button type="button" className="popover-btn" onClick={() => void copy()}>
        <IconCopy />
        {copied === 'copied' ? '복사함' : copied === 'failed' ? '복사 실패' : '복사'}
      </button>
      <button type="button" className="popover-btn popover-btn-icon" onClick={onDismiss} aria-label="선택 해제">
        <IconClose />
      </button>
    </div>
  );
}

function RegionPopover({
  region,
  blocked,
  onAsk,
  onCancel,
}: {
  region: PendingRegion;
  blocked: string | null;
  onAsk: () => void;
  onCancel: () => void;
}) {
  const position = popoverPosition(region.bbox);
  const askRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    askRef.current?.focus({ preventScroll: true });
  }, []);
  return (
    <div
      className="reader-popover reader-popover-region"
      data-above={position.above ? 'true' : undefined}
      style={{ left: position.left, top: position.top }}
      role="dialog"
      aria-label={`${region.page}쪽에서 고른 영역`}
      onKeyDown={(event) => {
        if (event.key === 'Escape') {
          event.stopPropagation();
          onCancel();
        }
      }}
    >
      {region.preview ? (
        <img className="region-preview" src={region.preview} alt={`${region.page}쪽에서 고른 영역 미리 보기`} />
      ) : null}
      <div className="popover-row">
        <button ref={askRef} type="button" className="popover-btn popover-btn-primary" onClick={onAsk} disabled={blocked !== null}>
          <IconAsk />이 영역 질문하기
        </button>
        <button type="button" className="popover-btn" onClick={onCancel}>
          취소
        </button>
      </div>
      {blocked ? <p className="popover-note">{blocked}</p> : null}
    </div>
  );
}

export const PdfPane = forwardRef<PdfPaneHandle, PdfPaneProps>(function PdfPane(
  {
    doc,
    zoom,
    fit,
    onFitZoom,
    onCurrentPage,
    targetsByPage,
    highlightsVisible,
    activeClaimId,
    flash,
    overlay,
    captureMode,
    onCaptureModeChange,
    regionBlocked,
    onActivateClaim,
    onAsk,
  },
  ref,
) {
  const pageCount = doc.numPages;
  const scrollerRef = useRef<HTMLDivElement>(null);
  const pageElements = useRef(new Map<number, HTMLDivElement>());
  const canvases = useRef(new Map<number, HTMLCanvasElement>());
  const located = useRef(new Map<number, PageHighlight[]>());
  const pendingScroll = useRef<{ page: number; keys: readonly string[]; until: number } | null>(null);
  const anchorRef = useRef({ page: 1, fraction: 0, left: 0.5 });
  const currentRef = useRef(1);
  const [sizes, setSizes] = useState<PageSize[] | null>(null);
  const [near, setNear] = useState<ReadonlySet<number>>(() => new Set([1, 2]));
  const [active, setActive] = useState<ReadonlySet<number>>(() => new Set());
  const [current, setCurrent] = useState(1);
  const [selection, setSelection] = useState<TextAnchor | null>(null);
  const [region, setRegion] = useState<PendingRegion | null>(null);
  const scale = zoom * CSS_UNITS;
  const laidOut = sizes !== null;
  const firstWidth = sizes?.[0]?.width ?? 0;

  // Placeholder sizes come from page 1; each page corrects its own size once loaded.
  useEffect(() => {
    let cancelled = false;
    doc.getPage(1).then((page) => {
      if (cancelled) return;
      const viewport = page.getViewport({ scale: 1 });
      const first: PageSize = { width: viewport.width, height: viewport.height, userUnit: page.userUnit || 1 };
      setSizes(Array.from({ length: pageCount }, () => first));
    });
    return () => {
      cancelled = true;
    };
  }, [doc, pageCount]);

  const onSize = useCallback((page: number, size: PageSize) => {
    setSizes((previous) => {
      if (!previous) return previous;
      const old = previous[page - 1];
      if (old && old.width === size.width && old.height === size.height && old.userUnit === size.userUnit) return previous;
      const next = previous.slice();
      next[page - 1] = size;
      return next;
    });
  }, []);

  const onCanvas = useCallback((page: number, canvas: HTMLCanvasElement | null) => {
    if (canvas) canvases.current.set(page, canvas);
    else canvases.current.delete(page);
  }, []);

  const registerElement = useCallback((page: number, element: HTMLDivElement | null) => {
    if (element) pageElements.current.set(page, element);
    else pageElements.current.delete(page);
  }, []);

  const scrollToFraction = useCallback((page: number, y: number | null, smooth: boolean) => {
    const scroller = scrollerRef.current;
    const element = pageElements.current.get(page);
    if (!scroller || !element) return;
    const top =
      y === null
        ? element.offsetTop - 16
        : element.offsetTop + y * element.offsetHeight - scroller.clientHeight * READING_LINE;
    const target = Math.max(0, top);
    const far = Math.abs(target - scroller.scrollTop) > scroller.clientHeight * 3;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    scroller.scrollTo({ top: target, behavior: smooth && !far && !reduced ? 'smooth' : 'auto' });
  }, []);

  useImperativeHandle(
    ref,
    () => ({
      scrollToPage(page, options = {}) {
        const keys = options.keys ?? null;
        const y = options.y ?? (keys ? firstBoxY(located.current.get(page), keys) : null);
        scrollToFraction(page, y, true);
        pendingScroll.current = keys && y === null ? { page, keys, until: Date.now() + 4000 } : null;
      },
      focus() {
        scrollerRef.current?.focus({ preventScroll: true });
      },
    }),
    [scrollToFraction],
  );

  const onHighlights = useCallback(
    (page: number, highlights: PageHighlight[] | null) => {
      if (highlights) located.current.set(page, highlights);
      else located.current.delete(page);
      const pending = pendingScroll.current;
      if (!highlights || !pending || pending.page !== page) return;
      pendingScroll.current = null;
      if (Date.now() > pending.until) return;
      const y = firstBoxY(highlights, pending.keys);
      if (y !== null) scrollToFraction(page, y, true);
    },
    [scrollToFraction],
  );

  // Fit width: recomputed when the pane resizes (window, side panel drag, panel toggle), at most
  // once per frame. The scale change below keeps the reading position (page + offset fraction).
  useEffect(() => {
    const scroller = scrollerRef.current;
    if (!fit || !scroller || !firstWidth) return;
    let frame = 0;
    const update = () => {
      frame = 0;
      const available = Math.min(scroller.clientWidth - PAGE_GUTTER_PX * 2, FIT_MAX_PAGE_WIDTH_PX);
      if (available <= 0) return;
      const next = Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, available / (firstWidth * CSS_UNITS)));
      onFitZoom(Math.round(next * 1000) / 1000);
    };
    update();
    const observer = new ResizeObserver(() => {
      if (!frame) frame = requestAnimationFrame(update);
    });
    observer.observe(scroller);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(frame);
    };
  }, [fit, firstWidth, onFitZoom]);

  // Keep the reading line on the same spot of the same page across zoom changes.
  const previousScale = useRef(scale);
  useLayoutEffect(() => {
    if (previousScale.current === scale) return;
    previousScale.current = scale;
    const scroller = scrollerRef.current;
    const element = pageElements.current.get(anchorRef.current.page);
    if (!scroller || !element) return;
    scroller.scrollTop =
      element.offsetTop + anchorRef.current.fraction * element.offsetHeight - scroller.clientHeight * READING_LINE;
    scroller.scrollLeft = anchorRef.current.left * Math.max(0, scroller.scrollWidth - scroller.clientWidth);
  }, [scale]);

  // Current page and zoom anchor from the scroll position.
  useEffect(() => {
    const scroller = scrollerRef.current;
    if (!scroller || !laidOut) return;
    let frame = 0;
    const measure = () => {
      frame = 0;
      const line = scroller.scrollTop + scroller.clientHeight * READING_LINE;
      let page = 1;
      for (let candidate = 1; candidate <= pageCount; candidate += 1) {
        const element = pageElements.current.get(candidate);
        if (!element) continue;
        if (element.offsetTop <= line) page = candidate;
        else break;
      }
      const element = pageElements.current.get(page);
      const fraction = element ? (line - element.offsetTop) / Math.max(1, element.offsetHeight) : 0;
      const spare = scroller.scrollWidth - scroller.clientWidth;
      anchorRef.current = { page, fraction, left: spare > 0 ? scroller.scrollLeft / spare : 0.5 };
      if (currentRef.current !== page) {
        currentRef.current = page;
        setCurrent(page);
      }
    };
    const onScroll = () => {
      if (!frame) frame = requestAnimationFrame(measure);
    };
    measure();
    scroller.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      scroller.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(frame);
    };
  }, [laidOut, pageCount]);

  useEffect(() => {
    onCurrentPage(current);
  }, [current, onCurrentPage]);

  // Render window: pages within one viewport above or below.
  useEffect(() => {
    const scroller = scrollerRef.current;
    if (!scroller || !laidOut) return;
    const visible = new Set<number>();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          const page = Number((entry.target as HTMLElement).dataset.pageNumber);
          if (entry.isIntersecting) visible.add(page);
          else visible.delete(page);
        }
        setNear(new Set(visible));
      },
      { root: scroller, rootMargin: '100% 0px 100% 0px' },
    );
    for (const element of pageElements.current.values()) observer.observe(element);
    return () => observer.disconnect();
  }, [laidOut, pageCount]);

  useEffect(() => {
    setActive((previous) => {
      const next = new Set(near);
      for (const page of previous) if (Math.abs(page - current) <= KEEP_PAGES) next.add(page);
      return sameSet(previous, next) ? previous : next;
    });
  }, [near, current]);

  // Text selection → popover on the page where the selection starts.
  useEffect(() => {
    const scroller = scrollerRef.current;
    if (!scroller) return;
    let pointerDown = false;
    let frame = 0;
    const read = () => {
      frame = 0;
      const selected = window.getSelection();
      if (!selected || selected.rangeCount === 0 || selected.isCollapsed) {
        setSelection(null);
        return;
      }
      const range = selected.getRangeAt(0);
      const start = range.startContainer;
      const startElement = start instanceof Element ? start : start.parentElement;
      const pageElement = startElement?.closest('.textLayer')?.closest<HTMLElement>('.pdf-page');
      if (!pageElement || !scroller.contains(pageElement)) {
        setSelection(null);
        return;
      }
      const text = selected.toString().replace(/\s+/g, ' ').trim().slice(0, MAX_SELECTION_CHARS);
      const rects = anchorRects(clientRectsToPage(range.getClientRects(), pageElement.getBoundingClientRect()));
      if (!text || rects.length === 0) {
        setSelection(null);
        return;
      }
      setSelection({ kind: 'text', page: Number(pageElement.dataset.pageNumber), text, rects });
    };
    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(read);
    };
    const onSelectionChange = () => {
      if (window.getSelection()?.isCollapsed !== false) setSelection(null);
      else if (!pointerDown) schedule();
    };
    const onPointerDown = (event: PointerEvent) => {
      pointerDown = true;
      // pdf.js viewer behaviour: while selecting, the end-of-content block keeps the selection sane.
      const layer = (event.target as Element | null)?.closest?.('.textLayer');
      layer?.classList.add('selecting');
    };
    const onPointerUp = () => {
      if (!pointerDown) return;
      pointerDown = false;
      for (const layer of scroller.querySelectorAll('.textLayer.selecting')) layer.classList.remove('selecting');
      schedule();
    };
    const onKeyUp = (event: KeyboardEvent) => {
      if (event.shiftKey || event.key === 'Shift') schedule();
    };
    document.addEventListener('selectionchange', onSelectionChange);
    scroller.addEventListener('pointerdown', onPointerDown);
    document.addEventListener('pointerup', onPointerUp);
    window.addEventListener('blur', onPointerUp);
    document.addEventListener('keyup', onKeyUp);
    return () => {
      document.removeEventListener('selectionchange', onSelectionChange);
      scroller.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('pointerup', onPointerUp);
      window.removeEventListener('blur', onPointerUp);
      document.removeEventListener('keyup', onKeyUp);
      cancelAnimationFrame(frame);
    };
  }, []);

  const dismissSelection = useCallback(() => {
    window.getSelection()?.removeAllRanges();
    setSelection(null);
  }, []);

  const askSelection = () => {
    if (!selection) return;
    // Copy the anchor before the composer takes focus (focus does not keep the PDF selection).
    const anchor = selection;
    dismissSelection();
    onAsk(anchor);
  };

  // Region preview URLs are revoked here unless ownership passed to the composer.
  const regionRef = useRef<PendingRegion | null>(null);
  useEffect(() => {
    regionRef.current = region;
  }, [region]);
  useEffect(
    () => () => {
      if (regionRef.current?.preview) URL.revokeObjectURL(regionRef.current.preview);
    },
    [],
  );

  const clearRegion = useCallback(() => {
    setRegion((previous) => {
      if (previous?.preview) URL.revokeObjectURL(previous.preview);
      return null;
    });
  }, []);

  const onRegion = useCallback(
    (page: number, bbox: PageRect) => {
      onCaptureModeChange(false);
      const canvas = canvases.current.get(page);
      setRegion((previous) => {
        if (previous?.preview) URL.revokeObjectURL(previous.preview);
        return { page, bbox, preview: null };
      });
      if (!canvas) return;
      void cropPreview(canvas, bbox).then((preview) => {
        setRegion((previous) => {
          if (previous && previous.page === page && previous.bbox === bbox) return { ...previous, preview };
          if (preview) URL.revokeObjectURL(preview);
          return previous;
        });
      });
    },
    [onCaptureModeChange],
  );

  const askRegion = () => {
    if (!region) return;
    const { page, bbox, preview } = region;
    setRegion(null); // the preview URL now belongs to the composer
    onAsk({ kind: 'region', page, bbox }, preview);
  };

  const cancelCapture = useCallback(() => onCaptureModeChange(false), [onCaptureModeChange]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== 'Escape') return;
      if (region) clearRegion();
      else if (selection) dismissSelection();
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [region, selection, clearRegion, dismissSelection]);

  const flashByPage = useMemo(() => {
    const map = new Map<number, ReadonlySet<string>>();
    if (!flash) return map;
    for (const [page, targets] of targetsByPage) {
      if (targets.some((target) => flash.keys.has(target.key))) map.set(page, flash.keys);
    }
    return map;
  }, [flash, targetsByPage]);

  const regionOverlay: ReaderAnchor | null = region ? { kind: 'region', page: region.page, bbox: region.bbox } : null;

  const onPagesPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    // A click outside any page clears a pending region box.
    if (region && !(event.target as Element).closest('.reader-popover')) {
      if (!(event.target as Element).closest('.pdf-page')) clearRegion();
    }
  };

  return (
    <div
      className="pdf-scroller"
      ref={scrollerRef}
      tabIndex={0}
      role="region"
      aria-label={`PDF 본문, 전체 ${pageCount}쪽`}
      data-capture={captureMode ? 'true' : undefined}
      onPointerDown={onPagesPointerDown}
    >
      {sizes ? (
        <div className="pdf-pages" style={{ paddingInline: `${PAGE_GUTTER_PX}px` }}>
          {sizes.map((size, index) => {
            const page = index + 1;
            const pageOverlay =
              regionOverlay?.page === page
                ? regionOverlay
                : selection?.page === page
                  ? null
                  : overlay && overlay.kind !== 'claim' && overlay.page === page
                    ? overlay
                    : null;
            return (
              <PdfPage
                key={page}
                doc={doc}
                pageNumber={page}
                scale={scale}
                size={size}
                active={active.has(page)}
                targets={targetsByPage.get(page) ?? EMPTY_TARGETS}
                highlightsVisible={highlightsVisible}
                activeClaimId={activeClaimId}
                flashKeys={flashByPage.get(page) ?? null}
                flashToken={flashByPage.has(page) || flash?.page === page ? (flash?.token ?? 0) : 0}
                flashPage={flash?.page === page}
                overlay={pageOverlay}
                captureMode={captureMode}
                onSize={onSize}
                onCanvas={onCanvas}
                onHighlights={onHighlights}
                onActivateClaim={onActivateClaim}
                onRegion={onRegion}
                onCancelCapture={cancelCapture}
                registerElement={registerElement}
              >
                {region?.page === page ? (
                  <RegionPopover region={region} blocked={regionBlocked} onAsk={askRegion} onCancel={clearRegion} />
                ) : selection?.page === page ? (
                  <SelectionPopover anchor={selection} onAsk={askSelection} onDismiss={dismissSelection} />
                ) : null}
              </PdfPage>
            );
          })}
        </div>
      ) : (
        <p className="pdf-loading" role="status">
          쪽 크기를 확인하는 중…
        </p>
      )}
    </div>
  );
});
