# 연구·학습 홈 (Home / MOC)

이 저장소의 사람용 시작 페이지이자 지도(Map of Content, MOC)다. 작업 규칙은 [AGENTS.md](../AGENTS.md), 저장소 소개와 빠른 시작은 [README.md](../README.md)를 본다. 여기서는 각 영역의 진입점만 안내한다.

## 연구 화면

- [하네스](../100-views/harness-dashboard.html) · [논문 라이브러리](../100-views/paper-library.html) · [사고실험](../100-views/thought-experiments.html)
- [화면 관리·실행 안내](../100-views/README.md)

## 지금 하는 일

- [RF sensing 연구 아이디어](../05-ideas/README.md) — 방 구조·목표 작업이 bandwidth와 Tx/Rx 배치 선택에 미치는 영향 요인 분석.
- [RF sensing 공부노트](../02-Concepts/README.md#rf-sensing-시작점) — bandwidth, multipath, synchronization, reconstruction을 논문 간에 연결.
- [WAVEVERSE 검증 프로젝트](../04-Projects/README.md#waveverse-forward-simulation-검증) — forward simulation으로 inverse reconstruction의 가능 범위를 측정.

## 영역 지도

| 영역 | 역할 | 현재 정본 / 시작점 |
|---|---|---|
| [00-Inbox](../00-Inbox/README.md) | 아직 분류하지 않은 질문·링크·관찰 | `00-Inbox/` |
| [01-Papers](../01-Papers/README.md) | 원문·리뷰·트리아지·목록 | `01-Papers/` |
| [02-Concepts](../02-Concepts/README.md) | 내가 이해한 내용을 쌓는 공부노트 | `02-Concepts/` |
| [03-Trends](../03-Trends/README.md) | 일일 논문 후보와 날짜별 주제 계획 | `03-Trends/daily/` |
| [04-Projects](../04-Projects/README.md) | 실험·구현·스터디 실행 단위 | `04-Projects/` |
| [05-ideas](../05-ideas/README.md) | 검증 전 연구 가설과 사고실험 | `05-ideas/` |
| [90-Templates](../90-Templates/README.md) | 노트 작성 양식 | `90-Templates/`, `templates/` |
| [99-Attachments](../99-Attachments/README.md) | 그림·로그·비원문 첨부 | `99-Attachments/` |

## 논문 상태와 보관함

- [전체 논문 인덱스](../01-Papers/index.md) — 읽을 예정·트리아지·읽는 중·완료 상태.
- [Keep 목록](../01-Papers/keep.md) — 나중에 읽거나 재검토할 논문/조사 주제. **유지한다.**
- [즐겨찾기](../01-Papers/favorites.md) — 개인적으로 다시 보고 싶은 논문. **유지한다.**
- [논문 JSON 시각화](../100-views/paper-library.html) — 논문 레코드 검색·필터·분포 보기.

Keep은 대기열이고, 즐겨찾기는 선호 기록이다. 둘을 공부노트나 프로젝트 목록으로 섞지 않는다.

## 작업 안내

- [처음 쓰는 사람의 노트북 온보딩](onboarding.md) — 설치·로그인·진단·첫 실행·문제 해결.
- [다른 저장소로 스킬 설치](research-harness-installer.md) — 공통 스킬을 옮기는 별도 도구.
- [연구 하네스 그래프](Harness-Graph.md) — 연구 단계와 실행 순서.
- [스킬 카탈로그](Skill-Catalog.md) — 설치된 스킬을 찾는 목록.
- [작업 규칙](../AGENTS.md) — 공통 에이전트 지침과 원문 근거 기준.
- 리뷰에서 나온 개념 후보는 `00-Inbox/concept-candidates/`에서 확인한다. 이해를 확인·수정하고 승격을 요청하기 전까지 `02-Concepts/` 정본으로 옮기지 않는다.
- 하네스 검사: 저장소 루트에서 `python3 .scripts/bin/verify_harness.py`

각 폴더의 README와 라이브러리 파일은 해당 영역의 세부 시작점이다. 정본 파일은 이동하지 않고 현재 위치에서 관리한다.
