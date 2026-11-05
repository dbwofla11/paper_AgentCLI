# Research WebUI

연구 하네스의 localhost WebUI다. 한 서버가 WebUI(논문 라이브러리·논문 리더·사고실험·하네스·상태·작업), 정적 HTML 화면(논문 라이브러리·하네스·사고실험), 논문 리뷰 실행 API를 함께 제공한다. 예전 로컬 리뷰 브리지를 이 서버로 흡수했으며 포트(8765)와 기존 리뷰 API는 그대로다.

## 실행

처음이면 온보딩으로 에이전트를 연결하고 서버까지 띄운다.

```bash
python3 .scripts/bin/onboard_research.py
```

같은 포트에 이 저장소의 서버가 이미 떠 있으면 온보딩은 그 서버를 재사용한다. 단, 그 서버가 방금 연결한 것과 다른 에이전트로 동작 중이면 재사용하지 않고 종료 코드 1로 끝난다. 실행 중인 서버를 Ctrl+C로 종료한 뒤 온보딩을 다시 실행한다.

이미 연결했다면 서버만 실행한다.

```bash
python3 .scripts/bin/research_webui.py serve                 # 브라우저 자동 열기
python3 .scripts/bin/research_webui.py serve --no-browser    # 주소만 출력
python3 .scripts/bin/research_webui.py serve --agent claude  # 이 서버의 에이전트 고정 (auto|codex|claude|omp)
python3 .scripts/bin/research_webui.py serve --port 8766 --timeout 3600
python3 .scripts/bin/research_webui.py check                 # 준비 상태 JSON, 모두 준비되면 종료 코드 0
```

- `--agent`를 생략하면 `.research-harness-agent.json`에 저장된 연결을 요청마다 읽는다.
- `--timeout`은 논문 리뷰 한 편의 제한 시간(초)이다.
- `check`는 에이전트 상태, `pdftotext` 설치 여부, 프런트엔드 빌드(`100-views/webui/index.html`) 존재 여부를 출력한다.
- 서버는 `127.0.0.1`에만 바인딩한다. Ctrl+C 또는 SIGTERM(`kill <pid>`)으로 종료한다. 종료할 때 진행 중인 논문 질문을 취소하고 최대 5초 동안 정리(답변 CLI 종료, 임시 작업 폴더 삭제)를 기다린다.

## 주소

| 주소 | 내용 |
|---|---|
| `http://127.0.0.1:8765/` | `/100-views/webui/`로 이동 |
| `http://127.0.0.1:8765/100-views/webui/` | WebUI 첫 화면: 논문 라이브러리 (`#/`, 통계·검색·필터·리뷰 시작) |
| `…/100-views/webui/#/papers/{slug}` | 논문 리더 (PDF + 리뷰 + 질문 + 리뷰 검증 실행) |
| `…/100-views/webui/#/ideas` | 사고실험 (아이디어 노트·심사 레지스트리·실험 기록) |
| `…/100-views/webui/#/harness` | 하네스 (스킬 흐름·카탈로그·검사·라우팅·연결 상태) |
| `…/100-views/webui/#/status` · `#/jobs` | 연결·리뷰 역할 상태, 작업 목록 |
| `http://127.0.0.1:8765/100-views/paper-library.html` · `harness-dashboard.html` · `thought-experiments.html` | 정적 대체 화면. 서버 없이 `file://`로도 열리며 WebUI 메뉴에는 없다 |

`localhost:8765`로 접속해도 된다. API와 SSE 계약은 [.scripts/docs/webui-api.md](../.scripts/docs/webui-api.md)에 있다. 논문 리뷰 실행의 격리·검증·게시 규칙은 [로컬 리뷰 실행기](paper-review-bridge.md)를 본다.

정적 화면은 생성기(`paper_catalog_html.py`, `harness_dashboard.py`, `thought_experiments_html.py`)가 WebUI API와 같은 데이터 함수로 만든다. 리뷰 파이프라인과 `verify_harness.py`가 계속 이 파일을 갱신·확인하므로 지우지 않는다.

## 화면

- **논문 라이브러리 (`#/`)**: 전체 논문·리뷰 완료·읽기 대기·연구 분야·PDF 있음 통계, 연도별·분야별 막대 차트, 검색(제목·저자·주제·초록·요약·학회)과 분야·읽기 상태·연도·PDF 필터. 카드 제목이나 "읽기"는 리더를 연다. "원문"은 원문 주소가 있을 때만 새 탭으로 연다. 두 버튼은 같은 모양(테두리와 옅은 강조색 배경)이고 카드 오른쪽에 세로 가운데로 놓인다. 768px보다 좁으면 카드 아래에 한 줄로 나란히 놓인다. PDF가 있고 리뷰가 필요한 논문에는 "리뷰 시작"이 보이며, 리뷰 에이전트가 준비되지 않았으면 이유와 함께 비활성화된다. 진행 중에는 `GET /api/reviews/{slug}`를 3초마다 확인하고(상태 API는 다시 부르지 않는다), 끝나면 목록을 새로 고치고 알림을 띄운다.
- **사고실험 (`#/ideas`)**: `05-Ideas/thought-experiments/`의 아이디어 노트를 비판 검증 레지스트리(`04-Projects/thought-experiment-runs/CRITICAL_VALIDATION_REGISTRY.md`), 실행 폴더(brief·분석 JSON·manifest·실험 결과·심사 의견·산출물), 조사 TODO 대기열과 묶어 보여 준다(`GET /api/ideas`, 정적 `thought-experiments.html`과 같은 기록). 제목·가설 검색, 심사 상태·역할 심사·문헌 상태·사용자 결정·실험 상태·조사 TODO 필터, 갱신일·제목 정렬, "N / M개" 표시가 있다. 카드에는 가설·반증 조건·역할 심사와 상태 배지가 있고, 노트와 레지스트리의 상태나 결정이 다르면 경고를 띄운다(어느 쪽도 자동으로 고치지 않는다). 연결 파일은 서버가 제공하는 것만 링크가 되고, 관련 논문은 라이브러리 기록이 있으면 리더로 연다. 아이디어가 없으면 노트를 두는 위치와 `thought-experiment-critique` 스킬을 안내한다. 기록 파일을 읽지 못하면 그 부분만 빼고 경고로 알린다.
- **하네스 (`#/harness`)**: 작업 흐름 탭과 단계별 입력·결과·실행 조건, 스킬 카탈로그(카드를 누르면 사용 위치와 SKILL.md 전문이 시트로 열린다), 검사, 라우팅 표, 스킬 정본·호스트 연결, omp 에이전트·페르소나, 검증기, Graphify 동기화 기록. 정본 파일은 수정하지 않는다. 파일 경로는 복사할 수 있고, 서버가 제공하는 파일만 링크가 된다(`.omp/` 등은 경로만 표시).
- **검사**: "하네스 구조 검사"(`python3 .scripts/bin/verify_harness.py`)와 "하네스 테스트"(`python3 -m unittest discover -s .scripts/tests`)만 실행할 수 있다. 한 번에 하나만 돌고, 출력은 실시간으로 보이며 작업 화면에서도 확인할 수 있다. 테스트는 몇 분 걸리고 CPU를 많이 쓴다. 화면을 다시 열면 마지막 실행 결과를 서버의 작업 기록에서 복원한다.

## 보안 모델

- **바인딩**: `127.0.0.1`에만 연다. 같은 컴퓨터의 브라우저만 접속한다.
- **Host 검사**: GET을 포함한 모든 요청의 `Host`가 `127.0.0.1:<port>` 또는 `localhost:<port>`여야 한다. TRACE·CONNECT 같은 기타 메서드도 먼저 이 검사를 거친다. DNS rebinding으로 다른 사이트가 응답을 읽는 것을 막는다.
- **상태 변경 요청**: POST 등은 `Origin`이 같은 로컬 출처여야 하고, `Sec-Fetch-Site`가 있으면 `same-origin`이어야 한다. `X-CSRF-Token`과 `Content-Type: application/json`도 필요하다. 토큰은 서버를 켤 때마다 새로 만들며 `GET /api/session`으로 받는다.
- **본문 크기**: 64 KiB 이하, 리뷰 요청은 4096 B 이하다.
- **CORS 없음**: 다른 출처에 응답을 열어 주지 않는다.
- **정적 파일**: 허용 폴더(`01-Papers/`, `docs/`, `100-views/` 등)와 루트의 `AGENTS.md`·`CLAUDE.md`·`README.md`만 제공한다. 경로 이탈(`..`, NUL, 대소문자 변형), 저장소 밖을 가리키는 심볼릭 링크, `.git`·`.env*`·`.mcp.json`·`.claude` 같은 개인 설정은 404다. 디렉터리 목록은 보여주지 않는다.
- **보안 헤더**: 모든 응답에 `nosniff`, `no-referrer`, `X-Frame-Options: DENY`를 붙인다. WebUI(`/100-views/webui/`)에는 외부 스크립트·폰트·연결을 막는 CSP를 붙인다.
- **에이전트 실행**: 에이전트 CLI는 본인 로그인으로 실행한다. 서버는 계정·토큰·API 키를 읽거나 복사하지 않는다. 임의 shell 명령이나 파일 경로를 요청으로 받지 않는다.

## 작업과 스트리밍

WebUI의 오래 걸리는 작업은 job으로 실행한다. 진행 상황은 `GET /api/jobs/{id}/events` SSE로 받는다. 연결이 끊겨도 브라우저가 `Last-Event-ID`로 이어 받는다. 이어 받을 기록이 이미 버퍼에서 밀려났으면 `gap` 이벤트로 알려 주고, 화면은 기록 누락을 표시한 뒤 최종 `result`의 답을 그대로 보여 준다. 동시에 열 수 있는 스트림은 서버 전체에서 32개이고, 넘으면 503 `too_many_streams`다. 작업은 서버 메모리에만 있어 서버를 끄면 사라진다. 논문 리뷰 큐(`04-Projects/review-queue/queue.json`)는 기존처럼 파일에 남는다.

WebUI가 만드는 작업은 `agent.ping`(에이전트나 리뷰 역할에 짧은 응답 요청), `paper.ask`(논문 리더 질문), `harness.verify`·`harness.tests`(하네스 화면의 검사)다. 작업 화면에서 대상을 "생성 역할 (paper-analyst)", "검증 역할 (paper-verifier)" 또는 준비된 에이전트로 고를 수 있다. 하네스 검사는 `POST /api/harness/checks`로만 시작하고 `POST /api/jobs`로는 만들 수 없다. 리뷰 검증은 작업 화면이 아니라 논문 리더에서 실행하며, 리뷰 큐 작업이라 상태 화면의 리뷰 대기열에 표시된다.

## 논문 리더

첫 화면 논문 라이브러리에서 PDF가 있는 논문의 제목이나 "읽기"를 누르면 리더가 열린다. 왼쪽은 PDF(pdf.js, 로컬 번들), 오른쪽은 리뷰·질문 패널이다.

- **리뷰 탭**: 5축 리뷰 주장과 근거 위치(`Table 3, p.8` 등)를 보여 준다. 근거 칩이나 `p.N` 링크를 누르면 그 쪽으로 이동해 해당 위치를 깜박인다. PDF 위 하이라이트를 누르면 연결된 리뷰 주장으로 이동한다. 하이라이트는 리뷰 근거 위치(표·그림·절 번호)와 주장 속 영문 용어·수치로 찾으며, 찾지 못하면 쪽 여백 표시로 대신한다. 리뷰 문장이 한국어라 원문 문장 단위로 일치시키지는 않는다.
- **리뷰 검증**: 리뷰 탭 머리(근거·리뷰 전문·검증 보기 모두)에 검증 상태 배지와 "검증 실행" 버튼이 있다. 검증 보고서가 이미 있으면(리뷰나 PDF가 바뀐 뒤 포함) "다시 검증"이다. 누르면 `POST /api/reviews/{slug}/verify`로 검증 역할(`paper-verifier`)만 실행해 리뷰를 원문 PDF와 대조하고, 리뷰 문서는 바꾸지 않는다. 진행 중에는 그라데이션 진행 막대를 보이고 `GET /api/reviews/{slug}`를 3초마다 확인한다(화면을 떠나면 멈춘다). 끝나면 리뷰 묶음을 다시 불러 배지와 검증 보기를 갱신하고 알림을 띄운다. 리뷰 문서나 PDF가 없거나 검증 역할이 미설정·준비 안 됨이면 버튼이 이유와 함께 비활성화된다. 역할 상태는 앱이 처음 받은 `GET /api/status` 결과를 쓰고 다시 부르지 않는다(실패했을 때만 "다시 확인"으로 한 번 요청한다). 다른 리뷰·검증이 진행 중이면 409 `review_active` 안내가 뜬다.
- **화면 구성**: 리더에는 전체 머리글이 없고 48px 툴바 하나만 있다(뒤로, 제목, 쪽·확대·영역 캡처·하이라이트, 패널, 연결 점, 메뉴). 폭이 768px보다 좁으면 확대·축소, 폭 맞춤, 영역 캡처, 하이라이트가 "보기 도구" 버튼의 팝오버로 들어가고, 480px보다 좁으면 이전·다음 쪽 버튼도 함께 들어간다. 쪽 번호 입력, 패널, 메뉴는 언제나 툴바에 남는다. 메뉴에서 다른 화면과 테마를 고른다. 폭 맞춤은 쪽 폭을 1100px까지만 키운다. 패널 기본 폭은 520px(최소 360px)이다. PDF 쪽은 다크 테마에서도 흰 바탕이다.
- **글자 크기**: 패널 머리의 "가" 세 단계(작게·보통·크게)로 리뷰·답변 글자 크기를 바꾼다. 선택은 `research-webui.reader.text-size`에 저장된다.
- **텍스트 질문**: PDF에서 문장을 드래그하고 "질문하기"를 누른다.
- **영역 질문**: 툴바(좁은 화면은 "보기 도구")의 "영역 캡처"(단축키 R)를 켜고 표·그림을 상자로 고른 뒤 "이 영역 질문하기"를 누른다. 서버가 `pdftoppm`으로 그 영역을 PNG로 잘라 에이전트에 넘긴다.
- **답변**: 스트리밍으로 받으며, 답 속 `p.N`을 누르면 해당 쪽으로 이동한다. 같은 스레드에서 이어 물으면 최근 6턴을 맥락으로 다시 보낸다. 답변 중 취소할 수 있다.
- **기록**: 질문·답변은 `04-Projects/reader-threads/{slug}.json`에 저장되고 다시 열면 복원된다. 이 폴더는 `.gitignore` 대상이며 정적 파일로도 제공하지 않는다(404). 서버를 정상 종료(Ctrl+C·SIGTERM)하면 진행 중이던 질문은 "취소됨"으로 저장된다. 강제 종료(`kill -9` 등)로 꺼졌다면 다음 실행에서 "중단됨"으로 표시된다. 그때 남은 임시 작업 폴더(`webui-reader-*`)는 다음 서버 시작 때 지워진다. 다만 강제 종료 시점에 실행 중이던 답변 CLI는 서버가 멈출 수 없어 스스로 끝날 때까지 남을 수 있다.

답변 에이전트는 `paper-reader` 역할이다. `.omp/config.yml`에 아래처럼 지정하면 그 모델을 쓰고, 지정하지 않으면 연결된 에이전트(`.research-harness-agent.json`)의 CLI 기본 모델로 답한다. 지정했는데 준비된 실행기가 없으면 다른 모델로 바꾸지 않고 질문을 막는다.

```yaml
modelRoles:
  paper-reading: "<provider>/<model>[:effort]"   # 예: 빠른 모델
task:
  agentModelOverrides:
    paper-reader: "@paper-reading"
```

답변은 읽기 전용으로 실행한다. 서버가 임시 폴더에 PDF·쪽별 텍스트·리뷰·메타데이터 사본을 만들고, 에이전트에는 읽기 도구(read·grep·glob)만 준다. 저장소 파일은 바뀌지 않는다. 답변 규칙은 `.omp/agents/paper-reader.md`, API는 [API 계약의 논문 리더](../.scripts/docs/webui-api.md#논문-리더)를 본다.

## 논문 리뷰 구성

WebUI는 리뷰 모델을 따로 설정하지 않고 하네스의 리뷰 에이전트 설정을 따른다. 생성은 `paper-analyst`, 검증은 `paper-verifier`가 맡고, 둘 다 요청 시점의 omp 병합 설정(`.omp/config.yml` 위에 전역 설정)에서 `task.agentModelOverrides` → `modelRoles` → `retry.fallbackChains` 순으로 해석한다. 설정을 고치면 약 5초 안에 서버 재시작 없이 반영된다.

- **우선순위**: 설정된 역할 > 연결된 에이전트. `paper-analyst`가 없으면 `.research-harness-agent.json`의 연결 에이전트가 기본 모델로 리뷰를 만든다(다른 저장소의 기존 동작). `paper-verifier`가 없으면 검증하지 않는다(공용 AGENTS.md 기본값 "리뷰 독립 검증은 요청 시 수행"). 설정되어 있으면 리뷰마다 검증한다.
- **실행기**: 선택자 `anthropic/<model>[:effort]`는 `claude` CLI, `openai-codex/<model>[:effort]`는 `codex` CLI, 그 밖의 provider는 `omp` CLI로 실행한다. 설정됐지만 준비된 실행기가 없으면 그 역할은 사용할 수 없고 다른 모델로 바꾸지 않는다.
- **상태 화면**: "논문 리뷰 구성" 카드가 두 역할의 에이전트 이름·역할·선택자·실행기·준비 상태·참고 사항을 보여 준다. 출처는 `.omp/config.yml (omp 설정)`이다.
- **검증 결과**: 보고서는 `04-Projects/review-queue/verifications/{slug}.json`에 저장하고, 리뷰 큐에 통과·이슈·오류·건너뜀 표시가 붙는다. 이미 리뷰된 논문은 논문 리더 리뷰 탭의 "검증 실행"(`POST /api/reviews/{slug}/verify`)으로 검증만 다시 실행한다.

자세한 해석 규칙·보고서 형식은 [API 계약의 리뷰 역할](../.scripts/docs/webui-api.md#리뷰-역할)과 [로컬 리뷰 실행기](paper-review-bridge.md)를 본다.

## 프런트엔드 개발

프런트엔드 소스는 `.scripts/webui/`(Vite + React + TypeScript)에 있고, 빌드 결과는 `100-views/webui/`에 커밋한다. Node.js와 npm이 필요하다.

```bash
cd .scripts/webui && npm install && npm run dev     # 개발 서버
cd .scripts/webui && npm install && npm run build   # 100-views/webui/에 빌드
```

- `npm run dev`는 `/api` 요청을 `http://127.0.0.1:8765`로 프록시한다. 다른 터미널에서 `python3 .scripts/bin/research_webui.py serve --no-browser`를 먼저 실행한다. 프록시는 `Origin`·`Host`를 서버 주소로 바꿔 가드를 통과시킨다.
- 개발 서버 주소는 Vite가 출력하는 주소를 연다.
- 화면을 바꿨으면 `npm run build` 결과(`100-views/webui/**`)를 함께 커밋한다. 다른 저장소 설치(`papers` 프로필)는 이 빌드를 그대로 복사한다.
- CDN이나 원격 폰트는 쓰지 않는다. 화면 주소는 해시 라우팅(`#/…`)을 쓴다.

### 디자인 토큰·글꼴·테마

- **토큰**: 색·간격·반경·z-index·모션 값은 `.scripts/webui/src/styles/tokens.css` 한 곳에 있다. 화면 CSS(`base.css`, `app.css`, `harness.css`, `ideas.css`, `markdown.css`, `reader.css`)는 토큰만 참조한다. WebUI는 정적 화면의 `100-views/assets/research-ui.css`를 더 이상 불러오지 않는다.
- **테마**: 헤더의 시스템·라이트·다크 선택은 브라우저 `localStorage`의 `research-webui.theme`에 저장한다. `public/theme-init.js`가 첫 그림 전에 `data-theme`를 적용해 깜박임을 막는다(CSP가 인라인 스크립트를 막으므로 별도 파일). PDF 쪽은 두 테마 모두 흰 바탕이다.
- **글꼴**: Roboto와 JetBrains Mono(코드·경로)를 Fontsource 가변 글꼴(`wght`, OFL)로 번들한다. 유니코드 범위별 조각으로 나뉘어 필요한 조각만 내려받는다. 한글은 번들하지 않고 시스템 글꼴(Apple SD Gothic Neo → Pretendard → Malgun Gothic → Noto Sans KR 순)로 표시한다. 한글 가변 글꼴 조각이 빌드에 3.5 MB를 더해 빌드 크기 한도(3 MB)를 넘었기 때문이며, 한글 모양은 운영체제마다 다를 수 있다.
- **수식**: 리더의 리뷰·답변 Markdown에서 `$…$`(인라인)와 `$$…$$`를 KaTeX(`remark-math` + `rehype-katex`)로 그린다. `$$`만 따로 줄에 둔 블록과, 앞뒤 문장과 빈 줄 없이 붙어 있어도 한 줄을 통째로 차지하는 `$$…$$`는 디스플레이 수식이고, 문장 안의 수식은 인라인 수식이다. 금액 같은 리터럴 달러는 `\$1.32`처럼 이스케이프한다(정적 `paper-library.html`도 `\$`를 `$`로 표시한다). 표 셀 안 수식의 `|`는 셀 구분자로 읽히므로 `\lvert…\rvert`나 `\mid`로 쓴다. 스킬 지침은 `$ARGUMENTS` 같은 셸 표기가 많아 수식으로 해석하지 않는다(`Markdown`의 `math` 속성). KaTeX 글꼴은 woff2만 번들한다(`vite.config.ts`의 `katexWoff2Only`). KaTeX JS·CSS·글꼴은 지연 로드되는 Markdown 조각에 들어가며 빌드에 약 590 KB를 더한다.
- **모션**: `motion` 라이브러리(`motion/react-m` + `LazyMotion`)로 화면 전환 페이드, 목록 등장, 탭 표시줄 이동을 그린다. 운영체제의 "동작 줄이기" 설정을 따르며, 그때는 위치 이동 없이 투명도만 바꾸고 반짝임·진행 표시 반복을 멈춘다.
- **아이콘**: `lucide-react`. 이모지는 쓰지 않는다.
