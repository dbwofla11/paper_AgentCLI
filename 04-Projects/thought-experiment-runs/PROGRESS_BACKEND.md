# 사고실험 진척 관리 설정

- backend: notion
- Notion 페이지 또는 데이터베이스: 첫 연결 시 설정

사고실험을 처음 실행하기 전에 다음 중 하나를 선택한다.

1. `repository` — 각 `04-Projects/thought-experiment-runs/{slug}/progress.md`가 진척 정본이다.
2. `notion` — 연결된 Notion 페이지 또는 데이터베이스가 진척 정본이다. 이 파일에는 Notion 링크·식별자만 기록한다.

이 개인 브랜치는 Notion을 진척 정본으로 선택한다. 대상 페이지 또는 데이터베이스가 설정되기 전에는 runner가 Notion 연결·대상 선택을 먼저 요청하며, 진척 판정은 하지 않는다.
