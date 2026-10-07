from __future__ import annotations

import json
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".scripts/bin"))
import idea_analysis  # noqa: E402
import graphify_sync  # noqa: E402


class IdeaAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix=".idea-analysis-test-", dir=ROOT)
        self.folder = Path(self.temp.name)
        (self.folder / "brief.md").write_text("# Test idea\n", encoding="utf-8")
        (self.folder / "paper.json").write_text('{"paper_id":"arxiv:1234.5678"}\n', encoding="utf-8")
        self.analysis_path = self.folder / "analysis.json"
        self.previous_sync_state = graphify_sync.STATE
        graphify_sync.STATE = self.folder / "sync-state.json"
        data = {
            "schema_version": "1.0", "idea_id": "test-idea",
            "brief": {"path": idea_analysis.relpath(self.folder / "brief.md"), "version": "v1"},
            "literature_search": {
                "status": "complete", "search_date": "2026-10-02",
                "queries": [
                    {"text": "test support", "purpose": "support"},
                    {"text": "test alternative", "purpose": "alternative"},
                ],
                "sources": [
                    {"name": "arXiv", "searched_at": "2026-10-02", "result_count": 4},
                    {"name": "Semantic Scholar", "searched_at": "2026-10-02", "result_count": 3},
                ],
                "included_papers": [{"paper_id": "arxiv:1234.5678", "title": "Test", "rationale": "Relevant", "source_url": "https://arxiv.org/abs/1234.5678", "source_record": idea_analysis.relpath(self.folder / "paper.json")}],
                "excluded_results": [], "limitations": [],
            },
            "evidence_bundle": {"status": "unfrozen", "version": None, "sha256": None, "path": None, "items": []},
            "claims_and_evidence": [{"claim": "A test claim", "polarity": "supports", "paper_id": "arxiv:1234.5678", "source": idea_analysis.relpath(self.folder / "paper.json"), "locator": "§1", "note": "Evidence"}],
            "critics": {role: idea_analysis.empty_critic() for role in idea_analysis.ROLES},
            "synthesis": {"status": "pending", "recommendation": "pending", "unresolved": []},
            "user_decision": {"decision": "pending", "date": None},
            "graphify_sync": {"status": "not_applicable", "updated_at": None, "message": None},
        }
        idea_analysis.write_json(self.analysis_path, data)

    def tearDown(self) -> None:
        graphify_sync.STATE = self.previous_sync_state
        self.temp.cleanup()

    def test_freeze_and_validate_records_identical_bundle_hash(self) -> None:
        idea_analysis.freeze(self.analysis_path)
        self.assertEqual([], idea_analysis.validate(self.analysis_path))
        data = idea_analysis.load(self.analysis_path)
        expected = data["evidence_bundle"]["sha256"]
        self.assertTrue(all(data["critics"][role]["evidence_bundle_sha256"] == expected for role in idea_analysis.ROLES))

    def test_source_edit_invalidates_frozen_bundle(self) -> None:
        idea_analysis.freeze(self.analysis_path)
        (self.folder / "brief.md").write_text("# Changed after freeze\n", encoding="utf-8")
        self.assertTrue(any("frozen evidence source changed" in error for error in idea_analysis.validate(self.analysis_path)))

    def test_refreeze_increments_version_and_clears_prior_reviews(self) -> None:
        idea_analysis.freeze(self.analysis_path)
        data = idea_analysis.load(self.analysis_path)
        data["critics"]["method"] = {
            "status": "complete", "evidence_bundle_sha256": data["evidence_bundle"]["sha256"], "verdict": "conditional",
            "fatal_flaws": [], "evidence_refs": ["arxiv:1234.5678 §1"], "requests": [], "recommendation": "narrow",
        }
        idea_analysis.write_json(self.analysis_path, data)
        (self.folder / "brief.md").write_text("# Revised test idea\n", encoding="utf-8")
        idea_analysis.freeze(self.analysis_path)
        updated = idea_analysis.load(self.analysis_path)
        self.assertEqual(2, updated["evidence_bundle"]["version"])
        self.assertTrue(all(updated["critics"][role]["status"] == "pending" for role in idea_analysis.ROLES))

    def test_experiment_recommendation_is_blocked_until_all_reviews_are_clear(self) -> None:
        idea_analysis.freeze(self.analysis_path)
        data = idea_analysis.load(self.analysis_path)
        data["synthesis"] = {"status": "complete", "recommendation": "experiment_candidate", "unresolved": []}
        idea_analysis.write_json(self.analysis_path, data)
        self.assertTrue(any("experiment_candidate is blocked" in error for error in idea_analysis.validate(self.analysis_path)))

    def test_three_matching_clear_reviews_allow_user_decision(self) -> None:
        idea_analysis.freeze(self.analysis_path)
        data = idea_analysis.load(self.analysis_path)
        bundle_hash = data["evidence_bundle"]["sha256"]
        for role in idea_analysis.ROLES:
            data["critics"][role] = {
                "status": "complete", "evidence_bundle_sha256": bundle_hash, "verdict": "no_fatal_flaw",
                "fatal_flaws": [], "evidence_refs": ["arxiv:1234.5678 §1"], "requests": [], "recommendation": "retain",
            }
        data["synthesis"] = {"status": "complete", "recommendation": "experiment_candidate", "unresolved": []}
        data["user_decision"] = {"decision": "proceed", "date": "2026-10-02"}
        idea_analysis.write_json(self.analysis_path, data)
        self.assertEqual([], idea_analysis.validate(self.analysis_path))

    def test_critic_result_with_mismatched_hash_is_rejected(self) -> None:
        idea_analysis.freeze(self.analysis_path)
        output = self.folder / "critic.json"
        output.write_text(json.dumps({
            "status": "complete", "evidence_bundle_sha256": "0" * 64, "verdict": "conditional",
            "fatal_flaws": [], "evidence_refs": ["arxiv:1234.5678 §1"], "requests": ["Need more evidence"], "recommendation": "narrow",
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "different evidence bundle hash"):
            idea_analysis.record_critic(self.analysis_path, "method", output)

    def test_graphify_sync_state_requires_begin_before_complete(self) -> None:
        source = "01-Papers/library/2019-khalilsarai-wifi-multiband-phase-retrieval.json"
        with patch("sys.argv", ["graphify_sync.py", "begin", "--source", source]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, graphify_sync.main())
        state = json.loads(graphify_sync.STATE.read_text(encoding="utf-8"))
        self.assertEqual("pending", state["sources"][source]["status"])
        with patch("sys.argv", ["graphify_sync.py", "complete", "--source", source]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, graphify_sync.main())
        state = json.loads(graphify_sync.STATE.read_text(encoding="utf-8"))
        self.assertEqual("success", state["sources"][source]["status"])


if __name__ == "__main__":
    unittest.main()
