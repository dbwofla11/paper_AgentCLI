# 논문 탐색 프로토콜 (Paper Search Protocol)

`/paper-search`가 따르는 상세 절차. 스킬 파일(`.claude/skills/paper-search/SKILL.md`)은 이 문서를 요약한 실행 가이드고, 여기가 근거·판정 기준의 원본이다.

## 0. 목적

사용자가 던진 주제·질문을 논문 목록으로 바꾸는 과정에서 **누락(못 찾음)**과 **오염(엉뚱한 논문을 관련 있다고 제시)**을 최소화한다. 결과 표를 빨리 만드는 것보다 "무엇을 못 찾았는가"를 정직하게 보고하는 것이 우선이다.

## 1. 질의 설계

토픽 하나를 그대로 검색하지 않는다. 아래로 분해한다.

| 구분 | 예시 (주제: "긴 문맥 처리 효율화") |
|---|---|
| 핵심 방법 용어 | `long-context`, `attention approximation`, `KV cache compression` |
| 태스크·도메인 용어 | `language modeling`, `retrieval-augmented generation` |
| 동의어·이전 세대 용어 | `efficient transformer`, `sparse attention`, `linear attention` |
| 제외할 인접 주제 | (있다면) `long-context`가 아닌 `long-form generation`처럼 헷갈리는 인접어를 명시해 결과에서 걸러낸다 |

- 질의는 **영어**로 만든다. 분야 용어가 몇 년 단위로 바뀌므로 한 표현만 쓰면 놓친다 (예: `efficient transformer` 2020 → `linear attention` 2021 → `state space model` 2023).
- 사용자가 준 토픽이 모호하면 검색을 시작하기 전에 분해한 질의 셋을 한 번 보여주고 방향이 맞는지 확인한다. 이미 구체적인 요청이면 바로 진행한다.

## 2. 소스와 역할 분담

| 소스 | 강점 | 약점 | 명령 |
|---|---|---|---|
| Semantic Scholar (S2) | 인용수, 폭넓은 커버리지(학술지·컨퍼런스 포함), refs/cites 그래프 | 무키 호출 시 rate limit(429) 잦음 | `paper.py search --source s2` |
| arXiv | 최신 프리프린트, 안정적, PDF 자동 다운로드 지원 | arXiv에 올라온 것만 (저널 전용·구간행사 논문 누락) | `paper.py search --source arxiv` |
| OpenAlex | 가장 넓은 커버리지(저널·구권 포함), rate limit 거의 없음 | 초록 미제공(API 자체가 inverted index로 줌), 관련도 랭킹이 S2보다 약함 | `paper.py search --source openalex` |
| WebSearch + WebFetch | 위 API가 다 놓친 것 보완, venue 전용 페이지 확인 | 구조화 안 됨, 수동 판단 필요 | 허용 도메인은 `.claude/settings.json` |

**우선순위**: 인용망 확장이 필요하면 S2, 최신 프리프린트 위주면 arXiv, 커버리지를 최대로 넓히려면 OpenAlex. 하나만 돌리고 끝내지 않는다 — **최소 2개 소스**를 항상 돌린다.

## 3. 실행 순서

1. **1차 광역 검색** — 질의 셋 각각을 S2로 돌린다. S2가 rate limit(429)에 걸리면 같은 질의를 arXiv와 OpenAlex로 재시도한다 (수동 폴백; `paper.py meta`/`refs`/`cites`는 자동 폴백이 있지만 `search`는 아직 없다 — 아래 "알려진 한계" 참고).
2. **스노우볼링(snowballing)** — 1차 검색에서 명백히 핵심인 논문(앵커) 1~3편을 고른다. 각각에 대해:
   - **후방(backward)**: `paper.py refs <id>` — 이 논문이 딛고 선 것
   - **전방(forward)**: `paper.py cites <id>` — 이 논문을 확장·반박한 것
   
   키워드 검색이 놓치는 논문(용어가 달라졌거나 인용만 되고 초록에 핵심어가 없는 경우)은 대개 여기서 잡힌다.
3. **포화 판정** — 새 질의·새 앵커를 돌렸는데 이미 나온 논문만 반복되면 그 방향은 종료한다. 계속 새 논문이 나오면 1~2단계를 반복한다. 무한정 넓히지 않는다 — 통상 앵커 2~3편, 소스 2~3개면 충분히 포화한다.
4. **중복 제거 및 존재 확인** — 같은 논문이 arXiv/S2/OpenAlex에서 각각 다른 ID로 나올 수 있다. arXiv ID 또는 DOI 기준으로 합친다. **API가 실제로 반환한 논문만** 남긴다. 기억으로 논문을 채워 넣지 않는다.
5. **관련도 필터링** — 초록을 훑어 주제와 무관한 것은 뺀다. 뺀 것은 개수만이라도 언급한다 ("검색 결과 34건 중 관련 12건").
6. **결과 제시** — `paper-search` 스킬의 표 형식(제목/저자/venue·연도/인용수/arXiv ID/한 줄 요지/관련 이유)으로 정렬해 보여준다.

## 4. 실패 처리

| 상황 | 조치 |
|---|---|
| S2 429 (rate limit) | 몇 초 대기 후 재시도 1회 → 안 되면 arXiv/OpenAlex로 전환. 사용자에게 소스를 바꿨다고 알린다. |
| PDF 페이월 | 다운로드 시도하지 않는다. 우회하지 않는다. 사용자에게 링크만 제공하고 수동 확보를 요청한다. |
| 검색 결과 0건 또는 빈약 | 질의가 너무 좁거나 용어가 틀렸을 가능성을 먼저 의심한다. 동의어·상위 개념어로 재시도. 그래도 빈약하면 "이 방향으로는 결과가 부족하다"고 정직하게 보고한다. |
| 존재를 확인할 수 없는 논문 | 목록에서 뺀다. "~라는 논문이 있을 것이다" 식으로 채워 넣지 않는다. |

## 5. 결과 보고 시 반드시 포함할 것

- 실제로 돌린 질의 목록과 사용한 소스
- 스노우볼링에 쓴 앵커 논문
- 커버리지가 약하다고 판단되는 지점 (예: "2024년 이후 논문은 못 찾음", "중국어권 venue는 검색 범위 밖")
- 관련도 기준으로 뺀 결과가 있다면 대략적인 개수

## 6. 알려진 한계 (2026-08-13 기준)

- `scripts/paper.py search`는 소스 전환을 사용자/에이전트가 수동으로 해야 한다. `meta`/`refs`/`cites`처럼 자동 폴백을 넣는 개선이 남아 있다.
- OpenAlex 검색 결과는 초록이 비어 있다 (inverted index 복원 미구현).
- 키워드/API 검색이라 의미 기반(semantic) 검색이 아니다 — 질의 분해(§1)로 보완한다. 의미 검색이 필요하면 §7의 MCP 옵션을 검토한다.

## 7. 연결된 MCP 서버

`.mcp.json`(프로젝트 루트)에 등록됨. 세션을 재시작하면 Claude Code가 신뢰 여부를 묻는 프롬프트를 띄운다 — 처음 한 번은 승인해야 한다.

| 서버 | 상태 | 용도 | 비고 |
|---|---|---|---|
| **exa** ([Exa MCP](https://exa.ai/docs/reference/exa-mcp), `research_paper_search`) | 연결됨, **API 키 필요** | 키워드가 아니라 **의미 기반**으로 1억 건 이상 논문 전문 검색 — §6의 키워드 검색 한계를 직접 해결 | 원격 HTTP 서버라 로컬 런타임 불필요. [dashboard.exa.ai/api-keys](https://dashboard.exa.ai/api-keys)에서 키 발급 후 `EXA_API_KEY` 환경변수로 설정해야 실제로 작동한다. 설정 전까지는 인증 실패로 도구 목록만 뜨고 호출이 막힌다. |
| **arxiv-mcp** ([blazickjp/arxiv-mcp-server](https://github.com/blazickjp/arxiv-mcp-server), PyPI) | 연결됨, 동작 확인 | 논문 전문을 섹션 단위로 가져오거나 연구 알림 유지 | `uvx`로 실행, 다운로드 캐시는 `.claude/mcp-cache/arxiv/`에 격리(우리 `papers/` 명명 규칙과 안 섞이게). 실제로 채택할 PDF는 여전히 `paper.py pdf`로 `papers/`에 정식 저장한다. |
| **paper-search-mcp** ([openags/paper-search-mcp](https://github.com/openags/paper-search-mcp), PyPI) | 연결됨, 동작 확인 | arXiv 외 PubMed·bioRxiv·Google Scholar·CORE·DOAJ·IEEE·ACM까지 한 번에 — AI/ML을 넘어서는 인접 분야 검색 시 유용 | `uvx`로 실행. CORE/DOAJ/Unpaywall 키는 선택 사항(없으면 경고만 뜨고 낮은 레이트리밋으로 동작) — 필요하면 `.mcp.json`의 `env`에 `PAPER_SEARCH_MCP_*` 변수 추가. |

**Semantic Scholar MCP는 연결하지 않았다.** PyPI의 `semantic-scholar-mcp` 패키지를 실행 검증했더니 `ModuleNotFoundError: mcp.server.fastmcp`로 즉시 죽는다 — 패키지 자체가 깨져 있음. 대안 구현(`JackKuo666/semanticscholar-MCP-Server`)은 git clone + Windows 절대경로 수동 설정이 필요해 번거롭고, `scripts/paper.py`가 이미 S2의 검색/메타데이터/인용망을 다 커버하므로 이득이 적다. 나중에 고쳐지면 재검토.

**uv/uvx는 이 세팅 과정에서 `pip install uv`로 로컬에 설치했다.** Node.js는 설치하지 않았다 — Exa를 npm 패키지(`npx exa-mcp-server`) 대신 공식 원격 HTTP 엔드포인트로 붙여서 필요 없게 만들었다.
