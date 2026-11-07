import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.scripts/bin'))
import paper


class PaperRelatedTests(unittest.TestCase):
    def test_related_rows_normalizes_sorts_and_forwards_budget(self):
        response = {'data': [
            {'citedPaper': {'title': 'Low', 'citationCount': 1, 'externalIds': {}}},
            {'citedPaper': None},
            {'citedPaper': {'title': 'High', 'citationCount': 9, 'externalIds': {}}},
        ]}
        with patch.object(paper, 'fetch_json', return_value=response) as fetch:
            rows, failure = paper.related_rows('2601.12345', 'refs', 50, timeout=12, retries=1)
        self.assertIsNone(failure)
        self.assertEqual([row['title'] for row in rows], ['High', 'Low'])
        args, kwargs = fetch.call_args
        self.assertIn('/references?', args[0])
        self.assertIn('limit=50', args[0])
        self.assertEqual(kwargs['timeout'], 12)
        self.assertEqual(kwargs['retries'], 1)

    def test_related_rows_soft_failure_and_cli_exit(self):
        with patch.object(paper, 'fetch_json', side_effect=paper.FetchError('HTTP 429', status=429)):
            rows, failure = paper.related_rows('2601.12346', 'cites', 10)
            self.assertIsNone(rows)
            self.assertIn('429', failure)
            with contextlib.redirect_stderr(io.StringIO()) as stderr:
                with self.assertRaises(SystemExit) as raised:
                    paper.get_related('2601.12346', 'cites', 10)
            self.assertNotEqual(raised.exception.code, 0)
            self.assertIn('Semantic Scholar', stderr.getvalue())


if __name__ == '__main__':
    unittest.main()
