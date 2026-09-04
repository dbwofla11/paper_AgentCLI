---
name: paper-scheduler
description: Schedule, inspect, update, or cancel a future paper-selection plan that the daily digest loop will consume. Use when the user asks to reserve papers, topics, or slots for a future digest date; do not use for immediate paper search or deep review.
---

# Paper Scheduler

논문을 미리 확정해 다운로드하는 기능이 아니라, 미래 다이제스트 회차의 논문 선정 기준을 예약하는 스킬이다. 예약 내용은 저장소의 `notes/trends/{YYYY-MM-DD}-plan.md`에 남기며, [daily-digest-loop](../daily-digest-loop/SKILL.md)가 해당 날짜에 이 파일을 읽어 논문 슬롯과 주제 배분을 우선 적용한다.

## 예약

사용자가 별도 날짜를 주지 않으면 Asia/Seoul 기준 다음 날짜를 사용한다. 날짜가 과거이면 즉시 알리고 예약하지 않는다. 날짜별 계획 파일이 이미 있으면 기존 내용을 먼저 보여주고, 사용자가 변경·교체를 명시한 경우에만 수정한다.

예약 요청에서 다음 정보를 자연어로 추출한다.

- 날짜: `YYYY-MM-DD`
- 논문 수: 기본값은 루프 규칙에 맞춘 정확히 3편
- 슬롯별 주제: 슬롯 번호와 주제, 또는 특정 논문 제목/arXiv ID
- 우선순위·제약: 데이터셋, 방법, 도메인, 최신성 등 사용자가 지정한 조건

논문 주제는 `WiFi CSI`, `게임 AI (Game AI)`, `에이전트 AI (Agent AI)`, `컴퓨터 비전 (Computer Vision)` 중 하나 이상이어야 한다. 이 목록 밖의 주제는 해당 허용 카테고리로 직접 구체화하도록 안내하거나 예약하지 않는다. 특정 논문 제목/arXiv ID를 예약하더라도 daily-digest-loop의 학회 발표·게재 확인을 통과해야 실제 회차에 포함된다.

정보가 부족해도 날짜와 주제만으로 계획을 만들 수 있다. 다만 논문 수가 3편이 아니면 루프가 정확히 3편을 요구한다는 점을 알리고, 사용자가 명시한 수를 그대로 저장할지 3편으로 맞출지 확인한다. 특정 논문을 예약할 때도 메타데이터를 새로 지어내지 말고 사용자가 준 식별자만 기록한다.

## 계획 파일 형식

다음 구조를 유지한다. 슬롯 수와 주제 배분은 사용자의 요청을 그대로 반영하고, 해석이나 검색어 확장은 `[추론]` 또는 `[확인 필요]`로 표시한다.

```markdown
# YYYY-MM-DD 논문 선정 계획

- 기준일: YYYY-MM-DD (Asia/Seoul)
- 논문 수: 정확히 3편
- 1번 슬롯: 주제 또는 특정 논문
- 2번 슬롯: 주제 또는 특정 논문
- 3번 슬롯: 주제 또는 특정 논문
- 추가 조건: 허용 카테고리 중 하나 이상; 학회 발표·게재 확인 필수

이 계획은 YYYY-MM-DD 회차에만 적용한다.
```

빈 슬롯은 임의의 주제로 채우지 말고 `사용자 지정 없음`으로 적는다. 예약 시에는 논문 검색, PDF 다운로드, 리뷰 작성, Git commit/push를 수행하지 않는다. 작업이 끝나면 생성·수정한 파일의 링크와 예약된 날짜·슬롯을 채팅으로 보고한다.

## 조회와 취소

- “예약 목록”, “예약 확인” 요청에는 `notes/trends/*-plan.md`를 날짜순으로 읽어 계획을 요약한다.
- “예약 취소” 요청에는 대상 날짜를 확인한 뒤 해당 날짜의 plan 파일만 삭제한다. 날짜가 특정되지 않거나 여러 계획이 해당하면 먼저 대상을 좁힌다.
- “예약 수정” 요청은 기존 계획을 보존하면서 요청된 항목만 갱신하고, 적용 날짜를 파일 안에서 다시 확인한다.

예약된 논문을 지금 바로 검색하거나 리뷰하려면 각각 `paper-search` 또는 `paper-review`를 사용한다. 예약 파일은 루프의 선정 지침이며, 예약 자체가 클라우드 루틴의 실행 일정을 새로 만들거나 변경하지는 않는다.
