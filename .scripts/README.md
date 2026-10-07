# .scripts — 자동화 안내

자동화 코드와 데이터 계약의 정본은 이 폴더 안에 둔다. 하네스의 큰 흐름은 [Harness-Graph.md](../docs/Harness-Graph.md), 공통 에이전트 지침은 100-views의 [AGENTS.md](../AGENTS.md)에서 관리한다.

- 논문 메타데이터·PDF·인용 조회: [`bin/paper.py`](bin/paper.py)
- 논문 레코드 생성·가져오기·검증: [`bin/paper_record.py`](bin/paper_record.py)
- 논문 JSON 카탈로그 HTML 생성: [`bin/paper_catalog_html.py`](bin/paper_catalog_html.py) → 100-views의 [`100-views/paper-library.html`](../100-views/paper-library.html)
- 아이디어 분석 JSON 초기화·근거 묶음 동결·상태 검증: [`bin/idea_analysis.py`](bin/idea_analysis.py)
- 정본 논문/개념/승인 아이디어의 Graphify 시작·완료·실패 추적: [`bin/graphify_sync.py`](bin/graphify_sync.py)
- `graphify_sync.py begin` 뒤 Graphify 스킬로 `--update`를 수행해야 문서 의미 추출까지 된다. 성공은 `complete`, 실패는 재시도 가능한 `fail`/`pending`으로 기록한다. `status`로 추적 상태를 본다.
- Graphify는 `.graphifyignore`에서 개념 후보, 독립 비평 초안, 동결 packet, 미결 analysis JSON을 제외한다.
- 대기 상태 점검: `python3 .scripts/bin/graphify_sync.py status`. 상태 원장은 `graphify-out/sync-state.json`이며, 미완료 항목은 같은 Graphify 업데이트를 재실행해 `complete` 처리한다.
- 연구 단계별 다음 스킬 라우팅: [`bin/research_workflow.py`](bin/research_workflow.py)
- 구조·라우팅·JSON 스모크 검사: [`bin/verify_harness.py`](bin/verify_harness.py)
- 첫 사용 환경·스킬·선택 도구 진단: [`bin/onboarding_check.py`](bin/onboarding_check.py) — `--host codex|claude`, 선택적으로 `--with-mcp --with-graphify`; [온보딩 안내](../docs/onboarding.md).
- 논문 JSON 데이터 계약: [`docs/paper-record.schema.json`](docs/paper-record.schema.json)
- 아이디어 분석 JSON 데이터 계약: [`docs/idea-analysis.schema.json`](docs/idea-analysis.schema.json)
- 논문 탐색 프로토콜: [`docs/search-protocol.md`](docs/search-protocol.md)

검사는 저장소 루트에서 `python3 .scripts/bin/verify_harness.py`로 실행한다. CLI 회귀 검사는 `python3 -B -m unittest discover -s .scripts/tests -v`로 실행한다. 논문 JSON은 `paper_record.py validate`, 아이디어 JSON은 `idea_analysis.py validate`로 검사한다.

논문 JSON 시각화 갱신은 저장소 루트에서 `python3 .scripts/bin/paper_catalog_html.py`를 실행한다. JSON 제목이 비어 있으면 로컬 PDF의 `pdfinfo` 제목을 사용하고, PDF 메타데이터도 없는 일부 레코드는 확인된 PDF 첫 페이지 제목을 표시용으로 사용한다. 생성된 HTML은 별도 서버나 외부 라이브러리 없이 열 수 있으며, 논문 카드를 클릭하면 저장된 PDF 원문이 새 탭으로 열린다. 리뷰가 있는 논문은 리뷰 Markdown도 HTML 안에 내장해 `리뷰 보기`를 누르면 읽기 창으로 표시한다.
