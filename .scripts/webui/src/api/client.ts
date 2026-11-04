import type {
  ApiErrorBody,
  AskRequest,
  AskResponse,
  CreateJobRequest,
  GraphifySync,
  HarnessCheckName,
  HarnessPayload,
  Idea,
  IdeasPayload,
  JobRecord,
  PaperBundle,
  PaperLabels,
  PapersPayload,
  ReaderStatus,
  ReaderThread,
  ReviewDetail,
  ReviewQueueJob,
  RoleResolution,
  Session,
  StatusPayload,
} from './types';

/** Failure of an API call. `code` is the server's error code or a client code (`offline`, `timeout`, `bad_response`). */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

export function toApiError(error: unknown): ApiError {
  if (error instanceof ApiError) return error;
  const message = error instanceof Error ? error.message : String(error);
  return new ApiError(0, 'client_error', message || '알 수 없는 오류가 발생했습니다.');
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError';
}

// ── Connection state shared by the header, the offline banner, and every call ──

export type ConnectionState = 'connecting' | 'online' | 'offline';

/** Session fields safe to render. The CSRF token stays private to this module. */
export interface PublicSession {
  workspace_id: string;
  port: number;
  version: string;
}

export interface ConnectionSnapshot {
  state: ConnectionState;
  session: PublicSession | null;
  sessionError: ApiError | null;
}

let snapshot: ConnectionSnapshot = { state: 'connecting', session: null, sessionError: null };
const listeners = new Set<() => void>();

function updateConnection(patch: Partial<ConnectionSnapshot>): void {
  const next = { ...snapshot, ...patch };
  if (
    next.state === snapshot.state &&
    next.session === snapshot.session &&
    next.sessionError === snapshot.sessionError
  ) {
    return;
  }
  snapshot = next;
  for (const listener of listeners) listener();
}

export function subscribeConnection(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getConnectionSnapshot(): ConnectionSnapshot {
  return snapshot;
}

// ── Transport ──

const DEFAULT_TIMEOUT_MS = 30_000;
/** Probing three agent CLIs can take tens of seconds (research_agent.probe uses 15 s timeouts). */
const STATUS_TIMEOUT_MS = 120_000;
/** The Vite dev proxy answers 502 when the WebUI server is down. */
const PROXY_DOWN_STATUSES = new Set([502, 503, 504]);
const ACCEPT_JSON = { Accept: 'application/json' } as const;

interface RequestOptions {
  signal?: AbortSignal;
  timeoutMs?: number;
}

function offlineError(): ApiError {
  return new ApiError(0, 'offline', '로컬 서버에 연결할 수 없습니다.');
}

function timeoutError(): ApiError {
  return new ApiError(0, 'timeout', '서버 응답 시간이 초과되었습니다.');
}

function isErrorBody(value: unknown): value is ApiErrorBody {
  return typeof value === 'object' && value !== null && 'error' in value && typeof value.error === 'string';
}

/**
 * Sends one request and returns the parsed JSON object.
 * Rejects with ApiError, or rethrows the AbortError when the caller's signal aborts.
 */
async function request<T>(path: string, init: RequestInit, options: RequestOptions = {}): Promise<T> {
  const { signal, timeoutMs = DEFAULT_TIMEOUT_MS } = options;
  const controller = new AbortController();
  let timedOut = false;
  const timer = window.setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const forwardAbort = () => controller.abort();
  if (signal?.aborted) controller.abort();
  else signal?.addEventListener('abort', forwardAbort, { once: true });

  try {
    let response: Response;
    try {
      response = await fetch(path, {
        ...init,
        signal: controller.signal,
        cache: 'no-store',
        credentials: 'same-origin',
      });
    } catch (error) {
      if (signal?.aborted) throw error;
      if (timedOut) throw timeoutError();
      updateConnection({ state: 'offline' });
      throw offlineError();
    }

    let body: unknown;
    try {
      const raw = await response.text();
      body = raw ? JSON.parse(raw) : null;
    } catch (error) {
      if (signal?.aborted) throw error;
      if (timedOut) throw timeoutError();
      body = undefined; // not JSON
    }

    if (!response.ok) {
      if (isErrorBody(body)) {
        updateConnection({ state: 'online' });
        const code = typeof body.code === 'string' && body.code ? body.code : `http_${response.status}`;
        throw new ApiError(response.status, code, body.error);
      }
      if (PROXY_DOWN_STATUSES.has(response.status)) {
        updateConnection({ state: 'offline' });
        throw offlineError();
      }
      updateConnection({ state: 'online' });
      throw new ApiError(response.status, `http_${response.status}`, `요청이 실패했습니다 (HTTP ${response.status}).`);
    }

    updateConnection({ state: 'online' });
    if (typeof body !== 'object' || body === null) {
      throw new ApiError(response.status, 'bad_response', '서버 응답 형식이 올바르지 않습니다.');
    }
    return body as T;
  } finally {
    window.clearTimeout(timer);
    signal?.removeEventListener('abort', forwardAbort);
  }
}

// ── Session and CSRF ──

let csrfToken: string | null = null;
let sessionRequest: Promise<PublicSession> | null = null;

/** GET /api/session once (or again with `force`); keeps the CSRF token in memory only. */
export function loadSession(force = false): Promise<PublicSession> {
  if (sessionRequest && !force) return sessionRequest;
  const pending: Promise<PublicSession> = request<Partial<Session>>('/api/session', {
    method: 'GET',
    headers: ACCEPT_JSON,
  })
    .then((body) => {
      if (typeof body.csrf_token !== 'string' || body.csrf_token === '') {
        throw new ApiError(200, 'bad_response', '세션 응답에 CSRF 토큰이 없습니다.');
      }
      csrfToken = body.csrf_token;
      const session: PublicSession = {
        workspace_id: typeof body.workspace_id === 'string' ? body.workspace_id : '',
        port: typeof body.port === 'number' ? body.port : 0,
        version: typeof body.version === 'string' ? body.version : '',
      };
      updateConnection({ session, sessionError: null });
      return session;
    })
    .catch((error: unknown) => {
      const apiError = toApiError(error);
      if (sessionRequest === pending) sessionRequest = null;
      updateConnection({ sessionError: apiError });
      throw apiError;
    });
  sessionRequest = pending;
  return pending;
}

/**
 * JSON POST/DELETE with the CSRF header. A rejected token (server restart) triggers one fresh session
 * and one retry.
 */
async function sendJson<T>(
  path: string,
  payload: unknown,
  { method = 'POST', timeoutMs }: { method?: 'POST' | 'DELETE'; timeoutMs?: number } = {},
): Promise<T> {
  const send = async (): Promise<T> => {
    await loadSession();
    return request<T>(
      path,
      {
        method,
        headers: {
          ...ACCEPT_JSON,
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken ?? '',
        },
        body: JSON.stringify(payload),
      },
      { timeoutMs },
    );
  };
  try {
    return await send();
  } catch (error) {
    if (!(error instanceof ApiError) || error.code !== 'bad_csrf') throw error;
    await loadSession(true);
    return send();
  }
}

// ── Endpoints ──

function jobPath(jobId: string): string {
  return `/api/jobs/${encodeURIComponent(jobId)}`;
}

function reviewPath(slug: string): string {
  return `/api/reviews/${encodeURIComponent(slug)}`;
}

function badResponse(): ApiError {
  return new ApiError(200, 'bad_response', '서버 응답 형식이 올바르지 않습니다.');
}

/**
 * Missing list fields become empty lists; an unusable resolution becomes null. A resolution whose
 * config read failed keeps `configured: null` with a non-empty `error`, so it can never read as unconfigured.
 */
function normalizeResolution(value: RoleResolution | null | undefined): RoleResolution | null {
  if (typeof value !== 'object' || value === null) return null;
  const error = typeof value.error === 'string' && value.error ? value.error : null;
  const configured = error === null && typeof value.configured === 'boolean' ? value.configured : null;
  return {
    ...value,
    configured,
    error: configured === null ? (error ?? '서버 응답에서 역할 설정 상태를 확인할 수 없습니다.') : null,
    candidates: Array.isArray(value.candidates) ? value.candidates : [],
    notes: Array.isArray(value.notes) ? value.notes : [],
    selected: typeof value.selected === 'number' ? value.selected : null,
  };
}

export async function fetchStatus(signal?: AbortSignal): Promise<StatusPayload> {
  const body = await request<StatusPayload>(
    '/api/status',
    { method: 'GET', headers: ACCEPT_JSON },
    { signal, timeoutMs: STATUS_TIMEOUT_MS },
  );
  const generation = normalizeResolution(body.review_roles?.generation);
  const verification = normalizeResolution(body.review_roles?.verification);
  return {
    ...body,
    candidates: Array.isArray(body.candidates) ? body.candidates : [],
    queue: { ...body.queue, jobs: Array.isArray(body.queue?.jobs) ? body.queue.jobs : [] },
    review_roles: generation && verification ? { generation, verification } : null,
    reader_role: normalizeResolution(body.reader_role),
  };
}

/** Newest first. */
export async function fetchJobs(signal?: AbortSignal): Promise<JobRecord[]> {
  const body = await request<{ jobs?: unknown }>('/api/jobs', { method: 'GET', headers: ACCEPT_JSON }, { signal });
  if (!Array.isArray(body.jobs)) throw badResponse();
  return body.jobs as JobRecord[];
}

export async function fetchJob(jobId: string, signal?: AbortSignal): Promise<JobRecord> {
  const body = await request<{ job?: JobRecord }>(jobPath(jobId), { method: 'GET', headers: ACCEPT_JSON }, { signal });
  if (!body.job) throw badResponse();
  return body.job;
}

export async function createJob(payload: CreateJobRequest): Promise<JobRecord> {
  const body = await sendJson<{ job?: JobRecord }>('/api/jobs', payload);
  if (!body.job) throw badResponse();
  return body.job;
}

export async function cancelJob(jobId: string): Promise<JobRecord> {
  const body = await sendJson<{ job?: JobRecord }>(`${jobPath(jobId)}/cancel`, {});
  if (!body.job) throw badResponse();
  return body.job;
}

/** Review-queue jobs of one paper, plus its stored verification report when one exists. */
export async function fetchReviewDetail(slug: string, signal?: AbortSignal): Promise<ReviewDetail> {
  const body = await request<Partial<ReviewDetail>>(reviewPath(slug), { method: 'GET', headers: ACCEPT_JSON }, { signal });
  if (!Array.isArray(body.jobs)) throw badResponse();
  return body.verification ? { jobs: body.jobs, verification: body.verification } : { jobs: body.jobs };
}

/** Queues a verification-only run (review-queue job of kind `verify`) for an already reviewed paper. */
export async function requestVerification(slug: string): Promise<ReviewQueueJob> {
  const body = await sendJson<{ job?: ReviewQueueJob }>(`${reviewPath(slug)}/verify`, {});
  if (!body.job) throw badResponse();
  return body.job;
}

/** Queues one full paper review (`POST /api/reviews`). The server probes the review role first. */
export async function startReview(slug: string): Promise<ReviewQueueJob> {
  const body = await sendJson<{ job?: ReviewQueueJob }>('/api/reviews', { slug }, { timeoutMs: STATUS_TIMEOUT_MS });
  if (!body.job) throw badResponse();
  return body.job;
}

/** SSE endpoint. `after` resumes a manual reconnect; EventSource's own retries send Last-Event-ID. */
export function jobEventsUrl(jobId: string, after = 0): string {
  const base = `${jobPath(jobId)}/events`;
  return after > 0 ? `${base}?after=${after}` : base;
}

// ── Paper reader ──

function paperPath(slug: string): string {
  return `/api/papers/${encodeURIComponent(slug)}`;
}

function normalizeThread(value: ReaderThread): ReaderThread {
  return { ...value, anchor: value.anchor ?? null, turns: Array.isArray(value.turns) ? value.turns : [] };
}

function stringMap(value: unknown): Record<string, string> {
  if (typeof value !== 'object' || value === null) return {};
  return Object.fromEntries(Object.entries(value).filter((entry): entry is [string, string] => typeof entry[1] === 'string'));
}

/** has_pdf first, then year desc, then title (server order). */
export async function fetchPapers(signal?: AbortSignal): Promise<PapersPayload> {
  const body = await request<Partial<PapersPayload>>('/api/papers', { method: 'GET', headers: ACCEPT_JSON }, { signal });
  if (!Array.isArray(body.papers)) throw badResponse();
  const labels: Partial<PaperLabels> = body.labels ?? {};
  return {
    papers: body.papers.map((paper) => ({
      ...paper,
      display_title: paper.display_title || paper.title || paper.slug,
      authors: Array.isArray(paper.authors) ? paper.authors : [],
      topics: Array.isArray(paper.topics) ? paper.topics : [],
      abstract: typeof paper.abstract === 'string' && paper.abstract ? paper.abstract : null,
      source_url: typeof paper.source_url === 'string' && paper.source_url ? paper.source_url : null,
      review_needed: paper.review_needed === true,
    })),
    errors: Array.isArray(body.errors) ? body.errors : [],
    labels: { category: stringMap(labels.category), reading_status: stringMap(labels.reading_status) },
    queued_statuses: Array.isArray(body.queued_statuses)
      ? body.queued_statuses.filter((status): status is string => typeof status === 'string')
      : [],
  };
}

export async function fetchPaper(slug: string, signal?: AbortSignal): Promise<PaperBundle> {
  const body = await request<Partial<PaperBundle>>(paperPath(slug), { method: 'GET', headers: ACCEPT_JSON }, { signal });
  if (!body.paper || !body.pdf || !body.review || !body.evidence) throw badResponse();
  const items = Array.isArray(body.evidence.items) ? body.evidence.items : [];
  return {
    paper: body.paper,
    pdf: body.pdf,
    review: body.review,
    verification: body.verification ?? null,
    evidence: {
      pages: body.evidence.pages ?? null,
      items: items.map((item) => ({
        ...item,
        evidence: Array.isArray(item.evidence) ? item.evidence : [],
        targets: Array.isArray(item.targets)
          ? item.targets.map((target) => ({
              ...target,
              terms: Array.isArray(target.terms) ? target.terms : [],
              quotes: Array.isArray(target.quotes) ? target.quotes : [],
            }))
          : [],
      })),
      summary: body.evidence.summary ?? { matched: 0, page_only: 0, unresolved: 0 },
    },
  };
}

/** Running turns are already checked against the broker (`interrupted` when the job is gone). */
export async function fetchThreads(slug: string, signal?: AbortSignal): Promise<ReaderThread[]> {
  const body = await request<{ threads?: unknown }>(
    `${paperPath(slug)}/threads`,
    { method: 'GET', headers: ACCEPT_JSON },
    { signal },
  );
  if (!Array.isArray(body.threads)) throw badResponse();
  return (body.threads as ReaderThread[]).map(normalizeThread);
}

export async function deleteThread(slug: string, threadId: string): Promise<void> {
  await sendJson<{ deleted?: string }>(`${paperPath(slug)}/threads/${encodeURIComponent(threadId)}`, {}, {
    method: 'DELETE',
  });
}

/** Submits a `paper.ask` job. The server probes the reader role first, which can take a few seconds. */
export async function askPaper(slug: string, payload: AskRequest): Promise<AskResponse> {
  const body = await sendJson<Partial<AskResponse>>(`${paperPath(slug)}/ask`, payload, {
    timeoutMs: STATUS_TIMEOUT_MS,
  });
  if (!body.job || !body.thread) throw badResponse();
  return { job: body.job, thread: normalizeThread(body.thread) };
}

export async function fetchReaderStatus(signal?: AbortSignal): Promise<ReaderStatus> {
  const body = await request<Partial<ReaderStatus>>(
    '/api/reader/status',
    { method: 'GET', headers: ACCEPT_JSON },
    { signal, timeoutMs: STATUS_TIMEOUT_MS },
  );
  if (typeof body.ready !== 'boolean') throw badResponse();
  return {
    ready: body.ready,
    region_ready: body.region_ready === true,
    reason: typeof body.reason === 'string' && body.reason ? body.reason : null,
    agent: typeof body.agent === 'string' && body.agent ? body.agent : null,
    selector: typeof body.selector === 'string' && body.selector ? body.selector : null,
    configured: typeof body.configured === 'boolean' ? body.configured : null,
    resolution: normalizeResolution(body.resolution),
    pdf_tools: {
      pdftotext: body.pdf_tools?.pdftotext === true,
      pdftoppm: body.pdf_tools?.pdftoppm === true,
      pdfinfo: body.pdf_tools?.pdfinfo === true,
    },
  };
}

// ── Harness ──

function list<T>(value: T[] | null | undefined): T[] {
  return Array.isArray(value) ? value : [];
}

const EMPTY_GRAPHIFY: GraphifySync = { path: '', exists: false, total: 0, by_status: {}, pending: 0, error: null };

/** Harness data for the 하네스 screen. Missing sections become empty (the server lists failed ones in `errors`). */
export async function fetchHarness(signal?: AbortSignal): Promise<HarnessPayload> {
  const body = await request<Partial<HarnessPayload>>('/api/harness', { method: 'GET', headers: ACCEPT_JSON }, { signal });
  if (typeof body.guide !== 'object' || body.guide === null) throw badResponse();
  const skills = list(body.guide.skills).map((skill) => ({ ...skill, uses: list(skill.uses) }));
  return {
    guide: {
      paths: list(body.guide.paths).map((path) => ({ ...path, steps: list(path.steps) })),
      skills,
    },
    routing: list(body.routing),
    skill_links: list(body.skill_links),
    omp_agents: list(body.omp_agents),
    personas: list(body.personas),
    validators: list(body.validators),
    tests_path: typeof body.tests_path === 'string' ? body.tests_path : '',
    graphify: { ...EMPTY_GRAPHIFY, ...body.graphify, by_status: body.graphify?.by_status ?? {} },
    checks: list(body.checks),
    links: {
      router: '',
      harness_graph: '',
      workflow_map: '',
      graphify_sync: '',
      installer_doc: '',
      installer: '',
      ...body.links,
    },
    hrefs: body.hrefs ?? {},
    errors: list(body.errors),
  };
}

/** Starts one of the two fixed harness checks as a broker job (`harness.verify` / `harness.tests`). */
export async function startHarnessCheck(check: HarnessCheckName): Promise<JobRecord> {
  const body = await sendJson<{ job?: JobRecord }>('/api/harness/checks', { check });
  if (!body.job) throw badResponse();
  return body.job;
}

// ── Thought experiments ──

const UNRECORDED = '미기록';

/** Idea values are copied from repository JSON unvalidated: odd scalars become text, null the fallback. */
function ideaText(value: unknown, fallback = UNRECORDED): string {
  if (typeof value === 'string') return value || fallback;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return fallback;
}

function ideaPath(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function ideaPaths(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string' && item !== '') : [];
}

function normalizeIdea(value: Partial<Record<keyof Idea, unknown>>): Idea {
  const id = ideaText(value.id, '');
  return {
    id,
    title: ideaText(value.title, id || UNRECORDED),
    hypothesis: ideaText(value.hypothesis),
    falsification: ideaText(value.falsification),
    topics: ideaText(value.topics),
    updated: ideaText(value.updated, ''),
    literature: ideaText(value.literature),
    review: ideaText(value.review),
    decision: ideaText(value.decision),
    experiment: ideaText(value.experiment),
    note: ideaPath(value.note),
    brief: ideaPath(value.brief),
    results: ideaPath(value.results),
    todo: ideaPath(value.todo),
    registry: stringMap(value.registry),
    validation: ideaText(value.validation),
    noteDecision: ideaText(value.noteDecision),
    noteStatus: ideaText(value.noteStatus),
    decisionConflict: value.decisionConflict === true,
    statusConflict: value.statusConflict === true,
    manifest: ideaPath(value.manifest),
    analysis: ideaPath(value.analysis),
    critiques: ideaPaths(value.critiques),
    evidence: ideaPaths(value.evidence),
    papers: ideaPaths(value.papers),
    paperPaths: ideaPaths(value.paperPaths),
    artifacts: ideaPaths(value.artifacts),
    todoStatus: ideaText(value.todoStatus),
    todoTasks: ideaPaths(value.todoTasks),
    todoResults: ideaPaths(value.todoResults),
  };
}

/** Thought-experiment index (the static page's records). Malformed entries are normalized, never dropped. */
export async function fetchIdeas(signal?: AbortSignal): Promise<IdeasPayload> {
  const body = await request<Partial<IdeasPayload>>('/api/ideas', { method: 'GET', headers: ACCEPT_JSON }, { signal });
  if (!Array.isArray(body.ideas)) throw badResponse();
  return {
    ideas: body.ideas
      .filter((idea): idea is Idea => typeof idea === 'object' && idea !== null)
      .map((idea) => normalizeIdea(idea)),
    hrefs: body.hrefs ?? {},
    errors: list(body.errors),
  };
}
