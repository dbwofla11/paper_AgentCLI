// Types mirroring the M0 HTTP/SSE contract (.scripts/docs/webui-api.md).

export type AgentName = 'codex' | 'claude' | 'omp';

/** Same order as research_agent.AGENTS. */
export const AGENT_NAMES: readonly AgentName[] = ['codex', 'claude', 'omp'];

export function isAgentName(value: unknown): value is AgentName {
  return typeof value === 'string' && (AGENT_NAMES as readonly string[]).includes(value);
}

/** GET /api/session */
export interface Session {
  csrf_token: string;
  workspace_id: string;
  port: number;
  version: string;
}

/** One research_agent.probe() result inside GET /api/status. */
export interface AgentCandidate {
  agent: string;
  installed: boolean;
  authenticated: boolean;
  compatible: boolean;
  ready: boolean;
  login_command: string;
  reason?: string;
}

/** Harness review agents (`.omp/agents/{name}.md`) that the WebUI resolves from the omp config. */
export type ReviewRoleAgent = 'paper-analyst' | 'paper-verifier';

export const REVIEW_ROLE_AGENTS: readonly ReviewRoleAgent[] = ['paper-analyst', 'paper-verifier'];

export function isReviewRoleAgent(value: unknown): value is ReviewRoleAgent {
  return typeof value === 'string' && (REVIEW_ROLE_AGENTS as readonly string[]).includes(value);
}

/** One model selector (`provider/model-id[:effort]`) of a review role, in fallback order. */
export interface RoleModelCandidate {
  selector: string;
  provider: string;
  model: string;
  effort: string | null;
  /** CLI that runs this candidate: claude, codex, or omp. */
  runner: string;
  ready: boolean;
  reason: string | null;
}

/** webui/roles.py resolution of one review agent from the merged omp config. */
export interface RoleResolution {
  agent_name: string;
  /**
   * True/false = the omp config was read and `task.agentModelOverrides` has / lacks the agent.
   * Null = the config could not be read (see `error`); never treated as unconfigured.
   */
  configured: boolean | null;
  source: string;
  /** Model role without the `@` (e.g. `paper-analysis`); null for literal selectors or when unconfigured. */
  role: string | null;
  candidates: RoleModelCandidate[];
  /** Index of the first candidate whose runner is ready; null when none is. */
  selected: number | null;
  notes: string[];
  /** Korean reason (with the raw cause) when the config read failed; null otherwise. */
  error: string | null;
}

/** GET /api/status `review_roles`. */
export interface ReviewRoles {
  generation: RoleResolution;
  verification: RoleResolution;
}

export type VerificationStatus = 'passed' | 'issues' | 'error' | 'skipped';

/** Verification summary on a review-queue entry (review jobs and `verify` jobs). */
export interface QueueVerification {
  status: VerificationStatus;
  blocking_issues: number;
  mismatches: number;
  /** Repo-relative report path (04-Projects/review-queue/verifications/{slug}.json); null when skipped. */
  report_path: string | null;
  selector: string | null;
  runner: string | null;
  /** Why `issues` has no counts; the server sets `검증된 주장이 없음` when the verifier checked no claim. */
  note?: string | null;
}

/** One generation candidate run of a review job, in order (informational). */
export interface GenerationAttempt {
  selector: string | null;
  runner: string | null;
  exit_code: number | null;
  error_kind: JobErrorKind | null;
  assistant_output: boolean;
  staged_changes: boolean;
  /** True when the job moved on to the next candidate after this attempt. */
  advanced: boolean;
}

/** Generation model of a review-queue entry; `selector` is null when the connected agent's default model ran. */
export interface QueueGeneration {
  selector: string | null;
  runner: string | null;
  attempts?: GenerationAttempt[];
}

/** One entry of the paper-review queue (04-Projects/review-queue/queue.json). */
export interface ReviewQueueJob {
  job_id: string;
  slug: string;
  /** `verify` for a verification-only run; absent for a full review. */
  kind?: string;
  record?: string;
  status: string;
  agent?: string | null;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  updated_at?: string;
  message?: string;
  changed_files?: string[];
  graphify_sync?: string;
  generation?: QueueGeneration | null;
  verification?: QueueVerification | null;
}

export type ClaimVerdict = 'supported' | 'mismatch' | 'unsupported' | 'unverifiable';

/** Output schema of `.omp/agents/paper-verifier.md`. */
export interface VerifierResult {
  status: string;
  review_path: string;
  checked_claims: { claim: string; locator: string; verdict: ClaimVerdict; note: string }[];
  blocking_issues: string[];
  summary: string;
}

/** Stored verification report: `result` on success, `error` when the verifier failed. */
export interface VerificationReport {
  schema_version: string;
  slug: string;
  review_path: string;
  review_sha256: string;
  pdf_sha256: string;
  verified_at: string;
  verifier: { agent_name: string; role: string | null; selector: string | null; runner: string | null };
  result?: VerifierResult;
  error?: string;
  /** Added by the server when reading the report; `stale` = the review or PDF changed since verification. */
  summary: Omit<QueueVerification, 'status'> & { status: Exclude<VerificationStatus, 'skipped'>; stale: boolean };
}

/** GET /api/reviews/{slug} */
export interface ReviewDetail {
  jobs: ReviewQueueJob[];
  /** Present only when a verification report exists. */
  verification?: VerificationReport;
}

export interface ReviewQueue {
  schema_version?: string;
  jobs: ReviewQueueJob[];
}

/** GET /api/status (keys preserved from the former review bridge). */
export interface StatusPayload {
  ok: boolean;
  workspace_id: string;
  agent: string | null;
  ready: boolean;
  reason?: string;
  candidates: AgentCandidate[];
  installed?: boolean;
  authenticated?: boolean;
  compatible?: boolean;
  login_command?: string;
  pdf_reader_ready?: boolean;
  runner: string | null;
  pdf_reader: string;
  max_parallel: number;
  queue: ReviewQueue;
  /** Review agents resolved from the omp config; null when the server omits them (normalized in fetchStatus). */
  review_roles: ReviewRoles | null;
  /** `paper-reader` resolution (논문 리더 질문 답변); null when the server omits it (normalized in fetchStatus). */
  reader_role: RoleResolution | null;
}

export type JobStatus = 'queued' | 'running' | 'completed' | 'failed' | 'cancelled';

/** Job record from the in-memory JobBroker. Timestamps are ISO-8601 UTC seconds. */
export interface JobRecord {
  job_id: string;
  kind: string;
  status: JobStatus;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
  agent: string | null;
  /** Role the job ran as: a review role for role pings, `paper-reader` for `paper.ask`; absent for agent pings. */
  role?: ReviewRoleAgent | typeof READER_ROLE_AGENT | null;
  /** Paper slug; only `paper.ask` records have it. */
  slug?: string;
  cost_usd: number | null;
  error: string | null;
  last_seq: number;
}

/** POST /api/jobs body. `agent` and `role` are mutually exclusive; neither = the connected agent. */
export type CreateJobRequest =
  | { kind: 'agent.ping'; agent?: AgentName; role?: never }
  | { kind: 'agent.ping'; role: ReviewRoleAgent; agent?: never };

// Normalized LLM events (webui/llm.py), streamed as SSE `event: <type>` with JSON `data`.

export interface StartEvent {
  type: 'start';
  agent: string;
  model: string | null;
  session_id: string | null;
}

export interface TextDeltaEvent {
  type: 'text_delta';
  text: string;
}

/** One complete assistant text message. */
export interface AssistantMessageEvent {
  type: 'message';
  text: string;
}

export interface ToolUseEvent {
  type: 'tool_use';
  name: string;
  summary: string;
}

export interface RetryEvent {
  type: 'retry';
  attempt: number;
  delay_ms: number | null;
  /** `usage_limit` when a review role advances to its next fallback candidate. */
  reason: string | null;
  /** Selector of the next candidate, when switching models. */
  next: string | null;
}

export interface ResultEvent {
  type: 'result';
  text: string;
  cost_usd: number | null;
  duration_ms: number | null;
  usage: Record<string, unknown> | null;
}

export type JobErrorKind = 'usage_limit' | 'auth' | 'timeout' | 'process' | 'other';

export interface JobErrorEvent {
  type: 'error';
  message: string;
  retryable: boolean;
  /** Heuristic failure class from webui/llm.py; null when the server sent none. */
  kind: JobErrorKind | null;
}

export interface CancelledEvent {
  type: 'cancelled';
}

/**
 * Stream-level notice from the server, not an LLM event: the subscriber's cursor fell behind the
 * broker's bounded buffer, so events `missed_from`..`missed_to` (inclusive seqs) are gone. Non-terminal.
 */
export interface GapEvent {
  type: 'gap';
  missed_from: number;
  missed_to: number;
}

/** Exactly one terminal event ends every job stream. */
export type TerminalEvent = ResultEvent | JobErrorEvent | CancelledEvent;

export type JobEvent =
  | StartEvent
  | TextDeltaEvent
  | AssistantMessageEvent
  | ToolUseEvent
  | RetryEvent
  | GapEvent
  | TerminalEvent;

export type JobEventType = JobEvent['type'];

export const JOB_EVENT_TYPES: readonly JobEventType[] = [
  'start',
  'text_delta',
  'message',
  'tool_use',
  'retry',
  'gap',
  'result',
  'error',
  'cancelled',
];

/** Error body returned by every failing endpoint. */
export interface ApiErrorBody {
  error: string;
  code: string;
}

// ── Paper reader (contract §3 of the reader design; .scripts/docs/webui-api.md "논문 리더") ──

/** Harness agent that answers reader questions (`.omp/agents/paper-reader.md`). */
export const READER_ROLE_AGENT = 'paper-reader';

/** Short verification state on a paper list entry. */
export interface PaperVerificationSummary {
  status: VerificationStatus;
  stale: boolean;
}

/** GET /api/papers entry. */
export interface PaperSummary {
  slug: string;
  title: string;
  /** Catalog title fallback (record title → PDF title → title-cased slug); never empty. */
  display_title: string;
  authors: string[];
  year: number | null;
  venue: string | null;
  category: string | null;
  topics: string[];
  abstract: string | null;
  one_line_summary: string | null;
  /** Original paper page (https only); null when the record has none. */
  source_url: string | null;
  reading_status: string | null;
  structured_review_status: string | null;
  has_pdf: boolean;
  has_review: boolean;
  /** True when the structured review is not complete or its Markdown file is missing. */
  review_needed: boolean;
  verification: PaperVerificationSummary | null;
  threads: { count: number; updated_at: string | null } | null;
}

/** Display labels the server shares with the static catalog (paper_catalog_html.LABELS). */
export interface PaperLabels {
  category: Record<string, string>;
  reading_status: Record<string, string>;
}

/** GET /api/papers. `errors` lists library records that could not be read. */
export interface PapersPayload {
  papers: PaperSummary[];
  errors: { file: string; error: string }[];
  labels: PaperLabels;
  /** Reading statuses counted as "읽기 대기" (paper_catalog_html.QUEUED_STATUSES). */
  queued_statuses: string[];
}

export type ReviewAxis =
  | 'problem_and_prior_work'
  | 'core_idea_and_difference'
  | 'evaluation_and_evidence'
  | 'limitations_and_future_work'
  | 'related_work';

export type ClaimKind = 'paper_fact' | 'analysis' | 'inference' | 'unknown';

export interface ClaimEvidence {
  locator: string;
  source: string;
}

/** Library record fields the reader reads (paper-record.schema.json); other keys pass through. */
export interface PaperRecord {
  slug: string;
  title: string;
  authors?: string[];
  year?: number | null;
  category?: string | null;
  topics?: string[];
  abstract?: string | null;
  one_line_summary?: string | null;
  publication?: { venue?: string | null } | null;
  review?: Partial<Record<ReviewAxis, { summary?: string; claims?: unknown[] }>> | null;
}

export type TargetConfidence = 'quote' | 'anchor' | 'terms' | 'page' | 'unresolved';

/** Locator anchor found by the server; `pattern` is a JS-compatible regex source. */
export interface TargetAnchor {
  kind: string;
  label: string;
  pattern: string;
}

/** One place in the PDF an evidence locator points to. `page` is a PDF page number (1-based) or null. */
export interface EvidenceTarget {
  evidence_index: number;
  page: number | null;
  listed_page: number | null;
  relocated_from: number | null;
  anchor: TargetAnchor | null;
  terms: string[];
  quotes: string[];
  confidence: TargetConfidence;
}

export type EvidenceStatus = 'matched' | 'page_only' | 'unresolved';

/** One review claim (axis order × claim index) with its highlight targets. */
export interface EvidenceItem {
  claim_id: string;
  axis: string;
  index: number;
  statement: string;
  kind: ClaimKind | string;
  evidence: ClaimEvidence[];
  targets: EvidenceTarget[];
  status: EvidenceStatus;
}

/** GET /api/papers/{slug} */
export interface PaperBundle {
  paper: PaperRecord;
  pdf: {
    url: string;
    available: boolean;
    pages: number | null;
    bytes: number | null;
    sha256: string | null;
    text_available: boolean;
  };
  review: { path: string | null; available: boolean; markdown: string | null; sha256: string | null };
  verification: VerificationReport | null;
  evidence: {
    pages: number | null;
    items: EvidenceItem[];
    summary: { matched: number; page_only: number; unresolved: number };
  };
}

/** Fractions (0–1) of the displayed page box, origin top-left: [x0, y0, x1, y1] with x0 < x1, y0 < y1. */
export type PageRect = [number, number, number, number];

export type ReaderAnchor =
  | { kind: 'text'; page: number; text: string; rects: PageRect[] }
  | { kind: 'region'; page: number; bbox: PageRect }
  | { kind: 'page'; page: number }
  | { kind: 'claim'; page: number | null; claim_id: string };

export type TurnStatus = JobStatus | 'interrupted';

export interface ThreadTurn {
  turn_id: string;
  created_at: string;
  question: string;
  anchor: ReaderAnchor | null;
  job_id: string;
  status: TurnStatus;
  /** Final answer; on failure or cancel the streamed text with `partial: true`. */
  answer: string | null;
  partial: boolean;
  error: { message: string; kind: string | null } | null;
  agent: string | null;
  model: string | null;
  selector: string | null;
  role_configured: boolean | null;
  cost_usd: number | null;
  duration_ms: number | null;
  finished_at: string | null;
  pdf_sha256: string | null;
  review_sha256: string | null;
}

export interface ReaderThread {
  thread_id: string;
  created_at: string;
  updated_at: string;
  /** First question, ≤60 chars. */
  title: string;
  anchor: ReaderAnchor | null;
  turns: ThreadTurn[];
}

/** POST /api/papers/{slug}/ask body. `thread_id` null starts a new thread. */
export interface AskRequest {
  thread_id: string | null;
  question: string;
  anchor: ReaderAnchor | null;
}

export interface AskResponse {
  job: JobRecord;
  thread: ReaderThread;
}

/** GET /api/reader/status */
export interface ReaderStatus {
  ready: boolean;
  /** Region questions also need pdftoppm/pdfinfo (and a runner that accepts images). */
  region_ready: boolean;
  reason: string | null;
  agent: string | null;
  selector: string | null;
  /** Null = the omp config could not be read. */
  configured: boolean | null;
  resolution: RoleResolution | null;
  pdf_tools: { pdftotext: boolean; pdftoppm: boolean; pdfinfo: boolean };
}

// ── Harness (GET /api/harness, POST /api/harness/checks; .scripts/docs/webui-api.md "하네스") ──

/** Step kinds of .scripts/docs/research-workflow-map.json; a step with `skill` is a skill step. */
export type WorkflowStepKind = 'procedure' | 'gate' | 'parallel' | 'tool' | 'playbook';

export interface WorkflowStep {
  skill?: string;
  kind?: WorkflowStepKind | string;
  label: string;
  input: string;
  output: string;
  condition: string;
  /** Repo-relative evidence file. */
  source?: string;
  optional?: boolean;
  /** Independent roles of a `parallel` step. */
  members?: string[];
}

export interface WorkflowPath {
  id: string;
  title: string;
  description: string;
  /** `choices`: independent tools, not a sequence. */
  layout?: string;
  steps: WorkflowStep[];
}

/** A step that uses the skill, with its path and 1-based position. */
export interface SkillUse extends WorkflowStep {
  path_id: string;
  path_title: string;
  order: number;
}

export interface HarnessSkill {
  name: string;
  title: string;
  description: string;
  /** Repo-relative SKILL.md path. */
  source: string;
  /**
   * Full SKILL.md text, front matter included; null when the static-file policy refuses the path
   * (an `errors` entry with section "guide" explains why).
   */
  instructions: string | null;
  uses: SkillUse[];
}

export interface RoutingRow {
  stage: string;
  next: string;
  reason: string;
}

export interface SkillLink {
  name: string;
  source: string;
  source_exists: boolean;
  claude: 'linked' | 'missing';
  codex: 'linked' | 'missing';
  omp: 'direct' | 'missing';
}

export interface OmpAgent {
  name: string;
  path: string;
  /** Front matter `description`; null when absent. */
  description: string | null;
}

export interface HarnessPersona {
  name: string;
  path: string;
}

export interface HarnessValidator {
  name: string;
  path: string;
  exists: boolean;
}

export interface GraphifySync {
  path: string;
  exists: boolean;
  total: number;
  by_status: Record<string, number>;
  pending: number;
  /** Set when the sync-state file could not be read. */
  error: string | null;
}

export type HarnessCheckName = 'verify' | 'tests';

export const HARNESS_CHECK_KINDS: Record<HarnessCheckName, string> = {
  verify: 'harness.verify',
  tests: 'harness.tests',
};

export interface HarnessCheck {
  check: HarnessCheckName;
  label: string;
  command: string;
}

export interface HarnessLinks {
  router: string;
  harness_graph: string;
  workflow_map: string;
  graphify_sync: string;
  installer_doc: string;
  installer: string;
}

/** GET /api/harness. A failing section is empty and listed in `errors`. */
export interface HarnessPayload {
  guide: { paths: WorkflowPath[]; skills: HarnessSkill[] };
  routing: RoutingRow[];
  skill_links: SkillLink[];
  omp_agents: OmpAgent[];
  personas: HarnessPersona[];
  validators: HarnessValidator[];
  tests_path: string;
  graphify: GraphifySync;
  checks: HarnessCheck[];
  links: HarnessLinks;
  /** Repo-relative path → static URL, or null when the server does not serve that file. */
  hrefs: Record<string, string | null>;
  errors: { section: string; error: string }[];
}

// ── Thought experiments (GET /api/ideas) ──

/**
 * One idea note joined with its critique registry row, run folder and research TODO entries
 * (`thought_experiments_html.scan`, the same records as the static page). Unrecorded text
 * fields read `미기록`; missing paths are empty strings.
 */
export interface Idea {
  /** Note file stem. */
  id: string;
  title: string;
  hypothesis: string;
  falsification: string;
  topics: string;
  /** ISO date (YYYY-MM-DD): the later of the note's mtime and the registry row. */
  updated: string;
  /** Literature-search status from analysis.json. */
  literature: string;
  /** `method: …, repro: …, novelty: …` (role critiques). */
  review: string;
  /** User decision (analysis.json, else the registry). */
  decision: string;
  /** `기록 있음` when results.md exists. */
  experiment: string;
  note: string;
  brief: string;
  results: string;
  todo: string;
  /** CRITICAL_VALIDATION_REGISTRY.md row (slug, grill, method, repro, novelty, overall, decision, evidence, updated); empty when unlisted. */
  registry: Record<string, string>;
  /** Registry overall verdict (심사 상태). */
  validation: string;
  noteDecision: string;
  noteStatus: string;
  /** The note's 사용자 결정 differs from the registry decision. */
  decisionConflict: boolean;
  /** The note's 상태 does not contain the registry verdict. */
  statusConflict: boolean;
  manifest: string;
  analysis: string;
  critiques: string[];
  evidence: string[];
  /** Paper IDs included by the literature search. */
  papers: string[];
  /** Library records (01-Papers/library/<slug>.json) of the included papers that exist. */
  paperPaths: string[];
  artifacts: string[];
  /** Comma-joined statuses of the linked research TODO tasks, or `미기록`. */
  todoStatus: string;
  todoTasks: string[];
  todoResults: string[];
}

/** GET /api/ideas. Data faults empty or degrade a section and are listed in `errors` (never a 500). */
export interface IdeasPayload {
  ideas: Idea[];
  /** Repo-relative path → static URL, or null when the server does not serve that file. */
  hrefs: Record<string, string | null>;
  errors: { section: string; error: string }[];
}
