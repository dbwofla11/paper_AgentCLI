# 05-ideas — 연구 아이디어와 사고실험

검증 전 가설, 선행연구 공백, 반증 조건을 기록한다. 구현 계획은 `04-Projects/`로 분리한다.

사고실험은 [`thought-experiments/`](thought-experiments/)에 둔다.

사고실험을 실행·구체화할 때는 `thought-experiment-runner`를 적용한다. 첫 실행에는 진척 정본을 저장소 MD 또는 Notion MCP 중에서 반드시 선택한다. 이 스킬은 선택 뒤에만 작은 결정론적 실험과 새 문헌 방향 탐색을 시작하며, 재현 가능한 실행 기록은 `04-Projects/thought-experiment-runs/{slug}/`에 분리한다. 논문 코드의 Paper2Agent MCP화는 공식 코드·튜토리얼 확인 뒤 실제 생성을 요청한 경우에만 수행한다.

## 진행 중

- [방·작업 조건에 따른 distributed RF sensing configuration](thought-experiments/2026-09-07-room-aware-distributed-rf-configuration.md)
  - 가설: 방의 크기·형태·반사 구조·목표 작업에 따라 적절한 bandwidth와 Tx/Rx geometry가 달라진다.
  - 현재 포지션: 정확도를 무조건 높이는 방법이 아니라, 정확도에 영향을 주는 요인을 분석한다.
- [RF simulation 실행·기록 보조를 위한 Agents API](thought-experiments/2026-09-15-agents-api-rf-simulation-loop.md)

## 아이디어 기록 형식

1. 문제와 가설
2. 물리적으로 가능한 이유 / 깨지는 조건
3. 선행연구가 이미 해결한 범위
4. 최소 반증 실험
5. 상태: 탐색 · 보류 · 프로젝트화 · 폐기
