---
name: keep-list
description: Manage the separate reading and research keep list when the user asks to keep, save for later, list, remove, or verify papers and research topics.
---

# Keep List

`library/keep.md`는 나중에 읽거나 다시 검토할 논문과 조사 주제를 위한 대기열이다. `library/favorites.md`와 목적이 다르다. favorites는 선호 논문, keep은 읽기·조사 보류 대상이다.

## 적용 범위

- 사용자가 “킵해둬”, “나중에 읽을 것에 넣어”, “킵 리스트 보여줘”, “킵에서 빼줘”, “킵 경로 확인해줘”라고 요청할 때 사용한다.
- 논문뿐 아니라 API, simulator, 사고실험처럼 후속 조사가 필요한 주제를 기록할 수 있다.
- 즐겨찾기만 추가·해제하는 요청에는 `paper-favorites`를 사용한다.

## 기록 규칙

- 항목은 `library/keep.md`의 `읽을 논문` 또는 `다시 볼 조사 주제` 아래에 둔다.
- 논문은 제목, 추가일, 확인된 출처/식별자, PDF 링크, 리뷰·메모 링크, 상태, 이유를 기록한다. 조사 주제는 자료 링크와 다음에 확인할 질문을 이유에 적는다.
- 추가일은 요청일을 쓴다. 이유가 없으면 `사용자 지정 이유 없음`이라고 쓴다.
- 제목·식별자·저장소 경로·자료 링크를 기준으로 중복을 막고, 기존 항목은 보존한다.
- PDF·리뷰·메모 파일을 이동·삭제·수정하지 않는다. 킵 목록만 변경한다.

## 작업 방식

- **추가:** 대상이 논문이면 `library/index.md`, `papers/`, `reviews/`를 대조해 현재 경로와 식별자를 확인한다. 조사 주제면 기존 note 또는 사용자가 준 1차 자료를 연결한다.
- **목록:** 제목, 유형, 상태, 이유, PDF/자료 링크를 짧게 요약한다. 끊긴 경로는 `[경로 확인 필요]`를 붙인다.
- **해제:** 지정 항목만 `library/keep.md`에서 제거한다. 원문·리뷰·메모는 건드리지 않는다.
- **검증:** 모든 상대 링크의 대상 존재를 확인한다. 이동된 PDF는 현재 카테고리 경로로 고치되, 메타데이터나 이유를 추측해 바꾸지 않는다.
