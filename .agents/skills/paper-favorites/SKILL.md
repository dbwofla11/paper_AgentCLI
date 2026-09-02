---
name: paper-favorites
description: Manage an explicit list of favorite papers in this paper-review repository when the user asks to favorite, bookmark, unbookmark, list, or validate saved papers.
---

# Paper Favorites

논문 즐겨찾기를 `library/favorites.md`에서 관리한다. 즐겨찾기 추가·해제는 사용자가 명시적으로 요청한 경우에만 수행하며, 논문 PDF·리뷰·인덱스 항목 자체는 건드리지 않는다.

## 저장 형식

파일이 없으면 다음 형식으로 새로 만든다.

```markdown
# 즐겨찾기 논문

## {논문 제목}

- 추가일: YYYY-MM-DD
- 저자: {원문 메타데이터}
- 연도·venue: {확인된 값}
- 식별자: arXiv/DOI 또는 `[확인 필요]`
- PDF: [papers/YYYY-MM-DD/file.pdf](../papers/YYYY-MM-DD/file.pdf)
- 리뷰: [reviews/file.md](../reviews/file.md) 또는 `없음`
- 이유: {사용자가 말한 이유 또는 간단한 기록}
```

기존 항목은 보존하고, 제목·식별자·PDF 경로를 이용해 중복을 막는다. 메타데이터를 확인하지 못한 값은 추측하지 말고 `[확인 필요]`로 표시한다. PDF 경로는 현재 저장소의 날짜별 구조인 `papers/YYYY-MM-DD/`를 따른다.

## 작업별 규칙

- **추가:** 제목·arXiv ID·DOI·PDF 경로 중 하나로 대상을 확정한 뒤 공식 메타데이터와 저장소 파일을 대조하고 항목을 append한다. 이유가 없으면 `사용자 지정 이유 없음`으로 적는다.
- **해제:** `library/favorites.md`에서 해당 항목만 제거한다. PDF나 리뷰 파일을 삭제하지 않는다.
- **목록:** `library/favorites.md`를 읽어 제목, 식별자, PDF/리뷰 링크, 이유를 요약한다. 링크가 끊겼으면 `[경로 확인 필요]`를 붙인다.
- **검증·동기화:** 모든 PDF·리뷰 링크의 존재를 확인하고, 이동된 날짜별 PDF 경로를 현재 위치로 갱신한다. 논문 내용이나 평점을 임의로 갱신하지 않는다.

대상 논문이 모호하면 제목만 보고 추측하지 말고 `library/index.md`, `reviews/`, `papers/`를 검색해 식별자를 대조한다. 그래도 하나로 확정되지 않으면 사용자에게 대상 논문을 한 가지로 지정해 달라고 요청한다.
