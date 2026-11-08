# 처음 사용하는 사람을 위한 노트북 설치·실행 안내

이 문서는 **이 저장소에서 논문 에이전트를 실행하는 절차**다. 다른 프로젝트에 스킬을 옮기는 방법은 [설치기 안내](research-harness-installer.md)를 본다. CLI 명령은 터미널에, 논문 요청은 실행한 에이전트의 채팅 입력란에 넣는다.

## 1. 무엇을 설치하는가

하네스(harness)는 에이전트가 따라야 할 규칙, 작업별 스킬, 단계 안내, 결과 저장 경로, 검사 도구를 묶은 것이다. 모델 실행은 Codex, Claude Code 또는 omp가 담당한다. **셋 중 하나만 설치해도 시작할 수 있다.** 이 저장소를 clone하면 공통 스킬은 `.agents/skills/`에 들어온다.

| 구성 | 필요한 시점 | 확인 방법 |
|---|---|---|
| Git | 저장소 받기·업데이트 | `git --version` |
| Python 3.10 이상 | 저장소 CLI·검사 도구 | `python3 --version` |
| Codex, Claude Code 또는 omp + 사용 가능한 계정 | 에이전트 실행 | `codex --version`, `claude --version` 또는 `omp --version` |
| 인터넷 | 로그인·모델 응답·논문 검색/다운로드 | 첫 요청과 검색으로 확인 |
| uv / uvx | 논문 MCP 서버, Graphify 설치 | `uv --version`, `uvx --version` |
| Graphify | 논문 관계 질의·정본 갱신 | `graphify --help` |
| diagram-design 스킬 + 프로필 | 심층 리뷰의 방법 구조도(SVG) 생성 | `onboarding_check.py` WARN 여부 |
| visual-explainer 스킬 + Node.js | 심층 리뷰의 시각 요약(선택, WebUI 리더 "시각 요약") 생성 | `onboarding_check.py` WARN 여부 |
| EXA_API_KEY | 선택 기능 Exa 의미 검색 | 환경 진단의 설정 여부 표시 |
| Orca | 예약 실행·Orca worker 기능 | 해당 기능을 사용할 때 별도 구성 |

Python CLI는 표준 라이브러리를 사용한다. 에이전트 로그인과 Exa 키는 서로 별개다. Exa 키가 없어도 `paper.py`와 다른 검색 경로를 사용할 수 있다. 예약과 다중 worker까지 한 번에 설치할 필요는 없다.

## 2. 운영체제와 기본 도구 준비

아래 실행 예시는 **macOS/Linux 또는 Windows의 WSL Ubuntu 터미널** 기준이다. Windows에서 시작한다면 관리자 PowerShell에서 `wsl --install`을 실행하고 안내에 따라 재시작·Ubuntu 사용자 생성을 마친 뒤 Ubuntu 터미널에서 계속한다. Git·Python·에이전트·uv를 같은 환경에 설치한다. Windows PowerShell의 프로그램과 WSL 프로그램을 섞으면 PATH·로그인·링크가 서로 달라질 수 있다. 이 저장소의 심볼릭 링크 구조 때문에 WSL 경로를 기본 안내로 사용한다. Windows 네이티브 전체 흐름은 이번 검증 범위에 포함되지 않는다.

Ubuntu/WSL에서 기본 도구가 없다면:

```bash
sudo apt update
sudo apt install git python3 curl
git --version
python3 --version
```

macOS는 `xcode-select --install`로 Git 도구를 준비하고, [Python 공식 다운로드](https://www.python.org/downloads/)에서 Python 3.10 이상을 설치한다. 설치 후 터미널을 다시 열어 버전을 확인한다. WSL 설치 상세는 [Microsoft 공식 안내](https://learn.microsoft.com/windows/wsl/install)를 따른다.

## 3. 저장소 받기

```bash
git clone --branch personal https://github.com/dbwofla11/paper_AgentCLI.git
cd paper_AgentCLI
```

비공개 저장소라면 GitHub 계정에 접근 권한이 있어야 한다. 기존 노트북에서 이미 받은 저장소라면 해당 폴더로 이동해서 계속한다. 매번 clone하지 않는다. 모든 명령은 `AGENTS.md`가 있는 저장소 루트에서 실행한다.

**배포 브랜치:** 이 온보딩과 연결된 하네스는 `personal` 브랜치에서 관리한다. 기본 브랜치가 같은 구성을 포함한다고 가정하지 않도록 위 명령에 브랜치를 명시했다. 배포 전 커밋할 파일만 별도 폴더에 복원해 아래 검사를 수행한다. 신규 사용자는 파일이 없으면 개인 설정을 추측해 만들기보다 제공받은 브랜치가 최신인지 확인한다.

## 자동 연결과 HTML 실행

저장소를 받은 뒤 루트에서 한 번 실행한다:

```bash
python3 .scripts/bin/onboard_research.py
```

설치된 Codex·Claude·omp의 준비 상태를 검사하고 자동 선택한다. 순서는 Codex → Claude → omp이며 기존 연결이 있으면 그 선택을 유지한다. CLI 로그인 안내 뒤 로컬 WebUI 서버를 시작하고 `http://127.0.0.1:8765/100-views/webui/`를 브라우저에서 연다. 연결을 마친 뒤에는 `python3 .scripts/bin/research_webui.py serve`로 서버만 띄울 수 있다. 주소·보안 모델은 [Research WebUI 안내](research-webui.md)를 본다.

연결 파일 `.research-harness-agent.json`은 개인 에이전트 선택과 선택적인 Orca 설정을 보관한다. 인증 정보는 보관하지 않는다. `.research-harness-agent.example.json`, `.omp/config.example.yml`, `AGENTS.local.example.md`의 로컬 사본을 만드는 방법은 [AGENTS.md](../AGENTS.md#개인-설정과-로컬-덮어쓰기)를 따른다.

```bash
python3 .scripts/bin/onboard_research.py --agent claude  # Codex: --agent codex, omp: --agent omp
python3 .scripts/bin/onboard_research.py --check         # 읽기 전용 진단
python3 .scripts/bin/onboard_research.py --connect-only  # 디렉터리·화면 생성과 연결 설정 후 종료
```

Python 3.10+, Poppler의 `pdftotext`가 필요하다. Claude 자동 리뷰는 `--restricted` 지원 버전과 OS 샌드박스를 사용한다. Linux/WSL은 bubblewrap·socat, macOS는 sandbox-exec를 검사한다. omp에는 OS 샌드박스 검사가 없으며 임시 작업 복사본을 사용한다. 준비되지 않은 환경은 연결 실패 원인을 표시한다.

구현 근거: [Codex 비대화형 실행](https://learn.chatgpt.com/docs/non-interactive-mode), [Codex 인증](https://learn.chatgpt.com/docs/auth), [Claude CLI·인증 명령](https://code.claude.com/docs/en/cli-reference), [Claude 비대화형 실행](https://code.claude.com/docs/en/headless).

## 4. 에이전트 설치·로그인

### 경로 A — Codex

공식 CLI 설치 명령:

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
```

터미널을 다시 열고 저장소 루트로 이동한다.

```bash
codex --version
codex login
codex login status
```

브라우저 안내에 따라 본인 계정으로 로그인한다. 사용 가능한 모델과 이용 권한은 계정에 따라 확인한다. 개인 인증 파일을 저장소에 복사할 필요는 없다. [공식 Codex CLI 안내](https://learn.chatgpt.com/docs/codex/cli).

### 경로 B — Claude Code

```bash
curl -fsSL https://claude.ai/install.sh | bash
```

새 터미널에서 저장소 루트로 이동한 뒤:

```bash
claude --version
claude
```

첫 실행의 로그인 안내를 따른다. `CLAUDE.md`가 공통 규칙을 연결하고 `.claude/skills/`가 공통 스킬을 노출한다. [공식 Claude Code quickstart](https://code.claude.com/docs/en/quickstart).

### 경로 C — omp

omp CLI를 설치한 뒤 저장소 루트에서 `omp --version`, `omp login`, `omp models --json`으로 실행·로그인과 사용 가능한 모델을 확인한다. `omp`로 대화형 세션을 시작한다. 모델 역할과 하위 에이전트 선호는 `.omp/config.example.yml`을 복사한 개인 `.omp/config.yml`에서 설정한다.

## 5. 환경과 하네스 검사

```bash
python3 -B .scripts/bin/onboarding_check.py --host codex
python3 -B .scripts/bin/verify_harness.py
```

Claude 또는 omp를 선택했다면 첫 명령을 각각 `--host claude` 또는 `--host omp`로 바꾼다. 새 세션에서 필요한 폴더도 준비하려면 `python3 .scripts/bin/onboarding_check.py --create-dirs`를 사용한다(Windows: `py -3 .scripts/bin/onboarding_check.py --create-dirs`). 첫 검사는 환경과 선택 도구를 확인한다. `FAIL`은 필수 항목 누락, `WARN`은 선택 기능 미준비다. 비밀값은 출력하지 않는다. 두 번째 검사는 저장소 구조·라우팅·논문 JSON 계약을 검사한다. **검사 통과만으로 로그인·MCP 연결·논문 리뷰 품질이 검증되는 것은 아니다.**

심층 리뷰는 방법 구조도를 `diagram-design` 스킬로 만든다. 아래 세 가지가 모두 있어야 하며, 하나라도 없으면 `onboarding_check.py`가 `WARN`으로 알리고 리뷰는 Mermaid 등으로 대체하지 않고 실패로 보고된다.

| 구성 | 위치 |
|---|---|
| 사용자 수준 스킬 (사용하는 호스트) | omp `~/.omp/agent/skills/diagram-design/`, Claude `~/.claude/skills/diagram-design/`, Codex `~/.codex/skills/diagram-design/` (다른 호스트 설치본으로의 심볼릭 링크 가능) |
| 저장소 마커 | 루트 `.diagram-design` 파일, 내용 `profile: research-harness` 한 줄 (저장소에 포함) |
| 프로필 | `~/.diagram-design/profiles/research-harness.md` (`Font source: system`) |

심층 리뷰는 끝에 리뷰 전체의 시각 요약(HTML 한 장)을 `visual-explainer` 스킬로 만든다. 선택 산출물이라 준비되지 않았으면 `onboarding_check.py`가 `WARN`으로 알리고, 리뷰는 시각 요약 없이 완료된다. WebUI 리더의 "시각 요약 만들기"도 같은 준비가 필요하다(없으면 503 `visual_unavailable`). WebUI 작업(리뷰·시각 요약 만들기)은 설치된 스킬 디렉터리를 작업 폴더의 `.visual-explainer/`로 복사해 그 사본만 쓰므로, 에이전트가 설치된 스킬을 고치지 않는다. 사본은 작업이 끝나면 지워진다.

| 구성 | 위치 |
|---|---|
| 사용자 수준 스킬 (사용하는 호스트) | omp `~/.omp/agent/skills/visual-explainer/`, Claude `~/.claude/skills/visual-explainer/`, Codex `~/.codex/skills/visual-explainer/`. `SKILL.md`와 `kit/render.mjs`가 있어야 한다. 원본은 [nicobailon/visual-explainer](https://github.com/nicobailon/visual-explainer)(MIT, 확인한 판 v0.15.0)의 `plugins/visual-explainer` 폴더이며, 한 호스트에 복사하고 다른 호스트는 심볼릭 링크로 연결해도 된다 |
| Node.js | PATH의 `node` (`render.mjs` 실행) |
| 시각 검사 (선택) | `npm install --no-save --prefix <스킬 디렉터리> playwright-core`로 스킬 폴더에 `playwright-core`를 설치하고, 브라우저는 Google Chrome 또는 `npx playwright-core@<버전> install chromium-headless-shell`을 쓴다. 없으면 렌더가 "Visual check skipped"를 출력하고 페이지는 그대로 만든다 |

`research_harness_check.py`는 다른 저장소에 설치기가 만든 manifest를 검사한다. 이 저장소의 첫 실행 진단에는 위 명령을 사용한다. 여기에서 설치 manifest가 없다는 오류가 나는 것은 설치기를 자기 저장소에 실행하라는 뜻이 아니다.

## 6. 첫 실행과 작동 확인

터미널에서 선택한 에이전트를 시작한다:

```bash
codex
```

Claude라면 `claude`, omp라면 `omp`를 실행한다. Codex는 신뢰한 프로젝트의 `.codex/config.toml`을 읽으므로 첫 실행 시 프로젝트 내용과 설정을 확인하고 신뢰 여부를 선택한다. 기존 공통 규칙이 있으므로 `/init`으로 새 규칙을 만들 필요는 없다. [공식 설정 안내](https://learn.chatgpt.com/docs/config-file/config-basic).

**첫 채팅 — 파일 쓰기 없이 지침 확인:**

```text
AGENTS.md와 docs/Harness-Graph.md를 읽어줘.
.agents/skills/paper-search/SKILL.md와 paper-review/SKILL.md가 보이는지 확인하고,
논문 수집 → 리뷰 → 인덱스 갱신 순서를 설명해줘. 파일은 수정하지 마.
```

기대 결과는 스킬 경로와 원문 근거 규칙을 인식하고 한국어로 설명하는 것이다. Codex는 저장소 `.agents/skills/`를 탐색한다. [공식 스킬 경로 안내](https://learn.chatgpt.com/docs/build-skills).

**두 번째 채팅 — 검색 통신 확인:**

```text
paper-search 스킬을 읽고 arXiv 1706.03762의 제목·저자·원문 주소를 확인해줘.
이번에는 연결 점검만 하고 PDF·Keep·JSON은 저장하지 마.
MCP를 쓸 수 없으면 .scripts/bin/paper.py의 meta 명령으로 확인해줘.
```

기대 제목은 `Attention Is All You Need`다. 통신 자체는 터미널에서도 확인할 수 있다:

```bash
python3 .scripts/bin/paper.py meta 1706.03762
python3 .scripts/bin/research_workflow.py collect
```

라우터는 `next: paper-search`를 안내할 뿐 스킬을 대신 실행하지 않는다.

**첫 실제 작업 — 아래 요청부터 파일이 저장된다:**

```text
arXiv 1706.03762를 paper-search로 수집해서 Keep과 논문 JSON에 등록해줘.
이어서 paper-review로 원문을 3패스 정독하고 한국어 심층 리뷰를 작성해줘.
원문 페이지를 실제로 읽지 못한 부분은 미확인으로 남겨줘.
리뷰 뒤 review-index와 Graphify 동기화 상태를 확인해줘.
```

Codex에서는 `$paper-search`, Claude에서는 `/paper-search`, omp에서는 `/skill:paper-search`로 명시할 수 있다. 자연어 요청도 가능하다. 이 표기는 에이전트 입력란에서 사용하며 셸 명령이 아니다.

원문을 구간별로 읽는지, 수치마다 위치를 붙이는지, 결과가 `01-Papers/pdfs/{category}/`, `01-Papers/reviews/{category}/`, `01-Papers/library/{slug}.json`, `keep.md`, `index.md`에 연결되는지 확인한다. 실행 환경에 PDF 페이지 읽기 도구가 없다면 그 문제부터 해결하고, 읽지 않은 논문을 완료 처리하지 않는다. 공부노트 승격은 사용자가 이해를 확인하고 명시적으로 요청한 뒤 진행한다.

## 7. MCP와 Graphify 확장

MCP(Model Context Protocol)는 검색·원문 조회 같은 외부 도구 연결이다. Claude 설정은 `.mcp.json`, Codex 설정은 `.codex/config.toml`에 있다. omp는 두 프로젝트 설정을 가져온다. 한쪽 설정을 고쳐도 다른 설정 파일이 바뀌지는 않는다.

uv 설치 후 새 터미널에서 확인한다. [uv 공식 설치 안내](https://docs.astral.sh/uv/getting-started/installation/).

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
uvx --version
python3 -B .scripts/bin/onboarding_check.py --host codex --with-mcp
codex mcp list
```

Claude는 `claude mcp list`로 설정을 확인한다. 이후 에이전트 안에서 `/mcp`를 열고 실제 연결과 도구 호출을 확인한다. `mcp list`에 이름이 보이는 것과 서버가 응답하는 것은 별도다. 처음 `uvx`가 서버 패키지와 Python을 내려받는 동안 인터넷과 시작 시간이 필요하다. [공식 Codex MCP 안내](https://learn.chatgpt.com/docs/extend/mcp?surface=cli).

| 서버 | 준비 | 실패 시 |
|---|---|---|
| arxiv-mcp | uvx; 설정의 Python 3.11·서버 버전 사용 | 로그와 패키지 다운로드를 확인; `paper.py` 대체 경로 |
| paper-search-mcp | uvx; `mcp<2` 제약 사용 | 버전 제약·연결 확인; 다른 검색 소스 사용 |
| exa | 본인 EXA_API_KEY | 키 없이 시작 가능; 사용할 때만 키 설정 |

Exa를 사용할 때는 터미널에서 비밀값을 화면에 표시하지 않고 입력한 뒤 같은 터미널에서 에이전트를 다시 시작한다:

```bash
read -r -s -p 'EXA_API_KEY: ' EXA_API_KEY
export EXA_API_KEY
codex
```

이 Bash 설정은 해당 터미널 세션에 적용된다. 지속 저장은 본인 환경의 비밀 관리 방법을 따른다. `.env` 자동 로딩을 가정하지 않는다. Codex에서 Exa를 사용하지 않는다면 `.codex/config.toml`의 `[mcp_servers.exa]` 아래에 `enabled = false`를 넣을 수 있다. Claude에서는 `/mcp`에서 해당 서버를 관리한다.

Graphify는 관계 질의와 리뷰 뒤 정본 동기화를 위해 준비한다:

```bash
uv tool install 'graphifyy[pdf]'
python3 -B .scripts/bin/onboarding_check.py --host codex --with-mcp --with-graphify
```

스킬은 이미 저장소에 있다. 지식 그래프 `graphify-out/graph.json`은 커밋하지 않으므로 새 clone에는 없다. 에이전트에 “Graphify 스킬을 읽고 이 저장소의 그래프를 구축해줘”라고 요청해 먼저 만든다. 이 구축은 의미 추출을 위해 모델 호출 비용이 든다. 그래프가 생기면 `graphify query "<질문>"`, `graphify path "A" "B"`, `graphify explain "X"`, `graphify affected "X"`로 질의하고, 정본이 바뀌면 `.scripts/bin/graphify_sync.py`로 동기화를 추적한다. 코드 변경의 `graphify update .`는 AST 갱신이며 논문 의미 추출 완료를 대신하지 않는다. 의미 동기화 실패는 재시도 가능한 pending으로 남긴다. 그래프가 없으면 `wiki-index.md`와 해당 페이지를 읽는다.

위키와 지식 그래프는 MCP 서버로 접근하지 않는다. 로컬 리뷰 브리지의 작업 복사본에는 프로젝트 MCP 설정(`.mcp.json`, `.codex/`, `.claude/`)이 복사되지 않는다. 위키·그래프 기능이 더 필요하면 MCP 서버를 추가하지 말고 저장소 CLI `.scripts/bin/wiki.py`를 확장한다.

주 화면은 로컬 서버(`python3 .scripts/bin/research_webui.py serve`)가 띄우는 WebUI다. 논문 라이브러리(`#/`)에서 리뷰를 시작하고, 하네스(`#/harness`)에서 스킬 흐름과 검사를 확인한다. 정적 화면 `100-views/harness-dashboard.html`, `paper-library.html`, `thought-experiments.html`은 서버 없이 브라우저에서 바로 열 수 있고, 정적 라이브러리의 리뷰 시작도 서버가 켜져 있으면 계속 동작한다. 화면과 실제 에이전트 실행의 차이는 [로컬 리뷰 실행기](paper-review-bridge.md)를 본다. 일일 자동 검색은 별도 Orca Automation이 필요하며, `$paper-scheduler`는 날짜별 주제 계획만 기록한다.

## 8. 막힐 때

| 증상 | 확인·해결 |
|---|---|
| 명령을 찾을 수 없음 | 새 터미널에서 버전 확인; WSL와 Windows 설치 위치를 구분 |
| docs 또는 도구가 없음 | 공유 브랜치에 하네스 변경이 반영됐는지 확인 |
| 스킬이 안 보임 | 루트에서 재실행; 진단으로 SKILL.md·링크 확인; 에이전트 재시작 |
| Claude 링크가 일반 텍스트 파일임 | 심볼릭 링크가 보존되는 WSL 파일 시스템에 새 clone; 개인 수정은 먼저 보관 |
| Codex 프로젝트 MCP가 안 보임 | 프로젝트 신뢰·시작 디렉터리·사용자 설정 확인 |
| MCP 시작 실패 | uvx/Python/네트워크/서버 로그 확인; 사용하지 않는 서버는 비활성화 |
| 401 또는 로그인 실패 | 선택한 에이전트 로그인 상태와 계정 접근 권한 확인 |
| 논문 API 429 | 재시도·대체 소스 사용; 결과를 지어내지 않기 |
| manifest 누락 | 이 저장소는 onboarding_check.py; 외부 설치 대상은 research_harness_check.py |
| PDF를 읽지 못함 | 페이지 읽기 지원을 점검하고 읽기 실패를 명시; 리뷰 완료 보류 |
| 리뷰가 "방법 구조도 생성 불가"로 실패 | `onboarding_check.py`의 diagram-design WARN 확인; 스킬·`.diagram-design` 마커·프로필 준비 |
| 리뷰 보고나 리더에 "시각 요약 없음" | `onboarding_check.py`의 visual-explainer·node WARN 확인; 준비 뒤 리더에서 "시각 요약 만들기" |

## 9. 발표에서 보여줄 순서

PPT에는 아래 다섯 단계를 한 장에 담고, 실제 데모는 첫 두 채팅으로 시작한다. 설치 완료 화면과 실제 리뷰 완료 화면은 구분한다.

| 단계 | 화면·명령 | 설명 |
|---|---|---|
| ① 준비 | Git·Python·에이전트 설치와 로그인 | 모델 실행 환경을 먼저 준비한다 |
| ② 연결 | clone → 루트에서 실행 | 저장소의 규칙과 스킬을 읽는다 |
| ③ 진단 | onboarding_check + verify_harness | 파일·도구·라우팅 준비를 검사한다 |
| ④ 첫 요청 | 지침 확인 → 메타데이터 조회 | 실제 모델 응답과 검색을 확인한다 |
| ⑤ 연구 작업 | 수집 → 정독 → 인덱스·그래프 | 원문 근거를 남기며 결과를 축적한다 |

발표 멘트: “새 사용자는 저장소를 받고 에이전트에 로그인한 다음 준비 검사를 실행합니다. 첫 요청으로 규칙과 검색 연결을 확인하고, 그 다음 논문 수집과 정독을 시작합니다. 검색 도구와 예약 기능은 필요할 때 추가합니다.”
