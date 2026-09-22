# 비판 검증: on-device-game-ai-problem-discovery

- 상태: 실험 가능 (사용자 결정 대기)
- 기획 정본: `brief-round4.md`
- 심사 완료일: 2026-09-18
- 사용자 결정: 미결정

## 심사 범위와 증거

- 검토한 입력: 보관된 Nair & Karim의 local LLM+PPO NPC, MASMP, PCSP, QuIP#, QTIP, QLoRA, GSQ, Gallotta survey 및 후보 5개를 4차 독립 심사로 축소한 기록.
- 검토하지 못한 근거: 학계 전체 선행연구, 실제 RTX 5060 configuration, 특정 게임 엔진의 workload. [확인 필요]

## Method critic

- 치명적 결함: 없음
- 근거: 사전 등록 quality/deadline, online-only predictor, trace-replay/closed-loop 분리, strong baseline과 반증 규칙.
- 반례 또는 대체 설명: EDF·weighted-EDF·batching·LLM-free fallback이 같은 결과를 내면 기각한다.
- 필수 최소 대조군/확인: 실제 LLM server bottleneck 확인, FIFO부터 oracle까지의 기준선, 실행 전 $Q_i^{min}$·$\delta$·$\epsilon$ 수치 고정.
- 권고: 유지

## Repro critic

- 치명적 결함: 없음
- 근거: 동일 trace 비교와 closed-loop paired-seed 품질 평가가 분리됐고, fallback과 취소 token까지 포함한 계측이 명시됐다.
- 반례 또는 대체 설명: 낮은 우선순위 NPC 품질을 포기한 평균 개선은 동일 quality floor 평가에서 실패한다.
- 필수 최소 대조군/확인: predictor split/freeze, request timing·KV·GPU/CPU memory·frame p95/p99 기록, RTX 5060 단일 configuration 고정.
- 권고: 유지

## Novelty critic

- 치명적 결함: 없음 (보관 논문 기준)
- 근거: 단일 global LLM tag(Nair), single-agent state/memory(MASMP), runtime LLM 없는 shared policy(PCSP)와 직접 중복하지 않는다.
- 반례 또는 대체 설명: 일반 queue policy, global plan, batching, static priority, shared fallback이 만족하면 기각한다.
- 필수 최소 대조군/확인: EDF/weighted-EDF 및 동일 admission/context 기준선, stale prediction이 우선순위를 바꾸는 trace strata.
- 권고: 유지

## 종합

- 미해결 치명적 결함: 없음
- 다시 답할 grill-me 질문: 실제 구현 전에 게임 장르·NPC role, 각 event의 deadline/$Q_i^{min}$/starvation 한도, RTX 5060 VRAM·model/engine/quant configuration을 확정한다.
- 다음 가능한 행동: 위 값을 사전 등록 표로 채운 뒤, server-bottleneck 측정 → trace replay → closed-loop evaluation 순으로 진행한다.
- 최종 권고: 실험 가능

## 사용자 결정 기록

- 결정: 미결정
- 근거: 심사 통과 후에도 실험 실행 승인과 구체 configuration 결정은 사용자에게 있다.
- 결정일: 미정
