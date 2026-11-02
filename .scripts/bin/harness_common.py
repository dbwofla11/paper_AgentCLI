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
