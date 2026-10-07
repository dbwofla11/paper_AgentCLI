# 연구 화면

직접 만든 HTML 화면과 공통 화면 자산을 이 폴더에서 관리한다.

[발표용 하네스 흐름도](harness-flows/index.html)는 전체 실행·사고실험·자료 저장·운영 루프를 HTML로 설명한다. PPT용 PNG·PDF는 `harness-flows/assets/`에서 관리한다. [Notion 안내 관리](../docs/notion-harness/README.md)에 기능별 페이지와 생성 방법을 기록했다.

- [하네스](harness-dashboard.html): 흐름 선택 → 단계 → 역할·입력·결과·다음 조건, 스킬 검색.
- [논문](paper-library.html): 검색·필터·원문·리뷰 보기, 로컬 실행기에서 리뷰 시작.
- [사고실험](thought-experiments.html): 가설·반증 조건·문헌·심사·실험 상태와 근거 파일.

## 열기

검색·필터·리뷰 보기는 HTML 파일을 직접 열어 사용할 수 있다. 새 리뷰 실행은 저장소 루트에서 `python3 .scripts/bin/onboard_research.py` 후 `http://127.0.0.1:8765/`로 접속한다. 실행기가 꺼져 있으면 페이지에 연결 안내가 표시된다.

## 갱신

정본 데이터는 기존 논문·아이디어·스킬 파일이다. HTML을 직접 수정하면 재생성 시 덮어써진다. 변경은 아래 생성기에서 한다.

```sh
python3 .scripts/bin/paper_catalog_html.py
python3 .scripts/bin/thought_experiments_html.py
python3 .scripts/bin/harness_dashboard.py --no-tests
```

공통 디자인은 `assets/research-ui.css`와 [DESIGN-figma.md](../docs/design/DESIGN-figma.md)를 따른다. 흰 바탕·검은 글자, 파스텔 섹션, 알약 형태 버튼을 사용하고 외부 폰트 다운로드 없이 시스템 폰트로 표시한다. 흐름도 디자인은 `assets/harness-flow.css`에서 관리하며 생성 시 HTML에 포함해 단독 파일로도 열 수 있다.

공통 화면 CSS는 `assets/research-ui.css`, 공통 메뉴는 `.scripts/bin/research_ui.py`에서 관리한다. 원문·근거 링크는 저장소 루트를 향하는 `../` 상대 경로다. 세 화면은 같은 폴더의 메뉴로 이동한다. Graphify 자체 출력은 엔진 정본인 `graphify-out/`에서 유지한다.

## 확인 방법

세 화면은 브라우저에서 열어 검색·필터와 메뉴를 사용할 수 있다. 논문 리뷰 시작은 로컬 실행기를 통해 수행한다.
