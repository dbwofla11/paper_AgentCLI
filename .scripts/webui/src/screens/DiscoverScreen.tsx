import type { Ref } from 'react';
import { ScreenHeader } from '../components/ScreenHeader';
import { DISCOVER_HREF, discoverDailyHref, type DiscoverView } from '../hooks/useHashRoute';
import { DailyTab } from './discover/DailyTab';
import { SearchTab } from './discover/SearchTab';
import '../styles/discover.css';

interface DiscoverScreenProps {
  headingRef: Ref<HTMLHeadingElement>;
  reloadToken: number;
  view: DiscoverView;
  /** Search session id (search tab) or `YYYY-MM-DD` (daily tab); null for the tab itself. */
  id: string | null;
  /** `?q=` from an entry link; prefills the search form. */
  prefill: string | null;
}

const TABS: ReadonlyArray<{ view: DiscoverView; href: string; label: string }> = [
  { view: 'search', href: DISCOVER_HREF, label: '검색' },
  { view: 'daily', href: discoverDailyHref(), label: '일일 후보' },
];

/** `#/discover`: external paper search (탭 "검색") and the daily-candidate feed (탭 "일일 후보"). */
export default function DiscoverScreen({ headingRef, reloadToken, view, id, prefill }: DiscoverScreenProps) {
  return (
    <div className="screen discover">
      <ScreenHeader
        eyebrow="00-Inbox/discovery"
        title="논문 탐색"
        description="외부 학술 DB에서 라이브러리에 없는 논문을 찾고, 자동화가 기록한 일일 후보를 날짜별로 살펴봅니다. 고른 후보는 Keep에 담거나 라이브러리에 등록합니다. 탐색 기록은 Git에서 제외된 로컬 캐시입니다."
        headingRef={headingRef}
      />

      <nav className="discover-tabs" aria-label="탐색 보기">
        <ul role="list">
          {TABS.map((tab) => (
            <li key={tab.view}>
              <a className="discover-tab" href={tab.href} aria-current={tab.view === view ? 'page' : undefined}>
                {tab.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      {view === 'daily' ? (
        <DailyTab date={id} reloadToken={reloadToken} />
      ) : (
        <SearchTab id={id} prefill={prefill} reloadToken={reloadToken} />
      )}
    </div>
  );
}
