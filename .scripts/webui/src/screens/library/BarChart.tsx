import * as m from 'motion/react-m';
import { formatCount } from '../../format';
import { DUR_ENTER, EASE_OUT, staggerDelay } from '../../motion/tokens';
import type { BarDatum } from './stats';

/** Bars beyond this index share the last stagger delay. */
const STAGGER_CAP = 8;

/**
 * Horizontal bar list. The rows are plain text ("2026 · 3편") for assistive tech; the bars are
 * decorative and grow scaleX 0 → 1 from the left.
 */
export function BarChart({ title, data, unit = '편' }: { title: string; data: BarDatum[]; unit?: string }) {
  const max = Math.max(1, ...data.map((datum) => datum.count));
  return (
    <figure className="bar-chart card">
      <figcaption className="bar-chart-title">{title}</figcaption>
      {data.length === 0 ? (
        <p className="meta">표시할 값이 없습니다.</p>
      ) : (
        <ol className="bar-list" role="list">
          {data.map((datum, index) => (
            <li className="bar-row" key={datum.key}>
              <span className="bar-label">{datum.label}</span>
              <span className="bar-track" aria-hidden="true">
                <m.span
                  className="bar-fill"
                  style={{ width: `${(datum.count / max) * 100}%`, originX: 0 }}
                  initial={{ scaleX: 0 }}
                  animate={{ scaleX: 1 }}
                  transition={{ duration: DUR_ENTER, ease: EASE_OUT, delay: staggerDelay(index, STAGGER_CAP) }}
                />
              </span>
              <span className="bar-value num">
                {formatCount(datum.count)}
                <span className="visually-hidden">{unit}</span>
              </span>
            </li>
          ))}
        </ol>
      )}
    </figure>
  );
}
