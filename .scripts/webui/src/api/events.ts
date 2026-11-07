import type { DiscoveryRegistration, JobErrorKind, JobEvent, TerminalEvent } from './types';

type Fields = Record<string, unknown>;

function isFields(value: unknown): value is Fields {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function nullableNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function nullableText(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null;
}

/** `registration` of a completed `discovery.register` result; undefined when absent or without a slug. */
function registration(value: unknown): DiscoveryRegistration | undefined {
  if (!isFields(value)) return undefined;
  const slug = nullableText(value.slug);
  if (!slug) return undefined;
  return {
    slug,
    record_path: nullableText(value.record_path),
    pdf_path: nullableText(value.pdf_path),
    keep_path: nullableText(value.keep_path),
    index_path: nullableText(value.index_path),
    warnings: Array.isArray(value.warnings)
      ? value.warnings.filter((warning): warning is string => typeof warning === 'string' && warning.trim() !== '')
      : [],
    upgraded: value.upgraded === true,
    notes: text(value.notes).trim(),
  };
}

const ERROR_KINDS: readonly JobErrorKind[] = ['usage_limit', 'auth', 'timeout', 'process', 'other'];

/**
 * Parses one SSE `data` payload into a normalized job event.
 * The payload carries its own `type`; the SSE event name is the fallback.
 * Unknown types and malformed JSON return null and are ignored by the stream.
 */
export function parseJobEvent(eventName: string, data: string): JobEvent | null {
  let value: unknown;
  try {
    value = JSON.parse(data);
  } catch {
    return null;
  }
  if (!isFields(value)) return null;
  const type = typeof value.type === 'string' ? value.type : eventName;
  switch (type) {
    case 'start':
      return {
        type: 'start',
        agent: text(value.agent),
        model: typeof value.model === 'string' ? value.model : null,
        session_id: typeof value.session_id === 'string' ? value.session_id : null,
      };
    case 'text_delta':
      return { type: 'text_delta', text: text(value.text) };
    case 'message':
      return { type: 'message', text: text(value.text) };
    case 'tool_use':
      return { type: 'tool_use', name: text(value.name), summary: text(value.summary) };
    case 'retry':
      return {
        type: 'retry',
        attempt: nullableNumber(value.attempt) ?? 0,
        delay_ms: nullableNumber(value.delay_ms),
        reason: typeof value.reason === 'string' && value.reason ? value.reason : null,
        next: typeof value.next === 'string' && value.next ? value.next : null,
      };
    case 'gap':
      return {
        type: 'gap',
        missed_from: nullableNumber(value.missed_from) ?? 0,
        missed_to: nullableNumber(value.missed_to) ?? 0,
      };
    case 'result': {
      const published = registration(value.registration);
      return {
        type: 'result',
        text: text(value.text),
        cost_usd: nullableNumber(value.cost_usd),
        duration_ms: nullableNumber(value.duration_ms),
        usage: isFields(value.usage) ? value.usage : null,
        ...(published ? { registration: published } : {}),
      };
    }
    case 'error':
      return {
        type: 'error',
        message: text(value.message),
        retryable: value.retryable === true,
        kind: (ERROR_KINDS as readonly unknown[]).includes(value.kind) ? (value.kind as JobErrorKind) : null,
      };
    case 'cancelled':
      return { type: 'cancelled' };
    default:
      return null;
  }
}

export function isTerminalEvent(event: JobEvent): event is TerminalEvent {
  return event.type === 'result' || event.type === 'error' || event.type === 'cancelled';
}
