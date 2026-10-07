"""Shared navigation and hero markup for the local research screens."""
from __future__ import annotations

import html

STYLESHEET = '<link rel="stylesheet" href="assets/research-ui.css">'
PAGES = [('harness', 'harness-dashboard.html', '하네스'),
         ('papers', 'paper-library.html', '논문 라이브러리'),
         ('ideas', 'thought-experiments.html', '사고실험')]


def page_header(active: str, title: str, eyebrow: str, description: str,
                action: str, target: str) -> str:
    parts = []
    for key, path, label in PAGES:
        current = ' aria-current="page"' if key == active else ''
        parts.append(f'<a href="{path}" target="_top"{current}>{label}</a>')
    links = ''.join(parts)
    return f'''<header class="site-header">
<div class="site-nav"><a class="brand" href="harness-dashboard.html"><span class="brand-mark" aria-hidden="true">P</span>PAPER AGENT<span class="brand-caption">RESEARCH WORKSPACE</span></a>
<nav class="desktop-nav" aria-label="주 메뉴">{links}</nav>
<details class="mobile-menu"><summary>메뉴 <span aria-hidden="true">☰</span></summary><nav aria-label="모바일 주 메뉴">{links}</nav></details></div>
<div class="hero"><div class="hero-copy"><p class="eyebrow">{html.escape(eyebrow)}</p><h1>{html.escape(title)}</h1><p class="hero-description">{html.escape(description)}</p><a class="hero-action" href="{html.escape(target, quote=True)}">{html.escape(action)} <span aria-hidden="true">↗</span></a></div><div class="hero-art" aria-hidden="true"><div class="art-note"></div><div class="art-front"><span>READ · THINK · BUILD</span><b>↗</b></div></div></div>
</header>'''
