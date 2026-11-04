import io
import os
import signal
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '.scripts/bin'))
from webui import llm
import research_agent

FIXTURES = ROOT / '.scripts/tests/fixtures/webui'
TERMINAL = {'result', 'error', 'cancelled'}


class FakeProcess:
    """Popen-compatible process with real file descriptors and scripted output."""
    def __init__(self, output, returncode=0, hold=False):
        self.pid = 43121
        self.returncode = None if hold else returncode
        self.exit_code = returncode
        self.hold = hold
        self.done = threading.Event()
        read_fd, self.write_fd = os.pipe()
        self.stdout = os.fdopen(read_fd, 'r', encoding='utf-8')
        self.stderr = io.StringIO('fixture process failed')
        os.write(self.write_fd, output.encode())
        if not hold:
            os.close(self.write_fd)
            self.done.set()

    def finish(self):
        if not self.done.is_set():
            self.returncode = self.exit_code
            os.close(self.write_fd)
            self.done.set()

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        if not self.done.wait(timeout):
            raise subprocess.TimeoutExpired('fixture', timeout)
        return self.returncode

    def terminate(self):
        self.finish()

    def kill(self):
        self.finish()

    def send_signal(self, sig):
        self.finish()


class LLMTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def request(self, agent, timeout=2):
        return llm.LLMRequest(prompt='Reply with exactly: OK', cwd=self.root,
                              agent=agent, timeout_s=timeout)

    def run_fixture(self, agent, text, returncode=0, malformed=None):
        process = FakeProcess(text, returncode)
        with patch.object(research_agent, 'resolve', return_value={'agent': agent, 'ready': True}), \
             patch.object(research_agent, 'probe', return_value={'agent': agent, 'ready': True}), \
             patch.object(research_agent, 'omp_model_roles', return_value={}), \
             patch.object(research_agent.shutil, 'which', return_value='/fake/' + agent), \
             patch.object(llm.subprocess, 'Popen', return_value=process):
            run = llm.start(self.request(agent), self.root)
            events = list(run.events())
            if malformed is not None:
                self.assertEqual(run.malformed_lines, malformed)
            return events

    def assert_single_terminal(self, events, kind):
        self.assertEqual(events[0]['type'], 'start')
        terminals = [event for event in events if event['type'] in TERMINAL]
        self.assertEqual(len(terminals), 1)
        self.assertEqual(terminals[0]['type'], kind)
        self.assertIs(events[-1], terminals[0])
        return terminals[0]

    def test_real_stream_samples_normalize_text(self):
        for agent in ('claude', 'codex', 'omp'):
            with self.subTest(agent=agent):
                fixture = FIXTURES / f'{agent}-ok.jsonl'
                if not fixture.exists():
                    self.skipTest(f'missing real {agent} stream capture')
                events = self.run_fixture(agent, fixture.read_text())
                result = self.assert_single_terminal(events, 'result')
                deltas = ''.join(e['text'] for e in events if e['type'] == 'text_delta')
                messages = [e['text'] for e in events if e['type'] == 'message']
                self.assertEqual(deltas or ''.join(messages), result['text'])
                self.assertEqual(result['text'], 'OK')
                if agent == 'claude':
                    self.assertIsInstance(result['cost_usd'], float)

    def test_malformed_lines_are_skipped(self):
        sample = (FIXTURES / 'malformed.jsonl').read_text() + (FIXTURES / 'codex-ok.jsonl').read_text()
        events = self.run_fixture('codex', sample, malformed=2)
        self.assertEqual(self.assert_single_terminal(events, 'result')['text'], 'OK')

    def test_nonzero_without_result_is_error(self):
        events = self.run_fixture('codex', (FIXTURES / 'nonzero.jsonl').read_text(), 1)
        result = self.assert_single_terminal(events, 'error')
        self.assertIn('fixture process failed', result['message'])

    def test_error_kind_distinguishes_explicit_limits_from_other_errors(self):
        samples = (
            ('claude', '{"type":"result","is_error":true,"result":"Rate limit exceeded"}\n', 'usage_limit'),
            ('codex', '{"type":"turn.failed","error":{"message":"quota exceeded"}}\n', 'usage_limit'),
            ('omp', '{"type":"error","message":"usage limit exceeded"}\n', 'usage_limit'),
            ('codex', '{"type":"turn.failed","error":{"message":"authentication failed"}}\n', 'auth'),
            ('codex', '{"type":"turn.failed","error":{"message":"unexpected failure"}}\n', 'other'),
        )
        for agent, sample, expected in samples:
            with self.subTest(agent=agent, expected=expected):
                event = self.assert_single_terminal(self.run_fixture(agent, sample, 1), 'error')
                self.assertEqual(event['kind'], expected)

    def test_timeout_is_retryable_error(self):
        process = FakeProcess('', hold=True)
        def signal_group(pid, sig):
            process.finish()
        try:
            with patch.object(research_agent, 'resolve', return_value={'agent': 'codex', 'ready': True}), \
                 patch.object(research_agent, 'probe', return_value={'agent': 'codex', 'ready': True}), \
                 patch.object(research_agent.shutil, 'which', return_value='/fake/codex'), \
                 patch.object(llm.subprocess, 'Popen', return_value=process), \
                 patch.object(os, 'killpg', side_effect=signal_group):
                run = llm.start(self.request('codex', timeout=0.1), self.root)
                events = list(run.events())
            self.assertTrue(self.assert_single_terminal(events, 'error')['retryable'])
        finally:
            process.finish()

    def test_cancel_sends_sigint_and_wins_over_late_result(self):
        sample = (FIXTURES / 'codex-ok.jsonl').read_text()
        process = FakeProcess(sample, hold=True)
        try:
            with patch.object(research_agent, 'resolve', return_value={'agent': 'codex', 'ready': True}), \
                 patch.object(research_agent, 'probe', return_value={'agent': 'codex', 'ready': True}), \
                 patch.object(research_agent.shutil, 'which', return_value='/fake/codex'), \
                 patch.object(llm.subprocess, 'Popen', return_value=process), \
                 patch.object(os, 'killpg', side_effect=lambda pid, sig: process.finish()) as killpg:
                run = llm.start(self.request('codex'), self.root)
                run.cancel()
                events = list(run.events())
            self.assert_single_terminal(events, 'cancelled')
            killpg.assert_any_call(process.pid, signal.SIGINT)
        finally:
            process.finish()

    def test_cancel_after_fallback_start_of_exited_process(self):
        process = FakeProcess('')
        with patch.object(research_agent, 'resolve', return_value={'agent': 'codex', 'ready': True}), \
             patch.object(research_agent, 'stream_command', return_value=['fixture']), \
             patch.object(llm.subprocess, 'Popen', return_value=process):
            run = llm.start(self.request('codex'), self.root)
            iterator = run.events()
            first = next(iterator)
            run.cancel()
            events = [first, *iterator]
        self.assert_single_terminal(events, 'cancelled')

    @unittest.skipUnless(all(hasattr(os, name) for name in
                             ('fork', 'waitid', 'P_PID', 'WEXITED', 'WNOHANG', 'WNOWAIT')),
                         'requires fork and non-reaping waitid (macOS Python 3.13+)')
    def test_exited_parent_with_stdout_holding_grandchild_drains_cancels_and_times_out(self):
        script = self.root / 'tree.py'
        pidfile = self.root / 'grandchild.pid'
        script.write_text(
            'import os, sys, time\n'
            'child = os.fork()\n'
            'if child == 0:\n'
            '    time.sleep(60)\n'
            '    os._exit(0)\n'
            'open(sys.argv[1], "w").write(str(child))\n'
            'print("{\\"type\\":\\"thread.started\\",\\"thread_id\\":\\"test\\"}", flush=True)\n'
            'os._exit(0)\n'
        )
        wait_flags = os.WEXITED | os.WNOHANG | os.WNOWAIT
        real_killpg = os.killpg
        for mode in ('drain', 'cancel', 'timeout'):
            with self.subTest(mode=mode):
                pidfile.unlink(missing_ok=True)
                # Launch and establish readiness before start() arms any watchdog.
                process = subprocess.Popen([sys.executable, str(script), str(pidfile)],
                    cwd=self.root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding='utf-8', start_new_session=True)
                child = None
                worker = None
                observations = []
                try:
                    deadline = time.monotonic() + 5
                    while time.monotonic() < deadline:
                        if pidfile.exists() and os.waitid(os.P_PID, process.pid, wait_flags) is not None:
                            break
                        threading.Event().wait(0.02)
                    else:
                        self.fail('fixture leader did not exit with child PID available')
                    child = int(pidfile.read_text())
                    os.kill(child, 0)

                    def checked_killpg(pgid, sig):
                        try:
                            os.waitid(os.P_PID, process.pid, wait_flags)
                            owned = True
                        except ChildProcessError:
                            owned = False
                        observations.append((sig, owned))
                        if owned:
                            return real_killpg(pgid, sig)

                    results, failures = [], []
                    def consume(run):
                        try:
                            results.extend(run.events())
                        except BaseException as exc:
                            failures.append(exc)

                    schedule = ((0.6, signal.SIGTERM), (1.0, signal.SIGKILL), (1.5, None))
                    if mode == 'timeout':
                        schedule = ((3.0, signal.SIGTERM), (3.5, signal.SIGKILL), (4.0, None))
                    with patch.object(research_agent, 'resolve', return_value={'agent': 'codex', 'ready': True}), \
                         patch.object(research_agent, 'stream_command', return_value=['fixture']), \
                         patch.object(llm.subprocess, 'Popen', return_value=process), \
                         patch.object(os, 'killpg', side_effect=checked_killpg), \
                         patch.object(llm, 'DRAIN_SCHEDULE', schedule), \
                         patch.object(llm, 'READ_POLL_S', 0.02), \
                         patch.object(llm, 'CANCEL_TERM_AFTER_S', 0.3), \
                         patch.object(llm, 'CANCEL_KILL_AFTER_S', 0.6), \
                         patch.object(llm, 'TIMEOUT_KILL_AFTER_S', 0.3):
                        run = llm.start(self.request('codex', 1.0 if mode == 'timeout' else 5), self.root)
                        if mode == 'cancel':
                            run.cancel()
                        worker = threading.Thread(target=consume, args=(run,), daemon=True)
                        worker.start()
                        worker.join(5)
                        self.assertFalse(worker.is_alive(), 'event iterator did not terminate')
                        self.assertEqual(failures, [])
                        terminal = self.assert_single_terminal(results, 'cancelled' if mode == 'cancel' else 'error')
                        if mode == 'timeout':
                            self.assertTrue(terminal['retryable'])
                        self.assertTrue(observations, 'expected a group signal')
                        threading.Event().wait(0.1)
                        self.assertTrue(all(owned for _, owned in observations), observations)

                    # An orphan may be dead but remain a zombie until its adopter reaps it.
                    deadline = time.monotonic() + 2
                    while True:
                        state = subprocess.run(['ps', '-o', 'stat=', '-p', str(child)],
                                               capture_output=True, text=True, timeout=1).stdout.strip()
                        if not state or state.startswith('Z'):
                            break
                        if time.monotonic() >= deadline:
                            self.fail(f'grandchild {child} is still running: {state}')
                        threading.Event().wait(0.05)
                    child = None
                finally:
                    if child is not None:
                        try:
                            os.kill(child, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                    if worker is not None:
                        worker.join(2)
                    if process.stderr:
                        process.stderr.close()

    def test_claude_stream_command_invariants(self):
        with patch.object(research_agent.shutil, 'which', return_value='/fake/claude'):
            command = research_agent.stream_command('claude', 'OK', cwd=self.root, system=None,
                tools=(), model=None, timeout_seconds=120, root=self.root)
        self.assertNotIn('--bare', command)
        self.assertIn('--include-partial-messages', command)
        self.assertEqual(command[command.index('--output-format') + 1], 'stream-json')

    def test_stream_commands_forward_model_effort_and_delimit_prompt(self):
        with patch.object(research_agent.shutil, 'which', side_effect=lambda name: '/fake/' + name):
            for agent, model in (('claude', 'model-a'), ('codex', 'model-b'),
                                 ('omp', 'vendor/model-c:high')):
                with self.subTest(agent=agent):
                    command = research_agent.stream_command(
                        agent, 'PROMPT', cwd=self.root, system=None, tools=(), model=model,
                        effort='high', timeout_seconds=120, root=self.root)
                    self.assertEqual(command[-2:], ['--', 'PROMPT'])
                    flag = '-m' if agent == 'codex' else '--model'
                    self.assertEqual(command[command.index(flag) + 1], model)
                    if agent == 'claude':
                        self.assertEqual(command[command.index('--effort') + 1], 'high')
                    elif agent == 'codex':
                        self.assertIn('model_reasoning_effort="high"', command)
