import { useId, useRef, useState, type FormEvent, type RefObject } from 'react';
import { Library } from 'lucide-react';
import { DISCOVERY_CATEGORIES, type DiscoveryCandidate, type DiscoveryCategory } from '../../api/types';
import { Dialog } from '../../components/Dialog';
import { useCategoryLabels } from './useDiscovery';

interface CategoryDialogProps {
  open: boolean;
  candidate: DiscoveryCandidate;
  pending: boolean;
  /** Why the last attempt failed (from the error code); null before the first attempt. */
  error: string | null;
  onSubmit: (category: DiscoveryCategory) => void;
  onClose: () => void;
  fallbackFocus: RefObject<HTMLElement | null>;
}

interface CategoryFormProps extends Omit<CategoryDialogProps, 'open' | 'fallbackFocus'> {
  headingId: string;
  /** The radio checked on open; the dialog focuses it so arrow keys move the choice. */
  checkedRef: RefObject<HTMLInputElement | null>;
}

function CategoryForm({ candidate, pending, error, onSubmit, onClose, headingId, checkedRef }: CategoryFormProps) {
  const labels = useCategoryLabels();
  const errorId = useId();
  // The agent's suggestion when it is one of the five categories (Q17); otherwise 기타 is preselected.
  const recommended = DISCOVERY_CATEGORIES.find((value) => value === candidate.suggested_category) ?? null;
  const initial = recommended ?? 'other';
  const [category, setCategory] = useState<DiscoveryCategory>(initial);
  const upgrade = candidate.status === 'keep';

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!pending) onSubmit(category);
  };

  return (
    <form className="dialog-form" onSubmit={submit} aria-busy={pending}>
      <div className="dialog-head">
        <h2 id={headingId}>등록할 카테고리</h2>
        <p className="dialog-subject">{candidate.title}</p>
      </div>
      <p className="field-hint">
        {upgrade
          ? 'Keep에 담은 논문 기록을 그대로 쓰고, PDF와 index.md 행을 채워 정식 등록합니다. '
          : '논문 기록, keep.md 항목, index.md 행을 만들어 정식 등록합니다. '}
        에이전트(<code translate="no">paper-searcher</code>)가 공식·오픈액세스 PDF만 받으며 페이월은 우회하지 않습니다. PDF를
        구하지 못하면 서지 정보만 등록하고 라이브러리에 ‘PDF 필요’로 표시합니다. 최대 10분 걸립니다.
      </p>
      <fieldset className="dialog-choices" aria-describedby={error ? errorId : undefined}>
        <legend className="field-label">카테고리</legend>
        {DISCOVERY_CATEGORIES.map((value) => {
          const label = labels[value];
          return (
            <label className="dialog-choice" key={value} data-checked={category === value ? 'true' : undefined}>
              <input
                ref={value === initial ? checkedRef : undefined}
                type="radio"
                name="category"
                value={value}
                checked={category === value}
                onChange={() => setCategory(value)}
              />
              <span className="dialog-choice-text">
                <span className="dialog-choice-label">
                  {label ?? <span translate="no">{value}</span>}
                  {value === recommended ? <span className="badge" data-tone="active">에이전트 추천</span> : null}
                </span>
                {label ? (
                  <code className="dialog-choice-path" translate="no">
                    pdfs/{value}/
                  </code>
                ) : null}
              </span>
            </label>
          );
        })}
      </fieldset>
      {recommended === null ? (
        <p className="field-hint">에이전트가 카테고리를 추천하지 않아 ‘기타’를 먼저 골랐습니다.</p>
      ) : null}
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
          <Library />
          {pending ? '요청하는 중…' : '등록'}
        </button>
      </div>
    </form>
  );
}

/**
 * "등록" (Q17, Q18): five category radios with the agent's suggestion preselected. Submitting queues a
 * `discovery.register` job (202); the card then follows it. Esc closes; the dialog stays open on failure.
 */
export function CategoryDialog({ open, candidate, pending, error, onSubmit, onClose, fallbackFocus }: CategoryDialogProps) {
  const headingId = useId();
  const checkedRef = useRef<HTMLInputElement>(null);
  return (
    <Dialog
      open={open}
      onClose={onClose}
      labelledBy={headingId}
      initialFocus={checkedRef}
      fallbackFocus={fallbackFocus}
      locked={pending}
    >
      <CategoryForm
        candidate={candidate}
        pending={pending}
        error={error}
        onSubmit={onSubmit}
        onClose={onClose}
        headingId={headingId}
        checkedRef={checkedRef}
      />
    </Dialog>
  );
}
