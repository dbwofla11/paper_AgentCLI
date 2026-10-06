# 로컬 논문 리뷰 실행기

`100-views/paper-library.html`은 정적 파일만으로 에이전트를 실행하지 않는다. 로컬 리뷰를 시작하려면 저장소 루트에서 다음 실행기를 띄우고 그 실행기가 안내하는 로컬 주소로 라이브러리를 연다.

```bash
python3 .scripts/bin/paper_review_bridge.py serve
```

기본 주소는 `http://127.0.0.1:8765/100-views/paper-library.html`이다. `리뷰 시작`은 클릭한 논문 slug 하나만 보내고, 실행기는 한 번에 한 작업만 큐에 넣는다. Codex CLI와 `pdftotext`가 설치되어 있어야 한다. PDF는 원문 페이지 범위를 10쪽 이내로 추출해 읽으며, 스캔 PDF나 읽기 실패는 완료 처리하지 않는다.

리뷰 에이전트는 저장소의 임시 작업 복사본에서 실행된다. 선택한 PDF만 복사하고 나머지 원문 PDF는 제외한다. `.mcp.json`, `.env*`, `.claude/`, `.codex/`, `.secrets/`, `credentials.json`도 복사하지 않으며, 복사본 밖을 가리키는 심볼릭 링크는 제거한다. 작업 전후 파일 상태를 비교하며 리뷰 Markdown, 선택 논문 JSON, 논문 인덱스, 카탈로그, Graphify 출력, 개념 후보 초안만 게시 후보로 받는다. JSON 스키마·5축 필드·실제 읽은 범위·Graphify 성공을 복사 전 확인하고, 실행 중 원본 파일이 바뀌었으면 해당 출력 게시를 거부한다. 실패 상태와 오류 요약은 `04-Projects/review-queue/queue.json`에 남긴다.

브리지는 `127.0.0.1`에만 바인딩하고 브라우저 요청의 `Origin`·`Host`를 같은 로컬 출처로 제한한다. 임의 shell 명령이나 파일 경로를 요청으로 받지 않는다. 이 실행기는 리뷰가 필요한 논문 한 편에 대한 전용 어댑터이며, 사고실험 문헌 조사 실행은 별도 Orca TODO 어댑터를 사용한다.
