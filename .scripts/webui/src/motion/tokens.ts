/**
 * Motion values shared by motion components. Mirrors the CSS pairs in src/styles/tokens.css:
 * EASE_OUT ↔ --ease-out, EASE_STANDARD ↔ --ease-standard, DUR_FAST ↔ --dur-fast,
 * DUR_BASE ↔ --dur-base, DUR_ENTER ↔ --dur-enter, STAGGER ↔ --stagger. Durations are seconds.
 */
export const EASE_OUT = [0.05, 0.7, 0.1, 1] as const;
export const EASE_STANDARD = [0.2, 0, 0, 1] as const;

export const DUR_FAST = 0.2;
export const DUR_BASE = 0.28;
export const DUR_ENTER = 0.42;
export const STAGGER = 0.08;

/** Paper-card filter changes: opacity only. */
export const DUR_FILTER = 0.16;
/** Nav/side-tab indicator (layoutId) and step-detail crossfade. */
export const DUR_INDICATOR = 0.24;

/** Delay of the `index`-th item in a staggered entrance, capped so long lists finish quickly. */
export function staggerDelay(index: number, cap: number): number {
  return STAGGER * Math.min(Math.max(index, 0), cap);
}

/** Entrance used by stat tiles, harness sections and first-mount cards: fade + y 16 → 0. */
export const ENTER_FROM = { opacity: 0, y: 16 } as const;
export const ENTER_TO = { opacity: 1, y: 0 } as const;

export function enterTransition(index = 0, cap = 11) {
  return { duration: DUR_ENTER, ease: EASE_OUT, delay: staggerDelay(index, cap) };
}
