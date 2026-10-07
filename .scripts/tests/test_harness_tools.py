import importlib.util
import json
import sys
import subprocess
import shutil
from types import SimpleNamespace
from unittest.mock import patch
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
import tempfile
import unittest
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".scripts/bin"))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


catalog = load("paper_catalog_html", ".scripts/bin/paper_catalog_html.py")
ideas = load("thought_experiments_html", ".scripts/bin/thought_experiments_html.py")
installer = load("install_research_harness", ".scripts/bin/install_research_harness.py")
research = load("research_todo", ".scripts/bin/research_todo.py")
review_bridge = load("paper_review_bridge", ".scripts/bin/paper_review_bridge.py")


class ViewTests(unittest.TestCase):
    def test_generated_views_and_static_links_stay_in_views(self):
        class Links(HTMLParser):
            def __init__(self):
                super().__init__(); self.links = []
            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if tag in {"a", "link"} and values.get("href"):
                    self.links.append(values["href"])
        self.assertEqual(catalog.OUTPUT.parent, ROOT / "100-views")
        self.assertEqual(ideas.OUTPUT.parent, ROOT / "100-views")
        for name in ("paper-library.html", "harness-dashboard.html", "thought-experiments.html"):
            self.assertFalse((ROOT / name).exists())
            path = ROOT / "100-views" / name
            parser = Links(); parser.feed(path.read_text())
            for href in parser.links:
                parsed = urlsplit(href)
                if parsed.scheme or not parsed.path:
                    continue
                target = (path.parent / unquote(parsed.path)).resolve()
                self.assertTrue(target.exists(), f"{name}: {href}")

    def test_bridge_serves_view_assets_and_reports_readiness(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), review_bridge.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            for name in ("paper-library.html", "harness-dashboard.html", "thought-experiments.html"):
                with urlopen(base + "/" + name) as response:
                    response.read()
                    self.assertEqual(response.geturl(), base + "/100-views/" + name)
                    self.assertEqual(response.status, 200)
            with urlopen(base + "/100-views/assets/research-ui.css") as response:
                self.assertEqual(response.status, 200)
                self.assertIn("text/css", response.headers["Content-Type"])
                response.read()
            with patch.object(review_bridge.shutil, "which", return_value=None):
                with urlopen(base + "/api/status") as response:
                    self.assertFalse(json.load(response)["ready"])
            with self.assertRaises(HTTPError) as error:
                urlopen(base + "/.mcp.json")
            self.assertEqual(error.exception.code, 404)
        finally:
            server.shutdown(); server.server_close()

    def test_review_post_launches_worker_and_prevents_duplicate_job(self):
        done = threading.Event()
        calls = []
        def worker(job_id, slug, timeout):
            calls.append((job_id, slug, timeout)); done.set()
        with tempfile.TemporaryDirectory() as directory, \
                patch.object(review_bridge, "QUEUE", Path(directory) / "queue.json"), \
                patch.object(review_bridge, "read_record", return_value=(ROOT / "01-Papers/library/example.json", {"slug": "example"})), \
                patch.object(review_bridge, "safe_pdf", return_value=ROOT / "01-Papers/pdfs/other/example.pdf"), \
                patch.object(review_bridge, "needs_review", return_value=True), \
                patch.object(review_bridge, "runtime_status", return_value={"ready": True, "agent": "codex"}), \
                patch.object(review_bridge, "review_worker", side_effect=worker):
            server = ThreadingHTTPServer(("127.0.0.1", 0), review_bridge.Handler)
            server.review_timeout = 123
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                def request():
                    return Request(base + "/api/reviews", data=b'{"slug":"example"}',
                                   headers={"Content-Type": "application/json", "Origin": base}, method="POST")
                with urlopen(request()) as response:
                    self.assertEqual(response.status, 202)
                    job = json.load(response)["job"]
                self.assertTrue(done.wait(2))
                self.assertEqual(calls, [(job["job_id"], "example", 123)])
                with urlopen(base + "/api/reviews/example") as response:
                    self.assertEqual(json.load(response)["jobs"][0]["job_id"], job["job_id"])
                with self.assertRaises(HTTPError) as error:
                    urlopen(request())
                self.assertEqual(error.exception.code, 409)
            finally:
                server.shutdown(); server.server_close()

    def test_graph_conflict_preserves_review_and_defers_graph(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "live"; stage = Path(directory) / "stage"
            record_name = "01-Papers/library/example.json"
            review_name = "01-Papers/reviews/other/example.md"
            graph_name = "graphify-out/graph.json"
            for base, values in ((root, {record_name: "old record", graph_name: "old graph"}),
                                 (stage, {record_name: "new record", review_name: "new review", graph_name: "staged graph"})):
                for name, content in values.items():
                    path = base / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)
            state = stage / "graphify-out/sync-state.json"
            state.write_text(json.dumps({"sources": {record_name: {"status": "success"}}}))
            before = review_bridge.snapshot(root)
            (root / graph_name).write_text("concurrent graph")
            with patch.object(review_bridge, "ROOT", root), patch.object(review_bridge.subprocess, "run", return_value=SimpleNamespace(returncode=0, stderr="")) as run:
                published, status = review_bridge.publish_review_outputs(stage, {record_name, review_name, graph_name, "graphify-out/sync-state.json"}, before, root / record_name, root / review_name)
            self.assertEqual(status, "pending")
            self.assertEqual((root / record_name).read_text(), "new record")
            self.assertEqual((root / review_name).read_text(), "new review")
            self.assertEqual((root / graph_name).read_text(), "concurrent graph")
            self.assertIn("100-views/paper-library.html", published)
            self.assertIn("--source", run.call_args_list[0].args[0])
            self.assertEqual(run.call_args_list[-1].kwargs["cwd"], root)

    def test_canonical_conflict_still_blocks_review_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "live"; stage = Path(directory) / "stage"
            name = "01-Papers/library/example.json"
            for base, content in ((root, "original"), (stage, "reviewed")):
                path = base / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)
            before = review_bridge.snapshot(root)
            (root / name).write_text("user edit")
            with patch.object(review_bridge, "ROOT", root), patch.object(review_bridge.subprocess, "run") as run:
                with self.assertRaisesRegex(RuntimeError, "live source files changed"):
                    review_bridge.publish_review_outputs(stage, {name}, before, root / name, root / "01-Papers/reviews/other/example.md")
            self.assertEqual((root / name).read_text(), "user edit")
            run.assert_not_called()

    def test_review_command_parses_in_installed_codex(self):
        command = review_bridge.review_command(Path("/tmp/review-stage"), Path("/tmp/review-last.md"), "review prompt")
        self.assertIn("--skip-git-repo-check", command)
        self.assertNotIn("--ask-for-approval", command)
        self.assertIn('approval_policy="never"', command)
        if not shutil.which("codex"):
            self.skipTest("Codex CLI is unavailable")
        # Help parses all supplied options without starting an agent.
        result = subprocess.run(command + ["--help"], capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_review_publication_uses_new_catalog_path(self):
        record = ROOT / "01-Papers/library/example.json"
        review = ROOT / "01-Papers/reviews/other/example.md"
        self.assertTrue(review_bridge.allowed_output("100-views/paper-library.html", record, review))
        self.assertFalse(review_bridge.allowed_output("paper-library.html", record, review))
        self.assertFalse(review_bridge.allowed_output("100-views/harness-dashboard.html", record, review))


class CatalogTests(unittest.TestCase):
    def test_local_pdf_precedes_url_and_rejects_outside_paths(self):
        record = {"source": {"pdf_path": "01-Papers/pdfs/agent-ai/2026-su-capnav.pdf", "urls": ["https://example.org/paper"]}}
        self.assertEqual(catalog.original_target(record), record["source"]["pdf_path"])
        record["source"]["pdf_path"] = "../../etc/passwd"
        self.assertEqual(catalog.original_target(record), "https://example.org/paper")

    def test_only_valid_http_urls_are_fallbacks(self):
        for value in ("javascript:alert(1)", "https://", "http:// /invalid"):
            self.assertEqual(catalog.original_target({"source": {"pdf_path": None, "urls": [value]}}), "")

    def test_review_target_uses_existing_path_only_inside_reviews(self):
        record = {"slug": "2025-example-paper", "category": "agent-ai", "source": {}}
        self.assertEqual(review_bridge.review_target(record).relative_to(ROOT).as_posix(), "01-Papers/reviews/agent-ai/2025-example-paper.md")
        self.assertEqual(review_bridge.review_target({**record, "source": {"review_path": "../../etc/passwd"}}).relative_to(ROOT).as_posix(), "01-Papers/reviews/agent-ai/2025-example-paper.md")


class ResearchPromptTests(unittest.TestCase):
    def test_verifier_reads_roles_and_uses_canonical_json(self):
        task = {"task_id": "1"*16, "idea_id": "idea", "idea_path": "05-ideas/idea.md", "brief_sha256": "a"*64,
                "question": "q", "conditions": [], "constraints": [], "counterfactuals": [], "existing_paper_ids": [],
                "search_scope": ["OpenAlex"], "budget": {}, "result_path": "04-Projects/research-todo/results/idea.md"}
        prompt = research.prompt_for(task, "evidence_verifier")
        self.assertIn("results/idea.json", prompt)
        self.assertIn("read the three role outputs", prompt)
        self.assertNotIn("idea.md.evidence_verifier.json", prompt)

    def test_review_stage_excludes_secrets_other_pdfs_and_external_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            source = base / "repo"
            stage = base / "stage"
            outside = base / "private.txt"
            outside.write_text("private", encoding="utf-8")
            (source / "01-Papers/pdfs/agent-ai").mkdir(parents=True)
            (source / ".mcp.json").write_text('{"apiKey":"secret"}', encoding="utf-8")
            (source / ".env.local").write_text("SECRET=x", encoding="utf-8")
            (source / ".claude").mkdir()
            (source / ".codex").mkdir()
            selected = source / "01-Papers/pdfs/agent-ai/selected.pdf"
            selected.write_bytes(b"selected")
            (source / "01-Papers/pdfs/agent-ai/other.pdf").write_bytes(b"other")
            (source / "outside-link").symlink_to(outside)
            prior_root = review_bridge.ROOT
            review_bridge.ROOT = source
            try:
                review_bridge.clone_review_workspace(stage, selected)
            finally:
                review_bridge.ROOT = prior_root
            self.assertFalse((stage / ".mcp.json").exists())
            self.assertFalse((stage / ".env.local").exists())
            self.assertFalse((stage / ".claude").exists())
            self.assertFalse((stage / ".codex").exists())
            self.assertEqual((stage / "01-Papers/pdfs/agent-ai/selected.pdf").read_bytes(), b"selected")
            self.assertFalse((stage / "01-Papers/pdfs/agent-ai/other.pdf").exists())
            self.assertFalse((stage / "outside-link").exists())

    def test_review_bridge_serves_catalog_and_restricts_post_origin(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), review_bridge.Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/paper-library.html") as response:
                self.assertEqual(response.status, 200)
                self.assertIn("논문 라이브러리", response.read().decode())
            request = Request(base + "/api/reviews", data=b"{}", headers={"Content-Type": "application/json", "Origin": "http://evil.example"}, method="POST")
            with self.assertRaises(HTTPError) as error:
                urlopen(request)
            self.assertEqual(error.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()

    def test_idea_catalog_preserves_registry_conflicts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            notes = root / "05-ideas/thought-experiments"
            notes.mkdir(parents=True)
            note = notes / "test-conflict.md"
            note.write_text("# Test idea\n- 상태: 실행 완료\n- 사용자 결정: 중단\n", encoding="utf-8")
            registry = root / "registry.md"
            registry.write_text(
                "| test-conflict | Test | 05-ideas/thought-experiments/test-conflict.md | complete | clear | clear | clear | 실험 가능 | 승인 | 없음 | 2026-10-06 |\n",
                encoding="utf-8",
            )
            with patch.multiple(ideas, ROOT=root, IDEAS=notes, RUNS=root / "runs", REGISTRY=registry, TODO_QUEUE=root / "queue.json"):
                items = ideas.scan()
        self.assertEqual(len(items), 1)
        jev = items[0]
        self.assertTrue(jev["statusConflict"])
        self.assertTrue(jev["decisionConflict"])
        self.assertEqual(jev["validation"], "실험 가능")
        self.assertEqual(jev["noteStatus"], "실행 완료")


class InstallerTests(unittest.TestCase):
    def test_dry_run_apply_idempotence_and_safe_remove(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            (target / "AGENTS.md").write_text("user instructions\n", encoding="utf-8")
            ops, conflicts = installer.plan(target, ["claude", "codex"], "auto", "preserve")
            self.assertIn("AGENTS.md", conflicts)
            self.assertFalse((target / installer.MANIFEST).exists())
            installer.apply(target, ops, ["claude", "codex"])
            second, _ = installer.plan(target, ["claude", "codex"], "auto", "preserve")
            self.assertFalse(any(op["action"] in {"create", "update", "link", "copy-link", "update-copy-link"} for op in second))
            self.assertEqual((target / "AGENTS.md").read_text(encoding="utf-8"), "user instructions\n")
            installer.remove(target)
            self.assertEqual((target / "AGENTS.md").read_text(encoding="utf-8"), "user instructions\n")
            self.assertFalse((target / installer.MANIFEST).exists())

    def test_existing_host_skill_is_preserved_and_copy_mode_diagnoses(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary)
            custom = target / ".claude/skills/paper-review"
            custom.mkdir(parents=True)
            (custom / "SKILL.md").write_text("user-owned skill\n", encoding="utf-8")
            ops, conflicts = installer.plan(target, ["claude"], "copy", "preserve")
            self.assertIn(".claude/skills/paper-review", conflicts)
            installer.apply(target, ops, ["claude"])
            self.assertEqual((custom / "SKILL.md").read_text(encoding="utf-8"), "user-owned skill\n")
            result = __import__("subprocess").run(["python3", ".scripts/bin/research_harness_check.py"], cwd=target, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("WARN: preserved, untracked host skill", result.stdout)
            installer.remove(target)
            self.assertTrue((custom / "SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
