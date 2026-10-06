# 논문 리뷰·공부 작업 공간

AI/ML/CS 논문을 찾고, 정독하고, 한국어 심층 리뷰로 남기기 위한 Codex / Claude Code 작업 공간.

처음에는 [Home.md](docs/Home.md)에서 시작한다. 원문·리뷰 관리는 `01-Papers/`, **내가 공부해서 이해한 내용**은 `02-Concepts/`, 실제 실험·구현은 `04-Projects/`, 검증 전 가설은 `05-ideas/`에 둔다. 인덱스·Keep·즐겨찾기는 `01-Papers/` 바로 아래에, 논문 JSON은 `01-Papers/library/`에 둔다. [논문 JSON 시각화](100-views/paper-library.html)에서 레코드를 탐색할 수 있다.

연구 단계별 다음 실행 스킬은 [Harness-Graph.md](docs/Harness-Graph.md)에서 확인한다. [Skill-Catalog.md](docs/Skill-Catalog.md)는 보기 전용이다.

HTML 화면과 공통 디자인 자산은 [100-views/](100-views/README.md)에서 관리한다.

## 빠른 시작

처음 설치한다면 **[노트북 온보딩 안내](docs/onboarding.md)**를 따라 Git·Python·에이전트 설치 → 로그인 → 저장소 받기 → 진단 → 첫 요청을 진행한다. 다른 프로젝트로 스킬을 옮기려면 [설치기 안내](docs/research-harness-installer.md)를 사용한다.

저장소 루트의 터미널에서:

```bash
python3 -B .scripts/bin/onboarding_check.py --host codex
python3 -B .scripts/bin/verify_harness.py
codex
```

Claude를 사용하면 `--host claude`와 `claude`로 바꾼다. 다음 요청은 **에이전트 채팅 입력란**에 넣는다. Codex는 `$paper-search`처럼 스킬을 지정하거나 자연어로 요청한다. 아래 `/스킬` 예시는 Claude Code 기준이다.

```
/paper-search      transformer 효율화 관련 최근 논문 찾아줘
/paper-review      1706.03762
/related-work      1706.03762
/paper-relations   저장소 논문들의 관계를 Graphify로 맵핑해줘
/review-index      정리해줘
/concept-note      이 논문의 핵심 개념을 공부노트로 정리해줘
/paper-scheduler   2026-09-05 논문을 게임 AI 1편과 컴퓨터 비전 2편으로 예약해줘
/math-derivation   Eq. 5의 softmax 그래디언트가 왜 저렇게 되는지 유도해줘
```

또는 그냥 자연어로 요청해도 된다 — 해당 스킬이 자동으로 걸린다.

## 구성

```
AGENTS.md              공통 에이전트 작업 규칙의 정본
CLAUDE.md              AGENTS.md를 포함하는 Claude Code 진입점 + Claude 전용 설정 안내
docs/Home.md           사람이 보는 시작 페이지 / MOC
docs/Harness-Graph.md  연구 하네스 실행 순서
docs/Skill-Catalog.md  스킬 보기 전용 목록
.claude/settings.json  논문 사이트 WebFetch·스크립트 실행 허용목록
.agents/skills/        모든 공통 스킬의 유일한 정본
.claude/skills/        공통 스킬 링크 + Claude 전용 math-derivation
.codex/skills/graphify Graphify 정본을 가리키는 호환 링크
90-Templates/paper/    review-template.md (심층) · triage-template.md (1차 판정)
.scripts/bin/paper.py  arXiv / Semantic Scholar / OpenAlex CLI (stdlib만, 설치 불필요)
.scripts/docs/search-protocol.md  논문 탐색 프로토콜
.mcp.json               연결된 MCP 서버: exa, arxiv-mcp, paper-search-mcp
01-Papers/pdfs/        원문 PDF
01-Papers/reviews/     카테고리별 최종 리뷰 (논문 1편 = 파일 1개)
01-Papers/triage/      논문별 트리아지·조사 메모
01-Papers/             전체 인덱스 · Keep · 즐겨찾기
01-Papers/library/     논문별 JSON 레코드
03-Trends/daily/       일일 트렌드 다이제스트·예약 계획
05-ideas/thought-experiments/  연구 아이디어 메모
```

## 학습·연구 하네스

```
docs/                  사람용 시작 페이지·하네스 그래프·스킬 카탈로그
00-Inbox/              분류 전 빠른 캡처
01-Papers/             papers·reviews·library로 가는 논문 리딩 관문
02-Concepts/           내 공부노트 (논문 간 개념 종합)
03-Trends/             날짜별 트렌드와 daily/ 다이제스트
04-Projects/           실험·구현·스터디 실행 단위
05-ideas/              thought-experiments/를 포함한 연구 아이디어
90-Templates/          공부노트 등 추가 양식
99-Attachments/        그림·실험 산출물 등 비원문 첨부
.scripts/              자동화 실행 코드와 탐색 프로토콜
```

연구 순서는 [Harness-Graph.md](docs/Harness-Graph.md), 스킬 탐색은 [Skill-Catalog.md](docs/Skill-Catalog.md), 공통 에이전트 규칙은 [AGENTS.md](AGENTS.md)가 정본이다. [Home.md](docs/Home.md)는 폴더와 작업 진입점을 안내하는 MOC이며 같은 규칙을 복제하지 않는다. 루트의 `papers/`, `reviews/`, `notes/`, `library/`, `templates/`, `scripts/`는 과거 링크와 자동화를 유지하기 위한 호환 링크다.

리뷰 뒤에는 개념 후보만 `00-Inbox/concept-candidates/`에 초안으로 생길 수 있다. 사용자의 이해 확인·승격 요청 전에는 `02-Concepts/` 학습 정본이 되지 않는다. 아이디어 검증은 필수 문헌 검색, 해시로 동결한 동일 근거 묶음, 독립 3인 심사 순으로 진행하며 상세는 [04-Projects](04-Projects/README.md)를 따른다.

## 논문 관계 그래프

Graphify를 프로젝트에 설치해 `01-Papers/pdfs/**/*.pdf` 사이의 인용·공유 방법·공유 데이터·개념적 유사성 후보를 질의할 수 있다. 관계 분석은 `$paper-relations` 스킬을 사용하며, 그래프의 `EXTRACTED`·`INFERRED`·`AMBIGUOUS` 표시를 원문 PDF와 대조해 기록한다.

```bash
uv tool install 'graphifyy[pdf]'
graphify install --project --platform agents
```

Graphify 스킬의 정본은 `.agents/skills/graphify/`다. `.claude/skills/graphify/`와 `.codex/skills/graphify/`는 같은 정본을 가리키는 호환 링크이며, 복사본을 두지 않는다. Graphify 규칙은 `AGENTS.md`에 둔다. 논문 관계는 원문에서 확인되지 않으면 `[확인 필요]`로 표시한다.

## .scripts/bin/paper.py

```bash
python .scripts/bin/paper.py search "query" --source s2|arxiv|openalex --limit 10
python .scripts/bin/paper.py meta  1706.03762
python .scripts/bin/paper.py pdf   1706.03762 --out 01-Papers/pdfs/other
python .scripts/bin/paper.py refs  1706.03762
python .scripts/bin/paper.py cites 1706.03762
```

`--json` 플래그로 원시 JSON 출력. Semantic Scholar는 API 키 없이 쓰면 429(rate limit)가 잦다 — 자동 재시도 후 arXiv/Crossref로 폴백한다. [무료 키](https://www.semanticscholar.org/product/api)를 발급받았다면:

```powershell
$env:S2_API_KEY = "..."
```

## MCP 서버

`.mcp.json`에 3개 연결됨. 자세한 배경은 [.scripts/docs/search-protocol.md](.scripts/docs/search-protocol.md) 참고.

| 서버 | 하는 일 | 설정 필요 |
|---|---|---|
| `exa` | 의미 기반 논문 전문 검색 | **필수** — [dashboard.exa.ai/api-keys](https://dashboard.exa.ai/api-keys)에서 키 발급 후 `EXA_API_KEY` 환경변수 설정 |
| `arxiv-mcp` | arXiv 전문 섹션 조회, 연구 알림 | 없음 (`uvx`로 즉시 동작) |
| `paper-search-mcp` | arXiv/PubMed/bioRxiv/Google Scholar 등 통합 검색 | 없음 (선택적으로 CORE/DOAJ 키 추가 가능) |

```powershell
# EXA_API_KEY를 영구적으로 쓰려면 사용자 환경변수로 등록
setx EXA_API_KEY "your_api_key"
```

## 자동화 루틴

매일 09:00 KST 예약은 Orca Automation이 `$daily-digest-loop`를 실행해 CV 1편·멀티모달 1편·관심 분야 1편을 채팅으로 제시한다. 후보는 채택되기 전까지 저장하지 않는다. 뉴스·자동 commit/push는 이 흐름에 포함하지 않는다.

날짜별 논문 주제 계획은 `$paper-scheduler`로 예약하고 `03-Trends/daily/{YYYY-MM-DD}-plan.md`에 저장한다. 과거 다이제스트 파일은 기록으로 보존한다.

## 설계 원칙

- **원문 근거 없는 서술 금지.** 모든 수치에 `(§4.2, Table 3)` 형태의 위치를 붙이고, 추론은 `[추론]`/`[내 의견]`/`[확인 필요]`로 표시한다.
- **PDF를 실제로 읽는다.** 초록만 보고 방법 섹션을 쓰지 않는다. Read 도구의 `pages` 인자로 구간을 나눠 읽는다.
- **리뷰의 값어치는 3패스에 있다.** 요약이 아니라 주장–증거 대응, 빠진 베이스라인, 혼동 요인, 일반화 조건을 판정하는 부분.
- **BibTeX와 메타데이터는 지어내지 않는다.** 서버에서 받아오거나 비워 둔다.
