"""Request guards, safe static path resolution, and security headers for the WebUI server.

Every guard raises ``GuardError`` carrying the HTTP status and the stable error ``code``
documented in ``.scripts/docs/webui-api.md``.
"""
from __future__ import annotations

import fnmatch
import hmac
import json
import os
import re
import urllib.parse
from http import HTTPStatus
from pathlib import Path
from typing import Iterable

HOST_NAMES = ("127.0.0.1", "localhost")
STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
MAX_BODY_BYTES = 64 * 1024
REVIEW_MAX_BODY_BYTES = 4096
REVIEW_ROUTE = "/api/reviews"
WEBUI_PREFIX = "/100-views/webui/"
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; "
    "worker-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
)
# Never served even under an allowed root (credentials, local settings, VCS data, reader Q&A threads).
SENSITIVE_NAMES = (".git", ".env", ".env.*", ".mcp.json", ".secrets", "credentials.json",
                   ".claude", ".codex", ".research-harness-agent.json", ".research-harness-agent.tmp",
                   "reader-threads")
# Review method figures: ``<review dir>/figures/<slug>-<suffix>.(svg|html)`` for any review folder
# under ``01-Papers/reviews`` (``reviews.review_target``/``allowed_output`` accept nested folders).
# Never served statically (agent-written HTML/SVG would run same-origin without a CSP); the SVG
# alone is served by ``GET /api/papers/{slug}/figures/{name}`` with ``FIGURE_CSP``.
FIGURE_DIR = "figures"
FIGURE_SUFFIX = r"[a-z0-9][a-z0-9-]*"
FIGURE_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"


def figure_name_ok(slug: str, name: str, extensions: Iterable[str] = ("svg",)) -> bool:
    """True when ``name`` is ``<slug>-<suffix>.<ext>`` for one of ``extensions`` (lowercase only)."""
    pattern = (re.escape(slug) + "-" + FIGURE_SUFFIX + r"\.(?:"
               + "|".join(re.escape(extension) for extension in extensions) + ")")
    return re.fullmatch(pattern, name) is not None


def _review_figure(parts: list[str] | tuple[str, ...]) -> bool:
    """True for a ``figures`` component at any depth under ``01-Papers/reviews`` and everything
    below it. Case-folded: on a case-insensitive filesystem ``Figures`` is the same directory."""
    return (list(parts[:2]) == ["01-Papers", "reviews"]
            and any(part.casefold() == FIGURE_DIR for part in parts[2:]))


class GuardError(Exception):
    """A rejected request: HTTP status, stable error code, and a human-readable message."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def error_code(status: int) -> str:
    """Stable snake_case code for a bare HTTP status (``404`` -> ``not_found``)."""
    try:
        phrase = HTTPStatus(status).phrase
    except ValueError:
        return "error"
    return "_".join(phrase.lower().replace("-", " ").replace("'", "").split())


def _single(headers, name: str) -> str | None:
    values = headers.get_all(name) or []
    if len(values) != 1:
        return None
    return values[0]


def check_host(headers, port: int) -> str:
    """Return the request Host when it is exactly ``127.0.0.1:<port>`` or ``localhost:<port>``."""
    host = _single(headers, "Host")
    if host not in {f"{name}:{port}" for name in HOST_NAMES}:
        raise GuardError(403, "bad_host", "requests must target this local server by 127.0.0.1 or localhost")
    return host


def check_state_change(headers, host: str, csrf_token: str) -> None:
    """Origin, Sec-Fetch-Site, and CSRF checks for POST/PUT/PATCH/DELETE."""
    if _single(headers, "Origin") != f"http://{host}":
        raise GuardError(403, "bad_origin", "same-origin local UI required")
    fetch_site = headers.get_all("Sec-Fetch-Site") or []
    if fetch_site and fetch_site != ["same-origin"]:
        raise GuardError(403, "bad_origin", "same-origin local UI required")
    provided = _single(headers, "X-CSRF-Token") or ""
    if not csrf_token or not hmac.compare_digest(provided.encode("utf-8", "replace"),
                                                 csrf_token.encode("utf-8", "replace")):
        raise GuardError(403, "bad_csrf", "missing or invalid X-CSRF-Token; fetch /api/session first")


def check_content_type(headers) -> None:
    media_type = (headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
    if media_type != "application/json":
        raise GuardError(415, "unsupported_media_type", "Content-Type must be application/json")


def body_limit(route: str) -> int:
    return REVIEW_MAX_BODY_BYTES if route == REVIEW_ROUTE else MAX_BODY_BYTES


def content_length(headers, limit: int) -> int:
    """Validated request body length; chunked bodies are refused."""
    if headers.get("Transfer-Encoding"):
        raise GuardError(411, "length_required", "chunked request bodies are not accepted; send Content-Length")
    raw = headers.get("Content-Length")
    if raw is None:
        return 0
    try:
        length = int(raw.strip())
    except ValueError:
        raise GuardError(400, "bad_request", "invalid Content-Length") from None
    if length < 0:
        raise GuardError(400, "bad_request", "invalid Content-Length")
    if length > limit:
        raise GuardError(413, "payload_too_large", f"request body exceeds {limit} bytes")
    return length


def parse_json(body: bytes) -> dict:
    """Decode a JSON object body; an empty body is an empty object."""
    if not body:
        return {}
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise GuardError(400, "bad_json", "request body is not valid JSON") from None
    if not isinstance(payload, dict):
        raise GuardError(400, "bad_json", "request body must be a JSON object")
    return payload


def response_headers(route: str) -> list[tuple[str, str]]:
    """Headers added to every response; ``route`` is the percent-decoded request path."""
    headers = [("X-Content-Type-Options", "nosniff"), ("Referrer-Policy", "no-referrer"),
               ("X-Frame-Options", "DENY")]
    if route == "/api" or route.startswith("/api/"):
        headers.append(("Cache-Control", "no-store"))
    if route.startswith(WEBUI_PREFIX) or route == WEBUI_PREFIX.rstrip("/"):
        headers.append(("Content-Security-Policy", CONTENT_SECURITY_POLICY))
    return headers


def _allowed(relative: str, allowed_roots: tuple[str, ...], allowed_files: Iterable[str]) -> bool:
    return relative in allowed_files or relative.startswith(allowed_roots)


def _sensitive(parts: Iterable[str]) -> bool:
    return any(fnmatch.fnmatchcase(part, pattern) for part in parts for pattern in SENSITIVE_NAMES)


def _exact_case(root: Path, parts: list[str]) -> bool:
    """True when every component exists with exactly the requested spelling.

    Case-insensitive filesystems would otherwise map ``/100-VIEWS/`` or ``/Docs/x`` onto
    real files and bypass the case-sensitive allow-list.
    """
    current = root
    for part in parts:
        try:
            names = os.listdir(current)
        except OSError:
            return False
        if part not in names:
            return False
        current = current / part
    return True


def resolve_static(root: Path, url_path: str, allowed_roots: tuple[str, ...],
                   allowed_files: Iterable[str]) -> Path | None:
    """Map a URL path to a real file or directory inside ``root``, or ``None`` (404).

    Rejects NUL bytes, backslashes, ``.``/``..``/empty segments after percent-decoding,
    paths outside the allow-list, sensitive names, case variants, and symlinks resolving
    outside ``root`` or outside the allow-list.
    """
    try:
        decoded = urllib.parse.unquote(url_path, errors="strict")
    except UnicodeDecodeError:
        return None
    if "\x00" in decoded or "\\" in decoded or not decoded.startswith("/"):
        return None
    relative = decoded[1:]
    if relative.endswith("/"):
        relative = relative[:-1]
    if not relative:
        return None
    parts = relative.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None
    if not _allowed(relative, allowed_roots, allowed_files) and not _allowed(relative + "/", allowed_roots, allowed_files):
        return None
    if _sensitive(parts) or _review_figure(parts):
        return None
    if not _exact_case(root, parts):
        return None
    try:
        base = root.resolve(strict=True)
        resolved = (root / relative).resolve(strict=True)
    except (OSError, RuntimeError, ValueError):
        return None
    if not resolved.is_relative_to(base):
        return None
    resolved_relative = resolved.relative_to(base).as_posix()
    if resolved.is_dir():
        resolved_relative += "/"
    resolved_parts = resolved.relative_to(base).parts
    if (not _allowed(resolved_relative, allowed_roots, allowed_files) or _sensitive(resolved_parts)
            or _review_figure(resolved_parts)):
        return None
    return resolved
