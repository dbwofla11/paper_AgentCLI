import { useId, useRef, useState } from 'react';
import { ArrowRight, BookmarkPlus, CircleAlert, CircleCheck, EyeOff, Library, Undo2 } from 'lucide-react';
import { keepCandidate, registerCandidate, setCandidateStatus, toApiError, type ApiError } from '../../api/client';
import type {
  DiscoveryCandidate,
  DiscoveryCategory,
  DiscoveryRegistration,
  DiscoverySource,
  TerminalEvent,
} from '../../api/types';
import { RelatedMenu, RelatedNotice } from '../../components/RelatedMenu';
import { useToast } from '../../components/Toast';
import { jobHref, paperHref } from '../../hooks/useHashRoute';
import { useJobStream, type TranscriptItem } from '../../hooks/useJobStream';
import { hasRelatedIdentifier, useRelatedLookup } from '../../hooks/useRelatedLookup';
import { StreamNotice } from '../JobDetail';
import { CategoryDialog } from './CategoryDialog';
import { KeepDialog } from './KeepDialog';
import {
  candidateKey,
  confirmCancel,
  finishRegister,
  trackRegister,
  useRegisterTrack,
  type RegisterOutcome,
  type RegisterTrack,
} from './useDiscovery';

/** What a card needs to adopt or set aside its candidate; omitted, the card is read-only. */
export interface CandidateActionHandlers {
  source: DiscoverySource;
  /** The server's copy of the candidate after Keep, 등록 (202), 넘김 or 복원 replaces the shown one. */
  onCandidate: (candidate: DiscoveryCandidate) => void;
  /**
   * Re-reads the cache file quietly; with `until`, keeps re-reading briefly until it holds for the
   * candidate. `until` sees the candidate of each successful re-read (undefined when it is gone).
   */
  onRefresh: (candidateId: string, until?: (candidate: DiscoveryCandidate | undefined) => boolean) => void;
  /** 넘김 removed the card from view (search list with skipped candidates hidden): the list takes focus. */
  onSkipped?: () => void;
}

/** Korean guidance per error code of the keep, register and status routes (.scripts/docs/webui-api.md). */
const ACTION_ERRORS: Record<string, string> = {
  not_found: '이 후보가 든 검색 기록이나 일일 후보 파일이 없습니다. 지워졌을 수 있습니다.',
  candidate_not_found: '캐시 파일에서 이 후보를 찾지 못했습니다. 목록을 새로 고쳤습니다.',
  already_in_library: '이미 라이브러리에 있는 논문입니다. 목록을 새로 고쳤습니다.',
  already_in_keep: 'keep.md에 같은 제목이나 식별자의 항목이 이미 있어 담지 않았습니다.',
  register_active: '이 후보의 등록이 이미 진행 중입니다. 작업 화면에서 진행 상황을 확인하세요.',
  review_active: '논문 리뷰가 진행 중이라 index.md를 지키려고 등록하지 않았습니다. 리뷰가 끝난 뒤 다시 등록하세요.',
  candidate_adopted: '이미 Keep에 담았거나 등록한 후보라 상태를 바꾸지 않았습니다. 목록을 새로 고쳤습니다.',
  shutting_down: '서버가 종료되는 중이라 요청을 받지 않았습니다.',
};

/** Codes whose server message names the specific problem; it follows the Korean headline. */
const DETAILED_ERRORS: Record<string, string> = {
  bad_request: '요청이 서버 기준에 맞지 않습니다.',
  write_failed: 'keep.md나 논문 기록을 쓰지 못해 바꾼 내용을 되돌렸습니다.',
  cache_unsafe: '탐색 캐시 폴더가 안전하지 않아 쓰지 않았습니다.',
  cache_corrupt: '탐색 캐시 파일을 읽지 못했습니다.',
  role_config_error: 'omp 설정을 읽지 못해 등록을 시작하지 않았습니다. 상태 화면에서 역할 구성을 확인하세요.',
  searcher_unavailable: '검색 역할(paper-searcher)에 준비된 실행기가 없어 등록을 시작하지 않았습니다.',
};

/** The shown data no longer matches the cache: these answers re-read it. */
const STALE_CODES: Record<string, true> = {
  not_found: true,
  candidate_not_found: true,
  already_in_library: true,
  already_in_keep: true,
  candidate_adopted: true,
};

function errorText(error: ApiError, failed: string): string {
  const known = ACTION_ERRORS[error.code];
  if (known) return known;
  const detailed = DETAILED_ERRORS[error.code];
  return detailed ? `${detailed} ${error.message}` : `${failed}: ${error.message}`;
}

function outcomeOf(event: TerminalEvent): RegisterOutcome {
  if (event.type === 'result') return { status: 'completed', registration: event.registration ?? null };
  if (event.type === 'error') return { status: 'failed', message: event.message || '등록 작업이 실패했습니다.' };
  return { status: 'cancelled', published: null };
}

interface RegisterProgressProps {
  track: RegisterTrack;
  id: string;
  onEnded: (jobId: string, outcome: RegisterOutcome) => void;
}

/** A queued or running `discovery.register` job, followed on its event stream while the card is shown. */
function RegisterProgress({ track, id, onEnded }: RegisterProgressProps) {
  const jobId = track.job.job_id;
  const stream = useJobStream(jobId, {
    onTerminal: (event) => onEnded(jobId, outcomeOf(event)),
    onMissing: () => onEnded(jobId, { status: 'missing' }),
  });
  const running = stream.start !== null || track.job.status === 'running';
  // The latest tool call (e.g. `paper.py pdf …`) tells what the agent is doing right now.
  const step = stream.items.findLast((item): item is Extract<TranscriptItem, { kind: 'tool' }> => item.kind === 'tool');

  return (
    <div className="candidate-register" id={id}>
      {stream.terminal ? null : <span className="ai-progress" aria-hidden="true" />}
      <p className="candidate-register-title" role="status">
        {stream.terminal
          ? '에이전트가 끝났습니다. 결과를 저장하는 중…'
          : running
            ? '등록하는 중… 에이전트가 공식·오픈액세스 PDF와 게재 정보를 확인합니다 (최대 10분).'
            : '등록 작업이 실행 순서를 기다리는 중…'}
      </p>
      {step && !stream.terminal ? (
        <p className="caption candidate-register-step">
          <span translate="no">{step.name}</span> {step.summary}
        </p>
      ) : null}
      <StreamNotice phase={stream.phase} interruption={stream.interruption} onReconnect={stream.reconnect} />
      <a className="btn btn-text btn-small candidate-register-link" href={jobHref(jobId)}>
        작업 화면에서 보기
        <ArrowRight />
      </a>
    </div>
  );
}

/** Card copy of a cancelled job whose publish had already begun, so the server finished it. */
const CANCEL_TOO_LATE = '취소 요청이 게시가 시작된 뒤에 도착해 등록을 마쳤습니다.';

/** A registration the library now holds: its slug, the agent's findings when the job reported them, and the link. */
function Registered({
  target,
  registration,
  note,
}: {
  target: string | null;
  registration: DiscoveryRegistration | null;
  note?: string;
}) {
  return (
    <div className="candidate-register" data-tone="success">
      <p className="candidate-register-title">
        <CircleCheck aria-hidden="true" />
        {target ? (
          <span>
            등록했습니다 — <span translate="no">{target}</span>
          </span>
        ) : (
          '등록했습니다.'
        )}
      </p>
      {note ? <p className="field-hint">{note}</p> : null}
      {registration ? (
        <p className="field-hint">
          {registration.upgraded ? 'Keep에 담은 기록을 정식 등록으로 올렸습니다. ' : null}
          {registration.pdf_path ? (
            <>
              PDF: <code translate="no">{registration.pdf_path}</code>
            </>
          ) : (
            'PDF를 구하지 못해 서지 정보만 등록했습니다. 라이브러리 카드에 ‘PDF 필요’로 표시됩니다.'
          )}
        </p>
      ) : null}
      {registration?.notes ? (
        <p className="field-hint candidate-register-message">에이전트 메모: {registration.notes}</p>
      ) : null}
      {registration && registration.warnings.length > 0 ? (
        <ul className="candidate-register-warnings" aria-label="등록 경고">
          {registration.warnings.map((warning, index) => (
            <li key={`${index}:${warning}`}>{warning}</li>
          ))}
        </ul>
      ) : null}
      {target ? (
        <a className="btn btn-text btn-small candidate-register-link" href={paperHref(target)}>
          라이브러리에서 보기
          <ArrowRight />
        </a>
      ) : null}
    </div>
  );
}

interface RegisterResultProps {
  outcome: RegisterOutcome;
  slug: string | null;
  /** The shown candidate is `registered`: only this job can have done it (등록 is offered only before). */
  candidateRegistered: boolean;
}

/** How the card's last registration in this page session ended; stays until the next one starts. */
function RegisterResult({ outcome, slug, candidateRegistered }: RegisterResultProps) {
  switch (outcome.status) {
    case 'completed':
      return <Registered target={outcome.registration?.slug ?? slug} registration={outcome.registration} />;
    case 'failed':
      return (
        <div className="candidate-register" data-tone="danger">
          <p className="candidate-register-title">
            <CircleAlert aria-hidden="true" />
            등록하지 못했습니다.
          </p>
          <p className="field-hint candidate-register-message">{outcome.message}</p>
        </div>
      );
    case 'cancelled': {
      // A fresher read of the card may already show the publish before the job's own re-read answers.
      const published = outcome.published ?? (candidateRegistered ? true : null);
      if (published) return <Registered target={slug} registration={null} note={CANCEL_TOO_LATE} />;
      return (
        <p className="field-hint">
          {published === false
            ? '취소했습니다. 게시가 시작되기 전이라 바뀐 파일은 없습니다.'
            : '취소를 요청했습니다. 게시가 이미 시작됐다면 등록 결과가 남을 수 있습니다.'}
        </p>
      );
    }
    case 'missing':
      return (
        <p className="field-error">
          서버가 다시 시작되어 등록 작업을 찾지 못했습니다. 후보 상태를 확인하고 필요하면 다시 등록하세요.
        </p>
      );
  }
}

type DialogName = 'keep' | 'register';
type Pending = 'keep' | 'register' | 'status' | null;

interface CandidateActionsProps {
  candidate: DiscoveryCandidate;
  /** Id of the card title; every action names the paper through it. */
  titleId: string;
  handlers: CandidateActionHandlers;
}

/**
 * Keep에 담기 / 등록 / 인용·피인용 / 넘김·복원 for one candidate (Q4, Q13, Q17, Q20, Q23). Keep is a
 * synchronous server write; 등록 queues a `discovery.register` job that the card follows on its event
 * stream. A library match or a finished adoption disables the buttons with the reason beside them; a
 * kept candidate can still be registered (the server upgrades its record). 인용·피인용 asks Semantic
 * Scholar by the candidate's IDs and opens the list as a related session.
 */
export function CandidateActions({ candidate, titleId, handlers }: CandidateActionsProps) {
  const { source, onCandidate, onRefresh, onSkipped } = handlers;
  const toast = useToast();
  const reasonId = useId();
  const progressId = useId();
  const relatedReasonId = useId();
  const notesRef = useRef<HTMLDivElement>(null);
  const [dialog, setDialog] = useState<DialogName | null>(null);
  const [pending, setPending] = useState<Pending>(null);
  const [dialogError, setDialogError] = useState<string | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  const candidateId = candidate.candidate_id;
  const key = candidateKey(source, candidateId);
  const track = useRegisterTrack(key);
  const registering = track !== null && track.outcome === null;
  const owned = candidate.library !== null;
  const canKeep = !owned && candidate.status !== 'keep' && candidate.status !== 'registered';
  const canRegister = candidate.status === 'keep' || (!owned && candidate.status !== 'registered');
  const canRestore = !owned && candidate.status === 'skipped';
  const canSkip = !owned && candidate.status === 'new';
  const librarySlug = candidate.library?.slug ?? candidate.slug;
  const related = useRelatedLookup({ title: candidate.title, ids: candidate.ids });
  const relatedBlocked = !hasRelatedIdentifier(candidate.ids);

  // Why Keep or 등록 is unavailable (or what 등록 would add), referenced by both buttons.
  const reason =
    candidate.status === 'keep'
      ? `Keep에 담았습니다${librarySlug ? ` (${librarySlug})` : ''}. ‘등록’하면 PDF를 찾아 정식으로 등록합니다.`
      : candidate.status === 'registered'
        ? `등록한 후보입니다${librarySlug ? ` (${librarySlug})` : ''}.`
        : owned
          ? '라이브러리에 이미 있는 논문이라 Keep에 담거나 등록하지 않습니다.'
          : null;
  const describedBy = [titleId, reason ? reasonId : null, registering ? progressId : null].filter(Boolean).join(' ');

  const openDialog = (name: DialogName) => {
    setDialogError(null);
    setDialog(name);
  };

  /** Message for a failed request; answers that mean the shown data is stale also re-read it. */
  const failure = (error: ApiError, failed: string): string => {
    if (STALE_CODES[error.code]) onRefresh(candidateId);
    return errorText(error, failed);
  };

  const submitKeep = async (reasonText: string) => {
    if (pending) return;
    setPending('keep');
    setDialogError(null);
    try {
      const result = await keepCandidate({
        source,
        candidate_id: candidateId,
        reason: reasonText.trim() ? reasonText : null,
      });
      onCandidate(result.candidate);
      setDialog(null);
      toast({
        tone: 'success',
        title: `Keep에 담았습니다 — ${result.slug}`,
        text: 'keep.md 맨 위에 항목을 넣고 논문 기록(읽기 상태 Keep)을 만들었습니다.',
        action: { label: '라이브러리에서 보기', href: paperHref(result.slug) },
      });
    } catch (caught) {
      setDialogError(failure(toApiError(caught), 'Keep에 담지 못했습니다'));
    } finally {
      setPending(null);
    }
  };

  const submitRegister = async (category: DiscoveryCategory) => {
    if (pending) return;
    setPending('register');
    setDialogError(null);
    try {
      const result = await registerCandidate({ source, candidate_id: candidateId, category });
      trackRegister(key, result.job, result.slug);
      onCandidate(result.candidate);
      setDialog(null);
    } catch (caught) {
      setDialogError(failure(toApiError(caught), '등록을 시작하지 못했습니다'));
    } finally {
      setPending(null);
    }
  };

  const toggleSkipped = async () => {
    if (pending || registering) return;
    const next = canRestore ? 'new' : 'skipped';
    setPending('status');
    setStatusError(null);
    try {
      onCandidate(await setCandidateStatus({ source, candidate_id: candidateId, status: next }));
      if (next === 'skipped') onSkipped?.();
    } catch (caught) {
      setStatusError(failure(toApiError(caught), next === 'skipped' ? '넘기지 못했습니다' : '복원하지 못했습니다'));
    } finally {
      setPending(null);
    }
  };

  // Announced once per job: a remounted card replaying the stream only records the outcome.
  const onRegisterEnded = (jobId: string, outcome: RegisterOutcome) => {
    if (!finishRegister(key, jobId, outcome)) return;
    if (outcome.status === 'cancelled') {
      // The server publishes before the terminal event and finishes a publish that already began even
      // when the cancel arrives meanwhile, so the first re-read after it tells which one happened.
      onRefresh(candidateId, (current) => {
        if (current === undefined) {
          toast({
            title: '등록 취소를 요청했습니다',
            text: '게시가 이미 시작됐다면 등록 결과가 남을 수 있습니다. 라이브러리에서 확인하세요.',
          });
          return true;
        }
        const published = current.status === 'registered';
        confirmCancel(key, jobId, published);
        if (!published) {
          toast({ title: '등록을 취소했습니다', text: '게시가 시작되기 전이라 바뀐 파일은 없습니다.' });
          return true;
        }
        const slug = current.slug ?? current.library?.slug ?? track?.slug ?? null;
        toast({
          tone: 'success',
          title: slug ? `등록했습니다 — ${slug}` : '등록했습니다',
          text: CANCEL_TOO_LATE,
          action: slug ? { label: '라이브러리에서 보기', href: paperHref(slug) } : undefined,
        });
        return true;
      });
      return;
    }
    if (outcome.status !== 'completed') {
      onRefresh(candidateId);
      if (outcome.status === 'failed') toast({ tone: 'danger', title: '등록하지 못했습니다', text: outcome.message });
      return;
    }
    // The server marks the candidate registered just before the terminal event.
    onRefresh(candidateId, (current) => current === undefined || current.status === 'registered');
    const slug = outcome.registration?.slug ?? track?.slug ?? null;
    const warnings = outcome.registration?.warnings.length ?? 0;
    const saved = outcome.registration?.pdf_path
      ? 'PDF와 논문 기록, keep.md·index.md 항목을 저장했습니다.'
      : 'PDF를 구하지 못해 서지 정보만 등록했습니다. 라이브러리에 ‘PDF 필요’로 표시됩니다.';
    toast({
      tone: 'success',
      title: slug ? `등록했습니다 — ${slug}` : '등록했습니다',
      text: warnings > 0 ? `${saved} 경고 ${warnings}건은 후보 카드에서 확인하세요.` : saved,
      action: slug ? { label: '라이브러리에서 보기', href: paperHref(slug) } : undefined,
    });
  };

  const skipBusy = pending !== null || registering;

  return (
    <div className="candidate-actions-area">
      {/* Focus lands here when the button that opened a dialog was disabled by its own success. */}
      <div className="candidate-action-notes" ref={notesRef} tabIndex={-1}>
        {reason ? (
          <p className="field-hint" id={reasonId}>
            {reason}
          </p>
        ) : null}
        {track && track.outcome === null ? (
          <RegisterProgress track={track} id={progressId} onEnded={onRegisterEnded} />
        ) : track?.outcome ? (
          <RegisterResult
            outcome={track.outcome}
            slug={track.slug ?? librarySlug}
            candidateRegistered={candidate.status === 'registered'}
          />
        ) : null}
        {statusError ? (
          <p className="field-error" role="alert">
            {statusError}
          </p>
        ) : null}
        {relatedBlocked ? (
          <p className="field-hint" id={relatedReasonId}>
            arXiv·DOI·Semantic Scholar 식별자가 없어 인용·피인용 목록은 조회할 수 없습니다.
          </p>
        ) : null}
        <RelatedNotice lookup={related} />
      </div>

      <div className="candidate-actions">
        <button
          type="button"
          className="btn btn-tonal btn-small"
          onClick={() => openDialog('keep')}
          disabled={!canKeep || registering}
          aria-describedby={describedBy}
        >
          <BookmarkPlus />
          Keep에 담기
        </button>
        <button
          type="button"
          className="btn btn-tonal btn-small"
          onClick={() => openDialog('register')}
          disabled={!canRegister || registering}
          aria-describedby={describedBy}
          aria-busy={registering}
        >
          <Library />
          {registering ? '등록하는 중…' : '등록'}
        </button>
        <RelatedMenu
          lookup={related}
          describedBy={relatedBlocked ? `${titleId} ${relatedReasonId}` : titleId}
          disabled={relatedBlocked}
          className="btn btn-secondary btn-small"
        />
        {canSkip || canRestore ? (
          // One element for both labels, so focus stays on it when 넘김 turns into 복원 and back.
          <button
            type="button"
            className="btn btn-text btn-small candidate-skip"
            onClick={() => void toggleSkipped()}
            aria-disabled={skipBusy}
            aria-busy={pending === 'status'}
            aria-describedby={titleId}
          >
            {canRestore ? <Undo2 /> : <EyeOff />}
            {pending === 'status' ? '처리하는 중…' : canRestore ? '복원' : '넘김'}
          </button>
        ) : null}
      </div>

      <KeepDialog
        open={dialog === 'keep'}
        candidate={candidate}
        pending={pending === 'keep'}
        error={dialog === 'keep' ? dialogError : null}
        onSubmit={(text) => void submitKeep(text)}
        onClose={() => setDialog(null)}
        fallbackFocus={notesRef}
      />
      <CategoryDialog
        open={dialog === 'register'}
        candidate={candidate}
        pending={pending === 'register'}
        error={dialog === 'register' ? dialogError : null}
        onSubmit={(category) => void submitRegister(category)}
        onClose={() => setDialog(null)}
        fallbackFocus={notesRef}
      />
    </div>
  );
}
