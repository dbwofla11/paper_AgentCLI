# 연구 화면

직접 만든 HTML 화면과 공통 화면 자산을 이 폴더에서 관리한다.

- [하네스](harness-dashboard.html): 흐름 선택 → 단계 → 역할·입력·결과·다음 조건, 스킬 검색.
- [논문](paper-library.html): 검색·필터·원문·리뷰 보기, 로컬 실행기에서 리뷰 시작.
- [사고실험](thought-experiments.html): 가설·반증 조건·문헌·심사·실험 상태와 근거 파일.

## 열기

검색·필터·리뷰 보기는 HTML 파일을 직접 열어 사용할 수 있다. 새 리뷰 실행은 저장소 루트에서 `python3 .scripts/bin/paper_review_bridge.py serve` 후 `http://127.0.0.1:8765/`로 접속한다. 실행기가 꺼져 있으면 페이지에 연결 안내가 표시된다.

## 갱신

정본 데이터는 기존 논문·아이디어·스킬 파일이다. HTML을 직접 수정하면 재생성 시 덮어써진다. 변경은 아래 생성기에서 한다.

```sh
python3 .scripts/bin/paper_catalog_html.py
python3 .scripts/bin/thought_experiments_html.py
python3 .scripts/bin/harness_dashboard.py
```

공통 디자인은 `assets/research-ui.css`, 공통 메뉴는 `.scripts/bin/research_ui.py`에서 관리한다. 원문·근거 링크는 저장소 루트를 향하는 `../` 상대 경로다. 세 화면은 같은 폴더의 메뉴로 이동한다. Graphify 자체 출력은 엔진 정본인 `graphify-out/`에서 유지한다.

## 동작 확인 (2026-10-06)

- 자동 테스트 19개 통과, 하네스 구조 검사 통과.
- 브라우저: 6개 흐름·28개 단계 선택, 스킬 검색·설명 열기, 논문 검색·필터·리뷰 팝업·닫기, 사고실험 검색·6개 상태 필터·정렬 확인.
- 파일 모드의 리뷰 실행 안내와 원문 상대 경로 확인. 로컬 서버의 기존 주소 이동·CSS 제공 확인.
- `.scripts/tests/view_review_mock.js`는 로컬 서버 라이브러리 페이지에서 실행하는 브라우저 검사용이다. API를 모의 응답으로 바꿔 작업 ID 선택·실패·작업 누락·서버 오류 후 버튼 복구를 확인하고 API를 복원한다. 실제 논문 리뷰는 시작하지 않았다.
