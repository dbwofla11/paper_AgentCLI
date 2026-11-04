import { useCallback, useEffect, useReducer, useRef, useState } from 'react';
import { fetchJob, isAbortError, jobEventsUrl, toApiError } from '../api/client';
import { isTerminalEvent, parseJobEvent } from '../api/events';
import { JOB_EVENT_TYPES, type JobEvent, type StartEvent, type TerminalEvent } from '../api/types';

/**
 * connecting → open ⇄ reconnecting → ended (terminal event).
 * A refused stream goes reconnecting → waiting (automatic retry scheduled) → connecting,
 * or → failed once the automatic retries are used up or the job is gone.
 */
export type StreamPhase = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'waiting' | 'failed' | 'ended';

export type TranscriptItem =
  | { kind: 'text'; key: string; text: string; open: boolean }
  | { kind: 'tool'; key: string; name: string; summary: string }
  /** `next` = selector of the fallback candidate when a review role switches models. */
  | { kind: 'retry'; key: string; attempt: number; delayMs: number | null; reason: string | null; next: string | null }
  | { kind: 'gap'; key: string; missedFrom: number; missedTo: number }
  /** The job completed with an empty `result.text`. */
  | { kind: 'empty'; key: string };

/**
 * Why the server refused the stream. EventSource exposes no HTTP status, so a follow-up
 * GET /api/jobs/{id} classifies it: `refused` = server online and job known, which in M0 means
 * 503 too_many_streams; `missing` = 404 (server restarted); `offline` = server unreachable.
 */
export type StreamRefusal = 'refused' | 'offline' | 'missing' | 'unknown';

export interface StreamInterruption {
  reason: StreamRefusal;
  /** Delay of the scheduled automatic reconnect; null when none is scheduled (phase `failed`). */
  retryInMs: number | null;
  /** Automatic reconnects used, including the scheduled one. */
  attempt: number;
  maxAttempts: number;
}

export interface JobStreamState {
  phase: StreamPhase;
  items: TranscriptItem[];
  start: StartEvent | null;
  terminal: TerminalEvent | null;
  lastSeq: number;
  interruption: StreamInterruption | null;
}

export interface JobStream extends JobStreamState {
  /** Opens a new EventSource now, resuming after the last received seq, and resets the automatic retry budget. */
  reconnect: () => void;
}

export interface JobStreamHandlers {
  onTerminal?: (event: TerminalEvent) => void;
  /** The server answered 404 for the job after refusing its stream (e.g. the server restarted). */
  onMissing?: () => void;
}

interface SequencedEvent {
  seq: number;
  event: JobEvent;
}

type Action =
  | { type: 'reset' }
  | { type: 'connect' }
  | { type: 'phase'; phase: 'open' | 'reconnecting' }
  | { type: 'interrupted'; interruption: StreamInterruption }
  | { type: 'events'; batch: SequencedEvent[] };

/** Backoff for automatic reconnects after a refusal; the user can reconnect manually afterwards. */
const RETRY_DELAYS_MS = [1_000, 2_000, 4_000, 8_000, 16_000, 30_000] as const;

const INITIAL_STATE: JobStreamState = {
  phase: 'idle',
  items: [],
  start: null,
  terminal: null,
  lastSeq: 0,
  interruption: null,
};

/** ±20 % so several tabs refused at once do not retry in lockstep. */
function jittered(ms: number): number {
  return Math.round(ms * (0.8 + Math.random() * 0.4));
}

/** Rejects with the AbortError when `signal` aborts. */
async function classifyRefusal(jobId: string, signal: AbortSignal): Promise<StreamRefusal> {
  try {
    await fetchJob(jobId, signal);
    return 'refused';
  } catch (error) {
    if (isAbortError(error)) throw error;
    const apiError = toApiError(error);
    if (apiError.status === 404) return 'missing';
    if (apiError.code === 'offline') return 'offline';
    return 'unknown';
  }
}

/** Seals a text segment built from deltas so later deltas start a new segment. */
function closeOpenText(items: TranscriptItem[]): void {
  const last = items.at(-1);
  if (last?.kind === 'text' && last.open) items[items.length - 1] = { ...last, open: false };
}

function applyBatch(state: JobStreamState, batch: SequencedEvent[]): JobStreamState {
  if (state.terminal) return state;
  let items = state.items.slice();
  let { start, lastSeq } = state;
  // Declared wide: the early return above narrows `state.terminal` to null.
  let terminal: TerminalEvent | null = null;
  for (const { seq, event } of batch) {
    if (terminal) break;
    lastSeq = Math.max(lastSeq, seq);
    // Items are append-only until the terminal event, so the insertion index is a stable key.
    const key = String(items.length);
    const last = items.at(-1);
    switch (event.type) {
      case 'start':
        start = event;
        break;
      case 'text_delta':
        if (!event.text) break;
        if (last?.kind === 'text' && last.open) {
          items[items.length - 1] = { ...last, text: last.text + event.text };
        } else {
          items.push({ kind: 'text', key, text: event.text, open: true });
        }
        break;
      case 'message':
        // A complete message supersedes the deltas that streamed it; CLIs without deltas only send this.
        if (last?.kind === 'text' && last.open) {
          items[items.length - 1] = { ...last, text: event.text || last.text, open: false };
        } else if (event.text) {
          items.push({ kind: 'text', key, text: event.text, open: false });
        }
        break;
      case 'tool_use':
        closeOpenText(items);
        items.push({ kind: 'tool', key, name: event.name, summary: event.summary });
        break;
      case 'retry':
        closeOpenText(items);
        items.push({
          kind: 'retry',
          key,
          attempt: event.attempt,
          delayMs: event.delay_ms,
          reason: event.reason,
          next: event.next,
        });
        break;
      case 'gap':
        closeOpenText(items);
        items.push({ kind: 'gap', key, missedFrom: event.missed_from, missedTo: event.missed_to });
        break;
      case 'result': {
        closeOpenText(items);
        const streamed = items.map((item) => (item.kind === 'text' ? item.text : '')).join('');
        const gapSeen = items.some((item) => item.kind === 'gap');
        if (gapSeen || streamed !== event.text) {
          // result.text is the authoritative final answer, even when empty: drop the partial or
          // diverged streamed text, keep the tool, retry, and gap rows, and show the answer last.
          items = items.filter((item) => item.kind !== 'text');
          if (event.text) items.push({ kind: 'text', key: 'result', text: event.text, open: false });
        }
        // No text item can remain here when result.text is empty.
        if (!event.text) items.push({ kind: 'empty', key: 'result' });
        terminal = event;
        break;
      }
      case 'error':
      case 'cancelled':
        closeOpenText(items);
        terminal = event;
        break;
    }
  }
  return { ...state, phase: terminal ? 'ended' : state.phase, items, start, terminal, lastSeq };
}

function reducer(state: JobStreamState, action: Action): JobStreamState {
  switch (action.type) {
    case 'reset':
      return INITIAL_STATE;
    case 'connect':
      return state.terminal ? state : { ...state, phase: 'connecting' };
    case 'phase':
      if (state.terminal) return state;
      return action.phase === 'open'
        ? { ...state, phase: 'open', interruption: null }
        : { ...state, phase: action.phase };
    case 'interrupted':
      if (state.terminal) return state;
      return {
        ...state,
        phase: action.interruption.retryInMs === null ? 'failed' : 'waiting',
        interruption: action.interruption,
      };
    case 'events':
      return applyBatch(state, action.batch);
  }
}

/**
 * Follows GET /api/jobs/{id}/events. Text deltas are batched per animation frame;
 * the EventSource closes on the terminal event, on unmount, or when `jobId` changes.
 * When the server refuses the stream (EventSource gives up on any non-200 answer, such as
 * 503 too_many_streams), the hook classifies the refusal and reconnects with backoff.
 */
export function useJobStream(jobId: string | null, handlers: JobStreamHandlers = {}): JobStream {
  const [state, dispatch] = useReducer(reducer, INITIAL_STATE);
  const [attempt, setAttempt] = useState(0);
  const streamJobRef = useRef<string | null>(null);
  const lastSeqRef = useRef(0);
  const endedRef = useRef(false);
  const autoRetriesRef = useRef(0);
  const handlersRef = useRef(handlers);

  useEffect(() => {
    handlersRef.current = handlers;
  });

  useEffect(() => {
    if (streamJobRef.current !== jobId) {
      streamJobRef.current = jobId;
      lastSeqRef.current = 0;
      endedRef.current = false;
      autoRetriesRef.current = 0;
      dispatch({ type: 'reset' });
    }
    if (!jobId || endedRef.current) return;

    dispatch({ type: 'connect' });
    const source = new EventSource(jobEventsUrl(jobId, lastSeqRef.current));
    const probe = new AbortController();
    let retryTimer = 0;
    let pending: SequencedEvent[] = [];
    let frame = 0;

    const flush = () => {
      if (frame) {
        cancelAnimationFrame(frame);
        frame = 0;
      }
      if (pending.length === 0) return;
      const batch = pending;
      pending = [];
      dispatch({ type: 'events', batch });
    };

    const receive = (eventName: string, message: MessageEvent) => {
      const seq = Number.parseInt(message.lastEventId, 10);
      const hasSeq = Number.isFinite(seq) && seq > 0;
      if (hasSeq && seq <= lastSeqRef.current) return; // already applied
      if (hasSeq) lastSeqRef.current = seq;
      const event = typeof message.data === 'string' ? parseJobEvent(eventName, message.data) : null;
      if (!event) return;
      pending.push({ seq: lastSeqRef.current, event });
      if (isTerminalEvent(event)) {
        endedRef.current = true;
        source.close();
        flush();
        handlersRef.current.onTerminal?.(event);
      } else if (!frame) {
        frame = requestAnimationFrame(() => {
          frame = 0;
          flush();
        });
      }
    };

    /** EventSource closed for good: the server answered with a status it does not expose. */
    const handleRefusal = async () => {
      let reason: StreamRefusal;
      try {
        reason = await classifyRefusal(jobId, probe.signal);
      } catch {
        return; // cleanup aborted the probe
      }
      const maxAttempts = RETRY_DELAYS_MS.length;
      const used = autoRetriesRef.current;
      const delay = reason === 'missing' ? undefined : RETRY_DELAYS_MS[used];
      if (delay === undefined) {
        dispatch({ type: 'interrupted', interruption: { reason, retryInMs: null, attempt: used, maxAttempts } });
        if (reason === 'missing') handlersRef.current.onMissing?.();
        return;
      }
      const retryInMs = jittered(delay);
      autoRetriesRef.current = used + 1;
      dispatch({ type: 'interrupted', interruption: { reason, retryInMs, attempt: used + 1, maxAttempts } });
      retryTimer = window.setTimeout(() => setAttempt((count) => count + 1), retryInMs);
    };

    const listeners = JOB_EVENT_TYPES.map((eventName) => {
      const listener = (event: Event) => {
        if (event instanceof MessageEvent) {
          receive(eventName, event);
          return;
        }
        // A plain `error` Event is a transport failure, not the job's terminal `error` event.
        if (eventName !== 'error' || endedRef.current) return;
        flush();
        dispatch({ type: 'phase', phase: 'reconnecting' });
        // CONNECTING: the browser retries by itself with Last-Event-ID. CLOSED: it gave up.
        if (source.readyState === EventSource.CLOSED) void handleRefusal();
      };
      source.addEventListener(eventName, listener);
      return [eventName, listener] as const;
    });
    source.onopen = () => {
      autoRetriesRef.current = 0;
      dispatch({ type: 'phase', phase: 'open' });
    };

    return () => {
      for (const [eventName, listener] of listeners) source.removeEventListener(eventName, listener);
      source.onopen = null;
      source.close();
      probe.abort();
      window.clearTimeout(retryTimer);
      flush();
    };
  }, [jobId, attempt]);

  const reconnect = useCallback(() => {
    autoRetriesRef.current = 0;
    setAttempt((count) => count + 1);
  }, []);
  return { ...state, reconnect };
}
