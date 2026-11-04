import { useEffect, useId, useRef, type ReactNode } from 'react';
import { Menu, Monitor, Moon, Sun } from 'lucide-react';
import * as m from 'motion/react-m';
import type { ConnectionSnapshot, ConnectionState } from '../api/client';
import {
  HARNESS_HREF,
  IDEAS_HREF,
  JOBS_HREF,
  PAPERS_HREF,
  STATUS_HREF,
  type Route,
} from '../hooks/useHashRoute';
import { DUR_INDICATOR, EASE_OUT } from '../motion/tokens';
import { setThemePreference, useThemePreference, type ThemePreference } from '../theme';

type ScreenName = 'papers' | 'ideas' | 'harness' | 'status' | 'jobs';

const SCREENS: ReadonlyArray<{ route: ScreenName; href: string; label: string }> = [
  { route: 'papers', href: PAPERS_HREF, label: '논문' },
  { route: 'ideas', href: IDEAS_HREF, label: '사고실험' },
  { route: 'harness', href: HARNESS_HREF, label: '하네스' },
  { route: 'status', href: STATUS_HREF, label: '상태' },
  { route: 'jobs', href: JOBS_HREF, label: '작업' },
];

const CONNECTION_LABELS: Record<ConnectionState, string> = {
  connecting: '서버 확인 중…',
  online: '서버 연결됨',
  offline: '서버 연결 끊김',
};

const THEME_OPTIONS: ReadonlyArray<{ value: ThemePreference; label: string; icon: ReactNode }> = [
  { value: 'system', label: '시스템', icon: <Monitor /> },
  { value: 'light', label: '라이트', icon: <Sun /> },
  { value: 'dark', label: '다크', icon: <Moon /> },
];

/** The reader belongs to the paper library in the navigation. */
function activeScreen(route: Route): ScreenName | null {
  if (route.name === 'reader') return 'papers';
  return route.name === 'not_found' ? null : route.name;
}

function Brand() {
  return (
    <a className="brand" href={PAPERS_HREF}>
      <svg className="brand-mark" viewBox="0 0 32 32" width="32" height="32" aria-hidden="true">
        <defs>
          <linearGradient id="brand-gradient" x1="0" y1="0" x2="1" y2="1">
            <stop offset="0" stopColor="#4285F4" />
            <stop offset="0.55" stopColor="#00BCD4" />
            <stop offset="1" stopColor="#34A853" />
          </linearGradient>
        </defs>
        <rect width="32" height="32" rx="8" fill="url(#brand-gradient)" />
        <path d="M16 7c.8 4.3 3.7 7.2 8 8-4.3.8-7.2 3.7-8 8-.8-4.3-3.7-7.2-8-8 4.3-.8 7.2-3.7 8-8z" fill="#FFFFFF" />
      </svg>
      <span className="brand-text">
        <span className="brand-name" translate="no">
          Paper Agent
        </span>
        <span className="brand-caption">연구 하네스</span>
      </span>
    </a>
  );
}

/** Primary navigation. `indicator` animates the active underline between items (desktop header). */
function NavLinks({ active, indicator }: { active: ScreenName | null; indicator: boolean }) {
  return (
    <>
      {SCREENS.map((screen) => (
        <a
          key={screen.route}
          className="nav-link"
          href={screen.href}
          aria-current={screen.route === active ? 'page' : undefined}
        >
          {screen.label}
          {indicator && screen.route === active ? (
            <m.span
              className="nav-indicator"
              layoutId="nav-indicator"
              transition={{ duration: DUR_INDICATOR, ease: EASE_OUT }}
              aria-hidden="true"
            />
          ) : null}
        </a>
      ))}
    </>
  );
}

/** 시스템 / 라이트 / 다크: native radios (arrow keys move the choice), icons as labels. */
export function ThemeToggle() {
  const preference = useThemePreference();
  const name = useId();
  return (
    <fieldset className="theme-toggle">
      <legend className="visually-hidden">화면 테마</legend>
      {THEME_OPTIONS.map((option) => (
        <label key={option.value} className="theme-option" title={`${option.label} 테마`}>
          <input
            type="radio"
            name={`theme-${name}`}
            value={option.value}
            checked={preference === option.value}
            onChange={() => setThemePreference(option.value)}
          />
          {option.icon}
          <span className="visually-hidden">{option.label}</span>
        </label>
      ))}
    </fieldset>
  );
}

export function ConnectionPill({ state }: { state: ConnectionState }) {
  return (
    <p className="connection" data-state={state} role="status">
      <span className="dot" aria-hidden="true" />
      <span className="connection-label">{CONNECTION_LABELS[state]}</span>
    </p>
  );
}

/** Dot-only connection state for dense bars (reader toolbar); the label stays available to assistive tech. */
export function ConnectionDot({ state }: { state: ConnectionState }) {
  return (
    <p className="connection connection-dot" data-state={state} role="status" title={CONNECTION_LABELS[state]}>
      <span className="dot" aria-hidden="true" />
      <span className="visually-hidden">{CONNECTION_LABELS[state]}</span>
    </p>
  );
}

/**
 * Menu button with a popover holding the navigation and the theme toggle. Used by the header
 * below 768px and by the reader toolbar, which has no global header. Closes on route change,
 * Esc and outside clicks (native popover light dismiss).
 */
export function AppMenu({ route, className }: { route: Route; className?: string }) {
  const popoverId = useId();
  const popoverRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const popover = popoverRef.current;
    if (popover?.matches(':popover-open')) popover.hidePopover();
  }, [route]);

  return (
    <div className={className ? `app-menu ${className}` : 'app-menu'}>
      <button type="button" className="icon-btn app-menu-button" popoverTarget={popoverId} aria-label="메뉴">
        <Menu />
      </button>
      <div className="app-menu-popover" id={popoverId} popover="auto" ref={popoverRef}>
        <nav aria-label="메뉴">
          <NavLinks active={activeScreen(route)} indicator={false} />
        </nav>
        <div className="app-menu-theme">
          <span className="field-label">화면 테마</span>
          <ThemeToggle />
        </div>
      </div>
    </div>
  );
}

/** Sticky 64px header of every screen except the reader. */
export function AppHeader({ route, connection }: { route: Route; connection: ConnectionSnapshot }) {
  return (
    <header className="app-header">
      <div className="app-header-inner">
        <Brand />
        <nav className="app-nav" aria-label="주 메뉴">
          <NavLinks active={activeScreen(route)} indicator />
        </nav>
        <div className="app-header-tools">
          <ThemeToggle />
          <ConnectionPill state={connection.state} />
          <AppMenu route={route} className="app-menu-narrow" />
        </div>
      </div>
    </header>
  );
}
