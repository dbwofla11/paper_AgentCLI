# 논문 리뷰 작업 공간

AI/ML/CS 논문을 찾고, 정독하고, 한국어 심층 리뷰로 남기기 위한 Claude Code 환경.

## 빠른 시작

```
/paper-search      transformer 효율화 관련 최근 논문 찾아줘
/paper-review      1706.03762
/related-work      1706.03762
/review-index      정리해줘
/math-derivation   Eq. 5의 softmax 그래디언트가 왜 저렇게 되는지 유도해줘
```

또는 그냥 자연어로 요청해도 된다 — 해당 스킬이 자동으로 걸린다.

## 구성

```
CLAUDE.md              에이전트 규칙 (근거 규칙, 서술 규칙, 품질 기준)
.claude/settings.json  논문 사이트 WebFetch·스크립트 실행 허용목록
.claude/skills/        paper-search · paper-review · related-work · review-index · math-derivation
templates/             review-template.md (심층) · triage-template.md (1차 판정)
scripts/paper.py       arXiv / Semantic Scholar / OpenAlex CLI (stdlib만, 설치 불필요)
docs/search-protocol.md  논문 탐색 프로토콜 (질의 분해·소스 우선순위·스노우볼링·실패 처리·MCP 목록)
.mcp.json               연결된 MCP 서버: exa, arxiv-mcp, paper-search-mcp
papers/                원문 PDF
reviews/               최종 리뷰 (논문 1편 = 파일 1개)
notes/                 작업 메모, 관련 연구 맵, notes/trends/ 일일 트렌드 다이제스트(자동)
library/index.md       전체 논문 인덱스
```

## scripts/paper.py

```bash
python scripts/paper.py search "query" --source s2|arxiv|openalex --limit 10
python scripts/paper.py meta  1706.03762          # 메타데이터 + 실제 BibTeX
python scripts/paper.py pdf   1706.03762          # papers/ 로 다운로드
python scripts/paper.py refs  1706.03762          # 인용한 문헌
python scripts/paper.py cites 1706.03762          # 인용된 문헌
```

`--json` 플래그로 원시 JSON 출력. Semantic Scholar는 API 키 없이 쓰면 429(rate limit)가 잦다 — 자동 재시도 후 arXiv/Crossref로 폴백한다. [무료 키](https://www.semanticscholar.org/product/api)를 발급받았다면:

```powershell
$env:S2_API_KEY = "..."
```

## MCP 서버

`.mcp.json`에 3개 연결됨 (세션 재시작 후 신뢰 승인 프롬프트가 한 번 뜬다). 자세한 배경과 각 서버를 고른/뺀 이유는 [docs/search-protocol.md §7](docs/search-protocol.md#7-연결된-mcp-서버) 참고.

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

매일 오전 9시(KST) 클라우드 에이전트가 자동으로 돌아 AI/ML/CS 기술 트렌드와 컴퓨터 비전 연구 동향 중 가장 중요한 것만 골라 요약하고, 이 저장소의 `notes/trends/{YYYY-MM-DD}.md`에 커밋한다 — 논문 3편 + 시사이슈 3편 구성. [claude.ai/code/routines](https://claude.ai/code/routines)에서 상태를 확인·일시정지할 수 있다.

## 설계 원칙

- **원문 근거 없는 서술 금지.** 모든 수치에 `(§4.2, Table 3)` 형태의 위치를 붙이고, 추론은 `[추론]`/`[내 의견]`/`[확인 필요]`로 표시한다.
- **PDF를 실제로 읽는다.** 초록만 보고 방법 섹션을 쓰지 않는다. Read 도구의 `pages` 인자로 구간을 나눠 읽는다.
- **리뷰의 값어치는 3패스에 있다.** 요약이 아니라 주장–증거 대응, 빠진 베이스라인, 혼동 요인, 일반화 조건을 판정하는 부분.
- **BibTeX와 메타데이터는 지어내지 않는다.** 서버에서 받아오거나 비워 둔다.
