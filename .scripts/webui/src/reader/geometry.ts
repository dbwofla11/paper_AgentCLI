import type { PageRect } from '../api/types';

/** Contract limit for text anchors (`rects` ≤ 64). */
export const MAX_ANCHOR_RECTS = 64;
/** Contract minimum region side: 1 % of the page. */
export const MIN_REGION_SIDE = 0.01;

function clamp01(value: number): number {
  return Math.min(1, Math.max(0, value));
}

/** Rounds to 5 decimals: enough for sub-pixel accuracy, short in the JSON body. */
function round5(value: number): number {
  return Math.round(value * 1e5) / 1e5;
}

/**
 * Client rects → page fractions (origin top-left) of `pageBox`. Rects outside the page, degenerate
 * rects, and rects under half a pixel are dropped; the rest are merged per line so a line of
 * text spans is one rect.
 */
export function clientRectsToPage(rects: Iterable<DOMRectReadOnly>, pageBox: DOMRectReadOnly): PageRect[] {
  if (pageBox.width <= 0 || pageBox.height <= 0) return [];
  const boxes: PageRect[] = [];
  for (const rect of rects) {
    if (rect.width < 0.5 || rect.height < 0.5) continue;
    const x0 = clamp01((rect.left - pageBox.left) / pageBox.width);
    const y0 = clamp01((rect.top - pageBox.top) / pageBox.height);
    const x1 = clamp01((rect.right - pageBox.left) / pageBox.width);
    const y1 = clamp01((rect.bottom - pageBox.top) / pageBox.height);
    if (x1 - x0 <= 0 || y1 - y0 <= 0) continue;
    boxes.push([x0, y0, x1, y1]);
  }
  return mergeLineRects(boxes);
}

/** Merges rects that share a line (vertical overlap ≥ 50 %) and touch or overlap horizontally. */
export function mergeLineRects(rects: PageRect[]): PageRect[] {
  const sorted = [...rects].sort((a, b) => a[1] - b[1] || a[0] - b[0]);
  const merged: PageRect[] = [];
  for (const rect of sorted) {
    const last = merged.at(-1);
    if (last) {
      const overlap = Math.min(last[3], rect[3]) - Math.max(last[1], rect[1]);
      const height = Math.min(last[3] - last[1], rect[3] - rect[1]);
      const gap = rect[0] - last[2];
      if (overlap >= height * 0.5 && gap <= 0.004 && rect[0] >= last[0] - 0.004) {
        merged[merged.length - 1] = [
          Math.min(last[0], rect[0]),
          Math.min(last[1], rect[1]),
          Math.max(last[2], rect[2]),
          Math.max(last[3], rect[3]),
        ];
        continue;
      }
    }
    merged.push(rect);
  }
  return merged;
}

/** Contract-shaped rects for a text anchor: rounded, non-degenerate, at most 64 (merged to line boxes first). */
export function anchorRects(rects: PageRect[]): PageRect[] {
  let result = mergeLineRects(rects);
  if (result.length > MAX_ANCHOR_RECTS) {
    // Too many separate boxes (e.g. a multi-column selection): keep one box per text line band.
    const bands: PageRect[] = [];
    for (const rect of result) {
      const last = bands.at(-1);
      if (last && rect[1] < last[3]) {
        bands[bands.length - 1] = [
          Math.min(last[0], rect[0]),
          last[1],
          Math.max(last[2], rect[2]),
          Math.max(last[3], rect[3]),
        ];
      } else {
        bands.push(rect);
      }
    }
    result = bands.slice(0, MAX_ANCHOR_RECTS);
  }
  return result
    .map((rect) => rect.map(round5) as PageRect)
    .filter(([x0, y0, x1, y1]) => x0 < x1 && y0 < y1);
}

/** Normalized box from two drag points (fractions), clamped to the page. */
export function boxFromPoints(ax: number, ay: number, bx: number, by: number): PageRect {
  return [
    clamp01(Math.min(ax, bx)),
    clamp01(Math.min(ay, by)),
    clamp01(Math.max(ax, bx)),
    clamp01(Math.max(ay, by)),
  ];
}

export function regionLargeEnough([x0, y0, x1, y1]: PageRect): boolean {
  return x1 - x0 >= MIN_REGION_SIDE && y1 - y0 >= MIN_REGION_SIDE;
}

export function roundRect(rect: PageRect): PageRect {
  return rect.map(round5) as PageRect;
}

/** Inline style for an absolutely positioned box inside a page (percentages, so it follows zoom). */
export function rectStyle([x0, y0, x1, y1]: PageRect): { left: string; top: string; width: string; height: string } {
  return {
    left: `${x0 * 100}%`,
    top: `${y0 * 100}%`,
    width: `${(x1 - x0) * 100}%`,
    height: `${(y1 - y0) * 100}%`,
  };
}
