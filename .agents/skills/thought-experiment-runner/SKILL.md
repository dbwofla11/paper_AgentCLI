---
name: thought-experiment-runner
description: "사고실험·연구 가설을 작은 재현 실험과 문헌 방향 탐색으로 전환하고, 실행 가능한 논문 코드는 Paper2Agent MCP 후보로 평가한다. 사고실험을 실행·검증·구체화하거나 다음 실험을 찾을 때 사용한다."
---

# Thought Experiment Runner

사고실험을 가설 노트에만 남기지 않고, 작은 반증 가능 실험과 재현 가능한 실행 기록으로 연결한다. 가설·반증 조건은 `05-ideas/thought-experiments/`에 유지하고, 실행 입력·manifest·결과는 `04-Projects/thought-experiment-runs/{slug}/`에 분리한다.

## 진척 관리 온보딩

정본은 [`04-Projects/thought-experiment-runs/PROGRESS_BACKEND.md`](../../../04-Projects/thought-experiment-runs/PROGRESS_BACKEND.md)의 `backend` 값으로 정한다. 비판 검증 기본 정책은 [`CRITICAL_VALIDATION_SETTINGS.md`](../../../04-Projects/thought-experiment-runs/CRITICAL_VALIDATION_SETTINGS.md)의 `mode` 값으로 정한다.

**처음 실행하거나 `backend` 값이 `unset`이면, 다른 작업을 시작하기 전에 반드시 아래 질문을 하고 답을 기다린다.**

> 사고실험 진척을 어디에서 관리할까요?
>
> 1. `repository` — 이 저장소의 `04-Projects/thought-experiment-runs/{slug}/progress.md`에서 관리합니다.
> 2. `notion` — Notion MCP에 연결된 페이지 또는 데이터베이스에서 관리합니다.

- `repository` 선택: `PROGRESS_BACKEND.md`를 `backend: repository`로 갱신한다. 각 실험 폴더의 `progress.md`가 상태·acceptance criteria·blocker·결정의 정본이다.
- `notion` 선택: Notion MCP 연결 여부와 대상 페이지 또는 데이터베이스를 확인한 뒤 `backend: notion`과 링크·식별자를 기록한다. Notion이 정본이고 로컬은 실행 증거만 보관한다. MCP가 없거나 인증이 끝나지 않으면 연결 방법을 안내하고 진척 판정은 하지 않는다.
- 설정이 이미 있으면 질문을 반복하지 않는다. 사용자가 변경을 요청할 때만 backend를 바꾼다.

**`mode`가 `unset`이면 저장 backend와 별개로, 사고실험의 구체화·문헌 탐색·실행 전에 `CRITICAL_VALIDATION_SETTINGS.md`의 질문을 하고 답을 기다린다.** 선택한 `required` / `on-request` / `off`를 파일에 기록하고 사용자가 변경을 요청할 때만 바꾼다.

- `required`: 모든 새 사고실험 기획에 `critical-validation`을 먼저 적용한다. 심사를 통과했다는 표기는 사용자가 최종 결정을 기록한 경우에만 한다.
- `on-request`: 사용자가 비판 검증을 요청한 경우에만 `critical-validation`을 적용한다.
- `off`: 기본 흐름에서는 적용하지 않는다. 사용자가 설정 변경을 요청하면 그때 mode를 갱신한다.

어느 backend든 `manifest.md`와 `results.md`에는 정본 위치와 criterion별 증거 경로를 남긴다. 로컬 결과만으로 Notion 상태를 자동 변경하지 않는다.

## 기본 흐름

1. 대상 사고실험에서 핵심 질문, 고정해야 할 조건, 성공·반증 조건, 금지된 정보 누수를 읽는다. `mode: required`이면 `critical-validation`을 먼저 적용한다. `mode: on-request`에서 사용자가 독립 심사를 요청했거나, 전제와 설계의 단일 분석이 필요하면 각각 `critical-validation` 또는 `thought-experiment-critique`를 적용한다.
2. 관련 논문의 새 방향을 탐색한다. 최신성이나 인용 관계가 결론에 영향을 주면 `paper-search` 절차를 적용한다. 논문은 가설을 지지하는 근거와 반증·대안 모두를 찾고, 확인하지 못한 세부는 `[확인 필요]`로 남긴다.
3. 기존에 실행 가능한 코드·데이터가 있으면 가장 작은 결정론적 실험을 설계한다. 기본 상한은 단일 가설, 12개 이하 condition, 고정 seed, 짧은 실행이다. 새 의존성 설치·대규모 다운로드·장시간 학습·외부 API 호출은 이 단계에서 하지 않는다.
4. `04-Projects/thought-experiment-runs/{slug}/`에 다음을 남긴다.
   - `brief.md` — `critical-validation`을 거친 경우에만 작성. 사용자가 승인한 가설·성공/반증 조건·최소 대조군·제약
   - `critique-{method,repro,novelty}.md`와 `critique.md` — 독립 비판 검증을 했을 때만 작성. `critique.md`의 미해결 치명적 결함이 있으면 실행하지 않음
   - `manifest.md` — 진척 정본 위치·실행 당시 상태, 조건 ID, 입력, seed, 코드·환경 버전, 성공·반증 기준
   - `results.md` — criterion별 증거, 실행 여부, condition별 결과, 실패·누락, artifact 경로, 해석과 원자료의 구분
   - `progress.md` — backend가 `repository`일 때만 작성. 상태, acceptance criteria, blocker, 결정, 다음 행동을 기록
   - 실행 코드가 이미 있을 때만 그 코드를 호출한다. 원본 논문 PDF·기존 simulator·원본 manifest는 수정하지 않는다.
5. 결과는 가설을 승인하지 않는다. 관측값, 결측, 재현 여부만 보고하고, 가설의 채택·변경은 사람이 승인한다.

## Paper2Agent 연동

사고실험에서 특정 논문의 방법을 실제로 적용할 필요가 생기면 자동으로 **준비성 검사**를 한다.

- 논문과 공식 코드 저장소가 연결되는지
- 실행 가능한 tutorial/example, 라이선스, 요구 데이터·compute가 있는지
- 작은 기준 실행이 사람이 만든 기대 결과를 재현하는지
- 노출할 함수가 좁고 안전한지 (`run_condition`, `reconstruct`, `compute_metrics`, `fetch_artifact` 등)

준비성 검사를 통과하면 `04-Projects/paper-agents/{paper-slug}/`를 Paper2Agent 산출물 후보 위치로 제시하고, MCP 도구의 입력·출력·권한을 사고실험 manifest에 맞춘다. MCP는 정답 데이터, 임의 shell, credential, manifest overwrite 권한을 받지 않는다.

Paper2Agent의 전체 agentification은 코드 분석·환경 구성·반복 테스트와 모델 비용을 수반할 수 있다. 따라서 사용자가 `agentify`, `Paper2Agent로 만들어`, 또는 동등하게 실제 생성을 요청했을 때만 실행한다. 준비성 검사와 작은 로컬 실험은 이 스킬의 기본 동작이다.

## RF simulation 적용

`2026-09-15-agents-api-rf-simulation-loop.md`에서는 agent를 물리 모델의 판정자가 아니라 고정 manifest의 실행·기록 controller로 제한한다. 첫 실행은 single-target localization의 작은 condition grid로 하고, simulator-to-real gap과 정보 누수는 별도 결과로 기록한다. WaveVerse 또는 inverse solver의 공식 코드가 tutorial과 함께 확보되면, 검증된 좁은 함수를 Paper2Agent MCP 후보로 평가한다.

## 보고 형식

짧게 다음을 보고한다: 핵심 가설, 실행한 작은 실험 또는 실행 불가 사유, 새 문헌 방향 1–3개, Paper2Agent 준비성(`준비됨` / `코드 필요` / `tutorial 필요` / `비용 승인 필요`), 다음 사람 결정 1개.
