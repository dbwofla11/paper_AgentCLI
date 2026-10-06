#!/usr/bin/env python3
"""Track Graphify update requests initiated by the assistant's Graphify skill."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import idea_analysis

ROOT = Path(__file__).resolve().parents[2]
STATE = ROOT / "graphify-out/sync-state.json"
PAPER_PREFIX = "01-Papers/library/"
CONCEPT_PREFIX = "02-Concepts/"
IDEA_PREFIX = "04-Projects/thought-experiment-runs/"


def load_state() -> dict[str, Any]:
    if not STATE.exists():
        return {"schema_version": "1.0", "sources": {}}
    data = json.loads(STATE.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("sources"), dict):
        raise ValueError(f"invalid Graphify sync state: {STATE.relative_to(ROOT)}")
    return data


def save_state(data: dict[str, Any]) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_idea_status(source: Path, status: str, message: str, updated_at: str | None = None) -> None:
    if source.name != "analysis.json" or not str(source).startswith(str(ROOT / IDEA_PREFIX)):
        return
    analysis = json.loads(source.read_text(encoding="utf-8"))
    analysis["graphify_sync"] = {"status": status, "updated_at": updated_at, "message": message[-4000:]}
    source.write_text(json.dumps(analysis, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_source(value: str) -> tuple[Path, str] | None:
    source = (ROOT / value).resolve()
    try:
        relative = source.relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return None
    allowed = relative.startswith(PAPER_PREFIX) and source.suffix == ".json"
    allowed = allowed or (relative.startswith(CONCEPT_PREFIX) and source.suffix == ".md")
    allowed = allowed or (relative.startswith(IDEA_PREFIX) and source.name == "analysis.json")
    if not allowed or not source.is_file():
        return None
    if relative.startswith(IDEA_PREFIX):
        analysis = json.loads(source.read_text(encoding="utf-8"))
        if analysis.get("user_decision", {}).get("decision") == "pending":
            raise ValueError("idea results enter Graphify only after all critics and a user decision are recorded")
        errors = idea_analysis.validate(source)
        if errors:
            raise ValueError("idea analysis is inconsistent and cannot enter Graphify:\n- " + "\n- ".join(errors))
    return source, relative


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    begin = sub.add_parser("begin", help="mark a canonical change pending before Graphify skill runs")
    begin.add_argument("--source", required=True, help="canonical paper JSON, concept note, or user-decided idea analysis")
    complete = sub.add_parser("complete", help="mark the pending update successful after Graphify skill succeeds")
    complete.add_argument("--source", required=True, help="same source passed to begin")
    fail = sub.add_parser("fail", help="leave a retryable pending state with failure details")
    fail.add_argument("--source", required=True, help="same source passed to begin")
    fail.add_argument("--message", required=True, help="short failure or retry note")
    sub.add_parser("status", help="show tracked Graphify sync status")
    args = parser.parse_args()
    if args.command == "status":
        state = load_state()
        sources = state.get("sources", {})
        if not sources:
            print("No tracked Graphify syncs.")
        for name, record in sorted(sources.items()):
            print(f"{record.get('status', 'unknown'):7} {name}  {record.get('updated_at') or '-'}")
            if record.get("message"):
                print(f"        {record['message'][:500]}")
            if record.get("status") == "pending":
                print(f"        retry: begin --source {name}, run Graphify skill --update, then complete --source {name}")
        return 0
    try:
        resolved = canonical_source(args.source)
        if resolved is None:
            raise ValueError("source must be a canonical paper JSON, concept note, or idea analysis")
        source, relative = resolved
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    state = load_state()
    record = state["sources"].get(relative, {"status": "pending", "updated_at": None, "message": None})
    if args.command == "begin":
        record = {"status": "pending", "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "updated_at": None, "message": "Run the Graphify skill on the repository; semantic extraction is required for document changes."}
        state["sources"][relative] = record
        save_state(state)
        update_idea_status(source, "pending", record["message"])
        print(record["message"])
        return 0
    if relative not in state["sources"] or record.get("status") != "pending":
        print("FAIL: no pending Graphify update exists for this source", file=sys.stderr)
        return 2
    if args.command == "fail":
        record["message"] = f"Retry pending: {args.message}"
        save_state(state)
        update_idea_status(source, "pending", record["message"])
        print(record["message"], file=sys.stderr)
        return 1
    record["status"] = "success"
    record["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    record["message"] = "Graphify skill completed successfully."
    save_state(state)
    update_idea_status(source, "success", record["message"], record["updated_at"])
    print(f"Graphify sync recorded for {relative}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
