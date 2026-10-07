#!/usr/bin/env python3
"""Detect/login/connect the user's CLI, build local views, and launch the UI."""
from __future__ import annotations
import argparse
import json
import hashlib
from urllib.request import urlopen
import shutil
import subprocess
import sys
import webbrowser
from pathlib import Path
import research_agent

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--agent', choices=('auto', 'codex', 'claude'), default=None)
    parser.add_argument('--check', action='store_true', help='read-only diagnosis; no login, writes, or server')
    parser.add_argument('--connect-only', action='store_true')
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    status = research_agent.resolve(ROOT, args.agent)
    if args.check:
        print(json.dumps({**status, 'pdf_reader_ready': bool(shutil.which('pdftotext'))}, ensure_ascii=False, indent=2))
        return 0 if status['ready'] and shutil.which('pdftotext') else 1
    for relative in ('01-Papers/library', '01-Papers/pdfs', '01-Papers/reviews', '05-ideas/thought-experiments'):
        (ROOT / relative).mkdir(parents=True, exist_ok=True)
    state_path = ROOT / 'graphify-out/sync-state.json'
    if not state_path.exists():
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps({'schema_version': '1.0', 'sources': {}}, indent=2))
    for generator in ('paper_catalog_html.py', 'thought_experiments_html.py', 'harness_dashboard.py'):
        cli = [sys.executable, str(ROOT / '.scripts/bin' / generator)]
        if generator == 'harness_dashboard.py': cli.append('--no-tests')
        subprocess.run(cli, cwd=ROOT, check=True)
    if status.get('installed') and not status['authenticated'] and sys.stdin.isatty():
        login = [shutil.which(status['agent']), *(['login'] if status['agent'] == 'codex' else ['auth', 'login'])]
        print('본인 계정으로 로그인하면 연결을 이어갑니다.', flush=True)
        subprocess.run(login, check=False)
    status = research_agent.connect(ROOT, args.agent)
    print(status['reason'])
    if not status['ready']:
        for candidate in status.get('candidates', []):
            print(f"{candidate['agent']}: {candidate['reason']}")
        print('설치·로그인 안내: docs/onboarding.md')
        return 1
    print(f"연결한 에이전트: {status['agent']} · 인증은 본인 CLI의 기존 로그인 사용")
    if args.connect_only:
        return 0
    if not shutil.which('pdftotext'):
        print('PDF 읽기 도구 필요: pdftotext (Poppler). 설치 후 같은 온보딩 명령을 실행하세요.')
        return 1
    import paper_review_bridge as bridge
    import http.server
    try:
        server = http.server.ThreadingHTTPServer(('127.0.0.1', args.port), bridge.Handler)
    except OSError:
        try:
            with urlopen(f'http://127.0.0.1:{args.port}/api/status', timeout=3) as response:
                existing = json.load(response)
            if existing.get('workspace_id') != hashlib.sha256(str(ROOT.resolve()).encode()).hexdigest()[:16]:
                raise ValueError('different workspace')
        except (OSError, ValueError):
            print(f'포트 {args.port}를 다른 프로그램이 사용합니다. --port로 다른 포트를 지정하세요.')
            return 1
        url = f'http://127.0.0.1:{args.port}/100-views/paper-library.html'
        print('이미 실행 중인 이 저장소의 실행기에 연결합니다: ' + url)
        if not args.no_browser: webbrowser.open(url)
        return 0
    server.review_timeout = 3600
    server.agent_status = status
    url = f'http://127.0.0.1:{server.server_port}/100-views/paper-library.html'
    print(url, flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
