---
name: daily-digest-loop
description: 매일 논문 후보 3편을 검색해 채팅으로 제시하고 로컬 캐시에 기록한다. CV·멀티모달·사용자 관심 분야의 학회 발표·게재 논문을 찾을 때 사용한다.
---

# Daily Paper Candidates

한 번 호출하면 Asia/Seoul 기준 날짜의 논문 후보 3편을 찾는다. 뉴스 검색, 정본 저장(PDF·Keep·인덱스·JSON), Git commit/push는 이 스킬의 실행에 포함하지 않는다. 후보를 채택하면 `paper-search`로 넘긴다.

일일 후보는 채팅으로 보고하고, 같은 내용을 Git에서 제외된 로컬 캐시 `00-Inbox/discovery/daily/YYYY-MM-DD.json`에 기록한다. 캐시는 위키·라이브러리·Graphify 대상이 아니다. PDF·Keep·논문 JSON 같은 정본 저장은 사용자가 채택("Keep에 담기" 또는 "등록")한 뒤에만 한다. 자동 Git commit/push는 하지 않는다.

## 선정

1. 아래 세 슬롯을 각각 한 편씩 채운다.
   - 컴퓨터 비전 (`computer-vision`) 1편
   - 멀티모달 1편. 저장소 카테고리는 논문의 주 입력·태스크·방법에 따라 `computer-vision`, `agent-ai`, `other` 중 하나를 택하고 `multimodal` 토픽 태그를 별도로 둔다.
   - 사용자의 관심 분야 1편. `05-Ideas/thought-experiments/`의 활성 아이디어, `01-Papers/keep.md`, `02-Concepts/`, 최근 리뷰·JSON을 확인해 가장 관련 높은 주제를 선택한다. 이 자료가 비어 있으면 `wifi-csi`, `game-ai`, `agent-ai` 중 최근 다루지 않은 분야를 고른다.
2. `01-Papers/reference/cs-conferences.csv`에서 관련 분야 학회를 참고하고, `paper-search` 절차로 최소 두 학술 소스를 탐색한다. 분야·방법·태스크 용어를 나눠 검색하고, 후보가 겹치면 DOI/arXiv ID 기준으로 합친다.
3. 공식 proceedings, 출판사 논문 페이지 또는 학회 공식 프로그램과 논문 원문으로 발표·게재를 확인한다. arXiv preprint만 확인된 논문은 제외한다. 학회명·연도·논문 유형과 확인 URL을 기록한다.
4. 제목·초록만으로 분야를 확정하지 않는다. 원문에서 실제 입력·태스크·방법을 확인한다. 특히 멀티모달은 둘 이상의 modality가 방법의 핵심인지 확인하며, 단순히 텍스트를 언급하는 논문은 포함하지 않는다.
5. 슬롯의 논문을 검증하지 못하면 다른 분야 논문으로 임의 대체하지 않는다. 부족한 슬롯과 검색 범위를 보고한다.

## 출력과 인계

표에 슬롯·정식 제목·저자·학회/연도/유형·발표 확인 링크·한 줄 요약·관심 분야와의 관련 이유를 제시한다. 이어 [paper-summary](../paper-summary/SKILL.md) 형식으로 각 논문의 초록, 전체 주장, 방법, 한계를 짧게 덧붙이고 실제 확인한 원문 범위를 명시한다. 후보 보고는 채팅으로만 하며 별도 보고서 파일을 만들지 않는다.

채팅 후보와 캐시는 정본이 아니다. 사용자가 특정 후보를 채택하면 해당 논문만 `paper-search`로 넘겨 PDF, Keep, 인덱스, `01-Papers/library/{slug}.json`에 등록한다. 기존 paper ID나 정규화한 제목과 중복인지 다시 확인한다.

날짜별 사용자가 지정한 선정 계획이 `03-Trends/daily/{YYYY-MM-DD}-plan.md`에 있으면 3개 슬롯의 주제 기준에 적용한다. 이 계획은 학회 게재 검증 조건을 낮추지 않는다.

## 캐시 기록

채팅 보고를 마친 뒤 같은 후보를 일일 캐시 JSON으로 기록한다. 로컬 WebUI의 탐색 화면(일일 후보 탭)이 이 파일을 읽어 보여 준다. 캐시 파일은 직접 만들거나 고치지 않고 아래 CLI로만 쓴다.

1. 저장소 밖 임시 파일(예: `mktemp`로 만든 경로)에 아래 형식의 JSON을 작성한다. 형식과 길이 한도의 정본은 `.scripts/docs/discovery-cache.schema.json`이다.
   - 최상위: `schema_version`(`"1.0"`), `date`(Asia/Seoul 기준 `YYYY-MM-DD`), `created_at`(ISO 8601), `plan_path`(적용한 `03-Trends/daily/{YYYY-MM-DD}-plan.md` 경로, 없으면 `null`), `slots`, `report`.
   - `slots`: 세 슬롯을 `computer-vision`, `multimodal`, `interest` 순서로 하나씩 둔다. 각 항목은 `slot`, `topic`(관심 분야 슬롯의 선택 주제 등, 없으면 `null`), `candidate`, `unfilled_reason`이다. 검증하지 못한 슬롯은 `candidate: null`과 부족한 이유·검색 범위를 담은 `unfilled_reason`을 쓴다. 채운 슬롯의 `unfilled_reason`은 `null`이다.
   - `candidate`: `title`, `authors`, `year`, `venue`, `publication`(`status`는 `published|accepted|preprint|unknown`, `verified`, 확인 URL을 담은 `verification_sources`), `citations`, `ids`(`arXiv`·`DOI`·`S2`·`OpenAlex`, 모르면 `null`), `url`(https만, 없으면 `null`), `abstract`, `relevance`(관심 분야와의 관련 이유 1–2문장), `sources`(`s2|arxiv|openalex|web` 중 실제 사용한 것), `suggested_category`(`wifi-csi|game-ai|agent-ai|computer-vision|other`), `topics`(멀티모달 슬롯은 `multimodal` 포함). 채팅 보고와 같은 값을 쓰고 확인하지 못한 값은 지어내지 않고 `null`로 둔다.
   - `candidate_id`, `status`, `status_updated_at`, `slug`, `conference_ref`, `library`는 쓰지 않는다. CLI와 WebUI 서버가 채운다. 위 목록에 없는 키는 넣지 않는다(검증 실패).
   - `report`: 실제 사용한 `queries`와 `sources`, 확인하지 못한 범위 `coverage_gaps`, `notes`.
2. `python3 .scripts/bin/discovery_cache.py daily-write <file>`을 실행한다. CLI가 형식을 검증하고 후보 ID와 `status: new`를 붙여 `00-Inbox/discovery/daily/{date}.json`에 원자적으로 기록한다.
   - 종료 코드 2(검증 실패): 출력된 오류를 고쳐 다시 실행한다.
   - 종료 코드 3(같은 날짜 캐시가 이미 있음): 덮어쓰지 않고 채팅에 알린다. 사용자가 같은 날짜의 재실행·교체를 명시적으로 요청한 경우에만 `--replace`를 붙인다. 교체해도 같은 후보의 기존 상태는 유지된다.
   - 종료 코드 1(캐시 경로가 안전하지 않거나 입출력 오류): 다시 시도하지 말고 출력된 오류를 채팅에 보고한다.
3. 임시 파일을 지우고, 기록한 캐시 경로 또는 기록 실패 이유를 채팅 보고 끝에 한 줄로 덧붙인다. 캐시 기록이 실패해도 채팅 보고는 유효하며 다른 파일로 대신 저장하지 않는다.

## 예약 실행

저장소는 스킬 실행 절차만 정의한다. 매일 09:00 KST 예약은 Orca Automation에서 이 스킬을 호출하도록 설정한다. 자동화 프롬프트는 “오늘의 Daily Paper Candidates 3편을 검색해 채팅으로 보고하고 `discovery_cache.py daily-write`로 캐시만 기록하며 다른 파일을 수정하지 말 것”을 포함한다. 예약 생성·변경(기존 예약의 프롬프트 갱신 포함)은 명시적인 사용자 요청이 있을 때만 수행한다.
