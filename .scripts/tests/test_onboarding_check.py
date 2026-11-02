import importlib.util
import json
import os
import contextlib
import io
import sys
from types import SimpleNamespace
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bin"))
SOURCE = Path(__file__).resolve().parents[1] / "bin/onboarding_check.py"
spec = importlib.util.spec_from_file_location("onboarding_check", SOURCE)
doctor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(doctor)


class OnboardingChecks(unittest.TestCase):
    def fixture(self, root):
        for relative in doctor.FILES + ("CLAUDE.md",):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        (root / ".mcp.json").write_text('{"mcpServers": {}}', encoding="utf-8")
        (root / ".codex/config.toml").write_text(
            '\n'.join(f'[mcp_servers.{name}]' for name in ('arxiv-mcp', 'exa', 'paper-search-mcp')),
            encoding="utf-8")
        for relative in doctor.DIRECTORIES:
            (root / relative).mkdir(parents=True, exist_ok=True)
        (root / ".omp/agents").mkdir(parents=True)
        for name in doctor.SKILLS:
            skill = root / ".agents/skills" / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("test", encoding="utf-8")
            alias = root / ".claude/skills" / name
            alias.parent.mkdir(parents=True, exist_ok=True)
            alias.symlink_to(f"../../.agents/skills/{name}", target_is_directory=True)

    def test_missing_optional_tools_do_not_block_basic_use_or_reveal_key(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            with patch.object(doctor.shutil, "which", side_effect=lambda cmd: None if cmd in {"uvx", "graphify"} else "/bin/tool"), \
                 patch.object(doctor.subprocess, "run", return_value=SimpleNamespace(returncode=0)), \
                 patch.dict(os.environ, {"EXA_API_KEY": "never-display-this-key"}):
                result = doctor.check(root, "codex")
                self.assertFalse(any(status == "FAIL" for status, _ in result), result)
                self.assertTrue(any(status == "WARN" for status, _ in result))
                self.assertNotIn("never-display-this-key", str(result))
                required = doctor.check(root, "codex", with_mcp=True, with_graphify=True)
                self.assertTrue(any(status == "FAIL" for status, _ in required))

    def test_relocated_clone_accepts_relative_links_and_rejects_broken_ones(self):
        with tempfile.TemporaryDirectory() as temporary:
            old = Path(temporary) / "old"
            new = Path(temporary) / "renamed-repo"
            self.fixture(old)
            old.rename(new)
            with patch.object(doctor.shutil, "which", return_value="/bin/tool"), \
                    patch.object(doctor.subprocess, "run", return_value=SimpleNamespace(returncode=0)):
                self.assertFalse(any(status == "FAIL" for status, _ in doctor.check(new, "claude")))
                alias = new / ".claude/skills/paper-review"
                alias.unlink()
                alias.symlink_to("../../missing", target_is_directory=True)
                result = doctor.check(new, "claude")
                self.assertTrue(any(status == "FAIL" and "paper-review" in text for status, text in result))

    def test_incomplete_clone_malformed_config_and_machine_paths_are_reported(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.fixture(root)
            (root / "AGENTS.md").unlink()
            (root / ".mcp.json").write_text("invalid", encoding="utf-8")
            (root / ".codex/config.toml").write_text('command = "/home/person/bin/npx"', encoding="utf-8")
            with patch.object(doctor.shutil, "which", return_value=None):
                result = doctor.check(root, "codex")
            failures = [text for status, text in result if status == "FAIL"]
            for expected in ("AGENTS.md", "JSON", "절대 경로", "codex"):
                self.assertTrue(any(expected in text for text in failures), failures)

    def test_omp_cli_creates_setup_directories_in_selected_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.fixture(root)
            for relative in reversed(doctor.DIRECTORIES):
                (root / relative).rmdir()
            argv = ["onboarding_check.py", "--host", "omp", "--root", str(root), "--create-dirs", "--json"]
            with patch.object(sys, "argv", argv), patch.object(doctor.shutil, "which", return_value="/bin/tool"), \
                    patch.object(doctor.subprocess, "run", return_value=SimpleNamespace(returncode=0)), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(doctor.main(), 0)
            expected = ["00-Inbox", *(f"01-Papers/{kind}/{category}" for kind in ("pdfs", "reviews")
                        for category in ("wifi-csi", "game-ai", "agent-ai", "computer-vision", "other")),
                        "01-Papers/triage", "01-Papers/library", "02-Concepts", "03-Trends/daily",
                        "04-Projects", "05-ideas/thought-experiments", "99-Attachments"]
            for relative in expected:
                self.assertTrue((root / relative).is_dir(), relative)

    def test_auto_host_prefers_config_then_available_cli_and_fails_without_host(self):
        cases = [("omp", {"omp"}, "omp"), (None, {"claude"}, "claude"), (None, set(), None)]
        for configured, installed, expected in cases:
            with self.subTest(configured=configured, installed=installed), tempfile.TemporaryDirectory() as directory:
                root = Path(directory).resolve()
                self.fixture(root)
                if configured:
                    (root / ".research-harness-agent.json").write_text(json.dumps({"agent": configured}))
                def which(name):
                    if name in {"codex", "claude", "omp"}:
                        return "/fake/" + name if name in installed else None
                    return "/fake/" + name
                output = io.StringIO()
                argv = ["onboarding_check.py", "--root", str(root), "--json"]
                with patch.object(sys, "argv", argv), patch.object(doctor.shutil, "which", side_effect=which), \
                        patch.object(doctor.subprocess, "run", return_value=SimpleNamespace(returncode=0)), \
                        contextlib.redirect_stdout(output):
                    code = doctor.main()
                payload = json.loads(output.getvalue())
                results = payload["results"]
                failures = [entry["message"] for entry in results if entry["status"] == "FAIL"]
                if expected:
                    self.assertEqual(code, 0, failures)
                    self.assertTrue(any(expected in entry["message"] and entry["status"] == "PASS"
                                        for entry in results), results)
                    self.assertFalse(any("codex" in message.lower() for message in failures), failures)
                else:
                    self.assertEqual(code, 1)
                    self.assertTrue(failures)


if __name__ == "__main__":
    unittest.main()
