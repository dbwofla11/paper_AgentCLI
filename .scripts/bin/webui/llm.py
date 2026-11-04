"""Streaming LLM runner: run the user's own CLI and normalize its JSONL stream.

`start()` resolves the agent with `research_agent.resolve()`, builds the argv with
`research_agent.stream_command()` (forwarding `LLMRequest.model`/`effort`), and launches it in its
own process group; `launch()` does the same for a prebuilt argv such as
`research_agent.verify_command()`. `LLMRun.events()` reads stdout line by line and yields normalized
events: `start` first, then any of `text_delta`, `message`, `tool_use`, `retry`, and exactly one
terminal `result`, `error` (with `kind`, see below), or `cancelled`.

Run completion follows the stdout stream, not the direct child: when the CLI exits while a
descendant still holds stdout, `DRAIN_SCHEDULE` gives the stream 5 s, then sends the process group
SIGTERM and SIGKILL, and stops reading after a final grace so the run always ends. Timeout and
cancellation signal the whole process group. Cancellation requested before the terminal event is
published always yields `cancelled`.

Process-group ownership: the CLI leads its own group (pgid = its pid). Its exit is observed with
`os.waitid(..., WNOWAIT)`, which leaves it a zombie, so neither its pid nor the pgid can be reused
while signals may still be sent. Signalling and reaping share one lock; the leader is reaped exactly
once, after the terminal is decided (cancelled and timed-out runs first SIGKILL the group), and no
signal is sent after that. An iterator closed early finishes the same lifecycle in the background:
cancel, escalate, then reap. Where `os.waitid` is unavailable (macOS before Python 3.13) or cannot
observe the child, exit is observed with `Popen.poll()`, which reaps; the group is then signalled
only while the leader is still running, so a descendant holding stdout after the leader exits is
not killed, only stopped being read after `DRAIN_SCHEDULE`.

Raw event mapping (observed: claude 2.1.231, codex-cli 0.162.1, omp 18.16.0; [docs] = taken from
the CLI's documentation, not seen in a captured run):

claude (`--output-format stream-json --verbose --include-partial-messages`)
  system/init                                    -> start (model, session_id)
  system/api_retry [docs]                        -> retry (attempt, retry_delay_ms)
  stream_event content_block_delta/text_delta    -> text_delta
  assistant (text blocks)                        -> message (one per assistant event)
  assistant (tool_use blocks) [docs]             -> tool_use (name, summary of a single input field)
  result, subtype success and is_error false     -> result (result, total_cost_usd, duration_ms, usage;
                                                    structured_output when --json-schema was used)
  result, otherwise                              -> error (retryable for HTTP 429/5xx/529)
  rate_limit_event, rate_limit_info.status "rejected" -> no event; marks a later error usage_limit
  ignored: system/hook_started, system/hook_response, system/status, other rate_limit_event, user,
           other stream_event types; events with parent_tool_use_id (subagent output)

codex (`exec --json`; no text deltas, the CLI emits completed items only)
  thread.started                                 -> start (session_id = thread_id)
  item.completed agent_message                   -> message; the last one is the result text
  item.started|completed command_execution, mcp_tool_call, web_search, file_change [docs]
                                                 -> tool_use (once per item id)
  turn.completed                                 -> result at exit (usage summed; cost unknown)
  turn.failed [docs]                             -> error (error.message)
  error "Reconnecting... N/M" [docs]             -> retry (attempt N, delay unknown)
  error, other [docs]                            -> error when no turn completed
  item.completed error                           -> no event (config warnings); its text only feeds
                                                    the error `kind`
  ignored: turn.started, reasoning, todo_list, item.updated agent_message

omp (`-p --mode json`; no cost-free result event, the final assistant message is the answer)
  session                                        -> start (session_id = id, model = requested)
  message_update assistantMessageEvent.text_delta -> text_delta
  message_end, role assistant                    -> message; usage and usage.cost.total summed
  tool_execution_start [docs]                    -> tool_use (toolName, intent or one args field)
  auto_retry_start [docs]                        -> retry (attempt, delayMs)
  exit 0, last assistant stopReason not error/aborted -> result (its text)
  last assistant stopReason error|aborted        -> error (errorMessage)
  error [docs]                                   -> error message when the run fails
  ignored: agent_start, turn_start, turn_end, message_start, agent_end, user messages, other
           message_update kinds (thinking, tool call deltas)

Duration for codex and omp is measured wall-clock time; claude reports its own `duration_ms`.
Lines that are not JSON objects, or whose shape breaks normalization, are skipped and counted in
`LLMRun.malformed_lines`.

Error `kind` (a heuristic over explicit signals only; see `classify_error_text`):
  timeout      our watchdog ended the run.
  usage_limit  claude: an `is_error` result with `api_error_status` 429, or a preceding
               rate_limit_event whose status is "rejected"; any CLI: the failure text (result text,
               turn.failed message, codex error item/event, omp errorMessage/error event, or stderr
               tail) matches USAGE_LIMIT_PATTERN, case-insensitive:
               `usage limit`, `rate limit` / `rate_limit` / `rate-limit`, `quota`,
               `too many requests`, `hit your limit`, `limit reached`.
  auth         `api_error_status` 401/403, or the text matches AUTH_PATTERN, case-insensitive:
               `authenticat`, `unauthori[sz]ed`, `not logged in`, `please log in`, `login required`,
               `invalid api key`, `invalid x-api-key`, `oauth token`.
  process      the CLI exited non-zero without a recognizable failure event.
  other        everything else.
"""
from __future__ import annotations

import codecs
import collections
import json
import os
import re
import selectors
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import research_agent

CANCEL_TERM_AFTER_S = 5
CANCEL_KILL_AFTER_S = 10
TIMEOUT_KILL_AFTER_S = 5
STDERR_TAIL_CHARS = 2000
SUMMARY_CHARS = 200
RETRYABLE_HTTP = {408, 409, 429, 500, 502, 503, 504, 529}
SUMMARY_KEYS = ('command', 'cmd', 'file_path', 'path', 'pattern', 'query', 'url', 'description', 'prompt')
CODEX_RECONNECT = re.compile(r'Reconnecting\.*\s*(\d+)\s*/\s*(\d+)')
CODEX_TOOL_ITEMS = {'command_execution', 'mcp_tool_call', 'web_search', 'file_change'}
USAGE_LIMIT_PATTERN = re.compile(
    r'usage limit|rate[ _-]limit|quota|too many requests|hit your limit|limit reached', re.IGNORECASE)
AUTH_PATTERN = re.compile(
    r'authenticat|unauthori[sz]ed|not logged in|please log in|login required|invalid api key|'
    r'invalid x-api-key|oauth token', re.IGNORECASE)
ERROR_KINDS = ('usage_limit', 'auth', 'timeout', 'process', 'other')
CLI_TIMEOUT_GRACE_S = 30
# Seconds after the CLI exits: (deadline, signal to the group); None stops reading stdout.
DRAIN_SCHEDULE = ((5.0, signal.SIGTERM), (7.0, signal.SIGKILL), (8.0, None))
READ_POLL_S = 0.2
READ_CHUNK = 65536
LEADER_POLL_S = 0.05
_WAITID_NAMES = ('waitid', 'P_PID', 'WEXITED', 'WNOHANG', 'WNOWAIT', 'CLD_EXITED')
CAN_OBSERVE_WITHOUT_REAP = all(hasattr(os, name) for name in _WAITID_NAMES)


def classify_error_text(*texts: object) -> str:
    """`usage_limit`, `auth` or `other` from failure texts; explicit phrases only (see module doc)."""
    joined = '\n'.join(str(text) for text in texts if text)
    if USAGE_LIMIT_PATTERN.search(joined):
        return 'usage_limit'
    if AUTH_PATTERN.search(joined):
        return 'auth'
    return 'other'


class LLMUnavailable(RuntimeError):
    """The requested agent CLI is not installed, not logged in, or could not be launched."""


@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    cwd: Path
    agent: str | None = None
    system: str | None = None
    tools: tuple[str, ...] = ()
    timeout_s: int = 600
    model: str | None = None
    effort: str | None = None


def start(request: LLMRequest, root: Path) -> LLMRun:
    status = research_agent.resolve(root, request.agent)
    if not status.get('ready') or not status.get('agent'):
        raise LLMUnavailable(status.get('reason') or '에이전트 연결이 준비되지 않았습니다.')
    agent = status['agent']
    # The CLI's own limit (omp --max-time) is a backstop after ours, so a timeout is always
    # reported by the watchdog as a retryable error rather than as an opaque non-zero exit.
    try:
        argv = research_agent.stream_command(
            agent, request.prompt, cwd=request.cwd, system=request.system, tools=tuple(request.tools),
            model=request.model, effort=request.effort,
            timeout_seconds=request.timeout_s + CLI_TIMEOUT_GRACE_S, root=root)
    except ValueError as error:
        raise LLMUnavailable(str(error)) from error
    return launch(agent, argv, request)


def launch(agent: str, argv: list[str], request: LLMRequest) -> LLMRun:
    """Run a prebuilt JSONL-streaming argv (e.g. `research_agent.verify_command`) under the same
    lifecycle and normalization as `start`. The caller has already checked readiness."""
    try:
        proc = subprocess.Popen(
            argv, cwd=str(request.cwd), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace', bufsize=1,
            start_new_session=True)
    except OSError as error:
        raise LLMUnavailable(f'{agent} CLI를 실행하지 못했습니다: {error}') from error
    return LLMRun(agent, proc, request)


def _clip(text: object, limit: int = SUMMARY_CHARS) -> str:
    value = ' '.join(str(text).split()) if text is not None else ''
    return value if len(value) <= limit else value[:limit - 1] + '…'


def _summary(arguments: object) -> str:
    """One identifying field of a tool input, never the full input."""
    if isinstance(arguments, str):
        return _clip(arguments)
    if isinstance(arguments, dict):
        for key in SUMMARY_KEYS:
            if isinstance(arguments.get(key), str) and arguments[key].strip():
                return _clip(arguments[key])
    return ''


def _add_usage(total: dict, usage: object) -> None:
    if isinstance(usage, dict):
        for key, value in usage.items():
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                total[key] = total.get(key, 0) + value


class LLMRun:
    def __init__(self, agent: str, proc: subprocess.Popen, request: LLMRequest):
        self.agent = agent
        self.malformed_lines = 0
        self._proc = proc
        self._request = request
        self._started_at = time.monotonic()
        self._lock = threading.Lock()
        self._cancelled = False
        self._timed_out = False
        self._terminal_decided = False
        # _proc_lock serializes every group signal with observing and reaping the leader.
        self._proc_lock = threading.Lock()
        self._observable = CAN_OBSERVE_WITHOUT_REAP
        self._exit_code: int | None = None
        self._reaped = False
        self._done = threading.Event()
        self._consumed = False
        self._start_sent = False
        self._model: str | None = request.model
        self._session_id: str | None = None
        self._result: dict | None = None
        self._failure: dict | None = None
        # error `kind` signals: claude api_error_status / rejected rate_limit_event, codex error items
        self._api_status: object = None
        self._rate_limited = False
        self._error_texts: list[str] = []
        # codex/omp accumulators
        self._last_text = ''
        self._completed = False
        self._stream_error: str | None = None
        self._usage: dict = {}
        self._cost: float | None = None
        self._last_assistant: dict | None = None
        self._seen_items: set[str] = set()
        self._stderr: collections.deque[str] = collections.deque()
        self._stderr_chars = 0
        self._stderr_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._stderr_thread.start()
        threading.Thread(target=self._watch_timeout, daemon=True).start()
        self._normalize = {'claude': self._claude, 'codex': self._codex, 'omp': self._omp}[agent]

    # ---- process control -------------------------------------------------------------------

    def _poll_leader(self) -> int | None:
        """Leader exit code or None while it runs. Caller holds _proc_lock. Reaps only in fallback."""
        if self._exit_code is not None:
            return self._exit_code
        if self._observable:
            try:
                info = os.waitid(os.P_PID, self._proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
            except OSError:
                self._observable = False
            else:
                if info is None:
                    return None
                self._exit_code = info.si_status if info.si_code == os.CLD_EXITED else -info.si_status
                return self._exit_code
        code = self._proc.poll()
        if code is not None:
            self._reaped = True
            self._exit_code = code
        return code

    def _leader_exit_code(self) -> int | None:
        with self._proc_lock:
            return self._poll_leader()

    def _wait_leader(self, seconds: float | None = None) -> int | None:
        deadline = None if seconds is None else time.monotonic() + seconds
        while True:
            code = self._leader_exit_code()
            if code is not None or (deadline is not None and time.monotonic() >= deadline):
                return code
            time.sleep(LEADER_POLL_S)

    def _signal(self, sig: int) -> None:
        with self._proc_lock:
            self._poll_leader()
            if self._reaped:
                return
            try:
                os.killpg(self._proc.pid, sig)
            except (ProcessLookupError, PermissionError):
                pass

    def _reap(self, stop_group: bool) -> None:
        """End of the lifecycle; the leader must have exited. No signal is sent after this."""
        with self._proc_lock:
            if not self._reaped:
                if stop_group:
                    try:
                        os.killpg(self._proc.pid, signal.SIGKILL)
                    except (ProcessLookupError, PermissionError):
                        pass
                self._proc.wait()
                self._reaped = True
        self._done.set()

    def _watch_timeout(self) -> None:
        if self._done.wait(self._request.timeout_s):
            return
        with self._lock:
            if self._cancelled or self._terminal_decided:
                return
            self._timed_out = True
        self._signal(signal.SIGTERM)
        if not self._done.wait(TIMEOUT_KILL_AFTER_S):
            self._signal(signal.SIGKILL)

    def _escalate(self, ended) -> None:
        """SIGTERM, then SIGKILL the group unless `ended(seconds)` reports the end in time."""
        began = time.monotonic()
        for after, sig in ((CANCEL_TERM_AFTER_S, signal.SIGTERM), (CANCEL_KILL_AFTER_S, signal.SIGKILL)):
            if ended(max(0.0, began + after - time.monotonic())):
                return
            self._signal(sig)

    def cancel(self) -> None:
        with self._lock:
            if self._cancelled or self._terminal_decided:
                return
            self._cancelled = True
        self._signal(signal.SIGINT)
        if not self._done.is_set():
            threading.Thread(target=self._escalate, args=(self._done.wait,), daemon=True).start()

    def terminate(self) -> None:
        """SIGKILL the CLI's process group now (e.g. server shutdown, where the 5–10 s cancel
        escalation is too slow). Holds the process lock and is a no-op once the leader was reaped,
        so a reused pid/pgid is never signalled. Call `cancel()` first so the run ends `cancelled`."""
        self._signal(signal.SIGKILL)

    def _abandon(self) -> None:
        """Lifecycle of an iterator closed before its terminal: cancel, escalate, reap."""
        with self._lock:
            self._cancelled = True
            self._terminal_decided = True
        self._signal(signal.SIGINT)
        self._escalate(lambda seconds: self._wait_leader(seconds) is not None)
        self._wait_leader()
        self._reap(stop_group=True)

    def _drain_stderr(self) -> None:
        stream = self._proc.stderr
        if stream is None:
            return
        try:
            for line in stream:
                self._stderr.append(line)
                self._stderr_chars += len(line)
                while self._stderr_chars > STDERR_TAIL_CHARS and len(self._stderr) > 1:
                    self._stderr_chars -= len(self._stderr.popleft())
        except (OSError, ValueError):
            pass

    def _stderr_tail(self) -> str:
        return ''.join(self._stderr)[-STDERR_TAIL_CHARS:].strip()

    # ---- event stream ----------------------------------------------------------------------

    def _start_event(self) -> dict:
        self._start_sent = True
        return {'type': 'start', 'agent': self.agent, 'model': self._model, 'session_id': self._session_id}

    def _lines(self, stdout) -> Iterator[str]:
        """Yield stdout lines until EOF, or until DRAIN_SCHEDULE gives up after the CLI exited."""
        fd = stdout.fileno()
        decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        pending = ''
        exited_at: float | None = None
        step = 0
        with selectors.DefaultSelector() as selector:
            selector.register(fd, selectors.EVENT_READ)
            while True:
                if exited_at is None and self._leader_exit_code() is not None:
                    exited_at = time.monotonic()
                if exited_at is not None and step < len(DRAIN_SCHEDULE):
                    after, sig = DRAIN_SCHEDULE[step]
                    if time.monotonic() - exited_at >= after:
                        step += 1
                        if sig is None:
                            break
                        self._signal(sig)
                if not selector.select(READ_POLL_S):
                    continue
                chunk = os.read(fd, READ_CHUNK)
                if not chunk:
                    break
                pending += decoder.decode(chunk)
                *lines, pending = pending.split('\n')
                yield from lines
        pending += decoder.decode(b'', final=True)
        if pending:
            yield pending

    def events(self) -> Iterator[dict]:
        if self._consumed:
            raise RuntimeError('LLMRun.events() can only be consumed once')
        self._consumed = True
        finished = False
        try:
            stdout = self._proc.stdout
            if stdout is not None:
                for raw in self._lines(stdout):
                    line = raw.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except ValueError:
                        self.malformed_lines += 1
                        continue
                    if not isinstance(event, dict):
                        self.malformed_lines += 1
                        continue
                    try:
                        normalized = self._normalize(event)
                    except (TypeError, AttributeError, ValueError, KeyError):
                        self.malformed_lines += 1
                        continue
                    for item in normalized:
                        if self._cancelled or self._timed_out:
                            break
                        if item['type'] == 'start':
                            if not self._start_sent:
                                yield self._start_event()
                            continue
                        if not self._start_sent:
                            yield self._start_event()
                        yield item
            returncode = self._wait_leader()
            self._stderr_thread.join(timeout=2)
            if not self._start_sent:
                yield self._start_event()
            # Decided after the last preceding yield, so a cancel issued meanwhile still wins.
            terminal = self._terminal(returncode)
            self._reap(stop_group=terminal['type'] == 'cancelled' or self._timed_out)
            finished = True
            yield terminal
        finally:
            if self._proc.stdout is not None:
                try:
                    self._proc.stdout.close()
                except OSError:
                    pass
            if not finished:
                threading.Thread(target=self._abandon, daemon=True).start()

    def _terminal(self, returncode: int) -> dict:
        with self._lock:
            self._terminal_decided = True
            cancelled, timed_out = self._cancelled, self._timed_out
        if cancelled:
            return {'type': 'cancelled'}
        if timed_out:
            return {'type': 'error', 'retryable': True, 'kind': 'timeout',
                    'message': f'시간 초과: {self._request.timeout_s}초 안에 응답이 끝나지 않았습니다.'}
        if self.agent == 'codex':
            self._finish_codex()
        elif self.agent == 'omp':
            self._finish_omp(returncode)
        if self._failure is not None:
            return {**self._failure, 'kind': self._error_kind(self._failure.get('message'))}
        if self._result is not None:
            return self._result
        tail = self._stderr_tail()
        if returncode != 0:
            message = tail or self._stream_error or f'{self.agent} CLI가 종료 코드 {returncode}로 끝났습니다.'
        else:
            message = self._stream_error or tail or f'{self.agent} CLI가 결과 없이 종료되었습니다.'
        kind = self._error_kind(message, self._stream_error, tail)
        if kind == 'other' and returncode != 0:
            kind = 'process'
        return {'type': 'error', 'message': message[-STDERR_TAIL_CHARS:], 'retryable': False, 'kind': kind}

    def _error_kind(self, *texts: object) -> str:
        if self._rate_limited or self._api_status == 429:
            return 'usage_limit'
        found = classify_error_text(*texts, *self._error_texts)
        if found == 'other' and self._api_status in (401, 403):
            return 'auth'
        return found

    def _elapsed_ms(self) -> int:
        return int((time.monotonic() - self._started_at) * 1000)

    # ---- claude ----------------------------------------------------------------------------

    def _claude(self, event: dict) -> list[dict]:
        kind = event.get('type')
        if kind == 'system':
            subtype = event.get('subtype')
            if subtype == 'init':
                self._model = event.get('model') or self._model
                self._session_id = event.get('session_id') or self._session_id
                return [{'type': 'start'}]
            if subtype == 'api_retry':
                delay = event.get('retry_delay_ms')
                return [{'type': 'retry', 'attempt': int(event.get('attempt') or 0),
                         'delay_ms': int(delay) if isinstance(delay, (int, float)) else None}]
            return []
        if kind == 'rate_limit_event':
            info = event.get('rate_limit_info')
            if isinstance(info, dict) and info.get('status') == 'rejected':
                self._rate_limited = True
            return []
        if event.get('parent_tool_use_id'):
            return []
        if kind == 'stream_event':
            inner = event.get('event') or {}
            delta = inner.get('delta') or {}
            if inner.get('type') == 'content_block_delta' and delta.get('type') == 'text_delta':
                text = delta.get('text')
                return [{'type': 'text_delta', 'text': text}] if isinstance(text, str) and text else []
            return []
        if kind == 'assistant':
            out: list[dict] = []
            texts: list[str] = []
            for block in (event.get('message') or {}).get('content') or []:
                if block.get('type') == 'text' and isinstance(block.get('text'), str):
                    texts.append(block['text'])
                elif block.get('type') == 'tool_use':
                    out.append({'type': 'tool_use', 'name': _clip(block.get('name') or 'tool'),
                                'summary': _summary(block.get('input'))})
            text = ''.join(texts)
            return ([{'type': 'message', 'text': text}] if text else []) + out
        if kind == 'result':
            self._session_id = self._session_id or event.get('session_id')
            text = event.get('result') if isinstance(event.get('result'), str) else ''
            if event.get('is_error') or event.get('subtype') != 'success':
                self._api_status = event.get('api_error_status')
                errors = event.get('errors')
                detail = text or ('; '.join(map(str, errors)) if isinstance(errors, list) and errors else '')
                message = detail or f'claude 실행 실패 ({event.get("subtype") or "error"})'
                self._failure = {'type': 'error', 'message': message[-STDERR_TAIL_CHARS:],
                                 'retryable': event.get('api_error_status') in RETRYABLE_HTTP}
            else:
                cost, duration, usage = event.get('total_cost_usd'), event.get('duration_ms'), event.get('usage')
                self._result = {'type': 'result', 'text': text,
                                'cost_usd': float(cost) if isinstance(cost, (int, float)) else None,
                                'duration_ms': int(duration) if isinstance(duration, (int, float)) else None,
                                'usage': usage if isinstance(usage, dict) else None}
                if event.get('structured_output') is not None:
                    self._result['structured_output'] = event['structured_output']
            return []
        return []

    # ---- codex -----------------------------------------------------------------------------

    def _codex(self, event: dict) -> list[dict]:
        kind = event.get('type')
        if kind == 'thread.started':
            self._session_id = event.get('thread_id') or self._session_id
            return [{'type': 'start'}]
        if kind in ('item.started', 'item.updated', 'item.completed'):
            item = event.get('item') or {}
            item_type = item.get('type')
            if item_type == 'agent_message':
                text = item.get('text')
                if kind == 'item.completed' and isinstance(text, str) and text:
                    self._last_text = text
                    return [{'type': 'message', 'text': text}]
                return []
            if item_type in CODEX_TOOL_ITEMS:
                item_id = str(item.get('id'))
                if item_id in self._seen_items:
                    return []
                self._seen_items.add(item_id)
                return [self._codex_tool(item)]
            if item_type == 'error' and kind == 'item.completed' and item.get('message'):
                self._error_texts.append(_clip(item.get('message'), STDERR_TAIL_CHARS))
            return []
        if kind == 'turn.completed':
            self._completed = True
            _add_usage(self._usage, event.get('usage'))
            return []
        if kind == 'turn.failed':
            error = event.get('error') or {}
            message = error.get('message') if isinstance(error, dict) else str(error)
            self._failure = {'type': 'error', 'message': _clip(message or 'codex 턴 실패', STDERR_TAIL_CHARS),
                             'retryable': False}
            return []
        if kind == 'error':
            message = str(event.get('message') or '')
            match = CODEX_RECONNECT.search(message)
            if match:
                return [{'type': 'retry', 'attempt': int(match.group(1)), 'delay_ms': None}]
            self._stream_error = message or self._stream_error
            return []
        return []

    @staticmethod
    def _codex_tool(item: dict) -> dict:
        item_type = item.get('type')
        if item_type == 'command_execution':
            return {'type': 'tool_use', 'name': 'shell', 'summary': _clip(item.get('command'))}
        if item_type == 'mcp_tool_call':
            name = '.'.join(str(part) for part in (item.get('server'), item.get('tool')) if part)
            return {'type': 'tool_use', 'name': _clip(name or 'mcp'), 'summary': ''}
        if item_type == 'web_search':
            return {'type': 'tool_use', 'name': 'web_search', 'summary': _clip(item.get('query'))}
        changes = item.get('changes') if isinstance(item.get('changes'), list) else []
        paths = ', '.join(str(change.get('path')) for change in changes if isinstance(change, dict))
        return {'type': 'tool_use', 'name': 'file_change', 'summary': _clip(paths)}

    def _finish_codex(self) -> None:
        if self._failure is None and self._completed:
            self._result = {'type': 'result', 'text': self._last_text, 'cost_usd': None,
                            'duration_ms': self._elapsed_ms(), 'usage': self._usage or None}

    # ---- omp -------------------------------------------------------------------------------

    def _omp(self, event: dict) -> list[dict]:
        kind = event.get('type')
        if kind == 'session':
            self._session_id = event.get('id') or self._session_id
            return [{'type': 'start'}]
        if kind == 'message_update':
            update = event.get('assistantMessageEvent') or {}
            delta = update.get('delta')
            if update.get('type') == 'text_delta' and isinstance(delta, str) and delta:
                return [{'type': 'text_delta', 'text': delta}]
            return []
        if kind == 'message_end':
            message = event.get('message') or {}
            if message.get('role') != 'assistant':
                return []
            self._last_assistant = message
            usage = message.get('usage') if isinstance(message.get('usage'), dict) else {}
            _add_usage(self._usage, {k: v for k, v in usage.items() if k != 'cost'})
            cost = (usage.get('cost') or {}).get('total') if isinstance(usage.get('cost'), dict) else None
            if isinstance(cost, (int, float)):
                self._cost = (self._cost or 0.0) + float(cost)
            text = self._omp_text(message)
            return [{'type': 'message', 'text': text}] if text else []
        if kind == 'tool_execution_start':
            summary = event.get('intent') if isinstance(event.get('intent'), str) else ''
            return [{'type': 'tool_use', 'name': _clip(event.get('toolName') or 'tool'),
                     'summary': _clip(summary) or _summary(event.get('args'))}]
        if kind == 'auto_retry_start':
            delay = event.get('delayMs')
            return [{'type': 'retry', 'attempt': int(event.get('attempt') or 0),
                     'delay_ms': int(delay) if isinstance(delay, (int, float)) else None}]
        if kind == 'error':
            error = event.get('error')
            message = event.get('message') or (error.get('message') if isinstance(error, dict) else error)
            if message:
                self._stream_error = _clip(message, STDERR_TAIL_CHARS)
            return []
        return []

    @staticmethod
    def _omp_text(message: dict) -> str:
        content = message.get('content')
        if isinstance(content, str):
            return content
        return ''.join(block.get('text', '') for block in content or []
                       if isinstance(block, dict) and block.get('type') == 'text' and isinstance(block.get('text'), str))

    def _finish_omp(self, returncode: int) -> None:
        last = self._last_assistant
        if last is not None and last.get('stopReason') in ('error', 'aborted'):
            message = last.get('errorMessage') or f'omp 응답 실패 ({last.get("stopReason")})'
            self._failure = {'type': 'error', 'message': _clip(message, STDERR_TAIL_CHARS), 'retryable': False}
        elif returncode == 0 and last is not None:
            self._result = {'type': 'result', 'text': self._omp_text(last), 'cost_usd': self._cost,
                            'duration_ms': self._elapsed_ms(), 'usage': self._usage or None}
        elif last is not None and last.get('errorMessage'):
            self._stream_error = str(last['errorMessage'])
