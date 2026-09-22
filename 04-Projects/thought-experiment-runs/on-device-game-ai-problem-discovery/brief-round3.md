# Final Candidate: Quality-SLO-aware Deadline Scheduling for Shared On-device NPC LLMs

- 상태: 심사 대기
- 검증 범위: 보관 논문 대비. 학계 전체 신규성은 `[확인 필요]`.
- 문제 성립 조건: 하나의 로컬 LLM 서버가 동시 NPC 의사결정 요청의 실제 병목인 게임 루프에 한정한다. 경로 탐색·물리·렌더링이 병목인 조건에는 적용을 주장하지 않는다.

## 문제 상황

다수 NPC가 하나의 로컬 LLM 서버에 동시에 고수준 의사결정을 요청하면, FIFO·균일 순서는 요청의 게임 deadline과 상태 노후화(staleness)를 구분하지 못한다. 늦은 응답은 단순히 느린 것이 아니라, 참조했던 게임 상태가 바뀌어 행동 효용이 사라질 수 있다. Nair & Karim의 전역 5초 전략 tag, MASMP의 단일 agent state/memory, PCSP의 LLM 없는 shared policy는 이 독립 요청 경쟁을 직접 다루지 않는다.

## 연구 질문

**공유 로컬 LLM 서버에서, 요청 생성 시점에 이용 가능한 관측·이력만으로 deadline, 서비스 비용, 지연 시 품질 손실을 추정하여 호출/폴백, context·retrieval budget, 실행 순서를 공동 결정하면, 같은 모델·동일 총 token/call budget·동일 NPC별 최소 서비스 quota 아래 FIFO, round-robin, aging priority, EDF/weighted-EDF, 고정 admission보다 NPC별 deadline miss·stale action·품질 불균형을 동시에 낮출 수 있는가?**

## 명시적 신규성 경계

기여는 일반 GPU/VRAM 할당이나 평균 처리량 개선이 아니다. 다음을 함께 제약하는 게임 런타임 정책이다.

1. 늦은 생성이 야기하는 **행동 효용의 상태 의존적 하락**
2. 특정 NPC를 희생시키지 않는 **NPC별 quality floor와 starvation 방지**
3. 호출 여부, context/retrieval budget, queue 순서의 **공동 결정**

global plan 1회 호출, batching, 캐시된 행동, 정적 우선순위, 경량 shared policy가 같은 결과를 내면 차별성 주장은 기각한다.

## 인과·누수 제약

- 비용·품질 손실 추정기는 요청 생성 시점까지의 관측, 이력, 현재 정책 출력을 입력으로만 쓴다. 이후 게임 전개, 실제 완료 시간, 사후 성공/실패, oracle 미래 상태를 입력으로 쓰지 않는다.
- 모든 정책은 동일 모델·프롬프트·context 상한·token/call budget·deterministic fallback·NPC별 최소 quota를 쓴다.
- fallback으로 넘긴 요청도 사전 정의한 과업·persona 평가에서 채점한다. 평균 개선을 위해 낮은 우선순위 NPC의 품질을 버리면 실패다.
- stale action은 `versioned state snapshot`에서 생성된 행동이 deadline 이후 도착했고, 실행 시점의 상태 버전에서 사전 등록한 action precondition이 깨져 task utility가 기준 행동보다 감소한 경우로 정의한다. 늦은 응답은 실행하지 않고 폐기 또는 재계획하며 횟수를 기록한다.

## 성공·반증

### 성공

동일 event replay에서 모든 NPC group이 사전 등록한 quality floor를 충족하면서, 강한 기준선 대비 deadline miss율, stale action율, starvation, 최악 group의 품질 손실 중 하나 이상을 낮추고 나머지를 악화시키지 않는다.

### 반증

EDF/weighted-EDF 또는 단순 admission·batching·LLM 없는 shared fallback이 같은 NPC별 품질 하한과 deadline/staleness 분포를 달성하면 기각한다. 온라인 추정이 oracle 상한과 큰 차이를 보이거나, 우선순위가 특정 NPC의 품질을 희생하면 기각한다.

## 최소 검증 설계

- 정책: FIFO, round-robin, aging priority, EDF, weighted-EDF, 동일 admission 비율의 random, 고정 admission/context, 제안 정책, LLM 없는 shared fallback. oracle quality-loss policy는 상한으로만 둔다.
- 기록: 요청 도착·시작·prefill 완료·decode 완료·실행/폐기, input/output token, KV cache, queue, deadline, stale, fallback, NPC별 quality, frame p95/p99, GPU VRAM, 시스템 RAM, page fault/I/O.
- 분할: scheduler 예측기 학습·검증·평가 event replay를 시간/seed 기준으로 분리하고, threshold는 검증 분할에서 고정한다.
- 하드웨어: 실제 RTX 5060 VRAM·엔진·양자화 형식은 도입 후 고정한다. 그 전에는 배포 가능성이나 절대 지연시간을 주장하지 않는다.

## 알려진 한계

- 학계 전체 선행연구 대비 신규성은 외부 문헌 확인 전 `[확인 필요]`.
- 게임 장르·NPC 역할·quality floor의 구체적 정의는 구현 전 사용자와 확정해야 한다.
- 이 문서는 문제·가설 검증용이며 실험 실행 승인이 아니다.
