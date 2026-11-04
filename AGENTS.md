# 논문 리뷰 에이전트

AI / ML / CS 논문을 **개별 심층 리뷰**하는 작업 공간이다. 산출물은 한국어로 쓰되 전문 용어와 논문 제목은 원어를 병기한다.

## 디렉터리

| 경로 | 용도 |
|---|---|
| `01-Papers/pdfs/{category}/` | 카테고리별 원문 PDF |
| `01-Papers/reviews/{category}/` | 카테고리별 최종 심층 리뷰 노트 (논문 1편 = 파일 1개) |
| `01-Papers/triage/` | 논문별 1차 판정·조사 메모 |
| `01-Papers/index.md` | 읽은/읽을 논문 인덱스 (한 줄 = 한 편) |
| `01-Papers/keep.md` | 나중에 읽거나 조사할 대기열 |
| `01-Papers/favorites.md` | 선호 논문 기록 |
| `02-Concepts/` | 사용자가 공부해 이해한 내용을 쌓는 공부노트 |
| `03-Trends/daily/` | 날짜별 다이제스트 |
| `05-Ideas/thought-experiments/` | 연구 아이디어·사고실험 |
| `wiki-index.md` | 위키 페이지 전체 목록 (자동 생성, 직접 수정 금지) |
| `wiki-log.md` | 위키 작업 기록 (추가만 함) |
| `90-Templates/paper/` | 리뷰·트리아지 템플릿 |
| `.scripts/bin/paper.py` | arXiv / Semantic Scholar / OpenAlex 조회 CLI (stdlib만 사용) |
| `.scripts/bin/wiki.py` | 위키 인덱스 생성·작업 기록·구조 점검 CLI (stdlib만 사용) |
| `.mcp.json` | 연결된 MCP 서버 — `exa`(의미 검색, API 키 필요), `arxiv-mcp`, `paper-search-mcp` |

## 새 세션 시작 (필수)

이 저장소를 새로 복제했거나 새 에이전트 세션에서 첫 사용자 요청을 받으면, 요청을 처리하기 전에 저장소 루트에서 다음 점검을 실행한다.

```bash
python3 .scripts/bin/onboarding_check.py --create-dirs
```

Windows에서는 `py -3 .scripts/bin/onboarding_check.py --create-dirs`를 사용한다.

`--host`를 생략하면 개인 연결 설정의 에이전트를 우선하고, 설정이 없으면 설치된 `codex` → `claude` → `omp` 순서에서 처음 발견된 호스트를 선택한다. 특정 호스트를 검사하려면 `--host omp`, `--host claude` 또는 `--host codex`를 명시한다.

- 성공하면 사용자 요청을 계속 처리한다. 사용자에게 README를 읽거나 수동 점검을 실행하라고 요구하지 않는다.
- 실패하면 출력의 `FAIL` 항목과 필요한 설치 명령만 간단히 보고한다. 해당 도구가 필수인 작업은 보류하되, 가능한 범위의 작업은 계속한다.
- 이 스크립트는 멱등(idempotent)이며 정해진 작업 디렉터리 생성과 환경 검증만 한다. 패키지 설치, API 키 저장, 기존 연구 자료 수정·삭제는 하지 않는다.
- `README.md`는 사람을 위한 clone·사용 안내다. 사용자가 요청했거나 사람이 읽을 안내가 필요할 때만 참조한다.

## 학습·연구 하네스

`docs/Home.md`는 전체 MOC다. `00-Inbox/`, `01-Papers/`, `02-Concepts/`, `03-Trends/`, `04-Projects/`, `05-Ideas/`, `90-Templates/`, `99-Attachments/`, `.scripts/`는 탐색과 운영을 위한 레이어다.

- `02-Concepts/`는 논문 한 편의 요약이 아니라 사용자가 공부해 이해한 내용을 축적하는 공부노트다.
- `04-Projects/`는 실행할 실험·구현·스터디를, `05-Ideas/`는 검증 전 가설과 반증 조건을 다룬다.
- 원문 PDF·심층 리뷰·일일 트렌드·사고실험·자동화의 정본은 각각 `01-Papers/pdfs/`, `01-Papers/reviews/`, `03-Trends/daily/`, `05-Ideas/thought-experiments/`, `.scripts/bin/`이다.
- 논문별 기계 판독 레코드는 `01-Papers/library/{slug}.json`에 둔다. 수집 때 메타데이터를 기록하고 심층 리뷰 뒤 5축 분석과 원문 근거를 보강한다. 모든 축 검증 뒤 `structured_review_status: complete`로 표시한다. 형식은 `.scripts/docs/paper-record.schema.json`을 따른다.
- `01-Papers/keep.md`(읽기/조사 대기열)와 `01-Papers/favorites.md`(선호 논문)는 독립 목록으로 유지한다. `01-Papers/library/`에는 논문 JSON만 둔다.
- 사람용 안내 문서는 `docs/`에 둔다.

- 직접 만든 HTML 화면은 `100-views/`, 공통 화면 자산은 `100-views/assets/`에서 관리한다. 생성기는 `.scripts/bin/`에 유지한다.

## LLM-Wiki 운영

이 저장소는 에이전트가 유지하는 위키로 운영한다. 세 층을 구분한다.

- **원본**: `01-Papers/pdfs/`의 PDF와 `99-Attachments/`의 첨부. 읽기만 하고 수정하지 않는다.
- **위키 페이지**: `01-Papers/reviews/{category}/`, `01-Papers/triage/`, `02-Concepts/`, `03-Trends/daily/`, `05-Ideas/thought-experiments/`, `04-Projects/thought-experiment-runs/{slug}/`의 `results.md`·`critique.md`·`manifest.md`. 범위의 정본은 `.scripts/bin/wiki.py`의 `PAGE_SCOPE`이고 Git이 보는 파일만 포함한다(`README.md`, 템플릿 제외).
- **규칙**: 이 `AGENTS.md`, `.agents/skills/`, `90-Templates/`.

작업 규칙:

- **수집(ingest)·갱신** — 위키 페이지를 만들거나 고친 뒤 `python3 .scripts/bin/wiki.py index`로 `wiki-index.md`를 다시 만들고, `python3 .scripts/bin/wiki.py log --op ingest --title "<제목>" --path <파일>`(새 페이지) 또는 `--op update`(기존 페이지 수정)로 기록한다. `wiki-index.md`는 손으로 고치지 않는다.
- **질의(query)** — 먼저 `wiki-index.md`를 읽는다. `graphify-out/graph.json`이 있으면 graphify CLI(`graphify query "<질문>"`, `graphify path "A" "B"`, `graphify explain "X"`, `graphify affected "X"`)로 범위를 좁힌 뒤 해당 페이지를 읽는다. 그래프는 커밋하지 않으므로 새 clone에는 없다. 없으면 `wiki-index.md`와 페이지만으로 답하고 그래프를 쓰지 않았다고 밝힌다. 답을 남길 가치가 있으면 범위 안의 새 페이지로 저장하고 `index`를 다시 실행한 뒤 `log --op query`로 기록한다.
- **점검(lint)** — `python3 .scripts/bin/wiki.py lint`로 깨진 링크·오래된 인덱스·고립 페이지·제목 누락을 확인한다(보고 전용). 수준: `ERROR`(`stale-index`, `broken-link`), `WARNING`(`orphan-page`, `missing-title`, 저장소 밖을 가리키는 `outside-repo`), `INFO`(`01-Papers/pdfs/` 아래 없는 원문 PDF `missing-source` — PDF는 커밋하지 않는다). HTML 주석 안의 링크는 검사하지 않으며, `ERROR`가 하나라도 있을 때만 종료 코드 1이다. `03-Trends/daily/`는 `wiki-index.md`로 접근하는 날짜순 기록이라 고립 페이지 검사에서 제외한다(`ORPHAN_EXEMPT`). 이어서 에이전트가 페이지 사이의 모순·낡은 주장을 직접 검토하고, 결과를 `log --op lint`로 기록한다.
- `wiki-log.md`는 추가만 한다. 기존 항목을 고치거나 지우지 않는다. 로컬 리뷰 브리지가 리뷰를 게시하면 브리지가 직접 `index`와 `log --op ingest`를 실행하므로, 브리지 작업 중인 에이전트는 두 파일을 수정하지 않는다.
- `verify_harness.py`는 `wiki.py index --check`로 인덱스가 최신인지만 검사한다. `lint`는 검증 단계에 포함하지 않는다.
- 위키와 지식 그래프는 MCP 서버로 접근하지 않는다. 로컬 리뷰 브리지의 작업 복사본에는 프로젝트 MCP 설정이 없다. 위키·그래프 기능이 더 필요하면 MCP 서버를 추가하지 말고 저장소 CLI `.scripts/bin/wiki.py`를 확장한다.

## 프로젝트 스킬

아래 16개는 이 저장소 범위의 스킬이다. omp, Claude Code, Codex는 저장소에서 실행할 때 이 프로젝트의 스킬을 발견한다. 다른 저장소에 전역 설치되는 것은 아니다.

| 이름 | 목적 | 정본 경로 |
|---|---|---|
| `paper-search` | 논문 검색·수집과 등록 | `.agents/skills/paper-search/` |
| `daily-digest-loop` | 일일 논문 후보를 채팅으로 제시 | `.agents/skills/daily-digest-loop/` |
| `paper-scheduler` | 날짜별 논문 선정 계획 관리 | `.agents/skills/paper-scheduler/` |
| `paper-summary` | 논문 세 편 요약 | `.agents/skills/paper-summary/` |
| `paper-review` | 원문 3패스 심층 리뷰 | `.agents/skills/paper-review/` |
| `review-index` | 리뷰 인덱스 갱신 | `.agents/skills/review-index/` |
| `keep-list` | 읽기 대기열 관리 | `.agents/skills/keep-list/` |
| `paper-favorites` | 선호 논문 관리 | `.agents/skills/paper-favorites/` |
| `concept-note` | 사용자 확인 개념을 공부노트로 정리 | `.agents/skills/concept-note/` |
| `related-work` | 선행·후속 문헌 추적 | `.agents/skills/related-work/` |
| `paper-relations` | 논문 간 관계를 원문으로 검증 | `.agents/skills/paper-relations/` |
| `graphify` | 지식 그래프 구축·질의·갱신 | `.agents/skills/graphify/` |
| `thought-experiment-critique` | 아이디어의 전제와 반증 조건 점검 | `.agents/skills/thought-experiment-critique/` |
| `critical-validation` | 근거 동결과 독립 3심사 | `.agents/skills/critical-validation/` |
| `thought-experiment-runner` | 승인된 가설의 작은 실험 실행 | `.agents/skills/thought-experiment-runner/` |
| `math-derivation` | 수식의 가정과 유도 단계 설명 | `.agents/skills/math-derivation/` |

## 호스트별 도구 어휘

| 능력 | omp | Claude Code | Codex |
|---|---|---|---|
| 파일 읽기 | `read` | Read | 셸 읽기 |
| PDF 쪽수 | `bash`: `pdfinfo` | Bash: `pdfinfo` | 셸: `pdfinfo` |
| PDF 범위 읽기 (최대 10쪽) | `bash`: `pdftotext -f a -l b -layout <pdf> -` | Read `pages` 또는 Bash `pdftotext` | 셸: `pdftotext` |
| 그림·표 확인 | `pdftoppm -f p -l p -png -r 150 <pdf> /tmp/<slug>-p<p>` 후 `read` | 같은 명령 후 Read | 같은 명령 후 이미지 보기 |
| 웹 검색 / URL | `web_search` / `read <url>` | WebSearch / WebFetch | 웹 검색 도구 |
| 하위 에이전트 | `task`와 `agent:` | Agent | `spawn_agent` / `wait_agent` / `close_agent` |
| 스킬 호출 | `/skill:<name>` 또는 자연어 + `skill://<name>` | `/<name>` | `$<name>` |

omp 팀은 `.omp/agents/`의 `paper-analyst`(정독), `paper-verifier`(독립 검증), `idea-critic`(아이디어 심사), `graph-extractor`(그래프 청크)다. 공유 정의는 모델을 지정하지 않으며 개인 설정이나 부모 세션에서 모델을 정한다. 리뷰 독립 검증은 요청 시 수행한다.

기본 관문인 `critical-validation`은 동일한 근거 묶음 경로·SHA-256·brief를 격리된 방법·재현성·새로움 심사자 셋에게 동시에 전달한다. omp에서는 `task` 한 번에 `agent: idea-critic` 항목 셋을 사용하고 각 항목에 해당 역할과 페르소나만 전달한다. 도구 부재, 깊이 제한, 해시 불일치 또는 심사 실패 시 `심사 대기`로 남기며 순차 역할극으로 대체하지 않는다. graphify 청크는 omp에서 청크당 `agent: graph-extractor` 항목 하나를 사용한다.

## 개인 설정과 로컬 덮어쓰기

개인 설정이 필요하면 `.omp/config.example.yml`을 `.omp/config.yml`로, `.research-harness-agent.example.json`을 `.research-harness-agent.json`으로, `AGENTS.local.example.md`를 `AGENTS.local.md`로 복사해 수정한다. 이 개인 파일은 Git에 커밋하지 않는다. omp에서 `AGENTS.local.md`를 자동으로 읽으려면 개인 설정의 `contextFiles.extra`에 추가한다.

`PROGRESS_BACKEND`와 `CRITICAL_VALIDATION_SETTINGS`는 같은 폴더에 `<이름>.local.md`가 있으면 공유 `<이름>.md` 대신 먼저 읽고, 없으면 공유 설정을 사용한다. 개인 온보딩 선택은 공유 파일이 아닌 로컬 파일에 쓴다. Notion 연동은 유지한다. 개인 `PROGRESS_BACKEND.local.md`에 `notion: disabled`가 있으면 Notion 분기를 실행하거나 제안하지 않으며, 사용자가 Notion 기록을 요청하면 로컬 비활성 상태를 알리고 저장소 정본에 기록한다.

## 파일 명명 규칙

`{연도}-{제1저자성}-{짧은슬러그}` (소문자, 하이픈). PDF는 논문의 주 카테고리 폴더인 `wifi-csi`, `game-ai`, `agent-ai`, `computer-vision`, `other` 중 하나에 저장한다.

```
01-Papers/pdfs/other/2017-vaswani-attention-is-all-you-need.pdf
01-Papers/reviews/{category}/2017-vaswani-attention-is-all-you-need.md
01-Papers/triage/2017-vaswani-attention-is-all-you-need.notes.md
```

## 표준 워크플로

1. **수집** — `paper-search`. 메타데이터 확정 후 `01-Papers/pdfs/{category}/`에 저장.
2. **트리아지** — `90-Templates/paper/triage-template.md`로 1패스. 메모는 `01-Papers/triage/`, 상태는 `01-Papers/index.md`에 남긴다.
3. **심층 리뷰** — `paper-review`. `90-Templates/paper/review-template.md`를 채워 `01-Papers/reviews/{category}/`에 작성한다.
4. **위치 파악** — 필요 시 `related-work`로 선행/후속 연구 맵핑.
5. **인덱스 갱신** — `review-index`로 `01-Papers/index.md` 한 줄 추가.

## 연구 하네스 라우팅

- 현재 단계가 수집·업로드·리뷰·문헌 맥락·아이디어·실험·초안·일일 논문 중 하나로 명시되면 `python3 .scripts/bin/research_workflow.py <stage>`의 다음 스킬을 따른다.
- [Harness-Graph.md](docs/Harness-Graph.md)는 실행 순서를, [Skill-Catalog.md](docs/Skill-Catalog.md)는 보기 전용 목록을 제공한다. 카탈로그로 실행 순서를 결정하지 않는다.
- 논문 리뷰 뒤 재사용할 개념 후보 초안은 `00-Inbox/concept-candidates/`에 둘 수 있지만, `02-Concepts/` 학습 정본은 사용자가 자신의 이해를 확인·수정하고 승격을 명시적으로 요청한 뒤에만 `concept-note`로 반영한다.
- 논문 JSON 또는 승인된 개념/아이디어 정본을 갱신한 뒤 `.scripts/bin/graphify_sync.py begin` → Graphify 스킬 `--update` → `complete` 순서로 동기화한다. CLI AST 갱신만으로 문서 의미 추출이 끝났다고 표시하지 않는다. 실패는 원문 작업 실패가 아니라 재시도 가능한 pending으로 기록한다.
- 아이디어 심사 전 지원·대안·반대 문헌 검색은 필수다. 검색이 부족하면 독립 심사를 시작하지 않는다. 같은 SHA-256 근거 묶음을 세 비판 페르소나에 제공하고 `.scripts/bin/idea_analysis.py validate`로 심사 완결성과 상태 일관성을 검사한다.
- 아이디어는 `critical-validation`의 승인 전 `thought-experiment-runner`로 실행하지 않는다. 초안은 [Argument Auditor](04-Projects/validation/paper-draft-logic-review.md)로 주장–근거 연결을 점검한다.
- 사용자가 대화에 올린 논문은 Keep 목록에 등록한다. 일일 후보는 채팅에만 제시하며 사용자가 채택하기 전에는 PDF·Keep·JSON을 저장하지 않는다.
- 논문 검색과 추천에는 사용자가 제공한 `01-Papers/reference/cs-conferences.csv`를 학술대회 참고 목록으로 활용한다. ARIS를 포함한 모든 검색에서 관련 분야의 학회를 탐색하고 결과의 학회명·유형을 확인할 때 참고한다. 이 목록은 엄격한 허용 목록이 아니며 등급이나 포함 여부만으로 품질·게재 사실을 단정하지 않는다. 사용자가 특정 논문이나 범위를 지정하면 그 요청을 우선한다.
- 매일 논문 후보는 컴퓨터 비전 1편, 멀티모달 1편, 사용자 관심 분야 1편이며 학회 발표·게재가 확인되어야 한다. 반복 실행 시각은 Orca Automation에서 관리한다.
- 일일 후보 검색은 뉴스, 자동 Git commit/push, 후보 보고서 파일 생성을 수행하지 않는다. 후보는 채팅으로만 보고하고, 날짜별 사용자 선정 계획만 `03-Trends/daily/{날짜}-plan.md`에 둔다. 과거 다이제스트의 정본도 `03-Trends/daily/`다.

## 원문 읽기

- PDF는 호스트별 도구 어휘에 따라 한 번에 최대 10쪽씩 읽고, 리뷰에 실제로 읽은 페이지의 `읽은 범위`를 남긴다. 근거 위치에도 실제 읽은 페이지 번호를 적는다. 추출된 텍스트가 비어 있는 스캔 PDF 등은 `needs_input`으로 남기고 완료 처리하지 않는다.
- **긴 논문은 통째로 읽지 말고 구간을 나눠 읽는다.** 본문 → 실험 → 부록 순으로 필요한 만큼만.
- 초록·서론만 읽고 방법 섹션을 추측해 쓰지 않는다. 방법·실험 서술은 반드시 해당 페이지를 실제로 읽은 뒤 쓴다.

## 근거 규칙 (가장 중요)

리뷰의 모든 사실 진술은 원문에 대응하는 근거가 있어야 한다.

- 수치·주장·설정을 인용할 때는 위치를 붙인다: `(§4.2, Table 3)`, `(p.7, Eq. 5)`.
- 원문에 없는 내용을 쓸 때는 반드시 표시한다: `[추론]`, `[내 의견]`, `[확인 필요]`.
- 논문이 명시하지 않은 하이퍼파라미터·데이터 규모·컴퓨트는 "미기재"라고 쓴다. 그럴듯한 값을 채워 넣지 않는다.
- BibTeX는 지어내지 않는다. arXiv/DBLP/Semantic Scholar에서 가져오거나, 못 구하면 비워 두고 `[확인 필요]`로 남긴다.
- 확신이 서지 않으면 확신하는 척하지 말고 불확실성을 그대로 적는다.

## 서술 규칙

- 본문은 한국어. 전문 용어는 첫 등장 시 `어텐션(attention)` 형태로 병기하고 이후에는 통일된 한 표기만 쓴다.
- 논문 제목, 모델·데이터셋·지표 이름, 저자명은 원어 그대로 (`Transformer`, `WMT14 En-De`, `BLEU`).
- 수식은 LaTeX 인라인(`$...$`) / 블록(`$$...$$`).
- 요약체로 쓴다. "~라고 볼 수 있을 것 같다" 같은 완충어 대신 "~다 / ~로 보인다 / 근거 없음"으로 단정하거나 불확실을 명시한다.
- 논문에 대한 비판은 구체적으로. "실험이 부족하다"가 아니라 "베이스라인 X가 빠져 있어 주장 Y를 검증할 수 없다".

## 리뷰 품질 기준

리뷰를 끝내기 전에 다음을 확인한다.

- [ ] 논문의 **핵심 주장**과 그것을 뒷받침하는 **구체적 증거**가 표로 대응되어 있는가
- [ ] 방법 설명이 논문을 안 본 사람도 재구현 방향을 잡을 만큼 구체적인가 (입력/출력 형태, 손실 함수, 학습 절차)
- [ ] 실험 설정(데이터셋, 베이스라인, 지표, 컴퓨트)이 빠짐없이 적혔는가 — 미기재는 미기재로
- [ ] 저자가 **주장하지 않은 것**과 결과가 **보여주지 못하는 것**을 구분해 적었는가
- [ ] 한계 섹션이 저자의 자기 고백을 옮긴 게 아니라 내가 찾아낸 문제를 담고 있는가
- [ ] 모든 수치에 출처 위치가 붙어 있는가

## 하지 말 것

- 논문 전문을 리뷰 파일에 복붙하지 않는다. 리뷰는 원문의 압축·재구성·비판이지 사본이 아니다.
- `01-Papers/pdfs/`의 PDF를 수정하지 않는다.
- 저자 홍보 문구를 그대로 옮기지 않는다 (`SOTA를 크게 뛰어넘는 혁신적인` → 실제 수치와 비교 대상으로 환원).
- 검색 결과 요약만으로 리뷰를 쓰지 않는다. 원문 PDF를 읽지 못했으면 그 사실을 리뷰 최상단에 명시한다.

## graphify

지식 그래프 질의 도구는 graphify CLI이며 `graphify-out/graph.json`을 읽는다. `graphify-out/`은 Git에 커밋하지 않으므로 새 clone에는 그래프가 없다. 먼저 graphify 스킬로 그래프를 구축한다(문서 의미 추출에 모델 호출 비용이 든다). 이후 정본 변경은 `.scripts/bin/graphify_sync.py`로 동기화를 추적한다.

When the user invokes the graphify skill (`/graphify` in Claude Code, `$graphify` in Codex, `/skill:graphify` in omp), use the installed graphify skill or instructions before doing anything else.

Rules:
- If `graphify-out/graph.json` exists, first run `graphify query "<question>"`. Use `graphify path "<A>" "<B>"` for relationships, `graphify explain "<concept>"` for focused concepts, and `graphify affected "<node>"` for what depends on a node. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If `graphify-out/graph.json` does not exist, do not claim graph results: fall back to `wiki-index.md` and the pages, say that no graph was used, and offer to build it with the graphify skill.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost). It does not replace semantic extraction for papers, concepts, or ideas.
- Graph access goes through the graphify CLI, not an MCP server. Extend `.scripts/bin/wiki.py` rather than adding a wiki/graph MCP server.
