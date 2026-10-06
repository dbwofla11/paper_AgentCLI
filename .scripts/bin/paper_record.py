#!/usr/bin/env python3
"""Create and validate machine-readable paper records using only the stdlib."""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CATEGORIES = {"wifi-csi", "game-ai", "agent-ai", "computer-vision", "other"}
METADATA_STATUSES = {"verified", "partial", "needs_review"}
STATUSES = {"candidate", "keep", "triage", "reading", "reviewed", "rejected"}
PUBLICATION_STATUSES = {"published", "accepted", "preprint", "unknown"}
RELATION_TYPES = {"supports", "contradicts", "extends", "compares", "uses", "cites", "related_to"}
REVIEW_AXES = (
    "problem_and_prior_work",
    "core_idea_and_difference",
    "evaluation_and_evidence",
    "limitations_and_future_work",
    "related_work",
)


def empty_axis() -> dict[str, Any]:
    return {"summary": "", "claims": []}


def record_from_args(args: argparse.Namespace) -> dict[str, Any]:
    slug = args.slug
    return {
        "schema_version": "1.0",
        "paper_id": args.paper_id or f"local:{slug}",
        "slug": slug,
        "title": args.title,
        "metadata_status": "partial",
        "structured_review_status": "pending",
        "authors": args.author,
        "year": args.year,
        "category": args.category,
        "topics": args.topic,
        "publication": {
            "venue": args.venue,
            "status": args.publication_status,
            "verified": False,
            "verification_sources": [],
        },
        "abstract": args.abstract,
        "one_line_summary": "",
        "source": {
            "urls": args.source_url,
            "pdf_path": args.pdf_path,
            "review_path": None,
            "uploaded_filename": args.uploaded_filename,
        },
        "reading_status": args.reading_status,
        "review": {axis: empty_axis() for axis in REVIEW_AXES},
        "relationships": [],
    }


def validate_record(data: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["record must be a JSON object"]
    required = {
        "schema_version", "paper_id", "slug", "title", "metadata_status", "structured_review_status", "authors", "year", "category",
        "topics", "publication", "abstract", "one_line_summary", "source", "reading_status",
        "review", "relationships",
    }
    missing = sorted(required - data.keys())
    if missing:
        errors.append(f"missing fields: {', '.join(missing)}")
    extras = sorted(data.keys() - required)
    if extras:
        errors.append(f"unsupported fields: {', '.join(extras)}")
    if data.get("schema_version") != "1.0":
        errors.append("schema_version must be '1.0'")
    if not isinstance(data.get("paper_id"), str) or not data.get("paper_id"):
        errors.append("paper_id must be a non-empty string")
    slug = data.get("slug")
    if not isinstance(slug, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        errors.append("slug must use lowercase letters, digits, and single hyphens")
    if not isinstance(data.get("title"), str):
        errors.append("title must be a string")
    if data.get("metadata_status") not in METADATA_STATUSES:
        errors.append(f"metadata_status must be one of: {', '.join(sorted(METADATA_STATUSES))}")
    if data.get("structured_review_status") not in {"pending", "complete"}:
        errors.append("structured_review_status must be 'pending' or 'complete'")
    if not isinstance(data.get("authors"), list) or not all(isinstance(x, str) for x in data.get("authors", [])):
        errors.append("authors must be a list of strings")
    year = data.get("year")
    if year is not None and (isinstance(year, bool) or not isinstance(year, int) or not 1800 <= year <= 2200):
        errors.append("year must be null or an integer between 1800 and 2200")
    if data.get("category") not in CATEGORIES:
        errors.append(f"category must be one of: {', '.join(sorted(CATEGORIES))}")
    if data.get("reading_status") not in STATUSES:
        errors.append(f"reading_status must be one of: {', '.join(sorted(STATUSES))}")
    for field in ("topics", "abstract", "one_line_summary"):
        value = data.get(field)
        if field == "topics":
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                errors.append("topics must be a list of strings")
        elif not isinstance(value, str):
            errors.append(f"{field} must be a string")

    publication = data.get("publication")
    if not isinstance(publication, dict):
        errors.append("publication must be an object")
    else:
        extras = sorted(publication.keys() - {"venue", "status", "verified", "verification_sources"})
        if extras:
            errors.append(f"unsupported publication fields: {', '.join(extras)}")
        for field in ("venue", "status", "verified", "verification_sources"):
            if field not in publication:
                errors.append(f"publication.{field} is required")
        if publication.get("status") not in PUBLICATION_STATUSES:
            errors.append(f"publication.status must be one of: {', '.join(sorted(PUBLICATION_STATUSES))}")
        if not isinstance(publication.get("verified"), bool):
            errors.append("publication.verified must be a boolean")
        if not isinstance(publication.get("verification_sources"), list) or not all(
            isinstance(x, str) for x in publication.get("verification_sources", [])
        ):
            errors.append("publication.verification_sources must be a list of strings")
        if publication.get("venue") is not None and not isinstance(publication.get("venue"), str):
            errors.append("publication.venue must be a string or null")

    source = data.get("source")
    if not isinstance(source, dict):
        errors.append("source must be an object")
    else:
        extras = sorted(source.keys() - {"urls", "pdf_path", "review_path", "uploaded_filename"})
        if extras:
            errors.append(f"unsupported source fields: {', '.join(extras)}")
        for field in ("urls", "pdf_path", "review_path"):
            if field not in source:
                errors.append(f"source.{field} is required")
        if not isinstance(source.get("urls"), list) or not all(isinstance(x, str) for x in source.get("urls", [])):
            errors.append("source.urls must be a list of strings")
        for field in ("pdf_path", "review_path", "uploaded_filename"):
            if source.get(field) is not None and not isinstance(source.get(field), str):
                errors.append(f"source.{field} must be a string or null")

    review = data.get("review")
    if not isinstance(review, dict):
        errors.append("review must be an object")
    else:
        extras = sorted(review.keys() - set(REVIEW_AXES))
        if extras:
            errors.append(f"unsupported review axes: {', '.join(extras)}")
        for axis in REVIEW_AXES:
            value = review.get(axis)
            if not isinstance(value, dict):
                errors.append(f"review.{axis} must be an object")
                continue
            extras = sorted(value.keys() - {"summary", "claims"})
            if extras:
                errors.append(f"unsupported fields in review.{axis}: {', '.join(extras)}")
            if not {"summary", "claims"}.issubset(value):
                errors.append(f"review.{axis} requires summary and claims")
            if not isinstance(value.get("summary"), str):
                errors.append(f"review.{axis}.summary must be a string")
            claims = value.get("claims")
            if not isinstance(claims, list):
                errors.append(f"review.{axis}.claims must be a list")
                continue
            for index, claim in enumerate(claims):
                label = f"review.{axis}.claims[{index}]"
                if not isinstance(claim, dict):
                    errors.append(f"{label} must be an object")
                    continue
                extras = sorted(claim.keys() - {"statement", "kind", "evidence"})
                if extras:
                    errors.append(f"unsupported fields in {label}: {', '.join(extras)}")
                if not isinstance(claim.get("statement"), str) or not claim.get("statement"):
                    errors.append(f"{label}.statement must be a non-empty string")
                if claim.get("kind") not in {"paper_fact", "analysis", "inference", "unknown"}:
                    errors.append(f"{label}.kind has an unsupported value")
                errors.extend(validate_evidence(claim.get("evidence"), f"{label}.evidence"))

    relationships = data.get("relationships")
    if not isinstance(relationships, list):
        errors.append("relationships must be a list")
    else:
        for index, relation in enumerate(relationships):
            label = f"relationships[{index}]"
            if not isinstance(relation, dict):
                errors.append(f"{label} must be an object")
                continue
            extras = sorted(relation.keys() - {"type", "target_paper_id", "statement", "evidence"})
            if extras:
                errors.append(f"unsupported fields in {label}: {', '.join(extras)}")
            if relation.get("type") not in RELATION_TYPES:
                errors.append(f"{label}.type has an unsupported value")
            if not isinstance(relation.get("target_paper_id"), str) or not relation.get("target_paper_id"):
                errors.append(f"{label}.target_paper_id must be a non-empty string")
            if not isinstance(relation.get("statement"), str):
                errors.append(f"{label}.statement must be a string")
            errors.extend(validate_evidence(relation.get("evidence"), f"{label}.evidence"))
    return errors


def validate_evidence(value: Any, label: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, list):
        return [f"{label} must be a list"]
    for index, evidence in enumerate(value):
        item_label = f"{label}[{index}]"
        if not isinstance(evidence, dict):
            errors.append(f"{item_label} must be an object")
            continue
        extras = sorted(evidence.keys() - {"locator", "source"})
        if extras:
            errors.append(f"unsupported fields in {item_label}: {', '.join(extras)}")
        if not isinstance(evidence.get("locator"), str) or not evidence.get("locator"):
            errors.append(f"{item_label}.locator must be a non-empty string")
        if not isinstance(evidence.get("source"), str) or not evidence.get("source"):
            errors.append(f"{item_label}.source must be a non-empty string")
    return errors


def cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.out)
    record = record_from_args(args)
    errors = validate_record(record)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 2
    if target.exists():
        print(f"ERROR: refusing to overwrite {target}", file=sys.stderr)
        return 2
    for existing in (sorted(target.parent.glob("*.json")) if target.parent.is_dir() else []):
        try:
            old = json.loads(existing.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        same_id = old.get("paper_id") == record["paper_id"]
        same_title = isinstance(old.get("title"), str) and old["title"].strip().casefold() == args.title.strip().casefold()
        if same_id or same_title:
            print(f"ERROR: duplicate paper record exists at {existing}", file=sys.stderr)
            return 3
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(target)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    result = 0
    for item in args.paths:
        path = Path(item)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: {path}: {exc}", file=sys.stderr)
            result = 2
            continue
        errors = validate_record(data)
        if errors:
            for error in errors:
                print(f"ERROR: {path}: {error}")
            result = max(result, 1)
        else:
            print(f"PASS: {path}")
    return result


def parse_frontmatter(path: Path) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not content.startswith("---\n"):
        return {}
    _, _, remainder = content.partition("---\n")
    raw, separator, body = remainder.partition("\n---")
    if not separator:
        return {}
    values: dict[str, Any] = {"_body": body}
    for line in raw.splitlines():
        match = re.match(r"^([a-zA-Z_][\w-]*):\s*(.*?)\s*$", line)
        if not match:
            continue
        key, value = match.groups()
        if key == "authors":
            try:
                parsed = json.loads(value)
                values[key] = parsed if isinstance(parsed, list) else []
            except json.JSONDecodeError:
                try:
                    parsed = ast.literal_eval(value)
                    values[key] = parsed if isinstance(parsed, list) else []
                except (SyntaxError, ValueError):
                    values[key] = []
        elif key == "tags":
            values[key] = [item.strip().strip("\"'") for item in value.strip("[]").split(",") if item.strip()]
        elif key == "year":
            values[key] = int(value) if value.isdigit() else None
        else:
            try:
                values[key] = ast.literal_eval(value)
            except (SyntaxError, ValueError):
                values[key] = value.strip("\"'") if value else None
    return values


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or f"paper-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:10]}"


def imported_record(pdf: Path, category: str, review: Path | None, metadata: dict[str, Any]) -> dict[str, Any]:
    relative_pdf = pdf.relative_to(ROOT)
    slug = slugify(pdf.stem)
    if review:
        slug = slugify(review.stem)
    arxiv = metadata.get("arxiv")
    doi = metadata.get("doi")
    paper_id = f"arxiv:{arxiv}" if arxiv else f"doi:{doi}" if doi else f"local:{category}:{hashlib.sha256(str(relative_pdf).encode()).hexdigest()[:16]}"
    sources: list[str] = []
    if arxiv:
        sources.append(f"https://arxiv.org/abs/{arxiv}")
    if doi:
        sources.append(f"https://doi.org/{doi}")
    title = metadata.get("title") if isinstance(metadata.get("title"), str) else ""
    year = metadata.get("year")
    venue = metadata.get("venue") if isinstance(metadata.get("venue"), str) else None
    if year is None:
        match = re.match(r"^(18|19|20|21)\d{2}-", pdf.name)
        year = int(pdf.name[:4]) if match else None
    body = metadata.get("_body", "")
    summary_match = re.search(r"^>\s*\*\*TL;DR\*\*\s*[—-]\s*(.+)$", body, re.MULTILINE)
    summary = summary_match.group(1).strip() if summary_match else ""
    has_review = review is not None
    return {
        "schema_version": "1.0",
        "paper_id": paper_id,
        "slug": slug,
        "title": title,
        "metadata_status": "partial" if title else "needs_review",
        "structured_review_status": "pending",
        "authors": metadata.get("authors", []) if isinstance(metadata.get("authors", []), list) else [],
        "year": year,
        "category": category,
        "topics": metadata.get("tags", []) if isinstance(metadata.get("tags", []), list) else [],
        "publication": {
            "venue": venue,
            "status": "preprint" if re.match(r"^arxiv(?:\s+preprint)?\b", (venue or "").strip(), re.IGNORECASE) else "unknown",
            "verified": False,
            "verification_sources": [],
        },
        "abstract": "",
        "one_line_summary": summary,
        "source": {
            "urls": sources,
            "pdf_path": relative_pdf.as_posix(),
            "review_path": review.relative_to(ROOT).as_posix() if review else None,
            "uploaded_filename": None,
        },
        "reading_status": "reviewed" if has_review else "candidate",
        "review": {axis: empty_axis() for axis in REVIEW_AXES},
        "relationships": [],
    }


def cmd_import_pdfs(args: argparse.Namespace) -> int:
    library = ROOT / "01-Papers/library"
    review_by_pdf: dict[str, Path] = {}
    review_metadata: dict[Path, dict[str, Any]] = {}
    for review in sorted((ROOT / "01-Papers/reviews").glob("*/*.md")):
        metadata = parse_frontmatter(review)
        pdf_value = metadata.get("pdf")
        if isinstance(pdf_value, str) and pdf_value:
            review_by_pdf[Path(pdf_value).name] = review
            review_metadata[review] = metadata

    existing_ids: set[str] = set()
    for record_path in library.glob("*.json"):
        if record_path.name == "paper-record.schema.json":
            continue
        try:
            record = json.loads(record_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(record, dict) and isinstance(record.get("paper_id"), str):
            existing_ids.add(record["paper_id"])

    created = 0
    disambiguated = 0
    skipped_duplicate = 0
    for category in sorted(CATEGORIES):
        folder = ROOT / "01-Papers/pdfs" / category
        for pdf in sorted(folder.glob("*.pdf")):
            review = review_by_pdf.get(pdf.name)
            metadata = review_metadata.get(review, {}) if review else {}
            record = imported_record(pdf, category, review, metadata)
            if record["paper_id"] in existing_ids:
                skipped_duplicate += 1
                continue
            target = library / f"{record['slug']}.json"
            if target.exists():
                record["slug"] = f"{category}-{record['slug']}"
                target = library / f"{record['slug']}.json"
                disambiguated += 1
            if target.exists():
                record["slug"] = f"{record['slug']}-{hashlib.sha256(str(pdf).encode()).hexdigest()[:8]}"
                target = library / f"{record['slug']}.json"
                disambiguated += 1
            errors = validate_record(record)
            if errors:
                print(f"ERROR: {pdf.relative_to(ROOT)}: {'; '.join(errors)}", file=sys.stderr)
                return 1
            target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            existing_ids.add(record["paper_id"])
            created += 1
    print(f"Imported {created} paper records; disambiguated {disambiguated} file names and skipped {skipped_duplicate} duplicate paper IDs.")
    return 0


def cmd_upgrade(args: argparse.Namespace) -> int:
    library = ROOT / "01-Papers/library"
    changed = 0
    for path in sorted(library.glob("*.json")):
        if path.name == "paper-record.schema.json":
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: {path}: {exc}", file=sys.stderr)
            return 1
        if not isinstance(record, dict):
            print(f"ERROR: {path}: record must be an object", file=sys.stderr)
            return 1
        updated = dict(record)
        if "metadata_status" not in updated:
            updated["metadata_status"] = "partial" if updated.get("title") else "needs_review"
        if "structured_review_status" not in updated:
            updated["structured_review_status"] = "pending"
        errors = validate_record(updated)
        if errors:
            print(f"ERROR: {path}: {'; '.join(errors)}", file=sys.stderr)
            return 1
        if updated != record:
            path.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            changed += 1
    print(f"Upgraded {changed} paper records; existing values were preserved.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init", help="create an empty paper record without overwriting files")
    init.add_argument("--out", required=True, help="output JSON path, normally 01-Papers/library/{slug}.json")
    init.add_argument("--slug", required=True)
    init.add_argument("--title", required=True)
    init.add_argument("--category", required=True, choices=sorted(CATEGORIES))
    init.add_argument("--paper-id")
    init.add_argument("--author", action="append", default=[])
    init.add_argument("--year", type=int)
    init.add_argument("--topic", action="append", default=[])
    init.add_argument("--venue")
    init.add_argument("--publication-status", choices=sorted(PUBLICATION_STATUSES), default="unknown")
    init.add_argument("--abstract", default="")
    init.add_argument("--source-url", action="append", default=[])
    init.add_argument("--pdf-path")
    init.add_argument("--uploaded-filename")
    init.add_argument("--reading-status", choices=sorted(STATUSES), default="keep")
    init.set_defaults(func=cmd_init)
    validate = subparsers.add_parser("validate", help="validate a paper record")
    validate.add_argument("paths", nargs="+")
    validate.set_defaults(func=cmd_validate)
    import_pdfs = subparsers.add_parser("import-pdfs", help="create missing records for canonical PDFs without overwriting records")
    import_pdfs.set_defaults(func=cmd_import_pdfs)
    upgrade = subparsers.add_parser("upgrade", help="add missing schema fields to existing paper records without replacing values")
    upgrade.set_defaults(func=cmd_upgrade)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
