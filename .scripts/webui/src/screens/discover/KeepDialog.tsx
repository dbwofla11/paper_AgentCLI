import { useId, useRef, useState, type FormEvent, type KeyboardEvent, type RefObject } from 'react';
import { BookmarkPlus } from 'lucide-react';
import type { DiscoveryCandidate } from '../../api/types';
import { Dialog } from '../../components/Dialog';
import { formatCount } from '../../format';

/** The server keeps at most this many characters of the reason (`webui/discovery.py` KEEP_ENTRY). */
const KEEP_REASON_MAX = 500;

interface KeepDialogProps {
  open: boolean;
  candidate: DiscoveryCandidate;
  pending: boolean;
  /** Why the last attempt failed (from the error code); null before the first attempt. */
  error: string | null;
  onSubmit: (reason: string) => void;
  onClose: () => void;
  /** Focus target after a successful Keep disabled the button that opened the dialog. */
  fallbackFocus: RefObject<HTMLElement | null>;
}

interface KeepFormProps extends Omit<KeepDialogProps, 'open' | 'fallbackFocus'> {
  headingId: string;
  inputRef: RefObject<HTMLInputElement | null>;
}

/** Mounted only while the dialog is open, so every opening starts from the relevance note again. */
function KeepForm({ candidate, pending, error, onSubmit, onClose, headingId, inputRef }: KeepFormProps) {
  const inputId = useId();
  const hintId = useId();
  const errorId = useId();
  // Prefill: the agent's relevance note, cut to the server limit by code point (never inside a surrogate pair).
  const [reason, setReason] = useState(() =>
    Array.from(candidate.relevance.replace(/\s+/g, ' ').trim()).slice(0, KEEP_REASON_MAX).join(''),
  );
  const length = Array.from(reason).length;

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!pending) onSubmit(reason);
  };

  // Enter that commits a Hangul syllable (IME composition) must not also submit the form.
  const guardComposition = (event: KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter' && (event.nativeEvent.isComposing || event.keyCode === 229)) event.preventDefault();
  };

  return (
    <form className="dialog-form" onSubmit={submit} aria-busy={pending}>
      <div className="dialog-head">
        <h2 id={headingId}>Keep에 담기</h2>
        <p className="dialog-subject">{candidate.title}</p>
      </div>
      <p className="field-hint">
        <code translate="no">01-Papers/keep.md</code> 맨 위에 항목을 추가하고, 검색 결과의 서지 정보로 논문 기록(읽기
        상태 Keep)을 만듭니다. PDF는 받지 않습니다.
      </p>
      <div className="field">
        <label htmlFor={inputId}>담는 이유</label>
        <input
          ref={inputRef}
          id={inputId}
          type="text"
          name="reason"
          value={reason}
          maxLength={KEEP_REASON_MAX}
          autoComplete="off"
          enterKeyHint="done"
          aria-describedby={error ? `${hintId} ${errorId}` : hintId}
          onChange={(event) => setReason(event.currentTarget.value)}
          onKeyDown={guardComposition}
        />
        <div className="dialog-field-foot">
          <p className="field-hint" id={hintId}>
            에이전트가 적은 관련 이유로 채웠습니다. 비우면 ‘사용자 지정 이유 없음’으로 적습니다. <kbd>Enter</kbd>로 담고{' '}
            <kbd>Esc</kbd>로 닫습니다.
          </p>
          <span className="dialog-count num" aria-hidden="true">
            {formatCount(length)}/{formatCount(KEEP_REASON_MAX)}
          </span>
        </div>
      </div>
      {error ? (
        <p className="field-error" id={errorId} role="alert">
          {error}
        </p>
      ) : null}
      <div className="dialog-actions">
        <button type="button" className="btn btn-secondary" onClick={onClose} disabled={pending}>
          취소
        </button>
        {/* aria-disabled, not disabled: the pressed button keeps focus while the request runs. */}
        <button type="submit" className="btn btn-primary" aria-disabled={pending} aria-busy={pending}>
          <BookmarkPlus />
          {pending ? '담는 중…' : 'Keep에 담기'}
        </button>
      </div>
    </form>
  );
}

/**
 * "Keep에 담기" (Q12, Q20): the title read-only and one reason field prefilled with the agent's relevance
 * note. Enter submits (implicit submission), Esc closes. The server writes the keep.md entry and a partial
 * library record; the dialog stays open on failure and shows why.
 */
export function KeepDialog({ open, candidate, pending, error, onSubmit, onClose, fallbackFocus }: KeepDialogProps) {
  const headingId = useId();
  const inputRef = useRef<HTMLInputElement>(null);
  return (
    <Dialog
      open={open}
      onClose={onClose}
      labelledBy={headingId}
      initialFocus={inputRef}
      fallbackFocus={fallbackFocus}
      locked={pending}
    >
      <KeepForm
        candidate={candidate}
        pending={pending}
        error={error}
        onSubmit={onSubmit}
        onClose={onClose}
        headingId={headingId}
        inputRef={inputRef}
      />
    </Dialog>
  );
}
