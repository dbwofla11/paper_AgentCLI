# 사고실험 진척 관리 설정

- backend: unset
- Notion 페이지 또는 데이터베이스: 미설정

사고실험을 처음 실행하기 전에 다음 중 하나를 선택한다.

1. `repository` — 각 `04-Projects/thought-experiment-runs/{slug}/progress.md`가 진척 정본이다.
2. `notion` — 연결된 Notion 페이지 또는 데이터베이스가 진척 정본이다. 이 파일에는 Notion 링크·식별자만 기록한다.

`unset` 상태에서는 runner가 실행·문헌 탐색·Paper2Agent 준비성 검사를 시작하지 않고, 사용자에게 저장 위치를 먼저 질문한다.
