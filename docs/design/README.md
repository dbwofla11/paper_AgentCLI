# 연구 화면 디자인

기준 문서는 [DESIGN-discord.md](DESIGN-discord.md)다. 사용자 제공 문서 `/home/user/Downloads/DESIGN-discord.md`를 보관한 사본이다.

## 적용 화면

- [하네스 대시보드](../../100-views/harness-dashboard.html): 작업 흐름 탭·단계 상세·스킬 검색·운영 정보.
- [논문 라이브러리](../../100-views/paper-library.html): 통계·검색·필터·논문 카드·리뷰 팝업·방법 구조도.
- [사고실험](../../100-views/thought-experiments.html): 상태 필터·가설·반증 조건·관련 기록.

## 공통 정본

색상·타이포그래피·반응형·컴포넌트 스타일은 `100-views/assets/research-ui.css`, 헤더·메뉴·주요 링크는 `.scripts/bin/research_ui.py`에서 관리한다. 세 HTML 생성기가 함께 사용한다. HTML과 `100-views/assets/research-ui.css`는 같은 저장소 구조에서 열어야 한다.

Blurple `#5865f2`, canvas `#0a0d3a`, indigo surface `#1e2353`, magenta `#ec48bd`를 적용했다. Green `#35ed7e`는 화면별 주요 탐색 버튼에 사용한다. 카드 반경은 16–40px, 내용 폭은 1200px, 조작 영역은 최소 44px이다. 모바일 메뉴는 768px 아래에서 접히며, 큰 표와 방법 흐름도는 내부 가로 스크롤을 사용한다. 애니메이션 축소 설정을 존중한다.

ABC Ginto Nord·ggsans는 저장소에 포함되어 있지 않다. CSS는 문서의 대체 폰트와 시스템 sans-serif를 차례로 사용하며 외부 폰트를 자동 다운로드하지 않는다. 실제 글꼴은 기기에 설치된 폰트에 따라 달라진다.

스타일 수정은 즉시 반영된다. 헤더·화면 내용 수정은 해당 `.scripts/bin/*_html.py` 또는 `harness_dashboard.py`로 다시 생성한다. Graphify 자체 생성 화면은 이 UI 테마의 관리 범위에 포함하지 않는다.
