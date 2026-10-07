# 데이터 저장·관리

## 역할

원문 PDF, 사람용 리뷰, 기계 판독 JSON, 가설, 실행 증거를 각각 정본 경로에 보관한다. 이 Notion 공간에는 운영 안내와 도식을 정리하며 개별 논문 PDF나 연구 데이터 전체를 복제하지 않는다.

## 논문 저장

- 원문: 01-Papers/pdfs/{category}/
- 리뷰: 01-Papers/reviews/{category}/ · 한 논문 한 파일
- 첫 판정: 01-Papers/triage/
- 구조화 기록: 01-Papers/library/{slug}.json
- 읽기 상태: index.md · 읽기/조사 대기열: keep.md · 선호: favorites.md

분야는 wifi-csi / game-ai / agent-ai / computer-vision / other다. 파일명은 연도-제1저자성-짧은슬러그를 따른다. JSON은 수집 시 메타데이터를 기록하고 리뷰 후 근거가 있는 5축 분석을 보강한다.

## 사고실험 저장

- 가설·반증 조건: 05-ideas/thought-experiments/
- 기획·심사·실행 증거: 04-Projects/thought-experiment-runs/{slug}/
- 문헌 조사 작업: 04-Projects/research-todo/queue.json
- 자동 리뷰 작업: 04-Projects/review-queue/queue.json
- 현재 진척 backend: notion · repository 선택 시 progress.md가 상태 정본

## 재생성

HTML은 정본에서 다시 만든다. Graphify는 검증된 정본에서 관계를 추출한다. 개념 후보는 사용자가 이해를 확인하고 승격 요청하기 전에는 학습 정본·지식 그래프로 들어가지 않는다.

## 근거 문서

- `AGENTS.md`
- `.scripts/docs/paper-record.schema.json`
- `.scripts/docs/idea-analysis.schema.json`
- `04-Projects/thought-experiment-runs/PROGRESS_BACKEND.md`

기준일: 2026-10-07. 이 페이지는 저장소 설정을 설명하는 안내이며 실행 상태의 정본을 대체하지 않습니다.
