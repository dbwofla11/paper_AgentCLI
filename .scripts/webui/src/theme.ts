import { useSyncExternalStore } from 'react';

/** `system` follows prefers-color-scheme; `light`/`dark` force it via `data-theme` on <html>. */
export type ThemePreference = 'system' | 'light' | 'dark';

export const THEME_PREFERENCES: readonly ThemePreference[] = ['system', 'light', 'dark'];

/** Same key and colours as public/theme-init.js, which applies a forced theme before first paint. */
const STORAGE_KEY = 'research-webui.theme';
const THEME_COLORS = { light: '#ffffff', dark: '#202124' } as const;

function isPreference(value: unknown): value is ThemePreference {
  return typeof value === 'string' && (THEME_PREFERENCES as readonly string[]).includes(value);
}

function readStored(): ThemePreference {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return isPreference(value) ? value : 'system';
  } catch {
    return 'system';
  }
}

function applyPreference(preference: ThemePreference): void {
  const root = document.documentElement;
  if (preference === 'system') root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', preference);
  // The two theme-color metas carry media queries; a forced theme overrides both.
  for (const meta of document.querySelectorAll<HTMLMetaElement>('meta[name="theme-color"]')) {
    const systemColor = meta.media.includes('dark') ? THEME_COLORS.dark : THEME_COLORS.light;
    meta.content = preference === 'system' ? systemColor : THEME_COLORS[preference];
  }
}

let current: ThemePreference = readStored();
const listeners = new Set<() => void>();

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  // Another tab changed the preference.
  const onStorage = (event: StorageEvent) => {
    if (event.key !== STORAGE_KEY) return;
    current = readStored();
    applyPreference(current);
    listener();
  };
  window.addEventListener('storage', onStorage);
  return () => {
    listeners.delete(listener);
    window.removeEventListener('storage', onStorage);
  };
}

export function setThemePreference(preference: ThemePreference): void {
  current = preference;
  try {
    window.localStorage.setItem(STORAGE_KEY, preference);
  } catch {
    // Storage unavailable (private mode): the choice lasts for this page only.
  }
  applyPreference(preference);
  for (const listener of listeners) listener();
}

export function useThemePreference(): ThemePreference {
  return useSyncExternalStore(subscribe, () => current);
}
