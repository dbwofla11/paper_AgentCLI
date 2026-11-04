import type { QueueVerification, VerificationStatus } from '../api/types';
import { formatCount, statusLabel, statusTone, type Tone } from '../format';
import type { RoleState } from '../roles';

/** Job or review-queue status. The label carries the meaning; the tone only reinforces it. */
export function StatusBadge({ status }: { status: string }) {
  return (
    <span className="badge" data-tone={statusTone(status)}>
      {statusLabel(status)}
    </span>
  );
}

export function ReadyBadge({ ready, readyLabel = '준비됨', notReadyLabel = '준비 안 됨' }: {
  ready: boolean;
  readyLabel?: string;
  notReadyLabel?: string;
}) {
  return (
    <span className="badge" data-tone={ready ? 'success' : 'danger'}>
      {ready ? readyLabel : notReadyLabel}
    </span>
  );
}

const ROLE_STATE_BADGES: Record<RoleState, { label: string; tone: Tone }> = {
  ready: { label: '준비됨', tone: 'success' },
  unavailable: { label: '사용 불가', tone: 'danger' },
  unconfigured: { label: '미설정', tone: 'neutral' },
  config_error: { label: '설정 읽기 실패', tone: 'danger' },
};

export function RoleStateBadge({ state }: { state: RoleState }) {
  const { label, tone } = ROLE_STATE_BADGES[state];
  return (
    <span className="badge" data-tone={tone}>
      {label}
    </span>
  );
}

const VERIFICATION_TONES: Record<VerificationStatus, Tone> = {
  passed: 'success',
  issues: 'warning',
  error: 'danger',
  skipped: 'neutral',
};

const VERIFICATION_LABELS: Record<Exclude<VerificationStatus, 'issues'>, string> = {
  passed: '검증 통과',
  error: '검증 오류',
  skipped: '검증 건너뜀',
};

/**
 * Review verification outcome. `issues` shows the blocking-issue count, or the count of claims not
 * verdicted `supported` when the verifier listed no blocking issue. With neither (no claim was
 * checked) it reads "검증 주장 없음", never "이슈 0".
 */
export function VerificationBadge({ verification }: { verification: QueueVerification }) {
  const { status, blocking_issues: blocking, mismatches } = verification;
  const count = blocking > 0 ? blocking : mismatches;
  return (
    <span className="badge" data-tone={VERIFICATION_TONES[status] ?? 'neutral'}>
      {status !== 'issues' ? (
        (VERIFICATION_LABELS[status] ?? `검증 ${String(status)}`)
      ) : count > 0 ? (
        <>
          검증 이슈&nbsp;<span className="num">{formatCount(count)}</span>
        </>
      ) : (
        '검증 주장 없음'
      )}
    </span>
  );
}
