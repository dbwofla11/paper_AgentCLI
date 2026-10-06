# 01-Papers — 논문 리딩 관문

논문 원문, 리뷰, 트리아지, 목록을 모두 이 폴더 안에 둔다.

- [원문 PDF](pdfs/README.md): `pdfs/{category}/`
- [심층 리뷰](reviews/README.md): `reviews/{category}/`
- [트리아지 메모](triage/): 논문별 1차 판정
- [전체 인덱스](index.md): 상태·평점·태그
- [논문별 JSON](library/): 메타데이터, 수집 상태, 5축 리뷰, 근거 위치와 관계. 형식: [paper-record.schema.json](../.scripts/docs/paper-record.schema.json)
- [Keep 목록](keep.md): 나중에 읽을 대상
- [즐겨찾기](favorites.md): 개인적으로 중요한 대상
- [JSON 시각화](../paper-library.html): 검색·필터·연도/분야 분포

논문 수집 시 `library/{slug}.json`을 만들고, 심층 리뷰 뒤 분석 축과 원문 근거를 보강한다. 시각화 파일은 아래 명령으로 JSON에서 다시 생성한다.

```bash
python3 .scripts/bin/paper_catalog_html.py
```

기존 PDF의 빈 레코드는 `python3 .scripts/bin/paper_record.py import-pdfs`로 한 번 생성할 수 있으며, PDF 파일명만 있는 레코드는 `needs_review`, 기존 리뷰의 구조화 분석을 아직 옮기지 않은 레코드는 `structured_review_status: pending`으로 표시한다. 논문 1편의 상세 해석은 리뷰에, 여러 논문을 합쳐 이해한 내용은 `02-Concepts/`에 쓴다.
