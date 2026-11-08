# 로컬 리뷰 실행기

논문 리뷰 실행은 로컬 [Research WebUI](research-webui.md) 서버가 담당한다. 예전 리뷰 브리지 스크립트는 이 서버에 흡수했으며 포트(8765), `/api/status`, `POST /api/reviews`, `/api/reviews/{slug}` 동작은 그대로다. 구현은 `.scripts/bin/webui/reviews.py`(큐·임시 작업공간·게시)와 `.scripts/bin/webui/server.py`(HTTP)에 있다.

## 사용자 에이전트 자동 연결

권장 진입점은 저장소 루트에서 `python3 .scripts/bin/onboard_research.py`다. 설치된 Codex·Claude·omp의 준비 상태를 감지하고 연결 설정 저장 뒤 WebUI 서버와 브라우저를 연다. `--agent codex`, `--agent claude`, `--agent omp`로 선택할 수 있다. `--check`는 읽기 전용이다. 인증 정보는 공식 CLI가 관리하고 개인 연결 파일에는 선택과 선택적인 Orca 설정을 둔다.

CLI 실행 옵션 검사를 통과하지 못하거나 PDF 읽기 도구가 없으면 이유를 표시한다. HTML은 `/api/status`에서 연결된 에이전트를 확인하고, 리뷰 요청은 그 에이전트로 실행한다. 실행 중인 작업은 시작할 때 선택한 에이전트를 유지한다. 단, 아래 리뷰 역할이 설정되어 있으면 역할이 연결 에이전트보다 우선한다.

## 리뷰 역할

리뷰 작업은 하네스의 리뷰 구조를 따른다. 생성은 `paper-analyst`, 검증은 `paper-verifier`가 맡으며, 서버가 요청 시점에 omp 병합 설정(`omp config get task.agentModelOverrides|modelRoles|retry.fallbackChains|retry.modelFallback --json`)을 읽어 모델·effort·실행기(claude·codex·omp CLI)를 정한다. WebUI는 모델 이름을 따로 저장하지 않는다.

| 역할 | 설정됨 | 미설정 |
|---|---|---|
| `paper-analyst` (생성) | 역할의 첫 준비 후보로 실행한다. 기존 리뷰 프롬프트에 `.omp/agents/paper-analyst.md` 본문(frontmatter 제외)을 붙이고 `.agents/skills/paper-review/SKILL.md`를 읽게 한다. | 연결 에이전트와 기본 모델로 기존과 같이 실행한다. |
| `paper-verifier` (검증) | 리뷰마다 검증한다. 검증 실행기도 준비되어야 리뷰를 시작할 수 있다. | 검증하지 않는다(`skipped`). |

설정됐지만 준비된 후보가 없으면 역할 이름과 실행기를 적은 사유로 리뷰를 거부하며, 다른 모델로 바꾸지 않는다. 후보가 여럿이면 사용량 한도로 실패했고 어시스턴트 출력 흔적도 작업 복사본 변경도 없을 때만 다음 후보로 넘어가며, 출력과 진단을 구분할 수 없으면 넘어가지 않는다. 시도 기록은 큐 작업의 `generation.attempts`에 남는다.

omp 설정을 읽지 못하면(시간 초과·실패 종료·잘못된 JSON) "미설정"으로 보지 않는다. 연결 에이전트로 대신 생성하거나 검증을 건너뛰지 않고, 리뷰·검증·역할 확인을 모두 그 사유로 거부한다. 저장소에서 `omp config get task.agentModelOverrides --json`이 성공하는지 확인한다.

## 서버 실행

리뷰는 로컬 서버가 띄운 WebUI의 첫 화면 논문 라이브러리(`#/`)에서 시작한다. `100-views/paper-library.html`은 정적 파일만으로 에이전트를 실행하지 않으므로, 정적 라이브러리에서 시작하려면 같은 서버 주소로 열어야 한다.

```bash
python3 .scripts/bin/research_webui.py serve
```

WebUI 주소는 `http://127.0.0.1:8765/100-views/webui/`(논문 라이브러리 `#/`), 정적 라이브러리 주소는 `http://127.0.0.1:8765/100-views/paper-library.html`이다. `리뷰 시작`은 논문 slug 하나만 보내고(`POST /api/reviews`) 실행기는 한 번에 한 작업만 처리한다. WebUI는 진행 중인 리뷰를 `GET /api/reviews/{slug}`로 3초마다 확인한다. 준비된 Codex·Claude·omp와 `pdftotext`가 필요하다. PDF는 한 번에 최대 10쪽씩 읽고 읽은 범위를 기록한다. 스캔 PDF나 읽기 실패는 완료 처리하지 않는다. omp는 OS 샌드박스 검사를 제공하지 않는다.

## 격리와 검증

리뷰 에이전트는 저장소의 임시 작업 복사본에서 실행된다. 선택한 PDF만 복사하고 나머지 원문 PDF는 제외한다. `.mcp.json`, `.env*`, `.claude/`, `.codex/`, `.secrets/`, `credentials.json`도 복사하지 않으며, 복사본 밖을 가리키는 심볼릭 링크는 제거한다. 작업 전후 파일 상태를 비교하며 리뷰 Markdown, 리뷰 옆 `figures/`의 해당 논문 방법 구조도(`{slug}-method.html`·`{slug}-method.svg`처럼 리뷰 slug로 시작하는 `.svg`·`.html`), 선택 논문 JSON, 논문 인덱스, 카탈로그, Graphify 출력, 개념 후보 초안만 게시 후보로 받는다. 다른 slug로 시작하거나 다른 확장자인 그림 파일은 허용 범위 밖 변경으로 실패 처리한다. JSON 스키마·5축 필드·실제 읽은 범위를 확인하고, 리뷰에 템플릿 지시문 주석(`<!--`)이 남아 있으면 실패 처리한다. 방법 구조도를 만들지 못한 리뷰는 에이전트가 실패로 보고하며 Mermaid 등으로 대체하지 않는다. Graphify 동기화 실패는 리뷰를 유지한 채 pending으로 남긴다. 실행 중 원본 파일이 바뀌었으면 해당 출력 게시를 거부한다. 실패 상태와 오류 요약은 `04-Projects/review-queue/queue.json`에 남긴다.

작업 복사본에는 Git이 무시하는 개인 논문 기록 `01-Papers/library/`, `01-Papers/reviews/`(`figures/` 포함), `01-Papers/index.md`도 복사한다. 그래서 에이전트와 게시 전 충돌 검사가 실제 저장소의 최신 기록을 본다. 리뷰 대상이 아닌 원문 PDF와 리더 질문 기록(`reader-threads`)은 계속 제외한다.

리뷰 에이전트는 `wiki-index.md`와 `wiki-log.md`를 수정할 수 없다(바뀌면 허용 범위 밖 변경으로 실패 처리한다). 게시가 끝나면 서버가 실제 저장소에서 `python3 .scripts/bin/wiki.py index`와 `wiki.py log --op ingest --title "<논문 제목>" --path <리뷰> --path <JSON>`을 실행하고, 두 파일을 변경 목록에 포함한다. 이 단계가 실패해도 게시한 리뷰는 유지되며 작업 메시지에 실패 내용과 재실행 방법을 남긴다.

## 독립 검증

`paper-verifier`가 설정되어 있으면 생성 결과가 위 검증을 통과한 뒤, 게시하기 전에 같은 임시 작업 복사본에서 검증기를 읽기 전용으로 실행한다(codex `--sandbox read-only`, claude 읽기 도구만, omp `read,grep,glob,bash`). 프롬프트는 `.omp/agents/paper-verifier.md` 본문, 리뷰·PDF 경로, 그 파일 frontmatter의 출력 스키마(`status`, `review_path`, `checked_claims[{claim, locator, verdict, note}]`, `blocking_issues`, `summary`)다. 답은 필수 키·타입·판정 값을 검사한다. 검증 전후로 작업 복사본 전체(선택한 PDF 포함, 복사 제외 규칙과 무관)를 비교해 무엇이든 바뀌면 검증 오류로 처리한다. 보고서의 리뷰·PDF SHA-256은 검증 전에 잰 값이다. 게시는 검증 직전에 따로 복사해 둔 검증 통과 출력에서 하므로, 검증기가 파일을 덮어쓰거나 지우거나 디렉터리·심볼릭 링크로 바꿔도 게시 내용은 생성 결과 그대로다.

검증은 게시를 막지 않는다. 차단 이슈가 있어도, 검증 실행이 실패하거나 JSON이 잘못돼도 리뷰는 게시하고 결과만 기록한다(AGENTS.local.md의 "결과를 리뷰 작성 결과와 함께 보고"). 서버는 보고서를 `04-Projects/review-queue/verifications/{slug}.json`에 원자적으로 쓰고(검증한 리뷰·PDF의 SHA-256, 검증 시각, 검증 에이전트·선택자·실행기, 검증 결과 또는 오류), 작업의 변경 목록에 넣는다. 큐 작업에는 `generation`과 `verification`(통과·이슈·오류·건너뜀, 차단 이슈 수, 미확인·불일치 주장 수)이 붙고, 작업 메시지 끝에 한 줄 요약이 붙는다.

이미 리뷰된 논문은 `POST /api/reviews/{slug}/verify`로 검증만 다시 실행한다. 리뷰 Markdown과 PDF가 있어야 하고 `paper-verifier`가 설정·준비되어 있어야 한다. 같은 임시 작업 복사본 방식으로 실행하며 리뷰와 같은 단일 실행 잠금을 쓴다(진행 중이면 409 `review_active`). 큐에는 `kind: "verify"` 작업으로 남는다.

## 요청 보호

서버는 `127.0.0.1`에만 바인딩한다. 모든 요청의 `Host`를 `127.0.0.1:<port>` 또는 `localhost:<port>`로 제한한다. 리뷰 요청(`POST /api/reviews`)은 같은 로컬 출처의 `Origin`, `GET /api/session`에서 받은 `X-CSRF-Token`, `Content-Type: application/json`이 필요하며 본문은 4096 B 이하다. 검증 요청(`POST /api/reviews/{slug}/verify`)도 같은 출처·토큰·JSON 본문이 필요하다. 라이브러리 화면은 리뷰를 시작할 때 토큰을 자동으로 받아 보낸다. 임의 shell 명령이나 파일 경로를 요청으로 받지 않는다. 이 실행기는 리뷰가 필요한 논문 한 편에 대한 전용 어댑터이며, 사고실험 문헌 조사 실행은 별도 Orca TODO 어댑터를 사용한다. 전체 HTTP 계약은 [.scripts/docs/webui-api.md](../.scripts/docs/webui-api.md)에 있다.
