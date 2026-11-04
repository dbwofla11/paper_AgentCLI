import http.client
import json
import os
import signal
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.scripts/bin'))
import harness_dashboard as dashboard
import paper_catalog_html as catalog
import research_workflow
from webui import reviews, server


class FakeProcess:
    """A real pipe, but no child process: safe for the recursive suite check."""
    pid = 912345

    def __init__(self, lines=(), code=0, hold=False):
        read_fd, self._write_fd = os.pipe()
        self.stdout = os.fdopen(read_fd, 'r', encoding='utf-8')
        self.code = code
        self.returncode = None
        self.release = threading.Event()
        self.started = threading.Event()
        self.lines = lines
        self.hold = hold
        self.writer = threading.Thread(target=self._write, daemon=True)
        self.writer.start()

    def _write(self):
        try:
            for line in self.lines:
                os.write(self._write_fd, line.encode())
            self.started.set()
            if self.hold:
                self.release.wait(15)
        finally:
            os.close(self._write_fd)
            self.returncode = self.code

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self.writer.join(timeout)
        if self.writer.is_alive():
            raise subprocess.TimeoutExpired('fake', timeout)
        return self.returncode

    def terminate(self):
        self.release.set()

    def kill(self):
        self.release.set()


class WebUITestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library = self.root / '01-Papers/library'
        self.library.mkdir(parents=True)
        for name, value in [('ROOT', self.root), ('LIBRARY', self.library)]:
            p = patch.object(reviews, name, value)
            p.start()
            self.addCleanup(p.stop)
        self.server = server.make_server(0, csrf_token='test-token')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.closed = False
        self.addCleanup(self.close_server)
        self.headers = {'Origin': f'http://127.0.0.1:{self.server.server_port}',
                        'X-CSRF-Token': 'test-token', 'Content-Type': 'application/json'}

    def close_server(self):
        if not self.closed:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(3)
            self.closed = True

    def request(self, method, path, body=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            response = conn.getresponse()
            return response.status, response.headers, response.read()
        finally:
            conn.close()

    def post(self, payload, path='/api/harness/checks', headers=None):
        return self.request('POST', path, json.dumps(payload).encode(), headers or self.headers)

    def events(self, job):
        events, heartbeats = [], 0
        for item in self.server.broker.events(job['job_id'], heartbeat_s=0.05):
            if item is None:
                heartbeats += 1
                if heartbeats > 120:
                    self.fail('event stream did not terminate')
            else:
                events.append(item)
            if len(events) > 1000:
                self.fail('event stream exceeded expected length')
        return events

    def put(self, path, content):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
        return target


class PaperContractTests(WebUITestCase):
    def test_papers_fields_urls_review_states_fallback_order_and_errors(self):
        cases = [
            ('2026-magne-nitrogen-generalist-gaming-agents', '', 'https://example.org/a', 'complete', True, True),
            ('2025-fallback-name', '', 'javascript:alert(1)', 'complete', False, False),
            ('2024-partial', 'Partial', 'https://', 'partial', True, False),
            ('2023-invalid', 'Invalid', 'http:// /x', 'complete', True, False),
        ]
        for slug, title, url, status, review, pdf in cases:
            source = {'urls': [url], 'review_path': f'01-Papers/reviews/{slug}.md'}
            if pdf:
                source['pdf_path'] = f'01-Papers/pdfs/{slug}.pdf'
                self.put(source['pdf_path'], '%PDF-1.4')
            if review:
                self.put(source['review_path'], '# Review')
            self.put(f'01-Papers/library/{slug}.json', json.dumps({
                'slug': slug, 'title': title, 'year': int(slug[:4]), 'source': source,
                'structured_review_status': status, 'abstract': 42 if slug == '2023-invalid' else 'abstract', 'category': 'other'}))
        self.put('01-Papers/library/broken.json', '{')
        with patch.object(catalog, 'PDFINFO', None):
            status, _, body = self.request('GET', '/api/papers')
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data['labels'], catalog.LABELS)
        self.assertEqual(data['queued_statuses'], catalog.QUEUED_STATUSES)
        self.assertEqual(len(data['errors']), 1)
        self.assertIn('broken.json', data['errors'][0]['file'])
        papers = data['papers']
        self.assertEqual([p['slug'] for p in papers], [row[0] for row in cases])
        old_keys = {'slug', 'title', 'authors', 'year', 'venue', 'category', 'topics',
                    'one_line_summary', 'reading_status', 'structured_review_status',
                    'has_pdf', 'has_review', 'verification', 'threads'}
        for p in papers:
            self.assertTrue(old_keys <= p.keys())
            self.assertIsInstance(p['display_title'], str)
            self.assertTrue(p['display_title'])
            self.assertTrue(p['abstract'] is None or isinstance(p['abstract'], str))
            self.assertIsInstance(p['review_needed'], bool)
        self.assertEqual([p['source_url'] for p in papers], ['https://example.org/a', None, None, None])
        self.assertEqual([p['review_needed'] for p in papers], [False, True, True, False])
        self.assertEqual(papers[-1]['abstract'], None)
        self.assertEqual(papers[0]['display_title'], catalog.PDF_TITLE_FALLBACKS[cases[0][0]])
        self.assertEqual(papers[1]['display_title'], '2025 Fallback Name')

    def test_malformed_source_url_does_not_break_paper_list(self):
        for slug, urls in (
            ('2026-valid-after-invalid', ['https://[', 'https://ok.example/x']),
            ('2025-invalid-only', ['https://[']),
        ):
            self.put(f'01-Papers/library/{slug}.json', json.dumps({
                'slug': slug, 'title': slug, 'source': {'urls': urls},
            }))
        status, _, body = self.request('GET', '/api/papers')
        self.assertEqual(status, 200)
        papers = {p['slug']: p for p in json.loads(body)['papers']}
        self.assertEqual(papers['2026-valid-after-invalid']['source_url'], 'https://ok.example/x')
        self.assertIsNone(papers['2025-invalid-only']['source_url'])

    def test_catalog_generated_labels_have_no_placeholders(self):
        output = self.root / '100-views/paper-library.html'
        with patch.object(catalog, 'ROOT', self.root), patch.object(catalog, 'LIBRARY', self.library), \
             patch.object(catalog, 'OUTPUT', output), patch.object(sys, 'argv', ['paper_catalog_html.py']):
            catalog.main()
        html = output.read_text(encoding='utf-8')
        self.assertNotIn('__LABELS__', html)
        self.assertNotIn('__QUEUED__', html)
        match = re.search(r'const labels\s*=\s*(\{[^\n;]*\})\s*;', html)
        self.assertIsNotNone(match, 'generated labels JSON missing')
        self.assertEqual(json.loads(match.group(1)), {**catalog.LABELS['category'], **catalog.LABELS['reading_status']})
        queued = re.search(r'(\[[^\n;]*?\])\.includes\(p\.reading_status\)', html)
        self.assertIsNotNone(queued, 'generated queued statuses JSON missing')
        self.assertEqual(json.loads(queued.group(1)), catalog.QUEUED_STATUSES)


class HarnessGetTests(WebUITestCase):
    def fixture(self):
        paths = [{'id': 'fixture', 'title': 'Fixture', 'steps': [
            {'skill': 'x', 'label': 'Step', 'input': 'in', 'output': 'out', 'condition': 'yes',
             'source': 'docs/evidence.md'}]}]
        self.put('.scripts/docs/research-workflow-map.json', json.dumps({'paths': paths}))
        self.put('.agents/skills/x/SKILL.md', '---\ndescription: Fixture\n---\n# X\n\nInstructions')
        self.put('.omp/agents/x.md', '---\ndescription: Agent\n---\n')
        self.put('04-Projects/validation/personas/a.md', '# Persona')
        self.put('docs/evidence.md', 'evidence')
        self.put('graphify-out/sync-state.json', json.dumps({'sources': {'a': {'status': 'pending'},
                                                                            'b': {'status': 'success'}}}))
        return paths

    def get_data(self):
        status, _, body = self.request('GET', '/api/harness')
        self.assertEqual(status, 200)
        return json.loads(body)

    def test_shape_inventory_graphify_and_security_links(self):
        paths = self.fixture()
        data = self.get_data()
        self.assertTrue({'guide', 'routing', 'skill_links', 'omp_agents', 'personas', 'validators',
                         'tests_path', 'graphify', 'checks', 'links', 'hrefs', 'errors'} <= data.keys())
        self.assertEqual(data['guide']['paths'], paths)
        self.assertEqual([s['name'] for s in data['guide']['skills']], ['x'])
        self.assertEqual([s['name'] for s in data['skill_links']], ['x'])
        self.assertEqual(data['routing'], [{'stage': stage, **value} for stage, value in research_workflow.WORKFLOW.items()])
        self.assertEqual([a['name'] for a in data['omp_agents']], ['x'])
        self.assertEqual([p['name'] for p in data['personas']], ['a'])
        self.assertEqual(data['graphify']['pending'], 1)
        self.assertEqual(data['graphify']['total'], 2)
        self.assertEqual(data['hrefs']['.agents/skills/x/SKILL.md'], '/.agents/skills/x/SKILL.md')
        self.assertIsNone(data['hrefs']['.omp/agents/x.md'])
        referenced = set(data['links'].values()) | {data['tests_path'], data['graphify']['path']}
        referenced |= {x['path'] for key in ('omp_agents', 'personas', 'validators') for x in data[key]}
        referenced |= {x['source'] for x in data['guide']['skills']}
        referenced |= {step['source'] for path in paths for step in path['steps'] if 'source' in step}
        self.assertTrue(referenced <= data['hrefs'].keys())

    def test_skill_symlinks_cannot_disclose_disallowed_targets(self):
        self.fixture()
        skill = self.root / '.agents/skills/x/SKILL.md'
        skill.unlink()
        sensitive = self.put('.omp/config.yml', 'SENTINEL-SECRET')
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / 'outside.md'
            external.write_text('SENTINEL-SECRET', encoding='utf-8')
            (self.root / '.omp/agents/y.md').symlink_to(external)
            for target in (sensitive, external):
                with self.subTest(target=target):
                    skill.symlink_to(target)
                    try:
                        status, _, body = self.request('GET', '/api/harness')
                        self.assertEqual(status, 200)
                        self.assertNotIn(b'SENTINEL-SECRET', body)
                        data = json.loads(body)
                        matching = [entry for entry in data['guide']['skills'] if entry['name'] == 'x']
                        self.assertEqual(len(matching), 1)
                        self.assertIsNone(matching[0]['instructions'])
                        agent = next(entry for entry in data['omp_agents'] if entry['name'] == 'y')
                        self.assertIsNone(agent['description'])
                    finally:
                        skill.unlink()

    def test_malformed_graphify_is_isolated(self):
        self.fixture()
        self.put('graphify-out/sync-state.json', '{')
        data = self.get_data()
        self.assertTrue(data['graphify']['error'])
        self.assertTrue(data['guide']['paths'])
        self.assertTrue(data['routing'])

    def test_host_and_method_guards(self):
        status, _, body = self.request('GET', '/api/harness', headers={'Host': 'evil.example'})
        self.assertEqual((status, json.loads(body)['code']), (403, 'bad_host'))
        for method in ('POST', 'HEAD'):
            status, headers, _ = self.request(method, '/api/harness', b'{}' if method == 'POST' else None,
                                               self.headers if method == 'POST' else None)
            self.assertEqual(status, 405)
            self.assertIn('GET', headers['Allow'])


class HarnessChecksTests(WebUITestCase):
    @patch('webui.server.subprocess.Popen', side_effect=AssertionError('guard allowed process launch'))
    def test_guards_validation_and_jobs_boundary(self, popen):
        for headers, status, code in [
            ({k: v for k, v in self.headers.items() if k != 'X-CSRF-Token'}, 403, 'bad_csrf'),
            ({**self.headers, 'Origin': 'http://evil.example'}, 403, 'bad_origin'),
            ({**self.headers, 'Content-Type': 'text/plain'}, 415, 'unsupported_media_type')]:
            actual, _, body = self.post({'check': 'verify'}, headers=headers)
            self.assertEqual((actual, json.loads(body)['code']), (status, code))
        for payload in ({}, {'check': 'x'}, {'check': 1}, {'check': ['verify']}):
            status, _, body = self.post(payload)
            self.assertEqual((status, json.loads(body)['code']), (400, 'bad_request'))
            self.assertIn('check must be one of: verify, tests', json.loads(body)['error'])
        status, _, _ = self.request('POST', '/api/harness/checks', b'x' * 65537, self.headers)
        self.assertEqual(status, 413)
        status, _, _ = self.post({'kind': 'harness.verify'}, '/api/jobs')
        self.assertEqual(status, 400)
        self.server.broker.closing.set()
        status, _, body = self.post({'check': 'verify'})
        self.assertEqual((status, json.loads(body)['code']), (503, 'shutting_down'))
        popen.assert_not_called()

    def test_success_stream_and_fixed_argv_for_both_checks(self):
        for check in ('verify', 'tests'):
            with self.subTest(check=check):
                process = FakeProcess(['first line\n', 'second line\n'])
                with patch('webui.server.subprocess.Popen', return_value=process) as popen:
                    status, _, body = self.post({'check': check})
                    self.assertEqual(status, 202)
                    job = json.loads(body)['job']
                    self.assertEqual((job['kind'], job['agent']), (f'harness.{check}', None))
                    self.assertNotIn('role', job)
                    self.assertNotIn('slug', job)
                    events = self.events(job)
                self.assertEqual([seq for seq, _ in events], list(range(1, len(events) + 1)))
                deltas = [event['text'] for _, event in events if event['type'] == 'text_delta']
                self.assertEqual(deltas, ['first line\n', 'second line\n'])
                terminal = events[-1][1]
                self.assertEqual((terminal['type'], terminal['text']), ('result', ''.join(deltas)))
                self.assertIsNone(terminal['cost_usd'])
                self.assertIsNone(terminal['usage'])
                self.assertIsInstance(terminal['duration_ms'], int)
                args, kwargs = popen.call_args
                self.assertEqual(args[0], dashboard.check_command(check, self.root))
                self.assertEqual(Path(kwargs['cwd']), self.root)
                self.assertEqual(kwargs['stdout'], subprocess.PIPE)
                self.assertEqual(kwargs['stderr'], subprocess.STDOUT)
                self.assertTrue(kwargs['text'])
                self.assertTrue(kwargs['start_new_session'])
                self.assertEqual(kwargs['env']['PYTHONUNBUFFERED'], '1')

    def test_process_failure_reports_exit_and_output(self):
        process = FakeProcess(['failure details\n'], code=1)
        with patch('webui.server.subprocess.Popen', return_value=process):
            status, _, body = self.post({'check': 'verify'})
            self.assertEqual(status, 202)
            terminal = self.events(json.loads(body)['job'])[-1][1]
        self.assertEqual((terminal['type'], terminal['kind'], terminal['retryable']), ('error', 'process', True))
        self.assertIn('exit 1', terminal['message'])
        self.assertIn('failure details', terminal['message'])

    def test_single_flight_and_cancel_terminate_process_group(self):
        process = FakeProcess(['running\n'], hold=True)
        def killpg(pid, sig):
            self.assertEqual(pid, process.pid)
            if sig == 0 and process.release.is_set():
                raise ProcessLookupError()
            if sig in (signal.SIGTERM, signal.SIGKILL):
                process.release.set()
        with patch('webui.server.subprocess.Popen', return_value=process), \
             patch('webui.server.os.killpg', side_effect=killpg) as kill:
            status, _, body = self.post({'check': 'tests'})
            self.assertEqual(status, 202)
            job = json.loads(body)['job']
            self.assertTrue(process.started.wait(2))
            status, _, body = self.post({'check': 'verify'})
            self.assertEqual((status, json.loads(body)['code']), (409, 'check_active'))
            self.assertTrue(self.server.broker.cancel(job['job_id']))
            self.assertEqual(self.events(job)[-1][1]['type'], 'cancelled')
            self.assertTrue(kill.called)
            self.assertEqual(kill.call_args_list[0].args, (process.pid, signal.SIGTERM))

    def test_timeout_terminates_process_group(self):
        process = FakeProcess(hold=True)
        def killpg(pid, sig):
            if sig == 0 and process.release.is_set():
                raise ProcessLookupError()
            if sig in (signal.SIGTERM, signal.SIGKILL):
                process.release.set()
        with patch('webui.server.subprocess.Popen', return_value=process), \
             patch('webui.server.os.killpg', side_effect=killpg) as kill, \
             patch.dict(server.HARNESS_CHECK_TIMEOUT_S, {'verify': 0.3}):
            status, _, body = self.post({'check': 'verify'})
            self.assertEqual(status, 202)
            terminal = self.events(json.loads(body)['job'])[-1][1]
            self.assertEqual((terminal['type'], terminal['kind']), ('error', 'timeout'))
            self.assertTrue(kill.called)

    def test_cancel_and_timeout_kill_lingering_children_before_next_check(self):
        for mode in ('cancel', 'timeout'):
            with self.subTest(mode=mode):
                process = FakeProcess(hold=True)
                next_process = FakeProcess(['next\n'])
                kill_entered = threading.Event()
                allow_kill = threading.Event()
                group_alive = threading.Event()
                group_alive.set()
                signals = []

                def killpg(pid, sig):
                    self.assertEqual(pid, process.pid)
                    signals.append(sig)
                    if sig == 0:
                        if not group_alive.is_set():
                            raise ProcessLookupError()
                    elif sig == signal.SIGTERM:
                        # The leader exits and closes stdout, but its child ignores TERM.
                        process.release.set()
                    elif sig == signal.SIGKILL:
                        kill_entered.set()
                        if not allow_kill.wait(3):
                            raise AssertionError('test did not release SIGKILL')
                        group_alive.clear()

                try:
                    with patch('webui.server.subprocess.Popen', side_effect=[process, next_process]), \
                         patch('webui.server.os.killpg', side_effect=killpg), \
                         patch.object(server, 'HARNESS_KILL_GRACE_S', 0.15), \
                         patch.dict(server.HARNESS_CHECK_TIMEOUT_S, {'verify': 0.3}):
                        status, _, body = self.post({'check': 'verify'})
                        self.assertEqual(status, 202)
                        job = json.loads(body)['job']
                        self.assertTrue(process.started.wait(2))
                        if mode == 'cancel':
                            self.assertTrue(self.server.broker.cancel(job['job_id']))
                        self.assertTrue(kill_entered.wait(2), 'group was not escalated to SIGKILL')
                        self.assertTrue(group_alive.is_set())
                        self.assertIn(self.server.broker.get(job['job_id'])['status'], ('queued', 'running'))
                        status, _, body = self.post({'check': 'tests'})
                        self.assertEqual((status, json.loads(body)['code']), (409, 'check_active'))
                        allow_kill.set()
                        terminal = self.events(job)[-1][1]
                        self.assertFalse(group_alive.is_set())
                        self.assertIn(signal.SIGTERM, signals)
                        self.assertIn(signal.SIGKILL, signals)
                        self.assertLess(signals.index(signal.SIGTERM), signals.index(signal.SIGKILL))
                        if mode == 'cancel':
                            self.assertEqual(terminal['type'], 'cancelled')
                        else:
                            self.assertEqual((terminal['type'], terminal['kind']), ('error', 'timeout'))
                        status, _, body = self.post({'check': 'tests'})
                        self.assertEqual(status, 202)
                        self.assertEqual(self.events(json.loads(body)['job'])[-1][1]['type'], 'result')
                finally:
                    allow_kill.set()
                    process.release.set()

    def test_large_single_line_and_no_newline_output_are_bounded(self):
        limit = 256 * 1024
        for suffix in ('\n', ''):
            with self.subTest(suffix=repr(suffix)):
                text = ('prefix-' * 50000) + 'TAIL' + suffix
                process = FakeProcess([text])
                with patch('webui.server.subprocess.Popen', return_value=process):
                    status, _, body = self.post({'check': 'verify'})
                    self.assertEqual(status, 202)
                    job = json.loads(body)['job']
                    self.assertTrue(self.server.broker.wait_finished([job['job_id']], timeout=5))
                    events = self.events(job)
                deltas = [e['text'] for _, e in events if e['type'] == 'text_delta']
                self.assertTrue(deltas)
                self.assertTrue(all(len(delta.encode('utf-8')) <= 8 * 1024 for delta in deltas))
                self.assertLessEqual(sum(len(delta.encode('utf-8')) for delta in deltas), limit)
                self.assertEqual(events[-1][1]['type'], 'result')
                self.assertEqual(events[-1][1]['text'], text.encode('utf-8')[-limit:].decode('utf-8'))

    def test_server_close_cancels_running_check_within_five_seconds(self):
        process = FakeProcess(hold=True)
        def killpg(pid, sig):
            if sig == 0 and process.release.is_set():
                raise ProcessLookupError()
            if sig in (signal.SIGTERM, signal.SIGKILL):
                process.release.set()
        with patch('webui.server.subprocess.Popen', return_value=process), \
             patch('webui.server.os.killpg', side_effect=killpg) as kill:
            status, _, body = self.post({'check': 'verify'})
            self.assertEqual(status, 202)
            job = json.loads(body)['job']
            self.assertTrue(process.started.wait(2))
            self.server.shutdown()
            started = time.monotonic()
            self.server.server_close()
            self.assertLessEqual(time.monotonic() - started, 5.0)
            self.closed = True
            self.thread.join(2)
            self.assertEqual(self.events(job)[-1][1]['type'], 'cancelled')
            self.assertTrue(kill.called)


class StaticRegressionTests(unittest.TestCase):
    def test_dashboard_headings_and_cross_links(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / '100-views/harness-dashboard.html'
            with patch.object(dashboard, 'ROOT', root), patch.object(dashboard, 'OUTPUT', output), \
                 patch.object(dashboard, 'validate', return_value=('PASS', 'ok')):
                dashboard.main(run_tests=False)
            html = output.read_text(encoding='utf-8')
            for heading in ('어떤 스킬을 언제 쓰나요?', '스킬 설명과 사용 위치', '하네스 구조 검사',
                            '현재 라우팅', '공통 스킬 정본 및 호스트 연결', 'omp 에이전트', '페르소나',
                            '검증기와 테스트', 'Graphify 동기화', '관리 범위'):
                self.assertIn(heading, html)
            self.assertIn('paper-library.html', html)
            self.assertIn('thought-experiments.html', html)


if __name__ == '__main__':
    unittest.main()
