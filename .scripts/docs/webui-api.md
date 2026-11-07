# Research WebUI HTTP·SSE 계약 (M0)

로컬 WebUI 서버(`.scripts/bin/research_webui.py`, 구현은 `.scripts/bin/webui/`)의 HTTP·SSE 계약이다. 서버는 `127.0.0.1`에만 바인딩하고 기본 포트는 `8765`다. 사람용 실행 안내는 [docs/research-webui.md](../../docs/research-webui.md)를 본다.

## 요청 가드

`webui/security.py`가 정적 파일을 포함한 **모든 요청**에 아래 순서로 가드를 적용한다. GET·POST뿐 아니라 TRACE·CONNECT·임의 메서드 토큰도 같은 순서를 거친다(표준 라이브러리의 501 경로를 쓰지 않는다).

1. **Host**: `Host` 헤더가 정확히 `127.0.0.1:<port>` 또는 `localhost:<port>`여야 한다. 다르거나 없거나 여러 개면 403 `bad_host`다. GET에도 적용하므로 DNS rebinding 페이지가 응답을 읽을 수 없다.
2. **상태 변경 메서드** (POST·PUT·PATCH·DELETE)
   - `Origin`이 `http://<Host>`와 같아야 한다. 아니면 403 `bad_origin`.
   - `Sec-Fetch-Site`가 있으면 `same-origin`이어야 한다. 아니면 403 `bad_origin`.
   - `X-CSRF-Token`이 서버의 `csrf_token`과 같아야 한다(`hmac.compare_digest`). 아니면 403 `bad_csrf`.
   - `Content-Type`의 media type이 `application/json`이어야 한다. 아니면 415 `unsupported_media_type`.
   - 본문은 64 KiB 이하(`POST /api/reviews`는 4096 B 이하)다. 넘으면 413 `payload_too_large`. chunked 본문은 411 `length_required`다.
   - 본문은 JSON 객체여야 한다. 아니면 400 `bad_json`. 빈 본문은 `{}`로 본다.
3. **라우트**: 없는 `/api/*` 경로는 404 `not_found`, 알려진 경로의 지원하지 않는 메서드(HEAD·OPTIONS·TRACE·CONNECT·임의 토큰 포함)는 405 `method_not_allowed`(`Allow` 헤더 포함)다. `/api/*` 밖 경로에서 GET·HEAD가 아닌 메서드는 405 `method_not_allowed`(`Allow: GET, HEAD`)다. GET·HEAD·POST·PUT·PATCH·DELETE가 아닌 메서드는 본문을 읽지 않으므로, 보낸 본문(1 MiB 이하)을 버리고 응답 뒤 연결을 닫는다.

토큰은 `GET /api/session`으로 받는다. 다른 출처 페이지는 CORS 헤더가 없어 이 응답을 읽을 수 없다.

## 응답 헤더

| 대상 | 헤더 |
|---|---|
| 모든 응답 | `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY` |
| `/api/*` | `Cache-Control: no-store` |
| `/100-views/webui/` 아래 | `Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'` |
| `GET`·`HEAD /api/papers/{slug}/figures/{name}` 200 | 위 `/api/*` 헤더에 더해 `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; img-src data:`, `Content-Disposition: inline; filename="<name>"` |

CORS 헤더는 보내지 않는다. 기존 정적 화면(`paper-library.html` 등)은 inline script를 쓰므로 CSP를 적용하지 않는다.

오류 본문은 항상 `{"error": str, "code": str}`이다.

## 엔드포인트

| 메서드 | 경로 | 동작 |
|---|---|---|
| GET | `/` | 302 → `/100-views/webui/` |
| GET | `/paper-library.html`, `/harness-dashboard.html`, `/thought-experiments.html` | 302 → `/100-views/<name>` (기존 주소 유지) |
| GET | 정적 파일 | 아래 "정적 파일" 규칙. `/100-views/webui/`는 `index.html`을 준다. |
| GET | `/api/session` | `{"csrf_token", "workspace_id", "port", "version": "webui-m0"}` |
| GET | `/api/status` | 기존 브리지와 같은 키: `ok`, `workspace_id`, 에이전트 상태 필드(`agent`, `ready`, `reason`, `candidates` 등), `pdf_reader_ready`, `runner`, `pdf_reader`, `max_parallel`, `queue`. 추가 키 `review_roles`: `{"generation": <역할 해석>, "verification": <역할 해석>}`(아래 "리뷰 역할"), `reader_role`: `paper-reader`의 역할 해석(아래 "논문 리더"). `ready`·`reason`은 리뷰 준비 상태로, 역할이 설정되어 있으면 역할 기준이다. |
| GET | `/api/reviews/{slug}` | `{"jobs": [...]}` — 리뷰 큐에서 해당 slug의 작업. 검증 보고서가 있으면 `verification`(아래 "검증 보고서")도 준다. |
| POST | `/api/reviews` | 본문 `{"slug"}`. 리뷰 한 편을 큐에 넣고 202 `{"job"}`. 이미 완료면 409 `review_complete`, 다른 리뷰 진행 중이면 409 `review_active`, 에이전트·리뷰 역할 미준비면 503 `agent_unavailable`, 잘못된 slug·PDF면 400 `bad_request` |
| POST | `/api/reviews/{slug}/verify` | 본문 `{}`. 이미 리뷰된 논문에 검증 단계만 실행하고 202 `{"job"}`(큐 작업 `kind: "verify"`). 잘못된 slug·레코드는 400 `bad_request`, 리뷰 Markdown이 없으면 409 `review_missing`, PDF가 없으면 409 `pdf_missing`, 역할 설정을 읽지 못하면 503 `role_config_error`, `paper-verifier` 미설정이면 409 `verifier_unconfigured`, 설정됐지만 실행기 미준비면 503 `verifier_unavailable`, 다른 리뷰·검증 진행 중이면 409 `review_active` |
| GET | `/api/jobs` | `{"jobs": [record…]}` (최신순) |
| POST | `/api/jobs` | 본문 `{"kind": "agent.ping", "agent"?: "claude"\|"codex"\|"omp", "role"?: "paper-analyst"\|"paper-verifier"}` → 202 `{"job": record}`. `agent`와 `role`은 함께 쓸 수 없다. 모르는 kind(`paper.ask`·`harness.*` 포함)·agent·role, 문자열이 아닌 값(배열·객체·숫자 등), `agent`+`role` 동시 지정은 400 `bad_request` |
| GET | `/api/jobs/{id}` | `{"job": record}`, 없으면 404 |
| GET | `/api/jobs/{id}/events` | SSE 스트림(아래). 없는 작업은 404, 동시 스트림이 상한이면 503 `too_many_streams` |
| POST | `/api/jobs/{id}/cancel` | 202 `{"job": record}`. 이미 끝났으면 409 `already_finished`, 없으면 404 |
| GET | `/api/papers` | `PapersPayload`: `{"papers": [PaperSummary], "errors": [{"file", "error"}], "labels", "queued_statuses"}`(아래 "논문 리더") |
| GET | `/api/papers/{slug}` | `PaperBundle`. 잘못된 slug 400 `bad_request`, 레코드 없음 404 `not_found` |
| GET | `/api/papers/{slug}/pdf` | `application/pdf` 본문과 `Content-Length`. 400, 404, PDF가 없거나 `01-Papers/pdfs` 밖이면 409 `pdf_missing` |
| GET·HEAD | `/api/papers/{slug}/figures/{name}` | 리뷰 방법 구조도 SVG(아래 "리뷰 그림"). 200 `image/svg+xml`, `Content-Length`, `Last-Modified`. 잘못된 slug·이름 400 `bad_request`, 레코드·파일 없음 404 `not_found` |
| GET | `/api/papers/{slug}/threads` | `{"slug", "threads": [Thread]}`. 진행 중 턴은 브로커 기준으로 다시 확인한다. 400, 404 |
| DELETE | `/api/papers/{slug}/threads/{thread_id}` | 본문 `{}`. 200 `{"deleted": "t_…"}`. 400, 404 `not_found`(레코드)·`thread_not_found`, 진행 중 턴이 있으면 409 `thread_busy` |
| POST | `/api/papers/{slug}/ask` | 202 `{"job": record, "thread": Thread}`. 오류는 아래 "질문 오류" |
| GET | `/api/reader/status` | `ReaderStatus` |
| GET | `/api/harness` | `HarnessPayload`(아래 "하네스") |
| POST | `/api/harness/checks` | 본문 `{"check": "verify"\|"tests"}` → 202 `{"job": record}`(`kind: "harness.verify"\|"harness.tests"`). 오류는 아래 "하네스" |
| GET | `/api/ideas` | `IdeasPayload`(아래 "사고실험"). GET 외 메서드(HEAD 포함)는 405, `Allow: GET` |

`workspace_id`는 `sha256(str(ROOT.resolve()))`의 앞 16자다. 온보딩이 같은 포트의 기존 서버가 이 저장소의 것인지 확인할 때 쓴다.

에이전트 선택: 서버를 `serve --agent X` 또는 온보딩으로 띄우면 그 에이전트를 리뷰·`/api/status`·`agent.ping` 기본값으로 고정한다. 고정하지 않으면 요청마다 `.research-harness-agent.json`의 연결을 읽는다. 단, `paper-analyst` 역할이 설정되어 있으면 리뷰 생성은 고정·연결 에이전트 대신 그 역할을 쓴다(설정된 역할 > 연결된 에이전트). 온보딩은 같은 포트에 이 저장소 서버가 이미 있을 때, 그 서버의 `/api/status` `agent`가 방금 연결한 에이전트와 같을 때만 재사용한다. 다르면 실행 중인 서버를 종료하고 다시 실행하라는 안내를 출력하고 종료 코드 1로 끝난다.

## 리뷰 역할

리뷰 생성과 검증은 하네스의 리뷰 에이전트 설정을 따른다(구현 `webui/roles.py`). WebUI는 모델 이름을 따로 저장하지 않고, 요청 시 omp의 병합 설정(프로젝트 `.omp/config.yml` 위에 전역 설정)을 `cwd=저장소`에서 `omp config get <key> --json`으로 읽는다. 읽는 키는 `task.agentModelOverrides`, `modelRoles`, `retry.fallbackChains`, `retry.modelFallback`이다. 설정과 실행기 probe 결과는 저장소별로 5초 동안 캐시하므로 설정을 고치면 서버를 다시 띄우지 않아도 곧 반영된다.

| 키 | 하네스 에이전트 | 미설정일 때 |
|---|---|---|
| `generation` | `paper-analyst` | 연결된 에이전트(`.research-harness-agent.json`)가 기본 모델로 리뷰를 만든다(기존 동작). |
| `verification` | `paper-verifier` | 검증하지 않는다(공용 AGENTS.md 기본값 "리뷰 독립 검증은 요청 시 수행"). 설정되어 있으면 리뷰마다 검증한다. |

해석 규칙(에이전트 `A`):

1. `task.agentModelOverrides[A]`가 없으면 미설정이다. 미설정은 설정을 **읽는 데 성공했을 때만** 판단한다(아래 "설정을 읽지 못할 때").
2. 값이 `@role`이면 `modelRoles[role]`을 쉼표로 나눈 순서가 후보이고, `retry.fallbackChains[role]`이 그 뒤에 붙는다(`retry.modelFallback`이 false면 붙이지 않는다). `@`가 없으면 값 자체가 쉼표로 나눈 선택자 목록이고 `role`은 `null`이다.
3. 선택자는 `provider/model-id[:effort]`다. effort는 `off`·`minimal`·`low`·`medium`·`high`·`xhigh`·`max`·`auto`·`inherit` 중 하나이며 생략할 수 있다.
4. 실행기: `anthropic` → `claude` CLI(`--model <model-id>`, `--effort <effort>`), `openai-codex` → `codex` CLI(`-m <model-id>`, `-c model_reasoning_effort="<effort>"`), 그 밖의 provider → `omp` CLI(`--model <선택자 전체>`). CLI가 받지 않는 effort(claude: `off`·`minimal`·`auto`·`inherit`, codex: `off`·`auto`·`inherit`)는 플래그를 생략하고 `notes`에 적는다.
5. `selected`는 실행기가 준비된(`research_agent.probe`) 첫 후보의 번호다. 설정됐지만 준비된 후보가 없으면 그 역할은 사용할 수 없고, 다른 모델로 바꿔 실행하지 않는다.

실행 중 후보 이동: 후보를 순서대로 시도하며, 실행기가 준비되지 않았거나 실행이 `kind: "usage_limit"` `error`로 끝나고 그 전에 `text_delta`·`message`가 없었을 때만 다음 후보로 넘어간다. 넘어가기 전에 `{"type": "retry", "attempt": n, "delay_ms": 0, "reason": "usage_limit", "next": "<선택자>"}`를 보낸다.

리뷰 생성은 텍스트 출력 명령이라 stdout의 답과 진단을 구분할 수 없다. 그래서 실패한 실행은 다음 세 조건을 모두 만족할 때만 다음 후보로 넘어간다. (1) 종료 코드가 0이 아니고 **stderr만** 사용량 한도로 읽힌다(stdout은 어시스턴트 출력으로 보고 분류에 쓰지 않는다). (2) 어시스턴트 출력 흔적이 없다: stdout에 비어 있지 않은 줄이 하나도 없고, `--output-last-message` 파일(codex)이 비어 있거나 없다. stdout에 무엇이든 있으면(사용량 한도 문구처럼 보여도) 넘어가지 않는다. (3) 작업 공간 전체(제외 없음, `audit_snapshot`)가 실행 전과 같다. 시도 기록은 큐 작업의 `generation.attempts`에 남는다.

역할 해석 형식:

```json
{"agent_name": "paper-verifier", "configured": true, "source": "omp-config", "role": "paper-verification",
 "candidates": [{"selector": "openai-codex/gpt-6.1-sol:high", "provider": "openai-codex", "model": "gpt-6.1-sol",
                 "effort": "high", "runner": "codex", "ready": true, "reason": "연결 준비 완료"}],
 "selected": 0, "notes": [], "error": null}
```

`reason`은 준비되지 않은 후보에서 항상 비어 있지 않은 문자열이고, 준비된 후보에서는 probe 문구 또는 빈 값이다. 미설정 역할은 `configured: false`, `candidates: []`, `selected: null`이다. `error`는 항상 있는 키이며 설정을 읽지 못했을 때만 문자열이다.

### 설정을 읽지 못할 때

`omp config get`이 시간 초과·0이 아닌 종료 코드·잘못된 JSON·형식이 틀린 값(예: `modelRoles`가 객체가 아님)으로 실패하면, 그 저장소의 두 역할 모두 아래처럼 해석한다. 값이 `null`이거나 빈 객체인 성공한 응답은 실패가 아니라 미설정이다.

```json
{"agent_name": "paper-analyst", "configured": null, "source": "omp-config", "role": null, "candidates": [],
 "selected": null, "notes": ["…"], "error": "리뷰 역할 설정(omp config)을 읽지 못했습니다: omp config get task.agentModelOverrides 시간 초과"}
```

이 상태에서는 연결 에이전트로 대체하거나 검증을 건너뛰지 않는다. `/api/status`의 `ready`는 false이고 `reason`은 이 사유다(`pdftotext`가 없으면 그 사유가 먼저다). `POST /api/reviews`는 503 `agent_unavailable`, 검증 요청은 503 `role_config_error`, 역할 `agent.ping`은 이 사유의 `error`로 끝나고, 이미 큐에 있던 리뷰 작업도 생성 전에 실패한다. 실패 결과도 5초 캐시되므로 설정을 고치면 곧 다시 읽는다. omp CLI 자체가 없으면 저장소에 `.omp/config.yml`이 없을 때만 미설정으로 보고(`notes`에 기록), 있으면 위와 같은 읽기 실패다.

리뷰 준비(`/api/status`의 `ready`, `POST /api/reviews`): `paper-analyst`가 설정되어 있으면 그 역할의 선택 후보가, `paper-verifier`가 설정되어 있으면 검증 후보도 준비되어야 한다. 실패 사유는 역할과 실행기를 함께 적는다. `pdftotext`가 없으면 기존과 같이 그 사유를 먼저 보여 준다.

## 검증 보고서

리뷰 작업은 생성 결과가 기존 검증(허용 출력·JSON 스키마·5축·읽은 범위·템플릿 지시문 주석 `<!--` 없음·인덱스·카탈로그)을 통과한 뒤, 게시하기 **전에** 같은 staged 작업 공간에서 `paper-verifier`를 읽기 전용으로 실행한다. 허용 출력은 그 논문의 레코드 JSON·리뷰 Markdown, 리뷰 옆 `figures/{slug}-<이름>.svg|html`(다른 slug 접두·확장자·하위 폴더는 불허), `01-Papers/index.md`, `100-views/paper-library.html`, `graphify-out/*`, `00-Inbox/concept-candidates/*`다. 프롬프트는 `.omp/agents/paper-verifier.md` 본문, staged 리뷰 경로, PDF 경로, 그 파일 frontmatter의 출력 스키마다. 스키마는 임시 파일로 써서 codex `--output-schema`·claude `--json-schema`에 넘긴다. 답은 필수 키·타입·판정 값(`supported`·`mismatch`·`unsupported`·`unverifiable`)을 검사한다.

변경 감사: 검증 전후로 staged 작업 공간 **전체**를 제외 없이 기록한다(`audit_snapshot`: 선택한 PDF·캐시 포함, 일반 파일은 SHA-256, 심볼릭 링크는 대상, 디렉터리·특수 파일은 종류). 하나라도 다르면(덮어쓰기·삭제·생성·파일→디렉터리·심볼릭 링크 교체 포함) 검증 `error`다. 보고서의 `review_sha256`·`pdf_sha256`은 검증 **전에** 잰 staged 리뷰·PDF 값이다.

검증은 게시를 막지 않는다. 차단 이슈가 있어도, 실행기가 실패하거나 JSON이 잘못되거나 검증기가 작업 공간을 망가뜨려도 리뷰는 게시하고 검증 상태만 기록한다. 게시는 검증 직전에 작업 공간 밖으로 복사해 둔 검증 통과 출력(과 Graphify 동기화 상태)에서 하므로, 검증기가 staged 파일을 어떻게 바꾸든 게시 내용은 생성 결과 그대로다. 보고서는 서버가 `04-Projects/review-queue/verifications/{slug}.json`에 원자적으로 쓰고(staged 에이전트는 쓰지 않는다), 작업의 `changed_files`에 넣는다.

```json
{"schema_version": "1.0", "slug": "…", "review_path": "01-Papers/reviews/…/….md",
 "review_sha256": "…", "pdf_sha256": "…", "verified_at": "2026-11-04T00:00:00+00:00",
 "verifier": {"agent_name": "paper-verifier", "role": "paper-verification",
              "selector": "openai-codex/gpt-6.1-sol:high", "runner": "codex"},
 "result": {"status": "…", "review_path": "…",
            "checked_claims": [{"claim": "…", "locator": "p.3 §2.1", "verdict": "supported", "note": "…"}],
            "blocking_issues": ["…"], "summary": "…"}}
```

실패하면 `result` 대신 `"error": "<사유>"`다. `GET /api/reviews/{slug}`의 `verification`은 이 보고서에 `summary`(큐 작업의 `verification`과 같은 형식 + `stale`: 현재 리뷰·PDF의 SHA-256이 보고서와 다르면 true)를 붙인 것이다.

리뷰 큐 작업(`queue.json`)의 추가 필드:

- 리뷰 작업: `generation: {"selector": str|null, "runner", "attempts": [{"selector": str|null, "runner", "exit_code": int, "error_kind": str|null, "assistant_output": bool|null, "staged_changes": bool|null, "advanced": bool}]}`(미설정 생성 역할이면 `selector: null`, `runner`는 연결 에이전트, 시도 1건). `error_kind`·`assistant_output`은 실패한 시도에서만 채우고, `staged_changes`는 후보가 둘 이상일 때만 잰다. `advanced: true`는 그 시도 뒤 다음 후보로 넘어갔다는 뜻이다. 생성이 실패해도 시도 기록은 남는다.
- 리뷰·검증 작업: `verification: {"status": "passed"|"issues"|"error"|"skipped", "blocking_issues": int, "mismatches": int, "report_path": str|null, "selector": str|null, "runner": str|null, "note"?: str}`. `passed`는 확인한 주장이 1건 이상이고 차단 이슈가 없으며 모든 판정이 `supported`일 때, `issues`는 그 밖의 결과다. 확인한 주장이 0건이면 통과로 보지 않는다: 차단 이슈도 없으면 `issues`이고 `note: "검증된 주장이 없음"`을 붙인다(`note`는 이 경우에만 있다). `mismatches`는 판정이 `supported`가 아닌 주장 수다. 검증 역할이 미설정이면 `skipped`이고 보고서를 쓰지 않는다. `message` 끝에 한국어 한 줄 검증 요약을 붙인다.
- 검증 작업은 `kind: "verify"`를 가진다(리뷰 작업에는 `kind`가 없다). 검증 결과가 `error`면 작업 상태도 `failed`다. 리뷰·검증 작업은 같은 단일 실행 잠금을 쓴다.

## 논문 리더

PDF를 읽으며 선택 텍스트·선택 영역·쪽·리뷰 항목을 앵커로 질문하고, 답을 스트리밍으로 받는다. 구현은 `webui/reader.py`, 라우팅은 `webui/server.py`다. 질문은 `POST /api/jobs`가 아니라 `POST /api/papers/{slug}/ask`로만 제출한다(`POST /api/jobs`는 여전히 `agent.ping`만 받는다).

### 형식

```jsonc
// PaperSummary — 정렬: has_pdf 먼저, 연도 내림차순, 제목
{"slug", "title", "authors": [], "year", "venue", "category", "topics": [], "one_line_summary",
 "reading_status", "structured_review_status", "has_pdf": true, "has_review": true,
 "verification": {"status": "passed|issues|error|skipped", "stale": false} | null,
 "threads": {"count": 3, "updated_at": "…"} | null,
 "display_title": "…",            // 비지 않음: title → PDF 제목(pdfinfo) → 확인된 대체 제목 → slug
 "abstract": "…" | null,           // 레코드 abstract가 문자열일 때만
 "source_url": "https://…" | null, // source.urls 중 처음 나오는 안전한 http(s) 주소
 "review_needed": true}            // structured_review_status가 complete가 아니거나 리뷰 파일 없음

// PapersPayload
{"papers": [PaperSummary], "errors": [{"file", "error"}],
 "labels": {"category": {"wifi-csi": "WiFi CSI", "game-ai": "Game AI", "agent-ai": "Agent AI",
                         "computer-vision": "Computer Vision", "other": "기타"},
            "reading_status": {"candidate": "후보", "keep": "Keep", "triage": "트리아지",
                               "reading": "읽는 중", "reviewed": "리뷰 완료", "rejected": "제외"}},
 "queued_statuses": ["candidate", "keep", "triage", "reading"]}

// PaperBundle
{"paper": <라이브러리 레코드 전체>,
 "pdf": {"url": "/api/papers/{slug}/pdf", "available": true, "pages": 21 | null, "bytes": 123, "sha256": "…", "text_available": true},
 "review": {"path": "01-Papers/reviews/…md", "available": true, "markdown": "…" | null, "sha256": "…" | null},
 "verification": <검증 보고서 + summary(위 "검증 보고서")> | null,
 "evidence": {"pages": 21, "items": [EvidenceItem], "summary": {"matched": n, "page_only": n, "unresolved": n}}}

// EvidenceItem — 리뷰 주장 하나(축 순서 × 주장 번호)
{"claim_id": "evaluation_and_evidence.4", "axis": "evaluation_and_evidence", "index": 4,
 "statement": "…", "kind": "paper_fact|analysis|inference|unknown",
 "evidence": [{"locator": "Table 3, p.8; Table 5, p.16; Fig.4, p.7", "source": "…"}],
 "targets": [{"evidence_index": 0, "page": 8, "listed_page": 8, "relocated_from": null,
              "anchor": {"kind": "table", "label": "Table 3", "pattern": "\\btable\\s*3\\b"} | null,
              "terms": ["78.9", "87.9"], "quotes": [],
              "confidence": "quote|anchor|terms|page|unresolved"}],
 "status": "matched|page_only|unresolved"}

// ReaderStatus
{"ready": true, "region_ready": true, "reason": null | "…", "agent": "claude" | null,
 "selector": "anthropic/…:high" | null, "configured": true | false | null,
 "resolution": <역할 해석>, "pdf_tools": {"pdftotext": true, "pdftoppm": true, "pdfinfo": true}}

// POST /api/papers/{slug}/ask 본문
{"thread_id": null | "t_…", "question": "…(1..4000자)", "anchor": Anchor | null}

// Anchor — 좌표는 화면에 표시된 쪽 상자 대비 비율(0–1), 원점은 왼쪽 위, x0<x1, y0<y1
{"kind": "text", "page": 7, "text": "…(1..8000자)", "rects": [[x0, y0, x1, y1], …(64개 이하)]}
{"kind": "region", "page": 7, "bbox": [x0, y0, x1, y1]}          // 각 변 ≥ 0.01
{"kind": "page", "page": 7}
{"kind": "claim", "page": 8 | null, "claim_id": "evaluation_and_evidence.4"}   // claim_id는 이 논문에 있어야 한다
```

- `claim_id`는 `<축>.<그 축 claims 배열의 0부터 세는 번호>`다. 축 순서는 `problem_and_prior_work`, `core_idea_and_difference`, `evaluation_and_evidence`, `limitations_and_future_work`, `related_work`다.
- `pdf.pages`는 `pdftotext` 쪽 수, 텍스트가 없으면 `pdfinfo`의 쪽 수, 둘 다 없으면 `null`이다. `text_available`은 비어 있지 않은 쪽 텍스트가 하나라도 있을 때 true다.
- `errors`는 읽지 못한 레코드 파일(JSON 오류, 잘못된 slug 이름)이다. 목록의 나머지는 그대로 준다.
- `display_title`·`source_url`·`review_needed`·`labels`·`queued_statuses`는 정적 논문 라이브러리와 같은 함수·상수(`paper_catalog_html.display_title`·`source_url`·`review_needed`·`LABELS`·`QUEUED_STATUSES`)에서 나온다. `source_url`은 로컬 PDF가 있어도 원문 주소가 있으면 준다. `javascript:`, 호스트 없는 주소, 호스트에 공백이 있는 주소는 `null`이다.
- 저장된 앵커의 `text`는 앞뒤 공백을 지우고, 좌표는 소수 6자리로 반올림한다.

### 리뷰 그림 `GET`·`HEAD /api/papers/{slug}/figures/{name}`

리뷰 Markdown의 `![…](figures/{slug}-method.svg)`를 리더가 표시할 때 쓰는 경로다(구현 `reader.open_paper_figure`, `server._api_paper_figure`). 파일은 리뷰 Markdown과 같은 폴더(`01-Papers/reviews/{category}/`, 하위 폴더 리뷰면 그 폴더)의 `figures/`에 있고, 같은 폴더의 `{slug}-method.html`은 diagram-design 원본이라 제공하지 않는다. 검사 순서:

1. slug·레코드: 잘못된 slug 400 `bad_request`, 레코드 없음 404 `not_found`(`/api/papers/{slug}`와 같다).
2. 이름: `^{slug}-[a-z0-9][a-z0-9-]*\.svg$`가 아니면 400 `bad_request`. 이름은 percent-decoding하지 않으므로 `%2F`·`..`·대문자·`.html`은 모두 여기서 걸린다.
3. 위치: `review_path`(실제 경로가 `01-Papers/reviews` 밖이거나 없으면 카테고리 기본 경로)의 폴더 아래 `figures/{name}`. 검사와 열기는 한 동작이다. 저장소 루트 디렉터리 디스크립터에서 시작해 `01-Papers` → `reviews` → 리뷰 폴더의 각 조각 → `figures`를 하나씩 `dir_fd` + `O_DIRECTORY|O_NOFOLLOW`로 열고, 파일은 `O_NOFOLLOW|O_NONBLOCK`으로 연 뒤 `fstat`으로 일반 파일인지 확인하고 그 디스크립터 그대로 스트리밍한다. 어느 조각이든 없거나, 심볼릭 링크이거나(요청 도중 바뀐 경우 포함), 디렉터리가 아니거나, 파일이 일반 파일이 아니면 404 `not_found`다.

응답은 `image/svg+xml` 본문과 위 "응답 헤더"의 그림 전용 CSP·`Content-Disposition: inline`이다. CSP가 스크립트·외부 요청을 모두 막으므로 SVG를 직접 열어도 스크립트가 실행되지 않는다. 이 그림은 정적 파일로 제공하지 않는다(아래 "정적 파일").

### 질문 오류 (`POST …/ask`)

| 상태 | 코드 | 조건 |
|---|---|---|
| 400 | `bad_request` | 잘못된 slug, 필드 형식(`bool`은 정수로 받지 않음), 쪽이 1..쪽 수 밖, 텍스트·사각형·bbox 제한, 모르는 anchor kind·claim_id |
| 404 | `not_found` / `thread_not_found` | 레코드 없음 / 모르는 스레드 |
| 409 | `pdf_missing` | PDF가 없거나 `01-Papers/pdfs` 밖 |
| 409 | `thread_busy` | 스레드의 마지막 턴이 `queued`·`running` |
| 409 | `thread_full` | 스레드당 50턴, 논문당 200스레드 |
| 503 | `role_config_error` | omp 설정을 읽지 못함 |
| 503 | `reader_unavailable` | 역할이 설정됐지만 준비된 후보가 없음, 또는 미설정인데 연결된 에이전트가 준비되지 않음 |
| 503 | `pdf_tools_missing` | `pdftotext`가 없음(쪽 수를 알 수 없음 포함), 또는 영역 질문인데 `pdftoppm`·`pdfinfo`가 없음 |
| 503 | `shutting_down` | 서버 종료가 시작됨(아래 "서버 종료"). 새 질문을 받지 않는다 |
| 500 | `thread_store_unsafe` | 스레드 저장 경로가 안전하지 않음(아래 "스레드 파일") |

검사 순서: 종료 중 → slug·레코드 → PDF → `pdftotext` → 본문 검증 → 영역 도구 → 스레드(404·409) → 역할(503). 종료 여부는 작업 제출 직전에 잠금 안에서 한 번 더 확인한다.

### 역할 `paper-reader`

| 상태 | 동작 |
|---|---|
| `task.agentModelOverrides["paper-reader"]` 설정 | `paper-analyst`와 같은 규칙으로 해석하고 `roles.walk`로 후보를 돈다(사용량 한도 `retry` 규칙 적용). 준비된 후보가 없으면 사용할 수 없고 다른 모델로 바꾸지 않는다. |
| 미설정(읽기 성공) | 연결된 에이전트(고정 `--agent`, 없으면 `.research-harness-agent.json`)가 `--model` 없이 CLI 기본 모델로 답한다. omp의 `@paper-analysis`도 물려받지 않는다. `notes`: `미설정: 연결된 에이전트(.research-harness-agent.json)의 기본 모델로 답합니다.` |
| 설정을 읽지 못함 | 실패로 닫는다. 연결된 에이전트로 대체하지 않는다. |

`paper-reader`는 `review_roles`에 들어가지 않고 리뷰 준비 상태에도 영향이 없다. 시스템 프롬프트는 `.omp/agents/paper-reader.md` 본문이다.

### 작업 `paper.ask`

- 작업 레코드: `kind: "paper.ask"`, 항상 `role: "paper-reader"`, `agent`는 선택된 실행기, 추가 키 `slug`. `slug`는 `paper.ask` 레코드에만 있다.
- 이벤트는 기존과 같다(`start`·`text_delta`·`message`·`tool_use`·`retry`·`result`·`error`·`cancelled`·`gap`). 취소는 `POST /api/jobs/{id}/cancel`, 제한 시간은 600초다.
- 실행: 임시 작업 공간 `webui-reader-*`에 `paper.json`(slug, title, authors, year, venue, abstract, one_line_summary, review), `review.md`(있을 때), `pages/p%03d.txt`(PDF 쪽 순서), `paper.pdf`, 영역 질문이면 `region.png`를 복사·생성하고, 실행 뒤 지운다. 어느 실행기에도 bash·edit·write가 없고, 사용자 MCP 서버도 쓰지 않는다:
  - claude: `--tools Read,Grep,Glob`, `--strict-mcp-config --mcp-config {"mcpServers":{}}`.
  - codex: `--sandbox read-only`, `--disable plugins --disable apps --disable hooks`, 사용자 설정의 MCP 서버마다 `-c mcp_servers.<이름>.enabled=false`. `-c mcp_servers={}`는 codex가 설정 표를 병합하므로 기존 서버를 지우지 못한다. 서버 이름은 실행 직전에 같은 `--disable` 옵션으로 `codex mcp list --json`을 실행해 읽는다. 목록을 읽지 못하거나 이름이 `[A-Za-z0-9_-]+`가 아니면 실행하지 않고 `error`로 끝낸다. 사용자 기본 모델을 유지하려고 `--ignore-user-config`는 쓰지 않는다.
  - omp: `--tools read,grep,glob`, `--no-extensions --no-skills --no-rules --no-context-files --no-lsp`.
- 이미지: claude는 프롬프트 지시에 따라 Read 도구로 `./region.png`를 읽고, codex는 `--image <절대 경로>`, omp는 `--` 앞의 `@<절대 경로>`로 받는다.
- 작업 공간 준비·영역 렌더링이 실패하면 `error`(`kind: "other"`, 한국어 메시지)로 끝나고 턴은 `failed`로 저장된다.
- 다중 턴: 서버가 스레드의 이전 턴(답이 있는 최근 6턴, 답은 3,000자까지)을 프롬프트에 다시 넣는다. CLI 세션은 유지하지 않는다.
- CLI 시작: argv를 만든 뒤(codex는 MCP 서버 목록 조회로 몇 초 걸릴 수 있다) 취소 여부를 다시 확인하고, 확인·실행·종료 대상 등록을 한 잠금 안에서 한다. 취소된 작업은 CLI를 시작하지 않고 `cancelled`로 끝난다.
- 서버 종료(`serve`·온보딩의 Ctrl+C 또는 SIGTERM, `server_close`): 먼저 새 질문을 막는다(503 `shutting_down`). 그다음 대기·실행 중인 `paper.ask` 작업을 모두 취소하고, 작업 함수가 아직 끝나지 않은 **모든** reader 작업을 최대 5초 기다린다. 이미 종료 이벤트를 냈지만 턴 저장·작업 공간 삭제가 남은 작업도 기다린다. 취소는 CLI에 SIGINT를 보낸다. 2.5초 뒤에도 끝나지 않은 CLI는 프로세스 그룹에 SIGKILL을 보낸다(`LLMRun.terminate`). 작업이 끝나면 턴이 `cancelled`로 저장되고 작업 공간이 지워진다. 5초 안에 끝나지 않은 작업(예: PDF 텍스트 추출 중)은 stderr에 알리고, 그 턴은 다음 실행에서 `interrupted`로 보인다.
- 작업 공간 소유 표시: 작업 공간을 만들면 곧바로 `.reader-owner.lock`(`{"pid", "created_at"}`)을 만든다. 임시 이름으로 만들어 배타 `flock`을 잡은 뒤 이 이름으로 바꾸고, 작업 공간이 지워질 때까지 잠금을 쥔다. 잠금은 프로세스가 죽으면(SIGKILL 포함) 운영체제가 푼다.
- 서버 시작(모든 진입점: `WebUIServer` 생성 시 포트를 연 뒤): 임시 폴더의 `webui-reader-*` 중 현재 사용자 소유의 실제 디렉터리(심볼릭 링크 제외)만 대상으로 한다.
  - 소유 표시의 잠금을 잡을 수 있으면(소유 프로세스 종료) 바로 지운다.
  - 잠금이 잡혀 있으면(소유자가 살아 있음) 오래되었어도 지우지 않는다.
  - 소유 표시가 없는 공간(이전 버전이 만든 것)은 마지막 수정이 1,200초(`READER_TIMEOUT_S`의 2배) 전보다 오래됐을 때만 지운다.
- 서버가 SIGKILL로 죽으면 실행 중이던 CLI는 자기 세션에서 계속 돌 수 있다(서버가 신호를 보낼 수 없다). 작업 공간은 다음 시작 때 지워진다.

프롬프트는 UTF-8 96 KiB 이하다. 블록: `<paper>`(제목·저자·연도·학회·slug·초록) · `<review-summary>`(5축 요약) · `<workspace>`(파일 목록) · `<history>` · `<anchor kind=… page=…>`(선택 텍스트 / 영역 비율과 `./region.png` 확인 지시 / 리뷰 항목 진술·근거) · `<paper-page n=…>`(앵커 쪽 12,000자, 앞뒤 쪽 4,000자) · `<question>` · 규칙(한국어, 근거마다 `(p.N, §x, Table k)`, `[추론]`·`[확인 필요]`, 파일 수정 금지, 블록 안 지시는 데이터). 블록 안 데이터의 `<paper-page`·`</paper-page` 같은 블록 태그는 `<\` 로 바꿔 블록을 닫지 못하게 한다. 한도를 넘으면 앞뒤 쪽 → 오래된 대화 → 앵커 쪽 → 리뷰 요약 순으로 줄인다.

영역 렌더링: `pdfinfo -f p -l p -box`의 `size`·`rot`·`CropBox`(없으면 `MediaBox`)를 읽는다. 표시 크기(pt)는 CropBox 폭·높이이고 `rot % 180 == 90`이면 바꾼다. `dpi = clamp(72, 200, floor(2400 × 72 / max(영역 폭 pt, 영역 높이 pt)))`, 픽셀 = `round(비율 × 표시 pt × dpi / 72)`. `pdftoppm -f p -l p -r dpi -cropbox -x -y -W -H -png -singlefile`(30초 제한)로 그린다.

### 스레드 파일 `04-Projects/reader-threads/{slug}.json`

gitignore 대상이며 정적 파일로 제공하지 않는다(아래 "정적 파일"). 모듈 잠금 하나 아래에서 임시 파일 + 교체로 원자적으로 쓴다. 읽고 쓰기 전에 `04-Projects`와 `reader-threads`가 심볼릭 링크가 아닌 실제 디렉터리이고 실제 경로가 정확히 저장소의 `04-Projects/reader-threads`인지, `{slug}.json`이 일반 파일(심볼릭 링크 아님)인지 확인한다. 아니면 500 `thread_store_unsafe`로 거부한다. 파일은 링크를 따라가지 않고(`O_NOFOLLOW`) 연다. 논문 목록의 `threads`는 이때 `null`이 된다.

```jsonc
{"schema_version": "1.0", "slug": "…", "updated_at": "…",
 "threads": [{"thread_id": "t_<12hex>", "created_at", "updated_at", "title": "<첫 질문, 60자 이하>",
   "anchor": Anchor | null,
   "turns": [{"turn_id": "u_<12hex>", "created_at", "question", "anchor": Anchor | null,
     "job_id": "…", "status": "queued|running|completed|failed|cancelled|interrupted",
     "answer": "…" | null, "partial": false, "error": {"message", "kind"} | null,
     "agent": "claude" | null, "model": "…" | null, "selector": "…" | null, "role_configured": true,
     "cost_usd": null, "duration_ms": null, "finished_at": null,
     "pdf_sha256": "…", "review_sha256": "…" | null}]}]}
```

- 턴을 만들 때와 끝날 때만 쓴다. 텍스트 조각마다 쓰지 않는다. 스레드는 만든 순서로 저장한다.
- 읽을 때 브로커가 모르는 `job_id`의 `queued`·`running` 턴(예: 서버 재시작)은 `interrupted`로, 대기 중에 취소되어 실행되지 않은 작업의 턴은 `cancelled`로 보여 주고 다음 쓰기 때 저장한다.
- 최종 상태: `ctx.cancelled`가 설정되면 `cancelled`(브로커 규칙과 같음), 아니면 종료 이벤트로 정한다. 완료 턴의 `answer`는 `result.text` 그대로다(빈 문자열이어도 스트리밍 텍스트로 바꾸지 않는다). 오류·취소면 `answer`에 그때까지 스트리밍된 텍스트 전체(`retry` 앞뒤 포함)를, `partial`에 그 텍스트가 있는지를 저장한다. `agent`·`model`·`selector`는 실제 실행(`start` 이벤트, 마지막 후보)으로 갱신한다.

### 하이라이트 규칙

서버가 근거 위치를 계산하고, 클라이언트는 돌려받은 정규식·용어만 pdf.js 텍스트 레이어에서 찾는다.

1. 근거 대상: 출처가 이 논문의 PDF(경로 또는 `PDF`)이거나 이 논문의 리뷰(`#` 앞 경로가 `review_path`)인 근거다. 다른 논문의 PDF·리뷰 근거는 대상을 만들지 않는다.
2. locator를 `;`로 나눈다. 조각마다 쪽: `pp?\.\s*(N([-–]M)?(\s*,\s*N([-–]M)?)*)`. 쪽이 없는 조각은 문서 전체에서 찾는다.
3. 앵커(정규화된 텍스트에 대한 `pattern`, Python·JS 공용):
   - Table `table N`(`Table 1-6`은 번호마다), Figure `fig(ure)?.? N`, Equation `\(N\)`(신뢰도 낮음), Algorithm `algorithm N`
   - Section `§x.y`(`§3.1-3.2`는 번호마다, 뒤의 영어 제목 단어 포함), Appendix `App(endix)? X(.n)`(`D–F`, `E.1–E.4`는 하나씩), Heading: Abstract·Introduction·Limitations·Conclusion·References
   - Section·Appendix·Heading은 서버가 원문 줄 머리(또는 단 사이 공백 뒤)의 `x.y 제목`으로 찾고, 찾으면 `pattern`을 실제 제목 단어로 좁혀 보낸다(예: `(?:^|\s)3\.3\.?\s+adaptive\s+curriculum\s+learning`).
   - 무시: `l.8-9`, `본문`, `(a)-(b)`
4. 진술에서 용어(합쳐서 8개 이하, 순서대로): `"…"`·`“…”`·`'…'` 안의 라틴 문자열(→ `quotes`) → 라틴 단어 2개 이상 연속 → 식별자(CamelCase, 대문자, 숫자 포함, 3자 이상, 불용어 제외) → 소수(`87.9`) → 2자리 이상 정수(`1,000` → `1000`). locator 토큰의 숫자와 한 자리 숫자는 뺀다. 1900–2099의 4자리 정수(인용 연도 `2026`, 접미사 붙은 `2025a` 포함)도 `terms`에서 뺀다. 인용문 안에 있을 때만 `quotes`의 일부로 남는다. 천 단위 쉼표가 있는 수(`1,950`)는 연도로 보지 않는다. `terms`·`quotes`는 정규화된 일반 문자열이다.
5. 정규화: NFKC, 소문자, 줄바꿈으로 나뉜 하이픈 단어 잇기, 공백 하나로 합치기.
6. 쪽마다 신뢰도: 인용 발견 `quote` → 앵커 발견 `anchor` → 서로 다른 용어 2개 이상 `terms` → 쪽 존재 `page` → 쪽도 없고 앵커도 못 찾음 `unresolved`(`page: null`). 대상의 `terms`·`quotes`는 그 쪽에서 찾은 것만 준다(텍스트가 없으면 전부).
7. 재배치: 적힌 쪽에 앵커가 없으면 ±1쪽, 그다음 문서 전체에서 가장 가까운 쪽을 쓰고 `relocated_from`에 적힌 쪽을 넣는다. 쪽 수보다 큰 쪽은 바로 재배치한다(캡션처럼 `:`·`.`가 뒤따르는 첫 적중 우선). 어디서도 못 찾으면 적힌 쪽에 `anchor: null` 대상을 만든다. 앵커 없는 조각의 쪽이 쪽 수보다 크면 인용·용어가 가장 많이 맞는 쪽으로 옮긴다.
8. 주장 상태: 대상 중 `quote`·`anchor`·`terms`가 있으면 `matched`, `page`만 있으면 `page_only`, 아니면 `unresolved`.
9. 클라이언트는 그 쪽의 정규화된 pdf.js 텍스트에서 바늘을 찾아 DOM Range의 `getClientRects()`로 사각형을 그리고, 쪽 비율로 저장해 확대·축소에도 맞춘다. 못 찾으면 쪽 여백 표시를 보여 준다.

알려진 실패(모두 쪽 표시로 떨어지며 사라지지 않는다): 예전 리뷰의 인쇄 쪽 번호, PDF에 없는 재계산 값(`36.95`), 그림 앵커는 캡션만 강조, `(5)`가 다른 괄호 숫자와 겹침, 두 단에 걸친 인용, 스캔 PDF(텍스트가 없어 모두 `page`), pdftotext와 pdf.js의 추출 차이.

## 하네스

WebUI `#/harness` 화면의 데이터와 검사 실행이다. 데이터는 정적 `100-views/harness-dashboard.html`과 같은 `harness_dashboard.dashboard_data(reviews.ROOT)`에서 나오며, 이 화면은 정본 파일을 수정하지 않는다.

### `GET /api/harness`

```jsonc
// HarnessPayload
{"guide": {"paths": [/* .scripts/docs/research-workflow-map.json의 "paths" 그대로 */],
           "skills": [{"name", "title", "description", "source": ".agents/skills/<name>/SKILL.md",
                       "instructions": "<SKILL.md 전문>" | null,
                       "uses": [{/* 단계 객체 */, "path_id", "path_title", "order": 1}]}]},
 "routing": [{"stage", "next", "reason"}],          // research_workflow.WORKFLOW 순서(import, 하위 프로세스 없음)
 "skill_links": [{"name", "source", "source_exists": true, "claude": "linked|missing",
                  "codex": "linked|missing", "omp": "direct|missing"}],
 "omp_agents": [{"name", "path": ".omp/agents/<name>.md", "description": "…" | null}],  // frontmatter description
 "personas": [{"name", "path"}],
 "validators": [{"name", "path", "exists": true}],
 "tests_path": ".scripts/tests/test_harness_tools.py",
 "graphify": {"path": "graphify-out/sync-state.json", "exists": true, "total": 11,
              "by_status": {"pending": 1, "success": 10}, "pending": 1, "error": null | "…"},
 "checks": [{"check": "verify", "label": "하네스 구조 검사", "command": "python3 .scripts/bin/verify_harness.py"},
            {"check": "tests", "label": "하네스 테스트", "command": "python3 -m unittest discover -s .scripts/tests"}],
 "links": {"router", "harness_graph", "workflow_map", "graphify_sync", "installer_doc", "installer"},  // 저장소 상대 경로
 "hrefs": {"<위의 모든 경로(단계 source 포함)>": "/<URL 인코딩 경로>" | null},
 "errors": [{"section": "guide|routing|skill_links|omp_agents|personas|validators|graphify|hrefs", "error": "…"}]}
```

- `hrefs` 값은 아래 "정적 파일" 규칙으로 이 서버가 그 경로를 제공할 때만 문자열이다. `.omp/agents/…`처럼 허용 루트 밖이거나 없는 파일은 `null`이고, 화면은 경로만 보여 준다.
- 파일 본문은 정적 파일 경계를 넘지 않는다. 워크플로 맵과 `sync-state.json`은 **읽기 전에** 같은 정책(`security.resolve_static`: 허용 루트, 민감 이름, 대소문자, 심볼릭 링크의 실제 대상)을 통과한 일반 파일일 때만 연다. 맵이 거부되면 `guide`가 비고 `errors`에 `{"section": "guide", "error": "<경로>: 정적 파일 정책 밖 경로라 읽지 않습니다."}`가 남는다. `sync-state.json`이 거부되면 `graphify.error`에 사유가 들어간다.
- `SKILL.md`는 전용 규칙(`harness_dashboard._skill_file`)으로 읽는다. 공유 스킬은 `.agents/skills/<name> -> ../../200-ARIS/upstream/skills/…`처럼 스킬 폴더 자체가 심볼릭 링크로 설치되고 그 실제 대상이 정적 허용 루트 밖이라, 정적 정책으로는 읽을 수 없기 때문이다. 조건: `.agents`·`.agents/skills`는 심볼릭 링크가 아닌 실제 폴더이고, 심볼릭 링크는 `<name>` 항목에만 허용하며 그 실제 대상은 저장소 실제 경로 안이고 어느 조각도 민감 이름(`.git`, `.claude`, `.codex` 등 아래 "정적 파일" 목록)이 아니어야 한다. 그 폴더의 `SKILL.md`는 심볼릭 링크가 아닌 일반 파일이어야 하고, 이 이름의 파일만 읽는다. 거부된 `SKILL.md`는 열지 않고 `instructions: null`, `title`은 스킬 이름, `description`은 `설명 미기록`이며 `errors`에 같은 형식의 오류를 남긴다. 이 규칙은 응답 본문에만 적용되고 정적 파일 제공은 바꾸지 않는다. 따라서 공유 스킬의 `hrefs` 값은 `null`이다.
- `.omp/agents`는 정적 파일로 제공하지 않는다. 에이전트 `description`은 파일의 실제 경로가 정확히 `<저장소 실제 경로>/.omp/agents/<name>.md`(경로 어디에도 심볼릭 링크 없음)인 일반 파일일 때만 앞 64 KiB의 frontmatter에서 읽고, 아니면 `null`이다.
- 데이터 오류(맵 JSON 깨짐, 디렉터리 없음, `sync-state.json` 깨짐 등)는 500이 아니다. 그 구역만 빈 값으로 두고 `errors`에 적는다. `sync-state.json`을 읽지 못하면 `graphify.error`에도 사유가 들어간다.
- 응답 크기는 SKILL.md 전문을 포함해 약 1.6 MB(스킬 103개 기준)다. 정적 `harness-dashboard.html`도 같은 데이터로 생성한다.

### `POST /api/harness/checks`

표준 가드(CSRF, Origin, JSON, 64 KiB)를 거친다. 서버에 고정된 두 명령만 실행한다.

| 상태 | 코드 | 조건 |
|---|---|---|
| 202 | — | `{"job": record}`. `kind: "harness.verify"\|"harness.tests"`, `agent: null`, `role`·`slug` 없음 |
| 400 | `bad_request` | `check`가 없거나 문자열이 아니거나 두 값이 아님(`check must be one of: verify, tests`) |
| 503 | `shutting_down` | 서버 종료 중(`broker.closing`) |
| 409 | `check_active` | 대기·실행 중인 `harness.*` 작업이 있음(검사는 한 번에 하나) |

- 검사 순서는 400 → 503 → 409다. 활성 검사 확인과 제출은 서버 잠금 하나 안에서 한 번에 일어난다.
- 명령: `harness_dashboard.check_command(check, ROOT)`. `verify`는 `[python, ROOT/.scripts/bin/verify_harness.py]`, `tests`는 `[python, -m, unittest, discover, -s, .scripts/tests]`. `cwd=ROOT`, stdout+stderr 합침, UTF-8(잘못된 바이트는 대체 문자), 새 프로세스 그룹, `PYTHONUNBUFFERED=1`.
- 이벤트: 출력을 최대 2,048자씩(줄바꿈에서 먼저 끊음) 읽어 조각마다 `text_delta`를 보낸다. 조각 하나는 UTF-8로 8 KiB 이하이고, 개행 없는 긴 출력도 이 크기로 나뉜다. 한 작업의 `text_delta` 합계는 UTF-8 256 KiB 이하다. 다음 조각이 상한을 넘으면 안내 문구 `text_delta` 하나(`[실시간 출력이 256 KiB 상한에 도달해 표시를 멈춥니다. 검사는 계속 실행됩니다.]`)를 보내고 그 뒤로는 보내지 않지만 출력은 계속 읽는다. 종료 이벤트는 아래 하나다.
  - 종료 코드 0: `result` — `text`는 전체 출력의 UTF-8 기준 마지막 256 KiB(경계에서 잘린 문자는 버림), `cost_usd: null`, `usage: null`, `duration_ms`.
  - 0이 아닌 종료 코드: `error` — `message`는 `"<label> 실패 (exit N)"`과 출력 마지막 2,000자, `retryable: true`, `kind: "process"`.
  - 제한 시간 초과(`verify` 300초, `tests` 1,800초): `error` — `message`는 `"<label> 시간 초과 (N초)"`와 출력 마지막 2,000자, `retryable: true`, `kind: "timeout"`.
  - 취소(`POST /api/jobs/{id}/cancel`): `cancelled`.
- 취소·시간 초과·서버 종료는 리더 프로세스가 아니라 **프로세스 그룹 전체**를 끝낸다. 그룹에 SIGTERM을 보내고, 그룹의 모든 프로세스가 사라질 때까지(`killpg(pgid, 0)`이 `ProcessLookupError`) 최대 2.5초 기다린 뒤, 남아 있으면 그룹에 SIGKILL을 보내고 최대 1초 더 기다린다. 리더가 먼저 끝나거나 stdout이 닫혀도 이 단계를 건너뛰지 않으며, 이 단계가 끝난 뒤에야 종료 이벤트를 보낸다. 그때까지 작업은 `running`이므로 새 검사는 409 `check_active`다.
- `server_close`는 대기·실행 중인 `harness.*` 작업을 취소하고, 리더 종료와 함께 최대 5초 기다린다.

## 사고실험

WebUI `#/ideas` 화면의 데이터다. 아이디어 레코드는 정적 `100-views/thought-experiments.html`과 같은 `thought_experiments_html.scan(reviews.ROOT, errors)`에서 나오고(구현 `webui/server.py`의 `ideas_data`), 이 화면은 정본 파일을 수정하지 않는다. 읽는 곳: `05-Ideas/thought-experiments/*.md`(노트), `04-Projects/thought-experiment-runs/<run>/`(실행 기록·`analysis.json`), 같은 폴더의 `CRITICAL_VALIDATION_REGISTRY.md`, `04-Projects/research-todo/queue.json`, `01-Papers/library/*.json`(`paper_id` → 레코드 경로).

### `GET /api/ideas`

```jsonc
// IdeasPayload
{"ideas": [Idea],
 "hrefs": {"<ideas에 나온 모든 경로>": "/<URL 인코딩 경로>" | null},
 "errors": [{"section": "registry|library|todo_queue|idea:<id>|hrefs|ideas", "error": "<저장소 상대 경로>: <예외 종류>: <메시지>"}]}

// Idea: 정적 페이지에 들어가는 객체와 같다. 상태 값은 기록이 없으면 "미기록"이다.
{"id": "<노트 파일 이름(확장자 제외)>", "title", "hypothesis", "falsification", "topics", "updated": "YYYY-MM-DD",
 "literature", "review": "method: …, repro: …, novelty: …", "decision", "experiment": "기록 있음|미기록",
 "note", "brief", "results", "todo": "docs/agent-research-todo.md", "manifest", "analysis",  // 저장소 상대 경로, 없으면 ""
 "registry": {"slug", "grill", "method", "repro", "novelty", "overall", "decision", "evidence", "updated"} | {},
 "validation", "noteDecision", "noteStatus", "decisionConflict": false, "statusConflict": false,
 "critiques": ["…"], "evidence": ["…"], "papers": ["<paper_id>"], "paperPaths": ["01-Papers/library/<slug>.json"],
 "artifacts": ["…"], "todoStatus": "open, done" | "미기록", "todoTasks": ["<task_id>"], "todoResults": ["…"]}
```

- 아이디어가 없으면 `{"ideas": [], "hrefs": {}, "errors": []}`다(현재 저장소의 실제 상태).
- `hrefs` 키는 각 아이디어의 `note`·`brief`·`results`·`todo`·`manifest`·`analysis`와 `critiques`·`evidence`·`paperPaths`·`artifacts`·`todoResults`의 비어 있지 않은 문자열 경로다. 값은 "정적 파일" 규칙(`security.resolve_static`)으로 이 서버가 제공할 때만 문자열이고, 없거나 허용 루트 밖이면 `null`이다(`/api/harness`의 `hrefs`와 같은 정책).
- `decisionConflict`·`statusConflict`는 노트의 `사용자 결정:`·`상태:` 줄이 레지스트리 행과 다를 때 true다. 서버는 어느 쪽도 고치지 않는다.
- 데이터 오류는 500이 아니다. 해당 부분만 비우고 `errors`에 적는다.
  - `queue.json`이 깨짐: `todo_queue` 오류 하나. 모든 아이디어의 `todoStatus`는 `미기록`, `todoTasks`·`todoResults`는 빈 목록이다. 문구는 JSON 오류면 `04-Projects/research-todo/queue.json: JSONDecodeError: …`, 최상위가 객체가 아니면 `…: ValueError: queue is not an object`, `tasks`가 목록이 아니면 `…: ValueError: tasks is not a list`다(`tasks`가 없으면 빈 목록으로 본다).
  - 작업 하나가 잘못됨(객체가 아님, 있는 `idea_path`·`status`·`task_id`·`result_path` 중 문자열이 아닌 값): 그 작업만 건너뛰고 작업마다 `todo_queue` 오류 하나를 남긴다. 문구는 `04-Projects/research-todo/queue.json: ValueError: tasks[<번호>]: task is not an object` 또는 `…: tasks[<번호>]: not a string: status, task_id`다. 다른 작업과 아이디어는 그대로다. 없는 필드는 정적 페이지처럼 기본값(`status`는 `unknown`, 나머지는 `""`)을 쓴다.
  - 레지스트리를 읽지 못함: `registry`. 모든 아이디어의 `registry`는 `{}`, 레지스트리 값은 `미기록`으로 둔다.
  - `analysis.json`이 깨짐(JSON 오류, 객체가 아님, 구조가 다름): `idea:<id>`, 오류 경로는 그 `analysis.json`. 그 아이디어만 분석 내용을 `{}`로 보고 목록에 남긴다(`review`·`decision`은 레지스트리 값 또는 `미기록`, `literature`는 `미기록`, `papers`는 빈 목록). `analysis` 필드에는 경로가 그대로 남는다. 다른 아이디어는 영향이 없다.
  - 노트를 읽지 못함(UTF-8 아님 등)이나 분석 없이도 레코드를 만들 수 없음: `idea:<id>`. 그 아이디어는 목록에서 빠진다.
  - 논문 레코드가 객체가 아니거나 UTF-8이 아님: `library`. 그 레코드만 `paperPaths` 대응에서 빠진다(JSON 문법 오류는 정적 페이지처럼 조용히 건너뛴다).
  - 그 밖의 예상하지 못한 예외: `ideas`(오류 문구는 `<예외 종류>: <메시지>`), `ideas: []`, `hrefs: {}`.
- 오류 문구는 500자에서 자른다. 정적 생성기(`python3 .scripts/bin/thought_experiments_html.py`)는 `errors` 없이 `scan()`을 부르므로 같은 오류에서 예전처럼 실패한다.

## 정적 파일

- `webui/reviews.py`의 `ALLOWED_ROOTS`(예: `01-Papers/`, `docs/`, `100-views/`, `.scripts/`)와 `ALLOWED_ROOT_FILES`(`AGENTS.md`, `CLAUDE.md`, `README.md`) 아래만 제공한다.
- percent-decoding 뒤 NUL, 역슬래시, `.`·`..`·빈 경로 조각이 있으면 404다.
- 경로의 각 조각이 디스크의 실제 이름과 대소문자까지 같아야 한다. 대소문자 변형(`/100-VIEWS/…`)은 404다.
- 심볼릭 링크를 따라 resolve한 경로가 저장소 밖이거나 허용 목록 밖이면 404다.
- `.git`, `.env*`, `.mcp.json`, `.secrets`, `credentials.json`, `.claude`, `.codex`, `.research-harness-agent.json`, `reader-threads`(논문 리더 스레드)는 허용 경로 안에 있어도 404다.
- `01-Papers/reviews/` 아래 어느 깊이든 `figures` 조각(대소문자 무시)이 있는 경로와 그 아래 모든 경로(리뷰 그림 `*.html`·`*.svg`, 하위 폴더 리뷰의 `…/nested/figures/` 포함)는 404다. 심볼릭 링크의 실제 대상이 그 아래여도 404다. 에이전트가 만든 HTML·SVG가 CSP 없이 같은 출처에서 실행되지 않도록, SVG만 위 "리뷰 그림" API로 제공한다.
- 디렉터리 목록은 보여주지 않는다. 슬래시 없는 디렉터리 요청은 301로 슬래시를 붙이고, `index.html`이 없으면 404다.

## 작업 레코드

```json
{"job_id": "…", "kind": "agent.ping|paper.ask|harness.verify|harness.tests", "status": "queued|running|completed|failed|cancelled",
 "created_at": "2026-11-03T07:00:00+00:00", "started_at": null, "ended_at": null,
 "agent": "claude", "cost_usd": null, "error": null, "last_seq": 0, "role": "paper-analyst"}
```

`role`은 역할 작업(`agent.ping`의 `role`, `paper.ask`의 `paper-reader`)에만, `slug`는 `paper.ask`에만 있다. `harness.*` 작업은 `agent: null`이고 `role`·`slug`가 없다.

- 시각은 ISO-8601 UTC 초 단위다. 작업은 메모리에만 있으며 서버를 끄면 사라진다.
- 동시에 최대 2개를 실행하고 나머지는 FIFO로 기다린다. 작업당 이벤트는 최근 10,000개까지 보관한다.
- 상태는 종료 이벤트로 정한다: `result` → `completed`, `error` → `failed`, `cancelled` → `cancelled`. 작업 함수가 예외를 내면 `error`, 종료 이벤트 없이 끝나면 `error` "job ended without result"를 기록한다. 취소 요청 뒤 종료 이벤트 없이 끝나면 `cancelled`다.
- 종료 이벤트는 정확히 하나다. 처음 기록된 종료 이벤트가 이기고, 그 뒤의 이벤트(종료 이벤트 포함)는 버린다.
- 취소는 브로커 잠금 안에서 결정한다. 대기 중인 작업은 큐에서 빠지는 것과 `cancelled` 기록이 한 번에 일어나므로, 동시에 들어온 두 번째 취소는 409 `already_finished`를 받는다. 실행 중인 작업은 취소가 받아들여진(202) 뒤 작업이 `result`나 `error`를 내도 `cancelled`로 기록한다.
- `agent`는 `start` 이벤트의 실제 에이전트로, `cost_usd`는 `result` 이벤트 값으로, `error`는 `error` 이벤트 메시지로 갱신한다.

`agent.ping`은 임시 폴더에서 도구 없이 "Reply with exactly: OK"를 보내는 연결 확인 작업이다(제한 시간 120초). 에이전트가 설치·로그인되지 않았으면 종료 이벤트 `error`(`retryable: false`)로 끝난다. `role`을 주면 그 역할의 후보(실행기·모델·effort)로 보내고 위의 후보 이동 규칙을 따른다. 작업 레코드에 `role`이 붙고 `agent`는 선택 후보의 실행기다(`role` 없는 작업에는 `role` 키가 없다). 미설정 `paper-analyst`는 연결 에이전트로, 미설정 `paper-verifier`는 `error`로 끝난다. 설정됐지만 준비된 후보가 없으면 그 사유로 `error`다.

## 작업 이벤트 (SSE)

`GET /api/jobs/{id}/events`는 `text/event-stream`이다. 이벤트 하나는 다음 형식이다.

```
id: <seq>
event: <type>
data: <JSON>

```

- `seq`는 1부터 단조 증가한다.
- 재연결 시 `Last-Event-ID` 헤더(우선) 또는 `?after=<seq>` 쿼리 이후의 이벤트부터 다시 보낸다. 정수가 아니면 400이다. `EventSource`는 자동으로 `Last-Event-ID`를 보낸다.
- 요청한 이벤트가 이미 버퍼(작업당 10,000개)에서 밀려났으면, 남은 이벤트보다 먼저 `gap` 이벤트 하나를 보낸다. `id`는 남은 가장 오래된 seq − 1이고 `data`는 `{"type": "gap", "missed_from": <after+1>, "missed_to": <가장 오래된 seq − 1>}`이다. `gap`은 종료 이벤트가 아니며 버퍼에 저장하지 않는다. 느린 구독자가 스트림 도중 뒤처져도 같은 방식으로 보낸다. 클라이언트는 기록 누락을 표시하고, `result`를 받으면 `result.text`를 최종 답으로 쓴다.
- 새 이벤트가 없으면 15초마다 `: ping` 주석을 보낸다.
- 종료 이벤트를 보낸 뒤 연결을 닫는다. 브라우저가 연결을 끊으면 서버는 조용히 정리한다.
- 서버 전체에서 동시에 열린 스트림은 최대 32개다. 넘으면 스트림을 열지 않고 503 `too_many_streams`(JSON)로 답한다. `EventSource`는 200이 아닌 응답에 재연결하지 않으므로, 클라이언트는 다른 스트림을 닫은 뒤 다시 연다.

이벤트 `data`(LLM 실행기가 정규화한 형식):

| type | 필드 | 종료 여부 |
|---|---|---|
| `start` | `agent`, `model`, `session_id` | 아니오(첫 이벤트) |
| `text_delta` | `text` | 아니오 |
| `message` | `text` (완성된 assistant 메시지 하나) | 아니오 |
| `tool_use` | `name`, `summary` (200자 이하, 전체 입력은 보내지 않음) | 아니오 |
| `retry` | `attempt`, `delay_ms`; 역할 후보 이동이면 `reason: "usage_limit"`, `next` | 아니오 |
| `result` | `text`, `cost_usd`, `duration_ms`, `usage`; claude `--json-schema` 실행이면 `structured_output` | 예 |
| `error` | `message`, `retryable`, `kind` | 예 |
| `cancelled` | — | 예 |
| `gap` | `missed_from`, `missed_to` (빠진 seq 범위, 양 끝 포함) | 아니오(재생 표시, 저장 안 함) |

`error.kind`는 `usage_limit`·`auth`·`timeout`·`process`·`other` 중 하나다. 명시적 신호만 `usage_limit`으로 본다: claude 결과의 `api_error_status` 429, 상태가 `rejected`인 `rate_limit_event`, 또는 실패 문구(claude 결과 텍스트, codex `turn.failed`·오류 항목·오류 이벤트, omp 오류 메시지, stderr)가 `usage limit`·`rate limit`(`rate_limit`·`rate-limit`)·`quota`·`too many requests`·`hit your limit`·`limit reached`와 맞을 때(대소문자 무시). `auth`는 HTTP 401·403 또는 `authenticat`·`unauthorized`·`not logged in`·`please log in`·`login required`·`invalid api key`·`invalid x-api-key`·`oauth token`이다. `timeout`은 서버 제한 시간 초과, `process`는 실패 이벤트 없이 0이 아닌 종료 코드로 끝난 경우다. 정확한 패턴은 `webui/llm.py` 문서 주석에 있다.
