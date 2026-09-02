# A2A (Agent2Agent Protocol) — 저장소 분석 메모

- 대상: [github.com/a2aproject/A2A](https://github.com/a2aproject/A2A), 스펙 사이트 [a2a-protocol.org](https://a2a-protocol.org/latest/specification/)
- 논문 아님(프로토콜 스펙 + SDK 저장소). Google 주도, Apache 2.0.
- 조사일: 2026-08-28. **WebFetch(AI 요약) 기반** — 저장소 raw 파일이나 스펙 원문을 직접 읽지 않음. 세부 필드명·JSON 구조는 재확인 필요 [확인 필요].

## 정체

AI 에이전트 간(agent-to-agent) 통신·협업을 위한 오픈 프로토콜. MCP가 "에이전트 ↔ 도구/데이터"를 잇는다면, A2A는 "에이전트 ↔ 에이전트"를 잇는 역할 — 상호 보완 관계로 소개됨.

## 핵심 메커니즘 (3단계)

1. **발견(Discovery)** — 서버 에이전트가 well-known URI(예: `/.well-known/a2a`)에 **Agent Card**(JSON)를 공개. 이름, 지원 스킬, 인증 방식(`securitySchemes`), 지원 프로토콜 바인딩(JSON-RPC/gRPC/HTTP+REST), 스트리밍·푸시 지원 여부를 담음. 클라이언트는 카드만 읽으면 상대 내부 구현을 몰라도 호출 가능("opaque" 협업).
2. **작업 위임(Task)** — 메시지를 보내면 서버가 **Task 상태 기계**로 관리. 상태값: `SUBMITTED → WORKING → {COMPLETED|FAILED|CANCELED|REJECTED}(종결)`, 중간 대기 상태 `INPUT_REQUIRED`/`AUTH_REQUIRED`. 종결 상태 진입 후 추가 메시지 불가.
3. **결과 전달 3방식** — ① 동기(블로킹, 완료까지 대기) ② 스트리밍(SSE, `TaskStatusUpdateEvent`/`TaskArtifactUpdateEvent`로 진행상황 실시간 전달) ③ 푸시(webhook, 클라이언트가 콜백 URL 등록 → 완료 시 서버가 POST).

## Message/Part 구조 (요약)

`Message`에 `messageId`, `contextId`(대화 그룹화), `taskId`, `role`, `parts[]`. Part는 `text`/`url`(외부 파일 참조)/`raw`(base64 인라인)/`structured`(JSON) 타입 지원, 순서 보장.

## 인증

Agent Card의 `securitySchemes`에 API Key/OAuth2/mTLS 선언 → 요청 시 헤더로 인증. 민감한 스킬은 별도 인증 후 `GetExtendedAgentCard`로 확장 카드 조회하는 흐름도 있다고 함.

## 기술 스택

- 통신: JSON-RPC 2.0 over HTTP(S) (+ gRPC/REST 바인딩)
- SDK 언어: Python, Go, JavaScript, Java, .NET, Rust
- 문서: MkDocs, 스펙은 `specification/`, 설계 결정은 `adrs/`(Architecture Decision Records)
- CI: GitHub Actions, Ruff(lint), Prettier, Lychee(링크 검증)
- 연동 프레임워크: Google ADK, LangGraph, BeeAI 등에서 지원

## 주의할 점 [확인 필요]

- 위 내용은 WebFetch 도구(소형 모델 요약)를 통해 얻은 것으로, GitHub 페이지·스펙 원문을 직접 인용·대조하지 않음. 실제 활용(구현/비교) 전에는 `specification/` 원문 또는 a2a-protocol.org 스펙 문서를 직접 읽고 필드명·상태값을 재검증할 것.
- Task 상태값 이름, Agent Card 필드명은 스펙 버전에 따라 바뀔 수 있음 — 사용 시점에 최신 스펙 재확인 필요.
