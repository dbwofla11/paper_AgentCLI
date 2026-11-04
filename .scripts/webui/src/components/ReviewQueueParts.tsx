import type { QueueVerification } from '../api/types';
import { formatCount } from '../format';

/** Longer queue messages (worker stderr tails) collapse behind a disclosure. */
const LONG_MESSAGE = 240;

/** The `message` of a review-queue job. */
export function QueueMessage({ message }: { message: string }) {
  if (message.length <= LONG_MESSAGE) return <p className="queue-message">{message}</p>;
  return (
    <details className="queue-details">
      <summary>{message.slice(0, LONG_MESSAGE)}…</summary>
      <pre className="queue-full">{message}</pre>
    </details>
  );
}

/**
 * Verifier model, issue counts and report link of a review-queue job; a skipped verification has none.
 * An `issues` result with a note (no claim was checked) shows the note instead of two zero counts.
 */
export function VerificationLine({ verification }: { verification: QueueVerification }) {
  if (verification.status === 'skipped') return null;
  const reportPath = verification.report_path;
  const noCounts = verification.blocking_issues === 0 && verification.mismatches === 0;
  return (
    <p className="queue-verification meta">
      검증
      {verification.selector ? (
        <>
          {' '}
          <span translate="no">{verification.selector}</span>
        </>
      ) : null}
      {verification.status === 'issues' ? (
        verification.note || noCounts ? (
          ` · ${verification.note || '검증된 주장이 없음'}`
        ) : (
          <>
            {' · 차단 이슈 '}
            <span className="num">{formatCount(verification.blocking_issues)}</span>건 · 미확인·불일치{' '}
            <span className="num">{formatCount(verification.mismatches)}</span>건
          </>
        )
      ) : null}
      {reportPath ? (
        <>
          {' · '}
          <a href={`/${reportPath.split('/').map(encodeURIComponent).join('/')}`}>검증 보고서 (JSON)</a>
        </>
      ) : null}
    </p>
  );
}
