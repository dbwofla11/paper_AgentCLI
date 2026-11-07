# 루프·운영 설정

## 역할

예약 시각은 Orca Automation에서 관리한다. 날짜별 선정 기준·사용자 확인 단계·에이전트 연결·문헌 조사 대기열·지식 동기화 규칙을 설명한다. 실제 실행 상태와 계정 설정은 로컬 자동화 도구에서 확인한다.

## 일일 후보 루프

Orca Automation이 `$daily-digest-loop` 스킬을 예약 실행한다. 컴퓨터 비전·멀티모달·사용자 관심 분야별 후보를 검증해 채팅으로 보고하고, 같은 내용을 Git에서 제외된 로컬 캐시 `00-Inbox/discovery/daily/YYYY-MM-DD.json`에 기록한다. 캐시는 WebUI 탐색 화면에서 보며 위키·라이브러리·Graphify 대상이 아니다. PDF·Keep·논문 JSON 같은 정본은 사용자가 채택한 뒤에만 저장한다.

## 사용자 확인 지점

후보 채택, 개념 승격, 사고실험 기획 승인, 독립 심사 후 진행 결정은 사용자에게 있다. 문헌 TODO dispatch는 명시적 실행 요청이 필요하다.

## 근거 문서

- `docs/daily-orca-automation.md`
- `docs/onboarding.md`
- `docs/agent-research-todo.md`
- `04-Projects/thought-experiment-runs/CRITICAL_VALIDATION_REGISTRY.md`

기준일: 2026-10-07. 이 페이지는 저장소 설정을 설명하는 안내이며 실행 상태의 정본을 대체하지 않습니다.
