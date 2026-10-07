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

`thought-experiment-runner`가 만든 작은 실험은 `thought-experiment-runs/{slug}/`에 둔다. 첫 사용자는 [`thought-experiment-runs/PROGRESS_BACKEND.md`](thought-experiment-runs/PROGRESS_BACKEND.md)에서 저장소 MD 또는 Notion MCP를, [비판 검증 온보딩 설정](thought-experiment-runs/CRITICAL_VALIDATION_SETTINGS.md)에서 `required` / `on-request` / `off`를 선택한다. 저장소 MD를 고르면 각 실험의 `progress.md`가 상태·acceptance criteria·blocker·결정의 정본이며, Notion을 고르면 그 페이지가 정본이고 로컬은 증거만 보관한다.

실행 전에 사용자 기획을 검증할 때는 `critical-validation`이 `grill-me → 필수 유사·대안·반대 문헌 검색 → 근거 해시 동결 → method/repro/novelty 독립 심사 → 사용자 결정` 순서로 처리한다. 전체 현황은 [비판 검증 레지스트리](thought-experiment-runs/CRITICAL_VALIDATION_REGISTRY.md)에서, 근거와 `analysis.json`은 각 실행 폴더에서 관리한다. JSON은 [.scripts/docs/idea-analysis.schema.json](../.scripts/docs/idea-analysis.schema.json)을 따르고 [.scripts/bin/idea_analysis.py](../.scripts/bin/idea_analysis.py)로 초기화·동결·검증한다. 심사자는 [역할별 페르소나](validation/personas/README.md)와 [공통 출력 계약](validation/critic-output.schema.json)을 따른다. 역할별 `critique-{method,repro,novelty}.md` 초안은 서로 격리하고 Graphify 대상에서 제외한다. 사용자의 결정을 받은 종합만 그래프 갱신 뒤 반영한다. 미해결 치명적 결함이나 조건부 판정이 남으면 실험으로 넘어가지 않는다. 논문 코드를 Paper2Agent MCP로 만들 후보·산출물은 `paper-agents/{paper-slug}/`에 분리한다.
