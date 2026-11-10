"""Paper review queue, staged review workspace, and publish logic for the WebUI server.

Moved from the former paper review bridge script. HTTP handling lives in ``webui.server``;
this module keeps the review behavior and its patchable module globals.

A deep review follows the harness review structure (see ``webui.roles``): ``paper-analyst``
generates the review in a staged workspace, and, when configured, ``paper-verifier`` checks the
validated review read-only in that same workspace before it is published. Verification reports;
it never gates publishing. Its report is a machine artifact under ``verifications_dir()``.
"""
from __future__ import annotations

import contextlib
import fnmatch
import hashlib
import json
import os
import posixpath
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
import research_agent
from harness_common import git_visible_files, sha256_file, write_json_atomic
from webui import roles, security

ROOT = Path(__file__).resolve().parents[3]
LIBRARY = ROOT / "01-Papers/library"
QUEUE = ROOT / "04-Projects/review-queue/queue.json"
LOCK = threading.RLock()
MAX_JOBS = 1
ALLOWED_ROOTS = ("01-Papers/", "02-Concepts/", "03-Trends/", "04-Projects/", "05-Ideas/", "00-Inbox/", "docs/", "100-views/", "graphify-out/", ".scripts/", ".agents/")
ALLOWED_ROOT_FILES = {"AGENTS.md", "CLAUDE.md", "README.md"}
VERDICTS = ("supported", "mismatch", "unsupported", "unverifiable")
VERIFICATION_SCHEMA_VERSION = "1.0"
PDF_READER_REASON = "PDF 읽기 도구 pdftotext(Poppler) 설치가 필요합니다."


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def root_relative(path: Path) -> Path:
    """`path` relative to ROOT when either side went through symlink resolution.

    `review_target`/`safe_pdf` return resolved paths while ROOT may be unresolved (macOS
    `/var` -> `/private/var`), so a plain `relative_to(ROOT)` can fail for a path inside ROOT.
    Raises ValueError when no form of `path` lies under a form of ROOT.

    NOT a containment guard: the lexical branches accept unresolved `..` components and symlinks
    that escape ROOT. Use it only to name paths that are already trusted (`review_target`,
    `safe_pdf`, `LIBRARY / <validated slug>`); authorization checks must resolve and test
    containment themselves (see `allowed_source`, `security.resolve_static`).
    """
    for base, candidate in ((ROOT, path), (ROOT.resolve(), path), (ROOT.resolve(), path.resolve())):
        try:
            return candidate.relative_to(base)
        except ValueError:
            continue
    raise ValueError(f"{path} is outside the repository root {ROOT}")


def load_queue() -> dict:
    if not QUEUE.exists():
        return {"schema_version": "1.0", "jobs": []}
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    if not isinstance(data.get("jobs"), list):
        raise ValueError("invalid review queue")
    return data


def save_queue(data: dict) -> None:
    QUEUE.parent.mkdir(parents=True, exist_ok=True)
    temporary = QUEUE.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, QUEUE)


def read_record(slug: str) -> tuple[Path, dict]:
    if not slug or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in slug):
        raise ValueError("invalid paper slug")
    path = LIBRARY / f"{slug}.json"
    if not path.is_file():
        raise ValueError("paper record was not found")
    return path, json.loads(path.read_text(encoding="utf-8"))


def review_target(record: dict) -> Path:
    source = record.get("source", {})
    relative = source.get("review_path")
    if relative:
        path = (ROOT / relative).resolve()
        if path.is_relative_to((ROOT / "01-Papers/reviews").resolve()):
            return path
    slug = record.get("slug", "")
    category = record.get("category", "other")
    if category not in {"wifi-csi", "game-ai", "agent-ai", "computer-vision", "other"}:
        category = "other"
    return ROOT / "01-Papers" / "reviews" / category / f"{slug}.md"


def needs_review(record: dict, target: Path) -> bool:
    return record.get("structured_review_status") != "complete" or not target.is_file()


def safe_pdf(record: dict) -> Path:
    relative = record.get("source", {}).get("pdf_path")
    if not relative:
        raise ValueError("PDF path is missing")
    path = (ROOT / relative).resolve()
    if not path.is_relative_to((ROOT / "01-Papers/pdfs").resolve()) or not path.is_file():
        raise ValueError("repository PDF is unavailable or outside 01-Papers/pdfs")
    return path


def allowed_source(path: Path) -> bool:
    """Containment check: `path`, after resolving symlinks and `..`, is an allowed repo path."""
    root = ROOT.resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        return False
    rel = resolved.relative_to(root).as_posix()
    return rel in ALLOWED_ROOT_FILES or rel.startswith(ALLOWED_ROOTS)


def allowed_output(name: str, record_path: Path, review_path: Path) -> bool:
    record_name = root_relative(record_path).as_posix()
    review_name = root_relative(review_path).as_posix()
    if name in {record_name, review_name, "01-Papers/index.md", "100-views/paper-library.html"} or name.startswith("graphify-out/") or name.startswith("00-Inbox/concept-candidates/"):
        return True
    # This review's figure files: method figures `<review dir>/figures/<slug>-<suffix>.(svg|html)`
    # and the visual summary `<slug>-visual.(src.html|html|sheet[-N].png)` (never its sidecar).
    figures = f"{posixpath.dirname(review_name)}/{security.FIGURE_DIR}/"
    if not name.startswith(figures) or "/" in name[len(figures):]:
        return False
    slug, leaf = Path(review_name).stem, name[len(figures):]
    return security.figure_name_ok(slug, leaf, ("svg", "html")) or security.visual_output_ok(slug, leaf)


# The job's own copy of the visual-explainer skill inside a stage or visual workspace
# (`visuals.copy_skill`); never cloned, snapshotted, or published.
VISUAL_SKILL_COPY = ".visual-explainer"
STAGING_IGNORES = (".git", "__pycache__", "*.pyc", "pdfs", ".mcp.json",
                   ".env", ".env.*", ".claude", ".codex", ".secrets",
                   "credentials.json", "node_modules", ".cache",
                   ".research-harness-agent.json", ".research-harness-agent.tmp", "reader-threads",
                   VISUAL_SKILL_COPY)


def staging_inventory(root: Path) -> set[Path]:
    """List safe files, including graph artifacts and permitted local settings.

    The personal paper records (`01-Papers/library/`, `01-Papers/reviews/` with its figures,
    `01-Papers/index.md`) are gitignored but every review job reads and rewrites them, so they
    are listed explicitly; PDFs and reader threads stay excluded (`STAGING_IGNORES`).
    """
    def allowed(relative: Path) -> bool:
        return all(not any(fnmatch.fnmatchcase(part, pattern) for pattern in STAGING_IGNORES)
                   for part in relative.parts)

    paths: set[Path] = set()
    def collect_tree(start: Path) -> None:
        if start.is_symlink():
            paths.add(start.relative_to(root))
            return
        for directory, dirs, files in os.walk(start):
            base = Path(directory)
            dirs[:] = [name for name in dirs if allowed((base / name).relative_to(root))]
            paths.update((base / name).relative_to(root) for name in files)
            paths.update((base / name).relative_to(root) for name in dirs if (base / name).is_symlink())

    resolved_root = root.resolve()
    listing = git_visible_files(root, "Git 제외 규칙을 확인하지 못해 리뷰 작업공간을 만들지 않았습니다")
    if listing is not None:
        paths.update(listing)
        paths.add(Path(".omp/config.yml"))
        for directory in (root, root / "04-Projects/thought-experiment-runs"):
            if directory.is_dir():
                paths.update(path.relative_to(root) for path in directory.glob("*.local.md"))
        collect_tree(root / "graphify-out")
        collect_tree(root / "01-Papers/library")
        collect_tree(root / "01-Papers/reviews")
        if os.path.lexists(root / "01-Papers/index.md"):
            paths.add(Path("01-Papers/index.md"))
    else:
        collect_tree(root)

    safe = set()
    for relative in paths:
        if relative.is_absolute() or ".." in relative.parts or not allowed(relative):
            continue
        path = root / relative
        if not os.path.lexists(path):
            continue
        if path.is_symlink() and os.path.isabs(os.readlink(path)):
            continue
        try:
            path.resolve(strict=False).relative_to(resolved_root)
        except (ValueError, OSError, RuntimeError):
            continue
        safe.add(relative)
    return safe


def snapshot(root: Path) -> dict[str, str]:
    result = {}
    for relative in staging_inventory(root):
        path = root / relative
        if path.is_symlink():
            result[relative.as_posix()] = "symlink:" + os.readlink(path)
        elif path.is_file():
            result[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def clone_review_workspace(destination: Path, pdf_path: Path) -> None:
    for relative in staging_inventory(ROOT):
        source = ROOT / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            target.symlink_to(os.readlink(source))
        elif source.is_file():
            shutil.copy2(source, target)
    relative = root_relative(pdf_path)
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pdf_path, target)


def review_command(stage: Path, last_message: Path, prompt: str, selected: str = "codex", *,
                   timeout_seconds: int | None = None, root: Path | None = None,
                   model: str | None = None, effort: str | None = None) -> list[str]:
    return research_agent.command(selected, stage, last_message, prompt,
                                  timeout_seconds=timeout_seconds, root=root, model=model, effort=effort)


@contextlib.contextmanager
def stage_visual_skill(stage: Path, runner: str) -> Iterator[None]:
    """For one generation run: ``runner``'s visual-explainer skill copied to
    ``<stage>/.visual-explainer`` (paper-review step 5-1 reads and renders with that copy, never
    the installed skill), removed after the run so a fallback attempt's audit and the publish never
    see it. A missing skill or a failed copy leaves no copy; the agent then skips the visual summary."""
    from webui import visuals  # visuals imports this module

    try:
        visuals.copy_skill(runner, stage)
    except OSError:
        pass
    try:
        yield
    finally:
        try:
            visuals.remove_skill_copy(stage)
        except OSError:
            pass


def runtime_status(requested: str | None = None) -> dict:
    """Connected-agent status plus review readiness under the harness review roles.

    A configured ``paper-analyst`` replaces the connected agent for generation, and a configured
    ``paper-verifier`` must also be runnable; unconfigured roles keep the pre-existing behavior.
    An unreadable role config (``configured: None``) makes reviews not ready.
    """
    status = research_agent.resolve(ROOT, requested)
    review_roles = roles.review_roles(ROOT)
    status["review_roles"] = review_roles
    status["pdf_reader_ready"] = bool(shutil.which("pdftotext"))
    generation, verification = review_roles["generation"], review_roles["verification"]
    role_reasons = [reason for reason in (roles.unavailable_reason(generation), roles.unavailable_reason(verification)) if reason]
    if generation.get("configured") is False:
        generation_ready = bool(status.get("ready"))
    else:
        generation_ready = generation.get("configured") is True and generation.get("selected") is not None
    status["ready"] = generation_ready and not role_reasons and status["pdf_reader_ready"]
    if not status["pdf_reader_ready"]:
        status["reason"] = PDF_READER_REASON
    elif role_reasons:
        status["reason"] = " / ".join(role_reasons)
    elif generation.get("configured"):
        status["reason"] = "리뷰 역할 준비 완료"
    return status


def review_agent(status: dict) -> str | None:
    """Runner that generates the review: the paper-analyst candidate, else the connected agent
    (only when the role is genuinely unconfigured)."""
    generation = (status.get("review_roles") or {}).get("generation") or {"configured": False}
    if generation.get("configured") is False:
        return status.get("agent")
    candidate = roles.selected_candidate(generation) if generation.get("configured") else None
    return candidate["runner"] if candidate else None


def generation_prompt(slug: str, record: dict, configured: bool) -> str:
    prompt = (
        f"Use the installed paper-review skill to review exactly the paper with slug {slug}. "
        f"Read AGENTS.md, .agents/skills/paper-review/SKILL.md and its review template. The repository PDF is {record.get('source', {}).get('pdf_path')}. "
        "Read actual numbered PDF pages using pdftotext or a host page-bounded PDF tool, "
        "in ranges of at most 10 pages; record the pages actually read in the review. "
        "Stop if actual pages cannot be read or extracted text is empty. Do not use only the abstract. "
        "Follow 3 passes, cite all factual claims and numbers, update only this paper's Markdown review, "
        f"its JSON record, its method figure files under figures/ beside the review ({slug}-method.html and {slug}-method.svg), "
        "01-Papers/index.md, Graphify sync artifacts, and the generated 100-views/paper-library.html. "
        "Remove every template instruction comment (<!-- ... -->) from the review. "
        "Do not edit wiki-index.md or wiki-log.md; the bridge updates them after publishing. "
        "Do not modify any other paper, skill, script, PDF, or user configuration. If a tool or source required for the paper review is missing, stop and report failure. Graphify failure is retryable: record it as pending and preserve the completed review. "
        "After the review is final, optionally render its visual summary with the visual-explainer skill (paper-review skill step 5-1) "
        f"using only this workspace's copy of that skill at ./{VISUAL_SKILL_COPY}/ (read its SKILL.md and references there; never edit the copy; "
        f"if ./{VISUAL_SKILL_COPY}/ is absent, skip the visual summary and report why) "
        f"into figures/ beside the review: {slug}-visual.src.html, then run "
        f"`node ./{VISUAL_SKILL_COPY}/kit/render.mjs <figures dir>/{slug}-visual.src.html` from the workspace root, which writes {slug}-visual.html and its look sheets "
        f"({slug}-visual.sheet.png, {slug}-visual.sheet-N.png); never write {slug}-visual.json. "
        "A missing visual-explainer skill or node, or a failed visual summary, never fails the review: "
        f"delete partial {slug}-visual.* files and report the reason."
    )
    if not configured:
        return prompt
    _, body = roles.agent_definition(roles.GENERATION, ROOT)
    return (f"{prompt}\n\nYou act as the harness agent `{roles.GENERATION}`. Its role definition "
            "(.omp/agents/paper-analyst.md) follows; the constraints above take precedence over it."
            f"\n\n<agent-definition name=\"{roles.GENERATION}\">\n{body}\n</agent-definition>")


def assistant_output(result: subprocess.CompletedProcess, last_message: Path) -> bool:
    """Whether a failed generation run left evidence of assistant output.

    The staged review commands print text, not events, so stdout cannot be told apart from
    assistant prose. Conservatively, any non-blank stdout line or a non-empty
    `--output-last-message` file (codex) counts as output; an unreadable file counts too.
    """
    try:
        if last_message.is_file() and last_message.read_text(encoding="utf-8", errors="replace").strip():
            return True
    except OSError:
        return True
    return any(line.strip() for line in (result.stdout or "").splitlines())


def run_generation(stage: Path, last_message: Path, prompt: str, status: dict, resolution: dict,
                   timeout: int) -> tuple[subprocess.CompletedProcess, dict]:
    """Run the staged review agent; returns the last process result and the generation record
    ``{"selector", "runner", "attempts": [...]}`` (one attempt per candidate run).

    Unconfigured ``paper-analyst`` runs the connected agent exactly as before. An unreadable role
    config raises. A configured role walks its ready candidates (``roles.walk``): a failed run
    moves on only when its stderr reads as a usage limit (``llm.classify_error_text`` over stderr
    only; stdout is assistant text and never classified), it left no assistant output
    (``assistant_output``), and the staged workspace is untouched (``audit_snapshot``).
    """
    def run(runner: str, model: str | None = None, effort: str | None = None) -> subprocess.CompletedProcess:
        last_message.unlink(missing_ok=True)  # output evidence must belong to this attempt
        with stage_visual_skill(stage, runner):
            return subprocess.run(
                review_command(stage, last_message, prompt, runner, timeout_seconds=timeout, model=model, effort=effort),
                cwd=stage, capture_output=True, text=True,
                timeout=timeout + 60 if runner == "omp" else timeout, check=False,
            )

    if resolution.get("configured") is None:
        raise RuntimeError(roles.unavailable_reason(resolution))
    if not resolution["configured"]:
        runner = status["agent"]
        with stage_visual_skill(stage, runner):
            result = subprocess.run(
                review_command(stage, last_message, prompt, runner, timeout_seconds=timeout),
                cwd=stage, capture_output=True, text=True,
                timeout=timeout + 60 if runner == "omp" else timeout, check=False,
            )
        return result, {"selector": None, "runner": runner, "attempts": [
            {"selector": None, "runner": runner, "exit_code": result.returncode, "error_kind": None,
             "assistant_output": None, "staged_changes": None, "advanced": False}]}
    from webui import llm

    ready = [candidate for candidate in resolution["candidates"] if candidate["ready"]]
    # Only a possible fallback needs the pre-run state; it is the same for every attempt that may advance.
    pristine = audit_snapshot(stage) if len(ready) > 1 else None
    attempts: list[dict] = []
    last: dict = {}

    def attempt(candidate: dict) -> list[dict]:
        call = roles.invocation(candidate)
        result = run(call["runner"], call["model"], call["effort"])
        record = {"selector": candidate["selector"], "runner": call["runner"], "exit_code": result.returncode,
                  "error_kind": None, "assistant_output": None, "staged_changes": None, "advanced": False}
        attempts.append(record)
        last["result"] = result
        if result.returncode == 0:
            return [{"type": "result", "text": ""}]
        record["error_kind"] = llm.classify_error_text(result.stderr)
        record["assistant_output"] = assistant_output(result, last_message)
        events: list[dict] = [{"type": "message", "text": ""}] if record["assistant_output"] else []
        if pristine is not None:
            record["staged_changes"] = audit_snapshot(stage) != pristine
        kind = record["error_kind"]
        if kind == "usage_limit" and record["staged_changes"] is not False:
            kind = "other"  # partial work in the stage (or unknown): never rerun on top of it
        return events + [{"type": "error", "kind": kind, "message": (result.stderr or result.stdout)[-2000:]}]

    try:
        for event in roles.walk(resolution, attempt):
            if event.get("type") == "retry":
                attempts[-1]["advanced"] = True
    except roles.RoleUnavailable as exc:
        raise RuntimeError(str(exc)) from exc
    final = attempts[-1]
    return last["result"], {"selector": final["selector"], "runner": final["runner"], "attempts": attempts}


# ---- verification ------------------------------------------------------------------------------

def verifications_dir() -> Path:
    """Verification reports live next to the review queue (machine artifacts, not wiki content)."""
    return QUEUE.parent / "verifications"


def verification_path(slug: str) -> Path:
    if not slug or any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789-" for ch in slug):
        raise ValueError("invalid paper slug")
    return verifications_dir() / f"{slug}.json"


def _display_path(path: Path) -> str:
    try:
        return root_relative(path).as_posix()
    except ValueError:
        return str(path)


def _with_string_enum_types(node: object) -> object:
    """Give `enum` nodes of strings an explicit `type` (strict structured-output schemas need it)."""
    if isinstance(node, dict):
        result = {key: _with_string_enum_types(value) for key, value in node.items()}
        if "enum" in result and "type" not in result and all(isinstance(item, str) for item in result["enum"]):
            result["type"] = "string"
        return result
    if isinstance(node, list):
        return [_with_string_enum_types(item) for item in node]
    return node


def verifier_definition() -> tuple[dict, str]:
    """Output schema (from the frontmatter `output`) and instruction body of paper-verifier."""
    meta, body = roles.agent_definition(roles.VERIFICATION, ROOT)
    schema = meta.get("output")
    if not isinstance(schema, dict) or schema.get("type") != "object":
        raise ValueError(".omp/agents/paper-verifier.md에 출력 스키마(output)가 없습니다.")
    return _with_string_enum_types(schema), body


def verification_prompt(body: str, review_rel: str, pdf_rel: str, schema: dict) -> str:
    return (f"{body}\n\n---\n\nVerify the completed paper review below against its PDF. This workspace is "
            "read-only: do not create, edit, or delete any file in it.\n"
            f"- Review: {review_rel}\n- Paper PDF: {pdf_rel}\n\n"
            "Return ONLY one JSON object, with no prose and no code fence, matching this JSON Schema:\n"
            f"{json.dumps(schema, ensure_ascii=False)}\n"
            f"Set review_path to \"{review_rel}\". Every checked_claims[].verdict is one of "
            f"{', '.join(VERDICTS)}.")


def run_verifier(candidate: dict, stage: Path, prompt: str, schema_path: Path, timeout: int) -> Iterator[dict]:
    """Normalized events of one read-only verifier run (`research_agent.verify_command`)."""
    from webui import llm

    call = roles.invocation(candidate)
    try:
        argv = research_agent.verify_command(
            call["runner"], stage, prompt, schema_path=schema_path, model=call["model"], effort=call["effort"],
            timeout_seconds=timeout + llm.CLI_TIMEOUT_GRACE_S, root=stage)
    except ValueError as exc:
        raise llm.LLMUnavailable(str(exc)) from exc
    request = llm.LLMRequest(prompt=prompt, cwd=stage, agent=call["runner"], timeout_s=timeout,
                             model=call["model"], effort=call["effort"])
    return llm.launch(call["runner"], argv, request).events()


def _json_from_text(text: str) -> object:
    value = text.strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1] if "\n" in value else ""
        value = value.rsplit("```", 1)[0]
    try:
        return json.loads(value)
    except ValueError:
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("verifier answer is not JSON") from None
        return json.loads(value[start:end + 1])


def validate_verification(data: object) -> dict:
    """Check the verifier answer against the paper-verifier output schema; returns its fields only."""
    if not isinstance(data, dict):
        raise ValueError("verifier answer must be a JSON object")
    for key, kind in (("status", str), ("review_path", str), ("checked_claims", list),
                      ("blocking_issues", list), ("summary", str)):
        if key not in data:
            raise ValueError(f"verifier answer is missing {key}")
        if not isinstance(data[key], kind):
            raise ValueError(f"verifier answer field {key} must be {kind.__name__}")
    claims = []
    for index, claim in enumerate(data["checked_claims"]):
        if not isinstance(claim, dict):
            raise ValueError(f"checked_claims[{index}] must be an object")
        for key in ("claim", "locator", "verdict", "note"):
            if not isinstance(claim.get(key), str):
                raise ValueError(f"checked_claims[{index}].{key} must be a string")
        if claim["verdict"] not in VERDICTS:
            raise ValueError(f"checked_claims[{index}].verdict must be one of {', '.join(VERDICTS)}")
        claims.append({key: claim[key] for key in ("claim", "locator", "verdict", "note")})
    if not all(isinstance(issue, str) for issue in data["blocking_issues"]):
        raise ValueError("blocking_issues must be strings")
    return {"status": data["status"], "review_path": data["review_path"], "checked_claims": claims,
            "blocking_issues": list(data["blocking_issues"]), "summary": data["summary"]}


def audit_snapshot(root: Path) -> dict[str, str]:
    """Every entry under `root` with no exclusions (unlike `snapshot`, PDFs and caches included).

    Regular files map to their SHA-256, symlinks to `symlink:<target>`, directories to `dir`, and
    anything else (FIFO, socket, device) to `special:<mode>`; symlinks are never followed and
    special files are never opened, so a hostile entry cannot block or redirect the audit.
    """
    result: dict[str, str] = {}
    for directory, dirs, files in os.walk(root):
        base = Path(directory)
        for name in (*dirs, *files):
            path = base / name
            relative = path.relative_to(root).as_posix()
            info = os.lstat(path)
            if stat.S_ISLNK(info.st_mode):
                result[relative] = "symlink:" + os.readlink(path)
            elif stat.S_ISDIR(info.st_mode):
                result[relative] = "dir"
            elif stat.S_ISREG(info.st_mode):
                result[relative] = sha256_file(path)
            else:
                result[relative] = f"special:{info.st_mode:o}"
    return result


def preserve_outputs(stage: Path, names: set[str], destination: Path) -> Path:
    """Copy the validated outputs (and the graph sync state publishing reads) out of the stage.

    Publishing reads this copy, so whatever a verifier later does to the stage (overwrite,
    delete, replace a file with a directory or a symlink, swap a parent directory) cannot change
    or block what is published. Copies exactly what `publish_review_outputs` would have read.
    """
    for name in {*names, "graphify-out/sync-state.json"}:
        source = stage / name
        if source.is_file():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
    return destination


def preserve_visual(stage: Path, visual: dict, names: set[str], destination: Path) -> dict:
    """`preserve_outputs` for the optional visual summary files (``stage_visual``'s ``names``),
    copied into the same pre-verifier ``destination``. A copy failure never touches the canonical
    copy: the partial visual copies are removed and the returned queue ``visual`` is ``failed``,
    so ``publish_staged_visual`` publishes nothing and the review still publishes."""
    if visual["status"] != "published":
        return visual
    try:
        for name in sorted(names):
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(stage / name, target)
    except OSError as exc:
        for name in names:
            try:
                (destination / name).unlink(missing_ok=True)
            except OSError:
                pass
        return {"status": "failed", "reason": f"검증 전 시각 요약 파일을 보관하지 못했습니다: {exc}"}
    return visual


def verify_stage(stage: Path, review_path: Path, pdf_path: Path, resolution: dict, timeout: int) -> dict:
    """Run paper-verifier read-only on the staged review; never raises.

    Returns ``{"selector", "runner", "review_sha256", "pdf_sha256"}`` plus ``"result"`` or ``"error"``.
    The hashes are the staged review and PDF as handed to the verifier (taken before it runs).
    ``audit_snapshot`` of the whole stage before and after the run must match; any difference
    (the PDF included) is an error. The stage is not repaired: callers publish from a copy taken
    before verification (``preserve_outputs``).
    """
    from webui import llm

    outcome: dict = {"selector": None, "runner": None, "review_sha256": None, "pdf_sha256": None}
    try:
        review_rel = root_relative(review_path).as_posix()
        pdf_rel = root_relative(pdf_path).as_posix()
        before = audit_snapshot(stage)
        outcome.update(review_sha256=before.get(review_rel), pdf_sha256=before.get(pdf_rel))
        for label, digest in (("review", outcome["review_sha256"]), ("PDF", outcome["pdf_sha256"])):
            if digest is None or digest == "dir" or digest.startswith(("symlink:", "special:")):
                return {**outcome, "error": f"staged {label} is not a regular file"}
    except (OSError, ValueError) as exc:
        return {**outcome, "error": f"could not audit the staged workspace: {exc}"[-2000:]}
    terminal: dict | None = None
    failure: str | None = None
    try:
        schema, body = verifier_definition()
        prompt = verification_prompt(body, review_rel, pdf_rel, schema)
        with tempfile.TemporaryDirectory(prefix="paper-verify-") as tmp:
            schema_path = Path(tmp) / "paper-verifier.output.schema.json"
            schema_path.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")

            def attempt(candidate: dict) -> Iterator[dict]:
                outcome.update(selector=candidate["selector"], runner=roles.invocation(candidate)["runner"])
                return run_verifier(candidate, stage, prompt, schema_path, timeout)

            for event in roles.walk(resolution, attempt):
                if event.get("type") in ("result", "error", "cancelled"):
                    terminal = event
    except (roles.RoleUnavailable, llm.LLMUnavailable, ValueError, OSError) as exc:
        failure = str(exc)[-2000:]
    except Exception as exc:  # a verifier failure must never block publishing
        failure = f"{type(exc).__name__}: {exc}"[-2000:]
    try:
        after = audit_snapshot(stage)
    except (OSError, ValueError) as exc:
        return {**outcome, "error": f"could not audit the staged workspace after verification: {exc}"[-2000:]}
    touched = sorted(name for name in before.keys() | after.keys() if before.get(name) != after.get(name))
    if touched:
        return {**outcome, "error": "verifier changed staged files: " + ", ".join(touched[:20])}
    if failure is not None:
        return {**outcome, "error": failure}
    if terminal is None or terminal.get("type") != "result":
        message = (terminal or {}).get("message") or ("검증이 취소되었습니다." if terminal else "검증기가 결과 없이 끝났습니다.")
        return {**outcome, "error": str(message)[-2000:]}
    try:
        data = terminal.get("structured_output")
        result = validate_verification(data if data is not None else _json_from_text(terminal.get("text") or ""))
    except ValueError as exc:
        return {**outcome, "error": f"invalid verifier JSON: {exc}"}
    return {**outcome, "result": result}


NO_CLAIMS_NOTE = "검증된 주장이 없음"


def verification_summary(report: dict | None) -> dict:
    """Job-record shape of a verification: status passed|issues|error|skipped plus counts.

    `passed` needs at least one checked claim, every verdict `supported`, and no blocking issue. A
    result without checked claims (and without blocking issues) is `issues` with `note`
    NO_CLAIMS_NOTE; `note` is present only then.
    """
    if report is None:
        return {"status": "skipped", "blocking_issues": 0, "mismatches": 0, "report_path": None,
                "selector": None, "runner": None}
    verifier = report.get("verifier") or {}
    summary = {"status": "error", "blocking_issues": 0, "mismatches": 0,
               "report_path": _display_path(verification_path(report["slug"])),
               "selector": verifier.get("selector"), "runner": verifier.get("runner")}
    result = report.get("result")
    if isinstance(result, dict) and "error" not in report:
        claims = result.get("checked_claims") or []
        blocking = len(result.get("blocking_issues") or [])
        mismatches = sum(1 for claim in claims if claim.get("verdict") != "supported")
        summary.update(status="passed" if claims and not blocking and not mismatches else "issues",
                       blocking_issues=blocking, mismatches=mismatches)
        if not claims and not blocking:
            summary["note"] = NO_CLAIMS_NOTE
    return summary


def verification_message(summary: dict, slug: str, error: str | None = None) -> str:
    if summary["status"] == "passed":
        return "검증 통과: 확인한 주장이 모두 원문과 일치합니다."
    if summary["status"] == "issues":
        if summary.get("note"):
            return f"검증 이슈: {summary['note']}(보고서 {summary['report_path']})."
        return (f"검증 이슈: 차단 이슈 {summary['blocking_issues']}건, 미확인·불일치 주장 {summary['mismatches']}건"
                f"(보고서 {summary['report_path']}).")
    if summary["status"] == "error":
        return f"검증 오류: {(error or '알 수 없는 오류')[-500:]} — POST /api/reviews/{slug}/verify로 다시 검증할 수 있습니다."
    return "검증 건너뜀: paper-verifier 역할이 설정되지 않았습니다."


def write_verification_report(slug: str, review_path: Path, resolution: dict, outcome: dict) -> dict:
    """Atomically store the report; its hashes are the review and PDF the verifier was given
    (``verify_stage`` takes them before the run, so a mutation cannot fingerprint itself)."""
    report = {"schema_version": VERIFICATION_SCHEMA_VERSION, "slug": slug,
              "review_path": root_relative(review_path).as_posix(),
              "review_sha256": outcome.get("review_sha256"), "pdf_sha256": outcome.get("pdf_sha256"),
              "verified_at": now(),
              "verifier": {"agent_name": resolution.get("agent_name", roles.VERIFICATION), "role": resolution.get("role"),
                           "selector": outcome.get("selector"), "runner": outcome.get("runner")}}
    if "result" in outcome:
        report["result"] = outcome["result"]
    else:
        report["error"] = outcome.get("error") or "verification failed"
    path = verification_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(path, report)
    return report


def load_verification(slug: str) -> dict | None:
    """Stored report with a `summary` (job shape plus `stale`), or None when there is none."""
    path = verification_path(slug)
    if not path.is_file():
        return None
    report = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(report, dict):
        return None
    summary = verification_summary(report)
    stale = True
    try:
        _, record = read_record(slug)
        review, pdf = review_target(record), safe_pdf(record)
        stale = not (review.is_file() and sha256_file(review) == report.get("review_sha256")
                     and sha256_file(pdf) == report.get("pdf_sha256"))
    except (ValueError, OSError):
        pass
    return {**report, "summary": {**summary, "stale": stale}}


def publish_review_outputs(stage: Path, changed: set[str], live_before: dict,
                           record_path: Path, review_path: Path) -> tuple[list[str], str]:
    """Protect canonical edits; retry shared graph updates without losing a review."""
    catalog_name = "100-views/paper-library.html"
    source_name = root_relative(record_path).as_posix()
    state_path = stage / "graphify-out/sync-state.json"
    state = json.loads(state_path.read_text()) if state_path.is_file() else {}
    synced = state.get("sources", {}).get(source_name, {}).get("status") == "success"
    candidates = [name for name in sorted(changed) if name != catalog_name
                  and allowed_output(name, record_path, review_path) and (stage / name).is_file()]
    conflicts = []
    for name in candidates:
        destination = ROOT / name
        current = hashlib.sha256(destination.read_bytes()).hexdigest() if destination.is_file() else None
        if current != live_before.get(name):
            conflicts.append(name)
    canonical_conflicts = [name for name in conflicts if not name.startswith("graphify-out/")]
    if canonical_conflicts:
        raise RuntimeError("live source files changed; review was not published: " + ", ".join(canonical_conflicts))
    if any(name.startswith("graphify-out/") for name in conflicts):
        synced = False
    publish = [name for name in candidates if synced or not name.startswith("graphify-out/")]
    for name in publish:
        destination = ROOT / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(stage / name, destination)
    if not synced:
        result = subprocess.run([sys.executable, str(ROOT / ".scripts/bin/graphify_sync.py"),
                                 "begin", "--source", source_name], cwd=ROOT, capture_output=True, text=True, check=False)
        if result.returncode:
            raise RuntimeError("review saved, but could not record pending graph sync: " + result.stderr[-1000:])
        publish.append("graphify-out/sync-state.json")
    # The staged workspace contains only the selected PDF. Regenerate against
    # the live library so other papers retain their canonical local PDF links.
    catalog = subprocess.run([sys.executable, str(ROOT / ".scripts/bin/paper_catalog_html.py")],
                             cwd=ROOT, capture_output=True, text=True, check=False)
    if catalog.returncode:
        raise RuntimeError("review saved, but catalog regeneration failed: " + catalog.stderr[-1000:])
    publish.append(catalog_name)
    return publish, "success" if synced else "pending"


def refresh_wiki(title: str, record_path: Path, review_path: Path) -> tuple[list[str], str | None]:
    """Refresh the live wiki index and append one ingest log entry after a publish.

    The review agent never edits these files; failures are reported, not raised,
    so a published review is never rolled back by bookkeeping.
    """
    script = str(ROOT / ".scripts/bin/wiki.py")
    steps = (
        ("wiki-index.md", [sys.executable, script, "index"]),
        ("wiki-log.md", [sys.executable, script, "log", "--op", "ingest", "--title", title,
                         "--path", root_relative(review_path).as_posix(),
                         "--path", root_relative(record_path).as_posix()]),
    )
    updated: list[str] = []
    errors: list[str] = []
    for name, command in steps:
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
        except OSError as exc:
            errors.append(f"{name}: {exc}")
            continue
        if result.returncode:
            errors.append(f"{name}: {(result.stderr or result.stdout).strip()[-1000:]}")
        else:
            updated.append(name)
    return updated, ("; ".join(errors) or None)


def _update_job(job_id: str, **fields) -> None:
    with LOCK:
        data = load_queue()
        job = next((item for item in data["jobs"] if item["job_id"] == job_id), None)
        if job:
            job.update(fields)
            save_queue(data)


def _start_job(job_id: str) -> dict | None:
    with LOCK:
        data = load_queue()
        job = next((item for item in data["jobs"] if item["job_id"] == job_id), None)
        if not job:
            return None
        job["status"] = "running"
        job["started_at"] = now()
        save_queue(data)
        return dict(job)


def _store_verification(slug: str, target: Path, resolution: dict, outcome: dict) -> tuple[dict, str | None]:
    """Write the report; returns the job summary and the error text (verifier or storage), if any."""
    try:
        report = write_verification_report(slug, target, resolution, outcome)
    except (OSError, ValueError) as exc:
        summary = {**verification_summary({"slug": slug, "verifier": outcome, "error": str(exc)}),
                   "report_path": None}
        return summary, f"검증 보고서를 저장하지 못했습니다: {exc}"
    return verification_summary(report), report.get("error")


# ---- visual summary in a staged review ----------------------------------------------------------

def _figures_name(review_path: Path) -> str:
    """Repository-relative ``figures`` folder beside ``review_path``."""
    return posixpath.join(posixpath.dirname(root_relative(review_path).as_posix()), security.FIGURE_DIR)


def stage_visual(stage: Path, review_path: Path, slug: str, changed: set[str]) -> tuple[dict, set[str]]:
    """Status of the visual summary the review agent left in the stage, plus the staged names of
    its files (page, source, sheets; empty unless the page passed the check).

    ``published`` (pending ``publish_staged_visual``) when ``{slug}-visual.html`` changed and passes
    ``visuals.checked_visual``; ``missing`` when it did not change or is gone; ``rejected`` when the
    check fails. Every ``{slug}-visual.*`` name is always removed from ``changed`` in place: the
    canonical review publish never carries the optional visual summary."""
    from webui import visuals  # visuals imports this module

    figures = _figures_name(review_path)
    staged = {name for name in changed if posixpath.dirname(name) == figures
              and security.visual_output_ok(slug, posixpath.basename(name))}
    changed.difference_update(staged)
    page = f"{figures}/{security.visual_name(slug)}.html"
    if page not in staged or not (stage / page).is_file():
        return {"status": "missing", "reason": "리뷰 에이전트가 새 시각 요약을 만들지 않았습니다."}, set()
    try:
        visuals.checked_visual(stage, slug, tuple(figures.split("/")))
    except ValueError as exc:
        return {"status": "rejected", "reason": str(exc)}, set()
    names = {f"{figures}/{path.name}" for path in (stage / figures).iterdir()
             if security.visual_output_ok(slug, path.name) and path.is_file() and not path.is_symlink()}
    return {"status": "published", "reason": None}, names


def publish_staged_visual(source: Path, review_path: Path, record: dict, slug: str, visual: dict,
                          live_before: dict, meta: dict) -> tuple[dict, list[str]]:
    """Publish a ``published``-pending staged visual summary from ``source`` (the stage or its
    validated copy) by itself, after the canonical review outputs; returns the final queue
    ``visual`` and the repository paths written. Never raises: the review stays completed.

    The live ``{slug}-visual.*`` set (sidecar included) must still match ``live_before``, else
    ``conflict`` with nothing written; a page that no longer passes the check is ``rejected``; an
    unreadable source or a failed write (the previous live files restored) is ``failed``. On success
    the set becomes the staged files plus a sidecar (``source: "review"``, ``check: null``)."""
    from webui import reader, visuals  # visuals imports this module

    if visual["status"] != "published":
        return visual, []
    figures = _figures_name(review_path)
    components = tuple(figures.split("/"))
    try:
        html = visuals.checked_visual(source, slug, components)
    except ValueError as exc:
        return {"status": "rejected", "reason": str(exc)}, []
    expected = {posixpath.basename(name): digest for name, digest in live_before.items()
                if posixpath.dirname(name) == figures and visuals.managed_name(slug, posixpath.basename(name))}
    data = visuals.sidecar(meta.get("review_sha256"), "review", meta.get("job_id"), meta, None)
    try:
        files = visuals.visual_outputs(source, slug, components)
        files[f"{security.visual_name(slug)}.html"] = html
        visuals.replace_visual(record, slug, files, data, expected)
    except OSError as exc:
        return {"status": "failed", "reason": f"시각 요약 파일을 읽지 못했습니다: {exc}"}, []
    except reader.ReaderError as exc:
        return {"status": "conflict" if exc.code == "conflict" else "failed", "reason": exc.message}, []
    return {"status": "published", "reason": None}, [f"{figures}/{name}" for name in sorted(files)]


def visual_message(visual: dict) -> str:
    status = visual["status"]
    if status == "published":
        return "시각 요약도 게시했습니다."
    if status == "rejected":
        return f"시각 요약 없음(검사 실패, 게시하지 않음): {visual['reason']}"
    if status in ("conflict", "failed"):
        return (f"시각 요약은 게시하지 않았고 기존 시각 요약은 그대로 둡니다({'충돌' if status == 'conflict' else '저장 실패'}): "
                f"{visual['reason']} 리더에서 \"시각 요약 만들기\"로 다시 만들 수 있습니다.")
    return f"시각 요약 없음: {visual['reason']} 리더에서 \"시각 요약 만들기\"로 다시 만들 수 있습니다."



def review_worker(job_id: str, slug: str, timeout: int) -> None:
    job = _start_job(job_id)
    if job is None:
        return
    generation: dict | None = None
    try:
        record_path, record = read_record(slug)
        pdf_path = safe_pdf(record)
        target = review_target(record)
        agent = runtime_status(job.get("agent"))
        if not agent["ready"]:
            raise RuntimeError(agent["reason"])
        review_roles = agent.get("review_roles") or roles.review_roles(ROOT)
        generation_role, verification_role = review_roles["generation"], review_roles["verification"]
        for resolution in (generation_role, verification_role):
            if resolution.get("configured") is None:  # never substitute or skip on an unreadable config
                raise RuntimeError(roles.unavailable_reason(resolution))
        with tempfile.TemporaryDirectory(prefix=f"paper-review-{slug}-") as tmp:
            stage = Path(tmp) / "workspace"
            live_before = snapshot(ROOT)
            clone_review_workspace(stage, pdf_path)
            before = snapshot(stage)
            prompt = generation_prompt(slug, record, generation_role.get("configured") is True)
            last_message = Path(tmp) / "last-message.md"
            result, generation = run_generation(stage, last_message, prompt, agent, generation_role, timeout)
            after = snapshot(stage)
            changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
            unexpected = sorted(name for name in changed if not allowed_output(name, record_path, target))
            if result.returncode != 0:
                raise RuntimeError(f"{generation['runner']} worker exited {result.returncode}: {(result.stderr or result.stdout)[-3000:]}")
            if unexpected:
                raise RuntimeError("staged worker changed files outside allowed outputs: " + ", ".join(unexpected[:20]))
            staged_record_path = stage / root_relative(record_path)
            updated = json.loads(staged_record_path.read_text(encoding="utf-8"))
            if updated.get("slug") != slug or updated.get("paper_id") != record.get("paper_id"):
                raise RuntimeError("staged paper JSON no longer identifies the clicked paper")
            if updated.get("source", {}).get("pdf_path") != record.get("source", {}).get("pdf_path"):
                raise RuntimeError("staged review changed the paper's canonical PDF source")
            if updated.get("structured_review_status") != "complete":
                detail = last_message.read_text(encoding="utf-8", errors="replace").strip() if last_message.is_file() else ""
                message = "paper JSON did not reach structured_review_status=complete"
                if detail:
                    message += "\n리뷰 작업자의 마지막 응답: " + detail[-3000:]
                raise RuntimeError(message)
            validation = subprocess.run([sys.executable, str(stage / ".scripts/bin/paper_record.py"), "validate", str(staged_record_path)], capture_output=True, text=True, check=False)
            if validation.returncode:
                raise RuntimeError("staged paper JSON validation failed: " + validation.stdout + validation.stderr)
            axes = updated.get("review", {})
            if len(axes) != 5 or any(not isinstance(axis, dict) or not axis.get("summary") or not axis.get("claims") for axis in axes.values()):
                raise RuntimeError("all five structured review axes need summaries and claims")
            staged_review = stage / root_relative(target)
            if not staged_review.is_file():
                raise RuntimeError("review Markdown was not created")
            review_text = staged_review.read_text(encoding="utf-8")
            if "읽은 범위" not in review_text and "읽은 구간" not in review_text:
                raise RuntimeError("review is missing its actually-read range")
            if "<!--" in review_text:
                raise RuntimeError("review still contains template instruction comments")
            if not staged_review.relative_to(stage).as_posix().startswith("01-Papers/reviews/"):
                raise RuntimeError("review path is outside the canonical reviews directory")
            if updated.get("source", {}).get("review_path") != root_relative(target).as_posix():
                raise RuntimeError("paper JSON review_path does not point to the reviewed Markdown file")
            staged_index = (stage / "01-Papers/index.md").read_text(encoding="utf-8")
            if slug not in staged_index:
                raise RuntimeError("paper index does not contain the reviewed paper slug")
            catalog = subprocess.run([sys.executable, str(stage / ".scripts/bin/paper_catalog_html.py")], cwd=stage, capture_output=True, text=True, check=False)
            if catalog.returncode:
                raise RuntimeError("catalog regeneration failed: " + catalog.stderr[-2000:])
            after = snapshot(stage)
            changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
            if "01-Papers/index.md" not in changed or "100-views/paper-library.html" not in changed:
                raise RuntimeError("index or paper catalog was not regenerated")
            # A visual summary is optional: it never rides in the canonical publish set and is
            # published by itself after it (publish_staged_visual), so it cannot fail the review.
            visual, visual_names = stage_visual(stage, target, slug, changed)
            review_sha256 = sha256_file(stage / root_relative(target))
            # Verification reports on the validated review before publishing; it never gates it.
            # Publishing reads a copy taken now, so nothing the verifier does to the stage matters.
            outcome = None
            source = stage
            if verification_role.get("configured"):
                source = preserve_outputs(stage, changed, Path(tmp) / "validated")
                visual = preserve_visual(stage, visual, visual_names, source)
                outcome = verify_stage(stage, target, pdf_path, verification_role, timeout)
            publish, sync_status = publish_review_outputs(source, changed, live_before, record_path, target)
            visual, visual_files = publish_staged_visual(source, target, record, slug, visual, live_before, {
                "job_id": job_id, "review_sha256": review_sha256, "agent": generation.get("runner"),
                "selector": generation.get("selector")})
            publish += visual_files
            verify_error = None
            if outcome is None:
                verification = verification_summary(None)
            else:
                verification, verify_error = _store_verification(slug, target, verification_role, outcome)
                if verification["report_path"]:
                    publish.append(verification["report_path"])
            title = updated.get("title") if isinstance(updated.get("title"), str) and updated["title"].strip() else slug
            wiki_files, wiki_error = refresh_wiki(" ".join(title.split()), record_path, target)
            publish += wiki_files
        message = ("리뷰 검증과 저장을 완료했습니다. 그래프 동기화도 완료했습니다." if sync_status == "success"
                   else "리뷰 검증과 저장을 완료했습니다. 그래프 동기화는 재시도 대기 중입니다.")
        if wiki_error:
            message += (" 위키 인덱스·작업 기록 갱신은 실패했습니다"
                        "(python3 .scripts/bin/wiki.py index로 다시 갱신하세요): " + wiki_error)
        message += " " + verification_message(verification, slug, verify_error)
        message += " " + visual_message(visual)
        _update_job(job_id, status="completed", completed_at=now(), changed_files=publish,
                    graphify_sync=sync_status, generation=generation, verification=verification,
                    visual=visual, message=message)
    except Exception as exc:  # preserve a retryable failure record for the UI
        fields = {"generation": generation} if generation else {}
        _update_job(job_id, status="failed", updated_at=now(), message=str(exc)[-4000:], **fields)


def verify_worker(job_id: str, slug: str, timeout: int) -> None:
    """Queue job of kind ``verify``: paper-verifier alone on an already published review."""
    if _start_job(job_id) is None:
        return
    try:
        _, record = read_record(slug)
        pdf_path = safe_pdf(record)
        target = review_target(record)
        if not target.is_file():
            raise RuntimeError("review Markdown does not exist; run the review first")
        resolution = roles.resolve(roles.VERIFICATION, ROOT)
        reason = roles.unavailable_reason(resolution) or (
            None if resolution["configured"] else "paper-verifier 역할이 설정되지 않았습니다.")
        if reason:
            raise RuntimeError(reason)
        with tempfile.TemporaryDirectory(prefix=f"paper-verify-{slug}-") as tmp:
            stage = Path(tmp) / "workspace"
            clone_review_workspace(stage, pdf_path)
            if not (stage / root_relative(target)).is_file():
                raise RuntimeError("review Markdown is not visible to the staged workspace")
            outcome = verify_stage(stage, target, pdf_path, resolution, timeout)
            verification, verify_error = _store_verification(slug, target, resolution, outcome)
        _update_job(job_id, status="failed" if verification["status"] == "error" else "completed",
                    completed_at=now(), verification=verification,
                    changed_files=[verification["report_path"]] if verification["report_path"] else [],
                    message=verification_message(verification, slug, verify_error))
    except Exception as exc:  # preserve a retryable failure record for the UI
        _update_job(job_id, status="failed", updated_at=now(), message=str(exc)[-4000:])
