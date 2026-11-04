import { useEffect, useRef, type MouseEvent, type ReactNode } from 'react';
import * as m from 'motion/react-m';
import { DUR_BASE, EASE_OUT } from '../motion/tokens';

interface SheetProps {
  open: boolean;
  /** Called after Esc, a backdrop click, or a close button; the parent sets `open` false. */
  onClose: () => void;
  /** Id of the sheet's heading. */
  labelledBy: string;
  /** Changing it replays the content entrance (e.g. another skill opened in the same sheet). */
  contentKey?: string;
  children: ReactNode;
}

/**
 * Right-side modal sheet on a native <dialog> (top layer, focus trap, Esc). The content slides
 * x 24 → 0 with opacity over 280 ms; the backdrop fades in CSS. Focus returns to the opener.
 */
export function Sheet({ open, onClose, labelledBy, contentKey, children }: SheetProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const openerRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      openerRef.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      dialog.showModal();
    } else if (!open && dialog.open) {
      dialog.close();
    }
  }, [open]);

  const handleClose = () => {
    onClose();
    const opener = openerRef.current;
    openerRef.current = null;
    if (opener?.isConnected && document.activeElement !== opener) opener.focus();
  };

  // A click whose target is the <dialog> itself landed on the backdrop.
  const closeOnBackdrop = (event: MouseEvent<HTMLDialogElement>) => {
    if (event.target === event.currentTarget) event.currentTarget.close();
  };

  return (
    <dialog ref={dialogRef} className="sheet" aria-labelledby={labelledBy} onClose={handleClose} onClick={closeOnBackdrop}>
      {open ? (
        <m.div
          key={contentKey}
          className="sheet-body"
          initial={{ opacity: 0, x: 24 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: DUR_BASE, ease: EASE_OUT }}
        >
          {children}
        </m.div>
      ) : null}
    </dialog>
  );
}
