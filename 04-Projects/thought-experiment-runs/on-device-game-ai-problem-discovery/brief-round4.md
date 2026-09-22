# Validated Candidate: Quality-SLO-aware Deadline Scheduling for Shared On-device NPC LLMs

- 상태: 심사 대기
- 주장 범위: **측정으로 공유 local LLM server가 병목임을 확인한 하나의 게임·NPC 역할·RTX 5060 구성**에서만 주장한다. 다른 엔진 병목, 모든 장르, 절대 latency, 학계 전체 신규성은 주장하지 않는다.
- 외부 문헌 기준 신규성: `[확인 필요]`.

## 문제 상황

여러 NPC의 고수준 결정이 하나의 local LLM server에서 경쟁하면, FIFO·균일·고정 주기 호출은 늦은 응답이 게임 상태 변화로 무효해지는 현상과 특정 NPC의 starvation을 구분하지 못한다. Nair & Karim의 전역 5초 strategy tag, MASMP의 단일 agent state/memory, PCSP의 런타임 LLM 없는 shared policy는 이 독립 요청 경쟁을 직접 다루지 않는다.

## 검증할 질문

**요청 도착 시점에 사전 등록된 deadline과, 그 시점까지 이용 가능한 관측·이력으로 추정한 서비스 비용·stale-quality loss를 이용해 호출/폴백, context·retrieval budget, 실행 순서를 공동 결정하면, NPC별 quality floor를 침해하지 않고 FIFO·round-robin·aging priority·EDF/weighted-EDF·고정 admission보다 deadline miss, stale action, starvation을 낮출 수 있는가?**

## 사전 등록 제약

1. 각 요청 $i$의 hard deadline $D_i$, NPC group, starvation 한도, quality floor $Q_i^{min}$은 game event type·NPC role의 사전 등록 표에서 요청 도착과 함께 결정한다. scheduler는 이를 변경·재추정하지 않는다.
2. $Q_i$는 사전 등록한 `과업 성공`, `persona 제약 충족`, `행동 유효성`의 고정 함수다. 임계값·가중치·group 분할은 predictor 학습 전에 고정한다.
3. 비용·stale-quality loss predictor는 요청 생성 시점까지의 game observation, history, current policy output만 쓴다. 이후 전개, 실제 완료 시간, 사후 성공/실패, oracle 미래 상태는 입력으로 금지한다. predictor 학습/검증/시험 event set은 time/seed로 분리하고 시험에서 동결한다.
4. 모든 비교 정책은 동일 모델·prompt·context 상한·token/call budget·deterministic fallback·NPC별 최소 service quota를 쓴다. fallback·폐기 요청도 동일 정답지로 평가한다.
5. stale action은 실행 시점 state $s$에서 (a) 사전 등록한 action precondition $P_a(s)$가 거짓이거나, (b) 실행 시점 관측만 쓰는 deterministic fallback $f(s)$보다 사전 등록한 즉시 효용 $u$에서 $u(s,f(s))-u(s,a) \ge \delta$인 행동이다. 사후 episode outcome·oracle 행동은 stale 판정 입력으로 쓰지 않는다.

## 두 단계 평가

### A. Trace-replay scheduler microbenchmark

동일 versioned snapshot·요청 도착·deadline·입력 trace를 모든 정책에 주고, 행동은 환경을 바꾸지 않는다. queue/prefill/decode/token/KV/deadline/stale만 비교한다. 동일 deadline·비용인 요청에서도 stale-quality prediction이 실제로 우선순위를 달리하는 strata를 사전 포함한다.

### B. Closed-loop game evaluation

각 정책은 자신의 행동으로 후속 상태·요청을 생성한다. 동일 초기 상태·상대 policy·seed 집합을 독립 반복하며, seed별 paired difference와 사전 등록 신뢰구간으로 NPC별 quality, deadline, stale, starvation을 비교한다. 이 단계에서만 게임 과업·persona 품질을 주장한다.

## 필수 기준선과 기각 규칙

- 기준선: FIFO, round-robin, aging priority, EDF, weighted-EDF, 동일 admission 비율 random, 고정 admission/context, batching, LLM 없는 shared fallback. oracle quality-loss policy는 simulator-only 상한이다.
- 기각: 위 기준선 중 하나가 모든 NPC group의 $Q_i^{min}$을 충족하면서 deadline/stale/starvation/quality 분포에서 동등 또는 우월하면 기각한다.
- online estimator는 같은 action space·자원 제약의 simulator-only oracle 대비 사전 등록한 regret 상한 $\epsilon$ 이내여야 하며, 초과하면 기각한다.
- 모든 결과에 request arrival/start/prefill/decode/execute/drop, input/output/cancelled token, KV cache, fallback, GPU VRAM, system RAM, page fault/I/O, frame p95/p99를 남긴다.

## 차별성 경계

기여는 평균 throughput 또는 GPU memory 할당이 아니다. **state-dependent stale action, NPC별 quality floor/starvation, admission·context/retrieval·queue 순서의 공동 결정**이 한 세트다. global plan, batching, cache, static priority, lightweight shared policy, 또는 EDF/weighted-EDF가 이를 만족시키면 이 후보는 실패다.

## 하드웨어 처리

RTX 5060의 실제 VRAM·모델 파일·quant format·engine·warm/cold cache·batching·power state는 장비 도입 후 단일 구성으로 고정해 기록한다. 그 전에는 배포 가능성·절대 latency를 주장하지 않는다.
