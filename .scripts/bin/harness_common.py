"""Shared, side-effect-free helpers for research harness scripts."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, data: object) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as output:
            temporary = Path(output.name)
            json.dump(data, output, ensure_ascii=False, indent=2)
            output.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def local_settings(root: Path = ROOT) -> dict:
    try:
        data = json.loads((root / ".research-harness-agent.json").read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def orca_executable() -> str:
    return os.environ.get("ORCA_CLI_COMMAND") or ("orca-ide" if sys.platform.startswith("linux") and shutil.which("orca-ide") else "orca")


def omp_model_roles(root: Path = ROOT) -> dict[str, str]:
    try:
        result = subprocess.run(["omp", "config", "get", "modelRoles", "--json"], cwd=root, capture_output=True, text=True, timeout=15, check=True)
        roles = json.loads(result.stdout)
        return {key: value for key, value in roles.items() if isinstance(key, str) and isinstance(value, str)} if isinstance(roles, dict) else {}
    except (OSError, subprocess.SubprocessError, ValueError):
        return {}


def resolve_model(value: str | None, root: Path = ROOT) -> str | None:
    if not value:
        return None
    if value.startswith("@"):
        role = omp_model_roles(root).get(value[1:], "")
        return role.split(",", 1)[0].strip() or None
    return value


def git_visible_files(root: Path, error_message: str = "Git 제외 규칙을 확인하지 못했습니다") -> list[Path] | None:
    """Return tracked plus untracked non-ignored paths, or None outside a Git checkout.

    Fails closed: when ``root`` looks like part of a Git checkout but Git cannot
    list it, raise RuntimeError(error_message) instead of falling back to a walk
    that would expose ignored files.
    """
    resolved_root = root.resolve()
    has_git_marker = any(os.path.lexists(directory / ".git")
                         for directory in (resolved_root, *resolved_root.parents))
    git_env = os.environ.copy()
    git_env["LC_ALL"] = "C"
    for name in ("LANGUAGE", "GIT_DIR", "GIT_WORK_TREE"):
        git_env.pop(name, None)
    try:
        context = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            capture_output=True, check=False, env=git_env,
        )
    except OSError as exc:
        if has_git_marker:
            raise RuntimeError(error_message) from exc
        return None
    if context.returncode != 0 and not has_git_marker:
        return None
    if context.returncode != 0 or context.stdout.strip() != b"true":
        raise RuntimeError(error_message + " (지원하지 않거나 확인할 수 없는 Git 경로입니다)")
    try:
        listing = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            capture_output=True, check=False, env=git_env,
        )
    except OSError as exc:
        raise RuntimeError(error_message) from exc
    if listing.returncode != 0:
        raise RuntimeError(error_message)
    return [Path(os.fsdecode(name)) for name in listing.stdout.split(b"\0") if name]
