import { useEffect, useRef, type MouseEvent, type ReactNode, type RefObject, type SyntheticEvent } from 'react';
import * as m from 'motion/react-m';
import { DUR_BASE, EASE_OUT } from '../motion/tokens';

interface DialogProps {
  open: boolean;
  /** Called after Esc, a backdrop click or a cancel button; the parent sets `open` false. */
  onClose: () => void;
  /** Id of the dialog's heading. */
  labelledBy: string;
  /** Focused when the dialog opens; otherwise the browser focuses the first focusable element. */
  initialFocus?: RefObject<HTMLElement | null>;
  /** Focused on close when the opener is gone or disabled (the action it opened just finished). */
  fallbackFocus?: RefObject<HTMLElement | null>;
  /** A request is in flight: Esc and backdrop clicks do not close the dialog. */
  locked?: boolean;
  children: ReactNode;
}

/**
 * Centered modal on a native <dialog> (top layer, focus trap, Esc). The content mounts on open, so a
 * form inside starts fresh each time, and rises 8 px with opacity; the backdrop fades in CSS.
 * Focus returns to the opener, or to `fallbackFocus` when the opener can no longer take it.
 */
export function Dialog({ open, onClose, labelledBy, initialFocus, fallbackFocus, locked = false, children }: DialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      dialog.showModal();
      initialFocus?.current?.focus();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open, initialFocus]);

  const handleClose = () => {
    onClose();
    const opener = openerRef.current;
    openerRef.current = null;
    if (opener?.isConnected && !opener.matches(':disabled')) opener.focus();
    else fallbackFocus?.current?.focus();
  };

  // Esc fires `cancel` first; while a request runs the dialog stays (the result must land somewhere).
  const handleCancel = (event: SyntheticEvent<HTMLDialogElement>) => {
    if (locked) event.preventDefault();
  };

  // A click whose target is the <dialog> itself landed on the backdrop.
  const closeOnBackdrop = (event: MouseEvent<HTMLDialogElement>) => {
    if (event.target === event.currentTarget && !locked) event.currentTarget.close();
  };

  return (
    <dialog
      ref={dialogRef}
      className="dialog"
      aria-labelledby={labelledBy}
      onClose={handleClose}
      onCancel={handleCancel}
      onClick={closeOnBackdrop}
    >
      {open ? (
        <m.div
          className="dialog-body"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: DUR_BASE, ease: EASE_OUT }}
        >
          {children}
        </m.div>
      ) : null}
    </dialog>
  );
}
