#!/usr/bin/env python3
"""Generate a read-only HTML view of harness state derived from canonical files."""
from __future__ import annotations

import html
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from harness_skill_guide import GUIDE_CSS, guide_html
from research_ui import STYLESHEET, page_header

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "100-views" / "harness-dashboard.html"
SKILLS = ROOT / ".agents/skills"
PERSONAS = ROOT / "04-Projects/validation/personas"
CHECKS = [
    ("Harness validator", ".scripts/bin/verify_harness.py"),
    ("Paper JSON validator", ".scripts/bin/paper_record.py"),
    ("Idea analysis validator", ".scripts/bin/idea_analysis.py"),
    ("Graphify sync tracker", ".scripts/bin/graphify_sync.py"),
]


def link(path: str) -> str:
    target = (ROOT / path).resolve()
    try:
        return html.escape("../" + target.relative_to(ROOT.resolve()).as_posix())
    except ValueError:
        return "#"


def validate() -> tuple[str, str]:
    result = subprocess.run(
        [sys.executable, str(ROOT / ".scripts/bin/verify_harness.py")],
        capture_output=True, text=True, check=False,
    )
    message = (result.stdout + result.stderr).strip() or "출력 없음"
    return ("PASS" if result.returncode == 0 else "FAIL", message)


def test_suite() -> tuple[str, str]:
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", ".scripts/tests"],
        cwd=ROOT, capture_output=True, text=True, check=False,
    )
    message = (result.stdout + result.stderr).strip() or "출력 없음"
    return ("PASS" if result.returncode == 0 else "FAIL", message)


def route_rows() -> str:
    result = subprocess.run(
        [sys.executable, str(ROOT / ".scripts/bin/research_workflow.py"), "--json"],
        capture_output=True, text=True, check=False,
    )
    if result.returncode:
        return '<tr><td colspan="3">라우터 조회 실패</td></tr>'
    stages = json.loads(result.stdout).get("stages", {})
    return "\n".join(
        f'<tr><td>{html.escape(stage)}</td><td>{html.escape(route.get("next", ""))}</td><td>{html.escape(route.get("reason", ""))}</td></tr>'
        for stage, route in stages.items()
    )


def skill_rows() -> str:
    rows = []
    for skill in sorted(p for p in SKILLS.iterdir() if p.is_dir()):
        source = skill / "SKILL.md"
        claude = ROOT / ".claude/skills" / skill.name
        codex = ROOT / ".codex/skills" / skill.name
        expected_codex = codex.is_symlink() and codex.resolve(strict=False) == skill.resolve()
        claude_ok = claude.is_symlink() and claude.resolve(strict=False) == skill.resolve()
        rows.append(
            f'<tr><td><a href="{link(source.relative_to(ROOT).as_posix())}">{html.escape(skill.name)}</a></td>'
            f'<td>{"있음" if source.is_file() else "누락"}</td><td>{"연결됨" if claude_ok else "미연결"}</td>'
            f'<td>{"연결됨" if expected_codex else "미연결"}</td></tr>'
        )
    return "\n".join(rows) or '<tr><td colspan="4">스킬 없음</td></tr>'


def main(run_tests: bool = True) -> None:
    state, message = validate()
    tests, test_message = test_suite() if run_tests else ("미실행", "온보딩은 구조 검사만 실행합니다.")
    validator_rows = "\n".join(
        f'<tr><td>{html.escape(name)}</td><td><a href="{link(path)}">{html.escape(path)}</a></td>'
        f'<td>{"있음" if (ROOT / path).is_file() else "누락"}</td></tr>'
        for name, path in CHECKS
    )
    persona_rows = "\n".join(
        f'<tr><td>{html.escape(p.stem)}</td><td><a href="{link(p.relative_to(ROOT).as_posix())}">열기</a></td></tr>'
        for p in sorted(PERSONAS.glob("*.md"))
    ) or '<tr><td colspan="2">필수 페르소나 없음</td></tr>'
    sync_path = ROOT / "graphify-out/sync-state.json"
    sync_state = json.loads(sync_path.read_text(encoding="utf-8")) if sync_path.exists() else {"sources": {}}
    pending = sum(1 for item in sync_state.get("sources", {}).values() if item.get("status") == "pending")
    sync_summary = f"기록 {len(sync_state.get('sources', {}))}건 · pending {pending}건"
    document = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>연구 하네스 대시보드</title><style>
{GUIDE_CSS}
body{{font:15px system-ui,sans-serif;margin:0;background:#f3f6f2;color:#1c2d24}}header{{background:#173c32;color:white;padding:26px max(20px,calc((100vw - 1050px)/2))}}main{{max-width:1050px;margin:24px auto;padding:0 18px 50px}}section{{background:white;border:1px solid #dce5dd;border-radius:12px;padding:18px 20px;margin:12px 0}}h1{{margin:0}}h2{{font-size:18px;margin:0 0 12px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:8px;border-bottom:1px solid #edf0ed;text-align:left}}th{{font-size:12px;color:#64716a}}a{{color:#256c4b}}.state{{font-weight:700;color:{'#237346' if state == 'PASS' else '#a33'}}}code{{background:#edf2ed;padding:2px 5px;border-radius:4px}}nav a{{margin-right:14px}}</style>
{STYLESHEET}</head><body class="harness-page">
{page_header('harness', '연구를 연결하는 하네스', 'SKILLS & WORKFLOWS', '어떤 스킬을 쓰고, 어떤 순서로 진행할까요? 논문 읽기부터 아이디어 검증까지 한곳에서 살펴보세요.', '스킬 흐름 살펴보기', '#skill-guide')}<main>
{guide_html()}
<section><h2>하네스 구조 검사: <span class="state">{state}</span></h2><p>{html.escape(message)}</p><p>검증 재실행: <code>python3 .scripts/bin/verify_harness.py</code> · 대시보드 갱신: <code>python3 .scripts/bin/harness_dashboard.py</code></p></section>
<section><h2>현재 라우팅</h2><p>세션 전역의 현재 단계는 따로 저장하지 않습니다. 각 요청이 선언한 단계를 아래 라우터로 연결합니다. 라우터 정본: <a href="{link('.scripts/bin/research_workflow.py')}">research_workflow.py</a> · <a href="{link('docs/Harness-Graph.md')}">Harness-Graph.md</a></p><div class="table-scroll"><table><thead><tr><th>요청 단계</th><th>다음 스킬</th><th>라우팅 이유</th></tr></thead><tbody>{route_rows()}</tbody></table></div></section>
<section><h2>공통 스킬 정본 및 호스트 연결</h2><p>Codex는 .agents/skills 정본을 직접 탐색합니다. Codex 호환 미러의 미연결은 스킬 사용 불가를 뜻하지 않습니다.</p><div class="table-scroll"><table><thead><tr><th>스킬</th><th>.agents 정본</th><th>Claude 연결</th><th>Codex 호환 미러</th></tr></thead><tbody>{skill_rows()}</tbody></table></div></section>
<section><h2>페르소나</h2><div class="table-scroll"><table><tbody>{persona_rows}</tbody></table></div></section>
<section><h2>검증기와 테스트</h2><p>정적 하네스 검사: <b>{state}</b> — {html.escape(message)}</p><p>테스트 실행: <b>{tests}</b></p><details><summary>실행 기록 보기</summary><pre>{html.escape(test_message)}</pre></details><div class="table-scroll"><table><tbody>{validator_rows}</tbody></table></div><p><a href="{link('.scripts/tests/test_harness_tools.py')}">테스트 코드</a></p></section>
<section><h2>Graphify 동기화</h2><p>{html.escape(sync_summary)}</p><p><code>graphify-out/sync-state.json</code> (로컬 생성 기록) · <a href="{link('.scripts/bin/graphify_sync.py')}">상태 명령</a></p></section>
<section><h2>관리 범위</h2><p>이 HTML은 읽기 전용이다. 파일 수정이나 검증 실행은 로컬 터미널에서 위 명령을 실행해야 한다. 정적 페이지가 셸 명령을 호출하지 않는다.</p><p><a href="{link('docs/research-harness-installer.md')}">온보딩 도구 안내</a> · <a href="{link('.scripts/bin/install_research_harness.py')}">설치기</a></p></section></main><footer class="page-footer"><p>논문을 읽고, 근거를 연결하고, 다음 연구를 설계하세요.</p><div class="footer-wordmark" aria-hidden="true">PAPER AGENT</div></footer></body></html>'''
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(document, encoding="utf-8")
    print(f"Generated {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-tests", action="store_true")
    args = parser.parse_args()
    main(run_tests=not args.no_tests)
