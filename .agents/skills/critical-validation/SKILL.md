---
name: critical-validation
description: "사용자의 연구 기획을 grill-me로 구체화한 뒤, 방법·재현성·새로움 관점의 독립 서브에이전트 심사로 검증한다. 사고실험이나 연구 기획의 진행 전 비판 검증에 사용한다."
---

# Critical Validation

사용자의 아이디어를 곧바로 실험으로 바꾸지 않는다. 먼저 `grill-me`로 검증 가능한 기획을 만들고, 그 기획을 서로 독립적인 비판 서브에이전트가 공격하게 한다. 이것은 A2A 연동이나 자율 프로젝트 실행 절차가 아니다. 서브에이전트는 **읽기 전용 심사자**이며, 진행·보류·폐기 결정은 사용자에게 남긴다.

## 시작 조건

- `thought-experiment-runner`의 진척 backend 온보딩이 완료된 뒤에 적용한다. backend가 `unset`이면 해당 스킬의 질문을 먼저 하고 기다린다.
- [`CRITICAL_VALIDATION_SETTINGS.md`](../../../04-Projects/thought-experiment-runs/CRITICAL_VALIDATION_SETTINGS.md)의 `mode`도 확인한다. `unset`이면 온보딩 질문을 먼저 하고 기다린다. `required`일 때는 모든 새 기획에 적용하고, `on-request`일 때는 사용자가 요청한 기획에만 적용한다. `off`일 때는 사용자가 mode 변경을 요청할 때까지 시작하지 않는다.
- [`CRITICAL_VALIDATION_REGISTRY.md`](../../../04-Projects/thought-experiment-runs/CRITICAL_VALIDATION_REGISTRY.md)를 먼저 읽어 대상 기획의 기존 심사 상태와 근거를 확인한다. 항목이 없으면 `미심사`·세 역할 `대기`로 새 행을 등록한다.
- 사용자가 아직 아이디어만 제시했다면 `grill-me` 단계부터 시작한다. 이미 구체적인 기획이 있더라도 아래 필수 항목이 비어 있으면 이 단계를 생략하지 않는다.
- 이 심사 요청에는 주장·대안·반례 문헌 검색이 포함된다. 검색 프로토콜과 접근 가능한 검색 소스를 사용하고, 접근이 막힌 경우에는 우회하거나 키를 만들지 말고 `문헌 확인 부족`으로 중단한다. 실험 실행, 유료 API 사용, 의존성 설치는 이 스킬만으로 승인되지 않는다.

## 1. Grill-me: 기획 고정

사용자가 답할 수 있을 만큼 한 번에 필요한 질문만 묻고, 답변을 바탕으로 `04-Projects/thought-experiment-runs/{slug}/brief.md`를 작성 또는 갱신한다. grill-me를 시작하면 레지스트리 전체 상태를 `grill-me`로 갱신한다. 확정 전에는 다음을 빈칸 없이 만든다.

- 해결하려는 문제와 대상 사용자/상황
- 핵심 주장 또는 가설, 그리고 기존 접근보다 나아질 이유
- 관측 가능한 성공 기준과 수치·비교 기준
- 무엇이 나오면 가설이 틀렸다고 인정할지(반증 조건)
- 최소 실험, 대조군, 필요한 데이터와 계산 자원
- 허용되지 않는 정보(누수 위험), 제약과 알려진 불확실성
- 사용자가 지금 원하는 결정: 탐색, 검증, 보류, 프로젝트화 중 하나

질문을 유도하거나 사용자의 답을 그럴듯하게 보완하지 않는다. 근거 없는 답은 `[가설]`, 확인하지 못한 내용은 `[확인 필요]`로 적는다. 사용자가 `brief.md`의 핵심 가설·성공/반증 조건을 승인하면 전체 상태를 `심사 대기`로 갱신하고 `python3 .scripts/bin/idea_analysis.py init {slug} --brief 04-Projects/thought-experiment-runs/{slug}/brief.md`로 analysis JSON을 한 번 초기화한다. 승인 전에는 심사를 시작하지 않는다.

## 2. 독립 서브에이전트 심사

먼저 메인 에이전트가 필수 문헌 검색과 동결 근거 묶음을 만든다. 검색은 지원 주장과 기존 대안·반례를 분리한 질의로 수행하고, 최소 2개의 검색 소스를 사용한다. 검색일, 질의·목적, 각 소스와 결과 수, 포함 논문 ID·URL·선정 이유·(존재하면) 로컬 JSON 경로, 제외 결과와 이유, 검색 한계를 기록한다. 관련 문헌을 찾지 못했거나 비교 근거가 부족하면 `문헌 확인 부족`으로 중단하고 심사를 통과시키지 않는다.

묶음에는 승인된 `brief.md`, 검색 기록, 관련 논문 JSON(있는 경우), 연결된 리뷰·원문 PDF의 필요한 범위, 주장별 지지·반대 근거와 위치를 포함한다. 온라인 출처 자체는 복제하지 않는다. URL·검색일·근거 위치·발췌 요약이 묶음 해시에 포함되고, 저장소 내 파일은 개별 SHA-256으로 검사된다. 분석 컨텍스트는 `.scripts/docs/idea-analysis.schema.json`에 따라 `04-Projects/thought-experiment-runs/{slug}/analysis.json`에 저장한다. 다음 명령으로 초기화·동결·검증한다.

```bash
python3 .scripts/bin/idea_analysis.py freeze 04-Projects/thought-experiment-runs/{slug}/analysis.json
python3 .scripts/bin/idea_analysis.py validate 04-Projects/thought-experiment-runs/{slug}/analysis.json
python3 .scripts/bin/idea_analysis.py record-critic 04-Projects/thought-experiment-runs/{slug}/analysis.json method <critic-output.json>
```

`record-critic` 명령은 `method`, `repro`, `novelty` 각각에 대해 한 번씩 실행한다. 각 심사 결과 JSON의 해시는 bundle 파일의 `sha256`과 같아야 한다.

동결 전에는 검색 항목·출처 위치·포함 논문 레코드를 채운다. `freeze`는 출처 파일 SHA-256을 수집하고 불변 `evidence-bundle-vN-<hash>.json`을 만든다. 해시가 바뀌면 기존 심사와 종합은 초기화된다. 이 **동일 파일과 동일 해시**를 아래 세 역할에 읽기 전용으로 제공한다. 심사자는 자신에게 할당된 페르소나 파일만 읽으며 다른 심사 결과, 주 에이전트 종합, 사용자 선호를 보지 않는다. 심사자에게 별도 검색 권한을 주지 않는다. 추가 근거가 필요하면 심사 결과에 요청을 남기고, 메인 에이전트가 근거를 보완해 새 버전으로 동결한 뒤 세 심사자를 모두 다시 호출한다.

방법·재현성·새로움 심사는 각각 독립된 서브에이전트로 병렬 호출한다. 각 호출 입력에는 동일한 bundle 경로·SHA-256과 해당 역할 페르소나 파일만 넣고, 출력은 공통 critic JSON 계약으로 받는다. 실행 플랫폼에서 세 호출의 입력·출력을 격리할 수 없다면 순차 역할극으로 대체하지 말고 `심사 대기`로 멈춘다.

시작 시 전체 상태를 `심사 중`으로, 각 역할은 실행 중일 때만 `진행`으로 표기한다. 각 심사자는 다른 심사자의 초안, 주 에이전트의 낙관적 결론, 사용자 결정의 선호를 보지 않는다. 심사자는 코드를 수정하거나 실행하지 않고, Notion·진척 상태·manifest를 바꾸지 않으며, 별도 서브에이전트를 만들거나 외부 서비스에 접근하지 않는다.

| 역할 | 페르소나 | 반드시 검증할 것 | 산출물 |
| --- | --- | --- | --- |
| `method-critic` | [`method-critic.md`](../../../04-Projects/validation/personas/method-critic.md) | 주장과 관측의 연결, 인과/식별가능성, 대조군, 반증 가능성, 대체 설명 | `critique-method.md` + analysis JSON |
| `repro-critic` | [`repro-critic.md`](../../../04-Projects/validation/personas/repro-critic.md) | 데이터·평가 누수, split/seed/환경/버전, 지표의 적합성, 재현 가능한 증거 | `critique-repro.md` + analysis JSON |
| `novelty-critic` | [`novelty-critic.md`](../../../04-Projects/validation/personas/novelty-critic.md) | 선행연구 대비 새로움, 자명한 조합 여부, 더 단순한 접근, 문헌 확인이 필요한 주장 | `critique-novelty.md` + analysis JSON |

각 산출물은 [`critic-output.schema.json`](../../../04-Projects/validation/critic-output.schema.json)의 공통 필드를 만족해야 한다. `evidence_bundle_sha256`가 analysis JSON의 동결 해시와 다르면 결과를 버리고 재실행한다. 근거 참조는 묶음 안의 paper ID와 `§`, `p.`, `Fig.`, `Table`, `Eq.` 위치로 연결한다. 심사자가 근거를 확인할 수 없으면 결론을 만들지 말고 `[확인 필요]`를 요청으로 남긴다. 결과를 analysis JSON에 반영한 뒤 validator를 실행한다.

멀티에이전트 실행 환경을 사용할 수 없으면 단일 에이전트가 세 역할을 순서대로 흉내 내지 않는다. analysis JSON과 레지스트리에 `심사 대기`를 남기고, `critique.md`를 만들어 Graphify에 섞지 않는다. 사용자에게 독립 심사가 실행되지 않았음을 알린다.

## 3. 사용자 결정용 종합

세 심사가 모두 끝난 뒤에만 JSON `synthesis`를 작성해 검증하고 사용자에게 결정 선택지를 보여준다. [`04-Projects/thought-experiment-runs/CRITIQUE_TEMPLATE.md`](../../../04-Projects/thought-experiment-runs/CRITIQUE_TEMPLATE.md)에 따른 최종 `critique.md`는 사용자의 결정을 받은 뒤 기록한다. 종합자는 심사 의견을 다수결로 처리하지 않는다. 세 역할 중 하나라도 미완료·해시 불일치·조건부/치명 판정·`유지` 외 권고가 있으면 `experiment_candidate`로 올리지 않는다. 사용자가 최종 결정을 JSON에 기록한 뒤 `idea_analysis.py validate`로 검사한다. 통과한 경우에만 `graphify_sync.py begin --source 04-Projects/thought-experiment-runs/{slug}/analysis.json`을 실행하고 Graphify 스킬 `.` `--update`로 전체 문서를 갱신한다. 성공/실패를 `graphify_sync.py complete` 또는 `fail`로 기록한다. `.graphifyignore`가 개별 critic 초안과 동결 packet을 제외하며, 종합·사용자 결정이 끝난 결과만 그래프에 들어간다. 최종 진행 결정은 사용자만 내린다.

- `보완 필요`: 비판이 구체적이며 brief를 수정하면 검증 가능한 경우. grill-me 질문으로 되돌아간다.
- `실험 가능`: 성공·반증·최소 대조군·누수 방지가 모두 명시되고 치명적 결함이 해소된 경우. 그때만 `thought-experiment-runner`로 넘긴다.
- `보류`: 핵심 근거나 자원, 문헌 확인이 부족한 경우.

어느 경우에도 상태 전환은 사용자가 승인한다. Paper2Agent 준비성은 이 심사에서 미해결 치명적 결함이 있으면 `준비됨`으로 기록하지 않는다.

## 보고

사용자에게는 brief에서 확정된 가설, 심사별 핵심 반론, 반드시 답해야 할 grill-me 질문, 권고 상태 하나를 짧게 보여준다. 비판의 원문과 증거는 실행 폴더에 남기고, Notion이 정본이면 해당 페이지에도 상태와 링크를 기록할 후보로만 제시한다.
