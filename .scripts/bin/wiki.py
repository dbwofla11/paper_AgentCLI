#!/usr/bin/env python3
"""Maintain the LLM-Wiki index, append-only work log, and structural lint.

Commands:
  index [--check] [--json]   regenerate wiki-index.md (or only compare it)
  log --op OP --title TEXT   append one entry to wiki-log.md
  lint [--json]              report broken links, stale index, orphans, missing titles

The index header links only the 01-Papers list files that exist. Sections in
ORPHAN_EXEMPT (Trends: a chronological digest series reached through
wiki-index.md) are not reported as orphan-page.

Lint levels (links inside fenced/inline code and HTML comments are skipped):
  ERROR   stale-index, broken-link (missing local target)
  WARNING orphan-page, missing-title, outside-repo (target resolves outside the
          repository root; existence is not checked)
  INFO    missing-source (missing target under 01-Papers/pdfs/; source PDFs are
          intentionally not committed)

Exit codes: 0 ok, 1 check failure or any lint ERROR, 2 usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import string
import sys
import tempfile
import urllib.parse
from datetime import date
from fnmatch import fnmatchcase
from pathlib import Path

from harness_common import git_visible_files

ROOT = Path(__file__).resolve().parents[2]
INDEX_NAME = "wiki-index.md"
LOG_NAME = "wiki-log.md"
PAPER_LISTS = (("논문 인덱스", "01-Papers/index.md"), ("Keep", "01-Papers/keep.md"), ("즐겨찾기", "01-Papers/favorites.md"))
# Wiki page scope: (section, patterns). Patterns match one path segment per `*`.
PAGE_SCOPE = (
    ("Papers", ("01-Papers/reviews/*/*.md",)),
    ("Triage", ("01-Papers/triage/*.md",)),
    ("Concepts", ("02-Concepts/*.md",)),
    ("Trends", ("03-Trends/daily/*.md",)),
    ("Ideas", ("05-Ideas/thought-experiments/*.md",)),
    ("Projects", tuple(f"04-Projects/thought-experiment-runs/*/{name}.md" for name in ("results", "critique", "manifest"))),
)
# Sections whose pages are not expected to have inbound links (lint orphan-page).
ORPHAN_EXEMPT = frozenset({"Trends"})
INDEX_GENERATED_LINE = "자동 생성 파일. 직접 수정하지 말고 python3 .scripts/bin/wiki.py index로 갱신한다."
LOG_HEADER = "# 작업 기록\n\n추가만 한다. 기존 항목을 수정·삭제하지 않는다.\n"
LOG_OPS = ("ingest", "update", "query", "lint")
SUMMARY_LIMIT = 120
GIT_ERROR = "Git 제외 규칙을 확인하지 못해 위키 페이지 목록을 만들지 않았습니다"
# Missing link targets under this repo-relative prefix are source PDFs kept out of Git (lint INFO).
SOURCE_PDF_DIR = "01-Papers/pdfs/"

ASCII_PUNCTUATION = frozenset(string.punctuation)
INLINE_CODE = re.compile(r"(`+)(?:(?!\1).)+?\1")
SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
LIST_MARKER = re.compile(r"^(?:[-*+]|\d+[.)])(?:\s|$)")
HORIZONTAL_RULE = re.compile(r"^(?:-{3,}|\*{3,}|_{3,})$")


class UsageError(ValueError):
    """Invalid command-line value (exit 2)."""


# ---------------------------------------------------------------- page scope

def _excluded(name: str) -> bool:
    return name == "README.md" or name == ".gitkeep" or "template" in name.casefold()


def _matches(relative: str, pattern: str) -> bool:
    parts, wanted = relative.split("/"), pattern.split("/")
    return len(parts) == len(wanted) and all(fnmatchcase(part, glob) for part, glob in zip(parts, wanted))


def scoped_pages(root: Path | None = None) -> dict[str, list[str]]:
    """Return section -> sorted repo-relative page paths (Git-visible files only)."""
    root = ROOT if root is None else root
    listing = git_visible_files(root, GIT_ERROR)
    if listing is None:
        candidates = {path.relative_to(root).as_posix()
                      for _, patterns in PAGE_SCOPE for pattern in patterns for path in root.glob(pattern)}
    else:
        candidates = {path.as_posix() for path in listing}
    sections: dict[str, list[str]] = {}
    for section, patterns in PAGE_SCOPE:
        sections[section] = sorted(
            relative for relative in candidates
            if any(_matches(relative, pattern) for pattern in patterns)
            and not _excluded(relative.rsplit("/", 1)[-1]) and (root / relative).is_file()
        )
    return sections


# ---------------------------------------------------------------- page parsing

def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _split_frontmatter(lines: list[str]) -> tuple[dict[str, str], int]:
    """Return (frontmatter fields, index of the first body line)."""
    if not lines or lines[0].strip() != "---":
        return {}, 0
    for end in range(1, len(lines)):
        if lines[end].strip() in ("---", "..."):
            break
    else:
        return {}, 0
    fields: dict[str, str] = {}
    key = None
    for line in lines[1:end]:
        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if match:
            key, value = match.group(1), match.group(2).strip()
            block = value in ("|", ">", "|-", ">-", "|+", ">+")
            fields[key] = "" if block else _unquote(value)
            if value and not block:
                key = None
        elif key and line[:1].isspace():
            fields[key] = (fields[key] + " " + line.strip()).strip()
    return fields, end + 1


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _body_lines(lines: list[str], start: int):
    """Yield (line number, text) for body lines outside fenced code blocks."""
    fence = None
    for number in range(start, len(lines)):
        stripped = lines[number].strip()
        marker = re.match(r"^(`{3,}|~{3,})", stripped)
        if fence:
            if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                fence = None
            continue
        if marker:
            fence = marker.group(1)
            continue
        yield number + 1, lines[number]


def _parse_link_tail(text: str, pos: int) -> tuple[str, int] | None:
    """Parse `destination [title])` after an inline link's `(` (CommonMark).

    Returns (unescaped destination, index after the closing `)`), or None when
    the tail is not a valid inline link. Bare destinations may contain balanced
    or backslash-escaped parentheses; `<...>` destinations may contain spaces.
    """
    size = len(text)
    while pos < size and text[pos] in " \t":
        pos += 1
    chars: list[str] = []
    if pos < size and text[pos] == "<":
        pos += 1
        while pos < size and text[pos] not in "<>\n":
            if text[pos] == "\\" and pos + 1 < size and text[pos + 1] in ASCII_PUNCTUATION:
                pos += 1
            chars.append(text[pos])
            pos += 1
        if pos >= size or text[pos] != ">":
            return None
        pos += 1
    else:
        depth = 0
        while pos < size:
            char = text[pos]
            if char == "\\" and pos + 1 < size and text[pos + 1] in ASCII_PUNCTUATION:
                chars.append(text[pos + 1])
                pos += 2
                continue
            if char.isspace() or ord(char) < 0x20:
                break
            if char == "(":
                depth += 1
            elif char == ")":
                if depth == 0:
                    break
                depth -= 1
            chars.append(char)
            pos += 1
        if depth:
            return None
    after = pos
    while pos < size and text[pos] in " \t":
        pos += 1
    if pos > after and pos < size and text[pos] in "\"'(":
        closer = ")" if text[pos] == "(" else text[pos]
        pos += 1
        while pos < size and text[pos] != closer:
            pos += 2 if text[pos] == "\\" else 1
        if pos >= size:
            return None
        pos += 1
        while pos < size and text[pos] in " \t":
            pos += 1
    if pos < size and text[pos] == ")":
        return "".join(chars), pos + 1
    return None


def _skip_code_span(text: str, pos: int) -> int:
    """Return the index after the code span opened by the backtick run at pos.

    CommonMark: the span closes at the next backtick run of exactly the same
    length; an unmatched run is literal text, so only the run itself is skipped.
    """
    end = pos
    while end < len(text) and text[end] == "`":
        end += 1
    size = end - pos
    search = end
    while (found := text.find("`" * size, search)) >= 0:
        stop = found + size
        if text[found - 1] != "`" and text[stop:stop + 1] != "`":
            return stop
        while stop < len(text) and text[stop] == "`":
            stop += 1
        search = stop
    return end


def _label_end(text: str, start: int) -> int | None:
    """Return the index of the `]` balancing the `[` at start, or None.

    Backslash escapes and code-span contents do not count as brackets.
    """
    depth = 0
    pos = start
    while pos < len(text):
        char = text[pos]
        if char == "\\":
            pos += 2
            continue
        if char == "`":
            pos = _skip_code_span(text, pos)
            continue
        if char == "[":
            depth += 1
        elif char == "]":
            depth -= 1
            if depth == 0:
                return pos
        pos += 1
    return None


def markdown_links(text: str):
    """Yield (start, end, label, destination) for top-level inline links and images in one line.

    Labels are matched with balanced brackets, so a label may itself contain
    links or images (`[![alt](img.svg)](page.md)`); callers recurse into labels.
    Escaped brackets and brackets inside code spans never open or close a link.
    """
    pos = 0
    while pos < len(text):
        char = text[pos]
        if char == "\\":
            pos += 2
            continue
        if char == "`":
            pos = _skip_code_span(text, pos)
            continue
        if char != "[":
            pos += 1
            continue
        start = pos
        close = _label_end(text, start)
        parsed = (_parse_link_tail(text, close + 2)
                  if close is not None and text[close + 1:close + 2] == "(" else None)
        if parsed is None:
            pos = start + 1
            continue
        destination, end = parsed
        begin = start - 1 if start and text[start - 1] == "!" else start
        yield begin, end, text[start + 1:close], destination
        pos = end


def link_destinations(text: str):
    """Yield every link/image destination in one line, outer links before their labels' links."""
    for _, _, label, destination in markdown_links(text):
        yield destination
        yield from link_destinations(label)


def _strip_links(text: str) -> str:
    """Replace links and images with their (recursively plain) label or alt text."""
    pieces, last = [], 0
    for start, end, label, _ in markdown_links(text):
        pieces += [text[last:start], _strip_links(label)]
        last = end
    return "".join(pieces) + text[last:]


def plain_text(text: str) -> str:
    text = re.sub(r"<!--.*?-->", "", text)
    text = _strip_links(text)
    text = re.sub(r"\[\[([^\]|]*)\|([^\]]*)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]*)\]\]", r"\1", text)
    text = re.sub(r"`+([^`]*)`+", r"\1", text)
    text = re.sub(r"<[^>\n]+>", "", text)
    text = re.sub(r"(\*\*|__|~~)(.+?)\1", r"\2", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"\1", text)
    text = re.sub(r"^\s*>+\s?", "", text)
    return " ".join(text.split())


def page_info(path: Path) -> dict:
    lines = _read(path).splitlines()
    fields, start = _split_frontmatter(lines)
    heading = None
    summary = None
    in_comment = False
    for _, line in _body_lines(lines, start):
        stripped = line.strip()
        if in_comment:
            in_comment = "-->" not in stripped
            continue
        if stripped.startswith("<!--") and "-->" not in stripped:
            in_comment = True
            continue
        if heading is None and re.match(r"^#\s+\S", stripped):
            heading = plain_text(re.sub(r"\s+#+\s*$", "", stripped[1:]).strip())
        if summary is None and not (not stripped or stripped.startswith(("#", "|"))
                                    or LIST_MARKER.match(stripped) or HORIZONTAL_RULE.match(stripped)):
            summary = plain_text(stripped) or None
        if heading is not None and summary is not None:
            break
    title = fields.get("title", "").strip() or heading or path.stem
    for key in ("summary", "description"):
        if fields.get(key, "").strip():
            summary = plain_text(fields[key])
            break
    if summary and len(summary) > SUMMARY_LIMIT:
        summary = summary[:SUMMARY_LIMIT - 1].rstrip() + "…"
    return {"title": title, "summary": summary or "", "has_title": bool(fields.get("title", "").strip() or heading)}


# ---------------------------------------------------------------- index

def _link_target(relative: str) -> str:
    return f"<{relative}>" if re.search(r"[\s()<>]", relative) else relative


def render_index(root: Path | None = None, sections: dict[str, list[str]] | None = None,
                 list_files: tuple[str, ...] | None = None) -> str:
    """Render wiki-index.md; list_files overrides which 01-Papers lists exist (installer plans)."""
    root = ROOT if root is None else root
    sections = scoped_pages(root) if sections is None else sections
    present = ({name for _, name in PAPER_LISTS if (root / name).is_file()} if list_files is None else set(list_files))
    links = " · ".join(f"[{label}]({name})" for label, name in PAPER_LISTS if name in present)
    parts = [f"# 위키 인덱스\n\n{INDEX_GENERATED_LINE}\n" + (f"\n목록: {links}\n" if links else "")]
    for section, _ in PAGE_SCOPE:
        parts.append(f"\n## {section}\n\n")
        entries = []
        for relative in sections[section]:
            info = page_info(root / relative)
            title = info["title"].replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
            entry = f"- [{title}]({_link_target(relative)})"
            entries.append(entry + (f": {info['summary']}" if info["summary"] else "") + "\n")
        parts.append("".join(entries) if entries else "없음.\n")
    return "".join(parts)


def index_state(root: Path) -> tuple[str, str, dict[str, list[str]]]:
    """Return (status fresh|stale|missing, rendered text, sections)."""
    sections = scoped_pages(root)
    rendered = render_index(root, sections)
    path = root / INDEX_NAME
    if not path.is_file():
        return "missing", rendered, sections
    return ("fresh" if path.read_bytes() == rendered.encode("utf-8") else "stale"), rendered, sections


def _write_atomic(path: Path, text: str) -> None:
    temporary = None
    try:
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="\n", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as output:
            temporary = Path(output.name)
            output.write(text)
        os.chmod(temporary, (path.stat().st_mode & 0o777) if path.exists() else 0o644)
        temporary.replace(path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def cmd_index(args: argparse.Namespace) -> int:
    root = ROOT
    state, rendered, sections = index_state(root)
    if args.check:
        status = state
    elif state == "fresh":
        status = "unchanged"
    else:
        _write_atomic(root / INDEX_NAME, rendered)
        status = "written"
    report = {
        "path": INDEX_NAME, "mode": "check" if args.check else "write", "status": status,
        "pages": sum(len(paths) for paths in sections.values()),
        "sections": [{"name": name, "count": len(sections[name])} for name, _ in PAGE_SCOPE],
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif status in ("stale", "missing"):
        print(f"{INDEX_NAME} is {status}; run python3 .scripts/bin/wiki.py index")
    else:
        print(f"{INDEX_NAME} {status} ({report['pages']} pages)")
    return 1 if status in ("stale", "missing") else 0


# ---------------------------------------------------------------- log

def repo_relative(value: str, root: Path | None = None) -> str:
    root = ROOT if root is None else root
    candidate = Path(value).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    lexical = Path(os.path.normpath(candidate))
    for base, path in ((Path(os.path.normpath(root)), lexical), (root.resolve(), lexical.resolve())):
        try:
            relative = path.relative_to(base)
        except ValueError:
            continue
        if relative.parts:
            return relative.as_posix()
    raise UsageError(f"path is outside the repository: {value}")


def cmd_log(args: argparse.Namespace) -> int:
    title = args.title.strip()
    if not title or "\n" in title or "\r" in title:
        raise UsageError("--title must be one non-empty line")
    if args.date is None:
        day = date.today().isoformat()
    else:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", args.date):
                raise ValueError
            day = date.fromisoformat(args.date).isoformat()
        except ValueError:
            raise UsageError("--date must be YYYY-MM-DD") from None
    paths = [repo_relative(value) for value in args.path or ()]
    entry = f"\n## [{day}] {args.op} | {title}\n" + "".join(f"- {path}\n" for path in paths)
    path = ROOT / LOG_NAME
    with path.open("a", encoding="utf-8", newline="\n") as output:
        if output.tell() == 0:
            output.write(LOG_HEADER)
        else:
            with path.open("rb") as existing:
                existing.seek(-1, os.SEEK_END)
                if existing.read(1) != b"\n":
                    output.write("\n")
        output.write(entry)
    print(f"{LOG_NAME}: appended [{day}] {args.op} | {title}")
    return 0


# ---------------------------------------------------------------- lint

def _visible_text(line: str) -> tuple[str, bool]:
    """Blank inline code spans and `<!-- … -->` regions outside a comment, scanning left to right.

    Inside a code span `<!--` is literal; returns (visible text, comment still open at line end).
    """
    visible = []
    pos = 0
    while pos < len(line):
        tick = line.find("`", pos)
        opener = line.find("<!--", pos)
        if opener < 0 and tick < 0:
            visible.append(line[pos:])
            break
        if opener < 0 or 0 <= tick < opener:
            span = INLINE_CODE.match(line, tick)
            end = span.end() if span else tick + 1
            visible.append(line[pos:tick] + (" " * (end - tick) if span else "`"))
            pos = end
            continue
        visible.append(line[pos:opener] + " ")
        closer = line.find("-->", opener + 4)
        if closer < 0:
            return "".join(visible), True
        pos = closer + 3
    return "".join(visible), False


def iter_links(path: Path):
    """Yield (line number, destination) for Markdown links outside fenced code, inline code, and HTML comments.

    An open HTML comment takes precedence: inside it only `-->` matters and code syntax is literal.
    Outside comments, fenced code and code spans keep `<!--` literal.
    """
    fence = None
    in_comment = False
    for number, line in enumerate(_read(path).splitlines(), 1):
        if in_comment:
            closer = line.find("-->")
            if closer < 0:
                continue
            in_comment = False
            line = " " * (closer + 3) + line[closer + 3:]
        else:
            marker = re.match(r"^(`{3,}|~{3,})", line.strip())
            if fence:
                if marker and marker.group(1)[0] == fence[0] and len(marker.group(1)) >= len(fence):
                    fence = None
                continue
            if marker:
                fence = marker.group(1)
                continue
        line, in_comment = _visible_text(line)
        for destination in link_destinations(line):
            yield number, destination


def local_target(target: str) -> str | None:
    """Strip anchors/queries; None for external, absolute, or anchor-only links."""
    if SCHEME.match(target) or target.startswith(("/", "\\")):
        return None
    target = re.split(r"[#?]", target, maxsplit=1)[0]
    return urllib.parse.unquote(target) or None


def _finding(level: str, code: str, path: str, line: int | None, detail: str) -> dict:
    return {"level": level, "code": code, "path": path, "line": line, "detail": detail}


def lint(root: Path | None = None) -> list[dict]:
    root = ROOT if root is None else root
    state, _, sections = index_state(root)
    pages = sorted(path for paths in sections.values() for path in paths)
    findings: list[dict] = []
    if state != "fresh":
        findings.append(_finding("ERROR", "stale-index", INDEX_NAME, None,
                                 f"{INDEX_NAME} is {state}; run python3 .scripts/bin/wiki.py index"))
    lists = [name for _, name in PAPER_LISTS if (root / name).is_file()]
    exempt = {page for section in ORPHAN_EXEMPT for page in sections.get(section, ())}
    checked = pages + lists + ([INDEX_NAME] if (root / INDEX_NAME).is_file() else [])
    link_sources = set(pages) | set(lists)
    page_set = set(pages)
    resolved_root = root.resolve()
    lexical_root = Path(os.path.normpath(root))
    source_pdfs = resolved_root / SOURCE_PDF_DIR
    inbound: dict[str, set[str]] = {page: set() for page in pages}
    for source in checked:
        directory = (root / source).parent
        for line, raw in iter_links(root / source):
            target = local_target(raw)
            if target is None:
                continue
            absolute = Path(os.path.normpath(directory / target))
            try:
                resolved = (directory / target).resolve()
            except (OSError, RuntimeError):
                findings.append(_finding("ERROR", "broken-link", source, line, f"unresolvable target {raw}"))
                continue
            if resolved != resolved_root and resolved_root not in resolved.parents:
                findings.append(_finding("WARNING", "outside-repo", source, line, f"target outside repository {raw}"))
                continue
            if not resolved.exists():
                if source_pdfs in resolved.parents:
                    findings.append(_finding("INFO", "missing-source", source, line,
                                             f"원문 PDF는 저장소에 포함되지 않음: {raw}"))
                else:
                    findings.append(_finding("ERROR", "broken-link", source, line, f"missing target {raw}"))
                continue
            if source not in link_sources:
                continue
            keys = set()
            for candidate, base in ((absolute, lexical_root), (resolved, resolved_root)):
                try:
                    keys.add(candidate.relative_to(base).as_posix())
                except ValueError:
                    pass
            for key in keys & page_set:
                if key != source:
                    inbound[key].add(source)
    for page in pages:
        if not inbound[page] and page not in exempt:
            findings.append(_finding("WARNING", "orphan-page", page, None,
                                     "no inbound links from other wiki pages or 01-Papers lists"))
        if not page_info(root / page)["has_title"]:
            findings.append(_finding("WARNING", "missing-title", page, None, "no frontmatter title and no H1"))
    order = {"ERROR": 0, "WARNING": 1, "INFO": 2}
    findings.sort(key=lambda item: (order[item["level"]], item["path"], item["line"] or 0, item["code"], item["detail"]))
    return findings


def cmd_lint(args: argparse.Namespace) -> int:
    findings = lint(ROOT)
    errors = sum(item["level"] == "ERROR" for item in findings)
    warnings = sum(item["level"] == "WARNING" for item in findings)
    if args.json:
        print(json.dumps(findings, ensure_ascii=False, indent=2))
    else:
        for item in findings:
            location = item["path"] + (f":{item['line']}" if item["line"] else "")
            print(f"{item['level']} {item['code']} {location} {item['detail']}")
        print(f"wiki lint: {errors} error(s), {warnings} warning(s), {len(findings) - errors - warnings} info")
    return 1 if errors else 0


# ---------------------------------------------------------------- CLI

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    index = commands.add_parser("index", help=f"regenerate {INDEX_NAME} from the wiki page scope")
    index.add_argument("--check", action="store_true", help="write nothing; exit 1 if the index is missing or stale")
    index.add_argument("--json", action="store_true", help="print a JSON report")
    index.set_defaults(handler=cmd_index)
    log = commands.add_parser("log", help=f"append one entry to {LOG_NAME}")
    log.add_argument("--op", required=True, choices=LOG_OPS)
    log.add_argument("--title", required=True)
    log.add_argument("--path", action="append", metavar="P", help="repo-relative (or absolute in-repo) path; repeatable")
    log.add_argument("--date", metavar="YYYY-MM-DD", help="entry date (default: today, local time)")
    log.set_defaults(handler=cmd_log)
    check = commands.add_parser("lint", help="report broken links, stale index, orphan pages, missing titles")
    check.add_argument("--json", action="store_true", help="print findings as a JSON list")
    check.set_defaults(handler=cmd_lint)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exit_:
        return exit_.code if isinstance(exit_.code, int) else 2
    try:
        return args.handler(args)
    except UsageError as error:
        print(f"wiki.py: error: {error}", file=sys.stderr)
        return 2
    except (RuntimeError, OSError) as error:
        print(f"wiki.py: error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
