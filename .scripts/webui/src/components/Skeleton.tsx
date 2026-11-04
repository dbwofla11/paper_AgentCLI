import type { CSSProperties } from 'react';

/** Shimmer block sized like the content it stands in for. Decorative: pair it with a status text. */
export function Skeleton({ height, width, radius, className }: {
  height: CSSProperties['height'];
  width?: CSSProperties['width'];
  radius?: CSSProperties['borderRadius'];
  className?: string;
}) {
  return (
    <span
      className={className ? `skeleton ${className}` : 'skeleton'}
      style={{ height, width, borderRadius: radius }}
      aria-hidden="true"
    />
  );
}
