#!/usr/bin/env python3
"""Serve local paper catalog and queue one-paper review jobs to a fixed Codex adapter."""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
import research_agent

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / "01-Papers/library"
QUEUE = ROOT / "04-Projects/review-queue/queue.json"
LOCK = threading.RLock()
MAX_JOBS = 1
ALLOWED_ROOTS = ("01-Papers/", "02-Concepts/", "03-Trends/", "04-Projects/", "05-ideas/", "00-Inbox/", "docs/", "100-views/", "graphify-out/", ".scripts/", ".agents/")
ALLOWED_ROOT_FILES = {"AGENTS.md", "CLAUDE.md", "README.md"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


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
    rel = path.relative_to(ROOT).as_posix()
    return rel in ALLOWED_ROOT_FILES or rel.startswith(ALLOWED_ROOTS)


def allowed_output(name: str, record_path: Path, review_path: Path) -> bool:
    record_name = record_path.relative_to(ROOT).as_posix()
    review_name = review_path.relative_to(ROOT).as_posix()
    return name in {record_name, review_name, "01-Papers/index.md", "100-views/paper-library.html"} or name.startswith("graphify-out/") or name.startswith("00-Inbox/concept-candidates/")


def snapshot(root: Path) -> dict[str, str]:
    result = {}
    for path in root.rglob("*"):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        if relative.startswith("01-Papers/pdfs/"):
            continue
        if path.is_symlink():
            result[relative] = "symlink:" + os.readlink(path)
        else:
            result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def clone_review_workspace(destination: Path, pdf_path: Path) -> None:
    ignored = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", "pdfs", ".mcp.json", ".env", ".env.*", ".claude", ".codex", ".secrets", "credentials.json")
    shutil.copytree(ROOT, destination, ignore=ignored, symlinks=True, dirs_exist_ok=True)
    for link in list(destination.rglob("*")):
        if link.is_symlink():
            try:
                link.resolve(strict=False).relative_to(destination.resolve())
            except ValueError:
                link.unlink()
    relative = pdf_path.relative_to(ROOT)
    target = destination / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pdf_path, target)


def review_command(stage: Path, last_message: Path, prompt: str) -> list[str]:
    return research_agent.command("codex", stage, last_message, prompt)


def runtime_status(requested: str | None = None) -> dict:
    status = research_agent.resolve(ROOT, requested)
    status["pdf_reader_ready"] = bool(shutil.which("pdftotext"))
    status["ready"] = status["ready"] and status["pdf_reader_ready"]
    if not status["pdf_reader_ready"]:
        status["reason"] = "PDF 읽기 도구 pdftotext(Poppler) 설치가 필요합니다."
    return status


def publish_review_outputs(stage: Path, changed: set[str], live_before: dict,
                           record_path: Path, review_path: Path) -> tuple[list[str], str]:
    """Protect canonical edits; retry shared graph updates without losing a review."""
    catalog_name = "100-views/paper-library.html"
    source_name = record_path.relative_to(ROOT).as_posix()
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


def review_worker(job_id: str, slug: str, timeout: int) -> None:
    with LOCK:
        data = load_queue()
        job = next((item for item in data["jobs"] if item["job_id"] == job_id), None)
        if not job:
            return
        job["status"] = "running"
        job["started_at"] = now()
        save_queue(data)
    try:
        record_path, record = read_record(slug)
        pdf_path = safe_pdf(record)
        target = review_target(record)
        agent = runtime_status(job.get("agent"))
        if not agent["ready"]:
            raise RuntimeError(agent["reason"])
        with tempfile.TemporaryDirectory(prefix=f"paper-review-{slug}-") as tmp:
            stage = Path(tmp) / "workspace"
            live_before = snapshot(ROOT)
            clone_review_workspace(stage, pdf_path)
            before = snapshot(stage)
            reader_instruction = ("Use the bounded pdftotext fallback because the headless Codex worker has no Read pages tool; "
                                  if agent["agent"] == "codex" else
                                  "Use the Read tool with explicit PDF page ranges; stop if actual pages cannot be read; ")
            prompt = (
                f"Use the installed paper-review skill to review exactly the paper with slug {slug}. "
                f"Read AGENTS.md, its SKILL.md and review template. The repository PDF is {record.get('source', {}).get('pdf_path')}. "
                + reader_instruction +
                "read actual numbered PDF pages in chunks of at most 10. Do not use only the abstract. "
                "Follow 3 passes, cite all factual claims and numbers, update only this paper's Markdown review, "
                "its JSON record, 01-Papers/index.md, Graphify sync artifacts, and the generated 100-views/paper-library.html. "
                "Do not modify any other paper, skill, script, PDF, or user configuration. If a tool or source required for the paper review is missing, stop and report failure. Graphify failure is retryable: record it as pending and preserve the completed review."
            )
            last_message = Path(tmp) / "last-message.md"
            result = subprocess.run(
                research_agent.command(agent["agent"], stage, last_message, prompt),
                cwd=stage, capture_output=True, text=True, timeout=timeout, check=False,
            )
            after = snapshot(stage)
            changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
            unexpected = sorted(name for name in changed if not allowed_output(name, record_path, target))
            if result.returncode != 0:
                raise RuntimeError(f"{agent['agent']} worker exited {result.returncode}: {(result.stderr or result.stdout)[-3000:]}")
            if unexpected:
                raise RuntimeError("staged worker changed files outside allowed outputs: " + ", ".join(unexpected[:20]))
            staged_record_path = stage / record_path.relative_to(ROOT)
            updated = json.loads(staged_record_path.read_text(encoding="utf-8"))
            if updated.get("slug") != slug or updated.get("paper_id") != record.get("paper_id"):
                raise RuntimeError("staged paper JSON no longer identifies the clicked paper")
            if updated.get("source", {}).get("pdf_path") != record.get("source", {}).get("pdf_path"):
                raise RuntimeError("staged review changed the paper's canonical PDF source")
            if updated.get("structured_review_status") != "complete":
                raise RuntimeError("paper JSON did not reach structured_review_status=complete")
            validation = subprocess.run([sys.executable, str(stage / ".scripts/bin/paper_record.py"), "validate", str(staged_record_path)], capture_output=True, text=True, check=False)
            if validation.returncode:
                raise RuntimeError("staged paper JSON validation failed: " + validation.stdout + validation.stderr)
            axes = updated.get("review", {})
            if len(axes) != 5 or any(not isinstance(axis, dict) or not axis.get("summary") or not axis.get("claims") for axis in axes.values()):
                raise RuntimeError("all five structured review axes need summaries and claims")
            staged_review = stage / target.relative_to(ROOT)
            if not staged_review.is_file():
                raise RuntimeError("review Markdown was not created")
            review_text = staged_review.read_text(encoding="utf-8")
            if "읽은 범위" not in review_text and "읽은 구간" not in review_text:
                raise RuntimeError("review is missing its actually-read range")
            if not staged_review.relative_to(stage).as_posix().startswith("01-Papers/reviews/"):
                raise RuntimeError("review path is outside the canonical reviews directory")
            if updated.get("source", {}).get("review_path") != target.relative_to(ROOT).as_posix():
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
            publish, sync_status = publish_review_outputs(stage, changed, live_before, record_path, target)
        with LOCK:
            data = load_queue()
            job = next(item for item in data["jobs"] if item["job_id"] == job_id)
            job["status"] = "completed"
            job["completed_at"] = now()
            job["changed_files"] = publish
            job["graphify_sync"] = sync_status
            job["message"] = ("리뷰 검증과 저장을 완료했습니다. 그래프 동기화도 완료했습니다." if sync_status == "success"
                              else "리뷰 검증과 저장을 완료했습니다. 그래프 동기화는 재시도 대기 중입니다.")
            save_queue(data)
    except Exception as exc:  # preserve a retryable failure record for the UI
        with LOCK:
            data = load_queue()
            job = next((item for item in data["jobs"] if item["job_id"] == job_id), None)
            if job:
                job["status"] = "failed"
                job["updated_at"] = now()
                job["message"] = str(exc)[-4000:]
                save_queue(data)


class Handler(http.server.SimpleHTTPRequestHandler):
    server_version = "PaperReviewBridge/1.0"

    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def translate_path(self, path: str) -> str:
        raw = urllib.parse.unquote(urllib.parse.urlsplit(path).path).lstrip("/")
        if not raw or raw == ".":
            raw = "100-views/paper-library.html"
        candidate = (ROOT / raw).resolve()
        if not candidate.is_relative_to(ROOT.resolve()) or not allowed_source(candidate):
            return str(ROOT / "__not_found__")
        return str(candidate)

    def do_GET(self):
        route = urllib.parse.urlsplit(self.path).path
        if route in {"/", "/paper-library.html", "/harness-dashboard.html", "/thought-experiments.html"}:
            name = route.lstrip("/") or "paper-library.html"
            self.send_response(302)
            self.send_header("Location", "/100-views/" + name)
            self.end_headers()
        elif route == "/api/status":
            status = runtime_status()
            self.send_json(200, {"ok": True, "workspace_id": hashlib.sha256(str(ROOT.resolve()).encode()).hexdigest()[:16], **status, "runner": f"{status.get('agent')}-cli", "pdf_reader": "pdftotext", "max_parallel": MAX_JOBS, "queue": load_queue()})
        elif self.path.startswith("/api/reviews/"):
            slug = self.path.rsplit("/", 1)[-1]
            data = load_queue()
            self.send_json(200, {"jobs": [job for job in data["jobs"] if job.get("slug") == slug]})
        else:
            super().do_GET()

    def do_POST(self):
        expected_origin = f"http://127.0.0.1:{self.server.server_port}"
        if self.headers.get("Origin") != expected_origin or self.headers.get("Host") != f"127.0.0.1:{self.server.server_port}":
            self.send_json(403, {"error": "same-origin local UI required"})
            return
        if self.path != "/api/reviews":
            self.send_json(404, {"error": "unknown endpoint"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length < 1 or length > 4096:
                raise ValueError("invalid request size")
            payload = json.loads(self.rfile.read(length))
            slug = payload.get("slug", "")
            _, record = read_record(slug)
            target = review_target(record)
            if not needs_review(record, target):
                self.send_json(409, {"error": "review is already complete"})
                return
            safe_pdf(record)
            status = runtime_status()
            if not status["ready"]:
                self.send_json(503, {"error": status["reason"]})
                return
            with LOCK:
                data = load_queue()
                if any(job.get("status") in {"queued", "running"} for job in data["jobs"]):
                    self.send_json(409, {"error": "another paper review is already active"})
                    return
                job_id = hashlib.sha256(f"{slug}:{time.time_ns()}".encode()).hexdigest()[:16]
                job = {"job_id": job_id, "slug": slug, "record": str((LIBRARY / f"{slug}.json").relative_to(ROOT)), "status": "queued", "agent": status["agent"], "created_at": now(), "message": "accepted"}
                data["jobs"].append(job)
                save_queue(data)
            threading.Thread(target=review_worker, args=(job_id, slug, self.server.review_timeout), daemon=True).start()
            self.send_json(202, {"job": job})
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            self.send_json(400, {"error": str(exc)})

    def send_json(self, status: int, payload: dict):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        sys.stderr.write((fmt % args) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("serve", choices=["serve"])
    parser.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost"])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()
    if args.host != "127.0.0.1":
        raise SystemExit("bridge must bind to 127.0.0.1")
    server = http.server.ThreadingHTTPServer((args.host, args.port), Handler)
    server.review_timeout = args.timeout
    print(f"Paper review bridge: http://127.0.0.1:{server.server_port}/100-views/paper-library.html")
    print("Only the local catalog UI can enqueue one paper at a time. Ctrl+C stops the bridge.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
