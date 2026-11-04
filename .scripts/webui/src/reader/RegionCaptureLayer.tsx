import { useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import type { PageRect } from '../api/types';
import { boxFromPoints, rectStyle, regionLargeEnough, roundRect } from './geometry';

/**
 * Drag-to-capture box over one page (top layer, pointer events only in capture mode).
 * The box is clamped to the page where the drag started; Esc cancels.
 */
export function RegionCaptureLayer({
  page,
  onRegion,
  onCancel,
}: {
  page: number;
  onRegion: (page: number, bbox: PageRect) => void;
  onCancel: () => void;
}) {
  const startRef = useRef<{ x: number; y: number; id: number } | null>(null);
  const [box, setBox] = useState<PageRect | null>(null);

  const point = (event: PointerEvent<HTMLDivElement>) => {
    const rect = event.currentTarget.getBoundingClientRect();
    return { x: (event.clientX - rect.left) / rect.width, y: (event.clientY - rect.top) / rect.height };
  };

  const onPointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    event.currentTarget.setPointerCapture(event.pointerId);
    event.currentTarget.focus({ preventScroll: true });
    const { x, y } = point(event);
    startRef.current = { x, y, id: event.pointerId };
    setBox([x, y, x, y]);
  };

  const onPointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const start = startRef.current;
    if (!start || start.id !== event.pointerId) return;
    const { x, y } = point(event);
    setBox(boxFromPoints(start.x, start.y, x, y));
  };

  const finish = (event: PointerEvent<HTMLDivElement>) => {
    const start = startRef.current;
    if (!start || start.id !== event.pointerId) return;
    event.stopPropagation();
    startRef.current = null;
    const { x, y } = point(event);
    const bbox = boxFromPoints(start.x, start.y, x, y);
    setBox(null);
    if (regionLargeEnough(bbox)) onRegion(page, roundRect(bbox));
  };

  const onKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'Escape') return;
    event.stopPropagation();
    startRef.current = null;
    setBox(null);
    onCancel();
  };

  return (
    <div
      className="region-layer"
      tabIndex={-1}
      aria-label={`${page}쪽 영역 캡처: 끌어서 영역을 고르세요. Esc로 취소합니다.`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={finish}
      onPointerCancel={() => {
        startRef.current = null;
        setBox(null);
      }}
      onKeyDown={onKeyDown}
    >
      {box ? <span className="region-draft" style={rectStyle(box)} data-small={regionLargeEnough(box) ? undefined : 'true'} /> : null}
    </div>
  );
}
