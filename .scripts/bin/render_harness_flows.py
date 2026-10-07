#!/usr/bin/env python3
"""Export the HTML slides to PNG and PDF; optional presentation tooling only."""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
VIEWS = ROOT / '100-views/harness-flows'
ASSETS = VIEWS / 'assets'


def main():
    ASSETS.mkdir(exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={'width':1600,'height':900}, device_scale_factor=2)
        for source in sorted(VIEWS.glob('0*.html')):
            page.goto(source.as_uri())
            page.evaluate('document.fonts.ready')
            overflow = page.locator('.node').evaluate_all('(nodes)=>nodes.filter(n=>n.scrollHeight>n.clientHeight).map(n=>({title:n.querySelector("h3").innerText,height:n.clientHeight,content:n.scrollHeight}))')
            page.screenshot(path=str(ASSETS / (source.stem+'.png')))
            page.pdf(path=str(ASSETS / (source.stem+'.pdf')),width='1600px',height='900px',print_background=True,prefer_css_page_size=True)
            print(source.name, 'overflow:', overflow)
        browser.close()


if __name__ == '__main__':
    main()
