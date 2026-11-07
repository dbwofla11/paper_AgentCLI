#!/usr/bin/env python3
"""Check first-run prerequisites without installing tools or revealing credentials."""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from harness_common import ROOT, local_settings

SKILLS = ("paper-search", "paper-review", "review-index", "graphify", "concept-note")
FILES = ("AGENTS.md", "docs/Home.md", "README.md", "docs/onboarding.md", ".scripts/bin/paper.py",
         ".scripts/bin/research_workflow.py", ".scripts/bin/verify_harness.py",
         "90-Templates/paper/review-template.md", "90-Templates/paper/triage-template.md",
         ".codex/config.toml", ".mcp.json")
DIRECTORIES = ("00-Inbox", *(f"01-Papers/{kind}/{category}" for kind in ("pdfs", "reviews")
               for category in ("wifi-csi", "game-ai", "agent-ai", "computer-vision", "other")),
               "01-Papers/triage", "01-Papers/library", "02-Concepts", "03-Trends/daily",
               "04-Projects", "05-Ideas/thought-experiments", "99-Attachments")
# Review method figures use the user-level diagram-design skill and the repository marker.
HOST_SKILL_DIRS = {"omp": ".omp/agent/skills", "claude": ".claude/skills", "codex": ".codex/skills"}
DIAGRAM_MARKER = re.compile(r"[ \t]*profile:[ \t]*([a-z0-9][a-z0-9-]{0,63})[ \t]*\n?")


def diagram_design_checks(root: Path, host: str | None) -> list[tuple[bool, str]]:
    """Optional readiness of the method-figure toolchain: host skill, marker grammar, profile."""
    home = Path.home()
    hosts = [host] if host in HOST_SKILL_DIRS else list(HOST_SKILL_DIRS)
    skill_paths = [home / HOST_SKILL_DIRS[name] / "diagram-design/SKILL.md" for name in hosts]
    shown = ", ".join(f"~/{HOST_SKILL_DIRS[name]}/diagram-design" for name in hosts)
    results = [(any(path.is_file() for path in skill_paths),
                f"방법 구조도용 diagram-design 스킬: {shown}")]
    marker = root / ".diagram-design"
    try:
        match = DIAGRAM_MARKER.fullmatch(marker.read_text(encoding="utf-8")) if marker.is_file() else None
    except (OSError, UnicodeError):
        match = None
    results.append((match is not None, "diagram-design 마커 .diagram-design 문법(profile: <slug> 한 줄)"))
    if match:
        slug = match.group(1)
        results.append(((home / ".diagram-design/profiles" / f"{slug}.md").is_file(),
                        f"diagram-design 프로필: ~/.diagram-design/profiles/{slug}.md"))
    else:
        results.append((False, "diagram-design 프로필: 유효한 마커가 없어 확인하지 못함"))
    return results


def check(root: Path, host: str | None, with_mcp: bool = False,
          with_graphify: bool = False, create_dirs: bool = False) -> list[tuple[str, str]]:
    results = []

    def report(ok: bool, message: str, optional: bool = False) -> None:
        results.append(("PASS" if ok else "WARN" if optional else "FAIL", message))

    report(sys.version_info >= (3, 10), "Python 3.10 이상")
    for command in ("git", "uv", "pdftotext", "pdfinfo", "pdftoppm"):
        report(shutil.which(command) is not None, f"PATH에서 {command} 실행 파일 탐색")
    if host:
        report(shutil.which(host) is not None, f"PATH에서 {host} 실행 파일 탐색")
    else:
        report(False, "에이전트 CLI가 없습니다. codex, claude 또는 omp를 설치하세요.")
    if shutil.which("uv"):
        try:
            result = subprocess.run(["uv", "--version"], capture_output=True, text=True, timeout=15, check=False)
            report(result.returncode == 0, "uv 버전 조회")
        except (OSError, subprocess.SubprocessError):
            report(False, "uv 버전 조회")
    if shutil.which("git"):
        try:
            result = subprocess.run(["git", "-C", str(root), "status", "--porcelain"], capture_output=True, timeout=15, check=False)
            report(result.returncode == 0, "Git 저장소 접근")
        except (OSError, subprocess.SubprocessError):
            report(False, "Git 저장소 접근")
    portable = (root / "docs/research-harness/profile.json").is_file()
    for relative in FILES + (("CLAUDE.md",) if host == "claude" else ()):
        optional = portable and relative in {"docs/Home.md", ".codex/config.toml", ".mcp.json"} and not with_mcp
        report((root / relative).is_file(), f"저장소 파일: {relative}", optional=optional)
    for relative in DIRECTORIES:
        directory = root / relative
        if create_dirs:
            try:
                directory.mkdir(parents=True, exist_ok=True)
            except OSError:
                pass
        report(directory.is_dir(), f"작업 디렉터리: {relative}")
    try:
        ast.parse((root / ".scripts/bin/paper.py").read_text(encoding="utf-8"))
        report(True, "paper.py 구문")
    except (OSError, SyntaxError, UnicodeError):
        report(False, "paper.py 구문")
    skills_root = root / ".agents/skills"
    names = sorted({*SKILLS, *(p.name for p in skills_root.iterdir() if (p / "SKILL.md").is_file())}) if skills_root.is_dir() else list(SKILLS)
    for name in names:
        report((skills_root / name / "SKILL.md").is_file(), f"공통 스킬: {name}")
        if host == "claude" and name in SKILLS:
            alias = root / ".claude/skills" / name
            report((alias / "SKILL.md").is_file(), f"Claude 스킬 진입점: {name}")
            if alias.is_symlink():
                report(alias.resolve() == (skills_root / name).resolve(), f"Claude 링크 대상: {name}")
    config = root / ".codex/config.toml"
    if config.is_file():
        content = config.read_text(encoding="utf-8")
        report(not re.search(r'/(?:home|Users)/|["\s][A-Za-z]:[\\/]', content), "Codex 설정에 개인 컴퓨터 절대 경로 없음")
        if host == "codex":
            for server in ("arxiv-mcp", "exa", "paper-search-mcp"):
                report(bool(re.search(r'^\s*\[mcp_servers\.' + re.escape(server) + r'\]\s*$', content, re.MULTILINE)), f"Codex MCP 설정: {server}")
    mcp = root / ".mcp.json"
    if mcp.is_file():
        try:
            data = json.loads(mcp.read_text(encoding="utf-8"))
            report(isinstance(data, dict) and isinstance(data.get("mcpServers"), dict), "MCP JSON 구조")
        except (OSError, ValueError):
            report(False, "MCP JSON 읽기/구문 오류")
    if host == "omp":
        report((root / ".omp/agents").is_dir(), "omp 에이전트 디렉터리")
        if (root / ".omp/config.yml").exists():
            try:
                result = subprocess.run(["git", "-C", str(root), "check-ignore", "-q", ".omp/config.yml"], timeout=15, check=False)
                report(result.returncode == 0, "개인 omp 설정 Git 제외")
            except (OSError, subprocess.SubprocessError):
                report(False, "개인 omp 설정 Git 제외")
    report(shutil.which("uvx") is not None, "MCP 실행용 uvx", optional=not with_mcp)
    report(shutil.which("graphify") is not None, "관계 그래프용 graphify", optional=not with_graphify)
    for ok, message in diagram_design_checks(root, host):
        report(ok, message, optional=True)
    report(bool(os.environ.get("EXA_API_KEY", "").strip()), "선택 검색용 EXA_API_KEY 환경변수 설정 여부", optional=True)
    results.append(("INFO", "로그인·모델 응답·MCP 연결·PDF 페이지 읽기는 에이전트 안에서 별도 확인하세요."))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("codex", "claude", "omp"))
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--with-mcp", action="store_true")
    parser.add_argument("--with-graphify", action="store_true")
    parser.add_argument("--create-dirs", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    host = args.host
    if host:
        selection = f"호스트 {host}: --host 옵션으로 지정"
    else:
        configured = local_settings(root).get("agent")
        if configured in ("codex", "claude", "omp"):
            host = configured
            selection = f"호스트 {host}: 개인 에이전트 설정에서 선택"
        else:
            host = next((name for name in ("codex", "claude", "omp") if shutil.which(name)), None)
            selection = f"호스트 {host}: PATH에서 첫 번째로 발견" if host else "호스트 미선택: 설치된 CLI가 없음"
    results = [("INFO", selection), *check(root, host, args.with_mcp, args.with_graphify, args.create_dirs)]
    failures = sum(status == "FAIL" for status, _ in results)
    if args.json:
        print(json.dumps({"results": [{"status": status, "message": message} for status, message in results], "failures": failures}, ensure_ascii=False, indent=2))
    else:
        for status, message in results:
            print(f"{status}: {message}")
        print(f"필수 검사 실패: {failures} · 안내: docs/onboarding.md")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
