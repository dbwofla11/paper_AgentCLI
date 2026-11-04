import * as m from 'motion/react-m';
import { formatCount } from '../../format';
import { ENTER_FROM, ENTER_TO, enterTransition } from '../../motion/tokens';
import type { LibraryStats as Stats } from './stats';

const TILES: ReadonlyArray<{ key: keyof Stats; stat: string; label: string; hint: string }> = [
  { key: 'total', stat: 'total', label: '전체 논문', hint: '라이브러리 기록' },
  { key: 'reviewed', stat: 'reviewed', label: '리뷰 완료', hint: '구조화 리뷰 완료' },
  { key: 'queued', stat: 'queued', label: '읽기 대기', hint: '후보 · Keep · 트리아지 · 읽는 중' },
  { key: 'categories', stat: 'categories', label: '연구 분야', hint: '서로 다른 분야' },
  { key: 'withPdf', stat: 'pdf', label: 'PDF 있음', hint: '리더로 열 수 있음' },
];

/** Five count tiles; they rise in with an 80 ms stagger on first render. */
export function LibraryStats({ stats, queuedHint }: { stats: Stats; queuedHint: string | null }) {
  return (
    <ul className="stat-grid" aria-label="라이브러리 요약">
      {TILES.map((tile, index) => (
        <m.li
          key={tile.key}
          className="stat-tile"
          data-stat={tile.stat}
          initial={ENTER_FROM}
          animate={ENTER_TO}
          transition={enterTransition(index)}
        >
          <span className="stat-label">{tile.label}</span>
          <span className="stat-value num">{formatCount(stats[tile.key])}</span>
          <span className="stat-hint">{tile.key === 'queued' && queuedHint ? queuedHint : tile.hint}</span>
        </m.li>
      ))}
    </ul>
  );
}
