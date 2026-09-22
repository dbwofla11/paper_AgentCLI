# Repro critic — Round 1

## 공통 치명 조건

RTX 5060의 실제 VRAM, 모델·양자화 형식·추론 엔진·동시 요청 수·컨텍스트/KV cache 상한이 아직 미정이다. 따라서 “동일 VRAM”과 “실시간”은 현재 수치 주장으로 쓰지 않는다. 시스템 RAM 16GB에서는 GPU 메모리 부족 시 CPU RAM·페이지 폴트·디스크 I/O가 생기는지도 측정해야 한다.

## 후보별 판정

- 후보 1: 축소. 고정 5초, 같은 호출 수의 무작위 트리거, FSM/RL, 의미 이벤트 트리거를 같은 event replay에서 비교해야 한다.
- 후보 2: 보류. `VRAM scheduler`가 아니라 request token·KV·queue·deadline·state staleness를 측정하는 deadline-aware scheduler여야 한다. FIFO·라운드로빈·노화된 정적 우선순위·무작위 배정과 비교가 필수다.
- 후보 3: 보류. persona consistency의 객관 정답과 기억 누수 방지가 없다.
- 후보 4: 축소. pure policy, hard safety shield, 같은 호출률의 random LLM, risk escalation을 분리해야 한다.
- 후보 5: 보류. 동시 상주/로드-언로드/warm cache를 분리하지 않으면 결론이 무효다.

## 필수 공통 측정

행동 반영까지의 end-to-end latency, frame-time p95/p99, deadline 초과율, stale action 비율, GPU 최대 VRAM 및 KV cache, 시스템 RAM·페이지 폴트·I/O, 토큰/queue/prefill/decode 시간을 같은 게임 seed와 replay에서 기록한다.
