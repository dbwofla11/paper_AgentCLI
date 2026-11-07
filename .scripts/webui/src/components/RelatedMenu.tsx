import { useEffect, useId, useRef, useState, type KeyboardEvent } from 'react';
import { ChevronDown, CircleAlert, LoaderCircle, Network } from 'lucide-react';
import type { ApiError } from '../api/client';
import type { RelatedKind } from '../api/types';
import {
  RELATED_KIND_DESCRIPTIONS,
  RELATED_KIND_LABELS,
  RELATED_KIND_ORDER,
  type RelatedLookup,
} from '../hooks/useRelatedLookup';

/** Menu geometry, known before it renders: width set here, height of two 52px items plus padding. */
const MENU_WIDTH = 256;
const MENU_HEIGHT = 128;
const GAP = 6;
const EDGE = 8;

/**
 * Below the button unless the viewport has no room there; right edge on the button's right edge when
 * that fits (actions columns sit at the card's right), otherwise left edge on its left edge.
 */
function placeMenu(menu: HTMLElement, button: HTMLElement): void {
  const rect = button.getBoundingClientRect();
  const { innerWidth, innerHeight } = window;
  const width = Math.min(MENU_WIDTH, innerWidth - 2 * EDGE);
  const below = innerHeight - rect.bottom >= MENU_HEIGHT + GAP + EDGE || rect.top < MENU_HEIGHT + GAP + EDGE;
  const left =
    rect.right - width >= EDGE ? rect.right - width : Math.min(Math.max(EDGE, rect.left), innerWidth - width - EDGE);
  menu.style.width = `${width}px`;
  menu.style.left = `${Math.round(left)}px`;
  menu.style.top = below ? `${Math.round(rect.bottom + GAP)}px` : 'auto';
  menu.style.bottom = below ? 'auto' : `${Math.round(innerHeight - rect.top + GAP)}px`;
}

interface RelatedMenuProps {
  lookup: RelatedLookup;
  /** Space-separated ids describing the button: the paper title, the reason it is disabled. */
  describedBy?: string;
  /** The paper has no arXiv, DOI or S2 ID: the button stays disabled (explain it through `describedBy`). */
  disabled?: boolean;
  /** Button classes, e.g. `btn btn-tonal btn-small`. */
  className: string;
}

type FocusIntent = 'first' | 'last';

/**
 * 인용·피인용 menu button (WAI-ARIA menu button): a native `popover="auto"` in the top layer, so it is
 * never clipped by a card and closes on outside clicks. Enter, Space and ↓ open it on the first item,
 * ↑ on the last; ↑/↓/Home/End move between the two items; Esc closes it back to the button; Tab moves
 * on and focus leaving the menu closes it. While the server asks Semantic Scholar (up to ~30 s) the
 * button stays focusable, reads "… 가져오는 중", and a live region announces the wait.
 */
export function RelatedMenu({ lookup, describedBy, disabled = false, className }: RelatedMenuProps) {
  const buttonId = useId();
  const menuId = useId();
  const buttonRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const itemRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const focusIntent = useRef<FocusIntent>('first');
  const [open, setOpen] = useState(false);
  const { pending, open: lookUp } = lookup;
  const busy = pending !== null;

  // The menu follows its button while the page or a panel scrolls, and when the window resizes.
  useEffect(() => {
    if (!open) return;
    let frame = 0;
    const follow = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        if (menuRef.current && buttonRef.current) placeMenu(menuRef.current, buttonRef.current);
      });
    };
    window.addEventListener('resize', follow);
    window.addEventListener('scroll', follow, true);
    return () => {
      window.removeEventListener('resize', follow);
      window.removeEventListener('scroll', follow, true);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, [open]);

  // A lookup that starts elsewhere (or a disabled button) never leaves the menu open.
  useEffect(() => {
    if ((busy || disabled) && menuRef.current?.matches(':popover-open')) menuRef.current.hidePopover();
  }, [busy, disabled]);

  const focusItem = (index: number) => {
    const items = itemRefs.current.filter((item): item is HTMLButtonElement => item !== null);
    if (items.length === 0) return;
    items[(index + items.length) % items.length].focus();
  };

  const close = (returnFocus: boolean) => {
    if (menuRef.current?.matches(':popover-open')) menuRef.current.hidePopover();
    if (returnFocus) buttonRef.current?.focus();
  };

  const choose = (kind: RelatedKind) => {
    close(true);
    lookUp(kind);
  };

  const onButtonKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    event.preventDefault();
    if (busy || disabled) return;
    const intent: FocusIntent = event.key === 'ArrowUp' ? 'last' : 'first';
    if (open) {
      focusItem(intent === 'first' ? 0 : -1);
      return;
    }
    focusIntent.current = intent;
    // Opens through the button's popovertarget, so the browser keeps it as the menu's invoker.
    buttonRef.current?.click();
  };

  const onMenuKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    const items = itemRefs.current;
    const index = items.findIndex((item) => item === document.activeElement);
    switch (event.key) {
      case 'ArrowDown':
        event.preventDefault();
        focusItem(index + 1);
        break;
      case 'ArrowUp':
        event.preventDefault();
        focusItem(index - 1);
        break;
      case 'Home':
        event.preventDefault();
        focusItem(0);
        break;
      case 'End':
        event.preventDefault();
        focusItem(-1);
        break;
      case 'Escape':
        // Only this menu closes; the reader's own Esc (leave capture, clear selection) waits.
        event.preventDefault();
        event.stopPropagation();
        close(true);
        break;
      case 'Tab':
        // Closes, then the browser moves focus on from the item as usual (Shift+Tab: back to the button).
        close(false);
        break;
    }
  };

  const label = pending !== null ? `${RELATED_KIND_LABELS[pending]} 가져오는 중…` : '인용·피인용';

  return (
    <>
      <button
        type="button"
        id={buttonId}
        ref={buttonRef}
        className={`${className} related-menu-button`}
        popoverTarget={busy || disabled ? undefined : menuId}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-describedby={describedBy}
        aria-disabled={busy || undefined}
        aria-busy={busy}
        disabled={disabled}
        onKeyDown={onButtonKeyDown}
      >
        {busy ? <LoaderCircle className="related-spinner" aria-hidden="true" /> : <Network aria-hidden="true" />}
        {label}
        {busy ? null : <ChevronDown className="related-menu-caret" aria-hidden="true" />}
      </button>
      <div
        id={menuId}
        ref={menuRef}
        className="related-menu"
        popover="auto"
        role="menu"
        tabIndex={-1}
        aria-labelledby={buttonId}
        onBeforeToggle={(event) => {
          if (event.newState === 'open' && menuRef.current && buttonRef.current) {
            placeMenu(menuRef.current, buttonRef.current);
          }
        }}
        onToggle={(event) => {
          const nowOpen = event.newState === 'open';
          setOpen(nowOpen);
          if (nowOpen) {
            // Placed again in case the browser opened it without a beforetoggle event reaching React.
            if (menuRef.current && buttonRef.current) placeMenu(menuRef.current, buttonRef.current);
            focusItem(focusIntent.current === 'first' ? 0 : -1);
            focusIntent.current = 'first';
            return;
          }
          // Light dismiss took focus from an item with it: give it back to the button.
          const active = document.activeElement;
          if (active === null || active === document.body || menuRef.current?.contains(active)) {
            buttonRef.current?.focus();
          }
        }}
        onKeyDown={onMenuKeyDown}
        onBlur={(event) => {
          // Focus left the menu (a click elsewhere, the window losing focus). A press on the button itself
          // is left to its popovertarget toggle, which would otherwise reopen the menu just closed here.
          const next = event.relatedTarget;
          if (next !== null && next === buttonRef.current) return;
          if (!(next instanceof Node) || !menuRef.current?.contains(next)) close(false);
        }}
      >
        {RELATED_KIND_ORDER.map((kind, index) => (
          <button
            key={kind}
            ref={(element) => {
              itemRefs.current[index] = element;
            }}
            type="button"
            role="menuitem"
            tabIndex={-1}
            className="related-menu-item"
            onClick={() => choose(kind)}
          >
            <span className="related-menu-label">{RELATED_KIND_LABELS[kind]}</span>
            <span className="related-menu-description">{RELATED_KIND_DESCRIPTIONS[kind]}</span>
          </button>
        ))}
      </div>
      <span className="visually-hidden" role="status">
        {pending !== null ? `Semantic Scholar에서 ${RELATED_KIND_LABELS[pending]} 목록을 가져오는 중입니다.` : ''}
      </span>
    </>
  );
}

/** Korean text per error code of POST /api/discovery/related (.scripts/docs/webui-api.md). */
const RELATED_ERRORS: Record<string, string> = {
  upstream_rate_limited: 'Semantic Scholar가 요청 한도 초과(HTTP 429)로 거절했습니다. 1–2분 뒤 다시 시도하세요.',
  upstream_unavailable: 'Semantic Scholar에 연결하지 못했습니다. 인터넷 연결을 확인하고 잠시 뒤 다시 시도하세요.',
  upstream_timeout: 'Semantic Scholar가 30초 안에 답하지 않아 조회를 멈췄습니다. 잠시 뒤 다시 시도하세요.',
  no_identifier:
    '이 논문에는 Semantic Scholar에서 찾을 식별자(arXiv·DOI·S2)가 없어 조회하지 않았습니다. 논문 기록에 식별자를 넣으면 조회할 수 있습니다.',
  timeout: '서버가 60초 안에 답하지 않았습니다. 상태 화면에서 서버를 확인한 뒤 다시 시도하세요.',
  offline: '로컬 서버에 연결할 수 없습니다. 서버를 실행한 뒤 다시 시도하세요.',
};

/** Codes whose server message names the specific problem; it follows the Korean headline. */
const DETAILED_RELATED_ERRORS: Record<string, string> = {
  not_found: 'Semantic Scholar나 라이브러리에서 이 논문을 찾지 못했습니다.',
  bad_request: '요청이 서버 기준에 맞지 않습니다.',
  cache_unsafe: '탐색 캐시 폴더가 안전하지 않아 결과를 저장하지 않았습니다.',
  write_failed: '받은 목록을 탐색 캐시에 저장하지 못했습니다.',
};

function relatedErrorText(error: ApiError): string {
  const known = RELATED_ERRORS[error.code];
  if (known) return known;
  const detailed = DETAILED_RELATED_ERRORS[error.code];
  return detailed ? `${detailed} ${error.message}` : error.message;
}

/**
 * What a lookup is doing or why it failed, placed by the host near the paper (card notes, reader
 * strip). The wait is announced by RelatedMenu's live region, so the visible line here is not live.
 * A 429 also says how to raise the limit: `S2_API_KEY` in the WebUI server's environment.
 */
export function RelatedNotice({ lookup, className }: { lookup: RelatedLookup; className?: string }) {
  const { pending, failure } = lookup;
  const extra = className ? ` ${className}` : '';
  if (pending) {
    return (
      <p className={`field-hint${extra}`}>
        Semantic Scholar에서 {RELATED_KIND_LABELS[pending]} 목록을 가져오는 중… 최대 30초쯤 걸립니다.
      </p>
    );
  }
  if (!failure) return null;
  const rateLimited = failure.error.code === 'upstream_rate_limited';
  return (
    <div className={`related-error${extra}`} role="alert">
      <p className="related-error-title">
        <CircleAlert aria-hidden="true" />
        {RELATED_KIND_LABELS[failure.kind]} 목록을 가져오지 못했습니다.
      </p>
      <p className="related-error-text">{relatedErrorText(failure.error)}</p>
      {rateLimited ? (
        <p className="related-error-text">
          자주 막히면 WebUI 서버를 실행하는 터미널에서 <code translate="no">S2_API_KEY</code> 환경 변수를 설정하고 서버를
          다시 시작하세요. 키는 서버만 읽으며 WebUI가 저장하거나 브라우저로 보내지 않습니다.
        </p>
      ) : null}
    </div>
  );
}
