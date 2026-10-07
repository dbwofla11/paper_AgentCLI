# 구조화 데이터·검증 계약

## 역할

논문 JSON은 paper_record.py로 필수 필드와 5축 근거를 검사한다. 아이디어 analysis.json은 idea_analysis.py로 동일 근거·세 심사·사용자 결정을 검사한다. 문헌 TODO는 literature-investigation / research-todo 스키마를 따른다.

## 검증 도구

- verify_harness.py: 정본·스킬 연결·라우팅 참조 검사
- onboarding_check.py: 실행 환경 준비 확인
- graphify_sync.py: 의미 동기화 begin / complete / fail 상태 기록

형식 검사 통과가 내용의 과학적 타당성이나 실제 에이전트 실행 성공을 보장하지는 않는다.

## 근거 문서

- `.scripts/docs/paper-record.schema.json`
- `.scripts/docs/idea-analysis.schema.json`
- `.scripts/docs/literature-investigation.schema.json`
- `.scripts/docs/research-todo.schema.json`
- `04-Projects/validation/critic-output.schema.json`

기준일: 2026-10-07. 이 페이지는 저장소 설정을 설명하는 안내이며 실행 상태의 정본을 대체하지 않습니다.
