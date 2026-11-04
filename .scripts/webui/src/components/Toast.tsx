import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { CircleAlert, CircleCheck, Info, X } from 'lucide-react';
import { AnimatePresence } from 'motion/react';
import * as m from 'motion/react-m';
import { DUR_BASE, EASE_OUT } from '../motion/tokens';

export type ToastTone = 'info' | 'success' | 'danger';

export interface ToastInput {
  title: string;
  text?: string;
  tone?: ToastTone;
}

interface ToastEntry extends ToastInput {
  id: number;
}

/** Auto-dismiss delay; paused while the pointer or focus is on the toast. */
const DISMISS_MS = 4_000;
/** Older toasts drop off beyond this many. */
const MAX_TOASTS = 3;

const TONE_ICONS = { info: Info, success: CircleCheck, danger: CircleAlert } as const;

const ToastContext = createContext<((toast: ToastInput) => void) | null>(null);

function ToastItem({ toast, onDismiss }: { toast: ToastEntry; onDismiss: (id: number) => void }) {
  const [paused, setPaused] = useState(false);
  const tone = toast.tone ?? 'info';
  const Icon = TONE_ICONS[tone];

  useEffect(() => {
    if (paused) return;
    const timer = window.setTimeout(() => onDismiss(toast.id), DISMISS_MS);
    return () => window.clearTimeout(timer);
  }, [paused, onDismiss, toast.id]);

  return (
    <m.div
      className="toast"
      data-tone={tone}
      layout="position"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 8, transition: { duration: DUR_BASE * 0.6, ease: EASE_OUT } }}
      transition={{ duration: DUR_BASE, ease: EASE_OUT }}
      onPointerEnter={() => setPaused(true)}
      onPointerLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <span className="toast-icon">
        <Icon />
      </span>
      <div>
        <p className="toast-title">{toast.title}</p>
        {toast.text ? <p className="toast-text">{toast.text}</p> : null}
      </div>
      <button type="button" className="icon-btn" aria-label="알림 닫기" onClick={() => onDismiss(toast.id)}>
        <X />
      </button>
    </m.div>
  );
}

/** Bottom-right toasts (z 500). `useToast()` returns the function that shows one. */
export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastEntry[]>([]);
  const nextId = useRef(0);

  const dismiss = useCallback((id: number) => setToasts((current) => current.filter((toast) => toast.id !== id)), []);
  const show = useCallback((toast: ToastInput) => {
    nextId.current += 1;
    const entry = { ...toast, id: nextId.current };
    setToasts((current) => [...current.slice(-(MAX_TOASTS - 1)), entry]);
  }, []);

  return (
    <ToastContext value={show}>
      {children}
      <div className="toast-region" role="status" aria-live="polite">
        <AnimatePresence initial={false}>
          {toasts.map((toast) => (
            <ToastItem key={toast.id} toast={toast} onDismiss={dismiss} />
          ))}
        </AnimatePresence>
      </div>
    </ToastContext>
  );
}

export function useToast(): (toast: ToastInput) => void {
  const show = useContext(ToastContext);
  if (!show) throw new Error('useToast must be used inside <ToastProvider>');
  return show;
}
