# 논문 리뷰 에이전트

AI / ML / CS 논문을 **개별 심층 리뷰**하는 작업 공간이다. 산출물은 한국어로 쓰되 전문 용어와 논문 제목은 원어를 병기한다.

## 디렉터리

| 경로 | 용도 |
|---|---|
| `01-Papers/pdfs/{category}/` | 카테고리별 원문 PDF |
| `01-Papers/reviews/{category}/` | 카테고리별 최종 심층 리뷰 노트 (논문 1편 = 파일 1개) |
| `01-Papers/triage/` | 논문별 1차 판정·조사 메모 |
| `01-Papers/library/index.md` | 읽은/읽을 논문 인덱스 (한 줄 = 한 편) |
| `01-Papers/library/keep.md` | 나중에 읽거나 조사할 대기열 |
| `01-Papers/library/favorites.md` | 선호 논문 기록 |
| `02-Concepts/` | 사용자가 공부해 이해한 내용을 쌓는 공부노트 |
| `03-Trends/daily/` | 날짜별 다이제스트 |
| `05-ideas/thought-experiments/` | 연구 아이디어·사고실험 |
| `90-Templates/paper/` | 리뷰·트리아지 템플릿 |
| `.scripts/bin/paper.py` | arXiv / Semantic Scholar / OpenAlex 조회 CLI (stdlib만 사용) |
| `.mcp.json` | 연결된 MCP 서버 — `exa`(의미 검색, API 키 필요), `arxiv-mcp`, `paper-search-mcp` |

## 새 세션 시작 (필수)

이 저장소를 새로 복제했거나 새 Codex 세션에서 첫 사용자 요청을 받으면, 요청을 처리하기 전에 저장소 루트에서 다음 점검을 실행한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\.scripts\setup.ps1
```

- 성공하면 사용자 요청을 계속 처리한다. 사용자에게 README를 읽거나 수동 점검을 실행하라고 요구하지 않는다.
- 실패하면 출력의 `FAIL` 항목과 필요한 설치 명령만 간단히 보고한다. 해당 도구가 필수인 작업은 보류하되, 가능한 범위의 작업은 계속한다.
- 이 스크립트는 멱등(idempotent)이며 정해진 작업 디렉터리 생성과 환경 검증만 한다. 패키지 설치, API 키 저장, 기존 연구 자료 수정·삭제는 하지 않는다.
- `README.md`는 사람을 위한 clone·사용 안내다. 사용자가 요청했거나 사람이 읽을 안내가 필요할 때만 참조한다.

## 학습·연구 하네스

`Home.md`는 전체 MOC다. `00-Inbox/`, `01-Papers/`, `02-Concepts/`, `03-Trends/`, `04-Projects/`, `05-ideas/`, `90-Templates/`, `99-Attachments/`, `.scripts/`는 탐색과 운영을 위한 레이어다.

- `02-Concepts/`는 논문 한 편의 요약이 아니라 사용자가 공부해 이해한 내용을 축적하는 공부노트다.
- `04-Projects/`는 실행할 실험·구현·스터디를, `05-ideas/`는 검증 전 가설과 반증 조건을 다룬다.
- 원문 PDF·심층 리뷰·일일 트렌드·사고실험·자동화의 정본은 각각 `01-Papers/pdfs/`, `01-Papers/reviews/`, `03-Trends/daily/`, `05-ideas/thought-experiments/`, `.scripts/bin/`이다.
- `01-Papers/library/keep.md`(읽기/조사 대기열)와 `01-Papers/library/favorites.md`(선호 논문)는 독립 목록으로 유지한다.
- 루트의 기존 `papers/`, `reviews/`, `library/`, `notes/`, `templates/`, `scripts/`, `docs/`는 과거 링크와 자동화를 위한 호환 링크다. 새 파일은 여기에 쓰지 않는다.

## 파일 명명 규칙

`{연도}-{제1저자성}-{짧은슬러그}` (소문자, 하이픈). PDF는 논문의 주 카테고리 폴더인 `wifi-csi`, `game-ai`, `agent-ai`, `computer-vision`, `other` 중 하나에 저장한다.

```
01-Papers/pdfs/other/2017-vaswani-attention-is-all-you-need.pdf
01-Papers/reviews/{category}/2017-vaswani-attention-is-all-you-need.md
01-Papers/triage/2017-vaswani-attention-is-all-you-need.notes.md
```

## 표준 워크플로

1. **수집** — `/paper-search`. 메타데이터 확정 후 `01-Papers/pdfs/{category}/`에 저장.
2. **트리아지** — `90-Templates/paper/triage-template.md`로 1패스. 메모는 `01-Papers/triage/`, 상태는 `01-Papers/library/index.md`에 남긴다.
3. **심층 리뷰** — `/paper-review`. `90-Templates/paper/review-template.md`를 채워 `01-Papers/reviews/{category}/`에 작성한다.
4. **위치 파악** — 필요 시 `/related-work`로 선행/후속 연구 맵핑.
5. **인덱스 갱신** — `/review-index`로 `01-Papers/library/index.md` 한 줄 추가.

## 원문 읽기

- PDF는 Read 도구의 `pages` 인자로 직접 읽는다 (`pages: "1-10"`, 요청당 최대 20쪽). 외부 변환 도구 불필요.
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

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, use the installed graphify skill or instructions before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
