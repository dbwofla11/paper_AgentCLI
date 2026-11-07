# 00-Inbox/discovery — 논문 탐색 캐시

로컬 WebUI 탐색 화면(`#/discover`)이 읽는 캐시다. 이 README만 Git에 커밋하고, 나머지 파일은 모두 Git에서 제외한다(`.gitignore`). 캐시는 위키(`wiki.py`의 `PAGE_SCOPE` 밖)·라이브러리·Graphify(`.graphifyignore`) 대상이 아니며 연구 정본이 아니다.

## 구성

| 경로 | 내용 | 작성 주체 |
|---|---|---|
| `daily/{YYYY-MM-DD}.json` | 날짜별 일일 후보(컴퓨터 비전·멀티모달·관심 분야 슬롯 3개)와 검색 보고 | `daily-digest-loop` 스킬이 `python3 .scripts/bin/discovery_cache.py daily-write <file>`로 기록 |
| `searches/{search_id}.json` | 검색 1회의 질의·사용 소스·커버리지 보고·후보 | WebUI 서버(탐색 화면의 검색 기능이 준비되면 기록) |

형식(후보·일일·검색 세션)의 정본은 [discovery-cache.schema.json](../../.scripts/docs/discovery-cache.schema.json)이다. `python3 .scripts/bin/discovery_cache.py validate <path…>`로 검사한다.

## 규칙

- 일일 후보는 채팅으로 보고하고, 같은 내용을 Git에서 제외된 로컬 캐시 `00-Inbox/discovery/daily/YYYY-MM-DD.json`에 기록한다. 캐시는 위키·라이브러리·Graphify 대상이 아니다. PDF·Keep·논문 JSON 같은 정본 저장은 사용자가 채택("Keep에 담기" 또는 "등록")한 뒤에만 한다. 자동 Git commit/push는 하지 않는다.
- 캐시 JSON은 손으로 만들거나 고치지 않는다. 일일 후보는 `discovery_cache.py daily-write`로만 쓴다. 같은 날짜 파일이 이미 있으면 거부되며, 교체는 사용자가 요청했을 때만 `--replace`로 한다.
- WebUI 서버는 이 폴더를 정적 파일로 제공하지 않는다. 내용은 `/api/discovery/…` API로만 읽는다.
- 지워도 연구 기록은 잃지 않는다. 채택한 논문은 `01-Papers/`의 정본에 따로 남는다.
