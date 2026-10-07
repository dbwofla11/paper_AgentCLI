# 루프·운영 설정

## 역할

시각 예약, 날짜별 선정 기준, 에이전트 연결, 작업 대기열, 지식 동기화를 나누어 운영한다.

## 일일 후보 루프 — 현재 런타임 조회

- Automation: Daily Paper Candidates
- ID: 03168daf-9499-4ca3-a6ba-2e93e65ed543
- 활성화: true · 매일 09:00 · Asia/Seoul
- Provider: codex · 기존 저장소에서 매번 새 세션
- 후보: CV 1 + 멀티모달 1 + 관심 분야 1
- 최소 두 학술 소스, 공식 게재·원문 확인
- 결과는 자동화 회차의 채팅이며 채택 전에는 PDF·Keep·JSON을 저장하지 않음

2026-10-07 Orca automations show로 예약 설정을 읽어 확인했다. 예약이 켜져 있다는 사실만으로 모든 회차의 결과 완성을 보장하지 않는다.

## 사용자 확인 지점

후보 채택, 개념 승격, 사고실험 기획 승인, 독립 심사 후 진행 결정은 사용자에게 있다. 문헌 TODO dispatch는 명시적 실행 요청이 필요하다.

## 기존 기록에서 확인된 차이

Jev 사례는 레지스트리와 brief의 승인 상태가 다르고 현재 계약의 analysis.json이 없다. Notion backend 설정에는 링크가 있으나 레지스트리에는 미연결 안내가 남아 있다. 이 페이지는 차이를 기록하며 원장 상태를 임의로 변경하지 않는다.

## 근거 문서

- `docs/daily-orca-automation.md`
- `docs/onboarding.md`
- `docs/agent-research-todo.md`
- `04-Projects/thought-experiment-runs/CRITICAL_VALIDATION_REGISTRY.md`

기준일: 2026-10-07. 이 페이지는 저장소 설정을 설명하는 안내이며 실행 상태의 정본을 대체하지 않습니다.
