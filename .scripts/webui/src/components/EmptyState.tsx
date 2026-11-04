import type { ReactNode } from 'react';
import type { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  children?: ReactNode;
  /** Usually one button or link. */
  action?: ReactNode;
}

/** Icon in a primary-container circle, a title, descriptive text, and an optional action. */
export function EmptyState({ icon: Icon, title, children, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <span className="empty-state-icon">
        <Icon />
      </span>
      <p className="empty-state-title">{title}</p>
      {children ? <div className="empty-state-text">{children}</div> : null}
      {action ? <div className="empty-state-action">{action}</div> : null}
    </div>
  );
}
