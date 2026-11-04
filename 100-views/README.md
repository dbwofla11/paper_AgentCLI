# 연구 화면

직접 만든 HTML 화면과 공통 화면 자산을 이 폴더에서 관리한다.

[발표용 하네스 흐름도](harness-flows/index.html)는 전체 실행·사고실험·자료 저장·운영 루프를 HTML로 설명한다. PPT용 PNG·PDF는 `harness-flows/assets/`에서 관리한다. [Notion 안내 관리](../docs/notion-harness/README.md)에 기능별 페이지와 생성 방법을 기록했다.

- `webui/`: Research WebUI 프런트엔드 빌드 결과. 주 화면이다(논문 라이브러리 `#/`, 논문 리더, 사고실험 `#/ideas`, 하네스 `#/harness`, 상태, 작업). 소스는 `.scripts/webui/`이며 직접 수정하지 않는다. [Research WebUI 안내](../docs/research-webui.md)를 본다.
- [하네스](harness-dashboard.html)·[논문](paper-library.html)·[사고실험](thought-experiments.html): 서버 없이 `file://`로 여는 정적 대체 화면. 하네스는 흐름·단계·스킬 검색, 논문은 검색·필터·원문·리뷰 보기, 사고실험은 가설·반증 조건·문헌·심사·실험 상태와 근거 파일을 보여 주고, 서버가 켜져 있으면 논문 화면에서도 리뷰를 시작할 수 있다. 같은 내용을 WebUI의 `#/harness`, `#/`, `#/ideas`가 보여 준다.

## 열기

저장소 루트에서 `python3 .scripts/bin/onboard_research.py`(처음 연결) 또는 `python3 .scripts/bin/research_webui.py serve`(연결 후)를 실행하고 `http://127.0.0.1:8765/`로 접속하면 WebUI(`/100-views/webui/`)가 열린다. 리뷰 시작은 WebUI 첫 화면(`#/` 논문 라이브러리)에서 한다. `--agent codex`, `--agent claude`, `--agent omp`로 실행할 호스트를 선택할 수 있다. 개인 연결 설정은 `.research-harness-agent.json`에 둔다.

정적 HTML 파일은 서버 없이 직접 열어 검색·필터·리뷰 보기를 쓸 수 있다. 정적 논문 라이브러리(`http://127.0.0.1:8765/100-views/paper-library.html`)에서 리뷰를 시작하는 기존 방법도 계속 동작하며, 서버가 꺼져 있으면 페이지에 연결 안내가 표시된다.

## 갱신

정본 데이터는 기존 논문·아이디어·스킬 파일이다. HTML을 직접 수정하면 재생성 시 덮어써진다. 변경은 아래 생성기에서 한다.

```sh
python3 .scripts/bin/paper_catalog_html.py
python3 .scripts/bin/thought_experiments_html.py
python3 .scripts/bin/harness_dashboard.py --no-tests
```

정적 화면(하네스·논문·사고실험)의 공통 디자인은 `assets/research-ui.css`와 [DESIGN-figma.md](../docs/design/DESIGN-figma.md)를 따른다. 흰 바탕·검은 글자, 파스텔 섹션, 알약 형태 버튼을 사용하고 외부 폰트 다운로드 없이 시스템 폰트로 표시한다. 흐름도 디자인은 `assets/harness-flow.css`에서 관리하며 생성 시 HTML에 포함해 단독 파일로도 열 수 있다. WebUI는 이 CSS를 쓰지 않고 자체 토큰(`.scripts/webui/src/styles/tokens.css`)을 쓴다.

정적 화면 CSS는 `assets/research-ui.css`, 정적 화면 메뉴는 `.scripts/bin/research_ui.py`에서 관리한다. 원문·근거 링크는 저장소 루트를 향하는 `../` 상대 경로다. 세 정적 화면은 같은 폴더의 메뉴로 서로 이동한다. Graphify 자체 출력은 엔진 정본인 `graphify-out/`에서 유지한다.

## 확인 방법

세 화면은 브라우저에서 열어 검색·필터와 메뉴를 사용할 수 있다. 논문 리뷰 시작은 로컬 실행기를 통해 수행한다.
