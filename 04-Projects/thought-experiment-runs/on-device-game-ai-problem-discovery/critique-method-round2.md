# Method critic — Round 2

## A: 조건부 유지

`지연 시 품질 손실`을 사후 성공·실패로 만들면 미래 정보 누수다. 공유 LLM 서버가 실제 병목인 경우로 한정하고, stale action을 단순 오래된 응답이 아니라 versioned state의 사전 정의된 전제조건이 깨진 행동으로 정의해야 한다.

필수 대조군은 FIFO, round-robin, aging priority, EDF/service-time-aware scheduling, LLM 없는 fallback이다. 동일 fallback·모델·token budget·NPC quota를 강제해야 한다.

## B: 보류

hard shield가 막는 constraint violation과 LLM이 줄이려는 critical task loss가 분리되지 않았다. 이 둘이 명시될 때까지 독립 연구 문제로 채택하지 않는다.
