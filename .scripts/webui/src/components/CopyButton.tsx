import { useEffect, useState } from 'react';
import { Check, Copy } from 'lucide-react';

type CopyState = 'idle' | 'copied' | 'failed';

const RESET_MS = 1_600;

/** Icon-only copy control. The live region announces the result; a failure stays visible. */
export function CopyButton({ text, label }: { text: string; label: string }) {
  const [state, setState] = useState<CopyState>('idle');

  useEffect(() => {
    if (state !== 'copied') return;
    const timer = window.setTimeout(() => setState('idle'), RESET_MS);
    return () => window.clearTimeout(timer);
  }, [state]);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setState('copied');
    } catch {
      setState('failed');
    }
  };

  return (
    <>
      <button
        type="button"
        className="icon-btn copy-btn"
        aria-label={label}
        title={label}
        data-copied={state === 'copied' ? 'true' : undefined}
        onClick={copy}
      >
        <span className="copy-icon">
          <Copy />
          <Check />
        </span>
      </button>
      <span className={state === 'failed' ? 'field-error copy-feedback' : 'visually-hidden'} role="status">
        {state === 'copied' ? '복사했습니다.' : state === 'failed' ? '복사하지 못했습니다. 직접 선택해 복사하세요.' : ''}
      </span>
    </>
  );
}
