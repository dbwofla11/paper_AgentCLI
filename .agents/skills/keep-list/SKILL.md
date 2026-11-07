---
name: keep-list
description: Manage the separate reading and research keep list when the user asks to keep, save for later, list, remove, or verify papers and research topics.
---

# Keep List

`01-Papers/keep.md`는 나중에 읽거나 다시 검토할 논문과 조사 주제를 위한 대기열이다. `01-Papers/favorites.md`와 목적이 다르다. 즐겨찾기는 선호 논문, Keep은 읽기·조사 보류 대상이다. 사용자가 PDF나 논문 자료를 직접 올리면 중복을 확인한 뒤 Keep에도 등록한다.

## 적용 범위

- 사용자가 “킵해둬”, “나중에 읽을 것에 넣어”, “킵 리스트 보여줘”, “킵에서 빼줘”, “킵 경로 확인해줘”라고 요청할 때 사용한다.
- 논문뿐 아니라 API, simulator, 사고실험처럼 후속 조사가 필요한 주제를 기록할 수 있다.
- 즐겨찾기만 추가·해제하는 요청에는 `paper-favorites`를 사용한다.

## 기록 규칙

- 항목은 `01-Papers/keep.md`의 `읽을 논문` 또는 `다시 볼 조사 주제` 아래에 둔다. 새 논문 항목은 `## 읽을 논문` 헤딩 바로 아래(최신 항목이 위)에 넣는다.
- 논문은 제목, 추가일, 확인된 출처/식별자, PDF 링크, 리뷰·메모 링크, 상태, 이유를 기록한다. 조사 주제는 자료 링크와 다음에 확인할 질문을 이유에 적는다.
- 추가일은 요청일(KST)을 쓴다. 이유가 없으면 `사용자 지정 이유 없음`이라고 쓴다.
- 제목·식별자·저장소 경로·자료 링크를 기준으로 중복을 막고, 기존 항목은 보존한다. 정규화한 `### ` 제목이 같거나 기존 항목 본문에 같은 arXiv id·DOI가 있으면 중복이다.
- PDF·리뷰·메모 파일을 이동·삭제·수정하지 않는다. 킵 목록만 변경한다.

## 논문 항목 형식

논문 항목 형식의 정본은 WebUI 서버 코드 `.scripts/bin/webui/discovery.py`의 `KEEP_ENTRY`다. WebUI의 "Keep에 담기"·"등록"이 이 형식으로 쓰며, 채팅에서 손으로 추가하는 논문 항목도 같은 7줄 형식을 따른다.

```markdown
### {제목}

- 추가일: {YYYY-MM-DD}
- 출처: {venue 또는 "출처 미확인"} · [arXiv:{id}](https://arxiv.org/abs/{id}) · [DOI](https://doi.org/{doi}) · [S2](https://www.semanticscholar.org/paper/{s2})
- PDF: {[원문](pdfs/{category}/{slug}.pdf) 또는 "없음"}
- 리뷰: {[심층 리뷰](reviews/{category}/{slug}.md) 또는 "없음"}
- 상태: {킵 또는 "리뷰 완료"}
- 이유: {한 줄 이유 또는 "사용자 지정 이유 없음"}
```

- `출처` 줄은 venue(없으면 `출처 미확인`) 뒤에 확인된 식별자 링크만 arXiv → DOI → S2 순서로 ` · `로 잇는다. 채팅에서 손으로 쓸 때 게재본 페이지(ACL Anthology·출판사 등)가 확인되면 그 링크를 더해도 된다.
- 추가일은 KST 날짜다. 항목 뒤에는 빈 줄 하나를 둔다.
- WebUI "Keep에 담기"는 `PDF: 없음`, `리뷰: 없음`, `상태: 킵`으로 쓰고, 이유는 대화상자 입력을 공백 축약해 500자에서 자른 값이다. "등록"은 PDF를 받았으면 `PDF:`에 `[원문](pdfs/{category}/{slug}.pdf)`을 쓴다. Keep만 했던 논문을 등록하면 새 항목을 만들지 않고 기존 항목의 `PDF: 없음` 줄만 원문 링크로 바꾼다.
- 리뷰를 마치면 `리뷰:` 링크와 `상태: 리뷰 완료`만 고친다. 나머지 줄은 유지한다.

## 작업 방식

- **추가:** 대상이 논문이면 `01-Papers/index.md`, `01-Papers/library/*.json`, `01-Papers/pdfs/`, `01-Papers/reviews/`를 대조해 현재 경로와 식별자를 확인한다. JSON이 없으면 수집 메타데이터로 생성한다. 조사 주제면 기존 Concept 또는 사용자가 준 1차 자료를 연결한다.
- **WebUI에서 추가된 항목:** WebUI 탐색 화면의 "Keep에 담기"는 서버가 결정적으로 `keep.md` 항목과 `01-Papers/library/{slug}.json`(`reading_status: keep`, `metadata_status: partial`, PDF 없음)만 만들고 `01-Papers/index.md` 행은 추가하지 않는다. 이런 항목을 정리할 때 인덱스 행이 없다고 오류로 보지 않는다. 카테고리를 정해 공식·오픈액세스 원문(구하지 못하면 메타데이터만)과 인덱스 `읽을 예정` 행까지 만드는 것은 WebUI "등록"이며, Keep만 한 논문도 나중에 등록할 수 있다. 채팅에서 인덱스만 보완하려면 `review-index`로 처리한다.
- **목록:** 제목, 유형, 상태, 이유, PDF/자료 링크를 짧게 요약한다. 끊긴 경로는 `[경로 확인 필요]`를 붙인다.
- **해제:** 지정 항목만 `01-Papers/keep.md`에서 제거한다. 원문·리뷰·메모는 건드리지 않는다.
- **검증:** 모든 상대 링크의 대상 존재를 확인한다. 이동된 PDF는 현재 카테고리 경로로 고치되, 메타데이터나 이유를 추측해 바꾸지 않는다.
