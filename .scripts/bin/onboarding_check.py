#!/usr/bin/env python3
"""Read-only first-run checks; no installs, network calls, or credential output."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILLS = ("paper-search", "paper-review", "review-index", "graphify", "concept-note")
FILES = ("AGENTS.md", "README.md", "docs/onboarding.md", ".scripts/bin/paper.py",
         ".scripts/bin/research_workflow.py", ".scripts/bin/verify_harness.py",
         "90-Templates/paper/review-template.md", ".codex/config.toml", ".mcp.json")


def check(root: Path, host: str, with_mcp: bool = False,
          with_graphify: bool = False) -> list[tuple[str, str]]:
    results = []

    def report(ok: bool, message: str, optional: bool = False) -> None:
        results.append(("PASS" if ok else "WARN" if optional else "FAIL", message))

    report(sys.version_info >= (3, 10), "Python 3.10 이상")
    for command in ("git", host):
        report(shutil.which(command) is not None, f"PATH에서 {command} 실행 파일 탐색")
    portable_profile = (root / "docs/research-harness/profile.json").is_file()
    for relative in FILES + (("CLAUDE.md",) if host == "claude" else ()):
        optional = portable_profile and relative in {".codex/config.toml", ".mcp.json"} and not with_mcp
        report((root / relative).is_file(), f"저장소 파일: {relative}", optional=optional)
    skills_root = root / ".agents/skills"
    names = sorted({*SKILLS, *(p.name for p in skills_root.iterdir()
                              if p.is_dir() or p.is_symlink())}) if skills_root.is_dir() else list(SKILLS)
    for name in names:
        report((skills_root / name / "SKILL.md").is_file(), f"공통 스킬: {name}")
        if host == "claude":
            alias = root / ".claude/skills" / name
            report((alias / "SKILL.md").is_file(), f"Claude 스킬 진입점: {name}")
            if alias.is_symlink():
                report(alias.resolve() == (skills_root / name).resolve(), f"Claude 링크 대상: {name}")
    config = root / ".codex/config.toml"
    if config.is_file():
        content = config.read_text(encoding="utf-8")
        report(not re.search(r'/(?:home|Users)/|["\s][A-Za-z]:[\\/]', content),
               "Codex 설정에 개인 컴퓨터 절대 경로 없음")
        if host == "codex" and 'command = "npx"' in content:
            report(shutil.which("npx") is not None, "llmwiki 실행용 npx", optional=not with_mcp)
    mcp = root / ".mcp.json"
    if mcp.is_file():
        try:
            data = json.loads(mcp.read_text(encoding="utf-8"))
            report(isinstance(data, dict) and isinstance(data.get("mcpServers"), dict), "MCP JSON 구조")
        except (OSError, ValueError):
            report(False, "MCP JSON 읽기/구문 오류")
    report(shutil.which("uvx") is not None, "MCP 실행용 uvx", optional=not with_mcp)
    report(shutil.which("graphify") is not None, "관계 그래프용 graphify", optional=not with_graphify)
    report(bool(os.environ.get("EXA_API_KEY")), "선택 검색용 EXA_API_KEY 환경변수 설정 여부", optional=True)
    results.append(("INFO", "로그인·모델 응답·MCP 연결·PDF 페이지 읽기는 에이전트 안에서 별도 확인하세요."))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", choices=("codex", "claude"), default="codex")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--with-mcp", action="store_true")
    parser.add_argument("--with-graphify", action="store_true")
    args = parser.parse_args()
    results = check(args.root.resolve(), args.host, args.with_mcp, args.with_graphify)
    for status, message in results:
        print(f"{status}: {message}")
    failures = sum(status == "FAIL" for status, _ in results)
    print(f"필수 검사 실패: {failures} · 안내: docs/onboarding.md")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
