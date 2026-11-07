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
| GET | `/api/status` | 기존 브리지와 같은 키: `ok`, `workspace_id`, 에이전트 상태 필드(`agent`, `ready`, `reason`, `candidates` 등), `pdf_reader_ready`, `runner`, `pdf_reader`, `max_parallel`, `queue`. 추가 키 `review_roles`: `{"generation": <역할 해석>, "verification": <역할 해석>}`(아래 "리뷰 역할"), `reader_role`: `paper-reader`의 역할 해석(아래 "논문 리더"), `searcher_role`: `paper-searcher`의 역할 해석(아래 "논문 탐색"). `ready`·`reason`은 리뷰 준비 상태로, 역할이 설정되어 있으면 역할 기준이다. |
| GET | `/api/reviews/{slug}` | `{"jobs": [...]}` — 리뷰 큐에서 해당 slug의 작업. 검증 보고서가 있으면 `verification`(아래 "검증 보고서")도 준다. |
| POST | `/api/reviews` | 본문 `{"slug"}`. 리뷰 한 편을 큐에 넣고 202 `{"job"}`. 이미 완료면 409 `review_complete`, 다른 리뷰 진행 중이면 409 `review_active`, 에이전트·리뷰 역할 미준비면 503 `agent_unavailable`, 잘못된 slug·PDF면 400 `bad_request` |
| POST | `/api/reviews/{slug}/verify` | 본문 `{}`. 이미 리뷰된 논문에 검증 단계만 실행하고 202 `{"job"}`(큐 작업 `kind: "verify"`). 잘못된 slug·레코드는 400 `bad_request`, 리뷰 Markdown이 없으면 409 `review_missing`, PDF가 없으면 409 `pdf_missing`, 역할 설정을 읽지 못하면 503 `role_config_error`, `paper-verifier` 미설정이면 409 `verifier_unconfigured`, 설정됐지만 실행기 미준비면 503 `verifier_unavailable`, 다른 리뷰·검증 진행 중이면 409 `review_active` |
| GET | `/api/jobs` | `{"jobs": [record…]}` (최신순) |
| POST | `/api/jobs` | 본문 `{"kind": "agent.ping", "agent"?: "claude"\|"codex"\|"omp", "role"?: "paper-analyst"\|"paper-verifier"}` → 202 `{"job": record}`. `agent`와 `role`은 함께 쓸 수 없다. 모르는 kind(`paper.ask`·`harness.*`·`discovery.*` 포함 — 검색은 `POST /api/discovery/searches`, 등록은 `POST /api/discovery/register`로만 제출)·agent·role, 문자열이 아닌 값(배열·객체·숫자 등), `agent`+`role` 동시 지정은 400 `bad_request` |
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
| GET | `/api/discovery/daily` | `{"days": [DailySummary], "errors": [{"file", "error"}]}`(아래 "논문 탐색") |
| GET | `/api/discovery/daily/{date}` | `{"daily": Daily, "plan_href": str\|null}`. 날짜 형식 400 `bad_request`, 없음 404 `not_found` |
| GET | `/api/discovery/searches` | `{"searches": [SearchSummary], "errors": [{"file", "error"}]}`. 재시작 정합 적용 |
| POST | `/api/discovery/searches` | 검색 요청 → 202 `{"job": JobRecord, "search": SearchSession}`(아래 "논문 탐색"). 400 `bad_request`, 409 `search_active`, 503 `role_config_error`·`searcher_unavailable`·`shutting_down` |
| GET | `/api/discovery/searches/{id}` | `{"search": SearchSession}`. 잘못된 id 400 `bad_request`, 없음 404 `not_found` |
| DELETE | `/api/discovery/searches/{id}` | 본문 `{}` → 200 `{"deleted": id}`. 400, 404, 진행 중이면 409 `search_active` |
| POST | `/api/discovery/keep` | "Keep에 담기" → 200 `{"candidate", "slug", "keep_path", "record_path"}`(아래 "논문 탐색"). 400, 404 `not_found`·`candidate_not_found`, 409 `already_in_library`·`already_in_keep`, 500 `write_failed` |
| POST | `/api/discovery/register` | "등록" → 202 `{"job": JobRecord, "candidate", "slug"}`. 400, 404, 409 `already_in_library`·`review_active`·`register_active`, 503 `role_config_error`·`searcher_unavailable`·`shutting_down` |
| POST | `/api/discovery/candidates/status` | 넘김·복원 `{"source", "candidate_id", "status": "skipped"\|"new"}` → 200 `{"candidate"}`. 400, 404, 409 `candidate_adopted` |
| POST | `/api/discovery/related` | 인용·피인용 `{"kind": "refs"\|"cites", "paper": {"slug"}\|{"title", "ids"}, "limit"?}` → 201 `{"search": SearchSession}`(mode `related`, 동기). 400 `bad_request`·`no_identifier`, 404 `not_found`, 502 `upstream_unavailable`, 503 `upstream_rate_limited`, 504 `upstream_timeout`, 500 `write_failed`·`cache_unsafe`(아래 "논문 탐색") |

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

## 논문 탐색

WebUI `#/discover` 화면의 데이터다. 외부 검색 결과와 일일 후보는 Git에서 제외된 로컬 캐시 `00-Inbox/discovery/`에만 있다(위키·라이브러리·Graphify 대상 아님). 구현은 `.scripts/bin/discovery_cache.py`(스키마·검증·정규화·라이브러리 대조·학회 참고·CLI)와 `webui/discovery.py`(읽기 API·검색·등록 작업·Keep 작성기), 라우팅은 `webui/server.py`다. 이 화면의 GET 라우트는 정본 파일을 수정하지 않는다(아래 재시작 정합만 캐시 파일을 고친다). 검색(`POST /api/discovery/searches`)은 에이전트 작업으로 실행하고 결과는 캐시에만 쓴다. 정본 파일(PDF·Keep·논문 JSON·인덱스)은 사용자가 후보를 채택했을 때만 서버가 쓴다: "Keep에 담기"(`POST /api/discovery/keep`)와 "등록"(`POST /api/discovery/register`). 아래 "후보 채택" 절들을 본다.

### 캐시 위치·안전

```
00-Inbox/discovery/
  README.md                  # Git 추적(유일)
  daily/{YYYY-MM-DD}.json    # Daily — daily-digest-loop가 discovery_cache.py daily-write로 기록
  searches/{search_id}.json  # SearchSession — 검색 1회 = 파일 1개 (mode: search | related)
```

- 읽고 쓰기 전에 `00-Inbox`·`discovery`·`daily|searches`가 심볼릭 링크가 아닌 실제 디렉터리이고 실제 경로가 정확히 저장소의 그 경로인지 확인한다. 아니면 500 `cache_unsafe`다. 캐시 파일은 링크를 따라가지 않고(`O_NOFOLLOW|O_NONBLOCK`) 열며 일반 파일이 아니면 `cache_unsafe`다(목록에서는 그 파일만 `errors`). 폴더가 없으면 목록은 빈 값, 상세는 404다. 쓰기만 폴더를 만든다.
- 쓰기는 임시 파일 + 교체(`harness_common.write_json_atomic`)로 원자적이다. `daily-write`(바꾸기 없음)는 임시 파일을 `os.link`로 게시해 이미 있는 날짜를 덮어쓰지 않는다. 서버 쪽 읽기-수정-쓰기는 모듈 잠금 `webui/discovery.LOCK` 하나 아래에서 한다.
- 일일 파일은 다른 프로세스(`discovery_cache.py daily-write --replace`)도 읽고-합쳐-쓰므로 날짜별 프로세스 간 잠금 `discovery_cache.daily_lock`(`daily/.{YYYY-MM-DD}.lock`에 배타 `fcntl.flock`, 링크를 따라가지 않고 `0600`으로 만들며 지우지 않음, 심볼릭 링크·일반 파일 아님이면 `cache_unsafe`)을 쓴다. CLI `daily-write`는 이전 파일을 읽을 때부터 기록까지, 서버는 일일 후보의 상태 변경·Keep·등록 게시에서 `LOCK` 다음에 이 잠금을 쥔다. 그래서 `--replace`가 그사이 WebUI가 저장한 후보 상태를 지우지 않는다. 검색 기록은 이 서버만 쓰므로 `LOCK`만 쓴다.
- 정적 파일로 제공하지 않는다(아래 "정적 파일"). 캐시는 이 API로만 읽는다.

### 스키마

문서용 JSON Schema는 [discovery-cache.schema.json](discovery-cache.schema.json)이고 정본은 `discovery_cache.py`의 검증 함수다. `schema_version`은 `"1.0"`이다.

```jsonc
// Candidate — 저장 형식(모든 키가 항상 있다)
{"candidate_id": "c_<12hex>", "title": "…(≤500)", "authors": ["…"](≤50), "year": 2026 | null, "venue": "…" | null,
 "publication": {"status": "published|accepted|preprint|unknown", "verified": false, "verification_sources": ["…"](≤10)},
 "citations": 12 | null, "ids": {"arXiv": "2603.25158" | null, "DOI": "10.…" | null, "S2": "…" | null, "OpenAlex": "…" | null},
 "url": "https://…" | null, "abstract": "…(≤5000)" | null, "relevance": "…(1–2문장, ≤600)",
 "sources": ["s2|arxiv|openalex|web"], "suggested_category": "wifi-csi|game-ai|agent-ai|computer-vision|other" | null,
 "topics": ["…"](≤10), "conference_ref": {"abbr": "EMNLP", "name": "…", "score": 0.95 | null} | null,
 "status": "new|keep|registered|skipped", "status_updated_at": "…" | null, "slug": "…" | null,
 "library": {"slug": "…", "match": "id|title"} | null}   // library는 읽기 응답에만 있다(저장 안 함)

// Daily — daily/{date}.json
{"schema_version": "1.0", "date": "2026-11-07", "created_at": "2026-11-07T00:00:00+00:00", "plan_path": "03-Trends/daily/2026-11-07-plan.md" | null,
 "slots": [{"slot": "computer-vision|multimodal|interest", "topic": "…" | null, "candidate": Candidate | null, "unfilled_reason": "…" | null}],
 "report": {"queries": ["…"], "sources": ["…"], "coverage_gaps": ["…"], "notes": "…"}}

// SearchSession — searches/{search_id}.json (M1은 읽기만, 생성은 M2)
{"schema_version": "1.0", "search_id": "s_<12hex>", "mode": "search|related", "created_at": "…",
 "status": "queued|running|completed|failed|cancelled", "job_id": "…" | null,
 "request": {"query", "year_from", "year_to", "limit", "category_hint", "anchors": [slug], "verified_only"}   // mode search
          | {"kind": "refs|cites", "paper": {"slug": "…" | null, "title", "ids": {…}}, "limit"},            // mode related
 "agent": {"agent", "model", "selector"} | null,
 "report": {"queries", "sources", "anchors": [{"title", "ids"}], "coverage_gaps", "excluded_count", "notes"} | null,
 "candidates": [Candidate], "error": {"message", "kind"} | null, "duration_ms": 1234 | null}
```

- **한도**: 제목 500·초록 5,000·관련 이유 600·저자 50명(각 200)·주제 10개(각 100)·검증 출처 10개(각 500)·venue 300·`ids` 각 200·`url` 2,000·슬롯 주제 200·미채움 이유 600·보고 목록 50개(각 500)·notes 5,000·`plan_path` 300(문자 수).
- **검증**(`validate_candidate`·`validate_daily`·`validate_session`): 구조·타입·열거값·필수 키와 위 한도를 본다. 한도를 넘으면 오류다(저장된 파일·`validate` 명령·쓰기 직전 검사). 알 수 없는 키는 오류다. Daily의 `slots`는 정확히 3개이고 `computer-vision`·`multimodal`·`interest`가 하나씩이다(입력 순서 무관, 저장은 이 순서). 후보가 `null`인 슬롯은 `unfilled_reason`이 비어 있으면 안 된다. 같은 날 두 슬롯이 같은 `candidate_id`면 오류다. `year`는 1800–2100, `ids.arXiv`·`ids.DOI`는 형식이 맞아야 한다. `plan_path`는 `/`로 시작하지 않고 `..`·역슬래시가 없는 저장소 상대 경로다.
- **정규화**(`normalize_candidate`·`prepare_daily`): 신뢰하지 않는 생산자 입력(에이전트 출력, `daily-write` 입력)은 한도 없이 구조만 검증(`limits=False`)한 뒤 제어문자(탭·줄바꿈 제외) 제거, 한 줄 필드 공백 축약, 한도 초과 **잘라냄**으로 정리한다. 결과는 위 검증을 통과한다. `url`은 `https://`가 아니면 `null`. DOI는 `10\.\d{4,9}/\S+`(대소문자 유지, 끝 문장부호 제거), arXiv는 `\d{4}\.\d{4,5}`(버전·`arXiv:`·URL 제거).
- **candidate_id**: `"c_" + sha256(key)[:12]`, key는 `doi:<casefold DOI>` > `arxiv:<버전 제거 id>` > `s2:<id casefold>` > `title:<정규화 제목>`. 정규화 제목은 NFKC → casefold → 영숫자 외 문자를 공백으로 → 공백 축약이다. 한 세션 안 중복은 `merge_candidates`가 처음 항목으로 합치고 `sources`를 합집합으로 만든다(DOI 대소문자만 다른 두 후보는 같은 후보).
- **파생 키**: 생산자는 `candidate_id`·`status`·`status_updated_at`·`slug`·`conference_ref`·`library`를 생략할 수 있다. 넣어도 무시하고 다시 계산한다(`status: "new"`).
- **상태**: 저장 상태는 `new`·`keep`·`registered`·`skipped`다. 응답의 `library`가 있으면 화면은 저장값과 상관없이 "등록됨"으로 보인다(저장값은 유지). `skipped`는 기본 숨김이다.

### 라이브러리 대조 (`library_index`·`library_match`)

`01-Papers/library/*.json`마다 arXiv id(`paper_id`의 `arXiv:` 접두, `source.urls`의 `arxiv.org/abs|pdf/<id>`, arXiv DOI `10.48550/arXiv.<id>`), DOI(`paper_id`의 `doi:` 접두, `source.urls`의 `doi.org/…`, `publication.verification_sources` 문자열 안의 DOI), S2(`paper_id`가 40자리 16진수), 정규화 제목을 모은다. 후보의 DOI·arXiv·S2 중 하나가 맞으면 `{"slug", "match": "id"}`, 아니면 정규화 제목이 같으면 `{"slug", "match": "title"}`(`paper_record.py init`도 casefold 제목 중복을 거부하므로 보유로 본다), 없으면 `null`이다. 색인은 파일 이름·크기·mtime이 바뀔 때만 다시 만든다. 읽지 못한 레코드는 색인의 `errors`에 남고 대조에서 빠진다.

### 학회 참고 (`conference_ref`, 표시 라벨 "참고")

`01-Papers/reference/cs-conferences.csv`(`약자`·`학회명`·`평균 (정규화)`)에서 venue에 맞는 행을 찾는다. 품질 판정이 아니라 참고 목록이다. 상세 응답은 저장값 대신 현재 CSV로 다시 계산한다(파일은 고치지 않음). CSV가 없으면 `null`이다.

- 약자는 단어 경계로 찾는다. 대문자가 2개 이상인 약자(`ACL`, `NeurIPS`)는 대소문자를 구분하고, 나머지 단어(`Findings`)는 구분하지 않는다. `/`는 대안(`NeurIPS/NIPS`, `FSE/ESEC`)이다.
- 맞은 단어가 가장 많은 약자가 이긴다(`Findings of ACL 2025` → `ACL Findings`). 서로 다른 학회가 동점이면 `null`이다(예: `FSE`).
- 약자가 없으면 15자 이상인 정규화 학회명(끝 괄호 약자 제외)이 venue에 들어 있어야 한다.
- `(oral)`·`(poster)`·`(spotlight)` 행: venue에 그 단어가 있으면 그 행, 없으면 `{"abbr": "CVPR", "name": <형식 제외 학회명>, "score": <변형 중 최솟값>}`.
- venue에 `workshop`이 있고 맞은 학회명에 없으면 `null`이다.

### `GET /api/discovery/daily`

```jsonc
{"days": [{"date": "2026-11-07", "created_at": "…" | null, "filled": 2,
           "slots": [{"slot": "computer-vision", "title": "…" | null, "status": "new" | null,
                      "library": {"slug", "match"} | null}]}],   // slots는 SLOTS 순서 3개, 미채움이면 title·status·library null
 "errors": [{"file": "00-Inbox/discovery/daily/2026-11-06.json", "error": "…"}]}
```

- 최신 날짜 먼저. `daily/*.json`만 읽는다. 파일 이름이 실제 날짜가 아니거나, JSON이 깨졌거나, 스키마가 틀렸거나, `date`가 파일 이름과 다르거나, 일반 파일이 아니면 그 파일만 `errors`(`error` 500자 이하)에 넣고 나머지는 그대로 준다.
- `status`는 저장값이다. 표시 상태 규칙은 위 "상태"를 따른다.

### `GET /api/discovery/daily/{date}`

200 `{"daily": Daily, "plan_href": "/03-Trends/…" | null}`. 각 후보는 모든 키를 갖추고 `library`와 다시 계산한 `conference_ref`가 붙는다. `plan_href`는 `plan_path`를 "정적 파일" 규칙으로 이 서버가 제공할 때만 URL이다(`/api/harness`의 `hrefs`와 같은 정책).

| 상태 | 코드 | 조건 |
|---|---|---|
| 400 | `bad_request` | `YYYY-MM-DD`가 아니거나 없는 날짜(`2026-02-30`) |
| 404 | `not_found` | 그 날짜 파일이 없음(캐시 폴더 없음 포함) |
| 500 | `cache_corrupt` | JSON 깨짐, 스키마 오류, `date`와 파일 이름 불일치 |
| 500 | `cache_unsafe` | 위 "캐시 위치·안전" 위반 |

### `GET /api/discovery/searches`, `GET /api/discovery/searches/{id}`

```jsonc
// 목록 — created_at 최신순
{"searches": [{"search_id": "s_…", "mode": "search|related", "created_at": "…", "status": "…",
               "query": "…" | null,          // mode search일 때만
               "kind": "refs|cites" | null,  // mode related일 때만
               "paper_title": "…" | null,    // mode related일 때만(기준 논문 제목)
               "candidate_count": 7, "job_id": "…" | null}],
 "errors": [{"file", "error"}]}
// 상세
{"search": SearchSession}   // 각 후보에 library·conference_ref(다시 계산)
```

- 재시작 정합: 목록·상세·삭제에서 읽을 때 `status`가 `queued`·`running`인데 `job_id`가 없거나 브로커가 모르는 작업이면 `status: "failed"`, `error: {"message": "서버가 재시작되어 검색이 중단되었습니다. 다시 실행하세요.", "kind": "interrupted"}`로 고쳐 저장한다. 대기 중에 취소되어 실행되지 않은 작업이면 `cancelled`로 고쳐 저장한다. 브로커에서 이미 끝난 작업(`completed`·`failed`·`cancelled`)이면 마지막 저장이 실패한 것이므로 `status: "failed"`, `error: {"message": "검색은 끝났지만 결과를 검색 기록에 저장하지 못했습니다. 다시 실행하세요.", "kind": "persist_failed"}`(`discovery_cache.PERSIST_FAILED_ERROR`)로 고쳐 저장한다(`webui/discovery.reconcile_session`). 그래서 저장 실패가 새 검색·삭제를 막지 않는다.
- 상세 오류: `s_<12hex>`가 아니면 400 `bad_request`, 없으면 404 `not_found`, 깨진 파일 500 `cache_corrupt`, 경로 위반 500 `cache_unsafe`. 목록에서는 깨진 파일·잘못된 이름만 `errors`로 간다.
- 삭제(`DELETE /api/discovery/searches/{id}`, 본문 `{}`): 200 `{"deleted": "s_…"}`. 잘못된 id 400 `bad_request`, 없음 404 `not_found`, `queued`·`running`이면 409 `search_active`(먼저 `POST /api/jobs/{job_id}/cancel`), 경로 위반 500 `cache_unsafe`. 스키마가 깨진 파일도 지울 수 있다. 자동 만료는 없다.

### `POST /api/discovery/searches`

표준 가드(CSRF, Origin, JSON, 64 KiB)를 거친다.

```jsonc
// 요청 — query만 필수. 생략하거나 null이면 기본값, 모르는 키는 400
{"query": "WiFi CSI human pose estimation", "year_from": 2022 | null, "year_to": 2026 | null,
 "limit": 10, "category_hint": "wifi-csi|game-ai|agent-ai|computer-vision|other" | null,
 "anchors": ["2026-ni-…"], "verified_only": false}
// 202
{"job": JobRecord,          // kind "discovery.search", role "paper-searcher", agent = 선택 실행기
 "search": SearchSession}   // status "queued", job_id, request(정규화), agent {agent, model, selector}, report null, candidates []
```

| 상태 | 코드 | 조건 |
|---|---|---|
| 400 | `bad_request` | 객체가 아님·모르는 키, `query`가 제어문자 제거·공백 축약 뒤 3–500자가 아님, `year_from`·`year_to`가 1900–(올해+1) 정수·null이 아니거나 from > to, `limit`이 1–30 정수가 아님(기본 10), `category_hint`가 5종·null이 아님, `anchors`가 문자열 목록이 아니거나 3개 초과·중복·slug 형식(`[a-z0-9-]+`) 위반·`01-Papers/library/{slug}.json` 없음, `verified_only`가 불리언이 아님 |
| 409 | `search_active` | 브로커에 `discovery.search` 작업이 `queued`·`running`으로 있음(동시에 하나, 리뷰·질문 작업과는 병행). 검사와 제출은 `server.discovery_lock` 하나 아래에서 한다 |
| 503 | `role_config_error` | 역할 설정(omp config)을 읽지 못함 |
| 503 | `searcher_unavailable` | `paper-searcher`가 설정됐지만 준비된 후보가 없음, 또는 미설정인데 연결 에이전트가 준비되지 않음 |
| 503 | `shutting_down` | 서버 종료 중 |
| 500 | `cache_unsafe` · `write_failed` | 캐시 경로 위반, 세션 파일 쓰기 실패(제출한 작업은 취소) |

제출 순서: 요청 검증 → 역할 해석 → (`discovery_lock`) 종료·단일 실행 검사 → (`discovery.LOCK`) `searches/` 폴더 확인 → `broker.submit` → `status: "queued"` 세션 기록. 기록이 실패하면 작업을 취소한다.

### 역할 `paper-searcher`

`.omp/agents/paper-searcher.md`(본문은 실행기의 시스템 프롬프트에 덧붙인다). 해석 규칙은 `paper-reader`와 같다: 설정을 읽지 못하면 503 `role_config_error`, 설정됐지만 준비된 후보가 없으면 503 `searcher_unavailable`(다른 모델로 대체하지 않음), **미설정이면 연결 에이전트(`.research-harness-agent.json`, 서버 고정 에이전트 우선)의 기본 모델**로 실행한다(omp의 `@paper-analysis`를 물려받지 않는다). 설정되면 후보 순서·사용 한도 시 다음 후보 이동은 "리뷰 역할"과 같다. `/api/status`의 `searcher_role`이 이 해석이다.

### 작업 `discovery.search`

- 레코드: `kind: "discovery.search"`, `role: "paper-searcher"`, `agent`는 선택 실행기. 제한 시간 900초(CLI `--max-time` 등은 900 + 30초 여유). 취소는 `POST /api/jobs/{id}/cancel`.
- 작업 공간: 임시 폴더 `webui-discovery-*`(저장소 복사본이 아니다). 넣는 파일은 `paper.py`(`.scripts/bin/paper.py`), `search-protocol.md`, `SKILL.md`(`paper-search`), `cs-conferences.csv`(있을 때), `library.json`(라이브러리 레코드의 `slug`·`title`·`ids`), `request.json`, `anchors.json`(기준 논문의 `title`·`year`·`venue`·`ids`·`abstract` 1500자 이하), `schema.json`([discovery-search.schema.json](discovery-search.schema.json)). 작업이 끝나면 폴더를 지운다.
- 답변: 스키마 JSON 객체 하나 `{"report": {queries, sources, anchors[{title, ids}], coverage_gaps, excluded_count, notes}, "candidates": [Candidate에서 파생 키를 뺀 형식]}`. claude는 `structured_output`을 먼저 쓰고, 없으면 결과 텍스트(코드 펜스 제거)를 파싱한다.
- 처리(`discovery_cache.prepare_search_result`): 검증(`validate_search_output`) → 후보 정규화(제어문자 제거·길이 자르기·https 아닌 `url` 제거·`candidate_id`·`status: "new"`·`conference_ref`) → `candidate_id`로 합치기(답변 순서 = 관련도 순서, `sources` 합집합) → 앞 `limit`편. `library`는 저장하지 않고 읽을 때 계산한다.
- 세션 상태: 작업이 시작되면 `running`, 종료 이벤트를 내보내기 **전에** 결과를 세션에 쓴다(클라이언트는 종료 이벤트를 받고 상세를 다시 읽으면 된다). 성공 → `completed`(`report`·`candidates`·`duration_ms`·관측된 `agent`). 실행기 오류 → `failed`, `error.kind`는 이벤트의 `kind`(`timeout`·`usage_limit`·`auth`·`process`·`other`). 답변이 JSON이 아니거나 스키마 검증에 실패하면 `failed`, `error.kind: "invalid_output"`, `report.notes`에 원문 앞 2000자를 남기고, 작업도 `result` 대신 `error`(`kind: "invalid_output"`)로 끝난다. 취소 → `cancelled`. 이 마지막 저장이 실패하면 작업은 성공 이벤트 대신 `error`(`kind: "persist_failed"`, "검색 결과를 검색 기록에 저장하지 못했습니다: …")로 끝나고(취소는 `cancelled` 그대로), 세션은 위 재시작 정합이 읽을 때 `persist_failed`로 고친다.
- 서버 종료(`server_close`): `discovery_lock` 아래에서 `closing`을 세운 뒤 탐색 작업(`discovery.search`·`discovery.register`)을 취소하고, `reader.shutdown` 다음에 `discovery.shutdown`이 최대 5초 기다린다(SIGINT 2.5초 뒤 프로세스 그룹 SIGKILL). 시간 안에 끝나지 않은 검색은 다음 실행 때 재시작 정합으로 `interrupted`가 된다. 등록 작업은 저장 상태가 없으므로 후보는 원래 상태로 남는다.

실행기별 명령(`research_agent.discovery_command`). 네트워크 허용 목록 `research_agent.DISCOVERY_DOMAINS`는 `search-protocol.md` §2의 18개 도메인이다.

| 실행기 | 명령 핵심 | 네트워크 |
|---|---|---|
| claude | `--print --output-format stream-json --verbose --include-partial-messages --restricted --permission-mode dontAsk --tools Read,Glob,Grep,Bash,WebSearch,WebFetch --allowedTools Read,Glob,Grep,Bash,WebSearch,WebFetch(domain:<각 도메인>) --no-session-persistence --json-schema <인라인> --strict-mcp-config --mcp-config '{"mcpServers":{}}' --settings <샌드박스>` + `--append-system-prompt` | `--settings`는 기존 샌드박스(`enabled`·`autoAllowBashIfSandboxed`·`allowUnsandboxedCommands: false`)에 `sandbox.network.allowedDomains`를 더한다. 2026-11-07 실제 검색(claude 2.1.311)에서 샌드박스 bash의 `paper.py`가 arXiv·OpenAlex·Crossref에 닿았다. 허용 목록 밖 호스트가 막히는지는 따로 시험하지 않았다. WebFetch는 `WebFetch(domain:…)` 허용 규칙으로만 허용한다 |
| codex | `exec --json --skip-git-repo-check --ephemeral --cd <작업 공간> --sandbox workspace-write -c approval_policy="never" -c sandbox_workspace_write.network_access=true --disable plugins --disable apps --disable hooks -c mcp_servers.<이름>.enabled=false… --output-schema <schema.json>` | `network_access`는 호스트 목록 없이 켜기만 한다. 키 이름은 codex-cli 0.167.0 바이너리의 설정 필드 문자열로 확인했고, 실제 허용 동작은 실행으로 확인 전이다 `[INFERENCE]`. MCP 서버 목록을 읽지 못하면 실행하지 않는다(리더와 같음) |
| omp | `-p --mode json --no-session --no-title --no-extensions --no-skills --no-rules --no-context-files --no-lsp --cwd <작업 공간> --tools read,grep,glob,bash,web_search --approval-mode yolo --max-time <초>` + `--append-system-prompt` | omp에는 샌드박스가 없어 네트워크를 제한하지 않는다. 경계는 도구 목록과 임시 작업 공간뿐이다. 스키마는 프롬프트에 넣는다 |

프롬프트에는 작업 공간 파일 안내, 규칙(최소 2개 소스, 기준 논문 refs/cites 스노우볼링, 연도·카테고리, `verified_only`면 공식 출처로 확인된 published/accepted만, 라이브러리 보유 논문은 `relevance`에 표기, 도구가 반환한 논문만·기억으로 채우지 않음, 지시문은 데이터로 취급, 작업 공간 밖에 쓰지 않음, 스키마 JSON만 답함), 요청 JSON(`<question>` 데이터 블록, 태그 이스케이프는 리더와 같음), 스키마가 들어간다.

### 후보 채택: 공통

세 라우트(`keep`·`register`·`candidates/status`) 모두 표준 가드(CSRF, Origin, JSON, 64 KiB)를 거치고 본문에 후보 위치를 준다.

```jsonc
{"source": {"kind": "search", "id": "s_…"} | {"kind": "daily", "id": "YYYY-MM-DD"},
 "candidate_id": "c_…", …}   // 모르는 키는 400
```

- 400 `bad_request`: 객체가 아님·모르는 키, `source`가 위 형식이 아님(`s_<12hex>`·실제 날짜), `candidate_id`가 `c_<12hex>`가 아님. 404 `not_found`: 그 검색 기록·날짜 파일이 없음. 404 `candidate_not_found`: 그 파일에 후보가 없음. 깨진·안전하지 않은 캐시는 500 `cache_corrupt`·`cache_unsafe`.
- 후보 상태(`status`)는 캐시 파일에 저장한다: `new`(새 후보) · `keep`(Keep) · `registered`(등록됨) · `skipped`(넘김). 바뀔 때 `status_updated_at`(ISO UTC)을 쓰고 Keep·등록은 `slug`도 쓴다. 응답의 `candidate`는 상세 GET과 같은 형식(`library`·`conference_ref` 계산)이다. 화면은 `library`가 있으면 저장값과 관계없이 "등록됨"으로 보이되, 저장값이 `keep`이면 "등록"(완성 등록)을 허용한다(아래).
- 정본 파일 쓰기(`01-Papers/library/*.json`, `keep.md`, `index.md`, `pdfs/`)와 캐시 갱신은 `discovery.LOCK` 한 임계구역에서 하고, 등록 게시는 그 앞에 `reviews.LOCK`도 잡는다. keep.md·index.md는 임시 파일 + `os.replace`(기존 권한 유지)로 바꾼다. 중간 단계가 실패하면 그때까지 쓴 파일을 이전 내용으로 되돌린다(만든 파일은 지운다).
- slug: `{year 또는 0000}-{paper.surname(제1저자)}-{paper.slugify(제목)}`. 레코드는 이 저장소의 `.scripts/bin/paper_record.py init`(`--reading-status keep`, `metadata_status: partial`, paper_id `arXiv:<id>` > `DOI:<doi>` > `local:<slug>`, `source.urls`는 후보 https URL·arXiv·doi.org·S2 페이지)으로 만든다. `init`이 종료 코드 3(같은 paper_id 또는 casefold 제목)이면 409 `already_in_library`다.

### `POST /api/discovery/keep` — Keep에 담기

본문에 선택 `reason`(문자열|null). 제어문자 제거·공백 축약 뒤 500자까지 자르고, 비면 "사용자 지정 이유 없음". 화면은 후보의 `relevance`로 미리 채운다.

```jsonc
// 200
{"candidate": Candidate,   // status "keep", slug
 "slug": "2026-ni-trace2skill-…", "keep_path": "01-Papers/keep.md", "record_path": "01-Papers/library/{slug}.json"}
```

순서: 라이브러리 대조(§"라이브러리 대조")에 걸리거나 `library/{slug}.json`이 있으면 409 `already_in_library` → keep.md에 같은 논문 항목(`### ` 제목 정규화 일치, 또는 항목 본문에 같은 arXiv id·DOI)이 있으면 409 `already_in_keep` → `paper_record.py init`(카테고리는 후보 `suggested_category`, 없으면 `other`; PDF 없음) → keep.md 항목 삽입 → 후보 `status: "keep"`. 레코드를 만든 뒤 실패하면 레코드를 지우고 keep.md를 되돌린 뒤 500 `write_failed`. **`01-Papers/index.md`는 고치지 않으며 리뷰 큐 검사도 하지 않는다**(사용자 결정).

keep.md 항목 형식은 `webui/discovery.py`의 `KEEP_ENTRY`가 정본이다. `## 읽을 논문` 바로 아래(최신이 위)에 넣고, 그 절이 없으면 파일 끝에 절을 만들고, 파일이 없으면 기존 머리말(`# 킵 리스트` + 설명)로 만든다.

```markdown
### {제목}

- 추가일: {KST YYYY-MM-DD}
- 출처: {venue 또는 "출처 미확인"} · [arXiv:{id}](https://arxiv.org/abs/{id}) · [DOI](https://doi.org/{doi}) · [S2](https://www.semanticscholar.org/paper/{s2})
- PDF: 없음
- 리뷰: 없음
- 상태: 킵
- 이유: {reason}
```

`출처`의 링크는 있는 것만 ` · `로 잇는다. 등록이 쓰는 항목은 `PDF: [원문](pdfs/{category}/{slug}.pdf)`(PDF가 있을 때)이고 `이유`는 후보의 `relevance`다.

### `POST /api/discovery/register` — 등록

본문 `category`: `wifi-csi`·`game-ai`·`agent-ai`·`computer-vision`·`other`(화면은 `suggested_category`를 미리 고른다).

```jsonc
// 202
{"job": JobRecord,   // kind "discovery.register", role "paper-searcher", slug
 "candidate": Candidate, "slug": "…"}
```

| 상태 | 코드 | 조건 |
|---|---|---|
| 400 | `bad_request` | 공통 + `category`가 5종이 아님 |
| 409 | `already_in_library` | 라이브러리 대조에 걸렸는데 그 레코드가 "완성 등록" 대상이 아님, 또는 `library/{slug}.json`이 이미 있음 |
| 409 | `review_active` | 리뷰 큐(`04-Projects/review-queue/queue.json`)에 `queued`·`running` 작업이 있음. 리뷰 게시는 라이브 `index.md`가 바뀌면 실패하므로 등록하지 않는다 |
| 409 | `register_active` | 같은 slug의 `discovery.register` 작업이 `queued`·`running`(검사와 제출은 `discovery_lock` 아래) |
| 503 | `role_config_error` · `searcher_unavailable` · `shutting_down` | 검색과 같은 역할 해석·종료 규칙 |

**완성 등록(Keep 뒤 등록)**: 대조된 레코드가 `reading_status: "keep"`이고 `source.pdf_path`가 비어 있으며 리뷰가 완료되지 않았으면 409 대신 그 레코드의 slug로 등록한다. 레코드는 새로 만들지 않고 카테고리(선택값)·PDF 경로·게재 정보·빈 `topics`/`one_line_summary`·`source.urls`를 보강하고, keep.md의 기존 항목은 `- PDF: 없음` 줄만 PDF 링크로 바꾸며(새 항목 없음), index.md에는 같은 제목 행이 없을 때만 행을 더한다.

### 작업 `discovery.register`

- 레코드: `kind: "discovery.register"`, `role: "paper-searcher"`, `slug`, `agent`는 선택 실행기. 제한 시간 600초(CLI 여유 +30초). 실행기 명령·네트워크는 `discovery.search`와 같다(`research_agent.discovery_command`; codex `workspace-write`, claude 샌드박스는 작업 폴더 쓰기 허용). 취소는 `POST /api/jobs/{id}/cancel`.
- 작업 공간: 임시 폴더 `webui-discovery-*`에 `paper.py`, `search-protocol.md`, `schema.json`([discovery-register.schema.json](discovery-register.schema.json)), `candidate.json`(후보의 제목·저자·연도·venue·publication·ids·url·초록·topics와 고른 `category`), 빈 `out/`. 저장소는 건드리지 않는다.
- 지시(`.omp/agents/paper-searcher.md` "등록 모드"): arXiv id면 `python3 paper.py pdf <id> --out out`, 아니면 허용 도메인의 공식·오픈액세스 PDF만 `out/`에 저장, 페이월 우회·비공식 사본 금지(없으면 `pdf_file: null`과 이유), venue·게재 상태를 공식 출처로 재확인, `topics` 3–8개, `one_line_summary`(초록 근거 한국어 한 문장 200자 이하, 판단 금지).
- 답변 `{"pdf_file": "out/…"|null, "pdf_source_url": str|null, "publication": {"venue": str|null, "status", "verified", "verification_sources"}, "topics": [str], "one_line_summary": str, "notes": str}`. 형식이 틀리면 작업은 `error`(`kind: "invalid_output"`)로 끝나고 아무것도 쓰지 않는다.
- 게시(`publish_registration`, `reviews.LOCK` → `discovery.LOCK` → 일일 후보면 `daily_lock`): 리뷰 큐가 활성이면 `error`(`kind: "review_active"`) → 후보가 아직 같은 slug로 등록 가능한지 다시 확인(아니면 `kind: "already_in_library"`) → PDF 검사 후 `01-Papers/pdfs/{category}/{slug}.pdf`로 배타적 생성(이미 있으면 덮어쓰지 않고 그 파일을 쓴다) → 레코드 `init`(완성 등록이면 기존 레코드) + `publication.verified`·`verification_sources`·`one_line_summary` 보강 → `paper_record.validate_record` → keep.md 항목(또는 PDF 줄) → `index.md` 표 마지막 행 뒤에 `| 읽을 예정 | {연도\|–} | {제목} | {제1저자 성} | {venue\|–} | – | – | {topics} |`(`\|` 이스케이프, 같은 제목 행이 있으면 생략, 표·파일이 없으면 만든다) → 후보 `status: "registered"`, `slug`. 한 단계라도 실패하면 쓴 파일을 모두 되돌리고 `error`(`kind: "publish_failed"`). 그 뒤 `wiki.py index`와 `wiki.py log --op ingest --title <제목> --path 01-Papers/library/{slug}.json`을 실행한다(실패는 `warnings`, 되돌리지 않음).
- PDF 검사(`checked_pdf`): `pdf_file`은 작업 공간 기준 `out/…` 상대 경로(절대 경로는 글자 그대로 작업 공간 아래일 때만, `..` 불가)다. 링크를 따라가지 않고 디렉터리 디스크립터로 연다: 작업 공간(`resolve()`)을 연 뒤 `out`과 그 아래 각 폴더를 `dir_fd` + `O_DIRECTORY|O_NOFOLLOW`로, 파일을 `O_NOFOLLOW|O_NONBLOCK`으로 열고 `fstat`으로 일반 파일인지 본다. 그래서 `out`이 정확히 작업 공간의 실제 폴더여야 하고, 에이전트가 `out`이나 하위 폴더를 바깥을 가리키는 심볼릭 링크로 바꾸면 읽지 않는다. 그다음 비어 있지 않음·50 MiB 이하·`%PDF` 시그니처를 확인한다. 하나라도 어기면 아래처럼 메타데이터만 등록한다.
- **PDF 없는 등록(Q18)**: `pdf_file`이 null이거나 PDF 검사에 실패하면 실패로 끝내지 않고 메타데이터만 등록한다(`source.pdf_path: null`, keep.md `PDF: 없음`). 라이브러리 카드는 "PDF 필요"를 표시한다. 이유는 `warnings`에 남는다("PDF를 쓰지 않았습니다: …").
- 후보 상태는 종료 이벤트를 내보내기 **전에** 저장한다. 성공 종료 이벤트는 `result`에 `registration`을 더한다: `{"slug", "record_path", "pdf_path": "01-Papers/pdfs/{category}/{slug}.pdf"|null, "keep_path", "index_path": "01-Papers/index.md", "upgraded": bool, "warnings": [str], "notes": str}`. 게시가 시작된 뒤 도착한 취소는 게시를 멈추지 않는다(작업은 `cancelled`로 기록되지만 후보는 `registered`).
- 정적 카탈로그 `100-views/paper-library.html`은 다시 만들지 않는다(WebUI는 JSON을 직접 읽고, 다음 리뷰 게시 때 재생성된다).

### `POST /api/discovery/candidates/status` — 넘김·복원

본문 `status`는 `"skipped"`(넘김, 기본 목록에서 숨김) 또는 `"new"`(복원)만 받는다. 그 밖의 값(`keep`·`registered` 포함)은 400 `bad_request`. 저장값이 `keep`·`registered`이거나 라이브러리 대조에 걸린 후보는 409 `candidate_adopted`. 성공하면 200 `{"candidate"}`(같은 값이면 파일을 고치지 않는다).

### `POST /api/discovery/related` — 인용·피인용 (M4)

서버가 Semantic Scholar(S2) references·citations를 **직접, 동기로** 조회해 `related` 세션 하나를 만든다(Q11; 에이전트 작업·작업 레코드 없음). 표준 가드(CSRF, Origin, JSON, 64 KiB)를 거친다. 구현은 `webui/discovery.create_related`와 `paper.related_rows`(CLI `paper.py refs|cites`와 같은 함수).

```jsonc
// 요청 — 모르는 키는 400
{"kind": "refs" | "cites",            // refs: 기준 논문이 인용한 문헌, cites: 기준 논문을 인용한 문헌
 "paper": {"slug": "2026-ni-…"}        // 라이브러리 논문: 레코드의 제목·식별자(§라이브러리 대조와 같은 출처)를 쓴다
        | {"title": "…", "ids": {"arXiv": "…"|null, "DOI": "…"|null, "S2": "…"|null, "OpenAlex": "…"|null}},  // 탐색 후보
 "limit": 1–50}                        // 생략·null이면 25
// 201
{"search": SearchSession}  // 아래 형식, 각 후보에 library·conference_ref
```

- S2 조회 id: `ids.S2`(영숫자) > `arXiv:<id>` > `DOI:<doi>`. 셋 다 없으면 400 `no_identifier`(OpenAlex id만으로는 조회하지 않는다).
- 세션: `mode: "related"`, `status: "completed"`, `job_id: null`, `agent: null`, `request: {"kind", "paper": {"slug": str|null, "title", "ids"}, "limit"}`, `report: {"queries": ["S2 references|citations <조회 id>"], "sources": ["s2"], "anchors": [{"title", "ids"}], "coverage_gaps": [응답이 limit만큼 차면 "앞 N건만 조회" 안내], "excluded_count": 제목 없는 행·중복 수, "notes"}`, `error: null`, `duration_ms`. 실패하면 세션을 만들지 않는다.
- 후보: S2 응답만으로 만든다(판단을 지어내지 않음). `publication`은 `{"status": "unknown", "verified": false, "verification_sources": []}`, `sources: ["s2"]`, `suggested_category: null`, `topics: []`, `relevance`는 관계와 S2 인용 수만 적은 고정 문장 — `"S2 참고문헌 — 기준 논문이 인용한 문헌. S2 인용 수 1,234회."` / `"S2 피인용 — 기준 논문을 인용한 문헌. S2 인용 수 정보 없음."`. 순서는 S2 인용 수 내림차순. 이후 Keep·등록·넘김은 일반 검색 후보와 같다(`source: {"kind": "search", "id": search_id}`).
- 호출 예산: 요청 1회 timeout 12초, 429만 2초 대기 뒤 1회 재시도(최악 ≈26초), 전체 데드라인 30초(서버 전체 세마포어 대기 포함) 초과 시 504. 서버 전체에서 S2 호출은 한 번에 하나, 앞 호출이 끝나고 1초 이상 지난 뒤 다음 호출. 성공한 응답은 `(조회 id, kind, limit)` 키로 서버 메모리에 10분·최대 200건 캐시(적중하면 S2를 부르지 않고 `notes`에 캐시 결과임을 적는다; 세션 파일은 매번 새로 만든다). 클라이언트 timeout은 60초.

| 상태 | 코드 | 조건 |
|---|---|---|
| 400 | `bad_request` | 본문 형식(kind, limit 1–50, paper 키, 잘못된 slug, 빈 title, ids 형식) |
| 400 | `no_identifier` | 기준 논문에 arXiv·DOI·S2 식별자가 없음 |
| 404 | `not_found` | slug의 라이브러리 레코드가 없거나 읽을 수 없음, 또는 S2가 404·400(그 id의 논문 없음) |
| 503 | `upstream_rate_limited` | S2 HTTP 429(재시도 뒤). 메시지는 잠시 뒤 재시도와, 서버 실행 환경에 `S2_API_KEY` 설정 후 서버 재시작을 안내한다(키가 이미 있으면 재시도만) |
| 502 | `upstream_unavailable` | 네트워크 실패, S2 5xx 등 그 밖의 HTTP 오류, JSON·응답 형식 오류 |
| 504 | `upstream_timeout` | 소켓 시간 초과 또는 30초 데드라인 초과 |
| 500 | `cache_unsafe`·`write_failed` | 캐시 경로 위반(조회 전에 검사), 세션 저장 실패 |

**서버의 외부 통신 범위**: WebUI 서버 프로세스가 직접 하는 외부 호출은 이 라우트의 `https://api.semanticscholar.org/graph/v1/paper/{id}/references|citations` GET **한 가지**뿐이다. 서버 실행 환경에 `S2_API_KEY`가 있으면 `paper.py`가 그 요청에만 `x-api-key` 헤더로 붙인다. WebUI는 키를 저장·로그·응답·브라우저 전송하지 않는다(429 안내 문구도 키 유무만 반영). 그 밖의 외부 접근(검색·등록)은 자식 CLI(`discovery.search`·`discovery.register` 작업)에서만 일어나며 허용 도메인은 [search-protocol.md](search-protocol.md)를 따른다.

### CLI `discovery_cache.py`

표준 라이브러리만 쓴다. 전역 옵션 `--root PATH`(기본: 이 저장소)는 하위 명령 앞에 둔다.

| 명령 | 동작 | 종료 코드 |
|---|---|---|
| `validate <path>…` | 파일마다 `search_id`가 있으면 SearchSession, 아니면 Daily로 검증 | 0 모두 유효, 2 하나라도 무효·읽기 실패 |
| `daily-write <input.json> [--replace]` | 검증·정규화·`candidate_id`·`status: "new"`·`conference_ref`·`created_at`(없으면 지금) 부여 후 `daily/{date}.json`에 원자적으로 기록, 경로 출력. `--replace`면 기존 파일의 같은 `candidate_id` 후보의 `status`·`status_updated_at`·`slug`를 유지. 이전 파일 읽기부터 기록까지 그 날짜의 `daily_lock`을 쥔다(WebUI 상태 변경과 직렬화) | 0 기록, 2 JSON·스키마 오류, 3 그 날짜 파일이 이미 있음(`--replace` 없음), 1 캐시 경로 위반·입출력 오류 |
| `library-match <path>` | 후보·Daily·SearchSession 파일의 후보를 라이브러리와 대조해 `{"matches": [{"candidate_id", "title", "key", "library"}], "errors"}` 출력(디버그) | 0, 읽기 실패 1·2 |

## 정적 파일

- `webui/reviews.py`의 `ALLOWED_ROOTS`(예: `01-Papers/`, `docs/`, `100-views/`, `.scripts/`)와 `ALLOWED_ROOT_FILES`(`AGENTS.md`, `CLAUDE.md`, `README.md`) 아래만 제공한다.
- percent-decoding 뒤 NUL, 역슬래시, `.`·`..`·빈 경로 조각이 있으면 404다.
- 경로의 각 조각이 디스크의 실제 이름과 대소문자까지 같아야 한다. 대소문자 변형(`/100-VIEWS/…`)은 404다.
- 심볼릭 링크를 따라 resolve한 경로가 저장소 밖이거나 허용 목록 밖이면 404다.
- `.git`, `.env*`, `.mcp.json`, `.secrets`, `credentials.json`, `.claude`, `.codex`, `.research-harness-agent.json`, `reader-threads`(논문 리더 스레드)는 허용 경로 안에 있어도 404다.
- `01-Papers/reviews/` 아래 어느 깊이든 `figures` 조각(대소문자 무시)이 있는 경로와 그 아래 모든 경로(리뷰 그림 `*.html`·`*.svg`, 하위 폴더 리뷰의 `…/nested/figures/` 포함)는 404다. 심볼릭 링크의 실제 대상이 그 아래여도 404다. 에이전트가 만든 HTML·SVG가 CSP 없이 같은 출처에서 실행되지 않도록, SVG만 위 "리뷰 그림" API로 제공한다.
- `00-Inbox/discovery/` 아래 모든 경로(일일 후보·검색 기록 캐시, `README.md` 포함)는 404다(대소문자 무시, 심볼릭 링크의 실제 대상이 그 아래여도 404). 캐시는 위 "논문 탐색" API로만 읽는다.
- 디렉터리 목록은 보여주지 않는다. 슬래시 없는 디렉터리 요청은 301로 슬래시를 붙이고, `index.html`이 없으면 404다.

## 작업 레코드

```json
{"job_id": "…", "kind": "agent.ping|paper.ask|discovery.search|discovery.register|harness.verify|harness.tests", "status": "queued|running|completed|failed|cancelled",
 "created_at": "2026-11-03T07:00:00+00:00", "started_at": null, "ended_at": null,
 "agent": "claude", "cost_usd": null, "error": null, "last_seq": 0, "role": "paper-analyst"}
```

`role`은 역할 작업(`agent.ping`의 `role`, `paper.ask`의 `paper-reader`, `discovery.*`의 `paper-searcher`)에만, `slug`는 `paper.ask`와 `discovery.register`에만 있다. `harness.*` 작업은 `agent: null`이고 `role`·`slug`가 없다.

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
