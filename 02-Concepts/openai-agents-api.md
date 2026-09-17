# OpenAI Agents API — 활용 가능성 조사·검증 메모

- 조사일: 2026-09-14
- 출발점: `notes/trends/2026-09-13.md`의 “OpenAI, Agents API public beta 발표” 항목. `2026-09-14.md`에는 해당 항목이 없다.
- 검증 범위: OpenAI 공식 개발자 문서. API 표면에 `beta.agents` 네임스페이스와 `OpenAI-Beta: agents=v1` 헤더가 남아 있으므로, 안정된 장기 인터페이스로 가정하면 안 된다.

## 한 줄 결론

Agents API는 **OpenAI가 Codex 기반 에이전트 루프와 세션 상태를 관리**하고, 우리 애플리케이션이 작업·도구·실행 환경을 연결하는 API다. 이 저장소에는 논문 탐색/트리아지/초안 작성의 **격리된 보조 작업자**로는 적합하지만, 원문 근거 확인이나 `git push`를 사람 검토 없이 완전히 위임할 단계는 아니다.

## 실제로 무엇을 제공하는가

공식 구조는 세 부분이다.

| 구성 | 담당 |
|---|---|
| Harness | OpenAI가 운영하는 Codex 인스턴스. 모델·도구 호출 루프와 세션을 유지한다. |
| Environment | 에이전트가 명령 실행·파일 작업을 하는 장소. 환경 없이도 실행하거나, OpenAI-hosted/self-hosted sandbox를 붙일 수 있다. |
| Application server | 우리가 작성하는 호출부. 작업을 보내고 stream/webhook 이벤트를 받고, 함수 도구를 실행한다. |

근거: [Architecture](https://developers.openai.com/api/docs/guides/agents-api/architecture), [Quickstart](https://developers.openai.com/api/docs/guides/agents-api/quickstart).

세션(session)은 에이전트 설정·대화·저장된 작업을 유지한다. 같은 session에 후속 입력을 보내면 작업을 이어갈 수 있고, turn은 그 안의 한 번의 작업 단위다. 진행은 stream 또는 webhook으로 받는다. [Run and continue sessions](https://developers.openai.com/api/docs/guides/agents-api/sessions)

### 환경 선택의 뜻

| 선택 | 가능한 일 | 이 프로젝트에서의 판단 |
|---|---|---|
| `none` | 외부 서비스용 도구 호출·질의 응답. shell/작업공간 파일은 없다. | 메타데이터 확인, 웹·MCP 기반 조사 초안에 적합하다. |
| `openai_hosted` | OpenAI가 Linux workspace(Python/Node/CLI)를 세션별로 제공한다. 패키지, 입력 파일, 네트워크 정책을 지정할 수 있다. | 작은 PDF/CSV/시뮬레이션 입력을 분석해 아티팩트를 만드는 PoC에 적합하다. 로컬 저장소가 자동으로 보이지는 않는다. |
| `self_hosted` | 우리 컴퓨터/서버/Docker/private network에서 executor를 연결한다. 환경 수명주기는 우리가 관리한다. | WaveVerse 같은 로컬 simulator, 사설 데이터, 하드웨어 도구가 필요해질 때만 고려한다. 운영·보안 부담이 커진다. |

근거: [Architecture](https://developers.openai.com/api/docs/guides/agents-api/architecture), [OpenAI-hosted sandboxes](https://developers.openai.com/api/docs/guides/agents-api/environments/openai-hosted).

## 이 저장소에서 쓸 만한 자리

### 1. 논문 후보 조사와 메타데이터 대조 — 가장 먼저 검증할 대상

입력으로 제목/키워드와 허용 출처(arXiv, OpenAlex, Semantic Scholar 등)를 주고, 출력은 다음처럼 **구조화된 초안(JSON 또는 Markdown)** 으로 제한한다.

```text
title, authors, year, venue, arXiv_id, DOI, PDF URL,
원문 근거 링크, 불확실한 필드 목록
```

에이전트는 후보 수집과 교차 대조만 맡고, `scripts/paper.py`의 최종 메타데이터 확정 규칙 및 PDF 원문 확인은 기존 워크플로가 유지한다. 즉 Agents API는 `paper-search`를 대체하는 판정자가 아니라 반복 조사량을 줄이는 보조자다.

### 2. 일일 다이제스트의 “초안 전용” 작업자

현재 일일 루프의 최종 산출물 규칙(원문 근거, 날짜별 양식, commit/push)은 그대로 둔다. Agent에는 다음만 맡긴다.

- 카테고리별 후보 3편과 이슈 3건을 찾고, 각 주장 옆에 출처 URL을 붙인 초안을 만든다.
- 주어진 `notes/trends/2026-09-07.md` 양식에 맞춰 빈칸 없이 작성 가능한지 검사한다.
- 원문/PDF를 못 읽은 주장에는 `[확인 필요]`를 붙인다.

에이전트 출력은 artifact 또는 응답으로 회수하고, 로컬 에이전트가 출처·중복·형식을 검토한 뒤에만 노트 작성 및 git 작업을 한다. 이 분리는 환각된 인용, 프롬프트 주입, 잘못된 외부 링크가 저장소 변경으로 바로 이어지는 것을 막는다.

### 3. RF sensing 사고실험의 계산 보조

OpenAI-hosted 환경에 작은 synthetic CSI/geometry 입력과 재현 가능한 Python 스크립트를 넣어 다음을 맡길 수 있다.

- Rx 수·간격·bandwidth 후보를 전수 실행하고 결과 표/plot artifact를 생성한다.
- 사전에 정한 지표(위치 오차, voxel IoU, 조건수 등)를 계산한다.
- 실패한 조건과 재현 명령을 기록한다.

그러나 **이 API가 RF 물리나 ESP32 동기화 문제를 해결하는 것은 아니다.** forward model의 정확성, phase calibration, clock synchronization, simulator-to-real gap은 별도의 실험 설계와 측정으로 검증해야 한다. 여기서 에이전트의 역할은 실험 실행·기록 자동화이지 과학적 타당성의 근거가 아니다.

## 바로 자동화하면 안 되는 것

1. **원문을 읽지 않은 심층 리뷰의 확정**: 이 저장소의 리뷰는 방법·실험 본문 근거가 필수다. 에이전트 초안은 원문 위치 검증 전에는 리뷰가 아니다.
2. **무인 `git commit`/`git push`**: 에이전트가 생성한 파일·명령·외부 링크를 바로 원격 저장소에 반영하면 오류와 프롬프트 주입의 피해 범위가 커진다.
3. **로컬 저장소/개인 키가 자동으로 sandbox에 있다고 가정**: OpenAI-hosted sandbox는 세션별 별도 workspace다. 필요한 입력 파일은 명시적으로 주입해야 하며, 템플릿은 실행 중인 workspace가 아니라 설정만 저장한다.
4. **비용이 ‘모델 한 번 호출’ 수준이라고 가정**: 한 작업 안에서 여러 모델 호출과 subagent 호출이 생길 수 있다. 토큰 외에도 tool, sandbox compute, 제3자 서비스 비용이 적용될 수 있다.

근거: [OpenAI-hosted sandboxes](https://developers.openai.com/api/docs/guides/agents-api/environments/openai-hosted), [Observability and usage](https://developers.openai.com/api/docs/guides/agents-api/observability).

## 보안·운영에서 확인된 병목

- agent-generated code는 해당 환경에 제공된 파일·자격증명·네트워크에 접근할 수 있다. 애플리케이션 API key는 sandbox 밖에 두어야 한다.
- 네트워크는 `disabled`를 기본값으로 두고, 정말 필요한 경우만 정확한 host allowlist를 쓰는 편이 안전하다.
- third-party credential은 sandbox에 넣지 말고, 가능하면 credential broker를 통해 승인된 요청에만 주입한다.
- OpenAI-hosted sandbox는 작업이 멈춘 뒤 약 1시간이면 삭제될 수 있으므로, 필요한 결과는 `/workspace/outputs` artifact로 회수해야 한다.

근거: [Sandbox security](https://developers.openai.com/api/docs/guides/agents-api/environments/security), [OpenAI-hosted sandboxes](https://developers.openai.com/api/docs/guides/agents-api/environments/openai-hosted).

## 권장 PoC: 작고 읽기 전용으로 시작

### 목표

“에이전트가 논문 조사 초안을 사람보다 덜 확인하게 만드는가?”만 측정한다. 저장소 쓰기·git 권한·개인 API 키·사설 데이터는 제공하지 않는다.

### 설계 [제안]

1. 이미 메타데이터가 확정된 논문 10편을 정답 세트로 만든다.
2. `environment: none`으로 후보 수집/메타데이터 JSON 생성을 시킨다. 허용 도구와 출처 도메인을 좁힌다.
3. 각 필드의 정확도, 존재하지 않는 DOI/arXiv ID 비율, 근거 URL 누락률, 사람 검토 시간을 기록한다.
4. 기존 `scripts/paper.py` 결과와 비교한다. 정확도가 아니라 **검토 시간 감소와 근거 오류율**이 도입 기준이다.
5. 이 단계에서 오류가 충분히 낮을 때만, 네트워크 비활성 `openai_hosted` 환경에 공개 PDF 한두 편을 넣어 표·수식·실험 설정 추출 artifact를 시험한다.

### 통과 기준 [제안]

- 존재하지 않는 식별자 0건
- 각 외부 사실에 원문 또는 서지 DB URL 1개 이상
- 사람 검토 후 수정률과 검토 시간이 기존 수동 흐름보다 낮음
- 어떤 단계에서도 자동 저장·commit·push 없음

## 최종 판단

도입 가치는 있다. 다만 가치는 “더 똑똑한 연구자”가 아니라, **명시한 도구·환경·출력 형식 안에서 반복 조사와 계산을 수행하고 상태를 이어 주는 실행 인프라**라는 데 있다. 이 저장소의 첫 적용은 `논문 조사 JSON 초안 → 로컬 검증 → 사람 승인` 흐름이 가장 타당하다. RF reconstruction 연구에는 simulator 실험을 반복 실행·기록하는 보조자로 확장할 수 있으나, 핵심 물리 가설의 검증 도구로 과대평가하면 안 된다.

## 공식 문서

- [Agents overview](https://developers.openai.com/api/docs/guides/agents)
- [Agents API quickstart](https://developers.openai.com/api/docs/guides/agents-api/quickstart)
- [Architecture](https://developers.openai.com/api/docs/guides/agents-api/architecture)
- [Run and continue sessions](https://developers.openai.com/api/docs/guides/agents-api/sessions)
- [OpenAI-hosted sandboxes](https://developers.openai.com/api/docs/guides/agents-api/environments/openai-hosted)
- [Sandbox security](https://developers.openai.com/api/docs/guides/agents-api/environments/security)
- [Observability and usage](https://developers.openai.com/api/docs/guides/agents-api/observability)
