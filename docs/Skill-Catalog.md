# 스킬 카탈로그 — 보기 전용

이 문서는 스킬을 찾기 위한 목록이다. 실행 순서와 다음 단계 선택은 [Harness-Graph](Harness-Graph.md)와 `.scripts/bin/research_workflow.py`가 담당한다.

[HTML 대시보드](../100-views/harness-dashboard.html)는 스킬 설명과 입력·결과·실행 조건을 보여준다. 작업 흐름을 선택해 단계별 상세를 확인하고 스킬 이름·역할을 검색할 수 있다. 스킬 설명은 각 `SKILL.md`에서 읽고, 순서·선택 단계·사용자 확인·병렬 역할은 `.scripts/docs/research-workflow-map.json`을 `research_workflow.py`와 대시보드가 함께 사용한다. 이 흐름도는 실행 안내이며 현재 작업 상태는 별도 대기열에서 관리한다.

| 영역 | 실행 스킬 | 역할·다음 흐름 |
|---|---|---|
| 입력·수집 | `paper-search` | 사용자 업로드 또는 채택된 검색 후보를 확인해 PDF·Keep·논문 JSON으로 등록 |
| 일일 후보 | `daily-digest-loop` | 09:00 KST 예약 실행에서 CV·멀티모달·관심 분야 논문 각 후보를 찾고 채팅으로만 제시 |
| 논문 정독 | `paper-review` | 3패스 정독 후 문제·기존 연구, 핵심 아이디어, 실험 근거, 한계, 관련 연구의 5축을 기록 |
| 공부노트 | `concept-note` | 사용자가 요청·검토한 개념 후보를 `02-Concepts/` 학습 정본으로 생성·수정·통합 |
| 인덱스·목록 | `review-index`, `keep-list`, `paper-favorites` | 읽기 상태·대기열·즐겨찾기 관리 |
| 문헌 맥락 | `related-work`, `paper-relations` | 인용 계보와 저장소 내부 논문 관계를 조사하고 Graphify로 확인 |
| 개념·아이디어 | `thought-experiment-critique`, `critical-validation` | 개념의 전제와 가설을 점검하고, 승인된 기획을 독립 3역할로 심사 |
| 심사 컨텍스트 | `idea_analysis.py` + 세 페르소나 | 지원·대안 문헌 필수 검색, 근거 bundle SHA-256 고정, 분석 JSON 상태·일관성 검사 |
| 실험 | `thought-experiment-runner` | 승인된 가설을 작은 재현 실험과 manifest·결과로 연결 |
| 요약·초안 | `paper-summary`, `paper-draft-logic-review` | 논문 3편 요약, 초안의 주장–근거 연결 검토 |
| 시각화 | `graphify`, `paper-relations` | 논문 JSON을 포함한 저장소 지식 그래프 조회·갱신 |
| 날짜별 선정 | `paper-scheduler` | 특정 날짜 논문 후보의 주제·슬롯 기준을 예약 |

논문 JSON 형식은 `../.scripts/docs/paper-record.schema.json`, 생성·검증 명령은 `../.scripts/bin/paper_record.py`를 따른다.
아이디어 분석 JSON은 `../.scripts/docs/idea-analysis.schema.json`, 초기화·동결·역할 결과 기록·검증은 `../.scripts/bin/idea_analysis.py`를 따른다. 리뷰 후 개념 후보는 Inbox에만 생성되며 사용자의 이해 확인 전에는 그래프와 학습 정본에 들어가지 않는다.

## 운영 도구

| 도구 | 역할 | 갱신 명령 |
|---|---|---|
| `100-views/harness-dashboard.html` | 라우팅·스킬 호스트 링크·페르소나·검증기·Graphify 상태 표시 | `python3 .scripts/bin/harness_dashboard.py` |
| `100-views/paper-library.html` | 논문 JSON 검색, 리뷰 표시, 원문 PDF 열기 | `python3 .scripts/bin/paper_catalog_html.py` |
| `100-views/thought-experiments.html` | 가설·반증 조건·레지스트리/실험/TODO 상태 탐색 | `python3 .scripts/bin/thought_experiments_html.py` |
| `install_research_harness.py` | 다른 저장소용 공통 스킬·안내 설치. dry-run 기본 | `python3 .scripts/bin/install_research_harness.py --help` |
| `research_todo.py` | 문헌 조사 작업 정본·상태·역할 prompt 관리 | `python3 .scripts/bin/research_todo.py --help` |

HTML은 정적 뷰다. 논문 리뷰 실행은 [로컬 리뷰 브리지](paper-review-bridge.md)를 통해서만 요청한다. 에이전트 실행이나 로컬 파일 수정은 로컬 실행기가 별도로 지원하고 검증할 때만 사용할 수 있다.
