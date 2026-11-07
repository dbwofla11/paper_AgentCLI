import {
  READER_ROLE_AGENT,
  SEARCHER_ROLE_AGENT,
  type ReviewRoleAgent,
  type ReviewRoles,
  type RoleModelCandidate,
  type RoleResolution,
} from './api/types';

/** One harness agent card on the status screen. */
export interface RoleCardSlot {
  key: keyof ReviewRoles | 'reader' | 'searcher';
  agent: string;
  title: string;
  /** What the job does when the agent has no omp override. */
  unconfigured: string;
  /** Unconfigured detail; null = the stage is skipped, otherwise it runs on the connected agent's default model. */
  connectedUse: { subject: string; predicate: string } | null;
  /** What the job does with the selected candidate. */
  readyText: string;
  /** Shown while the configured role has no ready candidate. */
  blockedText: string;
}

/** The two harness review stages, in pipeline order. */
export interface ReviewRoleSlot extends RoleCardSlot {
  key: keyof ReviewRoles;
  agent: ReviewRoleAgent;
  /** Ping-form target label. */
  targetLabel: string;
}

export const REVIEW_ROLE_SLOTS: readonly ReviewRoleSlot[] = [
  {
    key: 'generation',
    agent: 'paper-analyst',
    title: '생성',
    targetLabel: '생성 역할 (paper-analyst)',
    unconfigured: '미설정 — 연결된 에이전트 사용',
    connectedUse: { subject: '리뷰는', predicate: '의 기본 모델로 작성합니다.' },
    readyText: '이 모델로 리뷰를 작성합니다.',
    blockedText: '이 역할이 준비될 때까지 논문 리뷰를 시작할 수 없습니다. 다른 모델로 대신 실행하지 않습니다.',
  },
  {
    key: 'verification',
    agent: 'paper-verifier',
    title: '검증',
    targetLabel: '검증 역할 (paper-verifier)',
    unconfigured: '미설정 — 검증 비활성',
    connectedUse: null,
    readyText: '리뷰를 발행하기 전에 이 모델로 원문과 대조합니다.',
    blockedText: '이 역할이 준비될 때까지 논문 리뷰를 시작할 수 없습니다. 다른 모델로 대신 실행하지 않습니다.',
  },
];

/** `paper-reader` answers reader questions; it is not a ping target (`POST /api/jobs` accepts review roles only). */
export const READER_ROLE_SLOT: RoleCardSlot = {
  key: 'reader',
  agent: READER_ROLE_AGENT,
  title: '질문 답변',
  unconfigured: '미설정 — 연결된 에이전트의 기본 모델 사용',
  connectedUse: { subject: '논문 리더 질문은', predicate: '의 기본 모델로 답합니다.' },
  readyText: '논문 리더 질문에 이 모델로 답합니다.',
  blockedText: '이 역할이 준비될 때까지 논문 리더에서 질문할 수 없습니다. 다른 모델로 대신 답하지 않습니다.',
};

/** `paper-searcher` runs 논문 탐색 searches and registrations (`discovery.search`, `discovery.register`); not a ping target. */
export const SEARCHER_ROLE_SLOT: RoleCardSlot = {
  key: 'searcher',
  agent: SEARCHER_ROLE_AGENT,
  title: '논문 탐색',
  unconfigured: '미설정 — 연결된 에이전트의 기본 모델 사용',
  connectedUse: { subject: '논문 탐색 검색과 등록은', predicate: '의 기본 모델로 실행합니다.' },
  readyText: '논문 탐색 검색과 등록을 이 모델로 실행합니다.',
  blockedText: '이 역할이 준비될 때까지 논문 탐색 검색과 등록을 시작할 수 없습니다. 다른 모델로 대신 실행하지 않습니다.',
};

/** `config_error` = the omp config could not be read, so whether the role is configured is unknown. */
export type RoleState = 'ready' | 'unavailable' | 'unconfigured' | 'config_error';

/** The candidate review jobs run with: the first one whose runner is ready. */
export function selectedCandidate(resolution: RoleResolution): RoleModelCandidate | null {
  return resolution.selected === null ? null : (resolution.candidates[resolution.selected] ?? null);
}

export function roleState(resolution: RoleResolution): RoleState {
  if (resolution.configured === null) return 'config_error';
  if (!resolution.configured) return 'unconfigured';
  return selectedCandidate(resolution) ? 'ready' : 'unavailable';
}

/** Why the role cannot run (config read failed, or no ready candidate); null when it can or is unconfigured. */
export function blockedReason(resolution: RoleResolution): string | null {
  switch (roleState(resolution)) {
    case 'config_error':
      return `설정 읽기 실패: ${resolution.error ?? 'omp 설정을 읽지 못했습니다.'}`;
    case 'unavailable':
      if (resolution.candidates.length === 0) return '역할에 연결된 모델이 없습니다.';
      return `준비된 실행기가 없습니다. ${resolution.candidates
        .map((candidate) => `${candidate.selector}: ${candidate.reason || `${candidate.runner} 준비 안 됨`}`)
        .join(' / ')}`;
    default:
      return null;
  }
}
