# Repro critic — Round 2

## A: 조건부 유지

온라인 scheduler의 입력은 요청 생성 시점까지의 관측·이력만 사용해야 한다. 모든 요청은 동일 deterministic fallback으로 행동 결과를 내며, 늦은 결과는 상태 버전·전제조건을 재검증해 폐기한다. 같은 admission ratio의 무작위 정책과 고정 context/retrieval policy를 추가해야 한다.

요청별 도착/시작/prefill/decode/실행·폐기 시각, 토큰, KV cache, fallback, deadline/stale/starvation, NPC별 품질, frame p95/p99, GPU·시스템 RAM을 기록한다. RTX 5060 VRAM 미확정 상태에서는 결과를 특정 로컬 구성으로만 귀속한다.

## B: 조건부 유지이나 보류 권고

위험 사건 라벨·보정 검증 분할·shield 보장 범위가 아직 정해지지 않았다.
