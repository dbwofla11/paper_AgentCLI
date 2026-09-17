# 논문 리뷰·공부 작업 공간

AI/ML/CS 논문을 찾고, 정독하고, 한국어 심층 리뷰로 남기기 위한 Claude Code 환경.

처음에는 [Home.md](Home.md)에서 시작한다. 원문·리뷰 관리는 `01-Papers/`, **내가 공부해서 이해한 내용**은 `02-Concepts/`, 실제 실험·구현은 `04-Projects/`, 검증 전 가설은 `05-ideas/`에 둔다. Keep과 즐겨찾기는 `01-Papers/library/`에 유지한다.

## 빠른 시작

```
/paper-search      transformer 효율화 관련 최근 논문 찾아줘
/paper-review      1706.03762
/related-work      1706.03762
/paper-relations   저장소 논문들의 관계를 Graphify로 맵핑해줘
/review-index      정리해줘
/paper-scheduler   2026-09-05 논문을 게임 AI 1편과 컴퓨터 비전 2편으로 예약해줘
/math-derivation   Eq. 5의 softmax 그래디언트가 왜 저렇게 되는지 유도해줘
```

또는 그냥 자연어로 요청해도 된다 — 해당 스킬이 자동으로 걸린다.

## 구성

```
CLAUDE.md              에이전트 규칙 (근거 규칙, 서술 규칙, 품질 기준)
.claude/settings.json  논문 사이트 WebFetch·스크립트 실행 허용목록
.claude/skills/        paper-search · paper-review · related-work · review-index · math-derivation
90-Templates/paper/    review-template.md (심층) · triage-template.md (1차 판정)
.scripts/bin/paper.py  arXiv / Semantic Scholar / OpenAlex CLI (stdlib만, 설치 불필요)
.scripts/docs/search-protocol.md  논문 탐색 프로토콜
.mcp.json               연결된 MCP 서버: exa, arxiv-mcp, paper-search-mcp
01-Papers/pdfs/        원문 PDF
01-Papers/reviews/     카테고리별 최종 리뷰 (논문 1편 = 파일 1개)
01-Papers/triage/      논문별 트리아지·조사 메모
01-Papers/library/     전체 인덱스 · Keep · 즐겨찾기
03-Trends/daily/       일일 트렌드 다이제스트·예약 계획
05-ideas/thought-experiments/  연구 아이디어 메모
```

## 학습·연구 하네스

```
Home.md                전체 대시보드 / MOC
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

기존 문서는 새 하네스 안으로 이사했다. 루트의 `papers/`, `reviews/`, `notes/`, `library/`, `templates/`, `scripts/`, `docs/`는 과거 링크와 자동화를 유지하기 위한 호환 링크다.

## 논문 관계 그래프

Graphify를 프로젝트에 설치해 `01-Papers/pdfs/**/*.pdf` 사이의 인용·공유 방법·공유 데이터·개념적 유사성 후보를 질의할 수 있다. 관계 분석은 `$paper-relations` 스킬을 사용하며, 그래프의 `EXTRACTED`·`INFERRED`·`AMBIGUOUS` 표시를 원문 PDF와 대조해 기록한다.

```bash
uv tool install 'graphifyy[pdf]'
graphify install --project --platform codex
```

Graphify의 프로젝트 설정은 `.codex/skills/graphify/`와 `AGENTS.md`에 기록된다. 그래프를 만들거나 갱신할 때는 논문 PDF 폴더만 대상으로 하며, 관계가 원문에서 확인되지 않으면 `[확인 필요]`로 표시한다.

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

매일 다이제스트는 `03-Trends/daily/{YYYY-MM-DD}.md`에 저장하며, [`03-Trends/daily/2026-09-07.md`](03-Trends/daily/2026-09-07.md) 양식을 따른다.

미래 회차의 논문 주제는 `$paper-scheduler`로 예약한다. 예약 내용은 `03-Trends/daily/{YYYY-MM-DD}-plan.md`에 저장한다.

## 설계 원칙

- **원문 근거 없는 서술 금지.** 모든 수치에 `(§4.2, Table 3)` 형태의 위치를 붙이고, 추론은 `[추론]`/`[내 의견]`/`[확인 필요]`로 표시한다.
- **PDF를 실제로 읽는다.** 초록만 보고 방법 섹션을 쓰지 않는다. Read 도구의 `pages` 인자로 구간을 나눠 읽는다.
- **리뷰의 값어치는 3패스에 있다.** 요약이 아니라 주장–증거 대응, 빠진 베이스라인, 혼동 요인, 일반화 조건을 판정하는 부분.
- **BibTeX와 메타데이터는 지어내지 않는다.** 서버에서 받아오거나 비워 둔다.
