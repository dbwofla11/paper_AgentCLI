# 연구 하네스 그래프

논문을 모으는 두 입력 경로를 하나의 검증 가능한 연구 지식 흐름으로 연결한다. 연구 노트와 PDF의 폴더 구조는 유지한다.

```mermaid
flowchart LR
    upload["사용자 PDF·논문 링크"] --> intake["paper-search<br>메타데이터·중복 확인"]
    intake --> keep["01-Papers/keep.md<br>읽기 대기열"]
    daily["매일 09:00 KST<br>CV 1 + 멀티모달 1 + 관심 분야 1"] --> candidates["후보 3편을 채팅으로 제시"]
    candidates -->|사용자 채택| intake
    intake --> record["library/{slug}.json<br>수집 시 생성"]
    record --> review["paper-review<br>3패스 정독 + 5축 분석"]
    review -->|근거·분석 보강| record
    record --> graph["Graphify<br>논문·개념·주장 관계"]
    review --> candidate["개념 후보 초안<br>00-Inbox/concept-candidates"]
    candidate -->|사용자 이해 확인 + 승격 요청| concept_skill["concept-note"]
    concept_skill --> concepts["02-Concepts<br>학습 정본"]
    concepts --> graph["Graphify 갱신<br>pending / success"]
    review --> idea["05-ideas<br>가설·반증 조건"]
    idea --> grill["grill-me<br>기획 고정"]
    grill --> packet["동일한 읽기 전용 근거 묶음"]
    record --> packet
    packet --> method["method-critic persona"]
    packet --> repro["repro-critic persona"]
    packet --> novelty["novelty-critic persona"]
    method --> synth["종합·사용자 결정"]
    repro --> synth
    novelty --> synth
    synth -->|승인| experiment["04-Projects<br>작은 실험·결과"]
    experiment --> record
    experiment --> daily
```

## 실행 원칙

- 사용자가 올린 논문은 메타데이터를 확인해 Keep 목록과 논문별 JSON에 등록한다. PDF를 올렸으면 기존 `01-Papers/pdfs/{category}/`에 보관한다. 중복이면 기존 항목을 갱신하고 같은 논문을 추가하지 않는다.
- 일일 후보는 매일 정확히 3편이다. 컴퓨터 비전 1편, 멀티모달 1편, 그리고 사용자의 활성 아이디어·Keep·Concepts·최근 리뷰에서 관심 분야를 골라 1편을 제시한다. 공식 학회 발표·게재가 확인된 논문만 후보로 제시한다. 후보는 채팅에만 표시하며, 사용자가 채택한 뒤에 수집한다.
- 논문 JSON은 수집 때 확인된 메타데이터만 담고, 심층 리뷰가 끝나면 5개 분석 축과 위치가 명시된 근거를 보강한다. 근거가 없으면 빈 값 또는 `[확인 필요]`로 남긴다. 스키마는 [paper-record.schema.json](../.scripts/docs/paper-record.schema.json)을 따른다.
- 아이디어 심사 전 지원·대안·반대 문헌을 최소 2개 소스에서 검색한다. 결과·제외 이유·위치가 고정되지 않거나 관련 근거가 부족하면 심사를 중단한다. analysis JSON은 `.scripts/docs/idea-analysis.schema.json`과 `.scripts/bin/idea_analysis.py`로 관리하며, 동결 SHA-256이 동일한 입력만 세 심사자에게 준다.
- 논문 리뷰에서 재사용 가능한 개념 후보는 `00-Inbox/concept-candidates/`에 자동 초안으로 만들 수 있다. 이것은 사용자의 이해나 학습 노트가 아니다. `02-Concepts/` 정본은 사용자가 내용을 확인·수정하고 승격을 명시적으로 요청한 경우에만 만든다.
- 논문 JSON 또는 승인된 개념/아이디어 정본 변경 뒤에는 `graphify_sync.py begin` → Graphify 스킬 `--update` → `complete`로 상태를 기록한다. Graphify의 단순 CLI AST 갱신은 문서 의미 추출을 대체하지 않는다. 실패는 pending으로 재시도한다. 임시 심사 초안과 개념 후보는 그래프에서 제외한다.
- 기존 PDF는 `python3 .scripts/bin/paper_record.py import-pdfs`로 레코드를 보충할 수 있다. 리뷰 메타데이터가 없으면 제목을 추정하지 않고 `metadata_status: needs_review`로 둔다.
- 아이디어 심사자는 동일한 brief와 근거 묶음을 읽기 전용으로 받는다. 역할별 초안은 서로 공유하지 않는다. 종합자는 다수결로 승인하지 않으며, 최종 진행 결정은 사용자에게 있다.
- 승인된 아이디어만 작은 실험으로 보낸다. 결과와 해석을 구분하고, 관련 JSON·개념·검색 맥락을 갱신해 다음 탐색에 연결한다.
- 예약 실행은 Orca Automation이 담당한다. `daily-digest-loop` 스킬은 호출당 후보 검색·보고만 수행하며 파일 저장, 뉴스 수집, Git commit/push를 하지 않는다.

## 라우터

현재 단계를 선언하면 다음 진입점을 확인할 수 있다.

```bash
python3 .scripts/bin/research_workflow.py daily
python3 .scripts/bin/research_workflow.py idea
```

`Skill-Catalog.md`는 조회용이고 실행 순서는 `.scripts/bin/research_workflow.py`가 담당한다. Graphify 질문은 기존 그래프를 우선 조회한다. 코드 변경은 AST CLI 갱신, 논문·개념 문서 변경은 Graphify 스킬의 `--update` 의미 추출을 수행한다.

대시보드의 작업 흐름 안내는 `.scripts/docs/research-workflow-map.json`을 읽는다. 이 파일은 기본 순서와 선택 단계·확인 조건·병렬 역할을 명시하며 `research_workflow.py --json`에도 포함된다. 새 흐름을 추가하거나 순서를 바꾸면 관련 스킬 지침과 함께 갱신하고 `verify_harness.py`로 참조 경로를 검사한다. 모든 스킬을 한 번에 순차 실행하는 명령은 아니다.

## 운영 화면과 보조 자동화

- `100-views/harness-dashboard.html`은 스킬 연결, 페르소나, 검증기, Graphify 동기화를 정본과 검사 결과에서 읽는다. `python3 .scripts/bin/harness_dashboard.py`로 다시 만든다. 이 페이지는 읽기 전용이며 로컬 파일 수정이나 셸 실행은 제공하지 않는다.
- `100-views/paper-library.html`은 `01-Papers/library/*.json`에서 다시 생성한다. 로컬 PDF를 우선 연결하고, 유효한 HTTP(S) 원문만 대체 링크로 사용한다.
- `100-views/thought-experiments.html`은 아이디어 노트, 비판 검증 레지스트리, 실험 폴더, TODO JSON을 결합한다. 상태 충돌은 표시하고 자동 조정하지 않는다.
- 이 저장소의 첫 실행은 [노트북 온보딩 안내](onboarding.md)와 `onboarding_check.py`로 준비한다. 다른 저장소로 스킬을 옮길 때는 `install_research_harness.py`를 dry-run 기본으로 사용한다. 대상 저장소 적용·갱신·제거는 manifest와 충돌 보존 정책을 따른다.
- 연구 TODO의 구조화 원장은 `04-Projects/research-todo/queue.json`이다. `research_todo.py dispatch --execute`는 준비된 `orca-ide` 런타임과 현재 저장소 worktree를 확인한 뒤 세 탐색 worker 및 의존성으로 묶인 근거 확인 worker를 시작한다. `sync`는 정확한 Run만 조회하며, 결과 검증·보고서 publish가 끝나기 전에는 조사 완료로 표시하지 않는다. Orca가 없거나 준비되지 않으면 dispatch하지 않는다.

운영 화면 갱신 명령은 대시보드 하단과 각 HTML에 기록한다. 화면 간 이동은 하네스 대시보드, 논문 라이브러리, 사고실험 목록을 연결한다.
