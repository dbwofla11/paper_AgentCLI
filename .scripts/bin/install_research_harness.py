#!/usr/bin/env python3
"""Safely install shared research-harness guidance and skills into another repo."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERSION = "1.0.0"
MANIFEST = ".research-harness-manifest.json"
SKILL_ROOT = ROOT / ".agents/skills"
MARKER = "<!-- managed-research-harness:start -->"
END_MARKER = "<!-- managed-research-harness:end -->"
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


def plan(target: Path, hosts: list[str], link_mode: str, conflict: str) -> tuple[list[dict], list[str]]:
    manifest = load_manifest(target)
    tracked = manifest["files"]
    operations: list[dict] = []
    conflicts: list[str] = []

    def add_file(relative: str, data: bytes) -> None:
        destination = target / relative
        previous = tracked.get(relative)
        exists = destination.exists() or destination.is_symlink()
        current_hash = digest_bytes(destination.read_bytes()) if destination.is_file() and not destination.is_symlink() else None
        if exists and current_hash == digest_bytes(data):
            operations.append({"action": "keep", "path": relative, "sha256": current_hash})
        elif exists and previous and current_hash == previous.get("sha256"):
            operations.append({"action": "update", "path": relative, "data": data, "sha256": digest_bytes(data)})
        elif exists:
            conflicts.append(relative)
            if conflict == "append" and relative in {"AGENTS.md", "CLAUDE.md"} and destination.is_file():
                old = destination.read_bytes()
                text = old.decode("utf-8", errors="replace")
                if MARKER in text:
                    start = text.index(MARKER)
                    end = text.find(END_MARKER, start)
                    if end >= 0:
                        end += len(END_MARKER)
                        merged = text[:start] + GUIDANCE.rstrip() + text[end:]
                    else:
                        merged = text + "\n" + GUIDANCE
                else:
                    merged = text.rstrip() + "\n\n" + GUIDANCE
                merged_bytes = merged.encode("utf-8")
                operations.append({"action": "merge", "path": relative, "data": merged_bytes, "sha256": digest_bytes(merged_bytes)})
        else:
            operations.append({"action": "create", "path": relative, "data": data, "sha256": digest_bytes(data)})

    add_file("docs/research-harness/README.md", README.encode())
    add_file("docs/research-harness/routes.json", (json.dumps(ROUTES, ensure_ascii=False, indent=2) + "\n").encode())
    add_file("AGENTS.md", GUIDANCE.encode())
    add_file(".scripts/bin/install_research_harness.py", Path(__file__).read_bytes())
    add_file(".scripts/bin/research_harness_check.py", (ROOT / ".scripts/bin/research_harness_check.py").read_bytes())
    for skill_dir in sorted(p for p in SKILL_ROOT.iterdir() if p.is_dir() and (p / "SKILL.md").is_file()):
        for source in sorted(p for p in skill_dir.rglob("*") if p.is_file()):
            rel = source.relative_to(ROOT / ".agents").as_posix()
            add_file(f".agents/{rel}", source.read_bytes())
        for host in hosts:
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
        if action in {"create", "update", "merge"}:
            data = operation["data"]
            if action == "merge" and destination.exists():
                # Merge is an explicit append action. Preserve original bytes in a backup.
                backup = destination.with_name(destination.name + ".pre-research-harness.bak")
                if not backup.exists():
                    shutil.copy2(destination, backup)
            destination.write_bytes(data)
            files[relative] = {"sha256": operation["sha256"], "kind": "file"}
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
    manifest.update({"installer_version": VERSION, "hosts": hosts, "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "files": files})
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


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
    parser.add_argument("--host", action="append", choices=["claude", "codex"], default=[])
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
    hosts = sorted(set(args.host))
    operations, conflicts = plan(target, hosts, args.link_mode, args.conflict)
    print(f"Target: {target}\nMode: {'apply' if args.apply else 'dry-run'}\nHosts: {', '.join(hosts) or 'common only'}")
    for item in operations:
        print(f"{item['action']:12} {item['path']}{' -> ' + item['target'] if item.get('target') else ''}")
    for path in conflicts:
        print(f"CONFLICT     {path} (preserved; use --conflict append only for AGENTS.md / CLAUDE.md)")
    if args.apply:
        apply(target, operations, hosts)
        print(f"Manifest: {MANIFEST}")
    else:
        print("Dry run only. Re-run with --apply to write files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
