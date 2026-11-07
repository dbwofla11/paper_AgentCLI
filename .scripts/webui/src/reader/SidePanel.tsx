import { useRef, useState, type CSSProperties, type KeyboardEvent, type PointerEvent, type ReactNode } from 'react';

export type PanelTab = 'review' | 'questions';

export const PANEL_MIN_WIDTH = 360;
export const PANEL_MAX_WIDTH = 760;
const STEP_PX = 24;

const TABS: ReadonlyArray<{ key: PanelTab; label: string }> = [
  { key: 'review', label: '리뷰' },
  { key: 'questions', label: '질문' },
];

/** Reading size of the review and answer text (design §7.4); sizes live in reader.css. */
type TextSize = 's' | 'm' | 'l';

const TEXT_SIZE_KEY = 'research-webui.reader.text-size';
const TEXT_SIZES: ReadonlyArray<{ key: TextSize; label: string }> = [
  { key: 's', label: '작게' },
  { key: 'm', label: '보통' },
  { key: 'l', label: '크게' },
];

function storedTextSize(): TextSize {
  try {
    const value = window.localStorage.getItem(TEXT_SIZE_KEY);
    return value === 's' || value === 'l' ? value : 'm';
  } catch {
    return 'm';
  }
}

/** Clamp to the bounds and to 65 % of the reader width, so the PDF always keeps room. */
export function clampPanelWidth(width: number, containerWidth: number): number {
  const limit = Math.max(PANEL_MIN_WIDTH, Math.min(PANEL_MAX_WIDTH, containerWidth * 0.65));
  return Math.round(Math.min(limit, Math.max(PANEL_MIN_WIDTH, width)));
}

function PanelResizer({
  width,
  onResize,
}: {
  width: number;
  onResize: (width: number) => void;
}) {
  const dragRef = useRef<{ startX: number; startWidth: number } | null>(null);

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = { startX: event.clientX, startWidth: width };
  };
  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag) return;
    // The panel is on the right: dragging left widens it.
    onResize(drag.startWidth + (drag.startX - event.clientX));
  };
  const end = () => {
    dragRef.current = null;
  };
  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const delta =
      event.key === 'ArrowLeft' ? STEP_PX : event.key === 'ArrowRight' ? -STEP_PX : event.key === 'Home' ? -10_000 : event.key === 'End' ? 10_000 : 0;
    if (!delta) return;
    event.preventDefault();
    onResize(width + delta);
  };

  return (
    <div
      className="panel-resizer"
      role="separator"
      aria-orientation="vertical"
      aria-label="패널 폭 조절"
      aria-valuenow={width}
      aria-valuemin={PANEL_MIN_WIDTH}
      aria-valuemax={PANEL_MAX_WIDTH}
      tabIndex={0}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={end}
      onPointerCancel={end}
      onLostPointerCapture={end}
      onKeyDown={onKeyDown}
    />
  );
}

/** 가 S/M/L: three pressed-state buttons, saved in localStorage. */
function TextSizeControl({ size, onChange }: { size: TextSize; onChange: (size: TextSize) => void }) {
  return (
    <div className="text-size" role="group" aria-label="글자 크기">
      {TEXT_SIZES.map((item) => (
        <button
          key={item.key}
          type="button"
          className="text-size-btn"
          data-size={item.key}
          aria-pressed={size === item.key}
          title={`글자 크기 ${item.label}`}
          onClick={() => onChange(item.key)}
        >
          <span aria-hidden="true">가</span>
          <span className="visually-hidden">{item.label}</span>
        </button>
      ))}
    </div>
  );
}

export function SidePanel({
  open,
  width,
  onResize,
  tab,
  onTabChange,
  questionCount,
  header,
  children,
}: {
  open: boolean;
  width: number;
  onResize: (width: number) => void;
  tab: PanelTab;
  onTabChange: (tab: PanelTab) => void;
  questionCount: number;
  /** Content above the tab panels: the 인용·피인용 strip, plus the role strip on the 질문 tab. */
  header?: ReactNode;
  children: ReactNode;
}) {
  const tabRefs = useRef(new Map<PanelTab, HTMLButtonElement>());
  const [textSize, setTextSize] = useState<TextSize>(storedTextSize);

  const changeTextSize = (size: TextSize) => {
    setTextSize(size);
    try {
      window.localStorage.setItem(TEXT_SIZE_KEY, size);
    } catch {
      // Storage unavailable: the size lasts for this page only.
    }
  };

  const onTabKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight' && event.key !== 'Home' && event.key !== 'End') return;
    event.preventDefault();
    const index = TABS.findIndex((item) => item.key === tab);
    const next =
      event.key === 'Home'
        ? 0
        : event.key === 'End'
          ? TABS.length - 1
          : (index + (event.key === 'ArrowRight' ? 1 : -1) + TABS.length) % TABS.length;
    onTabChange(TABS[next].key);
    tabRefs.current.get(TABS[next].key)?.focus();
  };

  return (
    <>
      {open ? <PanelResizer width={width} onResize={onResize} /> : null}
      <aside
        id="reader-side-panel"
        className="side-panel"
        hidden={!open}
        data-text-size={textSize}
        style={{ '--panel-width': `${width}px` } as CSSProperties}
        aria-label="리뷰와 질문"
      >
        <div className="side-panel-head">
          <div className="side-tabs" role="tablist" aria-label="패널">
            {TABS.map((item) => (
              <button
                key={item.key}
                ref={(element) => {
                  if (element) tabRefs.current.set(item.key, element);
                  else tabRefs.current.delete(item.key);
                }}
                type="button"
                role="tab"
                id={`reader-tab-${item.key}`}
                className="side-tab"
                aria-selected={tab === item.key}
                aria-controls="reader-tab-panel"
                tabIndex={tab === item.key ? 0 : -1}
                onClick={() => onTabChange(item.key)}
                onKeyDown={onTabKeyDown}
              >
                {item.label}
                {item.key === 'questions' && questionCount > 0 ? (
                  <span className="side-tab-count num">{questionCount}</span>
                ) : null}
              </button>
            ))}
          </div>
          <TextSizeControl size={textSize} onChange={changeTextSize} />
        </div>
        {header}
        <div
          id="reader-tab-panel"
          className="side-panel-body"
          role="tabpanel"
          aria-labelledby={`reader-tab-${tab}`}
          tabIndex={-1}
        >
          {children}
        </div>
      </aside>
    </>
  );
}
