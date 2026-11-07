import http.client
import datetime
import json
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.scripts/bin'))
import research_agent
import paper_record
from webui import discovery
from webui import llm, reviews, roles, server


def candidate(title='A paper', doi='10.1234/Example', url='https://example.org/paper'):
    return {
        'candidate_id': 'c_0123456789ab', 'title': title, 'authors': ['A Author'],
        'year': 2026, 'venue': 'CVPR',
        'publication': {'status': 'preprint', 'verified': False, 'verification_sources': []},
        'citations': None, 'ids': {'arXiv': '2601.12345v2', 'DOI': doi, 'S2': None, 'OpenAlex': None},
        'url': url, 'abstract': None, 'relevance': 'Relevant to the topic.',
        'sources': ['arxiv'], 'suggested_category': 'computer-vision', 'topics': [],
        'conference_ref': None, 'status': 'new', 'status_updated_at': None, 'slug': None,
    }


def daily(date='2026-11-07', paper=None):
    return {
        'schema_version': '1.0', 'date': date, 'created_at': date + 'T10:00:00Z',
        'plan_path': None,
        'slots': [
            {'slot': 'computer-vision', 'topic': 'vision', 'candidate': paper or candidate(), 'unfilled_reason': None},
            {'slot': 'multimodal', 'topic': None, 'candidate': None, 'unfilled_reason': 'No result'},
            {'slot': 'interest', 'topic': None, 'candidate': None, 'unfilled_reason': 'No result'},
        ],
        'report': {'queries': [], 'sources': [], 'coverage_gaps': [], 'notes': ''},
    }


def session(search_id='s_0123456789ab'):
    return {
        'schema_version': '1.0', 'search_id': search_id, 'mode': 'search',
        'created_at': '2026-11-07T10:00:00Z', 'status': 'completed', 'job_id': None,
        'request': {'query': 'vision papers', 'year_from': None, 'year_to': None, 'limit': 10,
                    'category_hint': None, 'anchors': [], 'verified_only': False},
        'agent': None, 'report': None, 'candidates': [candidate()], 'error': None, 'duration_ms': 100,
    }


class DiscoveryRoutesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.cache = self.root / '00-Inbox/discovery'
        (self.cache / 'daily').mkdir(parents=True)
        (self.cache / 'searches').mkdir()
        self.root_patch = patch.object(reviews, 'ROOT', self.root)
        self.root_patch.start()
        self.library_patch = patch.object(reviews, 'LIBRARY', self.root / '01-Papers/library')
        self.library_patch.start()
        self.http = server.make_server(0, csrf_token='test-token')
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(2)
        self.root_patch.stop()
        self.library_patch.stop()
        self.temp.cleanup()

    def get(self, path):
        conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=3)
        try:
            conn.request('GET', path)
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def mutate(self, method, path, payload=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.http.server_port, timeout=3)
        try:
            conn.request(method, path, json.dumps(payload or {}).encode(), {
                'Origin': f'http://127.0.0.1:{self.http.server_port}',
                'X-CSRF-Token': 'test-token', 'Content-Type': 'application/json',
            })
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    def put_json(self, relative, value):
        (self.cache / relative).write_text(json.dumps(value), encoding='utf-8')

    def test_daily_list_detail_errors_and_dates(self):
        self.put_json('daily/2026-11-07.json', daily())
        self.put_json('daily/2026-11-06.json', daily('2026-11-06'))
        (self.cache / 'daily/2026-11-05.json').write_text('{', encoding='utf-8')
        status, body = self.get('/api/discovery/daily')
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertEqual([day['date'] for day in payload['days']], ['2026-11-07', '2026-11-06'])
        self.assertEqual(payload['days'][0]['filled'], 1)
        self.assertEqual(len(payload['errors']), 1)
        status, body = self.get('/api/discovery/daily/2026-11-07')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['daily']['slots'][0]['candidate']['title'], 'A paper')
        for date, expected, code in [('bad-date', 400, 'bad_request'), ('2026-02-30', 400, 'bad_request'),
                                     ('2026-11-01', 404, 'not_found')]:
            with self.subTest(date=date):
                status, body = self.get('/api/discovery/daily/' + date)
                self.assertEqual((status, json.loads(body)['code']), (expected, code))

    def test_search_list_detail_and_invalid_identifiers(self):
        self.put_json('searches/s_0123456789ab.json', session())
        status, body = self.get('/api/discovery/searches')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['searches'][0]['search_id'], 's_0123456789ab')
        status, body = self.get('/api/discovery/searches/s_0123456789ab')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['search']['candidates'][0]['title'], 'A paper')
        for name, expected, code in [('invalid', 400, 'bad_request'), ('s_aaaaaaaaaaaa', 404, 'not_found')]:
            with self.subTest(name=name):
                status, body = self.get('/api/discovery/searches/' + name)
                self.assertEqual((status, json.loads(body)['code']), (expected, code))

    def test_search_request_rejects_out_of_bounds_and_unknown_anchors(self):
        next_year = datetime.date.today().year + 1
        invalid = [
            {'query': 'ab'}, {'query': 'x' * 501},
            {'query': 'valid query', 'limit': 0}, {'query': 'valid query', 'limit': 31},
            {'query': 'valid query', 'year_from': 1899},
            {'query': 'valid query', 'year_to': next_year + 1},
            {'query': 'valid query', 'year_from': 2020, 'year_to': 2019},
            {'query': 'valid query', 'anchors': ['a', 'b', 'c', 'd']},
            {'query': 'valid query', 'anchors': ['nonexistent-paper']},
            {'query': 'valid query', 'category_hint': 'unknown'},
            {'query': 'valid query', 'verified_only': 'true'},
        ]
        for request in invalid:
            with self.subTest(request=request):
                status, result = self.mutate('POST', '/api/discovery/searches', request)
                self.assertEqual((status, result['code']), (400, 'bad_request'))

    def test_interrupted_search_reconciled_on_list_and_detail(self):
        for index, state in enumerate(('queued', 'running')):
            search_id = f's_{index:012x}'
            item = session(search_id)
            item.update(status=state, job_id=f'missing-{index}')
            self.put_json(f'searches/{search_id}.json', item)
        status, result = self.get('/api/discovery/searches')
        self.assertEqual(status, 200)
        self.assertEqual({s['status'] for s in json.loads(result)['searches']}, {'failed'})
        for index in range(2):
            search_id = f's_{index:012x}'
            status, result = self.get('/api/discovery/searches/' + search_id)
            self.assertEqual(status, 200)
            search = json.loads(result)['search']
            self.assertEqual((search['status'], search['error']['kind']), ('failed', 'interrupted'))
            persisted = json.loads((self.cache / f'searches/{search_id}.json').read_text())
            self.assertEqual(persisted['error']['kind'], 'interrupted')

    def test_delete_completed_and_missing_searches(self):
        search_id = 's_0123456789ab'
        self.put_json(f'searches/{search_id}.json', session(search_id))
        status, result = self.mutate('DELETE', '/api/discovery/searches/' + search_id)
        self.assertEqual((status, result['deleted']), (200, search_id))
        status, result = self.mutate('DELETE', '/api/discovery/searches/' + search_id)
        self.assertEqual((status, result['code']), (404, 'not_found'))

    def test_single_active_search_and_delete_conflict(self):
        entered, release = threading.Event(), threading.Event()
        def work(ctx):
            entered.set()
            release.wait(5)
            ctx.emit({'type': 'result', 'text': ''})
        job = self.http.broker.submit('discovery.search', {'role': 'paper-searcher'}, work)
        self.addCleanup(release.set)
        self.assertTrue(entered.wait(2))
        search_id = 's_0123456789ab'
        item = session(search_id)
        item.update(status='running', job_id=job['job_id'])
        self.put_json(f'searches/{search_id}.json', item)
        resolution = {'configured': False, 'error': None, 'candidates': [], 'selected': None}
        with patch.object(roles, 'resolve', return_value=resolution), \
             patch.object(research_agent, 'resolve', return_value={'agent': 'omp', 'ready': True}):
            status, result = self.mutate('POST', '/api/discovery/searches', {'query': 'valid query'})
        self.assertEqual((status, result['code']), (409, 'search_active'))
        status, result = self.mutate('DELETE', '/api/discovery/searches/' + search_id)
        self.assertEqual((status, result['code']), (409, 'search_active'))
        self.assertTrue((self.cache / f'searches/{search_id}.json').exists())
        release.set()
        self.assertTrue(self.http.broker.wait_finished([job['job_id']], 3))

    def run_search(self, query, output, cancel=False):
        for relative in ('.scripts/bin/paper.py', '.scripts/docs/search-protocol.md',
                         '.scripts/docs/discovery-search.schema.json',
                         '.agents/skills/paper-search/SKILL.md',
                         '01-Papers/reference/cs-conferences.csv'):
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, destination)
        library = self.root / '01-Papers/library'
        library.mkdir(parents=True, exist_ok=True)
        (library / 'library-paper.json').write_text(json.dumps({
            'slug': 'library-paper', 'title': 'Existing paper',
            'paper_id': 'arXiv:2601.12345', 'source': {'urls': []},
            'publication': {'verification_sources': []},
        }), encoding='utf-8')
        launched, release, calls = threading.Event(), threading.Event(), []

        class Run:
            def events(self):
                launched.set()
                if cancel:
                    release.wait(3)
                    yield {'type': 'cancelled'}
                else:
                    yield {'type': 'start', 'agent': 'omp', 'model': None}
                    yield {'type': 'result', 'text': output}
            def cancel(self):
                release.set()
            def terminate(self):
                release.set()

        def launch(agent, argv, request):
            calls.append((agent, argv, request))
            return Run()

        resolution = {'agent_name': 'paper-searcher', 'configured': False,
                      'error': None, 'selected': None, 'candidates': [], 'notes': []}
        with patch.object(roles, 'resolve', return_value=resolution), \
             patch.object(roles, 'agent_definition', return_value=({}, 'Search instructions')), \
             patch.object(research_agent, 'resolve', return_value={'agent': 'omp', 'ready': True}), \
             patch.object(research_agent, 'discovery_command', return_value=['omp']) as command, \
             patch.object(llm, 'launch', side_effect=launch):
            status, response = self.mutate('POST', '/api/discovery/searches', {'query': query})
            self.assertEqual(status, 202, response)
            job_id = response['job']['job_id']
            self.assertTrue(launched.wait(3))
            if cancel:
                self.assertTrue(self.http.broker.cancel(job_id))
            self.assertTrue(self.http.broker.wait_finished([job_id], 3))
            self.assertEqual(command.call_args.kwargs['timeout_seconds'], 900 + llm.CLI_TIMEOUT_GRACE_S)
        status, body = self.get('/api/discovery/searches/' + response['search']['search_id'])
        self.assertEqual(status, 200)
        return json.loads(body)['search'], calls

    def test_search_work_normalizes_and_matches_library_with_timeout(self):
        paper = candidate(url='http://insecure.example')
        for key in ('candidate_id', 'conference_ref', 'status', 'status_updated_at', 'slug'):
            del paper[key]
        paper['title'] = 'A\x00 paper'
        output = json.dumps({
            'report': {'queries': ['vision'], 'sources': ['arxiv', 's2'], 'anchors': [],
                       'coverage_gaps': [], 'excluded_count': 0, 'notes': ''},
            'candidates': [paper],
        })
        result, calls = self.run_search(' a\x00bc ', output)
        self.assertEqual(result['status'], 'completed')
        self.assertEqual(result['request']['query'], 'abc')
        self.assertEqual(calls[0][2].timeout_s, 900)
        found = result['candidates'][0]
        self.assertNotIn('\x00', found['title'])
        self.assertIsNone(found['url'])
        self.assertEqual(found['ids']['arXiv'], '2601.12345')
        self.assertEqual(found['library'], {'slug': 'library-paper', 'match': 'id'})
        self.assertTrue(found['candidate_id'].startswith('c_'))
        self.assertEqual(found['status'], 'new')

    def test_search_work_invalid_output_is_failed(self):
        result, _ = self.run_search('abc', 'not valid JSON')
        self.assertEqual((result['status'], result['error']['kind']), ('failed', 'invalid_output'))
        self.assertIn('not valid JSON', result['report']['notes'])

    def test_search_work_cancelled(self):
        result, _ = self.run_search('x' * 500, '', cancel=True)
        self.assertEqual(result['status'], 'cancelled')

    def test_completion_write_failure_fails_job_and_reconciles_session(self):
        original = discovery.cache.write_session
        failed_writes = []

        def fail_completed(root, item):
            if item['status'] == 'completed':
                failed_writes.append(item['search_id'])
                raise OSError('injected completion write failure')
            return original(root, item)

        output = json.dumps({
            'report': {'queries': [], 'sources': [], 'anchors': [],
                       'coverage_gaps': [], 'excluded_count': 0, 'notes': ''},
            'candidates': [],
        })
        with patch.object(discovery.cache, 'write_session', side_effect=fail_completed):
            result, _ = self.run_search('valid query', output)
        self.assertEqual(failed_writes, [result['search_id']])
        job = self.http.broker.get(result['job_id'])
        self.assertEqual(job['status'], 'failed', job)
        self.assertEqual(result['status'], 'failed')
        self.assertIn(result['error']['kind'], ('persist_failed', 'interrupted'))
        events = [event for _, event in self.http.broker.events(result['job_id'])]
        self.assertEqual(events[-1]['type'], 'error')
        status, response = self.mutate('DELETE', '/api/discovery/searches/' + result['search_id'])
        self.assertEqual((status, response['deleted']), (200, result['search_id']))
        next_search, _ = self.run_search('another query', output)
        self.assertEqual(next_search['status'], 'completed')

    def test_library_matches_ids_versioned_arxiv_and_normalized_title(self):
        library = self.root / '01-Papers/library'
        library.mkdir(parents=True)
        record = {'slug': 'library-paper', 'title': 'Library title',
                  'paper_id': 'arXiv:2601.12345', 'source': {'urls': []},
                  'publication': {'verification_sources': []}}
        (library / 'library-paper.json').write_text(json.dumps(record), encoding='utf-8')
        paper = candidate(title='Different title', doi=None)
        self.put_json('daily/2026-11-07.json', daily(paper=paper))
        status, body = self.get('/api/discovery/daily/2026-11-07')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['daily']['slots'][0]['candidate']['library'],
                         {'slug': 'library-paper', 'match': 'id'})
        paper['ids']['arXiv'] = None
        paper['title'] = 'LIBRARY, title!'
        self.put_json('daily/2026-11-07.json', daily(paper=paper))
        status, body = self.get('/api/discovery/daily/2026-11-07')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['daily']['slots'][0]['candidate']['library'],
                         {'slug': 'library-paper', 'match': 'title'})
        record['paper_id'] = 'DOI:10.1234/example'
        (library / 'library-paper.json').write_text(json.dumps(record), encoding='utf-8')
        paper['title'] = 'Unrelated title'
        paper['ids']['DOI'] = '10.1234/EXAMPLE'
        self.put_json('daily/2026-11-07.json', daily(paper=paper))
        status, body = self.get('/api/discovery/daily/2026-11-07')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['daily']['slots'][0]['candidate']['library'],
                         {'slug': 'library-paper', 'match': 'id'})

    def test_conference_reference_is_derived_from_csv(self):
        reference = self.root / '01-Papers/reference'
        reference.mkdir(parents=True)
        (reference / 'cs-conferences.csv').write_text(
            '약자,평균 (정규화),학회명,DBLP Key\nCVPR,1.00,Computer Vision Conference,conf/cvpr\n',
            encoding='utf-8')
        self.put_json('daily/2026-11-07.json', daily())
        status, body = self.get('/api/discovery/daily/2026-11-07')
        self.assertEqual(status, 200)
        ref = json.loads(body)['daily']['slots'][0]['candidate']['conference_ref']
        self.assertEqual(ref, {'abbr': 'CVPR', 'name': 'Computer Vision Conference', 'score': 1.0})

    def test_cache_static_paths_are_not_exposed(self):
        self.put_json('daily/2026-11-07.json', daily())
        self.put_json('searches/s_0123456789ab.json', session())
        for path in ('/00-Inbox/discovery/daily/2026-11-07.json',
                     '/00-Inbox/discovery/searches/s_0123456789ab.json'):
            with self.subTest(path=path):
                self.assertEqual(self.get(path)[0], 404)

    def test_symlinked_cache_directory_fails_closed_on_read_routes(self):
        with tempfile.TemporaryDirectory() as outside:
            (self.cache / 'daily').rmdir()
            (self.cache / 'daily').symlink_to(outside, target_is_directory=True)
            for path in ('/api/discovery/daily', '/api/discovery/daily/2026-11-07'):
                with self.subTest(path=path):
                    status, body = self.get(path)
                    self.assertEqual((status, json.loads(body)['code']), (500, 'cache_unsafe'))
        (self.cache / 'daily').unlink()
        (self.cache / 'daily').mkdir()
        with tempfile.TemporaryDirectory() as outside:
            (self.cache / 'searches').rmdir()
            (self.cache / 'searches').symlink_to(outside, target_is_directory=True)
            for path in ('/api/discovery/searches', '/api/discovery/searches/s_0123456789ab'):
                with self.subTest(path=path):
                    status, body = self.get(path)
                    self.assertEqual((status, json.loads(body)['code']), (500, 'cache_unsafe'))


class DiscoveryRelatedTests(unittest.TestCase):
    get = DiscoveryRoutesTests.get
    mutate = DiscoveryRoutesTests.mutate
    tearDown = DiscoveryRoutesTests.tearDown

    def setUp(self):
        DiscoveryRoutesTests.setUp(self)
        discovery.clear_related_cache()
        spacing = patch.object(discovery, 'RELATED_SPACING_S', 0)
        spacing.start()
        self.addCleanup(spacing.stop)
        self.addCleanup(discovery.clear_related_cache)

    def related(self, payload):
        return self.mutate('POST', '/api/discovery/related', payload)

    def test_invalid_requests_and_unknown_slug_do_not_fetch(self):
        valid_paper = {'title': 'Anchor', 'ids': {'arXiv': '2601.12345'}}
        invalid = [
            {'kind': 'other', 'paper': valid_paper},
            {'kind': 'refs', 'paper': valid_paper, 'limit': 0},
            {'kind': 'refs', 'paper': valid_paper, 'limit': 51},
            {'kind': 'refs', 'paper': valid_paper, 'limit': True},
            {'kind': 'refs', 'paper': {}},
            {'kind': 'refs', 'paper': {'ids': {'arXiv': '2601.12345'}}},
            {'kind': 'refs', 'paper': {'slug': '../escape'}},
        ]
        with patch.object(discovery.paper, 'fetch_json') as fetch:
            for request in invalid:
                with self.subTest(request=request):
                    status, result = self.related(request)
                    self.assertEqual((status, result['code']), (400, 'bad_request'))
            status, result = self.related({'kind': 'refs', 'paper': {'slug': 'missing-paper'}})
            self.assertEqual((status, result['code']), (404, 'not_found'))
            status, result = self.related({'kind': 'refs', 'paper': {'title': 'Anchor', 'ids': {}}})
            self.assertEqual((status, result['code']), (400, 'no_identifier'))
            fetch.assert_not_called()

    def test_related_session_persisted_and_library_matched(self):
        library = self.root / '01-Papers/library'
        library.mkdir(parents=True)
        (library / 'existing.json').write_text(json.dumps({
            'slug': 'existing', 'title': 'Existing paper', 'paper_id': 'arXiv:2602.12345',
            'source': {'urls': []},
        }), encoding='utf-8')
        response = {'data': [{'citedPaper': {
            'title': 'Existing paper', 'paperId': 'a' * 40,
            'externalIds': {'ArXiv': '2602.12345v2'}, 'authors': [{'name': 'A Author'}],
            'year': 2025, 'venue': 'CVPR', 'citationCount': 7,
        }}]}
        request = {'kind': 'refs', 'paper': {'title': 'Anchor',
                   'ids': {'arXiv': '2601.12345'}}, 'limit': 50}
        with patch.object(discovery.paper, 'fetch_json', return_value=response):
            status, result = self.related(request)
        self.assertEqual(status, 201, result)
        search = result['search']
        self.assertEqual((search['mode'], search['status']), ('related', 'completed'))
        self.assertEqual(search['request']['kind'], 'refs')
        self.assertEqual(search['request']['paper']['title'], 'Anchor')
        self.assertEqual(search['request']['limit'], 50)
        item = search['candidates'][0]
        self.assertRegex(item['candidate_id'], r'^c_[0-9a-f]{12}$')
        self.assertEqual(item['ids']['arXiv'], '2602.12345')
        self.assertEqual(item['authors'], ['A Author'])
        self.assertEqual(item['library'], {'slug': 'existing', 'match': 'id'})
        saved = json.loads((self.cache / 'searches' / (search['search_id'] + '.json')).read_text())
        self.assertEqual(saved['mode'], 'related')
        self.assertEqual(saved['candidates'][0]['candidate_id'], item['candidate_id'])
        self.assertNotIn('library', saved['candidates'][0])
        status, body = self.get('/api/discovery/searches/' + search['search_id'])
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['search']['candidates'][0]['library'], item['library'])

    def test_upstream_errors_are_mapped_without_real_network(self):
        import urllib.error
        cases = [
            ('2603.11111', urllib.error.HTTPError('https://api.semanticscholar.org/', 429,
                                                  'rate limited', {}, None), 503, 'upstream_rate_limited'),
            ('2603.22222', urllib.error.URLError('offline'), 502, 'upstream_unavailable'),
            ('2603.33333', TimeoutError('timed out'), 504, 'upstream_timeout'),
            ('2603.44444', urllib.error.HTTPError('https://api.semanticscholar.org/', 404,
                                                  'not found', {}, None), 404, 'not_found'),
        ]
        with patch.object(discovery.paper.time, 'sleep'), \
             patch.object(discovery.paper.urllib.request, 'urlopen') as fetch:
            for identifier, error, expected_status, code in cases:
                with self.subTest(code=code):
                    fetch.side_effect = error
                    status, result = self.related({'kind': 'cites', 'paper': {
                        'title': 'Anchor', 'ids': {'arXiv': identifier}}})
                    self.assertEqual((status, result['code']), (expected_status, code))
                    self.assertTrue(fetch.called)
                    fetch.reset_mock()
                    if code == 'upstream_rate_limited':
                        self.assertIn('S2_API_KEY', result['error'])

    def test_overall_deadline_returns_timeout(self):
        release = threading.Event()
        finished = threading.Event()

        def blocked_fetch(*args, **kwargs):
            try:
                release.wait(2)
                return {'data': []}
            finally:
                finished.set()

        with patch.object(discovery, 'RELATED_DEADLINE_S', 0.2), \
             patch.object(discovery.paper, 'fetch_json', side_effect=blocked_fetch):
            try:
                status, result = self.related({'kind': 'refs', 'paper': {
                    'title': 'Slow anchor', 'ids': {'arXiv': '2606.12345'}}})
                self.assertEqual((status, result['code']), (504, 'upstream_timeout'))
            finally:
                release.set()
                finished.wait(2)

    def test_library_slug_resolves_anchor_identifiers(self):
        library = self.root / '01-Papers/library'
        library.mkdir(parents=True)
        (library / 'anchor.json').write_text(json.dumps({
            'slug': 'anchor', 'title': 'Library anchor', 'paper_id': 'arXiv:2605.12345',
            'source': {'urls': []},
        }), encoding='utf-8')
        with patch.object(discovery.paper, 'fetch_json', return_value={'data': []}) as fetch:
            status, result = self.related({'kind': 'refs', 'paper': {'slug': 'anchor'}, 'limit': 1})
        self.assertEqual(status, 201, result)
        anchor = result['search']['request']['paper']
        self.assertEqual((anchor['slug'], anchor['title']), ('anchor', 'Library anchor'))
        self.assertEqual(anchor['ids']['arXiv'], '2605.12345')
        self.assertIn('2605.12345', fetch.call_args.args[0])

    def test_repeated_request_uses_cache_but_creates_sessions(self):
        request = {'kind': 'cites', 'paper': {'title': 'Cache anchor',
                   'ids': {'arXiv': '2604.55555'}}, 'limit': 1}
        response = {'data': [{'citingPaper': {
            'title': 'Citing paper', 'paperId': 'b' * 40,
            'externalIds': {}, 'authors': [], 'citationCount': 2,
        }}]}
        with patch.object(discovery.paper, 'fetch_json', return_value=response) as fetch:
            status1, first = self.related(request)
            status2, second = self.related(request)
        self.assertEqual((status1, status2), (201, 201))
        self.assertEqual(fetch.call_count, 1)
        self.assertNotEqual(first['search']['search_id'], second['search']['search_id'])
        self.assertEqual(first['search']['candidates'], second['search']['candidates'])


class DiscoveryAdoptionTests(unittest.TestCase):
    get = DiscoveryRoutesTests.get
    mutate = DiscoveryRoutesTests.mutate
    put_json = DiscoveryRoutesTests.put_json
    tearDown = DiscoveryRoutesTests.tearDown

    def setUp(self):
        DiscoveryRoutesTests.setUp(self)
        queue_patch = patch.object(reviews, 'QUEUE', self.root / '04-Projects/review-queue/queue.json')
        queue_patch.start()
        self.addCleanup(queue_patch.stop)
        self.put_json('searches/s_0123456789ab.json', session())
        self.papers = self.root / '01-Papers'
        self.papers.mkdir(exist_ok=True)
        self.keep = self.papers / 'keep.md'
        self.index = self.papers / 'index.md'
        self.index.write_text('# Index\n\n| 상태 | 연도 | 제목 | 제1저자 | venue | 평점 | 리뷰 | 태그 |\n'
                              '| --- | --- | --- | --- | --- | --- | --- | --- |\n', encoding='utf-8')
        for relative in ('.scripts/bin/paper_record.py', '.scripts/bin/paper.py',
                         '.scripts/docs/search-protocol.md',
                         '.scripts/docs/discovery-register.schema.json',
                         '.agents/skills/paper-search/SKILL.md'):
            source = ROOT / relative
            destination = self.root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)

    def request(self, path, **extra):
        payload = {'source': {'kind': 'search', 'id': 's_0123456789ab'},
                   'candidate_id': 'c_0123456789ab'}
        payload.update(extra)
        return self.mutate('POST', '/api/discovery/' + path, payload)

    def cached_candidate(self):
        data = json.loads((self.cache / 'searches/s_0123456789ab.json').read_text())
        return data['candidates'][0]

    def test_keep_record_entry_position_and_index_unchanged(self):
        self.keep.write_text('# Keep\n\n## 읽을 논문\n\n### Old paper\n\n- 상태: 킵\n'
                             '\n## 다시 볼 조사 주제\n', encoding='utf-8')
        before = self.index.read_bytes()
        status, result = self.request('keep', reason='  Useful   evidence  ')
        self.assertEqual(status, 200, result)
        record = json.loads((self.root / result['record_path']).read_text())
        self.assertEqual(paper_record.validate_record(record), [])
        self.assertEqual((record['reading_status'], record['metadata_status']), ('keep', 'partial'))
        self.assertIsNone(record['source']['pdf_path'])
        text = self.keep.read_text()
        self.assertLess(text.index('## 읽을 논문'), text.index('### A paper'))
        self.assertLess(text.index('### A paper'), text.index('### Old paper'))
        for line in ('- 추가일: ', '- 출처: CVPR', '[arXiv:2601.12345]',
                     '[DOI](https://doi.org/10.1234/Example)', '- PDF: 없음',
                     '- 리뷰: 없음', '- 상태: 킵', '- 이유: Useful evidence'):
            self.assertIn(line, text)
        kst_today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9))).date().isoformat()
        self.assertIn('- 추가일: ' + kst_today, text)
        self.assertEqual(result['keep_path'], '01-Papers/keep.md')
        self.assertEqual(self.index.read_bytes(), before)
        self.assertEqual(self.cached_candidate()['status'], 'keep')
        self.assertEqual(self.cached_candidate()['slug'], result['slug'])

    def test_keep_creates_missing_file_or_section(self):
        for existing in (None, '# Notes\n\n## 다른 항목\n'):
            with self.subTest(existing=existing):
                if existing is None:
                    self.keep.unlink(missing_ok=True)
                else:
                    self.keep.write_text(existing, encoding='utf-8')
                self.put_json('searches/s_0123456789ab.json', session())
                for record in (self.papers / 'library').glob('*.json') if (self.papers / 'library').exists() else ():
                    record.unlink()
                status, result = self.request('keep', reason='')
                self.assertEqual(status, 200, result)
                text = self.keep.read_text()
                self.assertIn('## 읽을 논문', text)
                self.assertIn('- 이유: 사용자 지정 이유 없음', text)
                if existing:
                    self.assertTrue(text.startswith(existing))

    def test_keep_rejects_library_id_and_casefold_title(self):
        library = self.papers / 'library'
        library.mkdir()
        for title, paper_id in [('Different title', 'arXiv:2601.12345'),
                                ('a PAPER', 'local:unrelated')]:
            with self.subTest(title=title):
                (library / 'existing.json').write_text(json.dumps({
                    'slug': 'existing', 'title': title, 'paper_id': paper_id,
                    'source': {'urls': []}, 'publication': {'verification_sources': []},
                }), encoding='utf-8')
                status, result = self.request('keep')
                self.assertEqual((status, result['code']), (409, 'already_in_library'))
                self.assertFalse(self.keep.exists())

    def test_keep_rejects_duplicate_title_arxiv_and_doi(self):
        for entry in ('### a PAPER\n', '### Another\nhttps://arxiv.org/abs/2601.12345\n',
                      '### Another\nhttps://doi.org/10.1234/example\n'):
            with self.subTest(entry=entry):
                self.keep.write_text('# Keep\n\n## 읽을 논문\n\n' + entry, encoding='utf-8')
                before = self.keep.read_bytes()
                status, result = self.request('keep')
                self.assertEqual((status, result['code']), (409, 'already_in_keep'))
                self.assertEqual(self.keep.read_bytes(), before)
                self.assertFalse(list((self.papers / 'library').glob('*.json')))

    def test_keep_rolls_back_record_when_keep_write_fails(self):
        self.keep.write_text('# Keep\n\n## 읽을 논문\n', encoding='utf-8')
        before = self.keep.read_bytes()
        original = discovery._write_text
        def fail_keep(path, text):
            if Path(path) == self.keep:
                raise OSError('injected keep write failure')
            return original(path, text)
        with patch.object(discovery, '_write_text', side_effect=fail_keep):
            status, result = self.request('keep')
        self.assertEqual((status, result['code']), (500, 'write_failed'))
        self.assertEqual(self.keep.read_bytes(), before)
        self.assertFalse(list((self.papers / 'library').glob('*.json')))
        self.assertEqual(self.cached_candidate()['status'], 'new')

    def test_status_skip_restore_and_reject_manual_adoption(self):
        for target in ('skipped', 'new'):
            status, result = self.request('candidates/status', status=target)
            self.assertEqual(status, 200, result)
            self.assertEqual(result['candidate']['status'], target)
            self.assertEqual(self.cached_candidate()['status'], target)
        for target in ('keep', 'registered', 'invalid', None):
            with self.subTest(target=target):
                status, result = self.request('candidates/status', status=target)
                self.assertEqual((status, result['code']), (400, 'bad_request'))
                self.assertEqual(self.cached_candidate()['status'], 'new')

    def test_daily_candidate_can_be_skipped_then_kept(self):
        self.put_json('daily/2026-11-07.json', daily())
        payload = {'source': {'kind': 'daily', 'id': '2026-11-07'},
                   'candidate_id': 'c_0123456789ab'}
        status, result = self.mutate('POST', '/api/discovery/candidates/status',
                                     {**payload, 'status': 'skipped'})
        self.assertEqual(status, 200, result)
        status, result = self.mutate('POST', '/api/discovery/keep', {**payload, 'reason': 'Daily'})
        self.assertEqual(status, 200, result)
        saved = json.loads((self.cache / 'daily/2026-11-07.json').read_text())
        self.assertEqual(saved['slots'][0]['candidate']['status'], 'keep')
        self.assertIn('- 이유: Daily', self.keep.read_text())

    def test_daily_replace_preserves_concurrent_server_status_change(self):
        input_path = self.root / 'daily-input.json'
        input_path.write_text(json.dumps(daily()), encoding='utf-8')
        cli = ROOT / '.scripts/bin/discovery_cache.py'
        first = subprocess.run([sys.executable, '-B', str(cli), '--root', str(self.root),
                                'daily-write', str(input_path)], capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        path = self.cache / 'daily/2026-11-07.json'
        candidate_id = json.loads(path.read_text())['slots'][0]['candidate']['candidate_id']
        script = '''
import sys
sys.path.insert(0, sys.argv[1])
import discovery_cache as cache
original = cache.prepare_daily
def paused(*args, **kwargs):
    if kwargs.get("previous") is not None:
        print("previous-read", flush=True)
        if not sys.stdin.readline():
            raise RuntimeError("parent closed barrier")
    return original(*args, **kwargs)
cache.prepare_daily = paused
raise SystemExit(cache.main(["--root", sys.argv[2], "daily-write", sys.argv[3], "--replace"]))
'''
        child = subprocess.Popen([sys.executable, '-B', '-c', script, str(cli.parent),
                                  str(self.root), str(input_path)],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        completed = threading.Event()
        results = []
        def change_status():
            try:
                results.append(self.mutate('POST', '/api/discovery/candidates/status', {
                    'source': {'kind': 'daily', 'id': '2026-11-07'},
                    'candidate_id': candidate_id, 'status': 'skipped',
                }))
            finally:
                completed.set()
        worker = None
        try:
            ready, _, _ = select.select([child.stdout], [], [], 5)
            self.assertTrue(ready, 'CLI did not reach the previous-state barrier')
            self.assertEqual(child.stdout.readline().strip(), 'previous-read')
            worker = threading.Thread(target=change_status, daemon=True)
            worker.start()
            completed.wait(0.5)  # An unlocked server completes here; a locked server waits.
            child.stdin.write('continue\n')
            child.stdin.flush()
            stdout, stderr = child.communicate(timeout=5)
            self.assertEqual(child.returncode, 0, stdout + stderr)
            self.assertTrue(completed.wait(5), 'status update did not finish')
            self.assertEqual(results[0][0], 200, results)
            self.assertEqual(json.loads(path.read_text())['slots'][0]['candidate']['status'], 'skipped')
        finally:
            if child.poll() is None:
                child.kill()
                child.communicate()
            if worker is not None:
                worker.join(5)

    def test_keep_truncates_reason_and_missing_candidate_is_not_found(self):
        status, result = self.request('keep', reason='x' * 501)
        self.assertEqual(status, 200, result)
        reason_line = next(line for line in self.keep.read_text().splitlines()
                           if line.startswith('- 이유: '))
        self.assertEqual(reason_line, '- 이유: ' + 'x' * 500)
        before = self.keep.read_bytes()
        status, result = self.request('keep', candidate_id='c_aaaaaaaaaaaa')
        self.assertEqual((status, result['code']), (404, 'candidate_not_found'))
        self.assertEqual(self.keep.read_bytes(), before)
        for source in ({'kind': 'search', 'id': 's_aaaaaaaaaaaa'},
                       {'kind': 'daily', 'id': '2026-11-01'}):
            with self.subTest(source=source):
                status, result = self.request('keep', source=source)
                self.assertEqual((status, result['code']), (404, 'not_found'))

    def test_adopted_candidates_cannot_be_manually_skipped(self):
        for current in ('keep', 'registered'):
            with self.subTest(current=current):
                item = session()
                item['candidates'][0].update(status=current, slug='2026-author-a-paper')
                self.put_json('searches/s_0123456789ab.json', item)
                status, result = self.request('candidates/status', status='skipped')
                self.assertEqual((status, result['code']), (409, 'candidate_adopted'))
                self.assertEqual(self.cached_candidate()['status'], current)

    def test_library_matched_candidate_cannot_be_manually_skipped(self):
        library = self.papers / 'library'
        library.mkdir()
        (library / 'existing.json').write_text(json.dumps({
            'slug': 'existing', 'title': 'Other title', 'paper_id': 'arXiv:2601.12345',
            'source': {'urls': []}, 'publication': {'verification_sources': []},
        }), encoding='utf-8')
        status, result = self.request('candidates/status', status='skipped')
        self.assertEqual((status, result['code']), (409, 'candidate_adopted'))
        self.assertEqual(self.cached_candidate()['status'], 'new')

    def test_keep_allowed_while_review_queue_active(self):
        with patch.object(reviews, 'load_queue', return_value={
                'schema_version': '1.0', 'jobs': [{'status': 'running'}]}):
            status, result = self.request('keep')
        self.assertEqual(status, 200, result)

    def test_register_rejects_invalid_category_and_active_review(self):
        for category in ('', 'unknown', None, '../other'):
            with self.subTest(category=category):
                status, result = self.request('register', category=category)
                self.assertEqual((status, result['code']), (400, 'bad_request'))
        for state in ('queued', 'running'):
            with self.subTest(state=state), patch.object(reviews, 'load_queue', return_value={
                    'schema_version': '1.0', 'jobs': [{'status': state}]}):
                status, result = self.request('register', category='other')
                self.assertEqual((status, result['code']), (409, 'review_active'))


    def test_register_same_candidate_active_conflict(self):
        entered, release = threading.Event(), threading.Event()
        class Run:
            def events(self):
                entered.set()
                release.wait(5)
                yield {'type': 'cancelled'}
            def cancel(self):
                release.set()
            def terminate(self):
                release.set()
        resolution = {'agent_name': 'paper-searcher', 'configured': False,
                      'error': None, 'selected': None, 'candidates': [], 'notes': []}
        self.addCleanup(release.set)
        with patch.object(roles, 'resolve', return_value=resolution), \
             patch.object(roles, 'agent_definition', return_value=({}, 'Register instructions')), \
             patch.object(research_agent, 'resolve', return_value={'agent': 'omp', 'ready': True}), \
             patch.object(research_agent, 'discovery_command', return_value=['omp']), \
             patch.object(llm, 'launch', return_value=Run()):
            status, result = self.request('register', category='other')
            self.assertEqual(status, 202, result)
            job_id = result['job']['job_id']
            self.assertTrue(entered.wait(3))
            status, result = self.request('register', category='other')
            self.assertEqual((status, result['code']), (409, 'register_active'))
            release.set()
            self.assertTrue(self.http.broker.wait_finished([job_id], 3))

    def run_register(self, pdf=None, oversized=False, fail_index=False, pdf_case='normal'):
        calls, wiki = [], []
        self.keep.write_text('# Keep\n\n## 읽을 논문\n', encoding='utf-8')
        output = {
            'pdf_file': ('paper.pdf' if pdf_case == 'outside' else
                         'out/link/paper.pdf' if pdf_case == 'nested_symlink' else 'out/paper.pdf')
                        if pdf is not None else None,
            'pdf_source_url': 'https://arxiv.org/pdf/2601.12345' if pdf is not None else None,
            'publication': {'venue': 'CVPR', 'status': 'published', 'verified': True,
                            'verification_sources': ['https://example.org/official']},
            'topics': ['vision', 'pose', 'learning'],
            'one_line_summary': 'A concise abstract-based summary.', 'notes': '',
        }

        class Run:
            def events(self):
                yield {'type': 'start', 'agent': 'omp', 'model': None}
                yield {'type': 'result', 'text': json.dumps(output)}
            def cancel(self):
                pass
            def terminate(self):
                pass

        def launch(agent, argv, request):
            calls.append(request)
            if pdf is not None:
                if pdf_case in ('out_symlink', 'nested_symlink'):
                    outside = self.root / ('external-' + pdf_case)
                    outside.mkdir(exist_ok=True)
                    (outside / 'paper.pdf').write_bytes(pdf)
                    link = request.cwd / ('out' if pdf_case == 'out_symlink' else 'out/link')
                    if pdf_case == 'out_symlink' and link.exists():
                        link.rmdir()
                    link.symlink_to(outside, target_is_directory=True)
                    return Run()
                target = request.cwd / ('paper.pdf' if pdf_case == 'outside' else 'out/paper.pdf')
                target.parent.mkdir(parents=True, exist_ok=True)
                if pdf_case == 'symlink':
                    source = request.cwd / 'source.pdf'
                    source.write_bytes(pdf)
                    target.symlink_to(source)
                elif pdf_case == 'directory':
                    target.mkdir()
                else:
                    with target.open('wb') as stream:
                        stream.write(pdf)
                        if oversized:
                            stream.truncate(50 * 1024 * 1024 + 1)
            return Run()

        real_run = subprocess.run
        def run_subprocess(argv, *args, **kwargs):
            if Path(argv[1]).name == 'wiki.py':
                wiki.append(list(argv))
                return subprocess.CompletedProcess(argv, 0, '', '')
            return real_run(argv, *args, **kwargs)

        original_write = discovery._write_text
        failed = False
        def write_text(path, text):
            nonlocal failed
            if fail_index and Path(path) == self.index and not failed:
                failed = True
                raise OSError('injected index publish failure')
            return original_write(path, text)

        resolution = {'agent_name': 'paper-searcher', 'configured': False,
                      'error': None, 'selected': None, 'candidates': [], 'notes': []}
        with patch.object(roles, 'resolve', return_value=resolution), \
             patch.object(roles, 'agent_definition', return_value=({}, 'Register instructions')), \
             patch.object(research_agent, 'resolve', return_value={'agent': 'omp', 'ready': True}), \
             patch.object(research_agent, 'discovery_command', return_value=['omp']), \
             patch.object(llm, 'launch', side_effect=launch), \
             patch.object(subprocess, 'run', side_effect=run_subprocess), \
             patch.object(discovery, '_write_text', side_effect=write_text):
            status, result = self.request('register', category='computer-vision')
            self.assertEqual(status, 202, result)
            job = result['job']
            self.assertEqual(job['kind'], 'discovery.register')
            self.assertEqual(job['role'], 'paper-searcher')
            self.assertTrue(self.http.broker.wait_finished([job['job_id']], 10))
            job = self.http.broker.get(job['job_id'])
        self.assertEqual(calls[0].timeout_s, 600)
        return job, wiki

    def test_register_pdf_and_metadata_only_publish(self):
        original_index = self.index.read_bytes()
        for pdf in (b'%PDF-1.7\nexample', None):
            with self.subTest(pdf=pdf):
                if (self.papers / 'library').exists():
                    shutil.rmtree(self.papers / 'library')
                if (self.papers / 'pdfs').exists():
                    shutil.rmtree(self.papers / 'pdfs')
                self.index.write_bytes(original_index)
                self.put_json('searches/s_0123456789ab.json', session())
                job, wiki = self.run_register(pdf)
                self.assertEqual(job['status'], 'completed', job)
                records = list((self.papers / 'library').glob('*.json'))
                self.assertEqual(len(records), 1)
                record = json.loads(records[0].read_text())
                self.assertEqual(paper_record.validate_record(record), [])
                self.assertTrue(record['publication']['verified'])
                self.assertEqual(record['publication']['verification_sources'], ['https://example.org/official'])
                self.assertEqual(record['one_line_summary'], 'A concise abstract-based summary.')
                self.assertEqual(record['topics'], ['vision', 'pose', 'learning'])
                pdf_path = record['source']['pdf_path']
                if pdf is None:
                    self.assertIsNone(pdf_path)
                    self.assertIn('- PDF: 없음', self.keep.read_text())
                else:
                    self.assertEqual((self.root / pdf_path).read_bytes(), pdf)
                    self.assertIn('- PDF: [원문](pdfs/computer-vision/', self.keep.read_text())
                self.assertIn('| 읽을 예정 | 2026 | A paper |', self.index.read_text())
                self.assertEqual(self.cached_candidate()['status'], 'registered')
                self.assertEqual([cmd[2] for cmd in wiki], ['index', 'log'])
                self.assertIn('--op', wiki[1])
                self.assertEqual(wiki[1][wiki[1].index('--op') + 1], 'ingest')
                self.assertEqual(wiki[1][wiki[1].index('--title') + 1], 'A paper')
                self.assertIn(records[0].relative_to(self.root).as_posix(), wiki[1])

    def test_register_invalid_pdf_falls_back_to_metadata(self):
        original_index = self.index.read_bytes()
        cases = ((b'not a PDF', False, 'normal'), (b'', False, 'normal'),
                 (b'%PDF-1.7\n', True, 'normal'), (b'%PDF-1.7\n', False, 'outside'),
                 (b'%PDF-1.7\n', False, 'symlink'), (b'%PDF-1.7\n', False, 'directory'),
                 (b'%PDF-1.7\n', False, 'out_symlink'), (b'%PDF-1.7\n', False, 'nested_symlink'))
        for pdf, oversized, pdf_case in cases:
            with self.subTest(oversized=oversized, pdf_case=pdf_case, pdf=pdf):
                if (self.papers / 'library').exists():
                    shutil.rmtree(self.papers / 'library')
                self.index.write_bytes(original_index)
                self.put_json('searches/s_0123456789ab.json', session())
                job, wiki = self.run_register(pdf, oversized, pdf_case=pdf_case)
                self.assertEqual(job['status'], 'completed', job)
                records = list((self.papers / 'library').glob('*.json'))
                self.assertEqual(len(records), 1)
                record = json.loads(records[0].read_text())
                self.assertEqual(paper_record.validate_record(record), [])
                self.assertIsNone(record['source']['pdf_path'])
                self.assertFalse(list((self.papers / 'pdfs').rglob('*.pdf')))
                if pdf_case in ('out_symlink', 'nested_symlink'):
                    self.assertEqual((self.root / ('external-' + pdf_case) / 'paper.pdf').read_bytes(), pdf)
                self.assertIn('- PDF: 없음', self.keep.read_text())
                self.assertIn('| 읽을 예정 |', self.index.read_text())
                self.assertEqual(self.cached_candidate()['status'], 'registered')
                self.assertEqual([cmd[2] for cmd in wiki], ['index', 'log'])
                events = [event for _, event in self.http.broker.events(job['job_id'])]
                result = next(event for event in events if event['type'] == 'result')
                self.assertIsNone(result['registration']['pdf_path'])
                self.assertTrue(any(warning.startswith('PDF를 쓰지 않았습니다:')
                                    for warning in result['registration']['warnings']))

    def test_register_publish_failure_rolls_back_all_outputs(self):
        before = self.index.read_bytes()
        job, wiki = self.run_register(b'%PDF-1.7\nexample', fail_index=True)
        self.assertEqual(job['status'], 'failed', job)
        self.assertEqual(self.index.read_bytes(), before)
        self.assertEqual(self.keep.read_text(), '# Keep\n\n## 읽을 논문\n')
        self.assertFalse(list((self.papers / 'library').glob('*.json')))
        self.assertFalse(list((self.papers / 'pdfs').rglob('*.pdf')))
        self.assertEqual(self.cached_candidate()['status'], 'new')
        self.assertEqual(wiki, [])


class DiscoveryCommandTests(unittest.TestCase):
    def test_runner_commands_include_schema_network_and_tools(self):
        schema_path = ROOT / '.scripts/docs/discovery-search.schema.json'
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(research_agent.shutil, 'which', side_effect=lambda name: '/fake/' + name), \
             patch.object(research_agent, 'codex_mcp_servers', return_value=['example']):
            cwd = Path(tmp)
            commands = {
                runner: research_agent.discovery_command(
                    runner, cwd, 'search prompt', schema_path=schema_path,
                    model='test-model', effort='low', timeout_seconds=930)
                for runner in ('claude', 'codex', 'omp')
            }
        claude = commands['claude']
        self.assertEqual(json.loads(claude[claude.index('--json-schema') + 1]),
                         json.loads(schema_path.read_text(encoding='utf-8')))
        settings = json.loads(claude[claude.index('--settings') + 1])
        self.assertEqual(set(settings['sandbox']['network']['allowedDomains']),
                         set(research_agent.DISCOVERY_DOMAINS))
        self.assertTrue({'Read', 'Glob', 'Grep', 'Bash', 'WebSearch', 'WebFetch'}
                        <= set(claude[claude.index('--tools') + 1].split(',')))
        codex = commands['codex']
        self.assertEqual(codex[codex.index('--output-schema') + 1], str(schema_path))
        self.assertEqual(codex[codex.index('--sandbox') + 1], 'workspace-write')
        self.assertIn('sandbox_workspace_write.network_access=true', codex)
        self.assertIn('mcp_servers.example.enabled=false', codex)
        for feature in ('plugins', 'apps', 'hooks'):
            self.assertIn(feature, codex)
        omp = commands['omp']
        self.assertEqual(set(omp[omp.index('--tools') + 1].split(',')),
                         {'read', 'grep', 'glob', 'bash', 'web_search'})
        self.assertIn('--no-skills', omp)
        self.assertIn('--no-context-files', omp)


if __name__ == '__main__':
    unittest.main()
