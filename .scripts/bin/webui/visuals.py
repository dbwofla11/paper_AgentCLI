"""Visual summaries of paper reviews (visual-explainer pages) for the WebUI.

A visual summary is one self-contained HTML page rendered by the visual-explainer skill
(``node .visual-explainer/kit/render.mjs``, run against the job's own copy of the skill, never the
installed one: ``copy_skill``) from a finished review Markdown. Files live beside the review:

  <review dir>/figures/{slug}-visual.src.html   page source (agent output)
  <review dir>/figures/{slug}-visual.html       rendered page; the only file served
  <review dir>/figures/{slug}-visual.sheet*.png look-check contact sheets (local debugging only)
  <review dir>/figures/{slug}-visual.json       sidecar written by the server, never by an agent

It is made either by the review agent inside the staged review (``reviews.review_worker``,
sidecar ``source: "review"``) or on demand by a ``review.visual`` job run by the
``visual-designer`` role in a throwaway workspace holding only ``review.md`` (``source:
"visual-job"``). A failed visual summary never fails or unpublishes a review.

``GET /api/papers/{slug}/visual`` serves the rendered page with ``security.VISUAL_CSP`` and a fixed
bridge (``inject_bridge``): clicks on ``[data-ve-page="N"]`` post
``{type: "research-webui:visual-page", page: N}`` to the parent window, and the kit's
select-to-comment reply UI is hidden. The contract is the "시각 요약" section of
``.scripts/docs/webui-api.md``.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
import stat
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

import research_agent
from webui import reader, reviews, roles, security

JOB_KIND = "review.visual"
TIMEOUT_S = 900
MAX_BYTES = 3 * 1024 * 1024  # rendered page and its source
SHEET_MAX_BYTES = 20 * 1024 * 1024
SIDECAR_MAX_BYTES = 64 * 1024
WORKSPACE_PREFIX = "webui-visual-"
SHUTDOWN_WAIT_S = 5.0
SHUTDOWN_SIGINT_S = 2.5  # of SHUTDOWN_WAIT_S: SIGINT grace before the CLI group is SIGKILLed
SIDECAR_SCHEMA_VERSION = "1.0"
SOURCES = ("review", "visual-job")
CHECKS = ("passed", "problems", "skipped")
ACTIVE_STATUSES = frozenset({"queued", "running"})
SKILL_NAME = "visual-explainer"
# Host skill folders per runner; expanded at call time (tests may use absolute paths).
SKILL_HOMES = {"omp": Path("~/.omp/agent/skills"), "claude": Path("~/.claude/skills"),
               "codex": Path("~/.codex/skills")}
KIT_MARKERS = (b"<style data-ve-kit", b"<script data-ve-kit")  # render.mjs output evidence
FONT_LINK = ("https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;600;700"
             "&family=Noto+Serif+KR:wght@400;600&display=swap")
PAGE_MESSAGE = "research-webui:visual-page"
BRIDGE_MARKER = "data-research-webui-bridge"
BRIDGE = (
    f"<style {BRIDGE_MARKER}>.ve-bar,.ve-sel,.ve-pop,.ve-toast,dialog.ve-respond,fieldset.ask"
    "{display:none!important}[data-ve-page]{cursor:pointer}</style>"
    f"<script {BRIDGE_MARKER}>(()=>{{\"use strict\";document.addEventListener(\"click\",(e)=>{{"
    "const t=e.target instanceof Element?e.target.closest(\"[data-ve-page]\"):null;if(!t)return;"
    "e.preventDefault();e.stopPropagation();const v=t.getAttribute(\"data-ve-page\")||\"\";"
    "if(!/^[1-9][0-9]{0,5}$/.test(v)||window.parent===window)return;"
    f"window.parent.postMessage({{type:\"{PAGE_MESSAGE}\",page:Number(v)}},\"*\");}},true);}})();</script>"
).encode("utf-8")
_CHECK_LINE = re.compile(r"CHECK:\s*(passed|problems|skipped)\b")
_DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
# A missing/symlinked file or folder, or a record whose review path cannot be used.
_LOOKUP_ERRORS = (OSError, ValueError, RuntimeError, AttributeError, TypeError)
_FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC
_active_lock = threading.Lock()
_active_runs: dict[object, list] = {}  # job id -> its launched LLMRun(s), for shutdown


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _error_event(message: str, kind: str = "other") -> dict:
    return {"type": "error", "message": message, "retryable": False, "kind": kind}


# ---- serving -----------------------------------------------------------------------------------

def inject_bridge(data: bytes) -> bytes:
    """The stored page with ``BRIDGE`` inserted before its last ``</body`` (case-insensitive), or
    appended when it has none."""
    index = data.lower().rfind(b"</body")
    return data + BRIDGE if index < 0 else data[:index] + BRIDGE + data[index:]


def read_served(slug: str) -> bytes:
    """Bytes of ``GET /api/papers/{slug}/visual``: the rendered page plus the bridge. 400/404 as
    ``reader.open_paper_visual``."""
    with reader.open_paper_visual(slug) as handle:
        return inject_bridge(handle.read())


# ---- descriptor-walk file access ---------------------------------------------------------------

def _open_dir(base: Path, components: Iterable[str], *, create_last: bool = False) -> int:
    """Descriptor of ``base``/``components`` reached with ``O_DIRECTORY|O_NOFOLLOW`` per component
    (``base`` itself may be a symlink). ``create_last`` makes the last component when missing."""
    parts = list(components)
    descriptor = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        for index, component in enumerate(parts):
            if create_last and index == len(parts) - 1:
                try:
                    os.mkdir(component, 0o755, dir_fd=descriptor)
                except FileExistsError:
                    pass
            descriptor, parent = os.open(component, _DIR_FLAGS, dir_fd=descriptor), descriptor
            os.close(parent)
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _read_regular(folder: int, name: str, limit: int) -> bytes:
    """Bytes of regular file ``name`` in ``folder`` (no symlink), at most ``limit``; ValueError
    (Korean reason) otherwise."""
    try:
        handle = os.open(name, _FILE_FLAGS, dir_fd=folder)
    except FileNotFoundError:
        raise ValueError(f"{name} 파일이 없습니다") from None
    except OSError as exc:
        raise ValueError(f"{name}을 열 수 없습니다(심볼릭 링크 등): {exc.strerror or exc}") from exc
    try:
        info = os.fstat(handle)
        if not stat.S_ISREG(info.st_mode):
            raise ValueError(f"{name}은 일반 파일이 아닙니다")
        if info.st_size > limit:
            raise ValueError(f"{name}이 {limit // (1024 * 1024)} MiB를 넘습니다")
        chunks, size = [], 0
        while size <= limit:
            chunk = os.read(handle, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
    except OSError as exc:
        raise ValueError(f"{name}을 읽을 수 없습니다: {exc.strerror or exc}") from exc
    finally:
        os.close(handle)
    data = b"".join(chunks)
    if len(data) > limit:
        raise ValueError(f"{name}이 {limit // (1024 * 1024)} MiB를 넘습니다")
    return data


def _write_at(folder: int, name: str, data: bytes) -> None:
    """Atomically replace ``name`` in ``folder`` (temporary file + rename, both by descriptor)."""
    temporary = f".{name}.{secrets.token_hex(4)}.tmp"
    handle = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o644, dir_fd=folder)
    try:
        with os.fdopen(handle, "wb") as output:
            output.write(data)
        os.rename(temporary, name, src_dir_fd=folder, dst_dir_fd=folder)
    except BaseException:
        try:
            os.unlink(temporary, dir_fd=folder)
        except OSError:
            pass
        raise


def _sheet_names(folder: int, slug: str) -> list[str]:
    return sorted(name for name in os.listdir(folder)
                  if name.endswith(".png") and security.visual_output_ok(slug, name))


def _figures_dir(record: dict, *, create: bool = False) -> int:
    """Descriptor of the review's live ``figures`` folder (``reader._figure_components``); OSError
    when a component is missing or a symlink, ValueError when the review path is unusable."""
    components = reader._figure_components(record)
    if components is None:
        raise ValueError("리뷰 경로가 01-Papers/reviews 밖에 있습니다")
    return _open_dir(reviews.ROOT, components, create_last=create)


# ---- validation ----------------------------------------------------------------------------------

def checked_visual(base: Path, slug: str, components: tuple[str, ...] = ()) -> bytes:
    """Bytes of ``base``/``components``/``{slug}-visual.html``. ValueError (Korean reason) unless it
    is a regular file reached without any symlink below ``base``, 1 B..MAX_BYTES, UTF-8, contains
    both kit markers (``<style data-ve-kit``, ``<script data-ve-kit``: a render.mjs output), and has
    no ``<ve-ask``."""
    name = f"{security.visual_name(slug)}.html"
    try:
        folder = _open_dir(Path(base), components)
    except FileNotFoundError:
        raise ValueError(f"{name} 파일이 없습니다") from None
    except OSError as exc:
        raise ValueError(f"경로에 심볼릭 링크나 폴더가 아닌 항목이 있습니다: {exc.strerror or exc}") from exc
    try:
        data = _read_regular(folder, name, MAX_BYTES)
    finally:
        os.close(folder)
    if not data:
        raise ValueError(f"{name}이 빈 파일입니다")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValueError(f"{name}이 UTF-8이 아닙니다") from None
    if not all(marker in data for marker in KIT_MARKERS):
        raise ValueError(f"{name}에 visual-explainer kit 표시(<style data-ve-kit>, <script data-ve-kit>)가 없습니다"
                         "(render.mjs로 렌더한 페이지가 아닙니다)")
    if "<ve-ask" in text.lower():
        raise ValueError(f"{name}에 금지된 <ve-ask> 요소가 있습니다")
    return data


# ---- sidecar, availability and bundle ------------------------------------------------------------

def sidecar(review_sha256: str | None, source: str, job_id: str | None, meta: dict,
            check: str | None) -> dict:
    return {"schema_version": SIDECAR_SCHEMA_VERSION, "review_sha256": review_sha256, "generated_at": _now(),
            "source": source, "job_id": job_id, "agent": meta.get("agent"), "model": meta.get("model"),
            "selector": meta.get("selector"), "check": check if check in CHECKS else None}


def _sidecar_bytes(data: dict) -> bytes:
    return (json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def managed_name(slug: str, name: str) -> bool:
    """Whether ``name`` belongs to the live visual set: page, source, sheets and the sidecar."""
    return security.visual_output_ok(slug, name) or name == f"{security.visual_name(slug)}.json"


def _live_names(folder: int, slug: str) -> list[str]:
    return sorted(name for name in os.listdir(folder) if managed_name(slug, name))


def _limit(name: str) -> int:
    if name.endswith(".json"):
        return SIDECAR_MAX_BYTES
    return MAX_BYTES if name.endswith(".html") else SHEET_MAX_BYTES


def _restore(folder: int, slug: str, backup: dict[str, bytes]) -> str:
    """Put the live visual set back to ``backup``; the problems met, or ``""``."""
    problems = []
    try:
        for name in _live_names(folder, slug):
            if name not in backup:
                os.unlink(name, dir_fd=folder)
    except OSError as exc:
        problems.append(str(exc))
    for name, content in backup.items():
        try:
            _write_at(folder, name, content)
        except OSError as exc:
            problems.append(f"{name}: {exc}")
    return f" 이전 파일 복원도 일부 실패했습니다: {'; '.join(problems)}" if problems else ""


def replace_visual(record: dict, slug: str, files: dict[str, bytes], data: dict,
                   expected: dict[str, str] | None = None) -> None:
    """Make the live ``{slug}-visual.*`` set of the review's ``figures`` folder exactly ``files``
    (page written after source and sheets) plus the sidecar ``data`` (written last); every other
    member is removed. The caller serialises publishers.

    ``expected`` (live name -> sha256 of the set the caller started from; None skips the check):
    any difference -> 409 ``conflict`` before anything is written. A live member that cannot be
    read back (symlink, oversized, not a regular file) or an unusable folder -> 500
    ``publish_failed`` with nothing written. A failed write or removal restores the previous set,
    then raises 500 ``publish_failed``."""
    sidecar_name = f"{security.visual_name(slug)}.json"
    page = f"{security.visual_name(slug)}.html"
    try:
        folder = _figures_dir(record, create=True)
    except (OSError, ValueError, RuntimeError) as exc:
        raise reader.ReaderError(500, "publish_failed", f"figures 폴더를 열 수 없습니다: {exc}") from exc
    try:
        try:
            backup = {name: _read_regular(folder, name, _limit(name)) for name in _live_names(folder, slug)}
        except (OSError, ValueError) as exc:
            raise reader.ReaderError(500, "publish_failed",
                                     f"기존 시각 요약 파일을 읽지 못해 게시하지 않았습니다: {exc}") from exc
        if expected is not None:
            current = {name: hashlib.sha256(content).hexdigest() for name, content in backup.items()}
            if current != expected:
                names = sorted(name for name in current.keys() | expected.keys()
                               if current.get(name) != expected.get(name))
                raise reader.ReaderError(409, "conflict", "작업 중 라이브 시각 요약 파일이 바뀌어 게시하지 않았습니다: "
                                         + ", ".join(names))
        try:
            for name in sorted(files, key=lambda item: item == page):
                _write_at(folder, name, files[name])
            for name in _live_names(folder, slug):
                if name not in files and name != sidecar_name:
                    os.unlink(name, dir_fd=folder)
            _write_at(folder, sidecar_name, _sidecar_bytes(data))
        except OSError as exc:
            restored = _restore(folder, slug, backup)
            raise reader.ReaderError(500, "publish_failed",
                                     f"시각 요약을 저장하지 못해 이전 파일로 되돌렸습니다: {exc}.{restored}") from exc
    finally:
        os.close(folder)


def has_visual(record: dict, slug: str) -> bool:
    """Whether the rendered page ``{slug}-visual.html`` is a regular file reachable without symlinks."""
    try:
        handle = reader.open_in_figures(record, f"{security.visual_name(slug)}.html", FileNotFoundError())
    except _LOOKUP_ERRORS:
        return False
    handle.close()
    return True


def read_sidecar(record: dict, slug: str) -> dict | None:
    """The stored sidecar with each field checked (wrong types read as None); None when absent or
    unreadable."""
    try:
        handle = reader.open_in_figures(record, f"{security.visual_name(slug)}.json", FileNotFoundError())
    except _LOOKUP_ERRORS:
        return None
    try:
        with handle:
            data = json.loads(handle.read(SIDECAR_MAX_BYTES + 1).decode("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    def text(key: str, allowed: Iterable[str] | None = None) -> str | None:
        value = data.get(key)
        if not isinstance(value, str) or (allowed is not None and value not in allowed):
            return None
        return value
    return {"review_sha256": text("review_sha256"), "generated_at": text("generated_at"),
            "source": text("source", SOURCES), "check": text("check", CHECKS)}


def active_job(broker, slug: str) -> dict | None:
    """The queued/running ``review.visual`` job of ``slug`` on ``broker``, else None."""
    if broker is None:
        return None
    return next((job for job in broker.list() if job.get("kind") == JOB_KIND and job.get("slug") == slug
                 and job.get("status") in ACTIVE_STATUSES), None)


def load_visual(slug: str, record: dict, review_sha256: str | None, broker=None) -> dict:
    """``PaperBundle.visual``: ``{url, available, generated_at, review_sha256, stale, source, check,
    job}``. ``stale`` compares the sidecar's ``review_sha256`` with the current review hash; it is
    None when the page is missing or has no readable sidecar."""
    info = {"url": f"/api/papers/{slug}/visual", "available": False, "generated_at": None,
            "review_sha256": None, "stale": None, "source": None, "check": None,
            "job": active_job(broker, slug)}
    if not has_visual(record, slug):
        return info
    info["available"] = True
    stored = read_sidecar(record, slug)
    if stored is not None:
        info.update(stored)
        info["stale"] = stored["review_sha256"] != review_sha256
    return info


# ---- skill, roles and submit -----------------------------------------------------------------

def skill_dir(runner: str | None) -> Path | None:
    """Resolved ``<host skills>/visual-explainer`` for ``runner`` when it has ``SKILL.md`` and
    ``kit/render.mjs``, else None."""
    home = SKILL_HOMES.get(runner or "")
    if home is None:
        return None
    directory = Path(home).expanduser() / SKILL_NAME
    if (directory / "SKILL.md").is_file() and (directory / "kit" / "render.mjs").is_file():
        return directory.resolve()
    return None


def _copyable(directory: str, names: list[str]) -> list[str]:
    """``shutil.copytree`` ignore hook: ``.git``, symlinks and anything that is not a regular file
    or a folder are left out of the skill copy."""
    skipped = []
    for name in names:
        try:
            mode = os.lstat(os.path.join(directory, name)).st_mode
        except OSError:
            skipped.append(name)
            continue
        if name == ".git" or not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
            skipped.append(name)
    return skipped


def remove_skill_copy(root: Path) -> None:
    """Remove ``root/.visual-explainer`` (an earlier copy, or whatever an agent left there)."""
    target = Path(root) / reviews.VISUAL_SKILL_COPY
    if not os.path.lexists(target):
        return
    if stat.S_ISDIR(os.lstat(target).st_mode):
        shutil.rmtree(target)
    else:
        target.unlink()


def copy_skill(runner: str | None, root: Path) -> Path | None:
    """Copy ``skill_dir(runner)`` to ``root/.visual-explainer`` (``reviews.VISUAL_SKILL_COPY``),
    replacing an earlier copy, and return the copy; None (no copy left) when the skill is not
    installed. Agents only ever get this copy, never the installed skill, so nothing they do can
    change it; it lives and dies with the job's workspace and is never published. Only regular
    files and folders are copied (``node_modules/playwright-core`` included, so the look check
    runs); ``.git`` and symlinks are skipped. OSError when copying fails (partial copy removed)."""
    remove_skill_copy(root)
    source = skill_dir(runner)
    if source is None:
        return None
    target = Path(root) / reviews.VISUAL_SKILL_COPY
    try:
        shutil.copytree(source, target, ignore=_copyable)
    except OSError as exc:
        shutil.rmtree(target, ignore_errors=True)
        raise OSError(f"visual-explainer 스킬을 작업 공간에 복사하지 못했습니다: {exc}") from exc
    return target


def node_path() -> str | None:
    return shutil.which("node")


def unavailable_reason(runner: str | None) -> str | None:
    """Why ``runner`` cannot make a visual summary (skill or ``node`` missing), else None."""
    if skill_dir(runner) is None:
        home = SKILL_HOMES.get(runner or "")
        where = f"{home}/{SKILL_NAME}" if home is not None else f"{runner} 실행기의 스킬 폴더"
        return f"visual-explainer 스킬(SKILL.md, kit/render.mjs)을 찾지 못했습니다: {where}"
    if node_path() is None:
        return "node를 PATH에서 찾지 못했습니다(visual-explainer 렌더에 필요합니다)."
    return None


def review_queue_active(slug: str) -> bool:
    """True while the review queue has a queued/running job (review or verify) for ``slug``; an
    unreadable queue counts as active."""
    try:
        data = reviews.load_queue()
    except (OSError, ValueError):
        return True
    jobs = data.get("jobs") if isinstance(data, dict) else None
    return any(isinstance(job, dict) and job.get("slug") == slug and job.get("status") in ACTIVE_STATUSES
               for job in jobs or [])


def designer_meta(pinned: str | None) -> dict:
    """Runner facts at submit time (``{"agent", "model", "selector"}``) under the paper-searcher
    rules: unreadable config -> 503 ``role_config_error``; configured without a ready candidate ->
    503 ``designer_unavailable``; unconfigured -> the connected agent's default model."""
    resolution = roles.resolve(roles.VISUAL, reviews.ROOT)
    configured = resolution.get("configured")
    if configured is None:
        raise reader.ReaderError(503, "role_config_error",
                                 roles.unavailable_reason(resolution) or "역할 설정을 읽지 못했습니다.")
    if configured:
        candidate = roles.selected_candidate(resolution)
        if candidate is None:
            raise reader.ReaderError(503, "designer_unavailable", roles.unavailable_reason(resolution)
                                     or f"{roles.VISUAL} 역할에 준비된 후보가 없습니다.")
        call = roles.invocation(candidate)
        return {"agent": call["runner"], "model": call["model"], "selector": candidate["selector"]}
    status = research_agent.resolve(reviews.ROOT, pinned)
    if not status.get("ready") or not status.get("agent"):
        raise reader.ReaderError(503, "designer_unavailable",
                                 status.get("reason") or "연결된 에이전트가 준비되지 않았습니다.")
    return {"agent": status["agent"], "model": None, "selector": None}


def _closing() -> reader.ReaderError:
    return reader.ReaderError(503, "shutting_down", "서버가 종료 중이라 새 시각 요약 작업을 받지 않습니다.")


REVIEW_ACTIVE_MESSAGE = "이 논문의 리뷰·검증 작업이 대기 중이거나 실행 중입니다. 끝난 뒤 다시 만드세요."


def submit_visual(slug: str, broker, pinned: str | None, gate: threading.Lock) -> dict:
    """``POST /api/papers/{slug}/visual``: submit a ``review.visual`` job (``role:
    visual-designer``, ``slug``). Returns ``{"job": JobRecord}``.

    400 ``bad_request`` (slug), 404 ``not_found``, 409 ``review_missing``, 409 ``review_active``
    (review queue busy with this slug), 409 ``visual_active`` (a job for this slug is queued or
    running), 503 ``role_config_error``/``designer_unavailable``/``visual_unavailable``/
    ``shutting_down``. ``gate`` (``server.discovery_lock``, which ``server_close`` holds while it
    sets ``closing``) and ``reviews.LOCK`` (which the review-queue enqueue holds for its
    ``visual_active`` check) make the final checks and the submit one step."""
    if broker.closing.is_set():
        raise _closing()
    record = reader.paper_record(slug)
    try:
        review_present = reviews.review_target(record).is_file()
    except (OSError, RuntimeError):
        review_present = False
    if not review_present:
        raise reader.ReaderError(409, "review_missing", "리뷰 Markdown이 없습니다. 리뷰를 먼저 만드세요.")
    if review_queue_active(slug):
        raise reader.ReaderError(409, "review_active", REVIEW_ACTIVE_MESSAGE)
    meta = designer_meta(pinned)
    reason = unavailable_reason(meta["agent"])
    if reason:
        raise reader.ReaderError(503, "visual_unavailable", reason)
    with gate, reviews.LOCK:
        if broker.closing.is_set():
            raise _closing()
        if review_queue_active(slug):
            raise reader.ReaderError(409, "review_active", REVIEW_ACTIVE_MESSAGE)
        if active_job(broker, slug) is not None:
            raise reader.ReaderError(409, "visual_active", "이 논문의 시각 요약 작업이 이미 진행 중입니다.")
        job = broker.submit(JOB_KIND, {"agent": meta["agent"], "role": roles.VISUAL, "slug": slug},
                            visual_work(slug, pinned))
    return {"job": job}


# ---- the job ---------------------------------------------------------------------------------------

def build_prompt(slug: str, title: str) -> str:
    """Task prompt of a visual-summary run in a workspace holding ``review.md`` and the job's copy of
    the skill at ``./.visual-explainer`` (``copy_skill``)."""
    stem = security.visual_name(slug)
    skill = f"./{reviews.VISUAL_SKILL_COPY}"
    return "\n".join([
        f"논문 `{slug}`({title})의 완성된 심층 리뷰를 visual-explainer 스킬로 시각 요약 페이지 하나로 만든다.",
        "",
        "근거와 내용",
        "- 근거는 작업 공간의 ./review.md 하나뿐이다. PDF·다른 파일·웹을 읽지 않고, review.md에 없는 사실·수치를 넣지 않는다.",
        "- 구조: 문제 → 방법 구조 → 핵심 결과(수치 그림) → 한계·비판. 방법 구조 그림은 review.md §3.0의 \"구조도 근거\" 목록을 정본으로 다시 그린다.",
        "- 본문·라벨은 한국어, 루트는 <html lang=\"ko\" data-register=\"paper\">.",
        "- 머리(eyebrow·h1·lead)는 작고 짧게 써서 약 920×780 화면의 첫 화면에 Fig.1(방법 구조)이 보이게 한다.",
        "- 원문 쪽 근거는 review.md에 적힌 쪽 번호로 <a href=\"#\" data-ve-page=\"N\">p.N</a> 형식(N은 1 이상의 정수)으로 적는다. 출처 절은 review.md의 § 번호로 적는다.",
        f"- <head>에 Google Fonts <link rel=\"stylesheet\" href=\"{FONT_LINK}\"> 하나만 더하고, page CSS에서 레지스터 글꼴 뒤에 \"Noto Sans KR\"(본문)·\"Noto Serif KR\"(제목)을 한글 폴백으로 둔다.",
        "- page CSS에 :where(h1,h2,h3,p,li,figcaption){word-break:keep-all;overflow-wrap:break-word}를 넣는다.",
        "- 금지: <ve-ask>, 외부 링크(<a href=\"http…\">), 그 밖의 글꼴·스크립트·이미지 파일 참조, 네트워크 요청.",
        "",
        "절차",
        f"1. 작업 공간의 visual-explainer 스킬 복사본에서 {skill}/SKILL.md, {skill}/references/kit.md, "
        f"{skill}/references/style-guide.md, {skill}/references/diagrams.md를 읽는다. 복사본은 고치지 않는다.",
        f"2. ./{stem}.src.html을 쓴다.",
        f"3. 작업 공간에서 `node {skill}/kit/render.mjs {stem}.src.html`을 실행한다. ✗가 있으면 .src.html을 작은 편집으로 고쳐 다시 렌더한다(최대 3회).",
        f"4. 소스 오류로 {stem}.html이 끝내 쓰이지 않으면 ./{stem}.* 파일을 모두 지우고 실패 이유(마지막 ✗ 1–3줄)를 답한다.",
        "5. 시각 검사 문제만 남으면(페이지는 쓰임) 파일을 그대로 두고 남은 문제를 답한다. \"Visual check skipped\"는 정상이다.",
        "- review.md를 고치지 않고, 작업 공간 밖에 아무것도 쓰지 않는다.",
        "",
        "답: 결과 한 줄 요약. 마지막 줄은 정확히 `CHECK: passed`(시각 검사 통과), `CHECK: problems`(문제가 남음), "
        "`CHECK: skipped`(검사를 건너뜀) 중 하나.",
    ])


def _clear_outputs(workspace: Path, slug: str) -> None:
    """Remove earlier ``{slug}-visual.*`` outputs from the workspace root (a fallback attempt must
    not publish a previous attempt's files)."""
    for path in workspace.iterdir():
        if path.name.startswith(security.visual_name(slug) + ".") and (path.is_file() or path.is_symlink()):
            path.unlink(missing_ok=True)


def _agent_events(ctx, key: object, workspace: Path, slug: str, title: str, system: str | None,
                  pinned: str | None, seen: dict) -> Iterable[dict] | str:
    """Events of one ``visual-designer`` run in ``workspace``, or a failure message when no runner
    can start. Role rules as ``discovery._agent_events``: configured -> ``roles.walk`` over its
    candidates; unconfigured -> the connected agent's default model."""
    from webui import llm  # imported lazily: the server must start without the runner

    def run(runner: str, model: str | None, effort: str | None):
        if ctx.cancelled.is_set():
            return [{"type": "cancelled"}]
        reason = unavailable_reason(runner)
        if reason:
            return [_error_event(reason)]
        prompt = build_prompt(slug, title)
        try:
            _clear_outputs(workspace, slug)
            skill = copy_skill(runner, workspace)
            if skill is None:
                return [_error_event(unavailable_reason(runner) or "visual-explainer 스킬을 찾지 못했습니다.")]
            argv = research_agent.visual_command(
                runner, workspace, prompt, skill_dir=skill, system=system, model=model, effort=effort,
                timeout_seconds=TIMEOUT_S + llm.CLI_TIMEOUT_GRACE_S)
        except (ValueError, OSError) as exc:
            return [_error_event(str(exc))]
        call = llm.LLMRequest(prompt=prompt, cwd=workspace, agent=runner, system=system,
                              timeout_s=TIMEOUT_S, model=model, effort=effort)
        # Launch and registration are atomic with the cancellation check (see reader.ask_work).
        with _active_lock:
            if ctx.cancelled.is_set():
                return [{"type": "cancelled"}]
            try:
                started = llm.launch(runner, argv, call)
            except llm.LLMUnavailable as exc:
                return [_error_event(str(exc))]
            _active_runs.setdefault(key, []).append(started)
        ctx.on_cancel(started.cancel)
        return started.events()

    resolution = roles.resolve(roles.VISUAL, reviews.ROOT)
    if resolution.get("configured") is None:
        return roles.unavailable_reason(resolution) or "역할 설정을 읽지 못했습니다."
    if resolution.get("configured") is False:
        status = research_agent.resolve(reviews.ROOT, pinned)
        if not status.get("ready") or not status.get("agent"):
            return status.get("reason") or "연결된 에이전트가 준비되지 않았습니다."
        seen["agent"] = status["agent"]
        return run(status["agent"], None, None)

    def attempt(candidate: dict):
        call = roles.invocation(candidate)
        seen["selector"], seen["agent"], seen["model"] = candidate["selector"], call["runner"], call["model"]
        return run(call["runner"], call["model"], call["effort"])
    try:
        return roles.walk(resolution, attempt)
    except roles.RoleUnavailable as exc:
        return str(exc)


def _check(text: object) -> str | None:
    matches = _CHECK_LINE.findall(text) if isinstance(text, str) else []
    return matches[-1] if matches else None


def visual_outputs(base: Path, slug: str, components: tuple[str, ...] = ()) -> dict[str, bytes]:
    """Optional outputs beside the checked page in ``base``/``components``: the source and the look
    sheets (each a regular file without symlinks; an unusable one is skipped)."""
    folder = _open_dir(base, components)
    files: dict[str, bytes] = {}
    try:
        names = [f"{security.visual_name(slug)}.src.html", *_sheet_names(folder, slug)]
        for name in names:
            try:
                files[name] = _read_regular(folder, name, _limit(name))
            except ValueError:
                continue
    finally:
        os.close(folder)
    return files


def publish_visual(slug: str, workspace: Path, html: bytes, meta: dict) -> dict:
    """Publish a checked page (``html``) with its source and sheets from ``workspace`` into the live
    ``figures`` folder under ``reviews.LOCK`` (``replace_visual``); returns the sidecar written last.

    409 ``review_active`` when the review queue took up this slug meanwhile; 500 ``publish_failed``
    when the workspace, record, folder, or a write fails (a failed write restores the previous
    files). Old sheets missing from the new set are removed.
    ``meta``: review_sha256, job_id, agent, model, selector, check."""
    try:
        files = visual_outputs(Path(workspace), slug)
    except OSError as exc:
        raise reader.ReaderError(500, "publish_failed", f"작업 공간을 읽지 못했습니다: {exc}") from exc
    files[f"{security.visual_name(slug)}.html"] = html
    data = sidecar(meta.get("review_sha256"), "visual-job", meta.get("job_id"), meta, meta.get("check"))
    with reviews.LOCK:
        if review_queue_active(slug):
            raise reader.ReaderError(409, "review_active", REVIEW_ACTIVE_MESSAGE)
        replace_visual(reader.paper_record(slug), slug, files, data)
    return data


def _outcome(ctx, event: dict, slug: str, workspace: Path, review_sha256: str, seen: dict) -> dict:
    """Terminal event of a run whose CLI ended with ``result``: the result with a ``visual``
    sidecar, ``cancelled``, or an ``error`` of kind ``invalid_output``/``review_active``/
    ``publish_failed``. ``ctx.begin_commit()`` is the publish/cancel boundary: a cancel accepted
    before it means nothing is written; after it, cancels are refused and the job ends with this
    event."""
    try:
        html = checked_visual(workspace, slug)
    except ValueError as exc:
        return _error_event(f"시각 요약 결과가 올바르지 않습니다: {exc}. 기존 시각 요약은 그대로 둡니다.",
                            "invalid_output")
    meta = {"review_sha256": review_sha256, "job_id": getattr(ctx, "job_id", None), "agent": seen.get("agent"),
            "model": seen.get("model"), "selector": seen.get("selector"), "check": _check(event.get("text"))}
    if not ctx.begin_commit():
        return {"type": "cancelled"}
    try:
        stored = publish_visual(slug, workspace, html, meta)
    except reader.ReaderError as exc:
        kind = "review_active" if exc.code == "review_active" else "publish_failed"
        return _error_event(exc.message, kind)
    return {**event, "visual": stored}


def visual_work(slug: str, pinned: str | None) -> Callable:
    """Work function of a ``review.visual`` job (TIMEOUT_S): the agent renders the page in a
    throwaway workspace holding ``review.md`` and its own skill copy; ``publish_visual`` runs before
    the terminal event, so a client refetching the bundle on it sees the new page. A job cancelled
    before ``ctx.begin_commit()`` publishes nothing; once it committed, it cannot be cancelled."""
    def work(ctx) -> None:
        seen = {"agent": None, "model": None, "selector": None, "done": False}
        key = getattr(ctx, "job_id", None) or id(ctx)

        def finish(event: dict) -> None:
            if not seen["done"]:
                seen["done"] = True
                ctx.emit(event)

        def fail(message: str, kind: str = "other") -> None:
            finish(_error_event(message, kind))

        try:
            if ctx.cancelled.is_set():
                finish({"type": "cancelled"})
                return
            with tempfile.TemporaryDirectory(prefix=WORKSPACE_PREFIX) as directory:
                workspace = Path(directory)
                try:
                    record = reader.paper_record(slug)
                    review = reviews.review_target(record).read_bytes()
                    _, system = roles.agent_definition(roles.VISUAL, reviews.ROOT)
                except reader.ReaderError as exc:
                    fail(exc.message)
                    return
                except (OSError, ValueError, RuntimeError) as exc:
                    fail(f"시각 요약 작업 공간을 준비하지 못했습니다: {exc}")
                    return
                (workspace / "review.md").write_bytes(review)
                title = " ".join(str(record.get("title") or slug).split())[:300]
                events = _agent_events(ctx, key, workspace, slug, title, reader.clean_text(system) or None,
                                       pinned, seen)
                if isinstance(events, str):
                    fail(events)
                    return
                review_sha256 = hashlib.sha256(review).hexdigest()
                for event in events:
                    event_type = event.get("type")
                    if event_type == "result":
                        finish(_outcome(ctx, event, slug, workspace, review_sha256, seen))
                    elif event_type in ("error", "cancelled"):
                        finish(event)
                    else:
                        ctx.emit(event)
        except Exception as exc:
            fail(f"{type(exc).__name__}: {exc}"[-2000:])
            raise
        finally:
            with _active_lock:
                _active_runs.pop(key, None)
            if not seen["done"]:
                fail("시각 요약 작업이 결과 없이 끝났습니다.")
    return work


def shutdown(broker, timeout: float = SHUTDOWN_WAIT_S) -> bool:
    """Stop ``review.visual`` jobs on ``broker``: set ``closing``, cancel every queued/running one,
    and wait (≤ ``timeout`` s) until their work functions returned (workspace removed). A cancelled
    job publishes nothing; one already publishing (``begin_commit``) refuses the cancel and is
    waited for. CLIs still running after SHUTDOWN_SIGINT_S get their process group SIGKILLed.
    False when some job did not finish in time."""
    deadline = time.monotonic() + timeout
    broker.closing.set()
    jobs_now = [job for job in broker.list() if job.get("kind") == JOB_KIND]
    for job in jobs_now:
        if job.get("status") in ACTIVE_STATUSES:
            broker.cancel(job["job_id"])
    ids = [job["job_id"] for job in jobs_now]
    if broker.wait_finished(ids, min(SHUTDOWN_SIGINT_S, timeout)):
        return True
    with _active_lock:
        for job_id in ids:
            for run in _active_runs.get(job_id, ()):
                run.terminate()
    return broker.wait_finished(ids, max(0.0, deadline - time.monotonic()))
