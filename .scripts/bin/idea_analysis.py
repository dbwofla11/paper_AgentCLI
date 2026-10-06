#!/usr/bin/env python3
"""Create, freeze, and validate independent research-idea review packets."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
ROLES = ("method", "repro", "novelty")
SCHEMA = ROOT / ".scripts/docs/idea-analysis.schema.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def empty_critic(bundle_hash: str | None = None) -> dict[str, Any]:
    return {
        "status": "pending", "evidence_bundle_sha256": bundle_hash, "verdict": "pending",
        "fatal_flaws": [], "evidence_refs": [], "requests": [], "recommendation": "pending",
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("analysis must be a JSON object")
    return data


def relpath(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def resolve_repo_path(value: str) -> Path:
    path = (ROOT / value).resolve()
    path.relative_to(ROOT.resolve())
    return path


def schema_issues(instance: Any, schema: dict[str, Any], root_schema: dict[str, Any] | None = None, path: str = "$") -> list[str]:
    root_schema = root_schema or schema
    if "$ref" in schema:
        target: Any = root_schema
        for part in schema["$ref"].removeprefix("#/").split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        return schema_issues(instance, target, root_schema, path)
    errors: list[str] = []
    expected_type = schema.get("type")
    type_ok = {
        "object": lambda value: isinstance(value, dict),
        "array": lambda value: isinstance(value, list),
        "string": lambda value: isinstance(value, str),
        "integer": lambda value: isinstance(value, int) and not isinstance(value, bool),
        "boolean": lambda value: isinstance(value, bool),
        "null": lambda value: value is None,
    }
    accepted_types = expected_type if isinstance(expected_type, list) else [expected_type]
    if expected_type and not any(type_ok[kind](instance) for kind in accepted_types):
        errors.append(f"{path}: expected type {expected_type}")
        return errors
    if "const" in schema and instance != schema["const"]:
        errors.append(f"{path}: must equal {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: value is not in allowed enum")
    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            errors.append(f"{path}: string is too short")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: string does not match required pattern")
    if isinstance(instance, int) and not isinstance(instance, bool) and instance < schema.get("minimum", instance):
        errors.append(f"{path}: integer is below minimum")
    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            errors.append(f"{path}: array has too few items")
        if "items" in schema:
            for index, item in enumerate(instance):
                errors.extend(schema_issues(item, schema["items"], root_schema, f"{path}[{index}]"))
    if isinstance(instance, dict):
        missing = sorted(set(schema.get("required", [])) - instance.keys())
        if missing:
            errors.append(f"{path}: missing fields {', '.join(missing)}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = sorted(instance.keys() - properties.keys())
            if extras:
                errors.append(f"{path}: unsupported fields {', '.join(extras)}")
        for key, child_schema in properties.items():
            if key in instance:
                errors.extend(schema_issues(instance[key], child_schema, root_schema, f"{path}.{key}"))
    return errors


def freeze(path: Path) -> None:
    data = load(path)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    shape_errors = schema_issues(data, schema)
    if shape_errors:
        raise ValueError("analysis does not match schema:\n- " + "\n- ".join(shape_errors))
    search = data["literature_search"]
    errors: list[str] = []
    if search["status"] != "complete":
        errors.append("literature_search.status must be complete")
    if not search["search_date"]:
        errors.append("literature_search.search_date is required")
    if len(search["queries"]) < 2:
        errors.append("at least two distinct queries are required (support and alternative/contradiction)")
    if len({query["text"].strip().casefold() for query in search["queries"]}) < 2:
        errors.append("literature search queries must be distinct")
    purposes = {query["purpose"] for query in search["queries"]}
    if "support" not in purposes or not purposes.intersection({"alternative", "contradiction"}):
        errors.append("queries must cover support and alternative or contradiction")
    if len({source["name"].casefold() for source in search["sources"]}) < 2:
        errors.append("at least two distinct literature sources are required")
    if not search["included_papers"]:
        errors.append("at least one relevant paper must be included; otherwise mark search insufficient and stop review")
    if not data["claims_and_evidence"]:
        errors.append("claims_and_evidence must contain source-located supporting or opposing evidence")

    source_paths = {data["brief"]["path"]}
    source_paths.update(paper["source_record"] for paper in search["included_papers"] if paper.get("source_record"))
    source_paths.update(item["source"] for item in data["claims_and_evidence"] if not item["source"].startswith(("https://", "http://")))
    items = []
    for value in sorted(source_paths):
        try:
            source = resolve_repo_path(value)
            if not source.is_file():
                errors.append(f"evidence source does not exist: {value}")
                continue
            items.append({"path": relpath(source), "sha256": sha256(source)})
        except (ValueError, OSError):
            errors.append(f"evidence source must be a repository-relative file: {value}")
    if errors:
        raise ValueError("cannot freeze evidence bundle:\n- " + "\n- ".join(errors))

    prior = data["evidence_bundle"].get("sha256")
    next_version = (data["evidence_bundle"].get("version") or 0) + (0 if prior else 1)
    payload = {
        "schema_version": "1.0", "idea_id": data["idea_id"], "version": next_version,
        "brief": data["brief"], "literature_search": search,
        "claims_and_evidence": data["claims_and_evidence"], "items": items,
    }
    bundle_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    if prior and bundle_hash != prior:
        next_version = data["evidence_bundle"]["version"] + 1
        payload["version"] = next_version
        bundle_hash = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
    bundle_name = f"evidence-bundle-v{next_version}-{bundle_hash[:12]}.json"
    bundle_path = path.parent / bundle_name
    write_json(bundle_path, {**payload, "sha256": bundle_hash})
    data["evidence_bundle"] = {"status": "frozen", "version": next_version, "sha256": bundle_hash, "path": relpath(bundle_path), "items": items}
    if bundle_hash != prior:
        data["critics"] = {role: empty_critic(bundle_hash) for role in ROLES}
        data["synthesis"] = {"status": "pending", "recommendation": "pending", "unresolved": []}
        data["user_decision"] = {"decision": "pending", "date": None}
    write_json(path, data)
    print(f"Frozen evidence v{next_version}: sha256:{bundle_hash}")
    print(f"Bundle: {relpath(bundle_path)}")


def validate(path: Path) -> list[str]:
    data = load(path)
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors: list[str] = schema_issues(data, schema)
    if errors:
        return errors
    required = {"schema_version", "idea_id", "brief", "literature_search", "evidence_bundle", "claims_and_evidence", "critics", "synthesis", "user_decision", "graphify_sync"}
    if data.get("schema_version") != "1.0" or set(data) != required:
        errors.append("analysis fields/schema_version do not match idea-analysis schema 1.0")
    if not isinstance(data.get("idea_id"), str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", data.get("idea_id", "")):
        errors.append("idea_id must use lowercase letters, digits, and single hyphens")
    brief = data.get("brief", {})
    if not isinstance(brief, dict) or set(brief) != {"path", "version"} or not all(isinstance(brief.get(key), str) and brief[key] for key in ("path", "version")):
        errors.append("brief must contain a repository-relative path and non-empty version")
    search = data.get("literature_search", {})
    search_fields = {"status", "search_date", "queries", "sources", "included_papers", "excluded_results", "limitations"}
    if not isinstance(search, dict) or set(search) != search_fields or search.get("status") not in {"required", "complete", "insufficient"}:
        errors.append("literature_search does not match idea-analysis schema")
    elif search["status"] == "complete":
        if not isinstance(search.get("search_date"), str) or not search["search_date"]:
            errors.append("completed literature search requires search_date")
        queries = search.get("queries", [])
        if not isinstance(queries, list) or len(queries) < 2 or any(not isinstance(q, dict) or not q.get("text") or q.get("purpose") not in {"support", "alternative", "contradiction", "broadening"} for q in queries):
            errors.append("completed literature search requires at least two valid purpose-tagged queries")
        elif len({q["text"].strip().casefold() for q in queries}) < 2:
            errors.append("completed literature search requires distinct queries")
        if isinstance(queries, list) and ("support" not in {q.get("purpose") for q in queries if isinstance(q, dict)} or not {q.get("purpose") for q in queries if isinstance(q, dict)}.intersection({"alternative", "contradiction"})):
            errors.append("literature queries must cover support and alternative/contradiction")
        sources = search.get("sources", [])
        if not isinstance(sources, list) or len({s.get("name", "").casefold() for s in sources if isinstance(s, dict)}) < 2:
            errors.append("completed literature search requires at least two distinct sources")
        if any(not isinstance(s, dict) or not s.get("name") or not s.get("searched_at") or not isinstance(s.get("result_count"), int) or s["result_count"] < 0 for s in sources if isinstance(sources, list)):
            errors.append("literature source entries require name, searched_at, and result_count")
        papers = search.get("included_papers", [])
        if not isinstance(papers, list) or not papers or any(not isinstance(p, dict) or not all(p.get(key) for key in ("paper_id", "title", "rationale", "source_url")) or (p.get("source_record") is not None and not isinstance(p.get("source_record"), str)) for p in papers):
            errors.append("completed literature search requires relevant papers with IDs, reasons, URLs, and optional local JSON paths")
    if not isinstance(data.get("claims_and_evidence"), list):
        errors.append("claims_and_evidence must be an array")
    elif any(not isinstance(item, dict) or not all(item.get(key) for key in ("claim", "paper_id", "source", "locator", "note")) or item.get("polarity") not in {"supports", "contradicts", "qualifies"} for item in data["claims_and_evidence"]):
        errors.append("each evidence claim requires claim, polarity, paper_id, source, locator, and note")
    bundle = data.get("evidence_bundle", {})
    if not isinstance(bundle, dict) or set(bundle) != {"status", "version", "sha256", "path", "items"} or bundle.get("status") not in {"unfrozen", "frozen"}:
        errors.append("evidence_bundle does not match idea-analysis schema")
    if bundle.get("status") == "frozen":
        expected = bundle.get("sha256")
        bundle_path_value = bundle.get("path")
        if not expected or not bundle_path_value:
            errors.append("frozen bundle requires sha256 and path")
        else:
            try:
                bundle_path = resolve_repo_path(bundle_path_value)
                saved = load(bundle_path)
                saved_hash = saved.pop("sha256", None)
                actual = hashlib.sha256(json.dumps(saved, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()
                if saved_hash != expected or actual != expected:
                    errors.append("frozen bundle hash does not match its content")
                for key in ("idea_id", "version", "brief", "literature_search", "claims_and_evidence", "items"):
                    analysis_value = data.get("idea_id") if key == "idea_id" else bundle.get("version") if key == "version" else data.get(key) if key in {"brief", "literature_search", "claims_and_evidence"} else bundle.get("items")
                    if saved.get(key) != analysis_value:
                        errors.append(f"analysis {key} differs from frozen bundle")
            except (OSError, ValueError, json.JSONDecodeError):
                errors.append("frozen bundle file is missing, invalid, or outside repository")
        for item in bundle.get("items", []):
            try:
                source = resolve_repo_path(item["path"])
                if not source.is_file() or sha256(source) != item["sha256"]:
                    errors.append(f"frozen evidence source changed: {item['path']}")
            except (KeyError, ValueError, OSError):
                errors.append("invalid frozen evidence source path")
        for role in ROLES:
            critic = data.get("critics", {}).get(role, {})
            if critic.get("evidence_bundle_sha256") != expected:
                errors.append(f"{role} critic did not use the frozen evidence hash")
            if not isinstance(critic, dict) or set(critic) != {"status", "evidence_bundle_sha256", "verdict", "fatal_flaws", "evidence_refs", "requests", "recommendation"}:
                errors.append(f"{role} critic does not match the common output contract")

    critics = data.get("critics", {})
    all_complete = all(critics.get(role, {}).get("status") == "complete" for role in ROLES)
    for role in ROLES:
        critic = critics.get(role, {})
        if critic.get("status") == "complete":
            if critic.get("verdict") in {None, "pending"} or critic.get("recommendation") in {None, "pending"}:
                errors.append(f"completed {role} critic lacks a verdict or recommendation")
            if not critic.get("evidence_refs"):
                errors.append(f"completed {role} critic lacks evidence references")
    synthesis = data.get("synthesis", {})
    decision = data.get("user_decision", {}).get("decision")
    if synthesis.get("status") == "complete" and not all_complete:
        errors.append("synthesis cannot complete until all three critics are complete")
    all_clear = all(critics.get(role, {}).get("verdict") == "no_fatal_flaw" and not critics.get(role, {}).get("fatal_flaws") and critics.get(role, {}).get("recommendation") == "retain" for role in ROLES)
    if synthesis.get("recommendation") == "experiment_candidate" and (not all_complete or not all_clear):
        errors.append("experiment_candidate is blocked by incomplete, conditional, fatal, or non-retain reviews")
    if decision == "proceed" and (synthesis.get("recommendation") != "experiment_candidate" or not all_complete or not all_clear):
        errors.append("user proceed decision requires all three critics to be complete, hash-matched, and recommending retain")
    return errors


def record_critic(analysis_path: Path, role: str, output_path: Path) -> None:
    data = load(analysis_path)
    initial_errors = validate(analysis_path)
    if initial_errors:
        raise ValueError("cannot accept a critic result against an invalid/stale analysis:\n- " + "\n- ".join(initial_errors))
    output = load(output_path)
    expected_fields = {"status", "evidence_bundle_sha256", "verdict", "fatal_flaws", "evidence_refs", "requests", "recommendation"}
    if set(output) != expected_fields or output.get("status") != "complete":
        raise ValueError("critic output must match critic-output.schema.json and be complete")
    if output.get("evidence_bundle_sha256") != data.get("evidence_bundle", {}).get("sha256"):
        raise ValueError("critic output used a different evidence bundle hash")
    if output.get("verdict") not in {"no_fatal_flaw", "conditional", "fatal_flaw"}:
        raise ValueError("critic verdict is invalid")
    if output.get("recommendation") not in {"retain", "narrow", "hold", "reject"}:
        raise ValueError("critic recommendation is invalid")
    for field in ("fatal_flaws", "evidence_refs", "requests"):
        if not isinstance(output.get(field), list) or not all(isinstance(item, str) for item in output[field]):
            raise ValueError(f"critic {field} must be a list of strings")
    if not output["evidence_refs"]:
        raise ValueError("critic output requires at least one evidence reference")
    if output["verdict"] == "fatal_flaw" and not output["fatal_flaws"]:
        raise ValueError("fatal_flaw verdict requires at least one unresolved fatal flaw")
    if output["verdict"] == "no_fatal_flaw" and output["fatal_flaws"]:
        raise ValueError("no_fatal_flaw verdict cannot retain fatal_flaws")
    if role not in ROLES:
        raise ValueError(f"unknown critic role: {role}")
    prior = copy.deepcopy(data["critics"][role])
    data["critics"][role] = output
    write_json(analysis_path, data)
    errors = validate(analysis_path)
    if errors:
        data["critics"][role] = prior
        write_json(analysis_path, data)
        raise ValueError("critic result stored, but analysis validation failed:\n- " + "\n- ".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    init_parser = sub.add_parser("init", help="create an idea analysis record")
    init_parser.add_argument("idea_id")
    init_parser.add_argument("--brief", required=True, help="repository-relative brief.md path")
    init_parser.add_argument("--version", default="v1", help="brief version label")
    init_parser.add_argument("--out", help="output analysis.json path")
    freeze_parser = sub.add_parser("freeze", help="hash and freeze the literature/evidence packet")
    freeze_parser.add_argument("analysis_json")
    critic_parser = sub.add_parser("record-critic", help="validate and record one independent critic result")
    critic_parser.add_argument("analysis_json")
    critic_parser.add_argument("role", choices=ROLES)
    critic_parser.add_argument("critic_output_json")
    validate_parser = sub.add_parser("validate", help="validate schema, source hashes, and state consistency")
    validate_parser.add_argument("analysis_json")
    args = parser.parse_args()
    try:
        if args.command == "init":
            if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", args.idea_id):
                raise ValueError("idea_id must use lowercase letters, digits, and single hyphens")
            brief = resolve_repo_path(args.brief)
            output = resolve_repo_path(args.out) if args.out else brief.parent / "analysis.json"
            if output.exists():
                raise ValueError(f"refusing to overwrite existing analysis: {relpath(output)}")
            data = {
                "schema_version": "1.0", "idea_id": args.idea_id,
                "brief": {"path": relpath(brief), "version": args.version},
                "literature_search": {"status": "required", "search_date": None, "queries": [], "sources": [], "included_papers": [], "excluded_results": [], "limitations": []},
                "evidence_bundle": {"status": "unfrozen", "version": None, "sha256": None, "path": None, "items": []},
                "claims_and_evidence": [], "critics": {role: empty_critic() for role in ROLES},
                "synthesis": {"status": "pending", "recommendation": "pending", "unresolved": []},
                "user_decision": {"decision": "pending", "date": None},
                "graphify_sync": {"status": "not_applicable", "updated_at": None, "message": None},
            }
            write_json(output, data)
            print(relpath(output))
            return 0
        path = resolve_repo_path(args.analysis_json)
        if args.command == "freeze":
            freeze(path)
            return 0
        if args.command == "record-critic":
            record_critic(path, args.role, resolve_repo_path(args.critic_output_json))
            print(f"Recorded {args.role} critic result")
            return 0
        errors = validate(path)
        if errors:
            print("FAIL:\n- " + "\n- ".join(errors))
            return 1
        print("PASS: idea analysis schema, frozen evidence, critic versions, and state transitions verified")
        return 0
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
