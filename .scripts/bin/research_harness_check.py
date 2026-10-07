#!/usr/bin/env python3
"""Check installed harness files and skill entry points without writing anything."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / ".research-harness-manifest.json"


def main() -> int:
    if not MANIFEST.is_file():
        print("FAIL: installation manifest is missing")
        return 1
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"FAIL: invalid installation manifest: {exc}")
        return 1
    skills_root = ROOT / ".agents/skills"
    failures = []
    warnings = []
    skills = sorted(p for p in skills_root.iterdir() if p.is_dir()) if skills_root.is_dir() else []
    for skill in skills:
        if not (skill / "SKILL.md").is_file():
            failures.append(f"missing {skill.relative_to(ROOT)}/SKILL.md")
    for host in manifest.get("hosts", []):
        host_root = ROOT / f".{host}/skills"
        for skill in skills:
            alias = host_root / skill.name
            relative = alias.relative_to(ROOT).as_posix()
            owned = relative in manifest.get("files", {})
            if alias.is_symlink():
                if alias.resolve(strict=False) != skill.resolve():
                    failures.append(f"broken link {alias.relative_to(ROOT)}")
            elif not (alias / "SKILL.md").is_file():
                failures.append(f"missing host skill {alias.relative_to(ROOT)}")
            elif not owned:
                warnings.append(f"preserved, untracked host skill {relative}")
    for path in ("docs/research-harness/README.md", "docs/research-harness/routes.json", ".scripts/bin/install_research_harness.py"):
        if not (ROOT / path).is_file():
            failures.append(f"missing {path}")
    print(f"Skills: {len(skills)} · hosts: {', '.join(manifest.get('hosts', [])) or 'common only'}")
    if failures:
        for failure in failures:
            print(f"FAIL: {failure}")
        return 1
    for warning in warnings:
        print(f"WARN: {warning}")
    print("PASS: installed files and host skill paths are discoverable")
    print("Project test/build commands are intentionally not run; use the target repository's own instructions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
