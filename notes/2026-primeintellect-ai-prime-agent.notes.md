# Prime Agent — 저장소 분석 메모

- 대상: [github.com/PrimeIntellect-ai/prime-agent](https://github.com/PrimeIntellect-ai/prime-agent)
- 논문 아님(오픈소스 CLI 에이전트 저장소). MIT 라이선스, ★19.5k(조사 시점).
- 조사일: 2026-09-01. **WebFetch(AI 요약) 기반** — 저장소 raw 문서(`packages/coding-agent/docs/*.md`)를 소형 모델 요약으로 읽었고, TypeScript/Python 소스 자체는 확인 못함. 필드명·정확한 API 시그니처는 재확인 필요 [확인 필요].

## 정체

코딩 작업·장시간 자율 작업용 에이전트 CLI. 핵심 표어는 "self-improving RLM agent". Claude Code류 도구와 달리 (1) 세션이 데몬 프로세스로 영속 — disconnect 후 `attach`/`--resume`으로 복귀, (2) 재귀적 서브에이전트 호출(RLM)을 언어 차원의 1급 기능으로 제공, (3) 세션 진행 중 스스로 보충 상태를 갱신하는 "Continual Harness"를 갖춘 것이 차별점.

## RLM (Recursive Language Model) — 실행 모델

- 각 세션은 지속적 Python REPL 커널(`prime-agent-runtime`)을 가짐. 부모 모델이 이 커널에서 `await rlm(prompt, name=...)`을 호출하면 자식 세션이 생성됨.
- 호출 즉시 `RLMSpawnHandle`을 반환하고 자식 완료를 기다리지 않음(non-blocking). 자식은 독립 `AgentSession`으로 실행되고, 결과는 나중에 `agent_message.send(..., receiver_role="parent")`로 회신하거나 파일로 남김.
- 깊이 제한: 기본 `RLM_MAX_DEPTH=2` (루트→자식→손자까지, 손자는 추가 생성 불가, 설정 시 변경 가능).
- 자식 사용량/비용은 비동기적으로 부모 assistant turn에 fold됨 (`child_usage_attributed` 트랜스크립트 항목). 부모 컨텍스트 윈도우는 부풀리지 않음.
- 부모-스코프 서브에이전트 레지스트리(TypeScript 측)가 자식 상태를 권위 있게 관리 — 커널 재시작·압축·부모 복원을 견딤. `rlm.list_subagents()` / `rlm.delete_subagent()`로 조회·삭제.
- 신뢰 경계: REPL은 워커 OS 권한으로 코드 실행 — **보안 샌드박스 아님**. 프로세스 격리는 프로토콜/생명주기 목적일 뿐, 신뢰 못 하는 코드는 별도 샌드박스 필요.

## 자가진단/자기개선 설계 — Continual Harness + `/refine` [본문 핵심]

**질문한 "자가진단"에 해당하는 메커니즘은 정확히는 자기 성능을 채점하는 평가 루프가 아니라, 세션 궤적을 리뷰해서 보충 상태(harness state)를 갱신하는 "자기 개정(self-refinement)" 구조다.**

### 1. 상태 저장 위치 및 구조

- `rlm.harness`: 프롬프트 노트, 메모리, 재사용 가능한 스킬 설명, 서브에이전트 사양, "개선 이벤트"를 담는 지속 원장(ledger). 문서는 명시적으로 "이것은 두 번째 실행 엔진이 아니다"라고 못박음 — 즉 harness는 판단/추론 엔진이 아니라 상태 저장소.
- 세션 로컬 상태 파일: `<session-artifacts>/<root-session-id>/harness/harness_state.json`
- 전역 상태: `~/.prime/agent/harness/`
- Python 쪽 저장소는 외부(호스트)의 수정 이후 재로드하도록 되어 있어, 호스트 측 `/refine` 기록과 커널 내부 기록이 서로 덮어쓰지 않게 설계됨 [확인 필요: 구체적 동시성 제어 방식(락/버전 체크)은 문서에 없음].

### 2. `/refine` 명령의 동작

- `/refine [instructions]` — 현재 세션의 trajectory(지금까지의 턴·도구 호출·결과 흐름)에 대해 "전담 리뷰(dedicated review)"를 실행.
- 리뷰 결과로 harness state에 **작은 create/update/delete 편집**만 적용 (대규모 재작성이 아니라 점진적 패치).
- **기본 시스템 프롬프트는 불변** — `/refine`이 건드리는 건 어디까지나 보충(supplementary) 상태이지 코어 프롬프트가 아님. 이는 모델의 근본 행동을 세션마다 임의로 바꾸지 못하게 막는 안전장치로 보임 [내 해석].
- 롤백: 편집마다 **before/after 스냅샷을 기록**해두고, 필요 시 이를 이용해 되돌림. 즉 자가개선이 단조 누적이 아니라 감사 가능(auditable)하고 되돌릴 수 있는 구조.

### 3. 장기 실행 중 자가 점검 루프 3종 (자가진단을 보조하는 주변 장치)

| 명령 | 역할 |
|---|---|
| `/heartbeat every 10m "..."` | 주기적으로 세션에 재진입해 지정된 점검(예: 배포 상태 확인)을 반복 수행. `--follow-up`으로 현재 작업 완료 후 실행하도록 예약 가능. status/pause/resume/clear로 관리 |
| `/goal "..." [--budget N]` | 목표를 `goal.complete()` 호출 전까지 매 턴 프롬프트에 지속 노출. 토큰 예산·진행 상태·사용량을 `AgentSession`이 추적 |
| `/autonomous on` (대화형) 또는 `--autonomous-gate "npm run check"` (CLI) | 지정한 품질 게이트 명령이 통과하거나 턴/토큰/시간 예산 소진 시까지 연속 실행. **게이트 실패 시 그 출력(bounded)을 에이전트에 되돌려줘서 재시도를 유도** — 변경 없는 상태로 동일 실패 게이트를 무한 반복하지는 않도록 설계 |

이 세 명령은 "자가진단"이라기보다 사람이 정의한 외부 검증 기준(셸 커맨드, 목표 완료 조건)에 대해 에이전트가 스스로 재시도/보고하게 만드는 장치에 가깝다. 즉 진단 기준 자체는 사용자가 준다(`npm run check` 같은 게이트 커맨드, heartbeat 지시문, goal 문구) — 에이전트가 스스로 "내가 잘하고 있는가"를 판단하는 내재적 자기평가 지표를 만들어내는 것은 아님 [내 해석, 확인 필요].

### 4. 세션 아티팩트 레이아웃 (자가개선 상태가 실제로 저장되는 파일 트리)

```
~/.prime/agent/
  sessions/<root-session-id>.jsonl
  session-artifacts/<root-session-id>/
    kernel-state.dill
    kernel-state.json
    scheduled-jobs.json
    harness/harness_state.json      ← /refine이 갱신하는 파일
    sub-xxxxxxxx/<child-session-id>.jsonl
```

### 5. 구현 소유권 (문서에 명시된 소스 위치, 미확인)

| 파일 | 책임 |
|---|---|
| `src/core/kernel/repl-manager.ts` | stdio 프로토콜, 실행, host-request 발송 |
| `src/core/tools/ipython.ts` | 커널 제공, 네임스페이스 부트스트랩 |
| `src/core/agent-session.ts` | RLM 정책, 자식 레지스트리, goal 핸들러 |
| `src/core/rlm-runtime.ts` | `rlm.run` 요청 검증, 모델 발견 |
| `prime-agent-runtime/src/rlm/` | Python shim, 세션 지원 harness 상태 |

## 스킬(Skills) — harness와 별개의 확장 메커니즘

- 마크다운 스킬(지시문 중심) / 파이썬 스킬(`pyproject.toml` + `src/<name>/__init__.py`, 커널 venv에 설치되어 `await skill_name()`으로 호출) 두 종류.
- 필수 `SKILL.md` frontmatter: `name`(≤64자), `description`(≤1024자), 선택적 `license`, `disable-model-invocation`(true면 `/skill:name`으로만 명시 호출).
- 내장 스킬 3종: `prime-intellect`, `skill-creator`, `websearch`.
- 저장소: 전역 `~/.prime/agent/skills/`, 프로젝트 `.prime/agent/skills/`, 패키지 `package.json`의 `skills/`, CLI `--skill <경로>`.
- 문서 자체가 "스킬은 임의 코드를 포함할 수 있어 실행 전 검토 필수"라고 경고 — harness가 스킬 "설명"을 자동으로 축적/개정할 수 있다는 점과 결합하면, `/refine`이 검증 없이 신뢰되지 않는 스킬 설명을 생성·수정할 잠재적 리스크가 있음 [내 의견, 확인 필요: 문서는 이 상호작용을 명시적으로 다루지 않음].

## 주의할 점 [확인 필요]

- 위 내용은 WebFetch(소형 모델 요약)로 얻은 것이며 TypeScript/Python 소스 코드 원문은 대조하지 않았다. `harness_state.json`의 실제 스키마(필드명, 이벤트 로그 포맷), `/refine`이 사용하는 리뷰 프롬프트나 판단 기준, before/after 스냅샷의 정확한 저장 위치는 문서에 상세 기술되지 않았거나 확인 못함.
- "자가진단"이라는 표현에 맞는 정량적 자기평가지표(성공률, 회귀 감지 등)는 문서에서 발견하지 못함 — 있다면 `packages/coding-agent/docs/development.md` 또는 소스 코드 직접 확인 필요.
- GitHub 코드 검색은 비로그인 상태에서 접근 불가하여 `/refine` 구현부(예: 리뷰 프롬프트 텍스트)를 직접 확인하지 못함.
