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

`thought-experiment-runner`가 만든 작은 실험은 `thought-experiment-runs/{slug}/`에 둔다. 첫 사용자는 [`thought-experiment-runs/PROGRESS_BACKEND.md`](thought-experiment-runs/PROGRESS_BACKEND.md)에서 저장소 MD 또는 Notion MCP를 선택한다. 저장소 MD를 고르면 각 실험의 `progress.md`가 상태·acceptance criteria·blocker·결정의 정본이며, Notion을 고르면 그 페이지가 정본이고 로컬은 증거만 보관한다.

실행 전에 사용자 기획을 검증할 때는 `critical-validation`이 `grill-me → method/repro/novelty 독립 심사 → 사용자 결정` 순서로 처리한다. 전체 현황은 [비판 검증 레지스트리](thought-experiment-runs/CRITICAL_VALIDATION_REGISTRY.md)에서, 세부 증거는 실행 폴더에서 관리한다. 실행 폴더에는 승인된 기획의 `brief.md`, 역할별 `critique-{method,repro,novelty}.md`, 그리고 [종합 양식](thought-experiment-runs/CRITIQUE_TEMPLATE.md)을 따른 `critique.md`를 둔다. 미해결 치명적 결함이 있으면 `manifest.md`와 `results.md`를 만들기 위한 실험으로 넘어가지 않는다. 논문 코드를 Paper2Agent MCP로 만들 후보·산출물은 `paper-agents/{paper-slug}/`에 분리한다.
