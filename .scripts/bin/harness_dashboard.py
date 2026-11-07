#!/usr/bin/env python3
"""Generate a read-only HTML view of harness state derived from canonical files.

``dashboard_data(root)`` is the single data source: the static page renders from it and the
WebUI serves it as ``GET /api/harness`` (``.scripts/docs/webui-api.md``).
"""
from __future__ import annotations

import fnmatch
import html
import json
import re
import subprocess
import sys
import urllib.parse
from datetime import date
from pathlib import Path
from harness_skill_guide import GUIDE_CSS, MAP_RELATIVE, guide_html, load_paths, skill_data
from research_ui import STYLESHEET, page_header

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "100-views" / "harness-dashboard.html"
SKILLS = ".agents/skills"
SKILL_FILE = "SKILL.md"
PERSONAS = "04-Projects/validation/personas"
OMP_AGENTS = ".omp/agents"
SYNC_STATE = "graphify-out/sync-state.json"
TESTS_PATH = ".scripts/tests/test_harness_tools.py"
CHECKS = [
    ("Harness validator", ".scripts/bin/verify_harness.py"),
    ("Paper JSON validator", ".scripts/bin/paper_record.py"),
    ("Idea analysis validator", ".scripts/bin/idea_analysis.py"),
    ("Graphify sync tracker", ".scripts/bin/graphify_sync.py"),
]
CHECK_LABELS = {"verify": "하네스 구조 검사", "tests": "하네스 테스트"}
HARNESS_CHECKS = [
    {"check": "verify", "label": CHECK_LABELS["verify"], "command": "python3 .scripts/bin/verify_harness.py"},
    {"check": "tests", "label": CHECK_LABELS["tests"], "command": "python3 -m unittest discover -s .scripts/tests"},
]
LINKS = {
    "router": ".scripts/bin/research_workflow.py",
    "harness_graph": "docs/Harness-Graph.md",
    "workflow_map": ".scripts/docs/research-workflow-map.json",
    "graphify_sync": ".scripts/bin/graphify_sync.py",
    "installer_doc": "docs/research-harness-installer.md",
    "installer": ".scripts/bin/install_research_harness.py",
}


def link(path: str) -> str:
    target = (ROOT / path).resolve()
    try:
        return html.escape("../" + target.relative_to(ROOT.resolve()).as_posix())
    except ValueError:
        return "#"


def check_command(check: str, root: Path) -> list[str]:
    """argv of a fixed harness check; run it with ``cwd=root``."""
    if check == "verify":
        return [sys.executable, str(Path(root) / ".scripts/bin/verify_harness.py")]
    if check == "tests":
        return [sys.executable, "-m", "unittest", "discover", "-s", ".scripts/tests"]
    raise ValueError("check must be one of: verify, tests")


def _run_check(check: str) -> tuple[str, str]:
    result = subprocess.run(check_command(check, ROOT), cwd=ROOT, capture_output=True, text=True, check=False)
    message = (result.stdout + result.stderr).strip() or "출력 없음"
    return ("PASS" if result.returncode == 0 else "FAIL", message)


def validate() -> tuple[str, str]:
    return _run_check("verify")


def test_suite() -> tuple[str, str]:
    return _run_check("tests")


REFUSED = "정적 파일 정책 밖 경로라 읽지 않습니다."
FRONTMATTER_MAX_BYTES = 64 * 1024  # an agent description is read from the head of its file only


def _href(root: Path, relative: str) -> str | None:
    """URL of ``relative`` when the WebUI static-file policy (``security.resolve_static``: allowed
    roots, sensitive names, exact case, symlink targets) would serve it, else None."""
    from webui import reviews, security

    url = "/" + urllib.parse.quote(relative)
    served = security.resolve_static(root, url, reviews.ALLOWED_ROOTS, reviews.ALLOWED_ROOT_FILES)
    return url if served is not None else None


def _servable_file(root: Path, relative: str) -> bool:
    """True when ``relative`` is a regular file the static-file policy would serve; repository
    text is read into the payload only then, so the API never shows a file a URL would refuse."""
    if _href(root, relative) is None:
        return False
    try:
        return (root / relative).resolve(strict=True).is_file()
    except (OSError, RuntimeError, ValueError):
        return False


def _plain_file(root: Path, relative: str) -> bool:
    """True when ``relative`` is a regular file at exactly that place under the real ``root``:
    no component is a symlink, so nothing outside the directory can be read through it. Used for
    ``.omp/agents``, which the static-file policy never serves."""
    try:
        real = (root / relative).resolve(strict=True)
        return real == root.resolve(strict=True) / relative and real.is_file()
    except (OSError, RuntimeError, ValueError):
        return False


def _skill_file(root: Path, source: Path) -> bool:
    """True when ``source`` is ``.agents/skills/<name>/SKILL.md`` and that file is a regular file,
    not a symlink, inside a skill directory whose real path is inside the real ``root``.

    Only the ``<name>`` entry may be a symlink: shared skills are installed as directory links
    (e.g. ``-> ../../200-ARIS/upstream/skills/skills-codex/<name>``), whose targets lie outside the
    static-file allow-list. ``.agents`` and ``.agents/skills`` must be real directories, and no
    component of the skill directory's real path may be a sensitive name (``security.SENSITIVE_NAMES``).
    This reads only the file named ``SKILL.md`` into the payload; static serving is unchanged."""
    from webui import security

    try:
        base = root.resolve(strict=True)
        parts = source.relative_to(root).parts
        if parts[:2] != tuple(SKILLS.split("/")) or len(parts) != 4 or parts[3] != SKILL_FILE:
            return False
        if (root / SKILLS).resolve(strict=True) != base / SKILLS:
            return False
        directory = (root / SKILLS / parts[2]).resolve(strict=True)
        if not directory.is_relative_to(base):
            return False
        if any(fnmatch.fnmatchcase(part, pattern) for part in directory.relative_to(base).parts
               for pattern in security.SENSITIVE_NAMES):
            return False
        real = directory / SKILL_FILE
        return not real.is_symlink() and real.is_file()
    except (OSError, RuntimeError, ValueError):
        return False


def _description(root: Path, path: Path) -> str | None:
    if not _plain_file(root, path.relative_to(root).as_posix()):
        return None
    with path.open("rb") as handle:
        text = handle.read(FRONTMATTER_MAX_BYTES).decode("utf-8", errors="replace")
    frontmatter = text.split("---", 2)[1] if text.startswith("---") else ""
    match = re.search(r"^description:\s*(.+)$", frontmatter, re.M)
    return match[1].strip().strip('"\'') if match else None


def _guide(root: Path, errors: list[dict]) -> dict:
    if not _servable_file(root, MAP_RELATIVE):
        raise ValueError(f"{MAP_RELATIVE}: {REFUSED}")
    skills = skill_data(root, readable=lambda source: _skill_file(root, source))
    for skill in skills:
        if skill["instructions"] is None:
            errors.append({"section": "guide", "error": f"{skill['source']}: {REFUSED}"})
    return {"paths": load_paths(root), "skills": skills}


def _routing() -> list[dict]:
    from research_workflow import WORKFLOW
    return [{"stage": stage, "next": route.get("next", ""), "reason": route.get("reason", "")}
            for stage, route in WORKFLOW.items()]


def _skill_links(root: Path) -> list[dict]:
    rows = []
    for skill in sorted(p for p in (root / SKILLS).iterdir() if (p / "SKILL.md").is_file()):
        source = skill / "SKILL.md"
        claude = root / ".claude/skills" / skill.name
        codex = root / ".codex/skills" / skill.name
        claude_ok = claude.is_symlink() and claude.resolve(strict=False) == skill.resolve()
        codex_ok = codex.is_symlink() and codex.resolve(strict=False) == skill.resolve()
        rows.append({"name": skill.name, "source": source.relative_to(root).as_posix(),
                     "source_exists": source.is_file(), "claude": "linked" if claude_ok else "missing",
                     "codex": "linked" if codex_ok else "missing", "omp": "direct" if source.is_file() else "missing"})
    return rows


def _graphify(root: Path) -> dict:
    state = {"path": SYNC_STATE, "exists": False, "total": 0, "by_status": {}, "pending": 0, "error": None}
    path = root / SYNC_STATE
    if not path.exists():
        return state
    state["exists"] = True
    if not _servable_file(root, SYNC_STATE):
        state["error"] = f"{SYNC_STATE}: {REFUSED}"
        return state
    try:
        sources = json.loads(path.read_text(encoding="utf-8")).get("sources", {})
        if not isinstance(sources, dict):
            raise ValueError("sources is not an object")
    except (OSError, ValueError, AttributeError) as exc:
        state["error"] = f"{type(exc).__name__}: {exc}"[:500]
        return state
    counts: dict[str, int] = {}
    for item in sources.values():
        status = item.get("status") if isinstance(item, dict) else None
        key = status if isinstance(status, str) and status else "unknown"
        counts[key] = counts.get(key, 0) + 1
    state.update(total=len(sources), by_status=dict(sorted(counts.items())), pending=counts.get("pending", 0))
    return state


def _hrefs(root: Path, data: dict) -> dict:
    """Server URL of every referenced path, or None when the WebUI would not serve it."""
    paths = [step["source"] for path in data["guide"]["paths"] for step in path.get("steps", [])
             if isinstance(step.get("source"), str)]
    paths += [skill["source"] for skill in data["guide"]["skills"]]
    paths += [row["source"] for row in data["skill_links"]]
    paths += [row["path"] for key in ("omp_agents", "personas", "validators") for row in data[key]]
    paths += [data["tests_path"], data["graphify"]["path"], *data["links"].values()]
    return {path: _href(root, path) for path in paths}


def dashboard_data(root: Path | None = None) -> dict:
    """Harness state under ``root`` (module ``ROOT`` when omitted). A failing section is left
    empty and recorded in ``errors``; this never raises for faulty repository data."""
    root = ROOT if root is None else Path(root)
    errors: list[dict] = []

    def section(name: str, empty, build):
        try:
            return build()
        except Exception as exc:  # data faults are reported per section, never raised
            errors.append({"section": name, "error": f"{type(exc).__name__}: {exc}"[:500]})
            return empty

    data = {
        "guide": section("guide", {"paths": [], "skills": []}, lambda: _guide(root, errors)),
        "routing": section("routing", [], _routing),
        "skill_links": section("skill_links", [], lambda: _skill_links(root)),
        "omp_agents": section("omp_agents", [], lambda: [
            {"name": p.stem, "path": p.relative_to(root).as_posix(), "description": _description(root, p)}
            for p in sorted((root / OMP_AGENTS).glob("*.md"))]),
        "personas": section("personas", [], lambda: [
            {"name": p.stem, "path": p.relative_to(root).as_posix()} for p in sorted((root / PERSONAS).glob("*.md"))]),
        "validators": section("validators", [], lambda: [
            {"name": name, "path": path, "exists": (root / path).is_file()} for name, path in CHECKS]),
        "tests_path": TESTS_PATH,
        "graphify": section("graphify", {"path": SYNC_STATE, "exists": False, "total": 0, "by_status": {},
                                         "pending": 0, "error": None}, lambda: _graphify(root)),
        "checks": [dict(check) for check in HARNESS_CHECKS],
        "links": dict(LINKS),
    }
    data["hrefs"] = section("hrefs", {}, lambda: _hrefs(root, data))
    data["errors"] = errors
    return data


def main(run_tests: bool = True) -> None:
    data = dashboard_data()
    state, message = validate()
    tests, test_message = test_suite() if run_tests else ("미실행", "온보딩은 구조 검사만 실행합니다.")
    failed = {error["section"] for error in data["errors"]}
    route_rows = ('<tr><td colspan="3">라우터 조회 실패</td></tr>' if "routing" in failed else "\n".join(
        f'<tr><td>{html.escape(row["stage"])}</td><td>{html.escape(row["next"])}</td><td>{html.escape(row["reason"])}</td></tr>'
        for row in data["routing"]
    ))
    skill_rows = "\n".join(
        f'<tr><td><a href="{link(row["source"])}">{html.escape(row["name"])}</a></td>'
        f'<td>{"있음" if row["source_exists"] else "누락"}</td><td>{"연결됨" if row["claude"] == "linked" else "미연결"}</td>'
        f'<td>{"연결됨" if row["codex"] == "linked" else "미연결"}</td>'
        f'<td>{"직접 탐색" if row["omp"] == "direct" else "누락"}</td></tr>'
        for row in data["skill_links"]
    ) or '<tr><td colspan="5">스킬 없음</td></tr>'
    validator_rows = "\n".join(
        f'<tr><td>{html.escape(row["name"])}</td><td><a href="{link(row["path"])}">{html.escape(row["path"])}</a></td>'
        f'<td>{"있음" if row["exists"] else "누락"}</td></tr>'
        for row in data["validators"]
    )
    persona_rows = "\n".join(
        f'<tr><td>{html.escape(row["name"])}</td><td><a href="{link(row["path"])}">열기</a></td></tr>'
        for row in data["personas"]
    ) or '<tr><td colspan="2">필수 페르소나 없음</td></tr>'
    agent_rows = "\n".join(
        f'<tr><td>{html.escape(row["name"])}</td><td><a href="{link(row["path"])}">열기</a></td></tr>'
        for row in data["omp_agents"]
    ) or '<tr><td colspan="2">omp 에이전트 없음</td></tr>'
    sync = data["graphify"]
    sync_summary = (f"동기화 기록을 읽지 못했습니다: {sync['error']}" if sync["error"]
                    else f"기록 {sync['total']}건 · pending {sync['pending']}건")
    document = f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>연구 하네스 대시보드</title><style>
{GUIDE_CSS}
body{{font:15px system-ui,sans-serif;margin:0;background:#f3f6f2;color:#1c2d24}}header{{background:#173c32;color:white;padding:26px max(20px,calc((100vw - 1050px)/2))}}main{{max-width:1050px;margin:24px auto;padding:0 18px 50px}}section{{background:white;border:1px solid #dce5dd;border-radius:12px;padding:18px 20px;margin:12px 0}}h1{{margin:0}}h2{{font-size:18px;margin:0 0 12px}}table{{width:100%;border-collapse:collapse}}td,th{{padding:8px;border-bottom:1px solid #edf0ed;text-align:left}}th{{font-size:12px;color:#64716a}}a{{color:#256c4b}}.state{{font-weight:700;color:{'#237346' if state == 'PASS' else '#a33'}}}code{{background:#edf2ed;padding:2px 5px;border-radius:4px}}nav a{{margin-right:14px}}</style>
{STYLESHEET}</head><body class="harness-page">
{page_header('harness', '연구를 연결하는 하네스', 'SKILLS & WORKFLOWS', '어떤 스킬을 쓰고, 어떤 순서로 진행할까요? 논문 읽기부터 아이디어 검증까지 한곳에서 살펴보세요.', '스킬 흐름 살펴보기', '#skill-guide')}<main>
{guide_html(data["guide"])}
<section><h2>하네스 구조 검사: <span class="state">{state}</span></h2><p>{html.escape(message)}</p><p>검증 재실행: <code>python3 .scripts/bin/verify_harness.py</code> · 대시보드 갱신: <code>python3 .scripts/bin/harness_dashboard.py</code></p></section>
<section><h2>현재 라우팅</h2><p>세션 전역의 현재 단계는 따로 저장하지 않습니다. 각 요청이 선언한 단계를 아래 라우터로 연결합니다. 라우터 정본: <a href="{link(LINKS['router'])}">research_workflow.py</a> · <a href="{link(LINKS['harness_graph'])}">Harness-Graph.md</a></p><div class="table-scroll"><table><thead><tr><th>요청 단계</th><th>다음 스킬</th><th>라우팅 이유</th></tr></thead><tbody>{route_rows}</tbody></table></div></section>
<section><h2>공통 스킬 정본 및 호스트 연결</h2><p>Codex와 omp는 .agents/skills 정본을 직접 탐색합니다. Codex 호환 미러의 미연결은 스킬 사용 불가를 뜻하지 않습니다.</p><div class="table-scroll"><table><thead><tr><th>스킬</th><th>.agents 정본</th><th>Claude 연결</th><th>Codex 호환 미러</th><th>omp</th></tr></thead><tbody>{skill_rows}</tbody></table></div></section>
<section><h2>omp 에이전트</h2><div class="table-scroll"><table><thead><tr><th>에이전트</th><th>정의</th></tr></thead><tbody>{agent_rows}</tbody></table></div></section>
<section><h2>페르소나</h2><div class="table-scroll"><table><tbody>{persona_rows}</tbody></table></div></section>
<section><h2>검증기와 테스트</h2><p>정적 하네스 검사: <b>{state}</b> — {html.escape(message)}</p><p>테스트 실행: <b>{tests}</b></p><details><summary>실행 기록 보기</summary><pre>{html.escape(test_message)}</pre></details><div class="table-scroll"><table><tbody>{validator_rows}</tbody></table></div><p><a href="{link(data['tests_path'])}">테스트 코드</a></p></section>
<section><h2>Graphify 동기화</h2><p>{html.escape(sync_summary)}</p><p><code>{html.escape(sync['path'])}</code> (로컬 생성 기록) · <a href="{link(LINKS['graphify_sync'])}">상태 명령</a></p></section>
<section><h2>관리 범위</h2><p>이 HTML은 읽기 전용이다. 파일 수정이나 검증 실행은 로컬 터미널에서 위 명령을 실행해야 한다. 정적 페이지가 셸 명령을 호출하지 않는다.</p><p><a href="{link(LINKS['installer_doc'])}">온보딩 도구 안내</a> · <a href="{link(LINKS['installer'])}">설치기</a></p></section></main><footer class="page-footer"><p>논문을 읽고, 근거를 연결하고, 다음 연구를 설계하세요.</p><div class="footer-wordmark" aria-hidden="true">PAPER AGENT</div></footer></body></html>'''
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(document, encoding="utf-8")
    print(f"Generated {OUTPUT.relative_to(ROOT)}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-tests", action="store_true")
    args = parser.parse_args()
    main(run_tests=not args.no_tests)
