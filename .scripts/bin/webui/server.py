"""Localhost WebUI HTTP server: static views, paper review API, jobs with SSE streams.

Binds 127.0.0.1 only. Every request passes the guards in ``webui.security`` first; the
HTTP/SSE contract is documented in ``.scripts/docs/webui-api.md``. Repository paths and
review functions are read through ``reviews.<name>`` at request time so tests can patch them.
"""
from __future__ import annotations

import collections
import email.utils
import hashlib
import http.server
import json
import mimetypes
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Callable

import harness_dashboard
import research_agent
import thought_experiments_html
from webui import jobs, reader, reviews, roles, security

VERSION = "webui-m0"
WEBUI_HOME = "/100-views/webui/"
LEGACY_PAGES = frozenset({"/paper-library.html", "/harness-dashboard.html", "/thought-experiments.html"})
PING_PROMPT = "Reply with exactly: OK"
PING_TIMEOUT_S = 120
JOB_KINDS = frozenset({"agent.ping"})
PING_ROLES = (roles.GENERATION, roles.VERIFICATION)
HARNESS_CHECK_KINDS = {"verify": "harness.verify", "tests": "harness.tests"}
HARNESS_CHECK_TIMEOUT_S = {"verify": 300, "tests": 1800}
HARNESS_KILL_GRACE_S = 2.5     # after SIGTERM, how long the check's process group may take to vanish
HARNESS_KILL_WAIT_S = 1.0      # after SIGKILL, how long to wait for the group to vanish
HARNESS_GROUP_POLL_S = 0.05
HARNESS_SHUTDOWN_WAIT_S = 5.0  # server_close waits this long for cancelled checks to end
HARNESS_OUTPUT_LIMIT = 256 * 1024  # UTF-8 bytes: result.text tail and total streamed text_delta text
HARNESS_CHUNK_CHARS = 2048     # characters per read, so one text_delta is at most 8 KiB of UTF-8
HARNESS_ERROR_TAIL = 2000  # characters of output appended to a failure message
HARNESS_STREAM_NOTICE = "\n[실시간 출력이 256 KiB 상한에 도달해 표시를 멈춥니다. 검사는 계속 실행됩니다.]\n"
DISCONNECTS = (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError)
DISCARD_LIMIT = 1024 * 1024  # largest rejected body drained before the connection closes
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8", ".htm": "text/html; charset=utf-8",
    ".js": "text/javascript; charset=utf-8", ".mjs": "text/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8", ".webmanifest": "application/manifest+json",
    ".md": "text/markdown; charset=utf-8", ".txt": "text/plain; charset=utf-8",
    ".csv": "text/csv; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png",
    ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp",
    ".ico": "image/x-icon", ".pdf": "application/pdf", ".woff2": "font/woff2", ".woff": "font/woff",
    ".ttf": "font/ttf", ".otf": "font/otf", ".wasm": "application/wasm", ".zip": "application/zip",
}
API_ROUTES = (
    (re.compile(r"/api/session"), {"GET": "session"}),
    (re.compile(r"/api/status"), {"GET": "status"}),
    (re.compile(r"/api/reviews"), {"POST": "create_review"}),
    (re.compile(r"/api/reviews/([^/]+)"), {"GET": "review_jobs"}),
    (re.compile(r"/api/reviews/([^/]+)/verify"), {"POST": "verify_review"}),
    (re.compile(r"/api/jobs"), {"GET": "list_jobs", "POST": "create_job"}),
    (re.compile(r"/api/jobs/([^/]+)"), {"GET": "get_job"}),
    (re.compile(r"/api/jobs/([^/]+)/events"), {"GET": "job_events"}),
    (re.compile(r"/api/jobs/([^/]+)/cancel"), {"POST": "cancel_job"}),
    (re.compile(r"/api/papers"), {"GET": "list_papers"}),
    (re.compile(r"/api/papers/([^/]+)"), {"GET": "paper"}),
    (re.compile(r"/api/papers/([^/]+)/pdf"), {"GET": "paper_pdf"}),
    (re.compile(r"/api/papers/([^/]+)/threads"), {"GET": "paper_threads"}),
    (re.compile(r"/api/papers/([^/]+)/threads/([^/]+)"), {"DELETE": "delete_thread"}),
    (re.compile(r"/api/papers/([^/]+)/ask"), {"POST": "ask_paper"}),
    (re.compile(r"/api/reader/status"), {"GET": "reader_status"}),
    (re.compile(r"/api/harness"), {"GET": "harness"}),
    (re.compile(r"/api/harness/checks"), {"POST": "harness_check"}),
    (re.compile(r"/api/ideas"), {"GET": "ideas"}),
)


def workspace_id() -> str:
    """Stable id of this repository checkout; onboarding uses it to detect port reuse."""
    return hashlib.sha256(str(reviews.ROOT.resolve()).encode()).hexdigest()[:16]


def content_type(path: Path) -> str:
    known = CONTENT_TYPES.get(path.suffix.lower())
    if known:
        return known
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or "application/octet-stream"


IDEA_PATH_FIELDS = ("note", "brief", "results", "todo", "manifest", "analysis")
IDEA_PATH_LISTS = ("critiques", "evidence", "paperPaths", "artifacts", "todoResults")


def ideas_data(root: Path) -> dict:
    """``GET /api/ideas`` payload: ``thought_experiments_html.scan`` records, the URL of every
    referenced path the static-file policy would serve (else None), and data faults. Malformed
    registry/queue/analysis files degrade inside ``scan``; any other failure empties the list.
    This never raises for faulty repository data."""
    errors: list[dict] = []
    try:
        ideas = thought_experiments_html.scan(root, errors)
    except Exception as exc:  # unexpected faults are reported, never a 500
        return {"ideas": [], "hrefs": {},
                "errors": [*errors, {"section": "ideas", "error": f"{type(exc).__name__}: {exc}"[:500]}]}
    try:
        paths: set[str] = set()
        for idea in ideas:
            values = [idea.get(field) for field in IDEA_PATH_FIELDS]
            values += [path for field in IDEA_PATH_LISTS if isinstance(idea.get(field), list) for path in idea[field]]
            paths.update(value for value in values if isinstance(value, str) and value)
        hrefs = {path: static_href(root, path) for path in sorted(paths)}
    except Exception as exc:
        errors.append({"section": "hrefs", "error": f"{type(exc).__name__}: {exc}"[:500]})
        hrefs = {}
    return {"ideas": ideas, "hrefs": hrefs, "errors": errors}


def static_href(root: Path, relative: str) -> str | None:
    """URL of repository path ``relative`` when ``security.resolve_static`` would serve it, else None."""
    url = "/" + urllib.parse.quote(relative)
    served = security.resolve_static(root, url, reviews.ALLOWED_ROOTS, reviews.ALLOWED_ROOT_FILES)
    return url if served is not None else None


def agent_ping_work(agent: str | None, root: Path) -> Callable[[jobs.JobContext], None]:
    """Work function for ``agent.ping``: one tool-less prompt, every LLM event forwarded."""
    def work(ctx: jobs.JobContext) -> None:
        from webui import llm  # imported lazily: the server must start without the runner

        if ctx.cancelled.is_set():
            ctx.emit({"type": "cancelled"})
            return
        with tempfile.TemporaryDirectory(prefix="webui-agent-ping-") as directory:
            request = llm.LLMRequest(prompt=PING_PROMPT, cwd=Path(directory), agent=agent,
                                     tools=(), timeout_s=PING_TIMEOUT_S)
            try:
                run = llm.start(request, root)
            except llm.LLMUnavailable as exc:
                ctx.emit({"type": "error", "message": str(exc), "retryable": False, "kind": "other"})
                return
            ctx.on_cancel(run.cancel)
            for event in run.events():
                ctx.emit(event)
    return work


def role_ping_agent(role: str, root: Path, pinned: str | None) -> str | None:
    """Runner a role ping will use: the selected candidate, or the connected agent for a genuinely
    unconfigured paper-analyst (pre-existing generation behavior). None when it cannot run."""
    resolution = roles.resolve(role, root)
    if resolution["configured"] is False:
        return pinned if role == roles.GENERATION else None
    candidate = roles.selected_candidate(resolution) if resolution["configured"] else None
    return candidate["runner"] if candidate else None


def role_ping_work(role: str, root: Path, pinned: str | None) -> Callable[[jobs.JobContext], None]:
    """Work function for ``agent.ping`` with ``role``: the role's candidates, walked by ``roles.walk``."""
    def work(ctx: jobs.JobContext) -> None:
        from webui import llm  # imported lazily: the server must start without the runner

        if ctx.cancelled.is_set():
            ctx.emit({"type": "cancelled"})
            return
        resolution = roles.resolve(role, root)
        if resolution["configured"] is False and role == roles.GENERATION:
            agent_ping_work(pinned, root)(ctx)
            return
        with tempfile.TemporaryDirectory(prefix="webui-agent-ping-") as directory:
            def run(candidate: dict):
                call = roles.invocation(candidate)
                request = llm.LLMRequest(prompt=PING_PROMPT, cwd=Path(directory), agent=call["runner"],
                                         tools=(), timeout_s=PING_TIMEOUT_S, model=call["model"],
                                         effort=call["effort"])
                try:
                    started = llm.start(request, root)
                except llm.LLMUnavailable as exc:
                    return [{"type": "error", "message": str(exc), "retryable": False, "kind": "other"}]
                ctx.on_cancel(started.cancel)
                return started.events()
            try:
                events = roles.walk(resolution, run)
            except roles.RoleUnavailable as exc:
                ctx.emit({"type": "error", "message": str(exc), "retryable": False, "kind": "other"})
                return
            for event in events:
                ctx.emit(event)
    return work


def _signal_group(pid: int, sig: int) -> None:
    try:
        os.killpg(pid, sig)
    except (ProcessLookupError, PermissionError):
        pass


def _group_alive(pgid: int) -> bool:
    """True while any process of group ``pgid`` exists (``killpg(pgid, 0)`` succeeds)."""
    try:
        os.killpg(pgid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    return True


def _wait_group_gone(pgid: int, seconds: float) -> bool:
    deadline = time.monotonic() + seconds
    while _group_alive(pgid):
        if time.monotonic() >= deadline:
            return False
        time.sleep(HARNESS_GROUP_POLL_S)
    return True


def _end_group(pgid: int) -> None:
    """SIGTERM the whole group, wait up to HARNESS_KILL_GRACE_S for every member (not just the
    leader) to vanish, then SIGKILL the group and wait up to HARNESS_KILL_WAIT_S more."""
    _signal_group(pgid, signal.SIGTERM)
    if not _wait_group_gone(pgid, HARNESS_KILL_GRACE_S):
        _signal_group(pgid, signal.SIGKILL)
        _wait_group_gone(pgid, HARNESS_KILL_WAIT_S)


def harness_check_work(check: str, root: Path) -> Callable[[jobs.JobContext], None]:
    """Work function for ``harness.<check>``: one fixed command (``harness_dashboard.check_command``)
    in its own process group. Output is read in pieces of at most HARNESS_CHUNK_CHARS characters
    and forwarded as ``text_delta`` until HARNESS_OUTPUT_LIMIT bytes were streamed; the last
    HARNESS_OUTPUT_LIMIT bytes are kept for the terminal event. Cancel and timeout end the whole
    process group (``_end_group``) before the terminal event is emitted."""
    label = harness_dashboard.CHECK_LABELS[check]

    def work(ctx: jobs.JobContext) -> None:
        if ctx.cancelled.is_set():
            ctx.emit({"type": "cancelled"})
            return
        timeout = HARNESS_CHECK_TIMEOUT_S[check]
        started = time.monotonic()
        try:
            proc = subprocess.Popen(
                harness_dashboard.check_command(check, root), cwd=root, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace",
                start_new_session=True, env={**os.environ, "PYTHONUNBUFFERED": "1"})
        except OSError as exc:
            ctx.emit({"type": "error", "message": f"{label} 실행 실패: {exc}", "retryable": True,
                      "kind": "process"})
            return
        finished = threading.Event()  # output drained and the leader reaped
        stopped = threading.Event()   # _end_group returned
        stop_lock = threading.Lock()
        state = {"stopping": False, "timed_out": False, "reaped": False}

        def stop(timed_out: bool = False) -> None:
            with stop_lock:
                if state["stopping"] or state["reaped"]:
                    return  # already ending, or the run is over: never signal a reaped group id
                state["stopping"], state["timed_out"] = True, timed_out

            def end() -> None:
                try:
                    _end_group(proc.pid)
                finally:
                    stopped.set()
            threading.Thread(target=end, name=f"webui-harness-stop-{ctx.job_id}", daemon=True).start()

        def watch() -> None:
            if not finished.wait(timeout) and not ctx.cancelled.is_set():
                stop(timed_out=True)

        ctx.on_cancel(stop)
        threading.Thread(target=watch, name=f"webui-harness-timeout-{ctx.job_id}", daemon=True).start()
        kept: collections.deque[tuple[str, int]] = collections.deque()  # (piece, UTF-8 size)
        kept_bytes = streamed = 0
        streaming = True
        notice_bytes = len(HARNESS_STREAM_NOTICE.encode("utf-8"))
        drained = False
        try:
            for piece in iter(lambda: proc.stdout.readline(HARNESS_CHUNK_CHARS), ""):
                size = len(piece.encode("utf-8"))
                if streaming and streamed + size <= HARNESS_OUTPUT_LIMIT - notice_bytes:
                    ctx.emit({"type": "text_delta", "text": piece})
                    streamed += size
                elif streaming:
                    ctx.emit({"type": "text_delta", "text": HARNESS_STREAM_NOTICE})
                    streamed += notice_bytes
                    streaming = False
                kept.append((piece, size))
                kept_bytes += size
                while kept_bytes - kept[0][1] >= HARNESS_OUTPUT_LIMIT:
                    kept_bytes -= kept.popleft()[1]
            drained = True
        finally:
            if not drained:  # the work itself failed: never leave the group running
                _signal_group(proc.pid, signal.SIGKILL)
            proc.stdout.close()
            code = proc.wait()
            with stop_lock:
                state["reaped"] = True
                stopping = state["stopping"]
            finished.set()
        if stopping:
            stopped.wait()  # the whole group is gone (or SIGKILLed) before the terminal event
        output = "".join(piece for piece, _ in kept).encode("utf-8")[-HARNESS_OUTPUT_LIMIT:]
        output = output.decode("utf-8", errors="ignore")
        tail = output[-HARNESS_ERROR_TAIL:].rstrip()
        if ctx.cancelled.is_set():
            ctx.emit({"type": "cancelled"})
        elif state["timed_out"]:
            message = f"{label} 시간 초과 ({timeout:g}초)" + (f"\n{tail}" if tail else "")
            ctx.emit({"type": "error", "message": message, "retryable": True, "kind": "timeout"})
        elif code == 0:
            ctx.emit({"type": "result", "text": output, "cost_usd": None, "usage": None,
                      "duration_ms": int((time.monotonic() - started) * 1000)})
        else:
            message = f"{label} 실패 (exit {code})" + (f"\n{tail}" if tail else "")
            ctx.emit({"type": "error", "message": message, "retryable": True, "kind": "process"})
    return work


def is_harness_job(job: dict) -> bool:
    return str(job.get("kind") or "").startswith("harness.")


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "ResearchWebUI/0.1"
    sys_version = ""
    timeout = 60  # socket timeout for slow or stalled clients
    server: "WebUIServer"
    _route = ""   # percent-decoded path of the current request, for response headers
    _response_started = False

    # -- connection plumbing ----------------------------------------------------
    def handle(self) -> None:
        try:
            super().handle()
        except DISCONNECTS:  # the browser went away; nothing to report
            self.close_connection = True

    def send_response(self, code: int, message: str | None = None) -> None:
        self._response_started = True
        super().send_response(code, message)

    def end_headers(self) -> None:
        for name, value in security.response_headers(self._route):
            self.send_header(name, value)
        super().end_headers()

    def send_error(self, code: int, message: str | None = None, explain: str | None = None) -> None:
        """JSON error bodies for errors raised by the stdlib request parser too."""
        phrase = self.responses.get(code, ("Error",))[0]
        self.log_error("code %d, message %s", code, message or phrase)
        self.close_connection = True
        self._error(code, security.error_code(code), message or phrase, close=True)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write((fmt % args) + "\n")

    def do_GET(self) -> None:
        self._dispatch()

    do_HEAD = do_POST = do_PUT = do_PATCH = do_DELETE = do_OPTIONS = do_GET

    def __getattr__(self, name: str):
        """Any other method token (TRACE, CONNECT, ...) also passes the Host guard first.

        ``BaseHTTPRequestHandler`` answers a method without a ``do_<METHOD>`` attribute with a
        bare 501 before any guard runs; resolving every ``do_*`` lookup to ``_dispatch`` keeps
        guard order and the JSON 403/404/405 errors uniform for all methods.
        """
        if name.startswith("do_"):
            return self._dispatch
        raise AttributeError(name)

    # -- responses -------------------------------------------------------------
    def _json(self, status: int, payload: dict, headers: tuple[tuple[str, str], ...] = ()) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _error(self, status: int, code: str, message: str, *, allow: str | None = None,
               close: bool = False) -> None:
        headers = []
        if allow:
            headers.append(("Allow", allow))
        if close:
            headers.append(("Connection", "close"))
        self._json(status, {"error": message, "code": code}, tuple(headers))

    def _redirect(self, location: str, status: int = 302) -> None:
        self.send_response(status)
        self.send_header("Location", location)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _discard_body(self) -> None:
        """Read a rejected request body (bounded) so closing the socket does not reset the reply."""
        if self.headers.get("Transfer-Encoding"):
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return
        if 0 < length <= DISCARD_LIMIT:
            self.rfile.read(length)

    # -- routing ---------------------------------------------------------------
    def _dispatch(self) -> None:
        split = urllib.parse.urlsplit(self.path)
        path = split.path
        self._route = urllib.parse.unquote(path, errors="replace")
        method = self.command
        payload: dict = {}
        body_read = False
        try:
            host = security.check_host(self.headers, self.server.server_port)
            if method in security.STATE_CHANGING_METHODS:
                security.check_state_change(self.headers, host, self.server.csrf_token)
                security.check_content_type(self.headers)
                length = security.content_length(self.headers, security.body_limit(path))
                body = self.rfile.read(length) if length else b""
                body_read = True
                payload = security.parse_json(body)
        except security.GuardError as exc:
            if not body_read:
                self._discard_body()
            self.close_connection = True
            self._error(exc.status, exc.code, exc.message, close=True)
            return
        if method not in {"GET", "HEAD"} and method not in security.STATE_CHANGING_METHODS:
            # OPTIONS, TRACE, CONNECT or any other token: its body is never read, so drain it
            # and close instead of leaving unread bytes on the connection.
            self._discard_body()
            self.close_connection = True
        if path == "/api" or path.startswith("/api/"):
            self._dispatch_api(method, path, split.query, payload)
        elif method not in {"GET", "HEAD"}:
            self._error(405, "method_not_allowed", f"{method} is not allowed here", allow="GET, HEAD")
        elif path == "/":
            self._redirect(WEBUI_HOME)
        elif path in LEGACY_PAGES:
            self._redirect("/100-views" + path)
        else:
            self._serve_static(path, split.query)

    def _dispatch_api(self, method: str, path: str, query: str, payload: dict) -> None:
        for pattern, methods in API_ROUTES:
            match = pattern.fullmatch(path)
            if match is None:
                continue
            name = methods.get(method)
            if name is None:
                self._error(405, "method_not_allowed", f"{method} is not allowed on {path}",
                            allow=", ".join(methods))
                return
            self._response_started = False
            try:
                getattr(self, "_api_" + name)(match.groups(), query, payload)
            except DISCONNECTS:
                raise
            except Exception as exc:  # report instead of dropping the connection silently
                self.log_error("%s %s failed: %r", method, path, exc)
                if self._response_started:
                    raise
                self._error(500, "internal_error", f"{type(exc).__name__}: {exc}"[-1000:], close=True)
            return
        self._error(404, "not_found", "unknown endpoint")

    # -- static files ----------------------------------------------------------
    def _resolve(self, path: str) -> Path | None:
        return security.resolve_static(reviews.ROOT, path, reviews.ALLOWED_ROOTS, reviews.ALLOWED_ROOT_FILES)

    def _serve_static(self, path: str, query: str) -> None:
        target = self._resolve(path)
        if target is not None and target.is_dir():
            if not path.endswith("/"):
                self._redirect(path + "/" + (f"?{query}" if query else ""), status=301)
                return
            target = self._resolve(path + "index.html")  # no directory listings
        if target is None or not target.is_file():
            self._error(404, "not_found", "file not found")
            return
        try:
            handle = target.open("rb")
        except OSError:
            self._error(404, "not_found", "file not found")
            return
        self._send_file(handle, content_type(target))

    def _send_file(self, handle, media_type: str) -> None:
        """Stream an open binary file (closed afterwards) with its length and modification time."""
        with handle:
            stat = os.fstat(handle.fileno())
            self.send_response(200)
            self.send_header("Content-Type", media_type)
            self.send_header("Content-Length", str(stat.st_size))
            self.send_header("Last-Modified", email.utils.formatdate(stat.st_mtime, usegmt=True))
            self.end_headers()
            if self.command != "HEAD":
                shutil.copyfileobj(handle, self.wfile, 64 * 1024)

    # -- API: session and status -----------------------------------------------
    def _pinned_agent(self) -> str | None:
        """Agent fixed at launch (onboarding or ``serve --agent``); None reads the saved connection."""
        status = self.server.agent_status
        return status.get("agent") if isinstance(status, dict) else None

    def _api_session(self, args: tuple, query: str, payload: dict) -> None:
        self._json(200, {"csrf_token": self.server.csrf_token, "workspace_id": workspace_id(),
                         "port": self.server.server_port, "version": VERSION})

    def _api_status(self, args: tuple, query: str, payload: dict) -> None:
        status = reviews.runtime_status(self._pinned_agent())
        self._json(200, {"ok": True, "workspace_id": workspace_id(), **status,
                         "runner": research_agent.RUNNERS.get(status.get("agent")), "pdf_reader": "pdftotext",
                         "max_parallel": reviews.MAX_JOBS, "queue": reviews.load_queue(),
                         "reader_role": roles.resolve(roles.READER, reviews.ROOT)})

    # -- API: paper reader -----------------------------------------------------
    def _reader_error(self, exc: reader.ReaderError) -> None:
        self._error(exc.status, exc.code, exc.message)

    def _api_list_papers(self, args: tuple, query: str, payload: dict) -> None:
        self._json(200, reader.list_papers(self.server.broker))

    def _api_paper(self, args: tuple, query: str, payload: dict) -> None:
        try:
            bundle = reader.paper_bundle(args[0])
        except reader.ReaderError as exc:
            self._reader_error(exc)
            return
        self._json(200, bundle)

    def _api_paper_pdf(self, args: tuple, query: str, payload: dict) -> None:
        try:
            handle = reader.paper_pdf(args[0]).open("rb")
        except reader.ReaderError as exc:
            self._reader_error(exc)
            return
        except OSError:
            self._error(409, "pdf_missing", "저장소 PDF를 열 수 없습니다.")
            return
        self._send_file(handle, "application/pdf")

    def _api_paper_threads(self, args: tuple, query: str, payload: dict) -> None:
        try:
            reader.paper_record(args[0])
            body = reader.load_threads(args[0], self.server.broker)
        except reader.ReaderError as exc:
            self._reader_error(exc)
            return
        self._json(200, body)

    def _api_delete_thread(self, args: tuple, query: str, payload: dict) -> None:
        slug, thread_id = args
        try:
            reader.paper_record(slug)
            if not reader.THREAD_ID_PATTERN.fullmatch(thread_id):
                raise reader.ReaderError(400, "bad_request", "thread_id는 t_<12자리 16진수>여야 합니다.")
            body = reader.delete_thread(slug, thread_id, self.server.broker)
        except reader.ReaderError as exc:
            self._reader_error(exc)
            return
        self._json(200, body)

    def _api_ask_paper(self, args: tuple, query: str, payload: dict) -> None:
        try:
            body = reader.submit_ask(args[0], payload, self.server.broker, self._pinned_agent())
        except reader.ReaderError as exc:
            self._reader_error(exc)
            return
        self._json(202, body)

    def _api_reader_status(self, args: tuple, query: str, payload: dict) -> None:
        self._json(200, reader.reader_status(self._pinned_agent()))

    # -- API: harness ----------------------------------------------------------
    def _api_harness(self, args: tuple, query: str, payload: dict) -> None:
        self._json(200, harness_dashboard.dashboard_data(reviews.ROOT))

    def _api_harness_check(self, args: tuple, query: str, payload: dict) -> None:
        check = payload.get("check")
        if not isinstance(check, str) or check not in HARNESS_CHECK_KINDS:
            self._error(400, "bad_request", "check must be one of: " + ", ".join(HARNESS_CHECK_KINDS))
            return
        broker = self.server.broker
        with self.server.harness_lock:  # single flight: the active check and submit are one step
            if broker.closing.is_set():
                record = None
                refusal = (503, "shutting_down", "server is shutting down")
            elif any(is_harness_job(job) and job.get("status") in {"queued", "running"} for job in broker.list()):
                record = None
                refusal = (409, "check_active", "another harness check is already active")
            else:
                record = broker.submit(HARNESS_CHECK_KINDS[check], {},
                                       harness_check_work(check, reviews.ROOT))
        if record is None:
            self._error(*refusal)
            return
        self._json(202, {"job": record})

    # -- API: thought experiments ----------------------------------------------
    def _api_ideas(self, args: tuple, query: str, payload: dict) -> None:
        self._json(200, ideas_data(reviews.ROOT))

    # -- API: paper reviews ----------------------------------------------------
    def _api_review_jobs(self, args: tuple, query: str, payload: dict) -> None:
        slug = args[0]
        data = reviews.load_queue()
        body: dict = {"jobs": [job for job in data["jobs"] if job.get("slug") == slug]}
        try:
            verification = reviews.load_verification(slug)
        except (ValueError, OSError):  # invalid slug or unreadable report: nothing to show
            verification = None
        if verification is not None:
            body["verification"] = verification
        self._json(200, body)

    def _enqueue_review_job(self, slug: str, agent: str | None, kind: str | None = None) -> dict | None:
        """Append a queued review-queue job unless one is already queued or running.

        Review jobs carry no ``kind``; verify-only jobs carry ``kind: "verify"``.
        """
        with reviews.LOCK:
            data = reviews.load_queue()
            if any(item.get("status") in {"queued", "running"} for item in data["jobs"]):
                return None
            job_id = hashlib.sha256(f"{slug}:{time.time_ns()}".encode()).hexdigest()[:16]
            job = {"job_id": job_id, **({"kind": kind} if kind else {}), "slug": slug,
                   "record": str(reviews.root_relative(reviews.LIBRARY / f"{slug}.json")),
                   "status": "queued", "agent": agent, "created_at": reviews.now(), "message": "accepted"}
            data["jobs"].append(job)
            reviews.save_queue(data)
            return job

    def _api_create_review(self, args: tuple, query: str, payload: dict) -> None:
        try:
            slug = payload.get("slug", "")
            if not isinstance(slug, str):
                raise ValueError("invalid paper slug")
            _, record = reviews.read_record(slug)
            target = reviews.review_target(record)
            if not reviews.needs_review(record, target):
                self._error(409, "review_complete", "review is already complete")
                return
            reviews.safe_pdf(record)
            status = reviews.runtime_status(self._pinned_agent())
            if not status["ready"]:
                self._error(503, "agent_unavailable", status["reason"])
                return
            job = self._enqueue_review_job(slug, agent=reviews.review_agent(status))
            if job is None:
                self._error(409, "review_active", "another paper review is already active")
                return
            threading.Thread(target=reviews.review_worker, args=(job["job_id"], slug, self.server.review_timeout),
                             daemon=True).start()
            self._json(202, {"job": job})
        except (ValueError, OSError) as exc:
            self._error(400, "bad_request", str(exc))

    def _api_verify_review(self, args: tuple, query: str, payload: dict) -> None:
        slug = args[0]
        try:
            _, record = reviews.read_record(slug)
            target = reviews.review_target(record)
        except (ValueError, OSError) as exc:
            self._error(400, "bad_request", str(exc))
            return
        if not target.is_file():
            self._error(409, "review_missing", "review Markdown does not exist; run the review first")
            return
        try:
            reviews.safe_pdf(record)
        except ValueError as exc:
            self._error(409, "pdf_missing", str(exc))
            return
        resolution = roles.resolve(roles.VERIFICATION, reviews.ROOT)
        if resolution["configured"] is None:
            self._error(503, "role_config_error", roles.unavailable_reason(resolution))
            return
        if not resolution["configured"]:
            self._error(409, "verifier_unconfigured",
                        "paper-verifier is not configured in task.agentModelOverrides (.omp/config.yml)")
            return
        reason = roles.unavailable_reason(resolution)
        if reason:
            self._error(503, "verifier_unavailable", reason)
            return
        job = self._enqueue_review_job(slug, kind="verify", agent=roles.selected_candidate(resolution)["runner"])
        if job is None:
            self._error(409, "review_active", "another paper review is already active")
            return
        threading.Thread(target=reviews.verify_worker, args=(job["job_id"], slug, self.server.review_timeout),
                         daemon=True).start()
        self._json(202, {"job": job})

    # -- API: jobs ---------------------------------------------------------------
    def _api_list_jobs(self, args: tuple, query: str, payload: dict) -> None:
        self._json(200, {"jobs": self.server.broker.list()})

    def _api_create_job(self, args: tuple, query: str, payload: dict) -> None:
        kind = payload.get("kind")
        if not isinstance(kind, str) or kind not in JOB_KINDS:
            self._error(400, "bad_request", "unsupported job kind; expected agent.ping")
            return
        agent, role = payload.get("agent"), payload.get("role")
        if agent is not None and role is not None:
            self._error(400, "bad_request", "agent and role are mutually exclusive")
            return
        if role is not None:
            if not isinstance(role, str) or role not in PING_ROLES:
                self._error(400, "bad_request", "role must be one of: " + ", ".join(PING_ROLES))
                return
            pinned = self._pinned_agent()
            runner = role_ping_agent(role, reviews.ROOT, pinned)
            record = self.server.broker.submit(kind, {"agent": runner, "role": role},
                                               role_ping_work(role, reviews.ROOT, pinned))
            self._json(202, {"job": record})
            return
        if agent is not None and (not isinstance(agent, str) or agent not in research_agent.AGENTS):
            self._error(400, "bad_request", "agent must be one of: " + ", ".join(research_agent.AGENTS))
            return
        agent = agent or self._pinned_agent()
        record = self.server.broker.submit(kind, {"agent": agent}, agent_ping_work(agent, reviews.ROOT))
        self._json(202, {"job": record})

    def _api_get_job(self, args: tuple, query: str, payload: dict) -> None:
        record = self.server.broker.get(args[0])
        if record is None:
            self._error(404, "not_found", "unknown job")
            return
        self._json(200, {"job": record})

    def _api_cancel_job(self, args: tuple, query: str, payload: dict) -> None:
        broker = self.server.broker
        if broker.get(args[0]) is None:
            self._error(404, "not_found", "unknown job")
            return
        if not broker.cancel(args[0]):
            self._error(409, "already_finished", "job already finished")
            return
        self._json(202, {"job": broker.get(args[0])})

    def _resume_after(self, query: str) -> int | None:
        """Last delivered seq from ``Last-Event-ID`` (reconnect) or ``?after=``; None if invalid."""
        raw = self.headers.get("Last-Event-ID")
        if raw is None:
            values = urllib.parse.parse_qs(query).get("after")
            raw = values[-1] if values else "0"
        try:
            return max(0, int(raw.strip() or "0"))
        except ValueError:
            return None

    def _api_job_events(self, args: tuple, query: str, payload: dict) -> None:
        job_id = args[0]
        after = self._resume_after(query)
        if after is None:
            self._error(400, "bad_request", "Last-Event-ID and after must be integers")
            return
        try:
            stream = self.server.broker.events(job_id, after, heartbeat_s=self.server.sse_heartbeat_s)
        except KeyError:
            self._error(404, "not_found", "unknown job")
            return
        if not self.server.acquire_stream():
            stream.close()
            self._error(503, "too_many_streams",
                        f"at most {self.server.max_streams} event streams may be open at once")
            return
        try:
            self.close_connection = True
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Connection", "close")
            self.end_headers()
            for item in stream:
                if item is None:
                    chunk = b": ping\n\n"
                else:
                    seq, event = item
                    data = json.dumps(event, ensure_ascii=False)
                    chunk = f"id: {seq}\nevent: {event['type']}\ndata: {data}\n\n".encode("utf-8")
                self.wfile.write(chunk)
                self.wfile.flush()
        except DISCONNECTS:
            pass  # client closed the stream; it can resume with Last-Event-ID
        finally:
            stream.close()
            self.server.release_stream()


class WebUIServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    sse_heartbeat_s = 15.0
    max_streams = 32  # concurrent SSE subscribers; each holds one handler thread

    def __init__(self, port: int, *, agent_status: dict | None = None, review_timeout: int = 3600,
                 broker: jobs.JobBroker | None = None, csrf_token: str | None = None):
        self.agent_status = agent_status
        self.review_timeout = review_timeout
        self.broker = broker if broker is not None else jobs.JobBroker()
        self.csrf_token = csrf_token or secrets.token_urlsafe(32)
        self._streams = 0
        self._streams_lock = threading.Lock()
        self.harness_lock = threading.Lock()  # serializes the harness check single-flight test and closing
        super().__init__(("127.0.0.1", port), Handler)
        # Every entry point (research_webui serve, onboarding, tests) starts here; workspaces whose
        # owner process is gone (a killed server) are removed once the port is ours.
        removed = reader.remove_stale_workspaces()
        if removed:
            sys.stderr.write(f"이전 실행이 남긴 논문 리더 작업 폴더 {len(removed)}개를 지웠습니다.\n")

    def acquire_stream(self) -> bool:
        """Reserve an SSE subscriber slot; False when ``max_streams`` are already open."""
        with self._streams_lock:
            if self._streams >= self.max_streams:
                return False
            self._streams += 1
            return True

    def release_stream(self) -> None:
        with self._streams_lock:
            self._streams -= 1

    def server_close(self) -> None:
        """Stop listening after cancelling reader jobs and harness checks and waiting briefly for
        their cleanup (``reader.shutdown``: turn recorded, CLI group ended, temp workspace removed;
        harness checks: process group ended), at most HARNESS_SHUTDOWN_WAIT_S in total for checks."""
        try:
            deadline = time.monotonic() + HARNESS_SHUTDOWN_WAIT_S
            with self.harness_lock:  # no harness check is submitted after this
                self.broker.closing.set()
            checks = [job for job in self.broker.list() if is_harness_job(job)]
            for job in checks:
                if job.get("status") in {"queued", "running"}:
                    self.broker.cancel(job["job_id"])
            try:
                if not reader.shutdown(self.broker):
                    sys.stderr.write(f"논문 리더 작업 일부가 {reader.SHUTDOWN_WAIT_S:g}초 안에 끝나지 않았습니다. "
                                     "남은 작업 폴더는 다음 실행 때 지웁니다.\n")
            finally:
                if not self.broker.wait_finished([job["job_id"] for job in checks],
                                                 max(0.0, deadline - time.monotonic())):
                    sys.stderr.write(f"하네스 검사 일부가 {HARNESS_SHUTDOWN_WAIT_S:g}초 안에 끝나지 않았습니다.\n")
        finally:
            super().server_close()


def make_server(port: int = 8765, **kw) -> WebUIServer:
    return WebUIServer(port, **kw)


def serve_until_stopped(server: WebUIServer) -> None:
    """Serve until Ctrl+C or SIGTERM, then close gracefully (``server_close`` cancels reader jobs
    and waits for their cleanup). SIGTERM is handled like Ctrl+C only when called from the main
    thread; the previous handler is restored afterwards."""
    previous = None

    def stop(signum, frame) -> None:
        raise KeyboardInterrupt

    if threading.current_thread() is threading.main_thread():
        previous = signal.signal(signal.SIGTERM, stop)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            server.server_close()
        finally:
            if previous is not None:
                signal.signal(signal.SIGTERM, previous)
