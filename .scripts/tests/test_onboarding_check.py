import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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
        (root / ".codex/config.toml").write_text('url = "https://mcp.example.com/mcp"', encoding="utf-8")
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
            with patch.object(doctor.shutil, "which", side_effect=lambda cmd: "/bin/tool" if cmd in {"codex", "git"} else None), \
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
            with patch.object(doctor.shutil, "which", return_value="/bin/tool"):
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


if __name__ == "__main__":
    unittest.main()
