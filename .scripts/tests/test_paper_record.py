import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '.scripts/bin'))
ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('paper_record', ROOT / '.scripts/bin/paper_record.py')
paper_record = importlib.util.module_from_spec(spec)
spec.loader.exec_module(paper_record)


class ImportedReviewSummaryTests(unittest.TestCase):
    def test_legacy_and_callout_tldr_are_extracted(self):
        cases = (
            '> **TL;DR** — 기존 요약입니다.\n',
            '> [!abstract] TL;DR\n> 새로운 요약입니다.\n',
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf = root / '01-Papers/pdfs/other/example.pdf'
            review = root / '01-Papers/reviews/other/example.md'
            review.parent.mkdir(parents=True)
            with patch.object(paper_record, 'ROOT', root):
                for text, expected in zip(cases, ('기존 요약입니다.', '새로운 요약입니다.')):
                    with self.subTest(text=text):
                        review.write_text('---\ntitle: Example\n---\n\n# Example\n\n' + text, encoding='utf-8')
                        metadata = paper_record.parse_frontmatter(review)
                        record = paper_record.imported_record(pdf, 'other', review, metadata)
                        self.assertEqual(record['one_line_summary'], expected)

    def test_tldr_paragraph_boundaries(self):
        self.assertEqual(paper_record.review_tldr(
            '> [!abstract]- TL;DR\n> 첫 문장.\n> 둘째 문장.\n>\n> 제외.\n'),
            '첫 문장. 둘째 문장.')
        self.assertEqual(paper_record.review_tldr('# 제목\n본문\n'), '')


if __name__ == '__main__':
    unittest.main()
