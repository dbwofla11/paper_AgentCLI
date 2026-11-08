"""In-memory job broker: FIFO scheduling, bounded replayable event logs, cancellation.

A job's ``work(ctx)`` runs on its own daemon thread and reports progress with
``ctx.emit(event)``. Exactly one terminal event (``result`` | ``error`` | ``cancelled``)
ends a job and determines its status; later emits are ignored. ``gap`` is reserved for the
replay marker that ``JobBroker.events`` synthesizes when a subscriber fell behind the buffer.
A job that writes durable results calls ``ctx.begin_commit()`` first: from then on cancellation
is refused, so a cancel either stops the job before any write or is not accepted at all.
"""
from __future__ import annotations

import json
import secrets
import sys
import threading
import time
from collections import deque
from datetime import datetime, timezone
from typing import Callable, Iterable, Iterator

TERMINAL_STATUS = {"result": "completed", "error": "failed", "cancelled": "cancelled"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class JobContext:
    """Handle passed to a job's work function."""

    def __init__(self, broker: "JobBroker", job_id: str):
        self.job_id = job_id
        self.cancelled = threading.Event()
        self._broker = broker

    def emit(self, event: dict) -> None:
        """Append an event; seq increases monotonically from 1. Ignored after a terminal event."""
        self._broker._emit(self.job_id, event)

    def on_cancel(self, fn: Callable[[], None]) -> None:
        """Run ``fn`` when the job is cancelled (immediately if cancellation already happened)."""
        self._broker._on_cancel(self.job_id, fn)

    def begin_commit(self) -> bool:
        """Enter the commit phase (atomic with ``JobBroker.cancel``): True when no cancellation
        was accepted, after which every cancel is refused and the job ends with its own
        terminal event; False (nothing changes) when the job is already cancelled."""
        return self._broker._begin_commit(self.job_id)


class _Job:
    __slots__ = ("record", "work", "context", "events", "base_seq", "hooks", "terminal", "changed", "finished",
                 "committing")

    def __init__(self, record: dict, work: Callable[[JobContext], None], context: JobContext,
                 changed: threading.Condition):
        self.record = record
        self.work = work
        self.context = context
        self.events: list[tuple[int, dict]] = []
        self.base_seq = 1          # seq of events[0]; older events were trimmed
        self.hooks: list[Callable[[], None]] = []
        self.terminal = False
        self.changed = changed
        self.finished = threading.Event()  # work returned, or never will run (cancelled while queued)
        self.committing = False  # ctx.begin_commit() succeeded: cancellation is refused


class JobBroker:
    def __init__(self, max_running: int = 2, max_events: int = 10_000):
        if max_running < 1 or max_events < 1:
            raise ValueError("max_running and max_events must be positive")
        self.max_running = max_running
        self.max_events = max_events
        self._lock = threading.Lock()
        self._jobs: dict[str, _Job] = {}
        self._pending: deque[str] = deque()
        self._running = 0
        self.closing = threading.Event()  # server shutdown began: callers stop submitting (reader.shutdown)

    # -- public API -------------------------------------------------------------
    def submit(self, kind: str, params: dict, work: Callable[[JobContext], None]) -> dict:
        """Register a job; it starts now or waits FIFO until a running slot frees up."""
        job_id = secrets.token_hex(8)
        record = {"job_id": job_id, "kind": kind, "status": "queued", "created_at": _now(),
                  "started_at": None, "ended_at": None, "agent": (params or {}).get("agent"),
                  "cost_usd": None, "error": None, "last_seq": 0}
        if (params or {}).get("role"):
            record["role"] = params["role"]  # role pings name the harness agent they resolved
        if (params or {}).get("slug"):
            record["slug"] = params["slug"]  # paper.ask jobs name the paper they answer about
        with self._lock:
            job = _Job(record, work, JobContext(self, job_id), threading.Condition(self._lock))
            self._jobs[job_id] = job
            self._pending.append(job_id)
            starting = self._schedule_locked()
            snapshot = dict(record)
        self._start(starting)
        return snapshot

    def get(self, job_id: str) -> dict | None:
        with self._lock:
            job = self._jobs.get(job_id)
            return dict(job.record) if job else None

    def list(self) -> list[dict]:
        """All jobs, newest first."""
        with self._lock:
            return [dict(job.record) for job in reversed(self._jobs.values())]

    def events(self, job_id: str, after_seq: int = 0, *,
               heartbeat_s: float = 15.0) -> Iterator[tuple[int, dict] | None]:
        """Replay events with seq > ``after_seq``, then block for new ones.

        Yields ``(seq, event)`` pairs and ``None`` as a heartbeat tick after ``heartbeat_s``
        seconds without events. When the wanted events were already trimmed from the bounded
        buffer, first yields ``(oldest_seq - 1, {"type": "gap", "missed_from", "missed_to"})``;
        ``gap`` is never stored and is not terminal. Stops after the terminal event. Raises
        ``KeyError`` for an unknown job.
        """
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(job_id)
        return self._stream(job, max(0, int(after_seq)), heartbeat_s)

    def cancel(self, job_id: str) -> bool:
        """Request cancellation. Returns False for an unknown or already-terminal job, and for
        one that entered its commit phase (``JobContext.begin_commit``).

        The decision is atomic: a queued job leaves the queue and becomes ``cancelled`` under
        the broker lock, so a concurrent second cancel sees it terminal and gets False. Once
        cancellation is accepted, the job's terminal event is always ``cancelled``.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None or job.terminal or job.committing:
                return False
            job.context.cancelled.set()
            if job.record["status"] == "queued":
                self._pending.remove(job_id)
                self._append_locked(job, {"type": "cancelled"})
                job.finished.set()
                return True
            hooks = list(job.hooks)
        for hook in hooks:
            self._call_hook(job_id, hook)
        return True

    def wait_finished(self, job_ids: Iterable[str], timeout: float) -> bool:
        """Wait up to ``timeout`` seconds in total until the work functions of ``job_ids`` have
        returned (a job cancelled while queued counts as finished; unknown ids are ignored).
        Unlike a terminal event, this covers the work's own cleanup. True when all finished."""
        deadline = time.monotonic() + max(0.0, timeout)
        with self._lock:
            jobs = [self._jobs[job_id] for job_id in job_ids if job_id in self._jobs]
        return all(job.finished.wait(max(0.0, deadline - time.monotonic())) for job in jobs)

    def committing(self, job_id: str) -> bool:
        """Whether ``job_id`` is in its commit phase (so ``cancel`` refuses it)."""
        with self._lock:
            job = self._jobs.get(job_id)
            return bool(job and job.committing and not job.terminal)

    # -- internals --------------------------------------------------------------
    def _schedule_locked(self) -> list[_Job]:
        starting = []
        while self._pending and self._running < self.max_running:
            job = self._jobs[self._pending.popleft()]
            job.record["status"] = "running"
            job.record["started_at"] = _now()
            self._running += 1
            starting.append(job)
        return starting

    def _start(self, jobs: list[_Job]) -> None:
        for job in jobs:
            threading.Thread(target=self._run, args=(job,), name=f"webui-job-{job.record['job_id']}",
                             daemon=True).start()

    def _run(self, job: _Job) -> None:
        context = job.context
        try:
            job.work(context)
        except Exception as exc:  # a failing job must still end with a terminal event
            message = f"{type(exc).__name__}: {exc}"[-2000:]
            self._emit(context.job_id, {"type": "error", "message": message, "retryable": False, "kind": "other"})
        finally:
            if context.cancelled.is_set():
                self._emit(context.job_id, {"type": "cancelled"})
            else:
                self._emit(context.job_id, {"type": "error", "message": "job ended without result",
                                            "retryable": False, "kind": "other"})
            with self._lock:
                self._running -= 1
                starting = self._schedule_locked()
            job.finished.set()
            self._start(starting)

    def _emit(self, job_id: str, event: dict) -> None:
        if not isinstance(event, dict):
            raise TypeError("job event must be a dict")
        kind = event.get("type")
        if not isinstance(kind, str) or not kind or "\n" in kind or "\r" in kind:
            raise ValueError("job event needs a single-line string 'type'")
        if kind == "gap":
            raise ValueError("job event type 'gap' is reserved for replay markers")
        payload = json.loads(json.dumps(event, ensure_ascii=False))  # JSON-safe private copy
        with self._lock:
            self._append_locked(self._jobs[job_id], payload)

    def _append_locked(self, job: _Job, payload: dict) -> None:
        """Store one event; the caller holds ``self._lock``. The first terminal event wins."""
        if job.terminal:
            return  # later events, terminal ones included, are dropped
        kind = payload["type"]
        status = TERMINAL_STATUS.get(kind)
        if status and status != "cancelled" and job.context.cancelled.is_set():
            # Cancellation was accepted before this terminal: the job ends cancelled.
            payload, kind, status = {"type": "cancelled"}, "cancelled", "cancelled"
        record = job.record
        seq = record["last_seq"] + 1
        record["last_seq"] = seq
        job.events.append((seq, payload))
        overflow = len(job.events) - self.max_events
        if overflow > 0:
            del job.events[:overflow]
            job.base_seq += overflow
        if kind == "start" and payload.get("agent"):
            record["agent"] = payload["agent"]
        if status:
            job.terminal = True
            record["status"] = status
            record["ended_at"] = _now()
            if kind == "result":
                record["cost_usd"] = payload.get("cost_usd")
            elif kind == "error":
                record["error"] = str(payload.get("message") or "error")
        job.changed.notify_all()

    def _begin_commit(self, job_id: str) -> bool:
        with self._lock:
            job = self._jobs[job_id]
            if job.context.cancelled.is_set() or job.terminal:
                return False
            job.committing = True
            return True

    def _on_cancel(self, job_id: str, fn: Callable[[], None]) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.hooks.append(fn)
            already = job.context.cancelled.is_set()
        if already:
            self._call_hook(job_id, fn)

    @staticmethod
    def _call_hook(job_id: str, fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception as exc:  # cancellation is best effort; the job still ends via its work
            sys.stderr.write(f"webui job {job_id}: cancel hook failed: {exc}\n")

    def _after_locked(self, job: _Job, last_seq: int) -> list[tuple[int, dict]]:
        """Events after ``last_seq``, preceded by a ``gap`` marker if some were trimmed."""
        pending = job.events[max(0, last_seq + 1 - job.base_seq):]
        if job.events and last_seq + 1 < job.base_seq:
            gap = {"type": "gap", "missed_from": last_seq + 1, "missed_to": job.base_seq - 1}
            pending.insert(0, (job.base_seq - 1, gap))
        return pending

    def _stream(self, job: _Job, last_seq: int, heartbeat_s: float) -> Iterator[tuple[int, dict] | None]:
        while True:
            deadline = time.monotonic() + heartbeat_s
            with job.changed:
                while True:
                    pending = self._after_locked(job, last_seq)
                    terminal = job.terminal
                    if pending or terminal:
                        break
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        break
                    job.changed.wait(remaining)
            if pending:
                for seq, event in pending:
                    yield seq, event
                    last_seq = seq
                    if event["type"] in TERMINAL_STATUS:
                        return
            elif terminal:
                return
            else:
                yield None
