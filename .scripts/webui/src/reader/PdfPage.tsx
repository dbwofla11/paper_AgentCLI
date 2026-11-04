import {
  AbortException,
  OutputScale,
  RenderingCancelledException,
  TextLayer,
  type PDFDocumentProxy,
  type PDFPageProxy,
  type RenderTask,
} from 'pdfjs-dist';
import {
  memo,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type KeyboardEvent,
  type PointerEvent,
  type ReactNode,
} from 'react';
import type { EvidenceTarget, PageRect, ReaderAnchor } from '../api/types';
import { rectStyle } from './geometry';
import { RegionCaptureLayer } from './RegionCaptureLayer';
import { buildTextIndex, locateTarget, type HighlightBox } from './textMatch';

/** Page size in CSS px at scale 1, after the page's own rotation. */
export interface PageSize {
  width: number;
  height: number;
  userUnit: number;
}

/** One claim target drawn on a page. `key` = `${claim_id}#${target index}`. */
export interface PageTarget {
  key: string;
  claimId: string;
  target: EvidenceTarget;
  /** Accessible description: the claim statement, shortened. */
  label: string;
}

export interface PageHighlight {
  key: string;
  claimId: string;
  label: string;
  boxes: HighlightBox[];
}

/** Canvas budget per page (pdf.js viewer defaults are of the same order). */
const MAX_CANVAS_PIXELS = 2 ** 24;
const MAX_CANVAS_DIM = 32767;
/** Re-render delay while zooming, so a burst of zoom steps renders once. */
const RERENDER_DELAY_MS = 120;
/** Pointer travel under which a pointerup counts as a click on a highlight. */
const CLICK_SLOP_PX = 4;

interface PdfPageProps {
  doc: PDFDocumentProxy;
  pageNumber: number;
  /** CSS px per PDF unit (zoom × 96/72). */
  scale: number;
  size: PageSize;
  /** Render canvas and text layer (inside the render window); inactive pages are placeholders. */
  active: boolean;
  targets: readonly PageTarget[];
  highlightsVisible: boolean;
  activeClaimId: string | null;
  /** Keys flashing on this page; `flashToken` restarts the animation for the same keys. */
  flashKeys: ReadonlySet<string> | null;
  flashToken: number;
  /** The whole page flashes (a plain `p.N` link landed here). */
  flashPage: boolean;
  /** Anchor drawn on this page (thread anchor, current selection, or captured region). */
  overlay: ReaderAnchor | null;
  captureMode: boolean;
  onSize: (page: number, size: PageSize) => void;
  onCanvas: (page: number, canvas: HTMLCanvasElement | null) => void;
  onHighlights: (page: number, highlights: PageHighlight[] | null) => void;
  onActivateClaim: (claimId: string) => void;
  onRegion: (page: number, bbox: PageRect) => void;
  onCancelCapture: () => void;
  registerElement: (page: number, element: HTMLDivElement | null) => void;
  /** Popovers anchored to this page. */
  children?: ReactNode;
}

function contains([x0, y0, x1, y1]: PageRect, x: number, y: number, slopX: number, slopY: number): boolean {
  return x >= x0 - slopX && x <= x1 + slopX && y >= y0 - slopY && y <= y1 + slopY;
}

function HighlightLayer({
  highlights,
  activeClaimId,
  flashKeys,
  flashToken,
  onActivateClaim,
}: {
  highlights: PageHighlight[];
  activeClaimId: string | null;
  flashKeys: ReadonlySet<string> | null;
  flashToken: number;
  onActivateClaim: (claimId: string) => void;
}) {
  const activate = (event: KeyboardEvent<HTMLDivElement>, claimId: string) => {
    if (event.key !== 'Enter' && event.key !== ' ') return;
    event.preventDefault();
    onActivateClaim(claimId);
  };
  return (
    <div className="hl-layer">
      {highlights.map((highlight) => {
        if (highlight.boxes.length === 0) return null;
        const flashing = flashKeys?.has(highlight.key) ?? false;
        return (
          <div
            key={flashing ? `${highlight.key}:${flashToken}` : highlight.key}
            className="hl-group"
            role="button"
            tabIndex={0}
            aria-label={`리뷰 근거: ${highlight.label}`}
            data-active={highlight.claimId === activeClaimId ? 'true' : undefined}
            data-flash={flashing ? 'true' : undefined}
            onKeyDown={(event) => activate(event, highlight.claimId)}
          >
            {highlight.boxes.map((box, index) => (
              <span key={index} className="hl-rect" data-strength={box.strength} style={rectStyle(box.rect)} />
            ))}
          </div>
        );
      })}
    </div>
  );
}

/** Targets with no box in the text layer get a marker in the page margin instead (one per claim). */
function PageMarkers({
  highlights,
  activeClaimId,
  flashKeys,
  flashToken,
  onActivateClaim,
}: {
  highlights: PageHighlight[];
  activeClaimId: string | null;
  flashKeys: ReadonlySet<string> | null;
  flashToken: number;
  onActivateClaim: (claimId: string) => void;
}) {
  const byClaim = new Map<string, { label: string; flashing: boolean }>();
  for (const highlight of highlights) {
    if (highlight.boxes.length > 0) continue;
    const flashing = flashKeys?.has(highlight.key) ?? false;
    const existing = byClaim.get(highlight.claimId);
    byClaim.set(highlight.claimId, { label: highlight.label, flashing: flashing || (existing?.flashing ?? false) });
  }
  if (byClaim.size === 0) return null;
  return (
    <div className="page-markers">
      {[...byClaim].map(([claimId, { label, flashing }]) => (
        <button
          key={flashing ? `${claimId}:${flashToken}` : claimId}
          type="button"
          className="page-marker"
          data-active={claimId === activeClaimId ? 'true' : undefined}
          data-flash={flashing ? 'true' : undefined}
          aria-label={`이 쪽의 리뷰 근거(위치 미표시): ${label}`}
          title={label}
          onClick={() => onActivateClaim(claimId)}
        >
          <span aria-hidden="true" />
        </button>
      ))}
    </div>
  );
}

function AnchorOverlay({ anchor }: { anchor: ReaderAnchor }) {
  if (anchor.kind === 'text') {
    return (
      <div className="anchor-layer" aria-hidden="true">
        {anchor.rects.map((rect, index) => (
          <span key={index} className="anchor-rect" style={rectStyle(rect)} />
        ))}
      </div>
    );
  }
  if (anchor.kind === 'region') {
    return (
      <div className="anchor-layer" aria-hidden="true">
        <span className="anchor-box" style={rectStyle(anchor.bbox)} />
      </div>
    );
  }
  return anchor.kind === 'page' ? <div className="anchor-page" aria-hidden="true" /> : null;
}

export const PdfPage = memo(function PdfPage({
  doc,
  pageNumber,
  scale,
  size,
  active,
  targets,
  highlightsVisible,
  activeClaimId,
  flashKeys,
  flashToken,
  flashPage,
  overlay,
  captureMode,
  onSize,
  onCanvas,
  onHighlights,
  onActivateClaim,
  onRegion,
  onCancelCapture,
  registerElement,
  children,
}: PdfPageProps) {
  const pageRef = useRef<HTMLDivElement | null>(null);
  const canvasHostRef = useRef<HTMLDivElement>(null);
  const textHostRef = useRef<HTMLDivElement>(null);
  const textLayerRef = useRef<TextLayer | null>(null);
  const hasCanvasRef = useRef(false);
  const scaleRef = useRef(scale);
  const pointerRef = useRef<{ x: number; y: number } | null>(null);
  const [proxy, setProxy] = useState<PDFPageProxy | null>(null);
  const [textReady, setTextReady] = useState(false);
  const [hasCanvas, setHasCanvas] = useState(false);
  const [highlights, setHighlights] = useState<PageHighlight[] | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  useEffect(() => {
    scaleRef.current = scale;
  }, [scale]);

  // Page proxy: loaded once, the first time the page enters the render window.
  useEffect(() => {
    if (!active || proxy) return;
    let cancelled = false;
    doc.getPage(pageNumber).then(
      (page) => {
        if (cancelled) return;
        const viewport = page.getViewport({ scale: 1 });
        onSize(pageNumber, { width: viewport.width, height: viewport.height, userUnit: page.userUnit || 1 });
        setProxy(page);
      },
      () => {
        if (!cancelled) setFailure('이 쪽을 불러오지 못했습니다.');
      },
    );
    return () => {
      cancelled = true;
    };
  }, [active, doc, pageNumber, proxy, onSize]);

  // Canvas: rendered off-DOM and swapped in when done, so zooming never shows a blank page.
  useEffect(() => {
    if (!active || !proxy) return;
    const host = canvasHostRef.current;
    if (!host) return;
    let cancelled = false;
    let task: RenderTask | null = null;
    const timer = window.setTimeout(
      () => {
        const viewport = proxy.getViewport({ scale });
        const output = new OutputScale();
        output.limitCanvas(viewport.width, viewport.height, MAX_CANVAS_PIXELS, MAX_CANVAS_DIM);
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, Math.floor(viewport.width * output.sx));
        canvas.height = Math.max(1, Math.floor(viewport.height * output.sy));
        task = proxy.render({
          canvas,
          viewport,
          transform: output.scaled ? [output.sx, 0, 0, output.sy, 0, 0] : undefined,
        });
        task.promise.then(
          () => {
            if (cancelled) return;
            for (const old of host.querySelectorAll('canvas')) {
              old.width = 0;
              old.height = 0;
            }
            host.replaceChildren(canvas);
            hasCanvasRef.current = true;
            setHasCanvas(true);
            onCanvas(pageNumber, canvas);
            setFailure(null);
          },
          (error: unknown) => {
            if (cancelled || error instanceof RenderingCancelledException) return;
            setFailure('이 쪽을 그리지 못했습니다.');
          },
        );
      },
      hasCanvasRef.current ? RERENDER_DELAY_MS : 0,
    );
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
      task?.cancel();
    };
  }, [active, proxy, scale, pageNumber, onCanvas]);

  // Leaving the render window releases the canvas memory.
  useEffect(() => {
    if (active) return;
    const host = canvasHostRef.current;
    if (!host || !hasCanvasRef.current) return;
    for (const canvas of host.querySelectorAll('canvas')) {
      canvas.width = 0;
      canvas.height = 0;
    }
    host.replaceChildren();
    hasCanvasRef.current = false;
    setHasCanvas(false);
    onCanvas(pageNumber, null);
    proxy?.cleanup();
  }, [active, proxy, pageNumber, onCanvas]);

  // Text layer: laid out once per activation; zoom only rescales it through the CSS variables.
  useEffect(() => {
    if (!active || !proxy) return;
    const host = textHostRef.current;
    if (!host) return;
    const layer = new TextLayer({
      textContentSource: proxy.streamTextContent({ includeMarkedContent: true, disableNormalization: true }),
      container: host,
      viewport: proxy.getViewport({ scale: scaleRef.current }),
    });
    textLayerRef.current = layer;
    let cancelled = false;
    layer.render().then(
      () => {
        if (cancelled) return;
        const end = document.createElement('div');
        end.className = 'endOfContent';
        host.append(end);
        setTextReady(true);
      },
      (error: unknown) => {
        if (cancelled || error instanceof AbortException) return;
        // No text layer (e.g. a broken content stream): highlights fall back to margin markers.
        setTextReady(true);
      },
    );
    return () => {
      cancelled = true;
      layer.cancel();
      textLayerRef.current = null;
      host.replaceChildren();
      setTextReady(false);
    };
  }, [active, proxy]);

  useEffect(() => {
    if (proxy) textLayerRef.current?.update({ viewport: proxy.getViewport({ scale }) });
  }, [proxy, scale]);

  // Highlight boxes, as page fractions, once the text layer is laid out.
  useEffect(() => {
    if (!textReady) {
      setHighlights(null);
      onHighlights(pageNumber, null);
      return;
    }
    const frame = requestAnimationFrame(() => {
      const page = pageRef.current;
      const host = textHostRef.current;
      if (!page || !host) return;
      const index = buildTextIndex(host);
      const pageBox = page.getBoundingClientRect();
      const result = targets.map((target) => ({
        key: target.key,
        claimId: target.claimId,
        label: target.label,
        boxes: locateTarget(index, target.target, pageBox),
      }));
      setHighlights(result);
      onHighlights(pageNumber, result);
    });
    return () => cancelAnimationFrame(frame);
  }, [textReady, targets, pageNumber, onHighlights]);

  const setPageRef = (element: HTMLDivElement | null) => {
    pageRef.current = element;
    registerElement(pageNumber, element);
  };

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    const inside = (event.target as Element).closest('.reader-popover, .page-marker');
    pointerRef.current = event.button === 0 && !inside ? { x: event.clientX, y: event.clientY } : null;
  };

  // The text layer sits above the highlights (text stays selectable), so clicks are hit-tested here.
  const onPointerUp = (event: PointerEvent<HTMLDivElement>) => {
    const down = pointerRef.current;
    pointerRef.current = null;
    if (!down || captureMode || !highlightsVisible || !highlights) return;
    if (Math.hypot(event.clientX - down.x, event.clientY - down.y) >= CLICK_SLOP_PX) return;
    if (window.getSelection()?.isCollapsed === false) return;
    const box = event.currentTarget.getBoundingClientRect();
    if (box.width <= 0 || box.height <= 0) return;
    const x = (event.clientX - box.left) / box.width;
    const y = (event.clientY - box.top) / box.height;
    const slopX = 2 / box.width;
    const slopY = 2 / box.height;
    let best: { claimId: string; area: number } | null = null;
    for (const highlight of highlights) {
      for (const { rect } of highlight.boxes) {
        if (!contains(rect, x, y, slopX, slopY)) continue;
        const area = (rect[2] - rect[0]) * (rect[3] - rect[1]);
        if (!best || area < best.area) best = { claimId: highlight.claimId, area };
      }
    }
    if (best) onActivateClaim(best.claimId);
  };

  // Hidden highlights still show the ones a locator chip or page link just flashed.
  const shown =
    active && highlights
      ? highlightsVisible
        ? highlights
        : flashKeys
          ? highlights.filter((item) => flashKeys.has(item.key))
          : null
      : null;
  const width = Math.floor(size.width * scale);
  const height = Math.floor(size.height * scale);
  const style = {
    width: `${width}px`,
    height: `${height}px`,
    '--scale-factor': String(scale),
    '--user-unit': String(size.userUnit),
    '--total-scale-factor': 'calc(var(--scale-factor) * var(--user-unit))',
    '--scale-round-x': '1px',
    '--scale-round-y': '1px',
  } as CSSProperties;

  return (
    <div
      ref={setPageRef}
      className="pdf-page"
      data-page-number={pageNumber}
      data-capture={captureMode ? 'true' : undefined}
      style={style}
      role="group"
      aria-label={`${pageNumber}쪽`}
      onPointerDown={onPointerDown}
      onPointerUp={onPointerUp}
    >
      <div className="pdf-canvas" ref={canvasHostRef} aria-hidden="true" />
      {!hasCanvas && !failure ? (
        <span className="pdf-page-placeholder" aria-hidden="true">
          <span className="num">{pageNumber}</span>
        </span>
      ) : null}
      {failure ? <p className="pdf-page-failure">{failure}</p> : null}
      {overlay ? <AnchorOverlay anchor={overlay} /> : null}
      {shown ? (
        <HighlightLayer
          highlights={shown}
          activeClaimId={activeClaimId}
          flashKeys={flashKeys}
          flashToken={flashToken}
          onActivateClaim={onActivateClaim}
        />
      ) : null}
      <div className="textLayer" ref={textHostRef} />
      {captureMode && active ? (
        <RegionCaptureLayer page={pageNumber} onRegion={onRegion} onCancel={onCancelCapture} />
      ) : null}
      {shown ? (
        <PageMarkers
          highlights={shown}
          activeClaimId={activeClaimId}
          flashKeys={flashKeys}
          flashToken={flashToken}
          onActivateClaim={onActivateClaim}
        />
      ) : null}
      {flashPage ? <div key={flashToken} className="page-flash" aria-hidden="true" /> : null}
      {children}
    </div>
  );
});
