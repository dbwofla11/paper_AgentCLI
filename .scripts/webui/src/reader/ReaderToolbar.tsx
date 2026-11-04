import { useCallback, useEffect, useId, useRef, useState, useSyncExternalStore, type Ref } from 'react';
import {
  ArrowLeft as IconBack,
  ChevronDown as IconDown,
  ChevronUp as IconUp,
  Highlighter as IconHighlight,
  Minus as IconMinus,
  MoveHorizontal as IconFitWidth,
  PanelRight as IconPanel,
  Plus as IconPlus,
  ScanSearch as IconRegion,
  SlidersHorizontal as IconViewTools,
} from 'lucide-react';
import { AppMenu, ConnectionDot } from '../components/AppHeader';
import { useConnection } from '../hooks/useConnection';
import { PAPERS_HREF, useHashRoute } from '../hooks/useHashRoute';

/**
 * Toolbar tiers, paired with the `max-width: 767px` and `max-width: 479px` blocks in reader.css.
 * Compact: zoom, fit and tools move into 보기 도구. Phone: the page steps move there too, so back,
 * title, page n/N, 보기 도구, panel toggle and app menu fit in one row down to 320px.
 */
const COMPACT_QUERY = '(max-width: 767px)';
const PHONE_QUERY = '(max-width: 479px)';

function useMediaQuery(query: string): boolean {
  const subscribe = useCallback(
    (onChange: () => void) => {
      const list = window.matchMedia(query);
      list.addEventListener('change', onChange);
      return () => list.removeEventListener('change', onChange);
    },
    [query],
  );
  return useSyncExternalStore(subscribe, () => window.matchMedia(query).matches);
}

export const ZOOM_STEPS = [0.5, 0.67, 0.75, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2, 2.5, 3, 4] as const;

/** Next zoom step above (`direction` 1) or below (-1) the current zoom. */
export function steppedZoom(zoom: number, direction: 1 | -1): number {
  if (direction > 0) return ZOOM_STEPS.find((step) => step > zoom + 0.001) ?? ZOOM_STEPS.at(-1)!;
  return [...ZOOM_STEPS].reverse().find((step) => step < zoom - 0.001) ?? ZOOM_STEPS[0];
}

function PageField({
  current,
  count,
  onGo,
}: {
  current: number;
  count: number;
  onGo: (page: number) => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  useEffect(() => {
    setDraft(null);
  }, [current]);
  const commit = () => {
    if (draft === null) return;
    const page = Number.parseInt(draft, 10);
    setDraft(null);
    if (Number.isInteger(page)) onGo(Math.min(count, Math.max(1, page)));
  };
  return (
    <span className="page-field">
      <label className="visually-hidden" htmlFor="reader-page-input">
        쪽 번호 (전체 {count}쪽)
      </label>
      <input
        id="reader-page-input"
        className="page-input num"
        type="text"
        inputMode="numeric"
        autoComplete="off"
        spellCheck={false}
        size={Math.max(2, String(count).length)}
        value={draft ?? String(current)}
        onFocus={(event) => event.currentTarget.select()}
        onChange={(event) => setDraft(event.target.value.replace(/[^\d]/g, ''))}
        onBlur={commit}
        onKeyDown={(event) => {
          if (event.key === 'Enter') {
            event.preventDefault();
            commit();
          } else if (event.key === 'Escape') {
            setDraft(null);
            event.currentTarget.blur();
          }
        }}
      />
      <span className="page-total num" aria-hidden="true">
        / {count}
      </span>
    </span>
  );
}

/** PDF controls; absent while the PDF is missing or loading. */
export interface PdfControls {
  pageCount: number;
  currentPage: number;
  onGoToPage: (page: number) => void;
  zoom: number;
  fit: boolean;
  onZoom: (zoom: number) => void;
  onFit: () => void;
  captureMode: boolean;
  onToggleCapture: () => void;
  highlightsVisible: boolean;
  onToggleHighlights: () => void;
}

export interface ReaderToolbarProps {
  title: string;
  headingRef: Ref<HTMLHeadingElement>;
  pdf: PdfControls | null;
  /** Side panel toggle; absent while the paper is not loaded. */
  panel: { open: boolean; onToggle: () => void } | null;
}

function PageStepButton({
  step,
  currentPage,
  pageCount,
  onGoToPage,
}: Pick<PdfControls, 'currentPage' | 'pageCount' | 'onGoToPage'> & { step: 1 | -1 }) {
  const label = step < 0 ? '이전 쪽' : '다음 쪽';
  return (
    <button
      type="button"
      className="icon-btn"
      onClick={() => onGoToPage(currentPage + step)}
      disabled={step < 0 ? currentPage <= 1 : currentPage >= pageCount}
      aria-label={label}
      title={label}
    >
      {step < 0 ? <IconUp /> : <IconDown />}
    </button>
  );
}

function ZoomGroup({ zoom, fit, onZoom, onFit }: PdfControls) {
  return (
    <div className="toolbar-group" role="group" aria-label="확대·축소">
      <button
        type="button"
        className="icon-btn"
        onClick={() => onZoom(steppedZoom(zoom, -1))}
        disabled={zoom <= ZOOM_STEPS[0]}
        aria-label="축소"
        title="축소"
      >
        <IconMinus />
      </button>
      <button
        type="button"
        className="zoom-value num"
        onClick={() => onZoom(1)}
        aria-label={`현재 ${Math.round(zoom * 100)}%, 누르면 100%`}
        title="100%로 보기"
      >
        {Math.round(zoom * 100)}%
      </button>
      <button
        type="button"
        className="icon-btn"
        onClick={() => onZoom(steppedZoom(zoom, 1))}
        disabled={zoom >= ZOOM_STEPS.at(-1)!}
        aria-label="확대"
        title="확대"
      >
        <IconPlus />
      </button>
      <button type="button" className="icon-btn" onClick={onFit} aria-pressed={fit} aria-label="폭 맞춤" title="폭 맞춤">
        <IconFitWidth />
      </button>
    </div>
  );
}

function ToolGroup({ captureMode, onToggleCapture, highlightsVisible, onToggleHighlights }: PdfControls) {
  return (
    <div className="toolbar-group" role="group" aria-label="도구">
      <button
        type="button"
        className="tool-btn"
        onClick={onToggleCapture}
        aria-pressed={captureMode}
        aria-keyshortcuts="R"
        title="표·그림 영역을 끌어서 골라 질문합니다 (R, Esc로 취소)"
      >
        <IconRegion />
        <span className="tool-btn-label">영역 캡처</span>
        <kbd className="tool-btn-key" aria-hidden="true">
          R
        </kbd>
      </button>
      <button
        type="button"
        className="tool-btn"
        onClick={onToggleHighlights}
        aria-pressed={highlightsVisible}
        title="리뷰 근거 하이라이트 표시"
      >
        <IconHighlight />
        <span className="tool-btn-label">하이라이트</span>
      </button>
    </div>
  );
}

/**
 * 보기 도구: zoom, fit and tools (plus the page steps on phones) in a native popover, like `AppMenu`.
 * Esc and outside clicks close it and return focus to the button. Turning region capture on also
 * closes it, because the capture drag happens on the page underneath.
 */
function ViewToolsMenu({ pdf, pageSteps }: { pdf: PdfControls; pageSteps: boolean }) {
  const popoverId = useId();
  const popoverRef = useRef<HTMLDivElement>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const popover = popoverRef.current;
    if (pdf.captureMode && popover?.matches(':popover-open')) popover.hidePopover();
  }, [pdf.captureMode]);

  return (
    <div className="view-tools">
      <button
        type="button"
        className="icon-btn view-tools-button"
        popoverTarget={popoverId}
        aria-expanded={open}
        aria-label="보기 도구"
        title={pdf.captureMode ? '보기 도구 (영역 캡처 켜짐)' : '보기 도구'}
        data-active={pdf.captureMode ? 'true' : undefined}
      >
        <IconViewTools />
      </button>
      <div
        className="view-tools-popover"
        id={popoverId}
        popover="auto"
        ref={popoverRef}
        role="group"
        aria-label="보기 도구"
        onToggle={(event) => setOpen(event.newState === 'open')}
        onKeyDown={(event) => {
          // Esc closes only this popover; the reader's Esc (leave capture, clear selection) waits.
          if (event.key === 'Escape') event.stopPropagation();
        }}
      >
        {pageSteps ? (
          <div className="view-tools-row">
            <span className="view-tools-label" aria-hidden="true">
              쪽 이동
            </span>
            <div className="toolbar-group" role="group" aria-label="쪽 이동">
              <PageStepButton step={-1} {...pdf} />
              <PageStepButton step={1} {...pdf} />
            </div>
          </div>
        ) : null}
        <div className="view-tools-row">
          <span className="view-tools-label" aria-hidden="true">
            확대·축소
          </span>
          <ZoomGroup {...pdf} />
        </div>
        <ToolGroup {...pdf} />
      </div>
    </div>
  );
}

/**
 * The reader's only top bar (48px; no global header on this route): back, title, PDF controls,
 * panel toggle, connection dot, and the app menu with navigation and theme. Below 768px the zoom,
 * fit and tool controls collapse into 보기 도구, and below 480px the page steps join them.
 */
export function ReaderToolbar({ title, headingRef, pdf, panel }: ReaderToolbarProps) {
  const route = useHashRoute();
  const connection = useConnection();
  const compact = useMediaQuery(COMPACT_QUERY);
  const phone = useMediaQuery(PHONE_QUERY);
  return (
    <div className="reader-toolbar">
      <a className="icon-btn" href={PAPERS_HREF} aria-label="논문 라이브러리로" title="논문 라이브러리로">
        <IconBack />
      </a>
      <h1 className="reader-title" ref={headingRef} tabIndex={-1} title={title}>
        {title}
      </h1>
      {pdf ? (
        <>
          <div className="toolbar-group" role="group" aria-label="쪽 이동">
            {phone ? null : <PageStepButton step={-1} {...pdf} />}
            <PageField current={pdf.currentPage} count={pdf.pageCount} onGo={pdf.onGoToPage} />
            {phone ? null : <PageStepButton step={1} {...pdf} />}
          </div>
          {compact ? (
            <ViewToolsMenu pdf={pdf} pageSteps={phone} />
          ) : (
            <>
              <ZoomGroup {...pdf} />
              <ToolGroup {...pdf} />
            </>
          )}
        </>
      ) : null}
      {panel ? (
        <button
          type="button"
          className="icon-btn toolbar-panel-toggle"
          onClick={panel.onToggle}
          aria-expanded={panel.open}
          aria-controls="reader-side-panel"
          aria-label={panel.open ? '리뷰·질문 패널 접기' : '리뷰·질문 패널 펼치기'}
          title={panel.open ? '패널 접기' : '패널 펼치기'}
        >
          <IconPanel />
        </button>
      ) : null}
      <ConnectionDot state={connection.state} />
      <AppMenu route={route} className="reader-menu" />
    </div>
  );
}
