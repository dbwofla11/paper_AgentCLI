# 논문 리뷰·연구 하네스 (Paper Review & Research Harness)

AI/ML/CS 논문을 찾고, 원문 근거에 따라 정독하고, 한국어 심층 리뷰와 연구 노트로 축적하는 **Codex 작업 공간**이다. 논문 제목·모델·데이터셋 이름은 원어를 유지하고, 본문은 한국어로 작성한다.

처음에는 [Home.md](Home.md)에서 시작한다. 이 문서는 작업의 출발점과 환경 설정만 다룬다.

## 3분 시작

Windows에서 저장소를 내려받고 Codex에서 루트 폴더를 연다.

```powershell
git clone https://github.com/dbwofla11/paper_AgentCLI.git
cd paper_AgentCLI
codex
```

그다음 논문 탐색처럼 원하는 첫 요청을 바로 입력한다. 새 Codex 세션은 작업에 앞서 자동으로 `.scripts/setup.ps1`을 실행해 폴더·Git·Python·`uv`·MCP 설정·논문 조회 CLI를 점검한다. README를 에이전트에게 따로 읽으라고 요청할 필요가 없다.

초기화 스크립트는 안전하게 여러 번 실행할 수 있다. 필요한 작업 폴더를 만들고, Git·Python·`uv`·설정 파일·논문 조회 CLI를 점검한다. MCP 캐시는 각 서버가 처음 실행될 때 생성된다. 패키지 설치, API 키 등록, 논문 다운로드, 기존 노트 수정은 하지 않는다.

Codex를 통하지 않고 현재 상태만 확인하려면 다음을 사용한다.

```powershell
powershell -ExecutionPolicy Bypass -File .\.scripts\setup.ps1 -CheckOnly
```

## 필요한 도구

| 도구 | 용도 | 설치 여부 |
|---|---|---|
| Git | 저장소 복제와 버전 관리 | 필수 |
| Python 3.10+ | `.scripts/bin/paper.py` 실행 | 필수 |
| [uv](https://docs.astral.sh/uv/) / `uvx` | `arxiv-mcp`, `paper-search-mcp` 실행 | 필수 |
| Codex Desktop 또는 Codex CLI | 에이전트·프로젝트 설정 사용 | 필수 |
| `EXA_API_KEY` | Exa 의미 기반 논문 검색 | 선택 |
| Graphify | 저장소 논문 관계 그래프 | 선택 |

`uv`가 없다면 Windows에서는 다음처럼 설치할 수 있다. 설치 후 터미널과 Codex를 다시 연다.

```powershell
winget install --id Astral-sh.UV -e
```

Python 또는 Git이 없다는 진단이 나오면 해당 도구를 먼저 설치한 뒤 초기화 스크립트를 다시 실행한다.

## 첫 작업

Codex에서 아래처럼 자연어로 요청하거나 해당 스킬을 호출한다.

```text
/paper-search transformer 효율화 관련 최근 논문 찾아줘
/paper-review 1706.03762
/related-work 1706.03762
/paper-relations 저장소에 있는 논문의 연구 계보를 정리해줘
/review-index 인덱스를 정리해줘
```

표준 흐름은 다음과 같다.

```text
논문 수집 → 트리아지 → 심층 리뷰 → 관련 연구 맵 → 인덱스 갱신
```

1. `/paper-search`로 메타데이터를 확인하고 PDF를 `01-Papers/pdfs/{category}/`에 저장한다.
2. `90-Templates/paper/triage-template.md`로 1차 판정을 `01-Papers/triage/`에 남긴다.
3. `/paper-review`로 `01-Papers/reviews/{category}/`에 논문 한 편당 리뷰 한 파일을 작성한다.
4. 필요하면 `/related-work` 또는 `/paper-relations`로 앞뒤 연구와 저장소 내 관계를 확인한다.
5. `/review-index`로 `01-Papers/library/index.md`를 갱신한다.

## 작업 공간 지도

| 경로 | 정본(source of truth) | 역할 |
|---|---|---|
| [Home.md](Home.md) | 예 | 전체 MOC와 현재 연구 맥락 |
| `00-Inbox/` | 예 | 아직 분류하지 않은 질문·링크·관찰 |
| `01-Papers/pdfs/` | 예 | 카테고리별 원문 PDF |
| `01-Papers/triage/` | 예 | 논문별 1차 판정·조사 메모 |
| `01-Papers/reviews/` | 예 | 카테고리별 최종 심층 리뷰 |
| `01-Papers/library/` | 예 | 인덱스, Keep, 즐겨찾기 |
| `02-Concepts/` | 예 | 논문 요약이 아닌 개념 공부노트 |
| `03-Trends/daily/` | 예 | 날짜별 다이제스트와 예약 계획 |
| `04-Projects/` | 예 | 실험·구현·스터디 |
| `05-ideas/thought-experiments/` | 예 | 검증 전 연구 가설과 반증 조건 |
| `90-Templates/` | 예 | 리뷰·트리아지·공부노트 양식 |
| `99-Attachments/` | 예 | 그림·로그 등 비원문 첨부 |
| `.scripts/` | 예 | 자동화와 검색 프로토콜 |

루트의 `papers`, `reviews`, `library`, `notes`, `templates`, `scripts`, `docs`는 과거 링크를 보존하는 호환 경로다. 새 파일은 이 경로들이 아니라 위 정본 디렉터리에 작성한다.

PDF와 리뷰는 다음 이름을 사용한다.

```text
{연도}-{제1저자성}-{짧은-슬러그}
01-Papers/pdfs/other/2017-vaswani-attention-is-all-you-need.pdf
01-Papers/reviews/other/2017-vaswani-attention-is-all-you-need.md
01-Papers/triage/2017-vaswani-attention-is-all-you-need.notes.md
```

PDF 카테고리는 `wifi-csi`, `game-ai`, `agent-ai`, `computer-vision`, `other` 중 하나다.

## Codex와 MCP 설정

Codex용 프로젝트 설정은 [.codex/config.toml](.codex/config.toml)에 있다. 처음 세션을 시작할 때 다음 MCP 구성이 로드된다.

| 서버 | 용도 | 준비 |
|---|---|---|
| `arxiv-mcp` | arXiv 섹션 조회·연구 알림 | `uvx` 필요 |
| `paper-search-mcp` | arXiv·PubMed·bioRxiv·Google Scholar 등 통합 검색 | `uvx` 필요 |
| `exa` | 의미 기반 논문 전문 검색 | `EXA_API_KEY` 필요 |

Exa는 선택 사항이다. 키를 현재 PowerShell 세션에만 넣으려면 다음을 실행한 뒤 Codex를 같은 세션에서 시작한다.

```powershell
$env:EXA_API_KEY = "your_api_key"
```

영구 등록은 본인의 환경 변수 관리 방식으로 설정한 뒤 Codex를 재시작한다. API 키를 저장소나 `.mcp.json`에 직접 넣지 않는다. `.mcp.json`은 다른 MCP 호환 클라이언트를 위한 동등 설정이며, Codex에서는 `.codex/config.toml`이 기준이다.

## 논문 조회 CLI

`.scripts/bin/paper.py`는 추가 Python 패키지 없이 arXiv, Semantic Scholar, OpenAlex를 조회한다.

```powershell
python .scripts/bin/paper.py search "efficient transformer" --source arxiv --limit 10
python .scripts/bin/paper.py meta 1706.03762
python .scripts/bin/paper.py pdf 1706.03762 --out 01-Papers/pdfs/other
python .scripts/bin/paper.py refs 1706.03762
python .scripts/bin/paper.py cites 1706.03762
```

검색 설계와 소스별 한계는 [.scripts/docs/search-protocol.md](.scripts/docs/search-protocol.md)에 정리돼 있다. 중요한 검색에는 최소 두 소스를 사용하고, API가 실제로 반환한 논문만 기록한다.

## 선택: 논문 관계 그래프

Graphify는 원문 PDF 사이의 인용·공유 방법·공유 데이터 관계 후보를 탐색할 때만 설치한다.

```powershell
uv tool install "graphifyy[pdf]"
```

설치 후 Codex에 `$paper-relations`를 요청한다. 관계는 `EXTRACTED`, `INFERRED`, `AMBIGUOUS` 상태를 원문과 대조하며, 원문에서 확인되지 않은 결론은 `[확인 필요]`로 남긴다.

## 리뷰 원칙

- 초록만으로 방법이나 실험을 추측하지 않는다. 긴 PDF는 본문 → 실험 → 부록 순으로 구간을 나눠 읽는다.
- 모든 수치·주장·설정에는 `(§4.2, Table 3)`, `(p.7, Eq. 5)`처럼 원문 위치를 붙인다.
- 원문에 없는 내용은 `[추론]`, `[내 의견]`, `[확인 필요]`로 명시한다. 하이퍼파라미터·컴퓨트가 없으면 `미기재`라고 쓴다.
- Keep 목록과 즐겨찾기는 독립 목록이다. `keep.md`는 나중에 읽을 대기열이고 `favorites.md`는 선호 기록이다.

세부 규칙과 리뷰 품질 기준은 [AGENTS.md](AGENTS.md)를 따른다.

## 문제 해결

| 증상 | 조치 |
|---|---|
| `uvx`를 찾지 못함 | `uv`를 설치하고 터미널·Codex를 다시 연 뒤 `setup.ps1`을 재실행한다. |
| Exa 인증 실패 | `EXA_API_KEY`가 설정됐는지 확인하고 Codex를 재시작한다. Exa 없이도 나머지 검색 도구는 사용할 수 있다. |
| Git이 `dubious ownership`을 보고함 | 저장소 소유자가 신뢰할 수 있는지 확인한 뒤 `git config --global --add safe.directory "<저장소 절대 경로>"`를 실행한다. |
| 초기화 검사 실패 | 출력의 `FAIL` 항목을 해결한 뒤 같은 명령을 다시 실행한다. 스크립트는 기존 연구 자료를 지우지 않는다. |
