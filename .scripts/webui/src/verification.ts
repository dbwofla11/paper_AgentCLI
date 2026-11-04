import type { StatusContextValue } from './status';
import { blockedReason, roleState } from './roles';

/** Korean explanation per error code of POST /api/reviews/{slug}/verify (.scripts/docs/webui-api.md). */
export const VERIFY_ERRORS: Record<string, string> = {
  bad_request: '논문 기록을 찾지 못했습니다. 01-Papers/library에 이 논문의 JSON 기록이 있는지 확인하세요.',
  review_missing: '이 논문의 리뷰 문서가 아직 없습니다. 먼저 논문 리뷰를 실행하세요.',
  pdf_missing: '논문 PDF를 찾을 수 없습니다. 원문과 대조하려면 01-Papers/pdfs 안에 PDF가 있어야 합니다.',
  review_active: '다른 논문 리뷰나 검증이 이미 진행 중입니다. 끝난 뒤 다시 실행하세요.',
  verifier_unconfigured:
    '검증 역할(paper-verifier)이 설정되지 않았습니다. .omp/config.yml의 task.agentModelOverrides를 확인하세요.',
  verifier_unavailable: '검증 역할의 실행기가 준비되지 않았습니다. 아래 사유를 확인하세요.',
  role_config_error: 'omp 설정을 읽지 못해 검증 역할을 판단할 수 없습니다. 상태 화면의 논문 리뷰 구성을 확인하세요.',
};

/** Errors meaning the verifier role changed since the last status check: reload GET /api/status once. */
export const ROLE_ERROR_CODES: Record<string, true> = {
  verifier_unconfigured: true,
  verifier_unavailable: true,
  role_config_error: true,
};

/**
 * Why a verification run cannot start, from the shared GET /api/status result (fetched once, never
 * polled); null when the verifier role has a ready candidate.
 */
export function verifierBlockedReason({ data, loading }: Pick<StatusContextValue, 'data' | 'loading'>): string | null {
  if (!data) return loading ? '검증 역할 상태를 확인하는 중…' : '검증 역할 상태를 확인하지 못했습니다.';
  const resolution = data.review_roles?.verification ?? null;
  if (!resolution) return '서버가 논문 리뷰 구성을 보내지 않았습니다.';
  switch (roleState(resolution)) {
    case 'ready':
      return null;
    case 'unconfigured':
      return '미설정 — 검증 비활성. .omp/config.yml의 task.agentModelOverrides에 paper-verifier를 추가하면 실행할 수 있습니다.';
    default:
      return blockedReason(resolution) ?? '검증 역할을 사용할 수 없습니다.';
  }
}
