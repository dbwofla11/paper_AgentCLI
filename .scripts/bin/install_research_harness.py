#!/usr/bin/env python3
"""Safely install shared research-harness guidance and skills into another repo."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path
from harness_common import now, write_json_atomic

ROOT = Path(__file__).resolve().parents[2]
VERSION = "1.1.0"
MANIFEST = ".research-harness-manifest.json"
SKILL_ROOT = ROOT / ".agents/skills"
MARKER = "<!-- managed-research-harness:start -->"
END_MARKER = "<!-- managed-research-harness:end -->"
IGNORE_START = "# managed-research-harness:start"
IGNORE_END = "# managed-research-harness:end"
IGNORE_PATTERNS = (".research-harness-agent.json", ".research-harness-agent.tmp", ".omp/config.yml", "*.local.md")
GUIDANCE = f"""{MARKER}
## Shared research harness

- Shared agent skills are installed in `.agents/skills/`.
- Read the selected skill's `SKILL.md` before following a workflow.
- Keep user files and credentials unchanged; inspect repository instructions first.
- Run only validators documented by this repository.
{END_MARKER}
"""
README = """# Research harness installation

This repository contains the shared agent workflow skills in `.agents/skills/`.
Paper-library paths, research data, credentials, and MCP settings are intentionally
not copied. Review `AGENTS.md` and the skills before adapting the generic guidance.
The installation manifest tracks files created by the installer.
"""
ROUTES = {
    "schema_version": "1.0",
    "skills_source": ".agents/skills",
    "stages": {
        "orientation": {"next": "read-repository-guidance", "reason": "Read AGENTS.md and existing project docs before making changes."},
        "implementation": {"next": "repository-native-workflow", "reason": "Follow the target repository's existing tools and architecture."},
        "review": {"next": "inspect-diff-and-evidence", "reason": "Review only the files changed for the requested task."},
        "validation": {"next": "repository-native-checks", "reason": "Run only test/build/lint commands documented or configured by the target repository."},
    },
    "paper_repository_routes": "not-installed",
}


def digest_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def legacy_guidance(path: Path, expected_hash: str | None) -> tuple[str, bytes | None]:
    """Distinguish a legacy whole-file install from an appended user document."""
    if path.is_symlink() or not path.is_file():
        return "ambiguous", None
    content = path.read_bytes()
    if digest_bytes(content) != expected_hash:
        return "ambiguous", None
    try:
        text = content.decode("utf-8")
        backup_path = path.with_name(path.name + ".pre-research-harness.bak")
        if backup_path.is_symlink():
            return "ambiguous", None
        backup = backup_path.read_bytes() if backup_path.is_file() else None
        start = text.find(MARKER)
        end = text.find(END_MARKER, start + len(MARKER)) if start >= 0 else -1
        if start < 0 or end < 0 or text.count(MARKER) != 1 or text.count(END_MARKER) != 1:
            return "ambiguous", None
        end += len(END_MARKER)
        if backup is None:
            return ("standalone", None) if start == 0 and text[end:] in ("", "\n") else ("ambiguous", None)
        original = backup.decode("utf-8")
        if MARKER not in original and END_MARKER not in original and text[:start] == original.rstrip() + "\n\n" and text[end:] == "\n":
            return "appended", backup
    except (OSError, UnicodeError):
        pass
    return "ambiguous", None


def within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def load_manifest(path: Path) -> dict:
    manifest = path / MANIFEST
    if not manifest.exists():
        return {"schema_version": "1.0", "installer_version": VERSION, "files": {}}
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"Invalid installation manifest: {exc}") from exc
    if not isinstance(data.get("files"), dict):
        raise SystemExit("Invalid installation manifest: files must be an object")
    return data


def plan(target: Path, hosts: list[str], link_mode: str, conflict: str, profile: str = "skills") -> tuple[list[dict], list[str]]:
    skill_dirs = sorted(p for p in SKILL_ROOT.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())
    skill_rows = []
    for skill_dir in skill_dirs:
        lines = (skill_dir / "SKILL.md").read_text(encoding="utf-8").splitlines()
        if not lines or lines[0].strip() != "---":
            raise ValueError(f"Missing frontmatter in {skill_dir / 'SKILL.md'}")
        description = None
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if line.startswith("description:"):
                description = line.partition(":")[2].strip()
                if len(description) >= 2 and description[0] == description[-1] and description[0] in ("'", '"'):
                    description = description[1:-1]
                break
        if not description:
            raise ValueError(f"Missing description in {skill_dir / 'SKILL.md'}")
        description = description.replace("|", "\\|")
        skill_rows.append(f"| `{skill_dir.name}` | {description} | `.agents/skills/{skill_dir.name}/SKILL.md` |")
    skill_table = "\n## Installed skills\n\n| Skill | Description | Path |\n| --- | --- | --- |\n" + "\n".join(skill_rows) + "\n\n"
    guidance = GUIDANCE.replace(END_MARKER, skill_table + END_MARKER)
    if profile == "papers":
        guidance = guidance.replace(END_MARKER, """- Read `docs/Harness-Graph.md` and route each paper request through the installed skills.
- Store PDFs/reviews/JSON in `01-Papers/pdfs/`, `01-Papers/reviews/`, and `01-Papers/library/`; JSON follows `.scripts/docs/paper-record.schema.json`.
- Read actual PDF pages and cite source locations; do not complete a review from an abstract alone.
- Study notes need explicit user promotion. Failed Graphify sync remains retryable pending.
- Manage generated HTML in `100-views/`. Run `.scripts/bin/onboard_research.py` to connect this user's CLI.
""" + END_MARKER)
    manifest = load_manifest(target)
    tracked = manifest["files"]
    operations: list[dict] = []
    conflicts: list[str] = []

    def add_file(relative: str, data: bytes) -> None:
        destination = target / relative
        previous = tracked.get(relative)
        exists = destination.exists() or destination.is_symlink()
        current_hash = digest_bytes(destination.read_bytes()) if destination.is_file() and not destination.is_symlink() else None
        if exists and previous and previous.get("kind") == "managed-guidance":
            text = destination.read_bytes().decode("utf-8") if current_hash is not None else ""
            start = text.find(MARKER)
            end = text.find(END_MARKER, start + len(MARKER)) if start >= 0 else -1
            block = text[start:end + len(END_MARKER)] if end >= 0 and text.count(MARKER) == 1 and text.count(END_MARKER) == 1 else None
            if block is None or digest_bytes(block.encode("utf-8")) != previous.get("block_sha256"):
                conflicts.append(relative)
            elif block == guidance.rstrip():
                operations.append({"action": "keep", "path": relative})
            else:
                merged = text[:start] + guidance.rstrip() + text[end + len(END_MARKER):]
                operations.append({"action": "merge-guidance", "path": relative, "data": merged.encode("utf-8"),
                                   "original_sha256": current_hash, "block_sha256": digest_bytes(guidance.rstrip().encode("utf-8")),
                                   "separator": previous.get("separator", ""), "suffix": previous.get("suffix", "")})
        elif exists and previous and previous.get("kind") == "file" and relative in {"AGENTS.md", "CLAUDE.md"}:
            legacy_kind, original = legacy_guidance(destination, previous.get("sha256"))
            if legacy_kind == "appended":
                text = original.decode("utf-8")
                separator = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
                merged = text + separator + guidance
                operations.append({"action": "merge-guidance", "path": relative, "data": merged.encode("utf-8"),
                                   "original_sha256": current_hash, "block_sha256": digest_bytes(guidance.rstrip().encode("utf-8")),
                                   "separator": separator, "suffix": guidance[len(guidance.rstrip()):]})
            elif legacy_kind == "standalone":
                action = "keep" if current_hash == digest_bytes(data) else "update"
                operations.append({"action": action, "path": relative, "data": data, "sha256": digest_bytes(data)})
            else:
                conflicts.append(relative)
        elif exists and current_hash == digest_bytes(data):
            operations.append({"action": "keep", "path": relative, "sha256": current_hash})
        elif exists and previous and previous.get("kind") == "file" and current_hash == previous.get("sha256"):
            operations.append({"action": "update", "path": relative, "data": data, "sha256": digest_bytes(data)})
        elif exists:
            conflicts.append(relative)
            if conflict == "append" and relative in {"AGENTS.md", "CLAUDE.md"} and current_hash is not None:
                old = destination.read_bytes()
                text = old.decode("utf-8")
                if MARKER not in text and END_MARKER not in text:
                    separator = "" if not text else ("\n" if text.endswith("\n") else "\n\n")
                    merged = text + separator + guidance
                    operations.append({"action": "merge-guidance", "path": relative, "data": merged.encode("utf-8"),
                                       "original_sha256": current_hash, "block_sha256": digest_bytes(guidance.rstrip().encode("utf-8")),
                                       "separator": separator, "suffix": guidance[len(guidance.rstrip()):]})
        else:
            operations.append({"action": "create", "path": relative, "data": data, "sha256": digest_bytes(data)})

    add_file("docs/research-harness/README.md", (README + ("\nPapers profile: run `python3 .scripts/bin/onboard_research.py` to connect your CLI and launch the local paper UI.\n" if profile == "papers" else "")).encode())
    add_file("docs/research-harness/routes.json", (json.dumps({**ROUTES, "paper_repository_routes": ".scripts/docs/research-workflow-map.json" if profile == "papers" else "not-installed"}, ensure_ascii=False, indent=2) + "\n").encode())
    add_file("AGENTS.md", guidance.encode())
    if "claude" in hosts:
        add_file("CLAUDE.md", guidance.encode())
    add_file(".scripts/bin/install_research_harness.py", Path(__file__).read_bytes())
    add_file(".scripts/bin/research_harness_check.py", (ROOT / ".scripts/bin/research_harness_check.py").read_bytes())
    add_file(".scripts/bin/harness_common.py", (ROOT / ".scripts/bin/harness_common.py").read_bytes())
    if profile == "papers":
        ignore_path = target / ".gitignore"
        prior = tracked.get(".gitignore", {})
        if ignore_path.is_symlink() or (ignore_path.exists() and not ignore_path.is_file()):
            conflicts.append(".gitignore")
        else:
            original = ignore_path.read_bytes().decode("utf-8") if ignore_path.exists() else ""
            existing = set(original.splitlines())
            missing = [pattern for pattern in IGNORE_PATTERNS if pattern not in existing]
            old_block = prior.get("block") if prior.get("kind") == "managed-ignore" else None
            if old_block and original.count(old_block) != 1:
                conflicts.append(".gitignore")
            elif missing:
                if IGNORE_START in original and not old_block:
                    conflicts.append(".gitignore")
                else:
                    prefix = "" if not original or original.endswith("\n") else "\n"
                    block = prefix + IGNORE_START + "\n" + "\n".join(missing) + "\n" + IGNORE_END + "\n"
                    if old_block:
                        block = old_block[:-len(IGNORE_END + "\n")] + "\n".join(missing) + "\n" + IGNORE_END + "\n"
                        updated = original.replace(old_block, block, 1)
                    else:
                        updated = original + block
                    operations.append({"action": "managed-ignore", "path": ".gitignore", "data": updated.encode("utf-8"),
                                       "block": block, "created": prior.get("created", not ignore_path.exists()),
                                       "original_sha256": digest_bytes(original.encode("utf-8"))})
            else:
                operations.append({"action": "keep", "path": ".gitignore"})
        resources = []
        for folder in (".scripts/bin", ".scripts/docs", "90-Templates/paper", "04-Projects/validation"):
            resources.extend(p for p in (ROOT / folder).rglob("*") if p.is_file() and p.suffix in {".py", ".json", ".md"} and "__pycache__" not in p.parts)
        resources.extend(ROOT / name for name in ("docs/onboarding.md", "docs/paper-review-bridge.md", "docs/Harness-Graph.md", "docs/Skill-Catalog.md", "docs/agent-research-todo.md", "docs/research-harness-installer.md", "100-views/assets/research-ui.css", "100-views/README.md", ".graphifyignore", "00-Inbox/concept-candidate-template.md", "03-Trends/daily/README.md"))
        resources.extend((ROOT / ".omp/agents").glob("*.md"))
        resources.extend((ROOT / ".omp").glob("*.example.*"))
        resources.extend(ROOT.glob("*.example.*"))
        resources.extend((ROOT / "04-Projects/thought-experiment-runs").glob("*.example.*"))
        for source in resources:
            relative = source.relative_to(ROOT).as_posix()
            if not any(item["path"] == relative for item in operations):
                add_file(relative, source.read_bytes())
        for name in ("index", "keep", "favorites"):
            add_file(f"01-Papers/{name}.md", f"# {name}\n\n".encode())
        # wiki.py ships with this profile; render the index for the target so
        # verify_harness passes. Same ownership/conflict policy as other files.
        import wiki
        add_file(wiki.INDEX_NAME,
                 wiki.render_index(target, list_files=tuple(name for _, name in wiki.PAPER_LISTS)).encode("utf-8"))
        add_file("docs/research-harness/profile.json", b'{"profile":"papers"}\n')
    for skill_dir in skill_dirs:
        for source in sorted(p for p in skill_dir.rglob("*") if p.is_file()):
            rel = source.relative_to(ROOT / ".agents").as_posix()
            add_file(f".agents/{rel}", source.read_bytes())
        for host in hosts:
            if host == "omp":
                continue
            alias = f".{host}/skills/{skill_dir.name}"
            source_rel = f".agents/skills/{skill_dir.name}"
            destination = target / alias
            if destination.exists() or destination.is_symlink():
                if destination.is_symlink() and destination.resolve(strict=False) == (target / source_rel).resolve(strict=False):
                    operations.append({"action": "keep-link", "path": alias})
                    continue
                prior = tracked.get(alias, {})
                if destination.is_dir() and prior.get("kind") == "copy-tree" and digest_tree(destination) == prior.get("sha256"):
                    operations.append({"action": "update-copy-link", "path": alias, "target": os.path.relpath(target / source_rel, destination.parent)})
                    continue
                conflicts.append(alias)
                continue
            action = "link" if link_mode in {"auto", "symlink"} else "copy-link"
            operations.append({"action": action, "path": alias, "target": os.path.relpath(target / source_rel, destination.parent)})
    return operations, conflicts


def apply(target: Path, operations: list[dict], hosts: list[str]) -> None:
    manifest_path = target / MANIFEST
    manifest = load_manifest(target)
    files = manifest["files"]
    for operation in operations:
        action, relative = operation["action"], operation["path"]
        destination = target / relative
        if not within(destination, target):
            raise SystemExit(f"Refusing path outside target: {relative}")
        if action in {"keep", "keep-link"}:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        if action in {"create", "update"}:
            destination.write_bytes(operation["data"])
            files[relative] = {"sha256": operation["sha256"], "kind": "file"}
        elif action == "merge-guidance":
            if destination.is_symlink() or not destination.is_file() or digest_bytes(destination.read_bytes()) != operation["original_sha256"]:
                raise SystemExit(f"Refusing to overwrite changed {relative}")
            backup = destination.with_name(destination.name + ".pre-research-harness.bak")
            if not backup.exists():
                shutil.copy2(destination, backup)
            destination.write_bytes(operation["data"])
            files[relative] = {"kind": "managed-guidance", "block_sha256": operation["block_sha256"],
                               "separator": operation["separator"], "suffix": operation["suffix"]}
        elif action == "managed-ignore":
            current = destination.read_bytes() if destination.exists() else b""
            if destination.is_symlink() or digest_bytes(current) != operation["original_sha256"]:
                raise SystemExit("Refusing to overwrite changed .gitignore")
            destination.write_bytes(operation["data"])
            files[relative] = {"kind": "managed-ignore", "block": operation["block"], "created": operation["created"]}
        elif action == "link":
            try:
                os.symlink(operation["target"], destination)
                files[relative] = {"kind": "symlink", "target": operation["target"]}
            except (OSError, NotImplementedError):
                source = (destination.parent / operation["target"]).resolve()
                shutil.copytree(source, destination)
                files[relative] = {"kind": "copy-tree", "sha256": digest_tree(destination)}
        elif action in {"copy-link", "update-copy-link"}:
            source = (destination.parent / operation["target"]).resolve()
            if action == "update-copy-link":
                shutil.rmtree(destination)
            shutil.copytree(source, destination)
            files[relative] = {"kind": "copy-tree", "sha256": digest_tree(destination)}
    manifest.update({"installer_version": VERSION, "hosts": hosts, "updated_at": now(), "files": files})
    write_json_atomic(manifest_path, manifest)


def digest_tree(path: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(p for p in path.rglob("*") if p.is_file()):
        digest.update(file.relative_to(path).as_posix().encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def remove(target: Path) -> int:
    manifest_path = target / MANIFEST
    manifest = load_manifest(target)
    removed, preserved = 0, 0
    for relative, record in sorted(manifest["files"].items(), reverse=True):
        path = target / relative
        if not within(path, target) or not (path.exists() or path.is_symlink()):
            continue
        kind = record.get("kind")
        if kind == "file" and relative in {"AGENTS.md", "CLAUDE.md"}:
            legacy_kind, original = legacy_guidance(path, record.get("sha256"))
            if legacy_kind == "appended":
                path.write_bytes(original)
                removed += 1
            elif legacy_kind == "standalone":
                path.unlink()
                removed += 1
            else:
                preserved += 1
                print(f"CONFLICT: preserved {relative}; legacy guidance ownership is ambiguous")
            continue
        if kind == "managed-guidance" and path.is_file() and not path.is_symlink():
            content = path.read_bytes()
            start = content.find(MARKER.encode("utf-8"))
            end = content.find(END_MARKER.encode("utf-8"), start + len(MARKER)) if start >= 0 else -1
            if start >= 0 and end >= 0 and content.count(MARKER.encode("utf-8")) == 1 and content.count(END_MARKER.encode("utf-8")) == 1:
                end += len(END_MARKER)
                separator = record.get("separator", "").encode("utf-8")
                suffix = record.get("suffix", "").encode("utf-8")
                prefix_start = start - len(separator)
                if (digest_bytes(content[start:end]) == record.get("block_sha256") and prefix_start >= 0
                        and content[prefix_start:start] == separator and content[end:end + len(suffix)] == suffix):
                    path.write_bytes(content[:prefix_start] + content[end + len(suffix):])
                    removed += 1
                    continue
            preserved += 1
            continue
        if kind == "managed-ignore" and path.is_file() and not path.is_symlink():
            text = path.read_bytes().decode("utf-8")
            block = record.get("block")
            if isinstance(block, str) and text.count(block) == 1:
                remaining = text.replace(block, "", 1)
                if not remaining and record.get("created"):
                    path.unlink()
                else:
                    path.write_bytes(remaining.encode("utf-8"))
                removed += 1
            else:
                preserved += 1
            continue
        owned = False
        if kind == "file" and path.is_file() and digest_bytes(path.read_bytes()) == record.get("sha256"):
            owned = True
        elif kind == "symlink" and path.is_symlink() and os.readlink(path) == record.get("target"):
            owned = True
        elif kind == "copy-tree" and path.is_dir() and digest_tree(path) == record.get("sha256"):
            owned = True
        if owned:
            shutil.rmtree(path) if path.is_dir() and not path.is_symlink() else path.unlink()
            removed += 1
        else:
            preserved += 1
    if manifest_path.exists():
        manifest_path.unlink()
    print(f"Removed {removed} unchanged installer-owned paths; preserved {preserved} changed paths.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", type=Path)
    parser.add_argument("--profile", choices=["skills", "papers"], default="skills")
    parser.add_argument("--agent", choices=["auto", "codex", "claude", "omp"])
    parser.add_argument("--host", action="append", choices=["claude", "codex", "omp"], default=[])
    parser.add_argument("--link-mode", choices=["auto", "symlink", "copy"], default="auto")
    parser.add_argument("--conflict", choices=["preserve", "append"], default="preserve")
    parser.add_argument("--apply", action="store_true", help="write planned files; default is --dry-run")
    parser.add_argument("--remove", action="store_true", help="remove only unchanged installer-tracked files")
    parser.add_argument("--diagnose", action="store_true", help="run read-only checks on an installed target")
    args = parser.parse_args()
    target = args.target.expanduser().resolve()
    if not target.is_dir():
        raise SystemExit(f"Target must be an existing directory: {target}")
    if args.remove:
        return remove(target)
    if args.diagnose:
        check = target / ".scripts/bin/research_harness_check.py"
        if not check.is_file():
            print("FAIL: installed diagnostic script is missing")
            return 1
        result = __import__("subprocess").run([sys.executable, str(check)], capture_output=True, text=True, check=False)
        print(result.stdout + result.stderr, end="")
        return result.returncode
    hosts = sorted(set(args.host or (["codex", "claude"] if args.profile == "papers" else [])))
    operations, conflicts = plan(target, hosts, args.link_mode, args.conflict, args.profile)
    print(f"Target: {target}\nMode: {'apply' if args.apply else 'dry-run'}\nHosts: {', '.join(hosts) or 'common only'}")
    for item in operations:
        print(f"{item['action']:12} {item['path']}{' -> ' + item['target'] if item.get('target') else ''}")
    for path in conflicts:
        print(f"CONFLICT     {path} (preserved; use --conflict append only for AGENTS.md / CLAUDE.md)")
    if args.apply:
        apply(target, operations, hosts)
        print(f"Manifest: {MANIFEST}")
        if args.profile == "papers":
            import subprocess
            connect_command = [sys.executable, str(target / ".scripts/bin/onboard_research.py"), "--connect-only"]
            if args.agent:
                connect_command.extend(["--agent", args.agent])
            result = subprocess.run(connect_command, cwd=target, check=False)
            print("HTML 실행: python3 .scripts/bin/onboard_research.py")
            return result.returncode
    else:
        print("Dry run only. Re-run with --apply to write files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
