# Method critic — Round 1

## 판정

- 후보 1: 축소 — 단순 호출 감소가 아니라 전략 무효화 확률을 추정하는 selective replanning이어야 한다.
- 후보 2: 조건부 유지 — “VRAM 공정성”이 아니라, 지연으로 인한 NPC별 품질 손실을 예측하는 deadline-aware scheduling으로 좁혀야 한다.
- 후보 3: 보류 — 메모리 압축이 persona 훼손을 일으킨다는 배포상 근거가 부족하다.
- 후보 4: 조건부 유지 — hard safety는 규칙으로 강제하고, LLM은 규칙으로 판정 불가능한 모호한 분기만 재계획해야 한다.
- 후보 5: 보류 — 다중 모델 상주·교체 비용이 정의되지 않았다.

## 핵심 근거

Nair & Karim은 고정 5초 주기의 로컬 LLM 전략 선택과 shared PPO를 이미 검증했고, 태그 선택이 `Surround`에 83.8% 편향됐다고 보고한다 (§3.9.1, §4.4–4.6). 따라서 “LLM 호출” 자체는 기여가 아니다. Gallotta et al.은 런타임 LLM의 응답성·비용 문제를 지적하며 (§5), Hong의 PCSP는 경량 shared policy의 병목이 항상 추론이 아님을 보인다 (§VII, Table XIV).

## 2차 심사 조건

후보 2는 `우선순위 점수`가 지연된 생성의 실제 품질 손실을 예측하는지 검증하고, FIFO·라운드로빈·정적 우선순위·LLM 없는 shared policy와 비교해야 한다. 후보 4는 LLM이 안전 보장을 하지 않으며 hard constraint가 별도 모듈이라는 조건을 명시해야 한다.
