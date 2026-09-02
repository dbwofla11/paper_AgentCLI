#!/usr/bin/env python3
"""논문 검색·메타데이터·PDF 다운로드 CLI.

표준 라이브러리만 사용한다 (설치 불필요). API 키 없이 동작하되
Semantic Scholar는 무키 호출 시 rate limit(429)이 걸릴 수 있다.

사용법:
    python scripts/paper.py search "query" [--source arxiv|s2|openalex] [--limit N]
    python scripts/paper.py meta <arxiv_id|doi|s2_id> [--bibtex]
    python scripts/paper.py pdf  <arxiv_id> [--out papers]
    python scripts/paper.py refs  <id> [--limit N]
    python scripts/paper.py cites <id> [--limit N]

모든 명령에 --json 을 붙이면 원시 JSON을 출력한다.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = "paper-review-agent/1.0 (personal literature review)"
TIMEOUT = 30
# 있으면 Semantic Scholar rate limit 이 크게 완화된다 (무료 발급).
S2_KEY = os.environ.get("S2_API_KEY", "").strip()

ARXIV_API = "http://export.arxiv.org/api/query"
S2_API = "https://api.semanticscholar.org/graph/v1"
OPENALEX_API = "https://api.openalex.org/works"

S2_FIELDS = "title,year,venue,citationCount,externalIds,authors,abstract,openAccessPdf"

ARXIV_ID_RE = re.compile(r"^(?:arxiv:)?(\d{4}\.\d{4,5})(v\d+)?$", re.I)
DOI_RE = re.compile(r"^(?:doi:)?(10\.\d{4,9}/\S+)$", re.I)


# ---------------------------------------------------------------- utilities

def die(msg: str, code: int = 1) -> "NoReturn":  # type: ignore[name-defined]
    print(f"오류: {msg}", file=sys.stderr)
    sys.exit(code)


class FetchError(Exception):
    pass


def fetch(url: str, accept: str | None = None, soft: bool = False,
          retries: int = 2) -> bytes | None:
    """soft=True 면 실패 시 None 을 반환한다 (폴백 경로용)."""
    headers = {"User-Agent": UA}
    if accept:
        headers["Accept"] = accept
    if S2_KEY and "semanticscholar.org" in url:
        headers["x-api-key"] = S2_KEY
    last = ""
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                return resp.read()
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code == 429 and attempt < retries:
                time.sleep(2 * (attempt + 1))  # 무키 S2 는 429 가 잦다 — 짧게 재시도
                continue
            if e.code == 429:
                last = "rate limit (429) — 몇 초 뒤 재시도하거나 --source arxiv / --source openalex 사용"
            break
        except urllib.error.URLError as e:
            last = f"네트워크 실패: {e.reason}"
            break
    if soft:
        return None
    die(f"{last} — {url}")


def fetch_json(url: str, soft: bool = False) -> dict | None:
    raw = fetch(url, soft=soft)
    if raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        if soft:
            return None
        die(f"JSON 파싱 실패 — {url}")


def slugify(text: str, max_words: int = 7) -> str:
    words = re.sub(r"[^a-z0-9\s-]", " ", text.lower()).split()
    stop = {"a", "an", "the", "of", "for", "on", "in", "with", "and", "to", "via", "is", "are"}
    kept = [w for w in words if w not in stop][:max_words] or words[:max_words]
    return re.sub(r"-+", "-", "-".join(kept))[:60].strip("-") or "untitled"


def surname(author: str) -> str:
    """'Ashish Vaswani' -> 'vaswani'. 'Vaswani, Ashish' -> 'vaswani'."""
    if not author:
        return "unknown"
    part = author.split(",")[0] if "," in author else author.split()[-1]
    return re.sub(r"[^a-z]", "", part.lower()) or "unknown"


def normalize_id(raw: str) -> str:
    """S2 가 이해하는 ID 로 정규화."""
    raw = raw.strip()
    m = ARXIV_ID_RE.match(raw)
    if m:
        return f"arXiv:{m.group(1)}"
    m = DOI_RE.match(raw)
    if m:
        return f"DOI:{m.group(1)}"
    if raw.lower().startswith(("corpusid:", "mag:", "acl:", "pmid:", "url:")):
        return raw
    return raw  # 40자 S2 paperId 등


def arxiv_bare_id(raw: str) -> str | None:
    m = ARXIV_ID_RE.match(raw.strip())
    return m.group(1) if m else None


def fmt_authors(names: list[str], limit: int = 3) -> str:
    if not names:
        return "저자 미상"
    if len(names) <= limit:
        return ", ".join(names)
    return f"{', '.join(names[:limit])} 외 {len(names) - limit}인"


def out(rows: list[dict], as_json: bool) -> None:
    if as_json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    if not rows:
        print("결과 없음.")
        return
    for i, r in enumerate(rows, 1):
        cites = r.get("citations")
        cite_s = f" · 인용 {cites}" if cites is not None else ""
        print(f"\n[{i}] {r['title']}")
        print(f"    {fmt_authors(r.get('authors', []))} · {r.get('venue') or '?'} {r.get('year') or '?'}{cite_s}")
        ids = " ".join(f"{k}:{v}" for k, v in (r.get("ids") or {}).items() if v)
        if ids:
            print(f"    {ids}")
        if r.get("url"):
            print(f"    {r['url']}")
        if r.get("abstract"):
            abstract = " ".join(r["abstract"].split())
            print(f"    {abstract[:260]}{'…' if len(abstract) > 260 else ''}")
    print(f"\n총 {len(rows)}건.")


# ------------------------------------------------------------------ sources

def search_arxiv(query: str, limit: int) -> list[dict]:
    params = urllib.parse.urlencode({
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": limit,
        "sortBy": "relevance",
    })
    root = ET.fromstring(fetch(f"{ARXIV_API}?{params}"))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    rows = []
    for e in root.findall("a:entry", ns):
        raw_id = (e.findtext("a:id", "", ns) or "").rsplit("/", 1)[-1]
        published = e.findtext("a:published", "", ns) or ""
        rows.append({
            "title": " ".join((e.findtext("a:title", "", ns) or "").split()),
            "authors": [a.findtext("a:name", "", ns) for a in e.findall("a:author", ns)],
            "year": published[:4] or None,
            "venue": "arXiv",
            "citations": None,
            "ids": {"arXiv": raw_id},
            "url": f"https://arxiv.org/abs/{raw_id}",
            "abstract": " ".join((e.findtext("a:summary", "", ns) or "").split()),
        })
    return rows


def _s2_row(p: dict) -> dict:
    ext = p.get("externalIds") or {}
    return {
        "title": p.get("title") or "(제목 없음)",
        "authors": [a.get("name", "") for a in (p.get("authors") or [])],
        "year": p.get("year"),
        "venue": p.get("venue") or None,
        "citations": p.get("citationCount"),
        "ids": {"arXiv": ext.get("ArXiv"), "DOI": ext.get("DOI"), "S2": p.get("paperId")},
        "url": (p.get("openAccessPdf") or {}).get("url")
        or (f"https://arxiv.org/abs/{ext['ArXiv']}" if ext.get("ArXiv") else None),
        "abstract": p.get("abstract"),
    }


def search_s2(query: str, limit: int) -> list[dict]:
    params = urllib.parse.urlencode({"query": query, "limit": limit, "fields": S2_FIELDS})
    data = fetch_json(f"{S2_API}/paper/search?{params}")
    return [_s2_row(p) for p in data.get("data", [])]


def search_openalex(query: str, limit: int) -> list[dict]:
    params = urllib.parse.urlencode({"search": query, "per-page": limit})
    data = fetch_json(f"{OPENALEX_API}?{params}")
    rows = []
    for w in data.get("results", []):
        loc = (w.get("primary_location") or {}).get("source") or {}
        rows.append({
            "title": w.get("display_name") or "(제목 없음)",
            "authors": [a["author"]["display_name"] for a in (w.get("authorships") or [])
                        if a.get("author", {}).get("display_name")],
            "year": w.get("publication_year"),
            "venue": loc.get("display_name"),
            "citations": w.get("cited_by_count"),
            "ids": {"DOI": (w.get("doi") or "").replace("https://doi.org/", "") or None,
                    "OpenAlex": (w.get("id") or "").rsplit("/", 1)[-1]},
            "url": w.get("doi"),
            "abstract": None,
        })
    return rows


def meta_from_arxiv(bare: str) -> dict | None:
    raw = fetch(f"{ARXIV_API}?{urllib.parse.urlencode({'id_list': bare})}", soft=True)
    if raw is None:
        return None
    ns = {"a": "http://www.w3.org/2005/Atom"}
    entry = ET.fromstring(raw).find("a:entry", ns)
    if entry is None or entry.findtext("a:title", "", ns) in (None, "Error"):
        return None
    doi = entry.findtext("{http://arxiv.org/schemas/atom}doi", None, {})
    return {
        "title": " ".join((entry.findtext("a:title", "", ns) or "").split()),
        "authors": [a.findtext("a:name", "", ns) for a in entry.findall("a:author", ns)],
        "year": (entry.findtext("a:published", "", ns) or "")[:4] or None,
        "venue": entry.findtext("{http://arxiv.org/schemas/atom}journal_ref", "arXiv", {}) or "arXiv",
        "citations": None,
        "ids": {"arXiv": bare, "DOI": doi, "S2": None},
        "url": f"https://arxiv.org/abs/{bare}",
        "abstract": " ".join((entry.findtext("a:summary", "", ns) or "").split()),
    }


def meta_from_crossref(doi: str) -> dict | None:
    data = fetch_json(f"https://api.crossref.org/works/{urllib.parse.quote(doi)}", soft=True)
    if not data or "message" not in data:
        return None
    m = data["message"]
    parts = (m.get("published-print") or m.get("published-online") or {}).get("date-parts") or [[None]]
    return {
        "title": (m.get("title") or ["(제목 없음)"])[0],
        "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in (m.get("author") or [])],
        "year": parts[0][0],
        "venue": (m.get("container-title") or [None])[0],
        "citations": m.get("is-referenced-by-count"),
        "ids": {"arXiv": None, "DOI": m.get("DOI"), "S2": None},
        "url": m.get("URL"),
        "abstract": None,
    }


def get_meta(paper_id: str) -> dict:
    """S2 우선, 실패하면 arXiv / Crossref 로 폴백한다."""
    pid = normalize_id(paper_id)
    data = fetch_json(
        f"{S2_API}/paper/{urllib.parse.quote(pid, safe=':/')}?fields={S2_FIELDS}", soft=True)
    if data and data.get("title"):
        return _s2_row(data)

    bare = arxiv_bare_id(paper_id)
    if bare:
        row = meta_from_arxiv(bare)
        if row:
            print("[알림] Semantic Scholar 실패 — arXiv API 로 조회함 (인용수 없음).", file=sys.stderr)
            return row
    m = DOI_RE.match(paper_id.strip())
    if m:
        row = meta_from_crossref(m.group(1))
        if row:
            print("[알림] Semantic Scholar 실패 — Crossref 로 조회함.", file=sys.stderr)
            return row
    die(f"메타데이터를 가져오지 못했다: {paper_id} (rate limit 이면 몇 초 뒤 재시도)")


def get_bibtex(paper_id: str, meta: dict) -> str | None:
    """실제 서버에서 받아온 BibTeX만 반환한다. 없으면 None — 지어내지 않는다."""
    bare = arxiv_bare_id(paper_id) or (meta.get("ids") or {}).get("arXiv")
    if bare:
        raw = fetch(f"https://arxiv.org/bibtex/{bare}", soft=True)
        if raw and b"@" in raw:
            return raw.decode("utf-8", "replace").strip()
    doi = (meta.get("ids") or {}).get("DOI")
    if doi:
        raw = fetch(f"https://doi.org/{doi}", accept="application/x-bibtex", soft=True)
        if raw and b"@" in raw:
            return raw.decode("utf-8", "replace").strip()
    return None


def get_related(paper_id: str, kind: str, limit: int) -> list[dict]:
    pid = normalize_id(paper_id)
    endpoint = "references" if kind == "refs" else "citations"
    key = "citedPaper" if kind == "refs" else "citingPaper"
    params = urllib.parse.urlencode({"limit": limit, "fields": S2_FIELDS})
    url = f"{S2_API}/paper/{urllib.parse.quote(pid, safe=':/')}/{endpoint}?{params}"
    data = fetch_json(url, soft=True)
    if data is None:
        die("Semantic Scholar 인용망 조회 실패 (대개 rate limit). 몇 초 뒤 재시도하거나, "
            "S2_API_KEY 환경변수를 설정하거나, OpenAlex/논문 참고문헌 절을 직접 확인할 것.")
    rows = [_s2_row(item[key]) for item in data.get("data", []) if item.get(key)]
    rows.sort(key=lambda r: (r.get("citations") or 0), reverse=True)
    return rows


def download_pdf(paper_id: str, outdir: str) -> str:
    bare = arxiv_bare_id(paper_id)
    if not bare:
        die("PDF 다운로드는 arXiv ID만 지원한다 (예: 1706.03762). "
            "그 외 논문은 출판사 페이지에서 직접 받아 papers/ 에 두세요.")
    meta = get_meta(bare)
    year = meta.get("year") or "0000"
    first = (meta.get("authors") or ["unknown"])[0]
    name = f"{year}-{surname(first)}-{slugify(meta['title'])}.pdf"
    os.makedirs(outdir, exist_ok=True)
    path = os.path.join(outdir, name)
    if os.path.exists(path):
        print(f"이미 존재: {path}")
        return path
    blob = fetch(f"https://arxiv.org/pdf/{bare}")
    if not blob.startswith(b"%PDF"):
        die("받은 파일이 PDF가 아니다 (arXiv가 차단 페이지를 반환했을 수 있음).")
    with open(path, "wb") as f:
        f.write(blob)
    print(f"저장: {path}  ({len(blob) // 1024} KB)")
    print(f"제목: {meta['title']}")
    return path


# --------------------------------------------------------------------- main

def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    ap = argparse.ArgumentParser(description="논문 검색·메타데이터·PDF CLI")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("search", help="논문 검색")
    p.add_argument("query")
    p.add_argument("--source", choices=["arxiv", "s2", "openalex"], default="s2")
    p.add_argument("--limit", type=int, default=10)
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("meta", help="메타데이터 + BibTeX")
    p.add_argument("id")
    p.add_argument("--json", action="store_true")

    p = sub.add_parser("pdf", help="arXiv PDF 다운로드")
    p.add_argument("id")
    p.add_argument("--out", default="papers")

    for cmd, helptext in (("refs", "이 논문이 인용한 문헌"), ("cites", "이 논문을 인용한 문헌")):
        p = sub.add_parser(cmd, help=helptext)
        p.add_argument("id")
        p.add_argument("--limit", type=int, default=25)
        p.add_argument("--json", action="store_true")

    args = ap.parse_args()

    if args.cmd == "search":
        fn = {"arxiv": search_arxiv, "s2": search_s2, "openalex": search_openalex}[args.source]
        out(fn(args.query, args.limit), args.json)

    elif args.cmd == "meta":
        meta = get_meta(args.id)
        out([meta], args.json)
        if not args.json:
            bib = get_bibtex(args.id, meta)
            print("\n--- BibTeX ---")
            print(bib if bib else "BibTeX를 가져오지 못했다. 직접 확인할 것 [확인 필요]")

    elif args.cmd == "pdf":
        download_pdf(args.id, args.out)

    else:  # refs / cites
        out(get_related(args.id, args.cmd, args.limit), args.json)


if __name__ == "__main__":
    main()
