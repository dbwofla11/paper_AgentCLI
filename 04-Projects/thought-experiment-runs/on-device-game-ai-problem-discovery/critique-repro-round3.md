# Repro critic — Round 3

## 판정: 보류

고정 event replay와 closed-loop 품질 평가는 분리해야 한다. replay는 동일 요청열 아래 scheduler microbenchmark, closed-loop는 동일 초기조건·상대 정책·seed 분포의 반복 평가로 쓴다.

NPC group·quality function·floor·deadline·starvation을 실험 전 고정하고, fallback도 같은 평가로 채점해야 한다. request prediction은 요청 시점까지의 관측만 쓰고, 비용 회계에는 취소 token·fallback 비용도 포함해야 한다.
