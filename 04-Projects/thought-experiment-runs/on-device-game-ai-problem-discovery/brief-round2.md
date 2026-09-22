# On-device Game AI Problem Discovery — Round 2

- 상태: 심사 대기
- 목적: 1차 심사에서 남은 두 후보가 `차별성`과 `문제 적합성`을 모두 만족하도록 최소 명세로 재구성한다.
- 범위: 로컬 보관 논문 대비. 학계 전체 신규성은 `[확인 필요]`다.

## 통과 후보 A — Quality-SLO-aware Deadline Scheduler for Shared NPC LLMs

### 문제 상황

여러 NPC가 하나의 로컬 LLM 서버에 동시에 결정을 요청할 때, FIFO·라운드로빈·고정 주기 호출은 생성 대기 중 게임 상태가 바뀌어 행동이 낡아지는 문제와 특정 NPC의 기아를 구분하지 못한다. 단일 global strategy tag(Nair & Karim), 단일 agent memory(MASMP), LLM 없이 shared policy를 쓰는 PCSP는 이 독립 요청 경쟁을 직접 해결하지 않는다.

### 연구 질문

**각 NPC 요청의 deadline, 예상 서비스 비용, 지연 시의 게임 품질 손실을 이용해 admission(호출/보류/폴백), context/retrieval budget, 실행 순서를 공동 결정하면, 동등한 로컬 자원·품질 하한에서 FIFO·균일·정적 우선순위보다 deadline 초과·stale action·NPC별 품질 불균형을 낮출 수 있는가?**

### 명시적 차별점

단순 GPU/VRAM 배분이 아니라, 게임 고유의 `늦게 생성된 행동의 효용 하락`과 `NPC별 persona/과업 품질 하한`을 제약으로 넣는다. batching·정적 priority·global plan·LLM 없는 shared policy가 같은 효과를 내면 기여는 없다.

### 반증

동일 event replay, 동일 모델·context 상한·총 토큰/호출 예산에서 FIFO/라운드로빈/노화된 정적 priority가 같은 deadline·staleness·품질 분포를 달성하면 기각한다. 낮은 우선순위 NPC의 품질을 버려 평균만 개선해도 기각한다.

### 최소 증거

request별 queue/prefill/decode time, input/output tokens, KV cache, action deadline, stale action, starvation, NPC별 persona/과업 품질을 기록한다. RTX 5060 VRAM과 엔진은 실제 도입 후 확정한다.

## 보조 후보 B — Calibrated Escalation with Hard Safety Shield

### 문제 상황

LLM 상위 계획+RL 실행은 적응성을 주지만, LLM의 환각·지연을 행동 안전 보장에 사용하면 위험하다. 반대로 hard rule만 쓰면 규칙으로 판정하기 어려운 서사·상황적 분기에서 적응하지 못한다.

### 연구 질문

**행동 유효성은 deterministic shield가 강제하고, 보정된 risk/uncertainty estimator가 규칙으로 분류 불가능한 고위험 분기만 LLM 재계획으로 승격할 때, 고정 주기 LLM-RL hybrid보다 치명 실패를 낮추면서 deadline을 유지할 수 있는가?**

### 명시적 차별점

Nair의 주기적 전략 tag와 달리, LLM은 안전 판정자가 아니며 calibrated escalation의 제한된 재계획자다. 안전성은 LLM 밖의 deterministic shield가 보장한다.

### 반증

hard shield만으로 같은 치명 실패율과 적응 과업 성공률을 얻거나, risk estimator의 오탐이 호출·deadline 초과를 늘려 이득을 없애면 기각한다.

### 최소 증거

pure policy, hard shield, fixed-period LLM hybrid, random-call-rate hybrid, risk escalation을 비교하고, risk calibration·false negative·치명 사건·end-to-end deadline을 분리해 측정한다.

## 탈락 후보

후보 1은 A의 admission/replanning 구성요소로 흡수한다. 후보 3은 객관적 장기기억 평가가 설계될 때까지, 후보 5는 실제 VRAM·모델 상주 방식이 확정될 때까지 보류한다.
