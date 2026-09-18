# 04-Projects — 실행 단위

아이디어가 아니라 **실제로 수행할 실험·구현·스터디**를 관리한다. 프로젝트 하나는 목표, 입력, 산출물, 다음 행동, 관련 근거를 가져야 한다.

## WAVEVERSE forward simulation 검증

아직 프로젝트 노트는 만들지 않았다. 시작 시 `waveverse-forward-simulation.md`를 만들고 다음을 기록한다.

- 목표: 환경·대역폭·Tx/Rx 배치 변화가 CSI와 reconstruction 가능성에 미치는 영향을 측정
- 입력: 방 geometry, material/multipath 설정, Tx/Rx geometry, bandwidth, 물체 배치
- 출력: synthetic CSI, reconstruction/localization 지표, 조건별 오차 표
- 연결: `05-ideas/thought-experiments/2026-09-07-room-aware-distributed-rf-configuration.md`
- 종료 조건: 어떤 요인이 오차를 지배하는지 구분 가능한 실험 설계 확보

연구 가설 자체는 [05-ideas](../05-ideas/README.md)에, 재사용 가능한 이해는 [02-Concepts](../02-Concepts/README.md)에 둔다.

## 사고실험 실행 기록

`thought-experiment-runner`가 만든 작은 실험은 `thought-experiment-runs/{slug}/`에 둔다. 첫 사용자는 [`thought-experiment-runs/PROGRESS_BACKEND.md`](thought-experiment-runs/PROGRESS_BACKEND.md)에서 저장소 MD 또는 Notion MCP를 선택한다. 저장소 MD를 고르면 각 실험의 `progress.md`가 상태·acceptance criteria·blocker·결정의 정본이며, Notion을 고르면 그 페이지가 정본이고 로컬은 증거만 보관한다. 각 실행은 `manifest.md`와 `results.md`를 가져야 하며, 가설 노트의 반증 조건과 연결한다. 논문 코드를 Paper2Agent MCP로 만들 후보·산출물은 `paper-agents/{paper-slug}/`에 분리한다.
