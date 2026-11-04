import http.client
import json
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.scripts/bin'))
from webui import server, jobs, llm

TERMINAL = {'result', 'error', 'cancelled'}


class FakeRun:
    def __init__(self, wait=False):
        self.agent = 'claude'
        self.cancelled = threading.Event()
        self.release = threading.Event()
        self.wait = wait
        self.cancel_calls = 0

    def events(self):
        yield {'type': 'start', 'agent': self.agent, 'model': None, 'session_id': None}
        if self.wait:
            self.release.wait(3)
        if self.cancelled.is_set():
            yield {'type': 'cancelled'}
        else:
            yield {'type': 'text_delta', 'text': 'OK'}
            yield {'type': 'result', 'text': 'OK', 'cost_usd': None, 'duration_ms': None, 'usage': None}

    def cancel(self):
        self.cancel_calls += 1
        self.cancelled.set()
        self.release.set()


def collect(broker, job_id, after=0):
    result = []
    heartbeats = 0
    for item in broker.events(job_id, after, heartbeat_s=0.05):
        if item is None:
            heartbeats += 1
            if heartbeats > 100:
                raise AssertionError('job event stream did not close')
        else:
            result.append(item)
    return result


class BrokerTests(unittest.TestCase):
    def test_order_replay_terminal_and_record(self):
        broker = jobs.JobBroker()
        def work(ctx):
            ctx.emit({'type': 'start', 'agent': 'claude', 'model': None, 'session_id': None})
            ctx.emit({'type': 'text_delta', 'text': 'OK'})
            ctx.emit({'type': 'result', 'text': 'OK', 'cost_usd': None, 'duration_ms': None, 'usage': None})
        record = broker.submit('agent.ping', {}, work)
        events = collect(broker, record['job_id'])
        self.assertEqual([seq for seq, _ in events], [1, 2, 3])
        self.assertEqual([e['type'] for _, e in events], ['start', 'text_delta', 'result'])
        self.assertEqual(collect(broker, record['job_id'], 1), events[1:])
        self.assertEqual(broker.get(record['job_id'])['status'], 'completed')

    def test_slug_is_only_present_when_supplied(self):
        broker = jobs.JobBroker()
        def work(ctx):
            ctx.emit({'type': 'result', 'text': 'ok'})
        paper = broker.submit('paper.ask', {'slug': 'example', 'role': 'paper-reader'}, work)
        other = broker.submit('agent.ping', {}, work)
        self.assertEqual(paper['slug'], 'example')
        self.assertNotIn('slug', other)
        collect(broker, paper['job_id'])
        collect(broker, other['job_id'])
        self.assertEqual(broker.get(paper['job_id'])['slug'], 'example')
        self.assertNotIn('slug', broker.get(other['job_id']))

    def test_fifo_capacity_queues_third_until_release(self):
        broker = jobs.JobBroker(max_running=2)
        gates = [threading.Event() for _ in range(3)]
        started = [threading.Event() for _ in range(3)]
        def work(i):
            def run(ctx):
                started[i].set()
                gates[i].wait(3)
                ctx.emit({'type': 'result', 'text': str(i), 'cost_usd': None, 'duration_ms': None, 'usage': None})
            return run
        records = [broker.submit('agent.ping', {}, work(i)) for i in range(3)]
        try:
            self.assertTrue(started[0].wait(1))
            self.assertTrue(started[1].wait(1))
            self.assertEqual(broker.get(records[2]['job_id'])['status'], 'queued')
            self.assertFalse(started[2].is_set())
            gates[0].set()
            self.assertTrue(started[2].wait(2))
        finally:
            for gate in gates:
                gate.set()
            for record in records:
                collect(broker, record['job_id'])

    def test_exception_and_missing_terminal_fail(self):
        broker = jobs.JobBroker()
        def raises(ctx):
            raise RuntimeError('deliberate failure')
        for work in (raises, lambda ctx: None):
            with self.subTest(work=work):
                record = broker.submit('agent.ping', {}, work)
                events = collect(broker, record['job_id'])
                self.assertEqual(events[-1][1]['type'], 'error')
                self.assertTrue(events[-1][1]['message'])
                self.assertEqual(broker.get(record['job_id'])['status'], 'failed')

    def test_cancelled_work_returning_without_terminal_is_cancelled(self):
        broker = jobs.JobBroker()
        started = threading.Event()
        def work(ctx):
            started.set()
            ctx.cancelled.wait(3)
        record = broker.submit('agent.ping', {}, work)
        self.assertTrue(started.wait(1))
        self.assertTrue(broker.cancel(record['job_id']))
        events = collect(broker, record['job_id'])
        self.assertEqual(events[-1][1]['type'], 'cancelled')
        self.assertEqual(broker.get(record['job_id'])['status'], 'cancelled')

    def test_concurrent_queued_cancel_is_atomic(self):
        from collections import deque

        broker = jobs.JobBroker(max_running=1)
        started, release, queued_ran = threading.Event(), threading.Event(), threading.Event()
        removed, second_started, second_finished = threading.Event(), threading.Event(), threading.Event()
        outcomes, errors = {}, []

        def blocking(ctx):
            started.set()
            release.wait(3)
            ctx.emit({'type': 'result', 'text': 'done'})

        first = broker.submit('agent.ping', {}, blocking)
        self.assertTrue(started.wait(1))
        queued = broker.submit('agent.ping', {}, lambda ctx: queued_ran.set())

        class ControlledPending(deque):
            def remove(self, value):
                super().remove(value)
                removed.set()
                if not second_started.wait(1):
                    raise AssertionError('second cancellation did not start')

        broker._pending = ControlledPending(broker._pending)
        original_emit = broker._emit

        def controlled_emit(job_id, event):
            # The old implementation published via _emit after releasing the lock.
            # Holding it here forces the second cancel into the removal/publication
            # gap, where its second deque.remove raised ValueError. The fixed path
            # publishes while still holding the lock and never enters this gap.
            if job_id == queued['job_id'] and event.get('type') == 'cancelled':
                if not second_finished.wait(1):
                    raise AssertionError('second cancellation did not finish')
            return original_emit(job_id, event)

        def cancel(label):
            try:
                if label == 'second':
                    second_started.set()
                outcomes[label] = broker.cancel(queued['job_id'])
            except Exception as exc:
                errors.append(exc)
            finally:
                if label == 'second':
                    second_finished.set()

        threads = [threading.Thread(target=cancel, args=(name,)) for name in ('first', 'second')]
        try:
            with patch.object(broker, '_emit', side_effect=controlled_emit):
                threads[0].start()
                self.assertTrue(removed.wait(1))
                threads[1].start()
                for thread in threads:
                    thread.join(2)
                self.assertFalse(any(thread.is_alive() for thread in threads))
                self.assertEqual(errors, [])
                self.assertEqual(outcomes, {'first': True, 'second': False})
                self.assertEqual([e['type'] for _, e in collect(broker, queued['job_id'])], ['cancelled'])
                self.assertFalse(queued_ran.is_set())
        finally:
            second_started.set()
            second_finished.set()
            release.set()
            for thread in threads:
                if thread.ident is not None:
                    thread.join(2)
            collect(broker, first['job_id'])
        self.assertFalse(queued_ran.is_set())

    def test_accepted_cancel_wins_over_late_result_or_error(self):
        for terminal in ({'type': 'result', 'text': 'late'},
                         {'type': 'error', 'message': 'late', 'retryable': False}):
            with self.subTest(terminal=terminal):
                broker = jobs.JobBroker()
                started, release = threading.Event(), threading.Event()
                def work(ctx):
                    started.set()
                    release.wait(3)
                    ctx.emit(terminal)
                record = broker.submit('agent.ping', {}, work)
                try:
                    self.assertTrue(started.wait(1))
                    self.assertTrue(broker.cancel(record['job_id']))
                finally:
                    release.set()
                events = collect(broker, record['job_id'])
                self.assertEqual([e['type'] for _, e in events], ['cancelled'])
                self.assertEqual(broker.get(record['job_id'])['status'], 'cancelled')

    def test_overflow_reports_gap_before_retained_events(self):
        broker = jobs.JobBroker(max_events=2)
        finished = threading.Event()
        def work(ctx):
            for event in ({'type': 'start'}, {'type': 'text_delta', 'text': 'A'},
                          {'type': 'text_delta', 'text': 'B'}, {'type': 'result', 'text': 'AB'}):
                ctx.emit(event)
            finished.set()
        record = broker.submit('agent.ping', {}, work)
        self.assertTrue(finished.wait(1))
        events = collect(broker, record['job_id'])
        self.assertEqual(events, [(2, {'type': 'gap', 'missed_from': 1, 'missed_to': 2}),
                                  (3, {'type': 'text_delta', 'text': 'B'}),
                                  (4, {'type': 'result', 'text': 'AB'})])


class SSETests(unittest.TestCase):
    def setUp(self):
        self.broker = jobs.JobBroker()
        self.server = server.make_server(0, broker=self.broker, csrf_token='token')
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.host = f'127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)

    def request(self, method, path, data=None, headers=None):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=4)
        conn.request(method, path, body=data, headers=headers or {})
        response = conn.getresponse()
        status, body = response.status, response.read()
        conn.close()
        return status, body

    def post(self, path, body):
        return self.request('POST', path, json.dumps(body), {'Origin': 'http://' + self.host,
            'X-CSRF-Token': 'token', 'Content-Type': 'application/json'})

    def submit(self):
        status, data = self.post('/api/jobs', {'kind': 'agent.ping', 'agent': 'claude'})
        self.assertEqual(status, 202)
        return json.loads(data)['job']['job_id']

    def frames(self, path, headers=None):
        status, body = self.request('GET', path, headers=headers)
        self.assertEqual(status, 200)
        frames = []
        for frame in body.decode().split('\n\n'):
            if not frame or frame.startswith(':'):
                continue
            fields = dict(line.split(': ', 1) for line in frame.splitlines())
            frames.append((int(fields['id']), fields['event'], json.loads(fields['data'])))
        return frames

    def test_sse_frames_replay_and_close(self):
        with patch.object(llm, 'start', return_value=FakeRun()):
            job_id = self.submit()
            path = f'/api/jobs/{job_id}/events'
            frames = self.frames(path)
            self.assertEqual([frame[0] for frame in frames], [1, 2, 3])
            self.assertEqual([frame[1] for frame in frames], ['start', 'text_delta', 'result'])
            self.assertTrue(all(kind == event['type'] for _, kind, event in frames))
            self.assertEqual(self.frames(path, {'Last-Event-ID': '1'}), frames[1:])
            self.assertEqual(self.frames(path + '?after=2'), frames[2:])

    def test_cancel_once_calls_run_and_finishes_cancelled(self):
        run = FakeRun(wait=True)
        with patch.object(llm, 'start', return_value=run):
            job_id = self.submit()
            iterator = self.broker.events(job_id, heartbeat_s=0.05)
            for _ in range(40):
                event = next(iterator)
                if event is not None:
                    break
            else:
                self.fail('job did not emit its start event')
            iterator.close()
            status, _ = self.post(f'/api/jobs/{job_id}/cancel', {})
            self.assertEqual(status, 202)
            events = collect(self.broker, job_id)
            self.assertEqual(events[-1][1]['type'], 'cancelled')
            self.assertEqual(run.cancel_calls, 1)
            self.assertEqual(self.broker.get(job_id)['status'], 'cancelled')
            status, data = self.post(f'/api/jobs/{job_id}/cancel', {})
            self.assertEqual(status, 409)
            self.assertEqual(json.loads(data)['code'], 'already_finished')

    def test_bad_kind_and_agent_are_rejected(self):
        for payload in ({'kind': 'unknown'}, {'kind': 'agent.ping', 'agent': 'unknown'},
                        {'kind': []}, {'kind': {}}, {'kind': 'agent.ping', 'agent': []}):
            status, data = self.post('/api/jobs', payload)
            self.assertEqual(status, 400)
            self.assertEqual(json.loads(data)['code'], 'bad_request')

    def test_overflow_gap_is_an_sse_frame(self):
        self.broker = self.server.broker = jobs.JobBroker(max_events=2)
        finished = threading.Event()
        def work(ctx):
            for event in ({'type': 'start'}, {'type': 'text_delta', 'text': 'A'},
                          {'type': 'text_delta', 'text': 'B'}, {'type': 'result', 'text': 'AB'}):
                ctx.emit(event)
            finished.set()
        job = self.broker.submit('agent.ping', {}, work)
        self.assertTrue(finished.wait(1))
        frames = self.frames(f"/api/jobs/{job['job_id']}/events")
        self.assertEqual(frames[0], (2, 'gap', {'type': 'gap', 'missed_from': 1, 'missed_to': 2}))
        self.assertEqual([frame[1] for frame in frames], ['gap', 'text_delta', 'result'])

    def test_stream_cap_rejects_then_releases_slot(self):
        self.server.max_streams = 1
        started, release = threading.Event(), threading.Event()
        def work(ctx):
            ctx.emit({'type': 'start'})
            started.set()
            release.wait(3)
            ctx.emit({'type': 'result', 'text': 'done'})
        job = self.broker.submit('agent.ping', {}, work)
        self.assertTrue(started.wait(1))
        path = f"/api/jobs/{job['job_id']}/events"
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=4)
        try:
            conn.request('GET', path)
            response = conn.getresponse()
            self.assertEqual(response.status, 200)
            status, data = self.request('GET', path)
            self.assertEqual((status, json.loads(data)['code']), (503, 'too_many_streams'))
            release.set()
            response.read()
            self.assertEqual(self.request('GET', path)[0], 200)
        finally:
            release.set()
            conn.close()

    def test_unavailable_is_nonretryable_failure(self):
        with patch.object(llm, 'start', side_effect=llm.LLMUnavailable('not ready')):
            job_id = self.submit()
            events = collect(self.broker, job_id)
        self.assertEqual(events[-1][1]['type'], 'error')
        self.assertFalse(events[-1][1]['retryable'])
        self.assertEqual(self.broker.get(job_id)['status'], 'failed')
