"""Role resolution through the public status API, using only synthetic omp config."""
import http.client
import hashlib
import shutil
import json
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
import research_agent
from webui import llm
from webui import reviews, roles, server


class RoleResolutionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.queue = self.root / '04-Projects/review-queue/queue.json'
        self.queue.parent.mkdir(parents=True)
        self.config = {'task.agentModelOverrides': {}, 'modelRoles': {},
                       'retry.fallbackChains': {}, 'retry.modelFallback': True}
        self.ready = {'claude', 'codex', 'omp'}
        self.calls = []
        def config_get(argv, **kwargs):
            self.assertEqual(argv[:3], ['omp', 'config', 'get'])
            self.assertEqual(argv[-1], '--json')
            self.assertEqual(Path(kwargs['cwd']), self.root)
            self.calls.append(argv[3])
            return subprocess.CompletedProcess(argv, 0, stdout=json.dumps(self.config[argv[3]]), stderr='')
        self.config_get = config_get
        def probe(agent):
            return {'agent': agent, 'installed': True, 'authenticated': agent in self.ready,
                    'ready': agent in self.ready, 'reason': None if agent in self.ready else 'not authenticated'}
        for p in (patch.object(reviews, 'ROOT', self.root),
                  patch.object(reviews, 'QUEUE', self.queue),
                  patch.object(reviews, 'LIBRARY', self.root / '01-Papers/library'),
                  patch.object(research_agent, 'probe', side_effect=probe),
                  patch.object(research_agent, 'resolve', return_value={'agent': 'omp', 'ready': True}),
                  patch('subprocess.run', side_effect=config_get),
                  patch.object(reviews.shutil, 'which', return_value='/fake/tool')):
            p.start()
            self.addCleanup(p.stop)
        self.http = server.make_server(0, csrf_token='token')
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.thread.join, 3)
        self.addCleanup(self.http.shutdown)

    def status(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=3)
        try:
            conn.request('GET', '/api/status')
            response = conn.getresponse()
            payload = json.loads(response.read())
            self.assertEqual(response.status, 200, payload)
            return payload['review_roles']
        finally:
            conn.close()

    def post_verify(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=3)
        try:
            host = f'127.0.0.1:{self.http.server_port}'
            conn.request('POST', '/api/reviews/example/verify', b'{}', {
                'Origin': 'http://' + host, 'X-CSRF-Token': 'token',
                'Content-Type': 'application/json'})
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def paper(self, review=True):
        source = {'pdf_path': '01-Papers/pdfs/example.pdf',
                  'review_path': '01-Papers/reviews/other/example.md'}
        record = {'slug': 'example', 'paper_id': 'paper-1', 'title': 'Example',
                  'source': source, 'structured_review_status': 'complete'}
        library = self.root / '01-Papers/library'
        library.mkdir(parents=True)
        (library / 'example.json').write_text(json.dumps(record), encoding='utf-8')
        pdf = self.root / source['pdf_path']
        pdf.parent.mkdir(parents=True)
        pdf.write_bytes(b'%PDF-synthetic')
        if review:
            path = self.root / source['review_path']
            path.parent.mkdir(parents=True)
            path.write_text('# Review\n읽은 범위: 1\n', encoding='utf-8')

    def test_verify_missing_review_returns_conflict(self):
        self.paper(review=False)
        self.config['task.agentModelOverrides']['paper-verifier'] = 'openai-codex/a:high'
        status, payload = self.post_verify()
        self.assertEqual(status, 409, payload)
        self.assertTrue(payload['code'])

    def test_verify_unavailable_returns_503(self):
        self.paper()
        self.config['task.agentModelOverrides']['paper-verifier'] = 'openai-codex/a:high'
        self.ready.remove('codex')
        status, payload = self.post_verify()
        self.assertEqual(status, 503, payload)
        self.assertTrue(payload['code'])

    def test_verify_unconfigured_returns_conflict(self):
        self.paper()
        status, payload = self.post_verify()
        self.assertEqual(status, 409, payload)
        self.assertTrue(payload['code'])

    def test_verify_active_review_returns_conflict(self):
        self.paper()
        self.config['task.agentModelOverrides']['paper-verifier'] = 'openai-codex/a:high'
        self.queue.write_text(json.dumps({'jobs': [
            {'job_id': 'busy', 'status': 'running', 'slug': 'another'}]}), encoding='utf-8')
        status, payload = self.post_verify()
        self.assertEqual((status, payload['code']), (409, 'review_active'))

    def role_ping_events(self, first_events, role='paper-analyst'):
        self.config['task.agentModelOverrides']['paper-analyst'] = '@analysis'
        self.config['modelRoles']['analysis'] = 'anthropic/a:high, openai-codex/b:low'
        class FakeRun:
            def __init__(self, events):
                self._events = events
            def events(self):
                return iter(self._events)
            def cancel(self):
                pass
        calls = []
        def start(request, root):
            calls.append(request)
            return FakeRun(first_events if len(calls) == 1 else [
                {'type': 'start', 'agent': 'codex', 'model': 'b', 'session_id': None},
                {'type': 'result', 'text': 'OK', 'cost_usd': None, 'duration_ms': None, 'usage': None}])
        conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=3)
        try:
            host = f'127.0.0.1:{self.http.server_port}'
            with patch.object(llm, 'start', side_effect=start):
                conn.request('POST', '/api/jobs', json.dumps({'kind': 'agent.ping', 'role': role}),
                             {'Origin': 'http://' + host, 'X-CSRF-Token': 'token',
                              'Content-Type': 'application/json'})
                response = conn.getresponse()
                payload = json.loads(response.read())
                self.assertEqual(response.status, 202, payload)
                events = []
                deadline = time.monotonic() + 3
                for item in self.http.broker.events(payload['job']['job_id'], heartbeat_s=0.05):
                    if item is not None:
                        events.append(item[1])
                    if time.monotonic() >= deadline:
                        self.fail('role ping did not terminate')
            return calls, events
        finally:
            conn.close()

    def test_usage_limit_without_output_advances_with_retry_event(self):
        calls, events = self.role_ping_events([
            {'type': 'start', 'agent': 'claude', 'model': 'a', 'session_id': None},
            {'type': 'error', 'kind': 'usage_limit', 'message': 'quota exceeded', 'retryable': True}])
        self.assertEqual([(r.agent, r.model, r.effort) for r in calls],
                         [('claude', 'a', 'high'), ('codex', 'b', 'low')])
        retries = [e for e in events if e['type'] == 'retry']
        self.assertEqual(len(retries), 1)
        self.assertEqual((retries[0]['delay_ms'], retries[0]['reason'], retries[0]['next']),
                         (0, 'usage_limit', 'openai-codex/b:low'))
        self.assertEqual(events[-1]['type'], 'result')

    def test_unready_first_candidate_is_skipped(self):
        self.ready.remove('claude')
        calls, events = self.role_ping_events([
            {'type': 'start', 'agent': 'codex', 'model': 'b', 'session_id': None},
            {'type': 'result', 'text': 'OK', 'cost_usd': None, 'duration_ms': None, 'usage': None}])
        self.assertEqual([(r.agent, r.model) for r in calls], [('codex', 'b')])
        self.assertEqual(events[-1]['type'], 'result')

    def test_role_ping_unavailable_fails_without_substitution(self):
        self.ready.clear()
        calls, events = self.role_ping_events([])
        self.assertEqual(calls, [])
        self.assertEqual(events[-1]['type'], 'error')
        self.assertTrue(events[-1]['message'])

    def test_usage_limit_after_output_does_not_advance(self):
        for kind in ('text_delta', 'message'):
            with self.subTest(kind=kind):
                calls, events = self.role_ping_events([
                    {'type': 'start', 'agent': 'claude', 'model': 'a', 'session_id': None},
                    {'type': kind, 'text': 'partial'},
                    {'type': 'error', 'kind': 'usage_limit', 'message': 'quota exceeded', 'retryable': True}])
                self.assertEqual(len(calls), 1)
                self.assertFalse(any(e['type'] == 'retry' for e in events))
                self.assertEqual(events[-1]['type'], 'error')

    def test_non_usage_error_does_not_advance(self):
        calls, events = self.role_ping_events([
            {'type': 'start', 'agent': 'claude', 'model': 'a', 'session_id': None},
            {'type': 'error', 'kind': 'auth', 'message': 'authentication failed', 'retryable': False}])
        self.assertEqual(len(calls), 1)
        self.assertFalse(any(e['type'] == 'retry' for e in events))
        self.assertEqual(events[-1]['type'], 'error')

    def test_override_role_comma_candidates_fallback_and_runner_mapping(self):
        self.config['task.agentModelOverrides']['paper-analyst'] = '@analysis'
        self.config['modelRoles']['analysis'] = 'anthropic/a:high, openai-codex/b:low'
        self.config['retry.fallbackChains']['analysis'] = ['other/c:max']
        role = self.status()['generation']
        self.assertEqual((role['configured'], role['source'], role['role'], role['selected']),
                         (True, 'omp-config', 'analysis', 0))
        self.assertEqual([(c['selector'], c['provider'], c['model'], c['effort'], c['runner'])
                          for c in role['candidates']],
                         [('anthropic/a:high', 'anthropic', 'a', 'high', 'claude'),
                          ('openai-codex/b:low', 'openai-codex', 'b', 'low', 'codex'),
                          ('other/c:max', 'other', 'c', 'max', 'omp')])
        self.assertEqual(set(self.calls), set(self.config))

    def test_literal_selector_and_dropped_effort_note(self):
        self.config['task.agentModelOverrides']['paper-verifier'] = 'anthropic/a:inherit'
        role = self.status()['verification']
        self.assertTrue(role['configured'])
        self.assertIsNone(role['role'])
        self.assertEqual(role['candidates'][0]['selector'], 'anthropic/a:inherit')
        self.assertEqual(role['candidates'][0]['effort'], 'inherit')
        self.assertTrue(role['notes'], 'omitted CLI effort must be explained')

    def test_unconfigured_roles_have_no_candidates(self):
        roles = self.status()
        for name in ('generation', 'verification'):
            with self.subTest(role=name):
                self.assertFalse(roles[name]['configured'])
                self.assertEqual(roles[name]['candidates'], [])
                self.assertIsNone(roles[name]['selected'])

    def test_reader_resolution_and_readiness(self):
        from webui import reader
        role = roles.resolve('paper-reader', self.root)
        self.assertFalse(role['configured'])
        self.assertIn('미설정: 연결된 에이전트(.research-harness-agent.json)의 기본 모델로 답합니다.',
                      role['notes'])
        self.assertTrue(reader.reader_status(None)['ready'])
        self.config['task.agentModelOverrides']['paper-reader'] = 'anthropic/a:high'
        roles.clear_cache()
        status = reader.reader_status(None)
        self.assertTrue(status['ready'])
        self.assertTrue(status['configured'])
        self.assertEqual(status['selector'], 'anthropic/a:high')
        self.ready.remove('claude')
        roles.clear_cache()
        status = reader.reader_status(None)
        self.assertFalse(status['ready'])
        self.assertTrue(status['configured'])
        self.assertIsNone(status['selector'])

    def test_reader_config_error_fails_closed(self):
        from webui import reader
        roles.clear_cache()
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired(['omp'], 1)):
            status = reader.reader_status(None)
        self.assertFalse(status['ready'])
        self.assertIsNone(status['configured'])
        self.assertTrue(status['resolution']['error'])

    def test_status_contains_reader_role(self):
        conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=3)
        try:
            conn.request('GET', '/api/status')
            response = conn.getresponse()
            payload = json.loads(response.read())
            self.assertEqual(response.status, 200)
            self.assertEqual(payload['reader_role']['agent_name'], 'paper-reader')
        finally:
            conn.close()

    def test_ask_config_error_and_region_missing_tools(self):
        self.paper()
        self.config['task.agentModelOverrides']['paper-reader'] = 'anthropic/a:high'
        host = f'127.0.0.1:{self.http.server_port}'
        headers = {'Origin': 'http://' + host, 'X-CSRF-Token': 'token',
                   'Content-Type': 'application/json'}
        def ask(anchor):
            conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=3)
            try:
                conn.request('POST', '/api/papers/example/ask',
                             json.dumps({'question': '질문', 'thread_id': None, 'anchor': anchor}), headers)
                response = conn.getresponse()
                return response.status, json.loads(response.read())
            finally:
                conn.close()
        from webui import reader
        roles.clear_cache()
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired(['omp'], 1)), \
             patch.object(reader, 'page_texts', return_value=['page']):
            status, body = ask({'kind': 'page', 'page': 1})
        self.assertEqual((status, body['code']), (503, 'role_config_error'))
        roles.clear_cache()
        def which(name):
            return None if name == 'pdftoppm' else '/fake/' + name
        with patch.object(reader.shutil, 'which', side_effect=which), \
             patch.object(reader, 'page_texts', return_value=['page']):
            status, body = ask({'kind': 'region', 'page': 1, 'bbox': [0, 0, 1, 1]})
        self.assertEqual((status, body['code']), (503, 'pdf_tools_missing'))

    def test_configured_unready_reports_reason_without_substitution(self):
        self.config['task.agentModelOverrides']['paper-analyst'] = 'anthropic/a:high'
        self.ready.remove('claude')
        role = self.status()['generation']
        self.assertTrue(role['configured'])
        self.assertIsNone(role['selected'])
        self.assertFalse(role['candidates'][0]['ready'])
        self.assertTrue(role['candidates'][0]['reason'])

    def test_model_fallback_false_ignores_configured_chain(self):
        self.config['task.agentModelOverrides']['paper-verifier'] = '@verify'
        self.config['modelRoles']['verify'] = 'openai-codex/a:high'
        self.config['retry.fallbackChains']['verify'] = ['anthropic/b:high']
        self.config['retry.modelFallback'] = False
        self.assertEqual([c['selector'] for c in self.status()['verification']['candidates']],
                         ['openai-codex/a:high'])

    def test_config_read_failures_fail_closed_across_status_jobs_and_review(self):
        self.paper()
        record_path = self.root / '01-Papers/library/example.json'
        record = json.loads(record_path.read_text(encoding='utf-8'))
        record['structured_review_status'] = 'pending'
        record_path.write_text(json.dumps(record), encoding='utf-8')
        failures = (
            subprocess.TimeoutExpired(['omp'], 1),
            subprocess.CompletedProcess(['omp'], 1, stdout='', stderr='config unavailable'),
            subprocess.CompletedProcess(['omp'], 0, stdout='not json', stderr=''),
            subprocess.CompletedProcess(['omp'], 0, stdout='[]', stderr=''),
        )
        for failure in failures:
            with self.subTest(failure=str(failure)):
                roles.clear_cache()
                def broken(argv, **kwargs):
                    if isinstance(failure, Exception):
                        raise failure
                    return failure
                with patch('subprocess.run', side_effect=broken):
                    status = reviews.runtime_status()
                    self.assertFalse(status['ready'])
                    self.assertTrue(status['reason'])
                    for resolution in status['review_roles'].values():
                        self.assertIsNone(resolution['configured'])
                        self.assertTrue(resolution['error'])
                        self.assertEqual(resolution['candidates'], [])
                        self.assertIsNone(resolution['selected'])
                    code, payload = self.post_verify()
                    self.assertEqual((code, payload['code']), (503, 'role_config_error'))
                    for role in ('paper-analyst', 'paper-verifier'):
                        calls, events = self.role_ping_events([], role)
                        self.assertEqual(calls, [])
                        self.assertEqual(events[-1]['type'], 'error')
                        self.assertTrue(events[-1]['message'])
                    conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=3)
                    try:
                        host = f'127.0.0.1:{self.http.server_port}'
                        conn.request('POST', '/api/reviews', json.dumps({'slug': 'example'}),
                                     {'Origin': 'http://' + host, 'X-CSRF-Token': 'token',
                                      'Content-Type': 'application/json'})
                        response = conn.getresponse()
                        payload = json.loads(response.read())
                        self.assertEqual((response.status, payload['code']), (503, 'agent_unavailable'))
                    finally:
                        conn.close()

    def test_successful_empty_config_is_unconfigured_not_error(self):
        for resolution in self.status().values():
            self.assertIs(resolution['configured'], False)
            self.assertIsNone(resolution['error'])

    def test_worker_never_falls_back_when_role_config_cannot_be_read(self):
        self.paper(review=False)
        self.queue.write_text(json.dumps({'jobs': [
            {'job_id': 'job-1', 'slug': 'example', 'status': 'queued'}]}), encoding='utf-8')
        failed = {'agent_name': 'paper-analyst', 'configured': None, 'error': 'config read failed',
                  'candidates': [], 'selected': None, 'role': None}
        status = {'agent': 'omp', 'ready': True,
                  'review_roles': {'generation': failed, 'verification': failed}}
        with patch.object(reviews, 'runtime_status', return_value=status), \
                patch.object(reviews, 'review_command') as command:
            reviews.review_worker('job-1', 'example', 30)
        job = json.loads(self.queue.read_text(encoding='utf-8'))['jobs'][0]
        self.assertEqual(job['status'], 'failed')
        self.assertIn('config read failed', job['message'])
        command.assert_not_called()

    def generation_fallback_case(self, scenario):
        self.config['task.agentModelOverrides']['paper-analyst'] = 'openai-codex/a:high, anthropic/b:high'
        resolution = roles.resolve('paper-analyst', self.root)
        stage = self.root / 'stage'
        stage.mkdir()
        last = self.root / 'last-message'
        last.write_text('stale output from earlier run', encoding='utf-8')
        calls = []
        def command(stage_arg, last_arg, prompt, runner, **kwargs):
            return [runner]
        def process(argv, **kwargs):
            calls.append(argv[0])
            if len(calls) == 1:
                self.assertFalse(last.exists(), 'stale last-message must be cleared')
                if scenario == 'file':
                    (stage / 'partial-review').write_text('partial', encoding='utf-8')
                elif scenario == 'last_message':
                    last.write_text('partial review', encoding='utf-8')
                if scenario == 'prose_limit':
                    stdout = 'The paper evaluates a quota-based allocation policy.\n'
                    stderr = 'rate limit exceeded'
                elif scenario == 'prose_auth':
                    stdout = 'The paper studies rate limit configuration.\n'
                    stderr = 'authentication failed'
                else:
                    stdout = 'partial review text\nusage limit\n' if scenario == 'output' else ''
                    stderr = 'usage limit reached'
                return subprocess.CompletedProcess(argv, 1, stdout=stdout, stderr=stderr)
            return subprocess.CompletedProcess(argv, 0, stdout='complete', stderr='')
        with patch.object(reviews, 'review_command', side_effect=command), \
                patch('subprocess.run', side_effect=process):
            result, generation = reviews.run_generation(stage, last, 'prompt', {'agent': 'omp'},
                                                         resolution, 30)
        return calls, result, generation['attempts']

    def test_generation_limit_without_output_advances_and_records_attempts(self):
        calls, result, attempts = self.generation_fallback_case('empty')
        self.assertEqual(calls, ['codex', 'claude'])
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(attempts), 2)
        self.assertEqual((attempts[0]['error_kind'], attempts[0]['assistant_output'],
                          attempts[0]['staged_changes'], attempts[0]['advanced']),
                         ('usage_limit', False, False, True))
        self.assertEqual(attempts[1]['selector'], 'anthropic/b:high')

    def test_generation_limit_after_stdout_does_not_advance(self):
        calls, result, attempts = self.generation_fallback_case('output')
        self.assertEqual(calls, ['codex'])
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(attempts[0]['assistant_output'])
        self.assertFalse(attempts[0]['advanced'])

    def test_generation_prose_mentioning_quota_with_real_limit_does_not_advance(self):
        calls, result, attempts = self.generation_fallback_case('prose_limit')
        self.assertEqual(calls, ['codex'])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]['error_kind'], 'usage_limit')
        self.assertIs(attempts[0]['assistant_output'], True)
        self.assertIs(attempts[0]['staged_changes'], False)
        self.assertIs(attempts[0]['advanced'], False)

    def test_generation_prose_mentioning_rate_limit_with_auth_error_does_not_advance(self):
        calls, result, attempts = self.generation_fallback_case('prose_auth')
        self.assertEqual(calls, ['codex'])
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]['error_kind'], 'auth')
        self.assertIs(attempts[0]['assistant_output'], True)
        self.assertIs(attempts[0]['staged_changes'], False)
        self.assertIs(attempts[0]['advanced'], False)

    def test_generation_limit_after_last_message_does_not_advance(self):
        calls, _, attempts = self.generation_fallback_case('last_message')
        self.assertEqual(calls, ['codex'])
        self.assertTrue(attempts[0]['assistant_output'])
        self.assertFalse(attempts[0]['advanced'])

    def test_generation_limit_after_stage_change_does_not_advance(self):
        calls, _, attempts = self.generation_fallback_case('file')
        self.assertEqual(calls, ['codex'])
        self.assertTrue(attempts[0]['staged_changes'])
        self.assertFalse(attempts[0]['advanced'])

    def run_review_case(self, outcome):
        self.paper(review=False)
        record_path = self.root / '01-Papers/library/example.json'
        record = json.loads(record_path.read_text(encoding='utf-8'))
        record['structured_review_status'] = 'pending'
        record_path.write_text(json.dumps(record), encoding='utf-8')
        index = self.root / '01-Papers/index.md'
        index.write_text('# Papers\n', encoding='utf-8')
        definitions = self.root / '.omp/agents'
        definitions.mkdir(parents=True)
        for name in ('paper-analyst', 'paper-verifier'):
            shutil.copyfile(ROOT / '.omp/agents' / (name + '.md'), definitions / (name + '.md'))
        if outcome != 'analyst_unconfigured':
            self.config['task.agentModelOverrides']['paper-analyst'] = 'anthropic/a:high'
        if outcome not in ('skipped', 'analyst_unconfigured'):
            self.config['task.agentModelOverrides']['paper-verifier'] = 'openai-codex/b:high'
        self.queue.write_text(json.dumps({'jobs': [
            {'job_id': 'job-1', 'slug': 'example', 'status': 'queued'}]}), encoding='utf-8')
        review_name = record['source']['review_path']
        pdf_name = record['source']['pdf_path']
        invoked = []
        def generation_command(stage, last_message, prompt, runner, **kwargs):
            invoked.append(('generation', runner, kwargs, prompt))
            return ['fixture-generation']
        def verifier(candidate, stage, prompt, schema_path, timeout):
            invoked.append(('verification', candidate, prompt))
            self.assertFalse((self.root / review_name).exists(), 'verification must precede publish')
            self.assertTrue((stage / review_name).exists())
            self.assertIn(review_name, prompt)
            self.assertIn(pdf_name, prompt)
            self.assertTrue(Path(schema_path).is_file())
            if outcome == 'mutation':
                (stage / review_name).write_text('modified by verifier', encoding='utf-8')
            if outcome == 'pdf_modified':
                (stage / pdf_name).write_bytes(b'tampered PDF')
            elif outcome == 'pdf_deleted':
                (stage / pdf_name).unlink()
            elif outcome == 'review_deleted':
                (stage / review_name).unlink()
            elif outcome == 'review_directory':
                path = stage / review_name
                path.unlink()
                path.mkdir()
            elif outcome == 'review_symlink':
                path = stage / review_name
                path.unlink()
                path.symlink_to(stage / pdf_name)
            elif outcome == 'parent_symlink':
                parent = (stage / review_name).parent
                shutil.rmtree(parent)
                parent.symlink_to(stage / '01-Papers/pdfs', target_is_directory=True)
            result = {'status': 'issues' if outcome == 'issues' else 'passed',
                      'review_path': review_name,
                      'checked_claims': [] if outcome == 'empty_claims' else [
                          {'claim': 'claim', 'locator': 'p. 1',
                           'verdict': 'mismatch' if outcome == 'issues' else 'supported',
                           'note': 'checked'}],
                      'blocking_issues': ['mismatch'] if outcome == 'issues' else [],
                      'summary': 'checked'}
            text = 'not json' if outcome == 'invalid' else json.dumps(result)
            return iter([{'type': 'result', 'text': text, 'cost_usd': None,
                          'duration_ms': None, 'usage': None}])
        def run(argv, **kwargs):
            if argv[:3] == ['omp', 'config', 'get']:
                return self.config_get(argv, **kwargs)
            if argv[0] == 'fixture-generation':
                stage = Path(kwargs['cwd'])
                updated = dict(record, structured_review_status='complete',
                               review={f'axis-{i}': {'summary': 'summary', 'claims': ['claim']}
                                       for i in range(5)})
                (stage / '01-Papers/library/example.json').write_text(json.dumps(updated), encoding='utf-8')
                review = stage / review_name
                review.parent.mkdir(parents=True, exist_ok=True)
                review.write_text('# Review\n읽은 범위: 1\n', encoding='utf-8')
                (stage / '01-Papers/index.md').write_text('# Papers\nexample\n', encoding='utf-8')
                graph = stage / 'graphify-out/sync-state.json'
                graph.parent.mkdir(parents=True, exist_ok=True)
                graph.write_text(json.dumps({'sources': {'01-Papers/library/example.json':
                                                        {'status': 'success'}}}), encoding='utf-8')
            elif len(argv) > 1 and str(argv[1]).endswith('paper_catalog_html.py'):
                catalog = Path(kwargs['cwd']) / '100-views/paper-library.html'
                catalog.parent.mkdir(parents=True, exist_ok=True)
                catalog.write_text('catalog', encoding='utf-8')
            return subprocess.CompletedProcess(argv, 0, stdout='', stderr='')
        def clone(stage, pdf):
            shutil.copytree(self.root, stage)
        with patch('subprocess.run', side_effect=run), \
                patch.object(reviews, 'git_visible_files', return_value=None), \
                patch.object(reviews, 'review_command', side_effect=generation_command), \
                patch.object(reviews, 'run_verifier', side_effect=verifier), \
                patch.object(reviews, 'clone_review_workspace', side_effect=clone), \
                patch.object(reviews, 'refresh_wiki', return_value=([], None)):
            reviews.review_worker('job-1', 'example', 30)
        job = json.loads(self.queue.read_text(encoding='utf-8'))['jobs'][0]
        self.assertEqual(job['status'], 'completed', job.get('message'))
        self.assertTrue((self.root / review_name).is_file())
        if outcome == 'analyst_unconfigured':
            self.assertEqual(invoked[0][0:2], ('generation', 'omp'))
            self.assertIsNone(invoked[0][2].get('model'))
        else:
            self.assertEqual(invoked[0][0:2], ('generation', 'claude'))
            self.assertEqual((invoked[0][2]['model'], invoked[0][2]['effort']), ('a', 'high'))
        self.assertIn('.agents/skills/paper-review/SKILL.md', invoked[0][3])
        return job, invoked, self.root / '04-Projects/review-queue/verifications/example.json'

    def test_worker_verifies_before_publish_and_stores_blocking_issues(self):
        job, invoked, report_path = self.run_review_case('issues')
        self.assertEqual(invoked[1][0], 'verification')
        self.assertEqual(job['verification']['status'], 'issues')
        self.assertGreater(job['verification']['blocking_issues'], 0)
        report = json.loads(report_path.read_text(encoding='utf-8'))
        self.assertEqual(report['review_sha256'], hashlib.sha256(
            (self.root / '01-Papers/reviews/other/example.md').read_bytes()).hexdigest())
        self.assertEqual(report['pdf_sha256'], hashlib.sha256(
            (self.root / '01-Papers/pdfs/example.pdf').read_bytes()).hexdigest())

    def test_worker_empty_checked_claims_are_issues_with_summary_note(self):
        job, _, report_path = self.run_review_case('empty_claims')
        self.assertEqual(job['verification']['status'], 'issues')
        self.assertEqual(job['verification']['note'], '검증된 주장이 없음')
        self.assertEqual(json.loads(report_path.read_text(encoding='utf-8'))['result']['checked_claims'], [])

    def test_worker_verifier_modification_is_error_but_publishes(self):
        job, _, _ = self.run_review_case('mutation')
        self.assertEqual(job['verification']['status'], 'error')

    def assert_verifier_tampering_preserves_published_review_and_hashes(self, outcome):
        job, _, report_path = self.run_review_case(outcome)
        self.assertEqual(job['verification']['status'], 'error')
        report = json.loads(report_path.read_text(encoding='utf-8'))
        self.assertIn('verifier changed staged files', report['error'])
        original_review = '# Review\n읽은 범위: 1\n'.encode()
        self.assertEqual((self.root / '01-Papers/reviews/other/example.md').read_bytes(), original_review)
        self.assertEqual(report['review_sha256'], hashlib.sha256(original_review).hexdigest())
        self.assertEqual(report['pdf_sha256'], hashlib.sha256(b'%PDF-synthetic').hexdigest())

    def test_verifier_pdf_modification_is_detected_and_original_hash_preserved(self):
        self.assert_verifier_tampering_preserves_published_review_and_hashes('pdf_modified')

    def test_verifier_pdf_deletion_is_detected_and_original_hash_preserved(self):
        self.assert_verifier_tampering_preserves_published_review_and_hashes('pdf_deleted')

    def test_verifier_review_deletion_does_not_destroy_published_review(self):
        self.assert_verifier_tampering_preserves_published_review_and_hashes('review_deleted')

    def test_verifier_replacing_review_with_directory_does_not_destroy_review(self):
        self.assert_verifier_tampering_preserves_published_review_and_hashes('review_directory')

    def test_verifier_replacing_review_with_symlink_does_not_destroy_review(self):
        self.assert_verifier_tampering_preserves_published_review_and_hashes('review_symlink')

    def test_verifier_replacing_review_parent_with_symlink_does_not_destroy_review(self):
        self.assert_verifier_tampering_preserves_published_review_and_hashes('parent_symlink')

    def test_worker_invalid_verifier_json_is_error_but_publishes(self):
        job, _, _ = self.run_review_case('invalid')
        self.assertEqual(job['verification']['status'], 'error')

    def test_worker_unconfigured_verifier_is_skipped_without_report(self):
        job, invoked, report = self.run_review_case('skipped')
        self.assertEqual(job['verification']['status'], 'skipped')
        self.assertEqual(len(invoked), 1)
        self.assertFalse(report.exists())

    def test_worker_unconfigured_analyst_uses_connected_agent_default(self):
        job, invoked, _ = self.run_review_case('analyst_unconfigured')
        self.assertEqual(job['verification']['status'], 'skipped')
        self.assertEqual(len(invoked), 1)

    def test_verify_endpoint_success_records_report_and_queue_job(self):
        self.paper()
        definitions = self.root / '.omp/agents'
        definitions.mkdir(parents=True)
        shutil.copyfile(ROOT / '.omp/agents/paper-verifier.md', definitions / 'paper-verifier.md')
        self.config['task.agentModelOverrides']['paper-verifier'] = 'openai-codex/b:high'
        review = '01-Papers/reviews/other/example.md'
        result = {'status': 'passed', 'review_path': review,
                  'checked_claims': [{'claim': 'claim', 'locator': 'p. 1',
                                      'verdict': 'supported', 'note': 'checked'}],
                  'blocking_issues': [], 'summary': 'checked'}
        def verify(candidate, stage, prompt, schema_path, timeout):
            self.assertTrue((stage / review).exists())
            return iter([{'type': 'result', 'text': json.dumps(result), 'cost_usd': None,
                          'duration_ms': None, 'usage': None}])
        with patch.object(reviews, 'run_verifier', side_effect=verify), \
                patch.object(reviews, 'git_visible_files', return_value=None), \
                patch.object(reviews, 'clone_review_workspace',
                             side_effect=lambda stage, pdf: shutil.copytree(self.root, stage)):
            status, payload = self.post_verify()
            self.assertEqual(status, 202, payload)
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                jobs = json.loads(self.queue.read_text(encoding='utf-8'))['jobs']
                job = next(item for item in jobs if item['job_id'] == payload['job']['job_id'])
                if job['status'] in ('completed', 'failed'):
                    break
                threading.Event().wait(0.01)
            self.assertEqual(job['status'], 'completed', job.get('message'))
        self.assertEqual(job['kind'], 'verify')
        self.assertEqual(job['verification']['status'], 'passed')
        report = self.root / '04-Projects/review-queue/verifications/example.json'
        self.assertTrue(report.is_file())
        conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=3)
        try:
            conn.request('GET', '/api/reviews/example')
            response = conn.getresponse()
            payload = json.loads(response.read())
            self.assertEqual(response.status, 200, payload)
            self.assertIn('verification', payload)
        finally:
            conn.close()
