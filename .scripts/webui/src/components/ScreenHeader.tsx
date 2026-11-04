import type { ReactNode, Ref } from 'react';

interface ScreenHeaderProps {
  /** Short mono caption above the title, e.g. the data source. */
  eyebrow: string;
  title: string;
  description: string;
  /** Receives focus after a route change so screen readers announce the new screen. */
  headingRef?: Ref<HTMLHeadingElement>;
  /** Screen-level actions such as refresh. */
  children?: ReactNode;
  /** A line of facts under the description (e.g. workspace and port on 상태). */
  meta?: ReactNode;
}

export function ScreenHeader({ eyebrow, title, description, headingRef, children, meta }: ScreenHeaderProps) {
  return (
    <div className="screen-head">
      <div className="screen-head-copy">
        <p className="eyebrow" translate="no">
          {eyebrow}
        </p>
        <h1 ref={headingRef} tabIndex={-1}>
          {title}
        </h1>
        <p className="screen-description">{description}</p>
        {meta ? <div className="screen-head-meta">{meta}</div> : null}
      </div>
      {children ? <div className="screen-actions">{children}</div> : null}
    </div>
  );
}
