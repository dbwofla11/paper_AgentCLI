import importlib.util
import hashlib
import json
import os
import platform
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
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".scripts/bin"))
from webui import server as webui_server, reviews as review_bridge


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


catalog = load("paper_catalog_html", ".scripts/bin/paper_catalog_html.py")
ideas = load("thought_experiments_html", ".scripts/bin/thought_experiments_html.py")
installer = load("install_research_harness", ".scripts/bin/install_research_harness.py")
research = load("research_todo", ".scripts/bin/research_todo.py")



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
        server = webui_server.make_server(0)
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
            with tempfile.TemporaryDirectory() as directory, \
                    patch.object(review_bridge, "ROOT", Path(directory).resolve()), \
                    patch.object(review_bridge, "QUEUE", Path(directory).resolve() / "queue.json"), \
                    patch.object(review_bridge.research_agent, "resolve", return_value={"agent": "codex", "ready": False}), \
                    patch.object(review_bridge.research_agent, "probe", return_value={"ready": False}), \
                    patch("subprocess.run", return_value=subprocess.CompletedProcess([], 0, stdout="{}", stderr="")), \
                    patch.object(review_bridge.shutil, "which", return_value=None):
                with urlopen(base + "/api/status") as response:
                    self.assertFalse(json.load(response)["ready"])
            with self.assertRaises(HTTPError) as error:
                with urlopen(base + "/.mcp.json"):
                    pass
            with error.exception:
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
            server = webui_server.make_server(0, review_timeout=123)
            thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
            base = f"http://127.0.0.1:{server.server_port}"
            with urlopen(base + "/api/session") as response:
                token = json.load(response)["csrf_token"]
            try:
                def request():
                    return Request(base + "/api/reviews", data=b'{"slug":"example"}',
                                   headers={"Content-Type": "application/json", "Origin": base,
                                            "X-CSRF-Token": token}, method="POST")
                with urlopen(request()) as response:
                    self.assertEqual(response.status, 202)
                    job = json.load(response)["job"]
                self.assertTrue(done.wait(2))
                self.assertEqual(calls, [(job["job_id"], "example", 123)])
                with urlopen(base + "/api/reviews/example") as response:
                    self.assertEqual(json.load(response)["jobs"][0]["job_id"], job["job_id"])
                with self.assertRaises(HTTPError) as error:
                    with urlopen(request()):
                        pass
                with error.exception:
                    self.assertEqual(error.exception.code, 409)
                    self.assertEqual(json.load(error.exception)["code"], "review_active")
                with patch.object(review_bridge, "needs_review", return_value=False):
                    with self.assertRaises(HTTPError) as completed:
                        with urlopen(request()):
                            pass
                    with completed.exception:
                        self.assertEqual(completed.exception.code, 409)
                        self.assertEqual(json.load(completed.exception)["code"], "review_complete")
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

    def test_gitignored_graph_is_staged_and_published_unless_live_graph_changes(self):
        for concurrent in (False, True):
            with self.subTest(concurrent=concurrent), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                root, stage = base / "repo", base / "stage"
                root.mkdir()
                subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
                (root / ".gitignore").write_text("graphify-out/\n", encoding="utf-8")
                record_name, graph_name = "01-Papers/library/example.json", "graphify-out/graph.json"
                record, graph = root / record_name, root / graph_name
                record.parent.mkdir(parents=True)
                graph.parent.mkdir(parents=True)
                record.write_text('{"slug":"example"}', encoding="utf-8")
                graph.write_text("original graph", encoding="utf-8")
                pdf = root / "01-Papers/pdfs/other/example.pdf"
                pdf.parent.mkdir(parents=True)
                pdf.write_bytes(b"pdf fixture")
                with patch.object(review_bridge, "ROOT", root):
                    before = review_bridge.snapshot(root)
                    review_bridge.clone_review_workspace(stage, pdf)
                    self.assertEqual((stage / graph_name).read_text(), "original graph")
                    (stage / graph_name).write_text("staged graph", encoding="utf-8")
                    state_name = "graphify-out/sync-state.json"
                    (stage / state_name).write_text(json.dumps({"sources": {record_name: {"status": "success"}}}))
                    if concurrent:
                        graph.write_text("concurrent graph", encoding="utf-8")
                    with patch.object(review_bridge.subprocess, "run", return_value=SimpleNamespace(returncode=0, stderr="")):
                        published, status = review_bridge.publish_review_outputs(
                            stage, {graph_name, state_name}, before, record, root / "01-Papers/reviews/other/example.md")
                self.assertEqual(status, "pending" if concurrent else "success")
                self.assertEqual(graph.read_text(), "concurrent graph" if concurrent else "staged graph")
                self.assertEqual(graph_name in published, not concurrent)

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

    def test_review_command_builds_codex_arguments_without_running_cli(self):
        with patch.object(review_bridge.research_agent.shutil, "which", return_value="/fake/codex"):
            command = review_bridge.review_command(Path("/tmp/review-stage"), Path("/tmp/review-last.md"),
                                                   "review prompt", "codex")
        self.assertIn("--skip-git-repo-check", command)
        self.assertNotIn("--ask-for-approval", command)
        self.assertIn('approval_policy="never"', command)
        self.assertEqual(command[command.index("--sandbox") + 1], "workspace-write")
        self.assertEqual(command[-1], "review prompt")

    def test_review_publication_uses_new_catalog_path(self):
        record = ROOT / "01-Papers/library/example.json"
        review = ROOT / "01-Papers/reviews/other/example.md"
        self.assertTrue(review_bridge.allowed_output("100-views/paper-library.html", record, review))
        self.assertFalse(review_bridge.allowed_output("paper-library.html", record, review))
        self.assertFalse(review_bridge.allowed_output("100-views/harness-dashboard.html", record, review))

    def test_review_figure_allowlist_and_publication(self):
        with tempfile.TemporaryDirectory() as directory:
            root = (Path(directory) / "live").resolve()
            stage = Path(directory) / "stage"
            record = root / "01-Papers/library/example.json"
            review = root / "01-Papers/reviews/other/example.md"
            base = "01-Papers/reviews/other/figures/"
            names = {base + "example-method.svg", base + "example-method.html"}
            with patch.object(review_bridge, "ROOT", root):
                for name in names:
                    self.assertTrue(review_bridge.allowed_output(name, record, review))
                    path = stage / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("figure")
                for name in (base + "evil.sh", base + "other-method.svg",
                             base + "example-Method.svg", base + "nested/example-method.svg",
                             "01-Papers/reviews/agent-ai/figures/example-method.svg"):
                    self.assertFalse(review_bridge.allowed_output(name, record, review), name)
            root.mkdir()
            before = review_bridge.snapshot(root)
            with patch.object(review_bridge, "ROOT", root), \
                 patch.object(review_bridge.subprocess, "run", return_value=SimpleNamespace(returncode=0, stderr="")):
                published, _ = review_bridge.publish_review_outputs(stage, names, before, record, review)
            for name in names:
                self.assertIn(name, published)
                self.assertEqual((root / name).read_text(), "figure")

    def test_review_worker_refreshes_live_wiki_and_rejects_staged_wiki_edits(self):
        for forbidden in (None, "wiki-index.md", "wiki-log.md", "wiki-failure", "comment", "missing-scope"):
            with self.subTest(forbidden=forbidden), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
                record_name = "01-Papers/library/example.json"
                review_name = "01-Papers/reviews/other/example.md"
                pdf_name = "01-Papers/pdfs/other/example.pdf"
                record = {"slug": "example", "paper_id": "paper-1", "title": "Example paper",
                          "source": {"pdf_path": pdf_name, "review_path": review_name}}
                for name, content in ((record_name, json.dumps(record)), (pdf_name, "fixture PDF"),
                                      ("01-Papers/index.md", "# Papers\n"),
                                      ("wiki-index.md", "live old index\n"),
                                      ("wiki-log.md", "# 작업 기록\n\nprior entry\n")):
                    path = root / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8")
                script = root / ".scripts/bin/wiki.py"
                script.parent.mkdir(parents=True)
                shutil.copy2(ROOT / ".scripts/bin/wiki.py", script)
                shutil.copy2(ROOT / ".scripts/bin/harness_common.py", script.parent / "harness_common.py")
                definitions = root / ".omp/agents"
                definitions.mkdir(parents=True)
                shutil.copy2(ROOT / ".omp/agents/paper-analyst.md", definitions / "paper-analyst.md")
                queue = {"jobs": [{"job_id": "job-1", "agent": "codex"}]}
                real_run = subprocess.run

                def run(command, **kwargs):
                    if command[:3] == ["omp", "config", "get"]:
                        value = False if command[3] == "retry.modelFallback" else {}
                        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(value), stderr="")
                    if command[0] == "fixture-review-agent":
                        stage = Path(kwargs["cwd"])
                        updated = {**record, "structured_review_status": "complete",
                                   "review": {f"axis-{i}": {"summary": "summary", "claims": ["claim"]}
                                              for i in range(5)}}
                        (stage / record_name).write_text(json.dumps(updated), encoding="utf-8")
                        review = stage / review_name
                        review.parent.mkdir(parents=True, exist_ok=True)
                        text = "# Published review\n"
                        if forbidden != "missing-scope":
                            text += "읽은 범위: 1\n"
                        if forbidden == "comment":
                            text += "<!-- instruction -->\n"
                        review.write_text(text, encoding="utf-8")
                        (stage / "01-Papers/index.md").write_text("# Papers\nexample\n", encoding="utf-8")
                        state = stage / "graphify-out/sync-state.json"
                        state.parent.mkdir(parents=True, exist_ok=True)
                        state.write_text(json.dumps({"sources": {record_name: {"status": "success"}}}), encoding="utf-8")
                        if forbidden in ("wiki-index.md", "wiki-log.md"):
                            (stage / forbidden).write_text("agent injected content\n", encoding="utf-8")
                        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                    if len(command) > 1 and command[1].endswith("paper_record.py"):
                        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                    if len(command) > 1 and command[1].endswith("paper_catalog_html.py"):
                        catalog = Path(kwargs["cwd"]) / "100-views/paper-library.html"
                        catalog.parent.mkdir(parents=True, exist_ok=True)
                        catalog.write_text("catalog", encoding="utf-8")
                        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                    if forbidden == "wiki-failure" and len(command) > 2 and command[1].endswith("wiki.py") and command[2] == "index":
                        return subprocess.CompletedProcess(command, 1, stdout="", stderr="fixture wiki failure")
                    return real_run(command, **kwargs)

                with patch.object(review_bridge, "ROOT", root), \
                     patch.object(review_bridge, "load_queue", return_value=queue), \
                     patch.object(review_bridge, "save_queue"), \
                     patch.object(review_bridge, "read_record", return_value=(root / record_name, record)), \
                     patch.object(review_bridge, "runtime_status", return_value={"ready": True, "agent": "codex"}), \
                     patch.object(review_bridge.research_agent, "resolve", return_value={"ready": True, "agent": "codex"}), \
                     patch.object(review_bridge.research_agent, "probe", return_value={"ready": True, "agent": "codex"}), \
                     patch.object(review_bridge, "review_command", return_value=["fixture-review-agent"]), \
                     patch.object(review_bridge.subprocess, "run", side_effect=run):
                    self.assertFalse(review_bridge.allowed_output("wiki-index.md", root / record_name, root / review_name))
                    self.assertFalse(review_bridge.allowed_output("wiki-log.md", root / record_name, root / review_name))
                    review_bridge.review_worker("job-1", "example", 30)
                job = queue["jobs"][0]
                if forbidden in ("comment", "missing-scope"):
                    self.assertEqual(job["status"], "failed", job.get("message"))
                    self.assertTrue(job.get("message"))
                    if forbidden == "comment":
                        self.assertIn("review still contains template instruction comments", job["message"])
                    self.assertFalse((root / review_name).exists())
                elif forbidden and forbidden != "wiki-failure":
                    self.assertEqual(job["status"], "failed", job.get("message"))
                    self.assertIn("outside allowed outputs", job["message"])
                    self.assertIn(forbidden, job["message"])
                    self.assertEqual((root / "wiki-index.md").read_text(encoding="utf-8"), "live old index\n")
                    self.assertEqual((root / "wiki-log.md").read_text(encoding="utf-8"), "# 작업 기록\n\nprior entry\n")
                    self.assertFalse((root / review_name).exists())
                elif forbidden == "wiki-failure":
                    self.assertEqual(job["status"], "completed", job.get("message"))
                    self.assertTrue((root / review_name).is_file())
                    self.assertIn("fixture wiki failure", job["message"])
                else:
                    self.assertEqual(job["status"], "completed", job.get("message"))
                    self.assertIn(review_name, (root / "wiki-index.md").read_text(encoding="utf-8"))
                    log = (root / "wiki-log.md").read_text(encoding="utf-8")
                    self.assertTrue(log.startswith("# 작업 기록\n\nprior entry\n"))
                    self.assertEqual(log.count(" ingest | Example paper"), 1)
                    self.assertIn("- " + review_name + "\n", log)
                    self.assertIn("- " + record_name + "\n", log)
                    self.assertIn("wiki-index.md", job["changed_files"])
                    self.assertIn("wiki-log.md", job["changed_files"])


class CatalogTests(unittest.TestCase):
    def test_local_pdf_precedes_url_and_rejects_outside_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            pdf = root / "01-Papers/pdfs/agent-ai/example.pdf"
            pdf.parent.mkdir(parents=True)
            pdf.write_bytes(b"%PDF-1.4\n")
            record = {"source": {"pdf_path": pdf.relative_to(root).as_posix(), "urls": ["https://example.org/paper"]}}
            with patch.object(catalog, "ROOT", root):
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
        task = {"task_id": "1"*16, "idea_id": "idea", "idea_path": "05-Ideas/idea.md", "brief_sha256": "a"*64,
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

    def test_review_stage_respects_git_exclusions_but_keeps_local_overrides(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary).resolve()
            root, stage = base / "repo", base / "stage"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
            (root / ".git/info/exclude").write_text("private-excluded.txt\n", encoding="utf-8")
            (root / ".gitignore").write_text("ignored.txt\n.omp/config.yml\n*.local.md\n", encoding="utf-8")
            files = {
                "private-excluded.txt": "excluded", "ignored.txt": "ignored",
                ".omp/config.yml": "fixture roles", "foo.local.md": "fixture override",
                "04-Projects/thought-experiment-runs/PROGRESS_BACKEND.local.md": "fixture backend",
                ".research-harness-agent.json": '{"agent":"omp"}',
                ".mcp.json": "{}", ".env": "fixture", "tracked.txt": "shared",
                "01-Papers/pdfs/other/selected.pdf": "selected",
                "01-Papers/pdfs/other/other.pdf": "other",
            }
            for name, content in files.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            with patch.object(review_bridge, "ROOT", root):
                review_bridge.clone_review_workspace(stage, root / "01-Papers/pdfs/other/selected.pdf")
            for name in ("private-excluded.txt", "ignored.txt", ".git", ".mcp.json", ".env",
                         ".research-harness-agent.json", "01-Papers/pdfs/other/other.pdf"):
                self.assertFalse((stage / name).exists(), name)
            for name in (".omp/config.yml", "foo.local.md", "tracked.txt", "01-Papers/pdfs/other/selected.pdf",
                         "04-Projects/thought-experiment-runs/PROGRESS_BACKEND.local.md"):
                self.assertEqual((stage / name).read_text(encoding="utf-8"), files[name])

    def test_git_inventory_failure_does_not_copy_excluded_private_file(self):
        for failure in ("nonzero", "oserror"):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                root, stage = base / "repo", base / "stage"
                root.mkdir()
                subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
                (root / ".git/info/exclude").write_text("private.txt\n", encoding="utf-8")
                (root / "private.txt").write_text("private fixture", encoding="utf-8")
                pdf = root / "01-Papers/pdfs/other/example.pdf"
                pdf.parent.mkdir(parents=True)
                pdf.write_bytes(b"pdf fixture")
                result = SimpleNamespace(returncode=1, stdout=b"", stderr=b"git failure")
                fake = {"return_value": result} if failure == "nonzero" else {"side_effect": OSError("git unavailable")}
                with patch.object(review_bridge, "ROOT", root), patch.object(review_bridge.subprocess, "run", **fake):
                    with self.assertRaises((OSError, RuntimeError)):
                        review_bridge.clone_review_workspace(stage, pdf)
                self.assertFalse((stage / "private.txt").exists())

    def test_non_git_staging_falls_back_to_walk(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root, stage = base / "repo", base / "stage"
            root.mkdir()
            (root / "ordinary file.txt").write_text("fixture", encoding="utf-8")
            pdf = root / "01-Papers/pdfs/other/example.pdf"
            pdf.parent.mkdir(parents=True)
            pdf.write_bytes(b"pdf fixture")
            with patch.object(review_bridge, "ROOT", root):
                review_bridge.clone_review_workspace(stage, pdf)
            self.assertEqual((stage / "ordinary file.txt").read_text(), "fixture")
            self.assertEqual((stage / "01-Papers/pdfs/other/example.pdf").read_bytes(), b"pdf fixture")

    def test_git_staging_handles_spaces_and_deleted_indexed_files(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            root, stage = base / "repo", base / "stage"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
            (root / "path with spaces.txt").write_text("fixture", encoding="utf-8")
            deleted = root / "deleted but indexed.txt"
            deleted.write_text("deleted", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "--", deleted.name], check=True, capture_output=True)
            deleted.unlink()
            pdf = root / "01-Papers/pdfs/other/example.pdf"
            pdf.parent.mkdir(parents=True)
            pdf.write_bytes(b"pdf fixture")
            with patch.object(review_bridge, "ROOT", root):
                review_bridge.clone_review_workspace(stage, pdf)
            self.assertEqual((stage / "path with spaces.txt").read_text(), "fixture")
            self.assertFalse((stage / deleted.name).exists())
    def test_nested_git_root_honors_parent_excludes_and_fails_closed(self):
        for unavailable in (False, True):
            with self.subTest(unavailable=unavailable), tempfile.TemporaryDirectory() as directory:
                parent = Path(directory).resolve()
                subprocess.run(["git", "init", "-q", str(parent)], check=True, capture_output=True)
                (parent / ".gitignore").write_text("research/private.txt\n", encoding="utf-8")
                root, stage = parent / "research", parent / "stage"
                root.mkdir()
                (root / "AGENTS.md").write_text("shared fixture", encoding="utf-8")
                (root / "private.txt").write_text("private fixture", encoding="utf-8")
                pdf = root / "01-Papers/pdfs/other/example.pdf"
                pdf.parent.mkdir(parents=True)
                pdf.write_bytes(b"pdf fixture")
                with patch.object(review_bridge, "ROOT", root):
                    if unavailable:
                        with patch.object(review_bridge.subprocess, "run", side_effect=OSError("git unavailable")):
                            with self.assertRaises(RuntimeError):
                                review_bridge.clone_review_workspace(stage, pdf)
                    else:
                        review_bridge.clone_review_workspace(stage, pdf)
                        self.assertEqual((stage / "AGENTS.md").read_text(), "shared fixture")
                self.assertFalse((stage / "private.txt").exists())

    def test_review_worker_persists_git_staging_failure_without_starting_agent(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True)
            queue = root / "queue.json"
            queue.write_text(json.dumps({"jobs": [{"job_id": "job1", "slug": "example",
                                                   "status": "queued", "agent": "omp"}]}))
            pdf = root / "01-Papers/pdfs/other/example.pdf"
            pdf.parent.mkdir(parents=True)
            pdf.write_bytes(b"pdf fixture")
            record = {"slug": "example", "category": "other",
                      "source": {"pdf_path": "01-Papers/pdfs/other/example.pdf"}}
            with patch.object(review_bridge, "ROOT", root), patch.object(review_bridge, "QUEUE", queue), \
                    patch.object(review_bridge, "read_record", return_value=(root / "01-Papers/library/example.json", record)), \
                    patch.object(review_bridge, "runtime_status", return_value={"ready": True, "agent": "omp"}), \
                    patch.object(review_bridge.roles, "review_roles", return_value={
                        "generation": {"configured": False}, "verification": {"configured": False}}), \
                    patch.object(review_bridge.research_agent, "command") as command, \
                    patch.object(review_bridge.subprocess, "run", side_effect=OSError("git unavailable")) as run:
                review_bridge.review_worker("job1", "example", 30)
            job = json.loads(queue.read_text())["jobs"][0]
            self.assertEqual(job["status"], "failed")
            self.assertIn("Git 제외 규칙을 확인하지 못해 리뷰 작업공간을 만들지 않았습니다", job["message"])
            command.assert_not_called()
            self.assertTrue(run.call_args_list)
            self.assertTrue(all(call.args[0][0] == "git" for call in run.call_args_list))


    def test_bare_and_git_internal_roots_fail_closed_before_starting_agent(self):
        for kind in ("bare", "git-internal"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                base = Path(directory).resolve()
                repo = base / "repo"
                if kind == "bare":
                    subprocess.run(["git", "init", "--bare", "-q", str(repo)], check=True, capture_output=True)
                    root = repo
                else:
                    subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
                    root = repo / ".git" / "fixture-root"
                    root.mkdir()
                stage = base / "stage"
                (root / "private.txt").write_text("private fixture", encoding="utf-8")
                pdf = root / "01-Papers/pdfs/other/example.pdf"
                pdf.parent.mkdir(parents=True)
                pdf.write_bytes(b"pdf fixture")
                queue = root / "queue.json"
                queue.write_text(json.dumps({"jobs": [{"job_id": "job1", "slug": "example",
                                                       "status": "queued", "agent": "omp"}]}))
                record = {"slug": "example", "category": "other",
                          "source": {"pdf_path": "01-Papers/pdfs/other/example.pdf"}}
                real_run = subprocess.run
                with patch.object(review_bridge, "ROOT", root), patch.object(review_bridge, "QUEUE", queue), \
                        patch.object(review_bridge, "read_record", return_value=(root / "01-Papers/library/example.json", record)), \
                        patch.object(review_bridge, "runtime_status", return_value={"ready": True, "agent": "omp"}), \
                        patch.object(review_bridge.roles, "review_roles", return_value={
                            "generation": {"configured": False}, "verification": {"configured": False}}), \
                        patch.object(review_bridge.research_agent, "command") as command, \
                        patch.object(review_bridge.subprocess, "run", wraps=real_run) as run:
                    with self.assertRaisesRegex(RuntimeError, "Git 제외 규칙"):
                        review_bridge.clone_review_workspace(stage, pdf)
                    self.assertFalse(stage.exists())
                    review_bridge.review_worker("job1", "example", 30)
                job = json.loads(queue.read_text())["jobs"][0]
                self.assertEqual(job["status"], "failed")
                self.assertIn("Git 제외 규칙을 확인하지 못해 리뷰 작업공간을 만들지 않았습니다", job["message"])
                command.assert_not_called()
                self.assertTrue(run.call_args_list)
                self.assertTrue(all(call.args[0][0] == "git" for call in run.call_args_list))

    def test_review_bridge_serves_catalog_and_restricts_post_origin(self):
        server = webui_server.make_server(0)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/paper-library.html") as response:
                self.assertEqual(response.status, 200)
                self.assertIn("논문 라이브러리", response.read().decode())
            request = Request(base + "/api/reviews", data=b"{}", headers={"Content-Type": "application/json", "Origin": "http://evil.example"}, method="POST")
            with self.assertRaises(HTTPError) as error:
                with urlopen(request):
                    pass
            with error.exception:
                self.assertEqual(error.exception.code, 403)
        finally:
            server.shutdown()
            server.server_close()

    def test_idea_catalog_preserves_registry_conflicts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            notes = root / "05-Ideas/thought-experiments"
            notes.mkdir(parents=True)
            note = notes / "test-conflict.md"
            note.write_text("# Test idea\n- 상태: 실행 완료\n- 사용자 결정: 중단\n", encoding="utf-8")
            registry = root / "registry.md"
            registry.write_text(
                "| test-conflict | Test | 05-Ideas/thought-experiments/test-conflict.md | complete | clear | clear | clear | 실험 가능 | 승인 | 없음 | 2026-10-06 |\n",
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

    def test_papers_unmanaged_wiki_index_is_preserved_and_never_claimed(self):
        header = "자동 생성 파일. 직접 수정하지 말고 python3 .scripts/bin/wiki.py index로 갱신한다."
        for contents in ("# My index\nUser content.\n", f"# My index\n{header}\nUser content.\n"):
            with self.subTest(contents=contents), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary).resolve()
                index = target / "wiki-index.md"
                original = contents.encode("utf-8")
                index.write_bytes(original)
                command = [sys.executable, str(ROOT / ".scripts/bin/install_research_harness.py"),
                           str(target), "--profile", "papers", "--host", "claude", "--link-mode", "copy"]
                result = subprocess.run(command, capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertRegex(result.stdout, r"(?m)^CONFLICT\s+wiki-index\.md\b")
                operations, conflicts = installer.plan(target, ["claude"], "copy", "preserve", "papers")
                self.assertIn("wiki-index.md", conflicts)
                installer.apply(target, operations, ["claude"])
                self.assertEqual(index.read_bytes(), original)
                manifest = json.loads((target / installer.MANIFEST).read_text(encoding="utf-8"))
                self.assertNotIn("wiki-index.md", manifest["files"])
                result = subprocess.run(command + ["--remove"], capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(index.read_bytes(), original)

    def test_papers_wiki_index_removal_respects_user_edits(self):
        for edited in (False, True):
            with self.subTest(edited=edited), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary).resolve()
                operations, conflicts = installer.plan(target, ["claude"], "copy", "preserve", "papers")
                self.assertNotIn("wiki-index.md", conflicts)
                installer.apply(target, operations, ["claude"])
                ignore = (target / ".gitignore").read_text(encoding="utf-8")
                managed = ignore.split(installer.IGNORE_START, 1)[1].split(installer.IGNORE_END, 1)[0]
                self.assertIn("04-Projects/reader-threads/", managed.splitlines())
                self.assertIn("00-Inbox/discovery/", managed.splitlines())
                verifier = load("reader_harness_verifier", ".scripts/bin/verify_harness.py")
                self.assertIn(ROOT / ".omp/agents/paper-reader.md", verifier.REQUIRED)
                index = target / "wiki-index.md"
                self.assertTrue(index.is_file())
                manifest = json.loads((target / installer.MANIFEST).read_text(encoding="utf-8"))
                self.assertIn("wiki-index.md", manifest["files"])
                if edited:
                    changed = index.read_bytes() + b"\nUser edit.\n"
                    index.write_bytes(changed)
                    preview = subprocess.run(
                        [sys.executable, str(ROOT / ".scripts/bin/install_research_harness.py"),
                         str(target), "--profile", "papers", "--host", "claude", "--link-mode", "copy"],
                        capture_output=True, text=True, check=False)
                    self.assertEqual(preview.returncode, 0, preview.stdout + preview.stderr)
                    self.assertRegex(preview.stdout, r"(?m)^CONFLICT\s+wiki-index\.md\b")
                    operations, conflicts = installer.plan(target, ["claude"], "copy", "preserve", "papers")
                    self.assertIn("wiki-index.md", conflicts)
                    installer.apply(target, operations, ["claude"])
                    self.assertEqual(index.read_bytes(), changed)
                result = subprocess.run(
                    [sys.executable, str(ROOT / ".scripts/bin/install_research_harness.py"),
                     str(target), "--remove"], capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                if edited:
                    self.assertEqual(index.read_bytes(), changed)
                else:
                    self.assertFalse(index.exists())

    def legacy_guidance_fixture(self, target):
        legacy_guidance = (
            "<!-- managed-research-harness:start -->\n"
            "## Shared research harness\n\n"
            "- Shared agent skills are installed in `.agents/skills/`.\n"
            "- Read the selected skill's `SKILL.md` before following a workflow.\n"
            "- Keep user files and credentials unchanged; inspect repository instructions first.\n"
            "- Run only validators documented by this repository.\n"
            "<!-- managed-research-harness:end -->\n"
        )
        originals = {"AGENTS.md": b"# Original agent rules\n\nKeep user content.\n",
                     "CLAUDE.md": b"# Original Claude rules\nKeep this as well.\n"}
        files = {}
        for name, original in originals.items():
            merged = original.rstrip() + b"\n\n" + legacy_guidance.encode("utf-8")
            (target / name).write_bytes(merged)
            (target / (name + ".pre-research-harness.bak")).write_bytes(original)
            files[name] = {"kind": "file", "sha256": hashlib.sha256(merged).hexdigest()}
        manifest = {"schema_version": "1.0", "installer_version": "1.1.0", "hosts": ["claude"], "files": files}
        (target / installer.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
        for name, original in originals.items():
            entry = json.loads((target / installer.MANIFEST).read_text())["files"][name]
            self.assertEqual(entry["kind"], "file")
            self.assertEqual(entry["sha256"], hashlib.sha256((target / name).read_bytes()).hexdigest())
            self.assertEqual((target / (name + ".pre-research-harness.bak")).read_bytes(), original)
        return originals

    def test_legacy_master_append_remove_preserves_user_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary).resolve()
            originals = self.legacy_guidance_fixture(target)
            installer.remove(target)
            for name, original in originals.items():
                self.assertEqual((target / name).read_bytes(), original)

    def test_legacy_master_append_update_preserves_user_prefix_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary).resolve()
            originals = self.legacy_guidance_fixture(target)
            for _ in range(2):
                ops, conflicts = installer.plan(target, ["claude"], "copy", "append", "skills")
                self.assertFalse(any(name in conflicts for name in originals), conflicts)
                installer.apply(target, ops, ["claude"])
            for name, original in originals.items():
                updated = (target / name).read_bytes()
                self.assertTrue(updated.startswith(original.rstrip()))
                self.assertEqual(updated.count(installer.MARKER.encode()), 1)
            installer.remove(target)
            for name, original in originals.items():
                self.assertEqual((target / name).read_bytes(), original)

    def test_legacy_edited_guidance_conflicts_and_remove_preserves(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary).resolve()
            originals = self.legacy_guidance_fixture(target)
            changed = {}
            for name in originals:
                path = target / name
                changed[name] = path.read_bytes().replace(b"## Shared research harness", b"## User-edited guidance")
                path.write_bytes(changed[name])
            ops, conflicts = installer.plan(target, ["claude"], "copy", "append", "skills")
            self.assertTrue(set(originals).issubset(conflicts), conflicts)
            installer.apply(target, ops, ["claude"])
            for name in originals:
                self.assertEqual((target / name).read_bytes(), changed[name])
            installer.remove(target)
            for name in originals:
                self.assertEqual((target / name).read_bytes(), changed[name])

    def test_papers_append_remove_preserves_existing_guidance_and_edits(self):
        for edited in (False, True):
            with self.subTest(edited=edited), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary).resolve()
                originals = {"AGENTS.md": "# User agent rules\nKeep this text.\n",
                             "CLAUDE.md": "# User Claude rules\nKeep this text too.\n"}
                for name, text in originals.items():
                    (target / name).write_text(text, encoding="utf-8")
                ops, _ = installer.plan(target, ["claude"], "copy", "append", "papers")
                installer.apply(target, ops, ["claude"])
                for name in originals:
                    text = (target / name).read_text(encoding="utf-8")
                    self.assertIn(originals[name].strip(), text)
                    self.assertIn(installer.MARKER, text)
                if edited:
                    path = target / "CLAUDE.md"
                    path.write_text(path.read_text(encoding="utf-8").replace(
                        installer.MARKER, installer.MARKER + "\nUser-edited managed guidance"), encoding="utf-8")
                    changed = path.read_text(encoding="utf-8")
                installer.remove(target)
                self.assertEqual((target / "AGENTS.md").read_text(encoding="utf-8"), originals["AGENTS.md"])
                if edited:
                    self.assertEqual((target / "CLAUDE.md").read_text(encoding="utf-8"), changed)
                else:
                    self.assertEqual((target / "CLAUDE.md").read_text(encoding="utf-8"), originals["CLAUDE.md"])

    @unittest.skipIf(os.name == "nt", "Executable fixtures use Unix shebangs")
    def test_papers_install_verifies_for_each_single_host(self):
        for host in ("omp", "codex", "claude"):
            with self.subTest(host=host), tempfile.TemporaryDirectory() as temporary:
                base = Path(temporary).resolve()
                target, bins, home = base / "repo", base / "bin", base / "home"
                target.mkdir()
                bins.mkdir()
                home.mkdir()
                for executable in ("codex", "claude", "omp", "sandbox-exec", "bwrap", "socat"):
                    path = bins / executable
                    path.write_text(
                        f"#!{sys.executable}\n"
                        "import sys\n"
                        "if sys.argv[1:] == ['models', '--json']:\n"
                        "    print('[{\"selector\":\"x/y\"}]')\n"
                        "elif '--help' in sys.argv:\n"
                        "    print('--restricted')\n"
                        "sys.exit(0)\n", encoding="utf-8")
                    path.chmod(0o755)
                operations, conflicts = installer.plan(target, [host], "copy", "preserve", "papers")
                self.assertFalse(conflicts)
                installer.apply(target, operations, [host])
                selected = host if host != "claude" or platform.system() in {"Darwin", "Linux"} else "codex"
                env = {**os.environ, "HOME": str(home), "XDG_CONFIG_HOME": str(home / ".config"),
                       "PATH": str(bins) + os.pathsep + os.defpath}
                onboard = subprocess.run([sys.executable, str(target / ".scripts/bin/onboard_research.py"),
                                          "--connect-only", "--agent", selected],
                                         cwd=target, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(onboard.returncode, 0, onboard.stdout + onboard.stderr)
                self.assertEqual(json.loads((target / ".research-harness-agent.json").read_text())["agent"], selected)
                result = subprocess.run([sys.executable, str(target / ".scripts/bin/verify_harness.py")],
                                        cwd=target, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                template = target / "90-Templates/paper/review-template.md"
                original_template = template.read_text(encoding="utf-8")
                template.write_text(original_template + "\n```mermaid\nflowchart LR\n```\n", encoding="utf-8")
                invalid = subprocess.run([sys.executable, str(target / ".scripts/bin/verify_harness.py")],
                                         cwd=target, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(invalid.returncode, 1, invalid.stdout + invalid.stderr)
                self.assertIn("FAIL", invalid.stdout)
                template.write_text(original_template, encoding="utf-8")
                index = target / "wiki-index.md"
                index.write_text(index.read_text(encoding="utf-8") + "\nstale fixture\n", encoding="utf-8")
                stale = subprocess.run([sys.executable, str(target / ".scripts/bin/verify_harness.py")],
                                       cwd=target, env=env, capture_output=True, text=True, timeout=30)
                self.assertEqual(stale.returncode, 1, stale.stdout + stale.stderr)
                self.assertIn("FAIL", stale.stdout)
                self.assertIn("wiki", stale.stdout.lower())
                self.assertIn("stale fixture", index.read_text(encoding="utf-8"))

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
