import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_webui_discovery import candidate, daily

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.scripts/bin'))
import discovery_cache


class DiscoveryCacheCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.bin = ROOT / '.scripts/bin'
        self.input = self.root / 'input.json'
        self.input.write_text(json.dumps(daily()), encoding='utf-8')

    def tearDown(self):
        self.temp.cleanup()

    def cli(self, *args):
        return subprocess.run([sys.executable, '-B', str(self.bin / 'discovery_cache.py'), '--root', str(self.root), *map(str, args)],
                              cwd=self.root, capture_output=True, text=True, check=False)

    def test_daily_write_duplicate_replace_and_atomic_validation(self):
        first = self.cli('daily-write', self.input)
        self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
        output = self.root / '00-Inbox/discovery/daily/2026-11-07.json'
        before = output.read_bytes()
        stored = json.loads(before)
        self.assertRegex(stored['slots'][0]['candidate']['candidate_id'], r'^c_[0-9a-f]{12}$')
        self.assertEqual(stored['slots'][0]['candidate']['status'], 'new')
        duplicate = self.cli('daily-write', self.input)
        self.assertEqual(duplicate.returncode, 3, duplicate.stdout + duplicate.stderr)
        self.assertEqual(output.read_bytes(), before)
        changed = daily(paper=candidate(title='Updated paper'))
        self.input.write_text(json.dumps(changed), encoding='utf-8')
        replaced = self.cli('daily-write', self.input, '--replace')
        self.assertEqual(replaced.returncode, 0, replaced.stdout + replaced.stderr)
        self.assertEqual(json.loads(output.read_text())['slots'][0]['candidate']['title'], 'Updated paper')
        before_invalid = output.read_bytes()
        changed['date'] = 'not-a-date'
        self.input.write_text(json.dumps(changed), encoding='utf-8')
        invalid = self.cli('daily-write', self.input, '--replace')
        self.assertEqual(invalid.returncode, 2, invalid.stdout + invalid.stderr)
        self.assertEqual(output.read_bytes(), before_invalid)
        self.assertEqual(list(output.parent.glob('*.tmp')), [])

    def test_daily_write_rejects_symlink_lock_without_touching_target(self):
        directory = self.root / '00-Inbox/discovery/daily'
        directory.mkdir(parents=True)
        outside = self.root / 'outside-lock'
        outside.write_text('unchanged', encoding='utf-8')
        (directory / '.2026-11-07.lock').symlink_to(outside)
        result = self.cli('daily-write', self.input, '--replace')
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(outside.read_text(), 'unchanged')
        self.assertFalse((directory / '2026-11-07.json').exists())

    def test_validate_accepts_valid_and_rejects_invalid_json_and_schema(self):
        valid = self.cli('validate', self.input)
        self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)
        self.input.write_text('{', encoding='utf-8')
        invalid_json = self.cli('validate', self.input)
        self.assertEqual(invalid_json.returncode, 2, invalid_json.stdout + invalid_json.stderr)
        value = daily()
        value['slots'][0]['candidate']['title'] = ''
        self.input.write_text(json.dumps(value), encoding='utf-8')
        invalid_schema = self.cli('validate', self.input)
        self.assertEqual(invalid_schema.returncode, 2, invalid_schema.stdout + invalid_schema.stderr)

    def test_candidate_id_is_deterministic_and_doi_case_insensitive(self):
        self.assertEqual(self.cli('daily-write', self.input).returncode, 0)
        output = self.root / '00-Inbox/discovery/daily/2026-11-07.json'
        first = json.loads(output.read_text())['slots'][0]['candidate']['candidate_id']
        value = daily(paper=candidate(title='Different title', doi='10.1234/eXAMPLE'))
        self.input.write_text(json.dumps(value), encoding='utf-8')
        result = self.cli('daily-write', self.input, '--replace')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(output.read_text())['slots'][0]['candidate']['candidate_id'], first)

    def test_non_https_candidate_url_is_removed(self):
        for url in ('http://example.org/paper', 'javascript:alert(1)', 'file:///tmp/paper'):
            with self.subTest(url=url):
                self.input.write_text(json.dumps(daily(paper=candidate(url=url))), encoding='utf-8')
                result = self.cli('daily-write', self.input, '--replace')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                output = self.root / '00-Inbox/discovery/daily/2026-11-07.json'
                self.assertIsNone(json.loads(output.read_text())['slots'][0]['candidate']['url'])


class DiscoveryCandidateTests(unittest.TestCase):
    def test_case_insensitive_doi_duplicates_merge_sources(self):
        first = candidate(doi='10.1234/AbC')
        second = candidate(title='Other title', doi='10.1234/abc')
        first['sources'] = ['s2']
        second['sources'] = ['web']
        first = discovery_cache.normalize_candidate(first)
        second = discovery_cache.normalize_candidate(second)
        self.assertEqual(first['candidate_id'], second['candidate_id'])
        merged = discovery_cache.merge_candidates([first, second])
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]['title'], first['title'])
        self.assertEqual(merged[0]['sources'], ['s2', 'web'])

    def test_candidate_validation_enforces_title_limit(self):
        paper = candidate(title='x' * 500)
        self.assertEqual(discovery_cache.validate_candidate(paper), [])
        paper['title'] = 'x' * 501
        self.assertTrue(discovery_cache.validate_candidate(paper))

    def test_candidate_id_key_priority_and_arxiv_versions(self):
        paper = candidate(doi=None)
        first = discovery_cache.make_candidate_id(paper)
        paper['ids']['arXiv'] = '2601.12345v9'
        self.assertEqual(discovery_cache.make_candidate_id(paper), first)
        paper['ids']['DOI'] = '10.1234/other'
        self.assertNotEqual(discovery_cache.make_candidate_id(paper), first)


if __name__ == '__main__':
    unittest.main()
