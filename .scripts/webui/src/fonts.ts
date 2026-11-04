// Self-hosted variable fonts (OFL), weight axis only, split into unicode-range chunks so the
// browser downloads only the chunks a page uses. Family names in tokens.css: "Roboto Variable",
// "JetBrains Mono Variable". Hangul falls back to system fonts (a bundled Korean font measured
// 3.5 MB of chunks, over the 3 MB build budget).
import '@fontsource-variable/roboto/wght.css';
import '@fontsource-variable/jetbrains-mono/wght.css';
