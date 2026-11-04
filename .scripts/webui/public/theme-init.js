// Applies a forced theme before first paint (loaded with a blocking <script src> in <head>; the CSP
// forbids inline scripts). "system" (or nothing stored) leaves the prefers-color-scheme rules in
// charge. Keep the key and colours in sync with src/theme.ts.
(function () {
  var KEY = 'research-webui.theme';
  var COLORS = { light: '#ffffff', dark: '#202124' };
  var preference = null;
  try {
    preference = window.localStorage.getItem(KEY);
  } catch (error) {
    return;
  }
  if (preference !== 'light' && preference !== 'dark') return;
  document.documentElement.setAttribute('data-theme', preference);
  var metas = document.querySelectorAll('meta[name="theme-color"]');
  for (var index = 0; index < metas.length; index += 1) metas[index].setAttribute('content', COLORS[preference]);
})();
