---
name: related-work
description: 앵커 논문의 references와 citations를 추적해 선행·후속 연구 관계를 확인하고 논문 JSON에 근거를 연결한다.
---

# 관련 연구 맵핑

앵커 논문을 중심으로 후방 references와 전방 citations를 조사한다. 인용수 순위가 아니라 앵커 본문에서 실제 기반·비교·확장·반박 관계를 확인한다.

## 절차

1. arXiv ID·DOI·S2 ID를 `.scripts/bin/paper.py meta`와 논문 JSON에서 확인한다.
2. `.scripts/bin/paper.py refs <id> --limit 40`으로 후방 문헌, `cites <id> --limit 40`으로 전방 문헌을 찾는다. 중요 후보 1–2편만 추가 추적한다.
3. 실제 관계를 말하려면 앵커 원문과 상대 논문의 관련 구간을 읽는다. API의 인용 연결이나 유사 제목만으로 관계를 추정하지 않는다.
4. 확인된 관계는 양쪽 `01-Papers/library/{slug}.json`의 `relationships`에 같은 관계 유형, 설명, 원문 위치를 연결한다. 미확인은 저장하지 않고 `[확인 필요]`로 보고한다.
5. JSON 변경 후 `python3 .scripts/bin/paper_record.py validate <path>`로 검증하고 Graphify 갱신 대상으로 둔다.

## 보고

채팅에서 `선행 기반`, `동시대 대안`, `후속 확장·반박`으로 나눠 핵심 문헌과 근거 위치를 요약한다. 새로운 `notes/` 파일은 만들지 않는다. 리뷰 §9를 보강한 경우 `paper-review` 절차로 리뷰와 JSON을 함께 갱신한다.
