#!/usr/bin/env python3
"""Fast structural checks for the local research harness; no network or writes."""
from __future__ import annotations

import subprocess
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REQUIRED = [
    ROOT / "docs/Harness-Graph.md",
    ROOT / "docs/Skill-Catalog.md",
    ROOT / "03-Trends/daily/README.md",
    ROOT / "04-Projects/validation/idea-review-persona.md",
    ROOT / "04-Projects/validation/paper-draft-logic-review.md",
    ROOT / ".scripts/bin/research_workflow.py",
    ROOT / ".scripts/bin/paper_record.py",
    ROOT / ".scripts/bin/idea_analysis.py",
    ROOT / ".scripts/bin/graphify_sync.py",
    ROOT / ".scripts/bin/harness_dashboard.py",
    ROOT / ".scripts/bin/harness_skill_guide.py",
    ROOT / ".scripts/bin/research_ui.py",
    ROOT / "100-views/assets/research-ui.css",
    ROOT / ".scripts/docs/research-workflow-map.json",
    ROOT / ".scripts/bin/thought_experiments_html.py",
    ROOT / ".scripts/bin/install_research_harness.py",
    ROOT / ".scripts/bin/research_harness_check.py",
    ROOT / ".scripts/bin/research_todo.py",
    ROOT / ".scripts/docs/paper-record.schema.json",
    ROOT / ".scripts/docs/idea-analysis.schema.json",
    ROOT / ".scripts/docs/research-todo.schema.json",
    ROOT / ".scripts/docs/literature-investigation.schema.json",
    ROOT / "100-views/paper-library.html",
    ROOT / "100-views/harness-dashboard.html",
    ROOT / "100-views/thought-experiments.html",
    ROOT / "04-Projects/validation/critic-output.schema.json",
    ROOT / "04-Projects/validation/personas/method-critic.md",
    ROOT / "04-Projects/validation/personas/repro-critic.md",
    ROOT / "04-Projects/validation/personas/novelty-critic.md",
    ROOT / "00-Inbox/concept-candidate-template.md",
]
CORE_SKILLS = (
    "paper-search", "paper-review", "review-index", "related-work",
    "paper-relations", "critical-validation", "thought-experiment-runner", "concept-note",
    "daily-digest-loop", "graphify",
)


def fail(message: str) -> int:
    print(f"FAIL: {message}")
    return 1


def main() -> int:
    for path in REQUIRED:
        if not path.is_file():
            return fail(f"missing {path.relative_to(ROOT)}")
    daily = (ROOT / "03-Trends/daily/README.md").read_text(encoding="utf-8")
    if "03-Trends/daily/" not in daily or "notes/trends/" not in daily:
        return fail("daily contract lacks canonical and legacy-path rules")
    catalog = (ROOT / "docs/Skill-Catalog.md").read_text(encoding="utf-8")
    if "보기 전용" not in catalog:
        return fail("catalog is not explicitly read-only")
    workflow = ROOT / ".scripts/bin/research_workflow.py"
    paths = json.loads((ROOT / ".scripts/docs/research-workflow-map.json").read_text(encoding="utf-8"))["paths"]
    if len({path["id"] for path in paths}) != len(paths):
        return fail("duplicate workflow path id")
    for path in paths:
        if not path.get("steps"):
            return fail(f"empty workflow path {path['id']}")
        for step in path["steps"]:
            source = f".agents/skills/{step['skill']}/SKILL.md" if step.get("skill") else step.get("source")
            if source and not (ROOT / source).is_file():
                return fail(f"workflow step references a missing source: {source}")
    for skill in CORE_SKILLS:
        if not (ROOT / ".agents/skills" / skill / "SKILL.md").is_file():
            return fail(f"missing installed skill {skill}")
    canonical_skills = ROOT / ".agents/skills"
    claude_skills = ROOT / ".claude/skills"
    for source in sorted(path for path in canonical_skills.iterdir() if path.is_dir()):
        alias = claude_skills / source.name
        if not alias.is_symlink() or alias.resolve(strict=False) != source.resolve():
            return fail(f"Claude skill {source.name} must symlink to .agents/skills")
    for alias in claude_skills.iterdir():
        if alias.name not in {path.name for path in canonical_skills.iterdir() if path.is_dir()} and alias.name != "math-derivation":
            return fail(f"unexpected Claude-only skill {alias.name}; keep shared skills in .agents/skills")
    codex_graphify = ROOT / ".codex/skills/graphify"
    if not codex_graphify.is_symlink() or codex_graphify.resolve(strict=False) != (canonical_skills / "graphify").resolve():
        return fail(".codex/skills/graphify must symlink to the canonical .agents skill")
    daily_skill = (ROOT / ".agents/skills/daily-digest-loop/SKILL.md").read_text(encoding="utf-8")
    for required_text in ("multimodal", "09:00 KST", "채팅으로만", "학회"):
        if required_text not in daily_skill:
            return fail(f"daily paper workflow is missing {required_text!r}")
    if "git push origin master" in daily_skill or "시사이슈 3건" in daily_skill:
        return fail("daily paper candidate flow contains legacy digest side effects")
    expected = {
        "upload": "paper-search",
        "collect": "paper-search",
        "daily": "daily-digest-loop",
        "review": "review-index",
        "idea": "critical-validation",
        "experiment": "thought-experiment-runner",
        "visualize": "graphify",
        "study-note": "concept-note",
        "concept-note": "concept-note",
    }
    for stage in expected:
        result = subprocess.run([sys.executable, str(workflow), stage, "--json"], check=False, capture_output=True, text=True)
        if result.returncode != 0 or f'"next": "{expected[stage]}"' not in result.stdout:
            return fail(f"workflow router failed for {stage}")
    review_skill = (ROOT / ".agents/skills/paper-review/SKILL.md").read_text(encoding="utf-8")
    if "concept-candidates/" not in review_skill or "02-Concepts/" not in review_skill or "graphify_sync.py" not in review_skill:
        return fail("paper review must create Inbox-only concept candidates and sync canonical data to Graphify")
    critical_skill = (ROOT / ".agents/skills/critical-validation/SKILL.md").read_text(encoding="utf-8")
    for required_text in ("최소 2개", "evidence-bundle-vN", "method-critic.md", "idea_analysis.py"):
        if required_text not in critical_skill:
            return fail(f"critical-validation flow is missing {required_text!r}")
    ignore = (ROOT / ".graphifyignore").read_text(encoding="utf-8")
    for excluded in ("concept-candidates/", "critique-method.md", "analysis.json", "evidence-bundle-v*.json"):
        if excluded not in ignore:
            return fail(f"Graphify does not exclude transient research artifact {excluded}")
    records = sorted((ROOT / "01-Papers/library").glob("*.json"))
    if not records:
        return fail("no paper JSON records exist")
    validation = subprocess.run(
        [sys.executable, str(ROOT / ".scripts/bin/paper_record.py"), "validate", *map(str, records)],
        check=False,
        capture_output=True,
        text=True,
    )
    if validation.returncode != 0:
        return fail(f"paper JSON validation failed: {validation.stdout}{validation.stderr}")
    for page, linked in (
        (ROOT / "100-views/paper-library.html", ("harness-dashboard.html", "thought-experiments.html")),
        (ROOT / "100-views/harness-dashboard.html", ("paper-library.html", "thought-experiments.html")),
        (ROOT / "100-views/thought-experiments.html", ("harness-dashboard.html", "paper-library.html")),
    ):
        content = page.read_text(encoding="utf-8")
        for target in linked:
            if target not in content:
                return fail(f"{page.relative_to(ROOT)} is missing navigation to {target}")
    print("PASS: harness structure and workflow routing verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
