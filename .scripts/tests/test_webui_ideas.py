import http.client
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.scripts/bin'))

import thought_experiments_html as ideas
from webui import reviews, security, server


class IdeasAPITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.notes = self.root / '05-Ideas/thought-experiments'
        self.runs = self.root / '04-Projects/thought-experiment-runs'
        self.registry = self.runs / 'CRITICAL_VALIDATION_REGISTRY.md'
        self.queue = self.root / '04-Projects/research-todo/queue.json'
        self.notes.mkdir(parents=True)
        patches = patch.multiple(ideas, ROOT=self.root, IDEAS=self.notes, RUNS=self.runs,
                                 REGISTRY=self.registry, TODO_QUEUE=self.queue)
        patches.start()
        self.addCleanup(patches.stop)
        root_patch = patch.object(reviews, 'ROOT', self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        self.server = server.make_server(0, csrf_token='test-token')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.close_server)
        self.headers = {'Origin': f'http://127.0.0.1:{self.server.server_port}',
                        'X-CSRF-Token': 'test-token', 'Content-Type': 'application/json'}

    def close_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(3)

    def put(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        return target

    def request(self, method='GET', headers=None, body=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            conn.request(method, '/api/ideas', body=body, headers=headers or {})
            response = conn.getresponse()
            return response.status, response.headers, response.read()
        finally:
            conn.close()

    def data(self):
        status, _, body = self.request()
        self.assertEqual(status, 200, body)
        data = json.loads(body)
        self.assertEqual(set(data), {'ideas', 'hrefs', 'errors'})
        return data

    def fixture(self):
        note = '05-Ideas/thought-experiments/alpha.md'
        self.put(note, '# Alpha\n- 상태: 실행 완료\n- 사용자 결정: 중단\n\n## 핵심 가설\nA hypothesis\n\n## 반증 조건\nA failure\n')
        self.put('05-Ideas/thought-experiments/beta.md', '# Beta\n\n## 가설\nAnother hypothesis\n')
        self.put('04-Projects/thought-experiment-runs/alpha/analysis.json', json.dumps({
            'critics': {'method': {'status': 'clear'}},
            'literature_search': {'status': 'done', 'included_papers': [{'paper_id': 'paper-1'}]},
            'user_decision': {'decision': '승인'},
        }))
        self.put('04-Projects/thought-experiment-runs/alpha/results.md', 'Results')
        self.put('04-Projects/thought-experiment-runs/alpha/brief.md', 'Brief')
        self.put('04-Projects/thought-experiment-runs/alpha/manifest.md', 'Manifest')
        self.put('04-Projects/thought-experiment-runs/alpha/critique-method.md', 'Critique')
        self.put('04-Projects/thought-experiment-runs/alpha/결과 data.csv', 'x,y\n1,2\n')
        self.put('01-Papers/library/paper.json', json.dumps({'paper_id': 'paper-1'}))
        self.put('docs/agent-research-todo.md', 'TODO')
        self.put('docs/evidence.md', 'Evidence')
        self.put('docs/result.md', 'Task result')
        self.put('.omp/private.md', 'Private')
        self.put('04-Projects/thought-experiment-runs/CRITICAL_VALIDATION_REGISTRY.md',
                 '| alpha | Alpha | ' + note + ' | complete | clear | clear | clear | 실험 가능 | 승인 | '
                 '[evidence](../../docs/evidence.md) | 2026-10-06 |\n')
        self.put('04-Projects/research-todo/queue.json', json.dumps({'tasks': [
            {'idea_path': note, 'task_id': 't1', 'status': 'done', 'result_path': 'docs/result.md'},
            {'idea_path': note, 'task_id': 't2', 'status': 'pending', 'result_path': '.omp/private.md'},
            {'idea_path': note, 'task_id': 't3', 'status': 'pending', 'result_path': '../outside.md'},
        ]}))

    def test_scan_payload_and_every_path_follows_static_policy(self):
        self.fixture()
        expected = ideas.scan()
        data = self.data()
        self.assertEqual(data['ideas'], expected)
        self.assertEqual(data['errors'], [])
        alpha = next(item for item in data['ideas'] if item['id'] == 'alpha')
        self.assertTrue(alpha['decisionConflict'])
        self.assertTrue(alpha['statusConflict'])
        self.assertEqual(alpha['hypothesis'], 'A hypothesis')
        self.assertEqual(alpha['falsification'], 'A failure')
        self.assertEqual(alpha['paperPaths'], ['01-Papers/library/paper.json'])
        self.assertEqual(alpha['evidence'], ['docs/evidence.md'])
        paths = set()
        for idea in data['ideas']:
            for key in ('note', 'brief', 'results', 'todo', 'manifest', 'analysis'):
                if idea[key]:
                    paths.add(idea[key])
            for key in ('critiques', 'evidence', 'paperPaths', 'artifacts', 'todoResults'):
                paths.update(path for path in idea[key] if path)
        self.assertTrue(paths <= data['hrefs'].keys())
        for path in paths:
            with self.subTest(path=path):
                resolved = security.resolve_static(self.root, '/' + quote(path, safe='/'),
                                                   reviews.ALLOWED_ROOTS, reviews.ALLOWED_ROOT_FILES)
                expected_href = '/' + quote(path, safe='/') if resolved is not None else None
                self.assertEqual(data['hrefs'][path], expected_href)
        self.assertIsNone(data['hrefs']['.omp/private.md'])
        self.assertIsNone(data['hrefs']['../outside.md'])
        self.assertEqual(data['hrefs']['04-Projects/thought-experiment-runs/alpha/결과 data.csv'],
                         '/04-Projects/thought-experiment-runs/alpha/%EA%B2%B0%EA%B3%BC%20data.csv')

    def test_symlinked_note_to_sensitive_file_has_no_href(self):
        self.fixture()
        sensitive = self.put('.omp/private-note.md', '# Private idea\n')
        note = self.notes / 'linked.md'
        note.symlink_to(sensitive)
        data = self.data()
        linked = next(item for item in data['ideas'] if item['id'] == 'linked')
        self.assertIsNone(data['hrefs'][linked['note']])

    def test_malformed_analysis_is_reported_without_losing_other_ideas(self):
        self.fixture()
        self.put('04-Projects/thought-experiment-runs/alpha/analysis.json', '{')
        data = self.data()
        self.assertTrue(all({'section', 'error'} <= error.keys() for error in data['errors']))
        self.assertIn('idea:alpha', {error['section'] for error in data['errors']})
        by_id = {item['id']: item for item in data['ideas']}
        self.assertEqual(set(by_id), {'alpha', 'beta'})
        self.assertEqual(by_id['alpha']['papers'], [])
        self.assertEqual(by_id['alpha']['analysis'], '04-Projects/thought-experiment-runs/alpha/analysis.json')
        self.assertEqual(by_id['beta']['hypothesis'], 'Another hypothesis')

    def test_malformed_queue_is_reported_without_losing_ideas(self):
        self.fixture()
        self.put('04-Projects/research-todo/queue.json', '{')
        data = self.data()
        self.assertTrue(data['errors'])
        self.assertTrue(all({'section', 'error'} <= error.keys() for error in data['errors']))
        self.assertIn('todo_queue', {error['section'] for error in data['errors']})
        self.assertEqual({item['id'] for item in data['ideas']}, {'alpha', 'beta'})
        for item in data['ideas']:
            self.assertEqual((item['todoStatus'], item['todoTasks'], item['todoResults']), ('미기록', [], []))

    def test_non_list_queue_tasks_are_reported_once(self):
        self.fixture()
        for tasks in ({}, ''):
            with self.subTest(tasks=tasks):
                self.put('04-Projects/research-todo/queue.json', json.dumps({'tasks': tasks}))
                data = self.data()
                self.assertEqual(len(data['errors']), 1)
                self.assertEqual(data['errors'][0]['section'], 'todo_queue')
                self.assertEqual({item['id'] for item in data['ideas']}, {'alpha', 'beta'})
                for item in data['ideas']:
                    self.assertEqual((item['todoStatus'], item['todoTasks'], item['todoResults']),
                                     ('미기록', [], []))

    def test_mixed_queue_preserves_valid_tasks_and_reports_each_invalid_task(self):
        self.fixture()
        alpha = '05-Ideas/thought-experiments/alpha.md'
        beta = '05-Ideas/thought-experiments/beta.md'
        tasks = [
            {'idea_path': alpha, 'task_id': 'good-alpha', 'status': 'done', 'result_path': 'docs/result.md'},
            None,
            {'idea_path': alpha, 'task_id': 42, 'status': 'pending', 'result_path': 'docs/result.md'},
            {'idea_path': beta, 'task_id': 'good-beta', 'status': 'pending', 'result_path': ''},
            {'idea_path': beta, 'task_id': 'bad-beta', 'status': [], 'result_path': ''},
        ]
        self.put('04-Projects/research-todo/queue.json', json.dumps({'tasks': tasks}))
        data = self.data()
        self.assertEqual(len(data['errors']), 3)
        self.assertTrue(all(error['section'] == 'todo_queue' for error in data['errors']))
        for index in (1, 2, 4):
            self.assertTrue(any(f'tasks[{index}]' in error['error'] for error in data['errors']))
        by_id = {item['id']: item for item in data['ideas']}
        self.assertEqual(set(by_id), {'alpha', 'beta'})
        self.assertEqual((by_id['alpha']['todoStatus'], by_id['alpha']['todoTasks'],
                          by_id['alpha']['todoResults']), ('done', ['good-alpha'], ['docs/result.md']))
        self.assertEqual((by_id['beta']['todoStatus'], by_id['beta']['todoTasks'],
                          by_id['beta']['todoResults']), ('pending', ['good-beta'], ['']))

    def test_empty_and_guards(self):
        data = self.data()
        self.assertEqual(data['ideas'], [])
        self.assertEqual(data['errors'], [])
        status, _, body = self.request(headers={'Host': 'evil.example'})
        self.assertEqual((status, json.loads(body)['code']), (403, 'bad_host'))
        for method in ('POST', 'HEAD'):
            with self.subTest(method=method):
                status, headers, _ = self.request(method, self.headers if method == 'POST' else None,
                                                  b'{}' if method == 'POST' else None)
                self.assertEqual(status, 405)
                self.assertEqual(headers['Allow'], 'GET')


if __name__ == '__main__':
    unittest.main()
