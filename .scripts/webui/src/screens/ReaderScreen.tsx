import { useCallback, useEffect, useMemo, useRef, useState, type Ref } from 'react';
import { fetchPaper, fetchReaderStatus, toApiError, type ApiError } from '../api/client';
import type { EvidenceItem, PaperBundle, ReaderAnchor, ReaderStatus, ReaderThread, ReviewQueueJob } from '../api/types';
import { ErrorNotice } from '../components/ErrorNotice';
import { useToast } from '../components/Toast';
import { formatCount } from '../format';
import { PAPERS_HREF } from '../hooks/useHashRoute';
import { ReaderContext, type ReaderActions } from '../reader/context';
import { targetKey, targetsByPage } from '../reader/evidence';
import { PdfPane, type FlashState, type PdfPaneHandle } from '../reader/PdfPane';
import { QuestionsPanel, ReaderRoleBadge, regionBlockedReason, type DraftAnchor } from '../reader/QuestionsPanel';
import { ReaderToolbar } from '../reader/ReaderToolbar';
import { RelatedStrip } from '../reader/RelatedStrip';
import { ReviewPanel, type ReviewView, type VerifyControl } from '../reader/ReviewPanel';
import { clampPanelWidth, SidePanel, type PanelTab } from '../reader/SidePanel';
import { usePdfDocument } from '../reader/usePdfDocument';
import { useThreads } from '../reader/useThreads';
import { useVerification } from '../reader/useVerification';
import { useStatus } from '../status';
import { verifierBlockedReason } from '../verification';
import '../styles/reader.css';

const PANEL_WIDTH_KEY = 'research-webui.reader.panel-width';
const DEFAULT_PANEL_WIDTH = 520;
/** Below this width the side panel overlays the PDF instead of sitting beside it. */
const NARROW_QUERY = '(max-width: 900px)';
const FLASH_MS = 2400;
const EMPTY_ITEMS: readonly EvidenceItem[] = [];
/** Review image paths the reader loads: `figures/<name>.svg`, optionally `./`, beside the review file. */
const FIGURE_SRC = /^(?:\.\/)?figures\/([a-z0-9][a-z0-9-]*\.svg)$/;
/** What must follow `{slug}-` in a figure name (the server's `^{slug}-[a-z0-9][a-z0-9-]*\.svg$`). */
const FIGURE_SUFFIX = /^[a-z0-9][a-z0-9-]*\.svg$/;

/** `GET /api/papers/{slug}/figures/{name}` for this paper's own figure, or null for any other image path. */
function figureApiUrl(slug: string, src: string): string | null {
  const name = FIGURE_SRC.exec(src)?.[1];
  if (!name?.startsWith(`${slug}-`) || !FIGURE_SUFFIX.test(name.slice(slug.length + 1))) return null;
  return `/api/papers/${encodeURIComponent(slug)}/figures/${name}`;
}

function storedPanelWidth(): number {
  try {
    const value = Number(window.localStorage.getItem(PANEL_WIDTH_KEY));
    return Number.isFinite(value) && value > 0 ? value : DEFAULT_PANEL_WIDTH;
  } catch {
    return DEFAULT_PANEL_WIDTH;
  }
}

function editableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return target.isContentEditable || target.tagName === 'INPUT' || target.tagName === 'TEXTAREA' || target.tagName === 'SELECT';
}

interface BundleState {
  bundle: PaperBundle | null;
  error: ApiError | null;
  loading: boolean;
}

interface StatusState {
  status: ReaderStatus | null;
  error: ApiError | null;
  loading: boolean;
}

function ReaderUnavailable({ error, onRetry }: { error: ApiError; onRetry: () => void }) {
  if (error.code === 'not_found' || error.code === 'bad_request') {
    return (
      <div className="reader-missing">
        <h2>{error.code === 'not_found' ? '논문을 찾을 수 없습니다' : '논문 주소가 올바르지 않습니다'}</h2>
        <p>
          라이브러리(<code translate="no">01-Papers/library/</code>)에 이 slug의 레코드가 없습니다. 주소를 확인하거나 목록에서
          논문을 고르세요.
        </p>
        <p className="notice-detail">
          <code translate="no">{error.code}</code> {error.message}
        </p>
        <a className="btn btn-primary" href={PAPERS_HREF}>
          논문 목록으로
        </a>
      </div>
    );
  }
  return (
    <div className="reader-missing">
      <ErrorNotice error={error} title="논문을 불러오지 못했습니다." onRetry={onRetry} />
    </div>
  );
}

export default function ReaderScreen({
  slug,
  headingRef,
  reloadToken,
}: {
  slug: string;
  headingRef: Ref<HTMLHeadingElement>;
  reloadToken: number;
}) {
  const [bundleState, setBundleState] = useState<BundleState>({ bundle: null, error: null, loading: true });
  const [statusState, setStatusState] = useState<StatusState>({ status: null, error: null, loading: true });
  const [loadToken, setLoadToken] = useState(0);
  /** Bumped after a verification run ends: reloads the bundle (badge, 검증 view) but not the threads. */
  const [bundleToken, setBundleToken] = useState(0);
  const [statusToken, setStatusToken] = useState(0);
  const [pdfToken, setPdfToken] = useState(0);
  const threadsState = useThreads(slug, reloadToken + loadToken);
  const appStatus = useStatus();
  const toast = useToast();

  useEffect(() => {
    const controller = new AbortController();
    setBundleState((previous) => ({ ...previous, loading: true }));
    fetchPaper(slug, controller.signal).then(
      (bundle) => setBundleState({ bundle, error: null, loading: false }),
      (error: unknown) => {
        if (!controller.signal.aborted) setBundleState((previous) => ({ ...previous, error: toApiError(error), loading: false }));
      },
    );
    return () => controller.abort();
  }, [slug, reloadToken, loadToken, bundleToken]);

  const refreshAppStatus = appStatus.refresh;
  const onVerified = useCallback(
    (job: ReviewQueueJob) => {
      setBundleToken((token) => token + 1);
      // One reload so the 상태 review queue shows the finished run (GET /api/status is never polled).
      refreshAppStatus();
      const verification = job.verification ?? null;
      if (job.status === 'failed') {
        toast({ tone: 'danger', title: '검증이 실패했습니다', text: job.message ? job.message.slice(0, 160) : undefined });
      } else if (job.status !== 'completed' || !verification) {
        toast({ title: '검증 작업이 끝났습니다' });
      } else if (verification.status === 'passed') {
        toast({ tone: 'success', title: '검증을 통과했습니다', text: '차단 이슈 없이 원문 대조를 마쳤습니다.' });
      } else if (verification.status === 'issues') {
        toast({
          title: '검증에서 이슈를 찾았습니다',
          text: verification.note || `차단 이슈 ${formatCount(verification.blocking_issues)}건 · 미확인·불일치 ${formatCount(verification.mismatches)}건`,
        });
      } else if (verification.status === 'error') {
        toast({ tone: 'danger', title: '검증 중 오류가 났습니다', text: '리뷰 탭의 검증 보기에서 사유를 확인하세요.' });
      } else {
        toast({ title: '검증을 건너뛰었습니다' });
      }
    },
    [refreshAppStatus, toast],
  );
  const verification = useVerification(slug, onVerified);

  useEffect(() => {
    const controller = new AbortController();
    setStatusState((previous) => ({ ...previous, loading: true }));
    fetchReaderStatus(controller.signal).then(
      (status) => setStatusState({ status, error: null, loading: false }),
      (error: unknown) => {
        if (!controller.signal.aborted) setStatusState((previous) => ({ ...previous, error: toApiError(error), loading: false }));
      },
    );
    return () => controller.abort();
  }, [reloadToken, statusToken]);

  const { bundle } = bundleState;
  const pdfUrl = bundle?.pdf.available ? bundle.pdf.url : null;
  const { doc, error: pdfError, progress } = usePdfDocument(pdfUrl, pdfToken);
  const pageCount = doc?.numPages ?? 0;
  const title = bundle?.paper.title || slug;

  useEffect(() => {
    document.title = `${title} · 논문 리더 · 연구 하네스 WebUI`;
  }, [title]);

  // ── View state ──
  const [zoom, setZoom] = useState(1);
  const [fit, setFit] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [captureMode, setCaptureMode] = useState(false);
  const [highlightsVisible, setHighlightsVisible] = useState(true);
  const [panelOpen, setPanelOpen] = useState(() => !window.matchMedia(NARROW_QUERY).matches);
  const [panelWidth, setPanelWidth] = useState(() => clampPanelWidth(storedPanelWidth(), window.innerWidth));
  const [tab, setTab] = useState<PanelTab>('review');
  const [reviewView, setReviewView] = useState<ReviewView>('evidence');
  const [activeClaimId, setActiveClaimId] = useState<string | null>(null);
  /** One-shot requests, cleared by the panel that handles them (so tab switches do not steal focus). */
  const [claimFocusRequest, setClaimFocusRequest] = useState<string | null>(null);
  const [flash, setFlash] = useState<FlashState | null>(null);
  const [overlay, setOverlay] = useState<ReaderAnchor | null>(null);
  const [draft, setDraft] = useState<DraftAnchor | null>(null);
  const [composerFocusRequest, setComposerFocusRequest] = useState(false);
  const [activeThreadId, setActiveThreadId] = useState<string | null>(null);
  const paneRef = useRef<PdfPaneHandle>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const flashTimer = useRef(0);
  const draftRef = useRef<DraftAnchor | null>(null);

  const items = bundle?.evidence.items ?? EMPTY_ITEMS;
  const claims = useMemo(() => new Map(items.map((item) => [item.claim_id, item])), [items]);
  const pageTargets = useMemo(() => targetsByPage(items), [items]);

  useEffect(() => {
    draftRef.current = draft;
  }, [draft]);
  useEffect(
    () => () => {
      window.clearTimeout(flashTimer.current);
      if (draftRef.current?.preview) URL.revokeObjectURL(draftRef.current.preview);
    },
    [],
  );

  /** Flashes claim highlights (`keys`), or the whole `page` when no highlight is named. */
  const startFlash = useCallback((keys: readonly string[], page: number | null) => {
    window.clearTimeout(flashTimer.current);
    setFlash((previous) => ({ keys: new Set(keys), page, token: (previous?.token ?? 0) + 1 }));
    flashTimer.current = window.setTimeout(() => setFlash(null), FLASH_MS);
  }, []);

  const goToPage = useCallback(
    (page: number, keys?: readonly string[]) => {
      if (page < 1 || page > pageCount) return;
      const named = keys && keys.length > 0 ? keys : null;
      paneRef.current?.scrollToPage(page, named ? { keys: named } : {});
      startFlash(named ?? [], named ? null : page);
    },
    [pageCount, startFlash],
  );

  const focusClaim = useCallback((claimId: string) => {
    setPanelOpen(true);
    setTab('review');
    setReviewView('evidence');
    setActiveClaimId(claimId);
    setClaimFocusRequest(claimId);
  }, []);

  const clearClaimFocusRequest = useCallback(() => setClaimFocusRequest(null), []);
  const clearComposerFocusRequest = useCallback(() => setComposerFocusRequest(false), []);

  const claimTargets = useCallback(
    (claimId: string): { page: number | null; keys: string[] } => {
      const claim = claims.get(claimId);
      if (!claim) return { page: null, keys: [] };
      const first = claim.targets.find((target) => target.page !== null);
      return { page: first?.page ?? null, keys: claim.targets.map((_, index) => targetKey(claimId, index)) };
    },
    [claims],
  );

  const showAnchor = useCallback(
    (anchor: ReaderAnchor) => {
      if (anchor.kind === 'claim') {
        const { page, keys } = claimTargets(anchor.claim_id);
        const target = anchor.page ?? page;
        if (target !== null) goToPage(target, keys);
        return;
      }
      if (anchor.page < 1 || anchor.page > pageCount) return;
      setOverlay(anchor);
      const y =
        anchor.kind === 'text' && anchor.rects.length > 0
          ? Math.min(...anchor.rects.map((rect) => rect[1]))
          : anchor.kind === 'region'
            ? anchor.bbox[1]
            : undefined;
      paneRef.current?.scrollToPage(anchor.page, y === undefined ? {} : { y });
    },
    [claimTargets, goToPage, pageCount],
  );

  const replaceDraft = useCallback((next: DraftAnchor | null) => {
    setDraft((previous) => {
      if (previous?.preview && previous.preview !== next?.preview) URL.revokeObjectURL(previous.preview);
      return next;
    });
  }, []);

  const askAbout = useCallback(
    (anchor: ReaderAnchor, preview: string | null = null) => {
      replaceDraft({ anchor, preview });
      setOverlay(anchor.kind === 'claim' ? null : anchor);
      setActiveThreadId(null);
      setPanelOpen(true);
      setTab('questions');
      setComposerFocusRequest(true);
    },
    [replaceDraft],
  );

  const clearDraft = useCallback(() => {
    replaceDraft(null);
    setOverlay(null);
  }, [replaceDraft]);

  const openThread = useCallback(
    (thread: ReaderThread | null, reveal = true) => {
      setActiveThreadId(thread?.thread_id ?? null);
      if (!thread) {
        setOverlay(draftRef.current && draftRef.current.anchor.kind !== 'claim' ? draftRef.current.anchor : null);
        return;
      }
      const anchor = thread.anchor ?? thread.turns[0]?.anchor ?? null;
      if (anchor && reveal) showAnchor(anchor);
      else if (anchor) setOverlay(anchor.kind === 'claim' ? null : anchor);
      else setOverlay(null);
    },
    [showAnchor],
  );

  const askClaim = useCallback(
    (item: EvidenceItem) => {
      const { page, keys } = claimTargets(item.claim_id);
      askAbout({ kind: 'claim', page, claim_id: item.claim_id });
      if (page !== null) goToPage(page, keys);
    },
    [askAbout, claimTargets, goToPage],
  );

  const onZoom = useCallback((next: number) => {
    setFit(false);
    setZoom(next);
  }, []);

  // Toolbar navigation: a plain jump, no flash.
  const pageGo = useCallback(
    (page: number) => paneRef.current?.scrollToPage(Math.min(pageCount, Math.max(1, page))),
    [pageCount],
  );

  const resizePanel = useCallback((width: number) => {
    setPanelWidth(clampPanelWidth(width, bodyRef.current?.clientWidth ?? window.innerWidth));
  }, []);

  useEffect(() => {
    try {
      window.localStorage.setItem(PANEL_WIDTH_KEY, String(panelWidth));
    } catch {
      // Storage can be unavailable (private mode); the width then lasts for this visit.
    }
  }, [panelWidth]);

  // R toggles region capture, Esc leaves it (outside text fields).
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.defaultPrevented || editableTarget(event.target)) return;
      if (event.key === 'Escape' && captureMode) {
        setCaptureMode(false);
        return;
      }
      if ((event.key === 'r' || event.key === 'R') && !event.metaKey && !event.ctrlKey && !event.altKey && pageCount > 0) {
        event.preventDefault();
        setCaptureMode((on) => !on);
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => document.removeEventListener('keydown', onKeyDown);
  }, [captureMode, pageCount]);

  const figureUrl = useCallback((src: string) => figureApiUrl(slug, src), [slug]);

  const actions = useMemo<ReaderActions>(
    () => ({ pageCount, goToPage, focusClaim, showAnchor, askAbout, figureUrl }),
    [pageCount, goToPage, focusClaim, showAnchor, askAbout, figureUrl],
  );

  if (!bundle) {
    return (
      <div className="reader">
        <ReaderToolbar
          title={bundleState.error ? slug : '논문을 불러오는 중…'}
          headingRef={headingRef}
          pdf={null}
          panel={null}
        />
        {bundleState.error ? (
          <ReaderUnavailable error={bundleState.error} onRetry={() => setLoadToken((token) => token + 1)} />
        ) : (
          <p className="reader-boot" role="status">
            논문과 리뷰 근거를 불러오는 중…
          </p>
        )}
      </div>
    );
  }

  const regionBlocked = regionBlockedReason(statusState.status);
  const threadCount = threadsState.threads?.length ?? 0;
  const roleBlocked = verifierBlockedReason(appStatus);
  const fileBlocked = !bundle.review.available
    ? '리뷰 문서가 없어 검증할 수 없습니다. 먼저 논문 리뷰를 실행하세요.'
    : !bundle.pdf.available
      ? '원문 PDF가 없어 리뷰와 대조할 수 없습니다.'
      : null;
  const verify: VerifyControl = {
    job: verification.job,
    pending: verification.pending,
    error: verification.error,
    blocked: fileBlocked ?? roleBlocked,
    blockedFix: fileBlocked ? null : !appStatus.data ? (appStatus.loading ? null : 'recheck') : roleBlocked ? 'status' : null,
    onStart: verification.start,
    onRecheck: refreshAppStatus,
  };

  let pdfArea;
  if (!bundle.pdf.available) {
    pdfArea = (
      <div className="pdf-state">
        <h2>PDF가 없습니다</h2>
        <p>
          이 논문은 라이브러리에 PDF가 없어 원문을 표시할 수 없습니다. 오른쪽 패널에서 리뷰와 근거는 볼 수 있습니다.{' '}
          <code translate="no">01-Papers/pdfs/</code>에 PDF를 두고 레코드의 <code translate="no">source.pdf_path</code>를
          맞추면 열립니다.
        </p>
      </div>
    );
  } else if (pdfError) {
    pdfArea = (
      <div className="pdf-state" role="alert">
        <h2>PDF를 열지 못했습니다</h2>
        <p>{pdfError}</p>
        <button type="button" className="btn btn-secondary btn-small" onClick={() => setPdfToken((token) => token + 1)}>
          다시 불러오기
        </button>
      </div>
    );
  } else if (!doc) {
    pdfArea = (
      <div className="pdf-state" role="status">
        <p>
          PDF를 불러오는 중…
          {progress !== null ? <span className="num"> {Math.round(progress * 100)}%</span> : null}
        </p>
        <span className="pdf-progress" aria-hidden="true">
          <span style={{ transform: `scaleX(${progress ?? 0.08})` }} />
        </span>
      </div>
    );
  } else {
    pdfArea = (
      <PdfPane
        ref={paneRef}
        doc={doc}
        zoom={zoom}
        fit={fit}
        onFitZoom={setZoom}
        onCurrentPage={setCurrentPage}
        targetsByPage={pageTargets}
        highlightsVisible={highlightsVisible}
        activeClaimId={activeClaimId}
        flash={flash}
        overlay={overlay}
        captureMode={captureMode}
        onCaptureModeChange={setCaptureMode}
        regionBlocked={regionBlocked}
        onActivateClaim={focusClaim}
        onAsk={askAbout}
      />
    );
  }

  return (
    <ReaderContext value={actions}>
      <div className="reader">
        <ReaderToolbar
          title={title}
          headingRef={headingRef}
          pdf={
            pageCount > 0
              ? {
                  pageCount,
                  currentPage,
                  onGoToPage: pageGo,
                  zoom,
                  fit,
                  onZoom,
                  onFit: () => setFit(true),
                  captureMode,
                  onToggleCapture: () => setCaptureMode((on) => !on),
                  highlightsVisible,
                  onToggleHighlights: () => setHighlightsVisible((on) => !on),
                }
              : null
          }
          panel={{ open: panelOpen, onToggle: () => setPanelOpen((open) => !open) }}
        />
        {captureMode ? (
          <p className="capture-hint" role="status">
            영역 캡처: 표나 그림을 끌어서 고르세요. <kbd>Esc</kbd>로 취소합니다.
          </p>
        ) : null}
        <div className="reader-body" ref={bodyRef}>
          <div className="pdf-area">{pdfArea}</div>
          <SidePanel
            open={panelOpen}
            width={panelWidth}
            onResize={resizePanel}
            tab={tab}
            onTabChange={setTab}
            questionCount={threadCount}
            header={
              <>
                <RelatedStrip slug={slug} />
                {tab === 'questions' ? (
                  <ReaderRoleBadge
                    status={statusState.status}
                    error={statusState.error}
                    loading={statusState.loading}
                    onRefresh={() => setStatusToken((token) => token + 1)}
                  />
                ) : null}
              </>
            }
          >
            {tab === 'review' ? (
              <ReviewPanel
                bundle={bundle}
                view={reviewView}
                onViewChange={setReviewView}
                activeClaimId={activeClaimId}
                focusRequest={claimFocusRequest}
                onFocusHandled={clearClaimFocusRequest}
                onAskClaim={askClaim}
                verify={verify}
              />
            ) : (
              <QuestionsPanel
                slug={slug}
                status={statusState.status}
                threadsState={threadsState}
                activeThreadId={activeThreadId}
                onOpenThread={openThread}
                draft={draft}
                onClearDraft={clearDraft}
                composerFocusRequest={composerFocusRequest}
                onComposerFocused={clearComposerFocusRequest}
                currentPage={currentPage}
                pdfAvailable={pageCount > 0}
                pdfSha={bundle.pdf.sha256}
                claims={claims}
              />
            )}
          </SidePanel>
        </div>
      </div>
    </ReaderContext>
  );
}
