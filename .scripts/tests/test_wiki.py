import contextlib
import importlib.util
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / ".scripts/bin"))
spec = importlib.util.spec_from_file_location("wiki", REPO / ".scripts/bin/wiki.py")
wiki = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = wiki
spec.loader.exec_module(wiki)


class WikiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, capture_output=True)
        self.root_patch = patch.object(wiki, "ROOT", self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def put(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def run_wiki(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["wiki.py", *args]), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                result = wiki.main()
            except SystemExit as exc:
                result = exc.code
        return result, out.getvalue(), err.getvalue()

    def test_index_scope_order_titles_summaries_and_determinism(self):
        self.put(".gitignore", "02-Concepts/ignored.md\n")
        for name in ("index", "keep", "favorites"):
            self.put(f"01-Papers/{name}.md", f"# {name}\n")
        self.put("01-Papers/reviews/z/z.md", "---\ntitle: Frontmatter title\nsummary: Frontmatter summary\n---\n# Ignored heading\nBody ignored.\n")
        self.put("01-Papers/reviews/a/a.md", "# Heading title\n\n- list ignored\n| table ignored |\n\nPlain **body** with [link](target.md).\n")
        self.put("01-Papers/triage/triage.md", "---\ndescription: Description summary\n---\n# Triage title\n")
        self.put("02-Concepts/stem.md", "- only a list\n")
        self.put("02-Concepts/long.md", "# Long title\n\n" + "x" * 150 + "\n")
        self.put("03-Trends/daily/day.md", "# Trend title\n")
        self.put("05-Ideas/thought-experiments/idea.md", "# Idea title\n")
        self.put("04-Projects/thought-experiment-runs/run/results.md", "# Result title\n")
        self.put("04-Projects/thought-experiment-runs/run/critique.md", "# Critique title\n")
        self.put("04-Projects/thought-experiment-runs/run/manifest.md", "# Manifest title\n")
        self.put("04-Projects/thought-experiment-runs/run/other.md", "# Outside scope\n")
        self.put("02-Concepts/README.md", "# Readme excluded\n")
        self.put("02-Concepts/ignored.md", "# Ignored untracked\n")
        self.put("90-Templates/template.md", "# Template excluded\n")
        subprocess.run(["git", "-C", str(self.root), "add", ".gitignore", "01-Papers/reviews/z/z.md"], check=True, capture_output=True)
        code, out, err = self.run_wiki("index")
        self.assertEqual(code, 0, out + err)
        index = (self.root / "wiki-index.md").read_text(encoding="utf-8")
        self.assertIn("자동 생성 파일. 직접 수정하지 말고 python3 .scripts/bin/wiki.py index로 갱신한다.", index)
        for name in ("index", "keep", "favorites"):
            self.assertIn(f"01-Papers/{name}.md", index)
        self.assertIn("- [Frontmatter title](01-Papers/reviews/z/z.md): Frontmatter summary", index)
        self.assertIn("- [Heading title](01-Papers/reviews/a/a.md): Plain body with link.", index)
        self.assertIn("- [Triage title](01-Papers/triage/triage.md): Description summary", index)
        self.assertRegex(index, r"(?m)^- \[stem\]\(02-Concepts/stem\.md\)\s*$")
        long_entry = next(line for line in index.splitlines() if "02-Concepts/long.md" in line)
        summary = long_entry.split(": ", 1)[1]
        self.assertTrue(summary.endswith("…"))
        self.assertGreaterEqual(len(summary), 120)
        self.assertLessEqual(len(summary), 121)
        paths = ["01-Papers/reviews/a/a.md", "01-Papers/reviews/z/z.md", "01-Papers/triage/triage.md", "02-Concepts/long.md", "02-Concepts/stem.md", "03-Trends/daily/day.md", "05-Ideas/thought-experiments/idea.md", "04-Projects/thought-experiment-runs/run/critique.md", "04-Projects/thought-experiment-runs/run/manifest.md", "04-Projects/thought-experiment-runs/run/results.md"]
        self.assertEqual([index.index(path) for path in paths], sorted(index.index(path) for path in paths))
        for excluded in ("Readme excluded", "Ignored untracked", "Template excluded", "Outside scope"):
            self.assertNotIn(excluded, index)
        self.assertEqual(self.run_wiki("index")[0], 0)
        self.assertEqual((self.root / "wiki-index.md").read_text(encoding="utf-8"), index)

    def test_review_callout_tldr_is_index_summary(self):
        self.put("01-Papers/reviews/other/example.md",
                 "# Example\n\n> [!abstract] TL;DR\n> 실제 요약입니다.\n\n본문입니다.\n")
        code, out, err = self.run_wiki("index")
        self.assertEqual(code, 0, out + err)
        index = (self.root / "wiki-index.md").read_text(encoding="utf-8")
        self.assertIn("- [Example](01-Papers/reviews/other/example.md): 실제 요약입니다.", index)
        self.assertNotIn("[!abstract]", index)

    def test_review_figure_relative_image_link_lint(self):
        review = "01-Papers/reviews/other/example.md"
        self.put(review, "# Example\n\n![방법](figures/x.svg)\n")
        figure = self.put("01-Papers/reviews/other/figures/x.svg", "<svg/>\n")
        self.assertEqual(self.run_wiki("index")[0], 0)
        _, output, _ = self.run_wiki("lint", "--json")
        self.assertFalse(any(f["code"] == "broken-link" and f["path"] == review
                             for f in json.loads(output)))
        figure.unlink()
        _, output, _ = self.run_wiki("lint", "--json")
        self.assertTrue(any(f["code"] == "broken-link" and f["path"] == review
                            and "figures/x.svg" in f["detail"] for f in json.loads(output)))

    def test_index_links_only_existing_paper_lists(self):
        self.assertEqual(self.run_wiki("index")[0], 0)
        index = (self.root / "wiki-index.md").read_text(encoding="utf-8")
        self.assertNotIn("목록:", index)
        for name in ("index", "keep", "favorites"):
            self.assertNotIn(f"01-Papers/{name}.md", index)
        self.put("01-Papers/keep.md", "# Keep\n")
        self.assertEqual(self.run_wiki("index")[0], 0)
        index = (self.root / "wiki-index.md").read_text(encoding="utf-8")
        self.assertIn("목록:", index)
        self.assertIn("01-Papers/keep.md", index)
        self.assertNotIn("01-Papers/index.md", index)
        self.assertNotIn("01-Papers/favorites.md", index)
        self.put("01-Papers/index.md", "# Index\n")
        self.put("01-Papers/favorites.md", "# Favorites\n")
        self.assertEqual(self.run_wiki("index")[0], 0)
        index = (self.root / "wiki-index.md").read_text(encoding="utf-8")
        for name in ("index", "keep", "favorites"):
            self.assertIn(f"01-Papers/{name}.md", index)

    def test_index_check_never_writes_missing_stale_or_fresh(self):
        self.put("02-Concepts/example.md", "# Example\n")
        index = self.root / "wiki-index.md"
        self.assertEqual(self.run_wiki("index", "--check")[0], 1)
        self.assertFalse(index.exists())
        index.write_text("stale\n", encoding="utf-8")
        before = (index.read_bytes(), index.stat().st_mtime_ns)
        self.assertEqual(self.run_wiki("index", "--check")[0], 1)
        self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), before)
        self.assertEqual(self.run_wiki("index")[0], 0)
        before = (index.read_bytes(), index.stat().st_mtime_ns)
        self.assertEqual(self.run_wiki("index", "--check")[0], 0)
        self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), before)

    def test_index_json_is_machine_readable_and_check_remains_read_only(self):
        self.put("02-Concepts/example.md", "# JSON example\n")
        code, output, err = self.run_wiki("index", "--json")
        self.assertEqual(code, 0, output + err)
        parsed = json.loads(output)
        self.assertEqual(parsed["path"], "wiki-index.md")
        self.assertEqual(parsed["mode"], "write")
        self.assertIn(parsed["status"], ("written", "unchanged"))
        self.assertEqual(parsed["pages"], 1)
        self.assertEqual([section["name"] for section in parsed["sections"]],
                         ["Papers", "Triage", "Concepts", "Trends", "Ideas", "Projects"])
        index = self.root / "wiki-index.md"
        before = (index.read_bytes(), index.stat().st_mtime_ns)
        code, output, err = self.run_wiki("index", "--check", "--json")
        self.assertEqual(code, 0, output + err)
        checked = json.loads(output)
        self.assertEqual((checked["path"], checked["mode"], checked["status"]),
                         ("wiki-index.md", "check", "fresh"))
        self.assertEqual(checked["pages"], 1)
        self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), before)

    def test_nested_image_links_supply_plain_index_text_and_lint_outer_target(self):
        self.put("02-Concepts/source.md",
                 "# [![logo](l.svg)](x.md) Title\n\nSee [![badge](badge.svg)](target.md)\n")
        self.put("02-Concepts/l.svg", "<svg/>\n")
        self.put("02-Concepts/badge.svg", "<svg/>\n")
        self.put("02-Concepts/x.md", "# Existing link target\n")
        self.assertEqual(self.run_wiki("index")[0], 0)
        index = (self.root / "wiki-index.md").read_text(encoding="utf-8")
        self.assertIn("- [logo Title](02-Concepts/source.md): See badge\n", index)
        code, output, err = self.run_wiki("lint", "--json")
        self.assertEqual(code, 1, output + err)
        findings = json.loads(output)
        self.assertTrue(any(f["code"] == "broken-link" and f["path"] == "02-Concepts/source.md"
                            and "target.md" in f["detail"] for f in findings), findings)
        self.put("02-Concepts/target.md", "# Resolved target\n")
        self.assertEqual(self.run_wiki("index")[0], 0)
        code, output, err = self.run_wiki("lint", "--json")
        self.assertEqual(code, 0, output + err)
        self.assertFalse(any(f["code"] == "broken-link" for f in json.loads(output)))

    def test_inline_code_and_unbalanced_or_escaped_link_text(self):
        self.put("02-Concepts/summary.md", "# Summary\n\nSee [a `[x` b](target.md)\n")
        self.put("02-Concepts/target.md", "# Target\n")
        self.put("02-Concepts/syntax.md",
                 "# Syntax\n\n\\[not a link](x.md)\n[a [b](t.md)\n[ref] text\n")
        self.assertEqual(self.run_wiki("index")[0], 0)
        index = (self.root / "wiki-index.md").read_text(encoding="utf-8")
        self.assertIn("- [Summary](02-Concepts/summary.md): See a [x b\n", index)
        self.assertIn("[not a link](x.md)", index)
        code, output, err = self.run_wiki("lint", "--json")
        self.assertEqual(code, 1, output + err)
        findings = json.loads(output)
        broken = [f for f in findings if f["code"] == "broken-link"]
        self.assertEqual(len(broken), 1, findings)
        self.assertEqual(broken[0]["path"], "02-Concepts/syntax.md")
        self.assertIn("t.md", broken[0]["detail"])
        self.assertNotIn("x.md", broken[0]["detail"])
        self.put("02-Concepts/t.md", "# Inner target\n")
        self.assertEqual(self.run_wiki("index")[0], 0)
        code, output, err = self.run_wiki("lint", "--json")
        self.assertEqual(code, 0, output + err)
        self.assertFalse(any(f["code"] == "broken-link" for f in json.loads(output)))

    def test_nested_image_outer_link_counts_as_inbound_for_orphan_check(self):
        self.put("02-Concepts/target.md", "# Target\n")
        self.put("01-Papers/triage/source.md",
                 "# Source\n\n[![i](i.svg)](../../02-Concepts/target.md)\n")
        self.put("01-Papers/triage/i.svg", "<svg/>\n")
        self.assertEqual(self.run_wiki("index")[0], 0)
        code, output, err = self.run_wiki("lint", "--json")
        self.assertEqual(code, 0, output + err)
        findings = json.loads(output)
        self.assertFalse(any(f["code"] == "orphan-page" and f["path"] == "02-Concepts/target.md"
                             for f in findings), findings)

    def test_log_appends_with_header_dates_and_relative_paths(self):
        review = self.put("01-Papers/reviews/other/example.md", "# Example\n")
        record = self.put("01-Papers/library/example.json", "{}\n")
        code, out, err = self.run_wiki("log", "--op", "ingest", "--title", "Example paper", "--date", "2024-02-29", "--path", str(review), "--path", str(record))
        self.assertEqual(code, 0, out + err)
        log = self.root / "wiki-log.md"
        first = log.read_text(encoding="utf-8")
        self.assertTrue(first.startswith("# 작업 기록\n"))
        self.assertIn("추가만 한다. 기존 항목을 수정·삭제하지 않는다.", first)
        self.assertIn("## [2024-02-29] ingest | Example paper\n- 01-Papers/reviews/other/example.md\n- 01-Papers/library/example.json\n", first)
        self.assertEqual(self.run_wiki("log", "--op", "query", "--title", "Follow up", "--date", "2025-01-02")[0], 0)
        second = log.read_text(encoding="utf-8")
        self.assertTrue(second.startswith(first))
        self.assertEqual(second.count("# 작업 기록"), 1)
        self.assertIn("## [2025-01-02] query | Follow up\n", second[len(first):])

    def test_lint_parses_balanced_escaped_angle_and_titled_destinations(self):
        self.put("02-Concepts/topic(v2).md", "# Balanced target\n")
        self.put("02-Concepts/topic(escaped).md", "# Escaped target\n")
        self.put("02-Concepts/x.md", "# Titled target\n")
        self.put("02-Concepts/dir with space/x.md", "# Space target\n")
        self.put(
            "02-Concepts/source.md",
            '# Source\n'
            '[balanced](topic(v2).md)\n'
            '[missing](topic(v3).md)\n'
            '[escaped](topic\\(escaped\\).md)\n'
            '[angle](<dir with space/x.md>)\n'
            '[title](x.md "t")\n',
        )
        self.assertEqual(self.run_wiki("index")[0], 0)
        code, output, err = self.run_wiki("lint", "--json")
        self.assertEqual(code, 1, output + err)
        findings = json.loads(output)
        broken = [finding for finding in findings if finding["code"] == "broken-link"]
        self.assertEqual(len(broken), 1, findings)
        self.assertIn("topic(v3).md", broken[0]["detail"])
        orphans = {finding["path"] for finding in findings if finding["code"] == "orphan-page"}
        for path in ("02-Concepts/topic(v2).md", "02-Concepts/topic(escaped).md", "02-Concepts/x.md"):
            self.assertNotIn(path, orphans)

    def test_lint_errors_warnings_json_and_link_exceptions(self):
        target = self.put("02-Concepts/target.md", "# Target\n")
        (target.parent / "alias.md").symlink_to(target.name)
        self.put("02-Concepts/source.md", "# Source\n[ok](alias.md#part?query)\n[missing](missing.md#part)\n[web](https://example.org/x)\n[mail](mailto:a@example.org)\n[local](#section)\n```md\n[code](not-real.md)\n```\n")
        self.put("02-Concepts/untitled.md", "A body without a title.\n")
        self.put("03-Trends/daily/orphan.md", "# Unlinked trend\n")
        self.put("01-Papers/index.md", "[Source](../02-Concepts/source.md)\n")
        self.assertEqual(self.run_wiki("index")[0], 0)
        code, output, err = self.run_wiki("lint", "--json")
        self.assertEqual(code, 1, output + err)
        findings = json.loads(output)
        self.assertIsInstance(findings, list)
        self.assertTrue(all(isinstance(f, dict) and {"level", "code", "path", "detail"} <= f.keys() for f in findings))
        broken = [f for f in findings if f["code"] == "broken-link"]
        self.assertEqual(len(broken), 1, findings)
        self.assertEqual(broken[0]["level"], "ERROR")
        self.assertIn("source.md", broken[0]["path"])
        self.assertIn("missing.md", broken[0]["detail"])
        self.assertTrue(any(f["code"] == "orphan-page" and "untitled.md" in f["path"] and f["level"] == "WARNING" for f in findings))
        self.assertFalse(any(f["code"] == "orphan-page" and f["path"] == "03-Trends/daily/orphan.md" for f in findings))
        self.assertTrue(any(f["code"] == "missing-title" and "untitled.md" in f["path"] and f["level"] == "WARNING" for f in findings))
        self.put("02-Concepts/source.md", "# Source\n[ok](alias.md#part)\n")
        self.assertEqual(self.run_wiki("index")[0], 0)
        code, output, err = self.run_wiki("lint", "--json")
        self.assertEqual(code, 0, output + err)
        self.assertTrue(any(f["level"] == "WARNING" for f in json.loads(output)))
        (self.root / "wiki-index.md").write_text("stale\n", encoding="utf-8")
        code, output, err = self.run_wiki("lint")
        self.assertEqual(code, 1, output + err)
        self.assertRegex(output, r"(?m)^ERROR stale-index ")
        self.assertRegex(output, r"(?m)^WARNING (orphan-page|missing-title) ")

    def test_lint_skips_single_and_multiline_html_comments(self):
        self.put("02-Concepts/target.md", "# Target\n")
        self.put("02-Concepts/source.md",
                 "# Source\n"
                 "<!-- [single](single-missing.md) -->\n"
                 "<!-- opening\n[multiline](multi-missing.md)\n"
                 "[hidden inbound](target.md) --> [visible](visible-missing.md)\n")
        self.put("01-Papers/index.md", "[Source](../02-Concepts/source.md)\n")
        self.assertEqual(self.run_wiki("index")[0], 0)
        code, output, err = self.run_wiki("lint", "--json")
        self.assertEqual(code, 1, output + err)
        findings = json.loads(output)
        broken = [f for f in findings if f["code"] == "broken-link"]
        self.assertEqual(len(broken), 1, findings)
        self.assertIn("visible-missing.md", broken[0]["detail"])
        self.assertTrue(any(f["code"] == "orphan-page" and f["path"] == "02-Concepts/target.md"
                            for f in findings), findings)

    def test_lint_classifies_missing_and_outside_targets(self):
        cases = (
            ("[pdf](../01-Papers/pdfs/other/missing.pdf#page=2)\n",
             "missing-source", "INFO", 0),
            ("[outside](../../missing-outside.pdf)\n",
             "outside-repo", "WARNING", 0),
            ("[existing outside](../../)\n",
             "outside-repo", "WARNING", 0),
            ("[missing](missing.md)\n",
             "broken-link", "ERROR", 1),
            ("[near pdf directory](../01-Papers/pdfs-other/missing.pdf)\n",
             "broken-link", "ERROR", 1),
        )
        for link, expected_code, level, exit_code in cases:
            with self.subTest(link=link):
                self.put("02-Concepts/source.md", "# Source\n" + link)
                self.put("01-Papers/index.md", "[Source](../02-Concepts/source.md)\n")
                self.assertEqual(self.run_wiki("index")[0], 0)
                code, output, err = self.run_wiki("lint", "--json")
                self.assertEqual(code, exit_code, output + err)
                findings = json.loads(output)
                classified = [f for f in findings if f["code"] in
                              {"missing-source", "outside-repo", "broken-link"}]
                self.assertEqual(len(classified), 1, findings)
                self.assertEqual((classified[0]["code"], classified[0]["level"]),
                                 (expected_code, level))
                self.assertEqual(classified[0]["path"], "02-Concepts/source.md")
                if expected_code == "missing-source":
                    self.assertIn("원문 PDF는 저장소에 포함되지 않음", classified[0]["detail"])
                code, output, err = self.run_wiki("lint")
                self.assertEqual(code, exit_code, output + err)
                self.assertRegex(output, rf"(?m)^{level} {expected_code} ")

    def test_lint_html_comments_and_code_delimiter_precedence(self):
        cases = (
            "<!--\n`-->`\n[visible](missing.md)\n",
            "<!--\n```\n-->\n[visible](missing.md)\n",
            "`<!--`\n[visible](missing.md)\n",
            "```html\n<!--\n```\n[visible](missing.md)\n",
        )
        for body in cases:
            with self.subTest(body=body):
                self.put("02-Concepts/source.md", "# Source\n" + body)
                self.put("01-Papers/index.md", "[Source](../02-Concepts/source.md)\n")
                self.assertEqual(self.run_wiki("index")[0], 0)
                code, output, err = self.run_wiki("lint", "--json")
                self.assertEqual(code, 1, output + err)
                broken = [f for f in json.loads(output) if f["code"] == "broken-link"]
                self.assertEqual(len(broken), 1, output)
                self.assertEqual(broken[0]["level"], "ERROR")
                self.assertIn("missing.md", broken[0]["detail"])

    def test_lint_classifies_resolved_symlink_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            outside = Path(directory).resolve()
            (outside / "existing.md").write_text("# External\n", encoding="utf-8")
            self.put("02-Concepts/source.md", "# Source\n")
            (self.root / "02-Concepts/external").symlink_to(outside, target_is_directory=True)
            pdfs = self.root / "01-Papers/pdfs"
            pdfs.mkdir(parents=True)
            (self.root / "02-Concepts/pdf-link").symlink_to(pdfs, target_is_directory=True)
            self.put("01-Papers/index.md", "[Source](../02-Concepts/source.md)\n")
            cases = (
                ("external/existing.md", "outside-repo", "WARNING"),
                ("external/missing.md", "outside-repo", "WARNING"),
                ("pdf-link/missing.pdf", "missing-source", "INFO"),
            )
            for target, expected_code, level in cases:
                with self.subTest(target=target):
                    self.put("02-Concepts/source.md", f"# Source\n[link]({target})\n")
                    self.assertEqual(self.run_wiki("index")[0], 0)
                    code, output, err = self.run_wiki("lint", "--json")
                    self.assertEqual(code, 0, output + err)
                    classified = [f for f in json.loads(output) if f["code"] in
                                  {"missing-source", "outside-repo", "broken-link"}]
                    self.assertEqual(len(classified), 1, output)
                    self.assertEqual((classified[0]["code"], classified[0]["level"]),
                                     (expected_code, level))

    def test_lint_text_summary_counts_all_levels(self):
        self.put("02-Concepts/source.md",
                 "# Source\n"
                 "[broken](missing.md)\n"
                 "[outside](../../missing-outside.md)\n"
                 "[pdf](../01-Papers/pdfs/other/missing.pdf)\n")
        self.put("01-Papers/index.md", "[Source](../02-Concepts/source.md)\n")
        self.assertEqual(self.run_wiki("index")[0], 0)
        code, output, err = self.run_wiki("lint")
        self.assertEqual(code, 1, output + err)
        self.assertIn("wiki lint: 1 error(s), 1 warning(s), 1 info\n", output)

    def test_help_has_no_filesystem_side_effects(self):
        before = {p.relative_to(self.root) for p in self.root.rglob("*")}
        for args in (("--help",), ("index", "--help"), ("log", "--help"), ("lint", "--help")):
            with self.subTest(args=args):
                code, output, err = self.run_wiki(*args)
                self.assertEqual(code, 0, output + err)
                self.assertIn("usage:", output.lower())
        self.assertEqual({p.relative_to(self.root) for p in self.root.rglob("*")}, before)


if __name__ == "__main__":
    unittest.main()
