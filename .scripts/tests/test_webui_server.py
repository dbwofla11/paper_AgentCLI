import http.client
import json
import sys
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.scripts/bin'))
from webui import server, reviews
import research_agent


class ServerSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / '100-views/webui').mkdir(parents=True)
        (self.root / '100-views/webui/index.html').write_text('webui')
        (self.root / '100-views/legacy.html').write_text('legacy')
        (self.root / '100-views/empty').mkdir()
        (self.root / '100-views/.git').mkdir()
        (self.root / '100-views/.git/config').write_text('private')
        (self.root / '100-views/.env.local').write_text('private')
        (self.root / '100-views/credentials.json').write_text('private')
        (self.root / '100-views/.research-harness-agent.json').write_text('private')
        self.outside = tempfile.TemporaryDirectory()
        (Path(self.outside.name) / 'secret').write_text('secret')
        (self.root / '100-views/link').symlink_to(Path(self.outside.name) / 'secret')
        self.root_patch = patch.object(reviews, 'ROOT', self.root)
        self.root_patch.start()
        self.server = server.make_server(0, csrf_token='test-token')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = f'127.0.0.1:{self.server.server_port}'
        self.origin = 'http://' + self.host

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)
        self.root_patch.stop()
        self.outside.cleanup()
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        connection.request(method, path, body=body, headers=headers or {})
        response = connection.getresponse()
        data = response.read()
        headers = response.headers
        status = response.status
        connection.close()
        self.assertNotIn('Access-Control-Allow-Origin', headers)
        return status, headers, data

    def post(self, headers, body=b'{}', path='/api/jobs'):
        return self.request('POST', path, body, headers)

    def test_host_guards_api_static_sse_and_accepts_localhost(self):
        for path in ('/api/session', '/100-views/webui/index.html', '/api/jobs/unknown/events'):
            with self.subTest(path=path):
                status, _, data = self.request('GET', path, headers={'Host': 'evil.example'})
                self.assertEqual(status, 403)
                self.assertEqual(json.loads(data)['code'], 'bad_host')
        status, _, _ = self.request('GET', '/api/session', headers={'Host': f'localhost:{self.server.server_port}'})
        self.assertEqual(status, 200)
        self.assertEqual(self.server.server_address[0], '127.0.0.1')

    def test_unsupported_methods_still_check_host_then_return_json_405(self):
        for method in ('TRACE', 'CUSTOM'):
            with self.subTest(method=method):
                status, _, data = self.request(method, '/api/session', headers={'Host': 'evil.example'})
                self.assertEqual((status, json.loads(data)['code']), (403, 'bad_host'))
                status, _, data = self.request(method, '/api/session')
                self.assertEqual((status, json.loads(data)['code']), (405, 'method_not_allowed'))

    def test_post_guards_and_body_limits(self):
        valid = {'Origin': self.origin, 'X-CSRF-Token': 'test-token', 'Content-Type': 'application/json'}
        cases = [({k: v for k, v in valid.items() if k != 'Origin'}, 403, 'bad_origin'),
                 ({**valid, 'Origin': 'http://evil.example'}, 403, 'bad_origin'),
                 ({**valid, 'Sec-Fetch-Site': 'cross-site'}, 403, 'bad_origin'),
                 ({k: v for k, v in valid.items() if k != 'X-CSRF-Token'}, 403, 'bad_csrf'),
                 ({**valid, 'X-CSRF-Token': 'wrong'}, 403, 'bad_csrf'),
                 ({**valid, 'Content-Type': 'text/plain'}, 415, None)]
        for headers, expected, code in cases:
            with self.subTest(headers=headers):
                status, _, data = self.post(headers)
                self.assertEqual(status, expected)
                if code:
                    self.assertEqual(json.loads(data)['code'], code)
        self.assertEqual(self.post(valid, b'x' * 65537)[0], 413)
        self.assertEqual(self.post(valid, b'x' * 4097, '/api/reviews')[0], 413)
        status, _, data = self.post(valid, b'{')
        self.assertEqual((status, json.loads(data)['code']), (400, 'bad_json'))
        status, _, data = self.post(valid, b'')
        self.assertEqual((status, json.loads(data)['code']), (400, 'bad_request'))
        status, _, data = self.post({**valid, 'Transfer-Encoding': 'chunked'}, b'')
        self.assertEqual((status, json.loads(data)['code']), (411, 'length_required'))

    def test_static_traversal_and_private_paths_are_not_served(self):
        for path in ('/100-views/%2e%2e/secret', '/100-views/%00x', '//etc/passwd',
                     '/100-views/link', '/.research-harness-agent.json', '/.git/config',
                     '/100-views/.git/config', '/100-views/.env.local',
                     '/100-views/credentials.json', '/100-views/.research-harness-agent.json',
                     '/100-views/empty/', '/100-views/LEGACY.html'):
            with self.subTest(path=path):
                self.assertEqual(self.request('GET', path)[0], 404)

    def test_csp_security_headers_and_routes(self):
        status, headers, _ = self.request('GET', '/100-views/webui/index.html')
        self.assertEqual(status, 200)
        self.assertIn("default-src 'self'", headers['Content-Security-Policy'])
        for name in ('X-Content-Type-Options', 'Referrer-Policy', 'X-Frame-Options'):
            self.assertIn(name, headers)
        self.assertNotIn('Content-Security-Policy', self.request('GET', '/100-views/legacy.html')[1])
        status, headers, data = self.request('GET', '/api/does-not-exist')
        self.assertEqual(status, 404)
        self.assertIn('code', json.loads(data))
        self.assertIn('no-store', headers['Cache-Control'])
        self.assertEqual(self.request('GET', '/api/reviews')[0], 405)
        status, headers, _ = self.request('GET', '/')
        self.assertEqual((status, headers['Location']), (302, '/100-views/webui/'))

    def test_role_ping_rejects_invalid_or_conflicting_targets(self):
        headers = {'Origin': self.origin, 'X-CSRF-Token': 'test-token', 'Content-Type': 'application/json'}
        for params in ({'kind': 'agent.ping', 'role': 'unknown'},
                       {'kind': 'agent.ping', 'role': 'paper-analyst', 'agent': 'codex'}):
            with self.subTest(params=params):
                status, _, data = self.post(headers, json.dumps(params).encode())
                self.assertEqual((status, json.loads(data)['code']), (400, 'bad_request'))

    def test_verify_endpoint_requires_csrf(self):
        headers = {'Origin': self.origin, 'Content-Type': 'application/json'}
        status, _, data = self.post(headers, path='/api/reviews/example/verify')
        self.assertEqual((status, json.loads(data)['code']), (403, 'bad_csrf'))

    def test_status_exposes_effective_review_roles(self):
        config = {
            'task.agentModelOverrides': {'paper-analyst': '@analysis', 'paper-verifier': '@verification'},
            'modelRoles': {'analysis': 'anthropic/example-a:high',
                           'verification': 'openai-codex/example-b:high'},
            'retry.fallbackChains': {'analysis': [], 'verification': []},
            'retry.modelFallback': True,
        }
        def fake_config(command, **kwargs):
            self.assertEqual(command[:3], ['omp', 'config', 'get'])
            self.assertEqual(Path(kwargs['cwd']), self.root)
            return subprocess.CompletedProcess(command, 0, stdout=json.dumps(config[command[3]]), stderr='')
        with patch('subprocess.run', side_effect=fake_config), \
                patch.object(reviews, 'QUEUE', self.root / 'queue.json'), \
                patch.object(research_agent, 'resolve', return_value={'agent': 'omp', 'ready': True}), \
                patch.object(research_agent, 'probe', side_effect=lambda runner: {
                    'agent': runner, 'installed': True, 'ready': True, 'authenticated': True}), \
                patch.object(reviews.shutil, 'which', return_value='/fake/cli'):
            status, _, data = self.request('GET', '/api/status')
        self.assertEqual(status, 200)
        roles = json.loads(data)['review_roles']
        for key, agent, role, selector, runner in (
            ('generation', 'paper-analyst', 'analysis', 'anthropic/example-a:high', 'claude'),
            ('verification', 'paper-verifier', 'verification', 'openai-codex/example-b:high', 'codex'),
        ):
            resolved = roles[key]
            self.assertEqual((resolved['agent_name'], resolved['source'], resolved['role']),
                             (agent, 'omp-config', role))
            selected = resolved['candidates'][resolved['selected']]
            self.assertEqual((selected['selector'], selected['runner'], selected['ready']),
                             (selector, runner, True))

    def test_reader_mutation_guards(self):
        valid = {'Origin': self.origin, 'X-CSRF-Token': 'test-token', 'Content-Type': 'application/json'}
        for method, path in (('POST', '/api/papers/example/ask'),
                             ('DELETE', '/api/papers/example/threads/t_123456789abc')):
            for headers, expected, code in (
                ({k: v for k, v in valid.items() if k != 'Origin'}, 403, 'bad_origin'),
                ({**valid, 'Origin': 'http://evil.example'}, 403, 'bad_origin'),
                ({k: v for k, v in valid.items() if k != 'X-CSRF-Token'}, 403, 'bad_csrf'),
                ({**valid, 'Content-Type': 'text/plain'}, 415, None),
            ):
                with self.subTest(method=method, headers=headers):
                    status, _, body = self.request(method, path, b'{}', headers)
                    self.assertEqual(status, expected)
                    if code:
                        self.assertEqual(json.loads(body)['code'], code)

    def test_ask_is_rejected_during_shutdown(self):
        self.server.broker.closing.set()
        valid = {'Origin': self.origin, 'X-CSRF-Token': 'test-token', 'Content-Type': 'application/json'}
        body = json.dumps({'question': '질문', 'anchor': None, 'thread_id': None}).encode()
        status, _, response = self.post(valid, body, '/api/papers/example/ask')
        self.assertEqual((status, json.loads(response)['code']), (503, 'shutting_down'))

    def test_reader_routes_reject_wrong_methods_and_private_threads(self):
        for path in ('/api/papers', '/api/papers/example/pdf', '/api/reader/status'):
            with self.subTest(path=path):
                valid = {'Origin': self.origin, 'X-CSRF-Token': 'test-token',
                         'Content-Type': 'application/json'}
                status, headers, _ = self.request('PUT', path, b'{}', valid)
                self.assertEqual(status, 405)
                self.assertIn('GET', headers['Allow'])
        private = self.root / '04-Projects/reader-threads/example.json'
        private.parent.mkdir(parents=True)
        private.write_text('{"private":"question"}')
        self.assertEqual(self.request('GET', '/04-Projects/reader-threads/example.json')[0], 404)

    def test_reader_missing_record_bad_slug_and_job_kind(self):
        with patch.object(reviews, 'LIBRARY', self.root / '01-Papers/library'):
            status, _, body = self.request('GET', '/api/papers/absent')
            self.assertEqual((status, json.loads(body)['code']), (404, 'not_found'))
            status, _, body = self.request('GET', '/api/papers/%2e%2e%2fx')
            self.assertEqual((status, json.loads(body)['code']), (400, 'bad_request'))
        headers = {'Origin': self.origin, 'X-CSRF-Token': 'test-token', 'Content-Type': 'application/json'}
        status, _, body = self.post(headers, b'{"kind":"paper.ask"}')
        self.assertEqual((status, json.loads(body)['code']), (400, 'bad_request'))

    def test_reader_pdf_stream_and_escaping_path(self):
        library = self.root / '01-Papers/library'
        library.mkdir(parents=True)
        pdf = self.root / '01-Papers/pdfs/example.pdf'
        pdf.parent.mkdir(parents=True)
        content = b'%PDF-1.4\nsynthetic PDF bytes\n'
        pdf.write_bytes(content)
        record = {'slug': 'example', 'title': 'Example', 'source': {'pdf_path': '01-Papers/pdfs/example.pdf'}}
        path = library / 'example.json'
        path.write_text(json.dumps(record))
        with patch.object(reviews, 'LIBRARY', library):
            status, headers, body = self.request('GET', '/api/papers/example/pdf')
            self.assertEqual((status, body), (200, content))
            self.assertEqual(headers['Content-Type'], 'application/pdf')
            self.assertEqual(int(headers['Content-Length']), len(content))
            record['source']['pdf_path'] = str(Path(self.outside.name) / 'secret')
            path.write_text(json.dumps(record))
            status, _, body = self.request('GET', '/api/papers/example/pdf')
            self.assertEqual((status, json.loads(body)['code']), (409, 'pdf_missing'))


class ReaderLifecycleTests(unittest.TestCase):
    def test_server_close_cancels_and_waits_for_reader_work(self):
        http = server.make_server(0, csrf_token='token')
        started = threading.Event()
        finished = threading.Event()
        def work(ctx):
            ctx.on_cancel(lambda: None)
            started.set()
            ctx.cancelled.wait(5)
            ctx.emit({'type': 'cancelled'})
            finished.set()
        record = http.broker.submit('paper.ask', {'slug': 'example'}, work)
        try:
            self.assertTrue(started.wait(2))
            http.server_close()
            self.assertTrue(finished.is_set(), 'server_close returned before reader cleanup')
            self.assertEqual(http.broker.get(record['job_id'])['status'], 'cancelled')
        finally:
            http.broker.cancel(record['job_id'])
            http.server_close()

    def test_server_close_waits_for_cleanup_after_terminal_event(self):
        http = server.make_server(0, csrf_token='token')
        terminal = threading.Event()
        release = threading.Event()
        returned = threading.Event()
        def work(ctx):
            ctx.emit({'type': 'result', 'text': 'done'})
            terminal.set()
            release.wait(4)
        record = http.broker.submit('paper.ask', {'slug': 'example'}, work)
        closer = threading.Thread(target=lambda: (http.server_close(), returned.set()), daemon=True)
        try:
            self.assertTrue(terminal.wait(2))
            self.assertEqual(http.broker.get(record['job_id'])['status'], 'completed')
            closer.start()
            self.assertFalse(returned.wait(0.2), 'terminal event must not bypass cleanup')
            release.set()
            self.assertTrue(returned.wait(3))
        finally:
            release.set()
            if closer.is_alive():
                closer.join(4)
            http.server_close()

    def test_startup_removes_stale_workspaces_but_not_recent_or_symlink(self):
        import os
        import time
        from webui import reader
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            old = root / 'webui-reader-old'
            recent = root / 'webui-reader-recent'
            middle = root / 'webui-reader-other-live'
            other = root / 'unrelated'
            target = root / 'outside-target'
            for path in (old, recent, middle, other, target):
                path.mkdir()
            link = root / 'webui-reader-link'
            link.symlink_to(target, target_is_directory=True)
            past = time.time() - reader.STALE_WORKSPACE_S - 30
            os.utime(old, (past, past))
            os.utime(other, (past, past))
            still_live = time.time() - reader.READER_TIMEOUT_S - 30
            os.utime(middle, (still_live, still_live))
            with patch.object(reader.tempfile, 'gettempdir', return_value=str(root)):
                http = server.make_server(0)
                http.server_close()
            self.assertFalse(old.exists())
            self.assertTrue(recent.is_dir())
            self.assertTrue(middle.is_dir())
            self.assertTrue(other.is_dir())
            self.assertTrue(link.is_symlink())
            self.assertTrue(target.is_dir())

    def test_cleanup_preserves_live_owner_and_other_uid(self):
        import os
        import time
        from webui import reader
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            live = root / 'webui-reader-live'
            dead = root / 'webui-reader-dead'
            foreign = root / 'webui-reader-foreign'
            for path in (live, dead, foreign):
                path.mkdir()
            live_fd = reader.claim_workspace(live)
            dead_fd = reader.claim_workspace(dead)
            os.close(dead_fd)
            past = time.time() - reader.STALE_WORKSPACE_S * 10
            os.utime(live, (past, past))
            os.utime(foreign, (past, past))
            try:
                with patch.object(reader.os, 'getuid', return_value=os.getuid() + 1):
                    reader.remove_stale_workspaces(root)
                self.assertTrue(foreign.exists())
                self.assertTrue(dead.exists())
                reader.remove_stale_workspaces(root)
                self.assertTrue(live.is_dir())
                self.assertFalse(dead.exists())
            finally:
                os.close(live_fd)
