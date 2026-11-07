#!/usr/bin/env python3
"""Local paper-discovery cache ``00-Inbox/discovery/``: schemas, validation, normalization,
library matching, conference reference lookup, and the CLI used by ``daily-digest-loop``.

The cache is Git-ignored and is neither wiki, library, nor Graphify content. Layout:
``daily/{YYYY-MM-DD}.json`` (one daily digest) and ``searches/{search_id}.json`` (one search
session). The schema is documented in ``.scripts/docs/discovery-cache.schema.json`` and
``.scripts/docs/webui-api.md`` ("논문 탐색"); this module is the authority.

Validation checks structure, types, and enumerations. Normalization removes control characters,
truncates over-long text to ``LIMITS``/``TEXT_LIMITS``, drops non-https ``url`` values,
normalizes ``ids`` (DOI as found, arXiv without version), and assigns ``candidate_id``. The WebUI
search job's agent answer (``.scripts/docs/discovery-search.schema.json``) goes through
``validate_search_output``/``prepare_search_result`` before it becomes a session.

CLI (exit 0 ok, 1 unsafe cache path or I/O error, 2 invalid input, 3 day already cached)::

    discovery_cache.py [--root PATH] validate <path>...
    discovery_cache.py [--root PATH] daily-write <input.json> [--replace]
    discovery_cache.py [--root PATH] library-match <path>

``daily-write`` holds ``daily_lock`` (``fcntl.flock`` on ``daily/.{date}.lock``) from reading the
previous day through the write, as does every WebUI read-modify-write of a daily file, so a
``--replace`` never drops a candidate status the WebUI saved meanwhile.

Standard library only.
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import os
import re
import stat
import sys
import threading
import unicodedata
from contextlib import contextmanager
from datetime import date as Date, datetime, timezone
from pathlib import Path

from harness_common import write_json_atomic

ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "1.0"
CACHE_RELATIVE = "00-Inbox/discovery"
CACHE_KINDS = ("daily", "searches")
LIBRARY_RELATIVE = "01-Papers/library"
CONFERENCES_RELATIVE = "01-Papers/reference/cs-conferences.csv"

PUBLICATION_STATUSES = ("published", "accepted", "preprint", "unknown")
SOURCES = ("s2", "arxiv", "openalex", "web")
CATEGORIES = ("wifi-csi", "game-ai", "agent-ai", "computer-vision", "other")
CANDIDATE_STATUSES = ("new", "keep", "registered", "skipped")
SLOTS = ("computer-vision", "multimodal", "interest")
SEARCH_MODES = ("search", "related")
SEARCH_STATUSES = ("queued", "running", "completed", "failed", "cancelled")
ACTIVE_SEARCH_STATUSES = frozenset({"queued", "running"})
RELATED_KINDS = ("refs", "cites")
ID_KEYS = ("arXiv", "DOI", "S2", "OpenAlex")
# Design limits (characters per string, entries per list).
LIMITS = {"title": 500, "abstract": 5000, "relevance": 600, "authors": 50, "topics": 10,
          "verification_sources": 10}
# Limits the design leaves open, fixed here.
TEXT_LIMITS = {"author": 200, "venue": 300, "topic": 100, "verification_source": 500, "id": 200,
               "url": 2000, "slot_topic": 200, "unfilled_reason": 600, "report_item": 500,
               "notes": 5000, "plan_path": 300}
REPORT_LIST_LIMIT = 50
YEAR_RANGE = (1800, 2100)
INTERRUPTED_ERROR = {"message": "서버가 재시작되어 검색이 중단되었습니다. 다시 실행하세요.", "kind": "interrupted"}
# A search whose job ended (broker terminal) while its session file still says queued/running:
# the final save failed, the job reported it as an error of this kind.
PERSIST_FAILED_ERROR = {"message": "검색은 끝났지만 결과를 검색 기록에 저장하지 못했습니다. 다시 실행하세요.",
                        "kind": "persist_failed"}

DATE_PATTERN = re.compile(r"\d{4}-\d{2}-\d{2}")
SEARCH_ID_PATTERN = re.compile(r"s_[0-9a-f]{12}")
CANDIDATE_ID_PATTERN = re.compile(r"c_[0-9a-f]{12}")
SLUG_PATTERN = re.compile(r"[a-z0-9-]+")
DOI_PATTERN = re.compile(r"10\.\d{4,9}/\S+")
ARXIV_ID = re.compile(r"(?i)(?:arxiv:\s*)?(\d{4}\.\d{4,5})(?:v\d+)?")
ARXIV_URL = re.compile(r"(?i)arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5})")
ARXIV_DOI = re.compile(r"(?i)10\.48550/arxiv\.(\d{4}\.\d{4,5})")
DOI_URL = re.compile(r"(?i)doi\.org/(10\.\S+)")
S2_ID = re.compile(r"[0-9a-f]{40}")
DOI_TRAILING = ".,;:)]}>\"'"
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")

CANDIDATE_KEYS = frozenset({
    "candidate_id", "title", "authors", "year", "venue", "publication", "citations", "ids", "url",
    "abstract", "relevance", "sources", "suggested_category", "topics", "conference_ref", "status",
    "status_updated_at", "slug", "library"})
# Keys a producer may omit or send: they are always recomputed (library is never stored).
DERIVED_KEYS = frozenset({"candidate_id", "conference_ref", "status", "status_updated_at", "slug", "library"})
DAILY_KEYS = frozenset({"schema_version", "date", "created_at", "plan_path", "slots", "report"})
SLOT_KEYS = frozenset({"slot", "topic", "candidate", "unfilled_reason"})
DAILY_REPORT_LISTS = ("queries", "sources", "coverage_gaps")
SESSION_KEYS = ("schema_version", "search_id", "mode", "created_at", "status", "job_id", "request",
                "agent", "report", "candidates", "error", "duration_ms")
SEARCH_REQUEST_KEYS = ("query", "year_from", "year_to", "limit", "category_hint", "anchors", "verified_only")
RELATED_REQUEST_KEYS = ("kind", "paper", "limit")
SESSION_REPORT_KEYS = frozenset({"queries", "sources", "anchors", "coverage_gaps", "excluded_count", "notes"})
SEARCH_OUTPUT_KEYS = frozenset({"report", "candidates"})


class CacheError(Exception):
    """A cache failure with an HTTP status, stable error code, and Korean message."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class ValidationError(ValueError):
    """Input that does not match the schema; ``errors`` lists every problem found."""

    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---- text and identifiers ------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """``text`` without NUL and other C0 control characters (and DEL); tab and newline stay."""
    return _CONTROL.sub("", text)


def _line(text: str, limit: int) -> str:
    """One-line text: control characters removed, whitespace collapsed, truncated."""
    return " ".join(clean_text(text).split())[:limit]


def _block(text: str, limit: int) -> str:
    """Multi-line text: control characters removed, outer whitespace stripped, truncated."""
    return clean_text(text).strip()[:limit]


def _line_or_none(value: object, limit: int) -> str | None:
    return (_line(value, limit) or None) if isinstance(value, str) else None


def _block_or_none(value: object, limit: int) -> str | None:
    return (_block(value, limit) or None) if isinstance(value, str) else None


def _lines(values: object, limit: int, count: int) -> list[str]:
    """Cleaned non-empty unique strings, first ``count`` kept."""
    result: list[str] = []
    for value in values if isinstance(values, list) else []:
        text = _line(value, limit) if isinstance(value, str) else ""
        if text and text not in result:
            result.append(text)
    return result[:count]


def normalize_title(title: object) -> str:
    """NFKC, casefold, every non-alphanumeric character as a space, whitespace collapsed."""
    if not isinstance(title, str):
        return ""
    folded = unicodedata.normalize("NFKC", title).casefold()
    return " ".join("".join(ch if ch.isalnum() else " " for ch in folded).split())


def bare_doi(value: object) -> str | None:
    """First DOI (``10.<registrant>/<suffix>``) in ``value`` with its original case, or None."""
    if not isinstance(value, str):
        return None
    match = DOI_PATTERN.search(value)
    return (match.group(0).rstrip(DOI_TRAILING) or None) if match else None


def bare_arxiv(value: object) -> str | None:
    """arXiv id without version from ``2603.25158``, ``arXiv:2603.25158v5``, or an arxiv.org URL."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    match = ARXIV_ID.fullmatch(text) or ARXIV_URL.search(text)
    return match.group(1) if match else None


def _arxiv_from_doi(doi: str | None) -> str | None:
    match = ARXIV_DOI.fullmatch(doi) if doi else None
    return match.group(1) if match else None


def _s2(value: object) -> str | None:
    return value.strip().casefold() or None if isinstance(value, str) else None


def candidate_key(candidate: dict) -> str:
    """Dedup key: ``doi:<casefold>`` > ``arxiv:<id without version>`` > ``s2:<id>`` > ``title:<normalized>``."""
    ids = candidate.get("ids") if isinstance(candidate.get("ids"), dict) else {}
    doi = bare_doi(ids.get("DOI"))
    if doi:
        return "doi:" + doi.casefold()
    arxiv = bare_arxiv(ids.get("arXiv"))
    if arxiv:
        return "arxiv:" + arxiv
    s2 = _s2(ids.get("S2"))
    if s2:
        return "s2:" + s2
    return "title:" + normalize_title(candidate.get("title"))


def make_candidate_id(candidate: dict) -> str:
    return "c_" + hashlib.sha256(candidate_key(candidate).encode("utf-8")).hexdigest()[:12]


def _https(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    url = value.strip()
    if not url.lower().startswith("https://") or len(url) > TEXT_LIMITS["url"] or len(url) <= len("https://"):
        return None
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in url):
        return None
    return url


# ---- validation ----------------------------------------------------------------------------------

def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: object) -> bool:
    return (_is_int(value) or isinstance(value, float)) and not isinstance(value, bool)


def _str_list(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def _opt_str(value: object) -> bool:
    return value is None or isinstance(value, str)


def _unknown(value: dict, allowed, where: str) -> list[str]:
    extra = sorted(str(key) for key in value if key not in allowed)
    return [f"{where}: 알 수 없는 키 {', '.join(extra)}"] if extra else []


def _text_limit(value: object, limit: int, where: str) -> list[str]:
    """Error when ``value`` is a string longer than ``limit`` characters."""
    if isinstance(value, str) and len(value) > limit:
        return [f"{where}: {limit}자 이하여야 합니다({len(value)}자)"]
    return []


def _list_limit(value: object, count: int, item_limit: int, where: str) -> list[str]:
    """Errors when ``value`` is a list longer than ``count`` or holds a string over ``item_limit``."""
    if not isinstance(value, list):
        return []
    errors = [f"{where}: {count}개 이하여야 합니다({len(value)}개)"] if len(value) > count else []
    over = [index for index, item in enumerate(value) if isinstance(item, str) and len(item) > item_limit]
    if over:
        errors.append(f"{where}[{over[0]}]: 항목은 {item_limit}자 이하여야 합니다")
    return errors


def validate_candidate(value: object, where: str = "candidate", *, limits: bool = True) -> list[str]:
    """Problems with one Candidate. Derived keys (``DERIVED_KEYS``) are optional.

    With ``limits`` (default) strings and lists over ``LIMITS``/``TEXT_LIMITS`` are errors.
    ``normalize_candidate`` checks untrusted input with ``limits=False`` and truncates instead."""
    if not isinstance(value, dict):
        return [f"{where}: 객체가 아닙니다"]
    errors = _unknown(value, CANDIDATE_KEYS, where)
    title = value.get("title")
    if not isinstance(title, str) or not _line(title, LIMITS["title"]):
        errors.append(f"{where}.title: 비어 있지 않은 문자열이어야 합니다")
    if not _str_list(value.get("authors")):
        errors.append(f"{where}.authors: 문자열 목록이어야 합니다")
    relevance = value.get("relevance")
    if not isinstance(relevance, str) or not relevance.strip():
        errors.append(f"{where}.relevance: 비어 있지 않은 문자열이어야 합니다")
    year = value.get("year")
    if year is not None and not (_is_int(year) and YEAR_RANGE[0] <= year <= YEAR_RANGE[1]):
        errors.append(f"{where}.year: {YEAR_RANGE[0]}–{YEAR_RANGE[1]} 정수 또는 null이어야 합니다")
    for key in ("venue", "url", "abstract", "status_updated_at"):
        if not _opt_str(value.get(key)):
            errors.append(f"{where}.{key}: 문자열 또는 null이어야 합니다")
    publication = value.get("publication")
    if publication is not None:
        if not isinstance(publication, dict):
            errors.append(f"{where}.publication: 객체 또는 null이어야 합니다")
        else:
            errors += _unknown(publication, {"status", "verified", "verification_sources"}, f"{where}.publication")
            if "status" in publication and publication["status"] not in PUBLICATION_STATUSES:
                errors.append(f"{where}.publication.status: {'|'.join(PUBLICATION_STATUSES)} 중 하나여야 합니다")
            if "verified" in publication and not isinstance(publication["verified"], bool):
                errors.append(f"{where}.publication.verified: true/false여야 합니다")
            if "verification_sources" in publication and not _str_list(publication["verification_sources"]):
                errors.append(f"{where}.publication.verification_sources: 문자열 목록이어야 합니다")
            elif limits:
                errors += _list_limit(publication.get("verification_sources"), LIMITS["verification_sources"],
                                      TEXT_LIMITS["verification_source"], f"{where}.publication.verification_sources")
    citations = value.get("citations")
    if citations is not None and not (_is_int(citations) and citations >= 0):
        errors.append(f"{where}.citations: 0 이상 정수 또는 null이어야 합니다")
    ids = value.get("ids")
    if ids is not None:
        if not isinstance(ids, dict):
            errors.append(f"{where}.ids: 객체 또는 null이어야 합니다")
        else:
            errors += _unknown(ids, ID_KEYS, f"{where}.ids")
            for key in ID_KEYS:
                if not _opt_str(ids.get(key)):
                    errors.append(f"{where}.ids.{key}: 문자열 또는 null이어야 합니다")
                elif limits:
                    errors += _text_limit(ids.get(key), TEXT_LIMITS["id"], f"{where}.ids.{key}")
            if isinstance(ids.get("arXiv"), str) and ids["arXiv"].strip() and not bare_arxiv(ids["arXiv"]):
                errors.append(f"{where}.ids.arXiv: arXiv id(YYMM.NNNNN) 형식이 아닙니다")
            if isinstance(ids.get("DOI"), str) and ids["DOI"].strip() and not bare_doi(ids["DOI"]):
                errors.append(f"{where}.ids.DOI: DOI(10.xxxx/…) 형식이 아닙니다")
    sources = value.get("sources")
    if sources is not None and not (isinstance(sources, list) and all(item in SOURCES for item in sources)):
        errors.append(f"{where}.sources: {'|'.join(SOURCES)} 값의 목록이어야 합니다")
    category = value.get("suggested_category")
    if category is not None and category not in CATEGORIES:
        errors.append(f"{where}.suggested_category: {'|'.join(CATEGORIES)} 중 하나 또는 null이어야 합니다")
    topics = value.get("topics")
    if topics is not None and not _str_list(topics):
        errors.append(f"{where}.topics: 문자열 목록이어야 합니다")
    reference = value.get("conference_ref")
    if reference is not None and not (
            isinstance(reference, dict) and set(reference) == {"abbr", "name", "score"}
            and isinstance(reference["abbr"], str) and isinstance(reference["name"], str)
            and (reference["score"] is None or _is_number(reference["score"]))):
        errors.append(f"{where}.conference_ref: {{abbr, name, score}} 또는 null이어야 합니다")
    candidate_id = value.get("candidate_id")
    if candidate_id is not None and not (isinstance(candidate_id, str) and CANDIDATE_ID_PATTERN.fullmatch(candidate_id)):
        errors.append(f"{where}.candidate_id: c_<12자리 16진수>여야 합니다")
    if "status" in value and value["status"] not in CANDIDATE_STATUSES:
        errors.append(f"{where}.status: {'|'.join(CANDIDATE_STATUSES)} 중 하나여야 합니다")
    slug = value.get("slug")
    if slug is not None and not (isinstance(slug, str) and SLUG_PATTERN.fullmatch(slug)):
        errors.append(f"{where}.slug: [a-z0-9-]+ 또는 null이어야 합니다")
    if limits:
        errors += _text_limit(title, LIMITS["title"], f"{where}.title")
        errors += _text_limit(relevance, LIMITS["relevance"], f"{where}.relevance")
        errors += _text_limit(value.get("abstract"), LIMITS["abstract"], f"{where}.abstract")
        errors += _text_limit(value.get("venue"), TEXT_LIMITS["venue"], f"{where}.venue")
        errors += _text_limit(value.get("url"), TEXT_LIMITS["url"], f"{where}.url")
        if _str_list(value.get("authors")):
            errors += _list_limit(value["authors"], LIMITS["authors"], TEXT_LIMITS["author"], f"{where}.authors")
        if _str_list(topics):
            errors += _list_limit(topics, LIMITS["topics"], TEXT_LIMITS["topic"], f"{where}.topics")
    return errors


def valid_date(value: object) -> bool:
    """True for a ``YYYY-MM-DD`` string that is a real calendar date."""
    if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value):
        return False
    try:
        Date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _safe_relative(value: str) -> bool:
    if not value or value.startswith("/") or "\\" in value or "\x00" in value:
        return False
    return all(part not in {"", ".", ".."} for part in value.split("/"))


def _validate_report(value: object, lists: tuple[str, ...], where: str, allowed=None, *,
                     limits: bool = True) -> list[str]:
    if not isinstance(value, dict):
        return [f"{where}: 객체 또는 null이어야 합니다"]
    errors = _unknown(value, allowed or set(lists) | {"notes"}, where)
    for key in lists:
        if key in value and not _str_list(value[key]):
            errors.append(f"{where}.{key}: 문자열 목록이어야 합니다")
        elif key in value and limits:
            errors += _list_limit(value[key], REPORT_LIST_LIMIT, TEXT_LIMITS["report_item"], f"{where}.{key}")
    if "notes" in value and not isinstance(value["notes"], str):
        errors.append(f"{where}.notes: 문자열이어야 합니다")
    elif limits:
        errors += _text_limit(value.get("notes"), TEXT_LIMITS["notes"], f"{where}.notes")
    return errors


def validate_daily(data: object, *, limits: bool = True) -> list[str]:
    """Problems with a Daily document (producer input or stored file). With ``limits`` (default)
    over-long strings and lists are errors; ``prepare_daily`` uses ``limits=False`` and truncates."""
    if not isinstance(data, dict):
        return ["daily: 객체가 아닙니다"]
    errors = _unknown(data, DAILY_KEYS, "daily")
    if "schema_version" in data and data["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version: \"{SCHEMA_VERSION}\"이어야 합니다")
    if not valid_date(data.get("date")):
        errors.append("date: YYYY-MM-DD 형식의 실제 날짜여야 합니다")
    if not _opt_str(data.get("created_at")):
        errors.append("created_at: 문자열이어야 합니다")
    plan_path = data.get("plan_path")
    if plan_path is not None and not (isinstance(plan_path, str) and _safe_relative(plan_path)
                                      and len(plan_path) <= TEXT_LIMITS["plan_path"]):
        errors.append("plan_path: 저장소 상대 경로 또는 null이어야 합니다")
    report = data.get("report")
    if report is not None:
        errors += _validate_report(report, DAILY_REPORT_LISTS, "report", limits=limits)
    slots = data.get("slots")
    if not isinstance(slots, list) or len(slots) != len(SLOTS):
        errors.append(f"slots: 슬롯 {len(SLOTS)}개({', '.join(SLOTS)})의 목록이어야 합니다")
        return errors
    seen: set[str] = set()
    for index, slot in enumerate(slots):
        where = f"slots[{index}]"
        if not isinstance(slot, dict):
            errors.append(f"{where}: 객체가 아닙니다")
            continue
        errors += _unknown(slot, SLOT_KEYS, where)
        name = slot.get("slot")
        if name not in SLOTS:
            errors.append(f"{where}.slot: {'|'.join(SLOTS)} 중 하나여야 합니다")
        elif name in seen:
            errors.append(f"{where}.slot: {name} 슬롯이 중복됩니다")
        else:
            seen.add(name)
        if not _opt_str(slot.get("topic")):
            errors.append(f"{where}.topic: 문자열 또는 null이어야 합니다")
        elif limits:
            errors += _text_limit(slot.get("topic"), TEXT_LIMITS["slot_topic"], f"{where}.topic")
        if not _opt_str(slot.get("unfilled_reason")):
            errors.append(f"{where}.unfilled_reason: 문자열 또는 null이어야 합니다")
        elif limits:
            errors += _text_limit(slot.get("unfilled_reason"), TEXT_LIMITS["unfilled_reason"],
                                  f"{where}.unfilled_reason")
        candidate = slot.get("candidate")
        if candidate is None:
            reason = slot.get("unfilled_reason")
            if not isinstance(reason, str) or not reason.strip():
                errors.append(f"{where}.unfilled_reason: 후보가 없으면 채우지 못한 이유가 필요합니다")
        else:
            errors += validate_candidate(candidate, f"{where}.candidate", limits=limits)
    return errors


def _validate_request(mode: object, request: object) -> list[str]:
    if not isinstance(request, dict):
        return ["request: 객체여야 합니다"]
    if mode == "related":
        errors = _unknown(request, RELATED_REQUEST_KEYS, "request")
        errors += [f"request.{key}: 필수입니다" for key in RELATED_REQUEST_KEYS if key not in request]
        if "kind" in request and request["kind"] not in RELATED_KINDS:
            errors.append("request.kind: refs|cites 중 하나여야 합니다")
        paper = request.get("paper")
        if "paper" in request and not (
                isinstance(paper, dict) and set(paper) == {"slug", "title", "ids"} and _opt_str(paper["slug"])
                and isinstance(paper["title"], str) and isinstance(paper["ids"], dict)):
            errors.append("request.paper: {slug, title, ids}여야 합니다")
    else:
        errors = _unknown(request, SEARCH_REQUEST_KEYS, "request")
        errors += [f"request.{key}: 필수입니다" for key in SEARCH_REQUEST_KEYS if key not in request]
        if "query" in request and not isinstance(request["query"], str):
            errors.append("request.query: 문자열이어야 합니다")
        for key in ("year_from", "year_to"):
            if key in request and request[key] is not None and not _is_int(request[key]):
                errors.append(f"request.{key}: 정수 또는 null이어야 합니다")
        if "category_hint" in request and request["category_hint"] is not None and request["category_hint"] not in CATEGORIES:
            errors.append("request.category_hint: 카테고리 5종 중 하나 또는 null이어야 합니다")
        if "anchors" in request and not _str_list(request["anchors"]):
            errors.append("request.anchors: 문자열 목록이어야 합니다")
        if "verified_only" in request and not isinstance(request["verified_only"], bool):
            errors.append("request.verified_only: true/false여야 합니다")
    if "limit" in request and not (_is_int(request["limit"]) and request["limit"] >= 1):
        errors.append("request.limit: 1 이상 정수여야 합니다")
    return errors


def validate_session(data: object) -> list[str]:
    """Problems with a stored search session; every key of the schema is required."""
    if not isinstance(data, dict):
        return ["session: 객체가 아닙니다"]
    errors = _unknown(data, SESSION_KEYS, "session")
    errors += [f"{key}: 필수입니다" for key in SESSION_KEYS if key not in data]
    if errors:
        return errors
    if data["schema_version"] != SCHEMA_VERSION:
        errors.append(f"schema_version: \"{SCHEMA_VERSION}\"이어야 합니다")
    if not (isinstance(data["search_id"], str) and SEARCH_ID_PATTERN.fullmatch(data["search_id"])):
        errors.append("search_id: s_<12자리 16진수>여야 합니다")
    if data["mode"] not in SEARCH_MODES:
        errors.append("mode: search|related 중 하나여야 합니다")
    if not isinstance(data["created_at"], str):
        errors.append("created_at: 문자열이어야 합니다")
    if data["status"] not in SEARCH_STATUSES:
        errors.append(f"status: {'|'.join(SEARCH_STATUSES)} 중 하나여야 합니다")
    if not _opt_str(data["job_id"]):
        errors.append("job_id: 문자열 또는 null이어야 합니다")
    errors += _validate_request(data["mode"], data["request"])
    agent = data["agent"]
    if agent is not None and not (isinstance(agent, dict) and set(agent) == {"agent", "model", "selector"}
                                  and all(_opt_str(item) for item in agent.values())):
        errors.append("agent: {agent, model, selector} 또는 null이어야 합니다")
    report = data["report"]
    if report is not None:
        errors += _validate_report(report, ("queries", "sources", "coverage_gaps"), "report", SESSION_REPORT_KEYS)
        if isinstance(report, dict):
            anchors = report.get("anchors", [])
            if not (isinstance(anchors, list) and all(isinstance(item, dict) for item in anchors)):
                errors.append("report.anchors: 객체 목록이어야 합니다")
            excluded = report.get("excluded_count")
            if excluded is not None and not (_is_int(excluded) and excluded >= 0):
                errors.append("report.excluded_count: 0 이상 정수 또는 null이어야 합니다")
    candidates = data["candidates"]
    if not isinstance(candidates, list):
        errors.append("candidates: 목록이어야 합니다")
    else:
        for index, candidate in enumerate(candidates):
            errors += validate_candidate(candidate, f"candidates[{index}]")
    error = data["error"]
    if error is not None and not (isinstance(error, dict) and isinstance(error.get("message"), str)
                                  and isinstance(error.get("kind"), str)):
        errors.append("error: {message, kind} 또는 null이어야 합니다")
    duration = data["duration_ms"]
    if duration is not None and not (_is_int(duration) and duration >= 0):
        errors.append("duration_ms: 0 이상 정수 또는 null이어야 합니다")
    return errors


# ---- normalization -------------------------------------------------------------------------------

def normalize_candidate(raw: object, conferences: dict | None = None) -> dict:
    """Stored Candidate from producer input. Derived keys are recomputed: ``status`` is ``new``,
    ``status_updated_at``/``slug`` are null (callers carry over saved state), ``conference_ref``
    comes from ``conferences`` (null without an index), ``library`` is dropped."""
    errors = validate_candidate(raw, limits=False)  # untrusted input: over-long values are truncated
    if errors:
        raise ValidationError(errors)
    publication = raw.get("publication") or {}
    ids = raw.get("ids") or {}
    venue = _line_or_none(raw.get("venue"), TEXT_LIMITS["venue"])
    candidate = {
        "candidate_id": "",
        "title": _line(raw["title"], LIMITS["title"]),
        "authors": _lines(raw["authors"], TEXT_LIMITS["author"], LIMITS["authors"]),
        "year": raw.get("year"),
        "venue": venue,
        "publication": {
            "status": publication.get("status", "unknown"),
            "verified": publication.get("verified", False),
            "verification_sources": _lines(publication.get("verification_sources"),
                                           TEXT_LIMITS["verification_source"], LIMITS["verification_sources"]),
        },
        "citations": raw.get("citations"),
        "ids": {
            "arXiv": bare_arxiv(ids.get("arXiv")),
            "DOI": bare_doi(ids.get("DOI")),
            "S2": _line_or_none(ids.get("S2"), TEXT_LIMITS["id"]),
            "OpenAlex": _line_or_none(ids.get("OpenAlex"), TEXT_LIMITS["id"]),
        },
        "url": _https(raw.get("url")),
        "abstract": _block_or_none(raw.get("abstract"), LIMITS["abstract"]),
        "relevance": _line(raw["relevance"], LIMITS["relevance"]),
        "sources": list(dict.fromkeys(raw.get("sources") or [])),
        "suggested_category": raw.get("suggested_category"),
        "topics": _lines(raw.get("topics"), TEXT_LIMITS["topic"], LIMITS["topics"]),
        "conference_ref": conference_ref(venue, conferences) if conferences is not None else None,
        "status": "new",
        "status_updated_at": None,
        "slug": None,
    }
    candidate["candidate_id"] = make_candidate_id(candidate)
    return candidate


def merge_candidates(candidates: list[dict]) -> list[dict]:
    """One entry per ``candidate_id`` in first-seen order; later duplicates add their ``sources``."""
    merged: dict[str, dict] = {}
    for candidate in candidates:
        key = candidate["candidate_id"]
        if key not in merged:
            merged[key] = {**candidate, "sources": list(candidate.get("sources") or [])}
            continue
        sources = merged[key]["sources"]
        sources.extend(source for source in candidate.get("sources") or [] if source not in sources)
    return list(merged.values())


def complete_candidate(candidate: dict) -> dict:
    """Fill every schema key a valid stored candidate may omit (hand-written files), keeping
    stored values; non-https ``url`` becomes null. Used on read so responses always carry the
    full Candidate shape."""
    defaults = {"year": None, "venue": None, "citations": None, "url": None, "abstract": None,
                "sources": [], "suggested_category": None, "topics": [], "conference_ref": None,
                "status": "new", "status_updated_at": None, "slug": None}
    for key, value in defaults.items():
        candidate.setdefault(key, list(value) if isinstance(value, list) else value)
    publication = candidate.get("publication") or {}
    candidate["publication"] = {"status": publication.get("status", "unknown"),
                                "verified": publication.get("verified", False),
                                "verification_sources": publication.get("verification_sources", [])}
    ids = candidate.get("ids") or {}
    candidate["ids"] = {key: ids.get(key) for key in ID_KEYS}
    candidate["url"] = _https(candidate["url"])
    if not candidate.get("candidate_id"):
        candidate["candidate_id"] = make_candidate_id(candidate)
    return candidate


def _report(raw: object) -> dict:
    report = raw if isinstance(raw, dict) else {}
    result = {key: _lines(report.get(key), TEXT_LIMITS["report_item"], REPORT_LIST_LIMIT) for key in DAILY_REPORT_LISTS}
    result["notes"] = _block(report.get("notes") or "", TEXT_LIMITS["notes"])
    return result


def _validate_anchor(value: object, where: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{where}: 객체가 아닙니다"]
    errors = _unknown(value, {"title", "ids"}, where)
    if not isinstance(value.get("title"), str):
        errors.append(f"{where}.title: 문자열이어야 합니다")
    ids = value.get("ids")
    if ids is not None:
        if not isinstance(ids, dict):
            errors.append(f"{where}.ids: 객체 또는 null이어야 합니다")
        else:
            errors += _unknown(ids, ID_KEYS, f"{where}.ids")
            errors += [f"{where}.ids.{key}: 문자열 또는 null이어야 합니다" for key in ID_KEYS if not _opt_str(ids.get(key))]
    return errors


def validate_search_output(data: object) -> list[str]:
    """Problems with a ``paper-searcher`` answer (``.scripts/docs/discovery-search.schema.json``):
    ``{"report": {queries, sources, anchors, coverage_gaps, excluded_count, notes} | null,
    "candidates": [Candidate without derived keys]}``. Structure, types and enumerations only;
    ``prepare_search_result`` truncates over-long values."""
    if not isinstance(data, dict):
        return ["answer: JSON 객체가 아닙니다"]
    errors = _unknown(data, SEARCH_OUTPUT_KEYS, "answer")
    report = data.get("report")
    if report is not None:
        errors += _validate_report(report, DAILY_REPORT_LISTS, "report", SESSION_REPORT_KEYS, limits=False)
        if isinstance(report, dict):
            anchors = report.get("anchors")
            if anchors is not None and not isinstance(anchors, list):
                errors.append("report.anchors: 목록이어야 합니다")
            for index, anchor in enumerate(anchors if isinstance(anchors, list) else []):
                errors += _validate_anchor(anchor, f"report.anchors[{index}]")
            excluded = report.get("excluded_count")
            if excluded is not None and not (_is_int(excluded) and excluded >= 0):
                errors.append("report.excluded_count: 0 이상 정수 또는 null이어야 합니다")
    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        errors.append("candidates: 목록이어야 합니다")
    else:
        for index, candidate in enumerate(candidates):
            errors += validate_candidate(candidate, f"candidates[{index}]", limits=False)
    return errors


def _normalized_ids(ids: object) -> dict:
    ids = ids if isinstance(ids, dict) else {}
    return {"arXiv": bare_arxiv(ids.get("arXiv")), "DOI": bare_doi(ids.get("DOI")),
            "S2": _line_or_none(ids.get("S2"), TEXT_LIMITS["id"]),
            "OpenAlex": _line_or_none(ids.get("OpenAlex"), TEXT_LIMITS["id"])}


def prepare_search_result(raw: object, *, conferences: dict | None = None, limit: int | None = None) -> dict:
    """Session ``report`` and ``candidates`` from a validated ``paper-searcher`` answer.

    Candidates are normalized (``status: new``, ``candidate_id``, ``conference_ref`` from
    ``conferences``), merged by ``candidate_id`` in answer order (= relevance order), and cut to
    the first ``limit``. Raises ValidationError listing every problem of an invalid answer."""
    errors = validate_search_output(raw)
    if errors:
        raise ValidationError(errors)
    candidates = merge_candidates([normalize_candidate(item, conferences) for item in raw["candidates"]])
    source = raw.get("report") or {}
    report = _report(source)
    anchors = source.get("anchors") or []
    report["anchors"] = [{"title": _line(anchor["title"], LIMITS["title"]), "ids": _normalized_ids(anchor.get("ids"))}
                         for anchor in anchors[:REPORT_LIST_LIMIT]]
    report["excluded_count"] = source.get("excluded_count")
    return {"report": report, "candidates": candidates[:limit] if limit is not None else candidates}


def record_ids(record: dict) -> dict:
    """``{"arXiv", "DOI", "S2", "OpenAlex"}`` of a library record (§2.3 sources; the smallest value
    when a record yields several; DOI casefolded; OpenAlex is never recorded)."""
    dois, arxivs, s2s = _record_ids(record)
    return {"arXiv": min(arxivs) if arxivs else None, "DOI": min(dois) if dois else None,
            "S2": min(s2s) if s2s else None, "OpenAlex": None}


def _saved_states(previous: object) -> dict[str, dict]:
    states: dict[str, dict] = {}
    slots = previous.get("slots") if isinstance(previous, dict) else None
    for slot in slots if isinstance(slots, list) else []:
        candidate = slot.get("candidate") if isinstance(slot, dict) else None
        if isinstance(candidate, dict) and isinstance(candidate.get("candidate_id"), str) \
                and candidate.get("status") in CANDIDATE_STATUSES:
            states[candidate["candidate_id"]] = {key: candidate.get(key) for key in ("status", "status_updated_at", "slug")}
    return states


def prepare_daily(raw: object, *, conferences: dict | None = None, previous: object = None,
                  now: str | None = None) -> dict:
    """Stored Daily from producer input: validated, normalized, slots in ``SLOTS`` order, each
    candidate ``status: new`` unless ``previous`` (the file being replaced) holds the same
    ``candidate_id``, whose ``status``/``status_updated_at``/``slug`` are kept."""
    errors = validate_daily(raw, limits=False)  # untrusted input: over-long values are truncated
    if errors:
        raise ValidationError(errors)
    by_name = {slot["slot"]: slot for slot in raw["slots"]}
    saved = _saved_states(previous)
    seen: dict[str, str] = {}
    slots = []
    for name in SLOTS:
        slot = by_name[name]
        candidate = None
        if slot.get("candidate") is not None:
            candidate = normalize_candidate(slot["candidate"], conferences)
            candidate_id = candidate["candidate_id"]
            if candidate_id in seen:
                errors.append(f"slots: {name} 후보가 {seen[candidate_id]} 후보와 같은 논문입니다({candidate_id})")
            seen[candidate_id] = name
            candidate.update(saved.get(candidate_id, {}))
        slots.append({
            "slot": name,
            "topic": _line_or_none(slot.get("topic"), TEXT_LIMITS["slot_topic"]),
            "candidate": candidate,
            "unfilled_reason": None if candidate else _block(slot["unfilled_reason"], TEXT_LIMITS["unfilled_reason"]),
        })
    if errors:
        raise ValidationError(errors)
    return {
        "schema_version": SCHEMA_VERSION,
        "date": raw["date"],
        "created_at": raw.get("created_at") or now or now_iso(),
        "plan_path": raw.get("plan_path"),
        "slots": slots,
        "report": _report(raw.get("report")),
    }


# ---- cache files ---------------------------------------------------------------------------------

def _unsafe(detail: str) -> CacheError:
    return CacheError(500, "cache_unsafe", f"탐색 캐시 경로가 안전하지 않습니다: {detail}")


def cache_dir(root: Path, kind: str, *, create: bool) -> Path | None:
    """``<root>/00-Inbox/discovery/<kind>`` after checking every component is a real directory
    (no symlink) and the result resolves to exactly root's own copy. None when it does not exist
    and ``create`` is false. Violations raise ``CacheError(500, "cache_unsafe")``."""
    if kind not in CACHE_KINDS:
        raise ValueError(f"unknown cache kind: {kind}")
    root = Path(root)
    current = root
    parts = (*Path(CACHE_RELATIVE).parts, kind)
    for part in parts:
        current = current / part
        if not current.is_symlink() and not current.exists():
            if not create:
                return None
            current.mkdir(exist_ok=True)
        if current.is_symlink():
            raise _unsafe(f"{CACHE_RELATIVE}/{kind}의 {part}가 심볼릭 링크입니다.")
        if not current.is_dir():
            raise _unsafe(f"{part}가 디렉터리가 아닙니다.")
    if Path(os.path.realpath(current)) != Path(os.path.realpath(root)).joinpath(*parts):
        raise _unsafe("저장소 밖을 가리킵니다.")
    return current


def _cache_file(directory: Path, name: str) -> Path:
    path = directory / name
    try:
        info = path.lstat()
    except FileNotFoundError:
        return path
    if not stat.S_ISREG(info.st_mode):
        raise _unsafe(f"{name}가 일반 파일이 아닙니다(심볼릭 링크 포함).")
    return path


def daily_path(root: Path, day: str, *, create: bool = False) -> Path | None:
    """Path of ``daily/{day}.json`` (may not exist), or None when the cache folder is absent."""
    directory = cache_dir(root, "daily", create=create)
    return None if directory is None else _cache_file(directory, f"{day}.json")


def search_path(root: Path, search_id: str, *, create: bool = False) -> Path | None:
    """Path of ``searches/{search_id}.json`` (may not exist), or None when the folder is absent."""
    directory = cache_dir(root, "searches", create=create)
    return None if directory is None else _cache_file(directory, f"{search_id}.json")


def read_json(path: Path) -> object:
    """Parse a cache file without following symlinks. Missing files raise FileNotFoundError; a
    non-regular file ``cache_unsafe``; undecodable JSON ``CacheError(500, "cache_corrupt")``."""
    try:
        handle = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise _unsafe(f"{path.name}: {exc.strerror or exc}") from exc
    with os.fdopen(handle, "rb") as source:
        if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
            raise _unsafe(f"{path.name}가 일반 파일이 아닙니다.")
        data = source.read()
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise CacheError(500, "cache_corrupt", f"{path.name}: JSON을 읽지 못했습니다: {exc}") from exc


def _write_new(path: Path, data: object) -> None:
    """Write ``data`` to ``path`` atomically, failing with FileExistsError when ``path`` exists."""
    temporary = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        write_json_atomic(temporary, data)
        os.link(temporary, path)  # atomic no-clobber publish
    finally:
        temporary.unlink(missing_ok=True)


def write_daily(root: Path, data: dict, *, replace: bool = False) -> Path:
    """Atomically write a prepared Daily to ``daily/{date}.json``. An existing day raises
    ``CacheError(409, "daily_exists")`` unless ``replace``."""
    errors = validate_daily(data)
    if errors:
        raise ValidationError(errors)
    path = daily_path(root, data["date"], create=True)
    if replace:
        write_json_atomic(path, data)
        return path
    try:
        _write_new(path, data)
    except FileExistsError:
        raise CacheError(409, "daily_exists",
                         f"{data['date']} 일일 후보가 이미 있습니다. 바꾸려면 --replace를 쓰세요.") from None
    return path


def write_session(root: Path, session: dict) -> Path:
    """Atomically write a validated search session to ``searches/{search_id}.json``."""
    errors = validate_session(session)
    if errors:
        raise ValidationError(errors)
    path = search_path(root, session["search_id"], create=True)
    write_json_atomic(path, session)
    return path


@contextmanager
def daily_lock(root: Path, day: str, *, create: bool = False):
    """Exclusive inter-process lock of ``daily/{day}.json`` for a read-modify-write: blocking
    ``fcntl.flock`` on ``daily/.{day}.lock`` (created ``0600`` without following symlinks, never
    deleted). Without the daily folder and ``create`` false nothing is locked (there is no file to
    change). The lock belongs to the open file description: do not nest it in one process.
    ``cache_unsafe`` when the folder or the lock file is a symlink or not a regular file."""
    if not valid_date(day):
        raise ValueError(f"invalid date: {day}")
    directory = cache_dir(root, "daily", create=create)
    if directory is None:
        yield None
        return
    lock_path = directory / f".{day}.lock"
    flags = os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
    try:
        handle = os.open(lock_path, flags, 0o600)
    except OSError as exc:
        raise _unsafe(f"{lock_path.name}: {exc.strerror or exc}") from exc
    try:
        if not stat.S_ISREG(os.fstat(handle).st_mode):
            raise _unsafe(f"{lock_path.name}가 일반 파일이 아닙니다.")
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield lock_path
    finally:
        os.close(handle)  # releases the flock


# ---- library index -------------------------------------------------------------------------------

_index_lock = threading.Lock()
_library_cache: dict[str, tuple[tuple, dict]] = {}
_conference_cache: dict[str, tuple[tuple, dict]] = {}


def _dois_in(text: object) -> list[str]:
    if not isinstance(text, str):
        return []
    return [doi for doi in (match.group(0).rstrip(DOI_TRAILING) for match in DOI_PATTERN.finditer(text)) if doi]


def _record_ids(record: dict) -> tuple[set[str], set[str], set[str]]:
    dois: set[str] = set()
    arxivs: set[str] = set()
    s2s: set[str] = set()
    paper_id = record.get("paper_id")
    if isinstance(paper_id, str):
        text = paper_id.strip()
        folded = text.casefold()
        if folded.startswith("arxiv:") and bare_arxiv(text[6:]):
            arxivs.add(bare_arxiv(text[6:]))
        elif folded.startswith("doi:") and bare_doi(text[4:]):
            dois.add(bare_doi(text[4:]).casefold())
        elif S2_ID.fullmatch(folded):
            s2s.add(folded)
    source = record.get("source") if isinstance(record.get("source"), dict) else {}
    urls = source.get("urls") if isinstance(source.get("urls"), list) else []
    for url in urls:
        if not isinstance(url, str):
            continue
        match = ARXIV_URL.search(url)
        if match:
            arxivs.add(match.group(1))
        match = DOI_URL.search(url)
        if match and bare_doi(match.group(1)):
            dois.add(bare_doi(match.group(1)).casefold())
    publication = record.get("publication") if isinstance(record.get("publication"), dict) else {}
    sources = publication.get("verification_sources")
    for text in sources if isinstance(sources, list) else []:
        dois.update(doi.casefold() for doi in _dois_in(text))
    arxivs.update(filter(None, (_arxiv_from_doi(doi) for doi in dois)))
    return dois, arxivs, s2s


def _build_library_index(root: Path, files: list[Path]) -> dict:
    index: dict = {"doi": {}, "arxiv": {}, "s2": {}, "title": {}, "errors": []}
    for path in files:
        relative = f"{LIBRARY_RELATIVE}/{path.name}"
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            index["errors"].append({"file": relative, "error": f"{type(exc).__name__}: {exc}"[:500]})
            continue
        if not isinstance(record, dict):
            index["errors"].append({"file": relative, "error": "레코드가 객체가 아닙니다"})
            continue
        slug = record.get("slug")
        if not (isinstance(slug, str) and SLUG_PATTERN.fullmatch(slug)):
            slug = path.stem
        dois, arxivs, s2s = _record_ids(record)
        for key, values in (("doi", dois), ("arxiv", arxivs), ("s2", s2s)):
            for value in values:
                index[key].setdefault(value, slug)
        title = normalize_title(record.get("title"))
        if title:
            index["title"].setdefault(title, slug)
    return index


def library_index(root: Path) -> dict:
    """Identifier and title maps of ``01-Papers/library/*.json`` (§2.3), cached until any file's
    name, size, or mtime changes. Do not mutate the result.

    ``{"doi": {casefold DOI: slug}, "arxiv": {id without version: slug}, "s2": {40-hex: slug},
    "title": {normalize_title: slug}, "errors": [{"file", "error"}]}``"""
    directory = Path(root) / LIBRARY_RELATIVE
    files = sorted(directory.glob("*.json")) if directory.is_dir() else []
    signature = []
    for path in files:
        try:
            info = path.stat()
            signature.append((path.name, info.st_size, info.st_mtime_ns))
        except OSError:
            signature.append((path.name, -1, -1))
    key = str(Path(root).resolve())
    with _index_lock:
        cached = _library_cache.get(key)
        if cached is not None and cached[0] == tuple(signature):
            return cached[1]
    value = _build_library_index(Path(root), files)
    with _index_lock:
        _library_cache[key] = (tuple(signature), value)
    return value


def library_match(candidate: dict, index: dict) -> dict | None:
    """``{"slug", "match": "id"}`` on a DOI/arXiv/S2 hit, ``{"slug", "match": "title"}`` on a
    normalized-title hit, else None."""
    ids = candidate.get("ids") if isinstance(candidate.get("ids"), dict) else {}
    doi = bare_doi(ids.get("DOI"))
    arxiv = bare_arxiv(ids.get("arXiv")) or _arxiv_from_doi(doi)
    s2 = _s2(ids.get("S2"))
    for table, value in (("doi", doi.casefold() if doi else None), ("arxiv", arxiv), ("s2", s2)):
        if value and value in index[table]:
            return {"slug": index[table][value], "match": "id"}
    title = normalize_title(candidate.get("title"))
    if title and title in index["title"]:
        return {"slug": index["title"][title], "match": "title"}
    return None


# ---- conference reference (cs-conferences.csv, shown as "참고") ----------------------------------

_QUALIFIED = re.compile(r"(.*?)\s*\(([^()]*)\)")
_TRAILING_PAREN = re.compile(r"\s*\([^()]*\)\s*$")
NAME_MATCH_MIN = 15


def _token_pattern(token: str) -> re.Pattern:
    # Acronym-like tokens (two or more capitals: ACL, NeurIPS, EuroS&P) match case-sensitively.
    flags = 0 if sum(ch.isupper() for ch in token) >= 2 else re.IGNORECASE
    return re.compile(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", flags)


def _score(value: str | None) -> float | None:
    try:
        return float(value) if value and value.strip() else None
    except ValueError:
        return None


def _build_conference_index(path: Path) -> dict:
    groups: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as source:
        for row in csv.DictReader(source):
            abbr = (row.get("약자") or "").strip()
            name = (row.get("학회명") or "").strip()
            if not abbr:
                continue
            match = _QUALIFIED.fullmatch(abbr)
            base, qualifier = (match.group(1).strip(), match.group(2).strip().casefold()) if match else (abbr, None)
            name_base = name
            if qualifier and name.casefold().endswith(f"({qualifier})"):
                name_base = name[:-(len(qualifier) + 2)].rstrip()
            group = groups.get(base)
            if group is None:
                alternatives = [alt.split() for alt in base.split("/") if alt.split()]
                plain = _TRAILING_PAREN.sub("", name_base)
                group = groups[base] = {
                    "base": base, "name": name_base,
                    "patterns": [[_token_pattern(token) for token in alt] for alt in alternatives],
                    "name_key": normalize_title(plain) if len(plain) >= NAME_MATCH_MIN else "",
                    "entries": []}
            group["entries"].append({"abbr": abbr, "name": name, "score": _score(row.get("평균 (정규화)")),
                                     "qualifier": qualifier})
    return {"groups": list(groups.values()), "error": None}


def conference_index(root: Path) -> dict:
    """Parsed ``01-Papers/reference/cs-conferences.csv`` (opaque; pass to ``conference_ref``),
    cached by size and mtime. A missing or unreadable file gives an index with no groups."""
    path = Path(root) / CONFERENCES_RELATIVE
    try:
        info = path.stat()
        signature = (info.st_size, info.st_mtime_ns)
    except OSError as exc:
        return {"groups": [], "error": f"{CONFERENCES_RELATIVE}: {exc.strerror or exc}"}
    key = str(path.resolve())
    with _index_lock:
        cached = _conference_cache.get(key)
        if cached is not None and cached[0] == signature:
            return cached[1]
    try:
        value = _build_conference_index(path)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        return {"groups": [], "error": f"{CONFERENCES_RELATIVE}: {type(exc).__name__}: {exc}"}
    with _index_lock:
        _conference_cache[key] = (signature, value)
    return value


def _group_ref(group: dict, venue: str) -> dict:
    entries = group["entries"]
    if len(entries) == 1 and entries[0]["qualifier"] is None:
        entry = entries[0]
        return {"abbr": entry["abbr"], "name": entry["name"], "score": entry["score"]}
    folded = venue.casefold()
    chosen = [entry for entry in entries if entry["qualifier"] and re.search(
        rf"(?<![a-z0-9]){re.escape(entry['qualifier'])}(?![a-z0-9])", folded)]
    if len(chosen) == 1:
        entry = chosen[0]
        return {"abbr": entry["abbr"], "name": entry["name"], "score": entry["score"]}
    # Presentation type unknown: the conference with the lowest variant score (conservative).
    scores = [entry["score"] for entry in entries if entry["score"] is not None]
    return {"abbr": group["base"], "name": group["name"], "score": min(scores) if scores else None}


def conference_ref(venue: object, index: dict | None) -> dict | None:
    """Reference row for ``venue``: ``{"abbr", "name", "score"}`` or None.

    Abbreviations match as whole words (acronyms case-sensitively); the entry with the most
    matched words wins (``Findings of ACL`` -> ``ACL Findings``), alternatives split on ``/``
    (``NeurIPS/NIPS``). Without an abbreviation hit the full conference name (at least 15
    characters, normalized) must appear in the venue. Ties between different conferences give
    None, and so does a workshop venue unless the matched name is itself a workshop. For
    oral/poster/spotlight rows the venue's word picks the row; otherwise the result is the bare
    abbreviation with the lowest variant score. A reference list, not a quality verdict.
    """
    if not isinstance(venue, str) or not venue.strip() or not index or not index.get("groups"):
        return None
    best, matched = 0, []
    for group in index["groups"]:
        words = max((len(alt) for alt in group["patterns"] if all(p.search(venue) for p in alt)), default=0)
        if words > best:
            best, matched = words, [group]
        elif words and words == best:
            matched.append(group)
    if not matched:
        normalized = f" {normalize_title(venue)} "
        matched = [group for group in index["groups"] if group["name_key"] and f" {group['name_key']} " in normalized]
    if len(matched) != 1:
        return None
    if "workshop" in venue.casefold() and "workshop" not in matched[0]["name"].casefold():
        return None  # a workshop of a listed conference is not that conference
    return _group_ref(matched[0], venue)


# ---- CLI -----------------------------------------------------------------------------------------

def _load_input(path: Path) -> object:
    with path.open(encoding="utf-8") as source:
        return json.load(source)


def _cmd_validate(args) -> int:
    status = 0
    for path in args.paths:
        try:
            data = _load_input(path)
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            print(f"{path}: 읽지 못했습니다: {exc}", file=sys.stderr)
            status = 2
            continue
        is_session = isinstance(data, dict) and "search_id" in data
        errors = validate_session(data) if is_session else validate_daily(data)
        if errors:
            status = 2
            for error in errors:
                print(f"{path}: {error}", file=sys.stderr)
        else:
            print(f"OK {path} ({'search' if is_session else 'daily'})")
    return status


def _cmd_daily_write(args) -> int:
    root = args.root
    try:
        raw = _load_input(args.input)
    except (UnicodeDecodeError, ValueError) as exc:
        print(f"{args.input}: JSON을 읽지 못했습니다: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"{args.input}: {exc}", file=sys.stderr)
        return 1
    try:
        errors = validate_daily(raw, limits=False)  # before the lock creates the cache folder
        if errors:
            raise ValidationError(errors)
        with daily_lock(root, raw["date"], create=True):  # WebUI status writes wait for this
            previous = None
            if args.replace:
                path = daily_path(root, raw["date"])
                try:
                    previous = read_json(path)
                except FileNotFoundError:
                    previous = None
                except CacheError as exc:
                    if exc.code != "cache_corrupt":
                        raise
            data = prepare_daily(raw, conferences=conference_index(root), previous=previous)
            path = write_daily(root, data, replace=args.replace)
    except ValidationError as exc:
        for error in exc.errors:
            print(f"{args.input}: {error}", file=sys.stderr)
        return 2
    except CacheError as exc:
        print(exc.message, file=sys.stderr)
        return 3 if exc.code == "daily_exists" else 1
    except OSError as exc:
        print(f"캐시를 쓰지 못했습니다: {exc}", file=sys.stderr)
        return 1
    try:
        shown = path.relative_to(root).as_posix()
    except ValueError:
        shown = str(path)
    print(shown)
    return 0


def _candidates_in(data: object) -> list:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("slots"), list):
        return [slot.get("candidate") for slot in data["slots"] if isinstance(slot, dict) and slot.get("candidate")]
    if isinstance(data.get("candidates"), list):
        return data["candidates"]
    return [data]


def _cmd_library_match(args) -> int:
    try:
        data = _load_input(args.path)
    except (UnicodeDecodeError, ValueError) as exc:
        print(f"{args.path}: JSON을 읽지 못했습니다: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"{args.path}: {exc}", file=sys.stderr)
        return 1
    index = library_index(args.root)
    matches = [{"candidate_id": candidate.get("candidate_id") or make_candidate_id(candidate),
                "title": candidate.get("title"), "key": candidate_key(candidate),
                "library": library_match(candidate, index)}
               for candidate in _candidates_in(data) if isinstance(candidate, dict)]
    print(json.dumps({"matches": matches, "errors": index["errors"]}, ensure_ascii=False, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="discovery_cache.py",
                                     description="WebUI 논문 탐색 캐시(00-Inbox/discovery) 검증·기록 도구")
    parser.add_argument("--root", type=Path, default=ROOT, help="저장소 루트(기본: 이 스크립트의 저장소)")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="일일 후보·검색 세션 JSON 검증(종료 0/2)")
    validate.add_argument("paths", nargs="+", type=Path)
    daily = commands.add_parser("daily-write", help="일일 후보 JSON을 검증·정규화해 daily/{date}.json에 기록")
    daily.add_argument("input", type=Path)
    daily.add_argument("--replace", action="store_true", help="같은 날짜 파일이 있으면 바꾼다")
    match = commands.add_parser("library-match", help="파일의 후보를 라이브러리와 대조(디버그)")
    match.add_argument("path", type=Path)
    args = parser.parse_args(argv)
    handlers = {"validate": _cmd_validate, "daily-write": _cmd_daily_write, "library-match": _cmd_library_match}
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
