---
name: daily-digest-loop
description: Run one repeatable daily cycle that collects three current AI/ML/CS papers and three news issues, saves the dated digest, shows the result in chat, and commits only that cycle's changes.
---

# Daily Digest Loop

이 스킬의 한 번의 실행은 **오늘의 수집·정리·채팅 보고·Git 커밋**까지 완료하는 한 회차다. 프로세스를 무한히 실행하지 않는다. 다음 호출에서는 Asia/Seoul 기준 새 날짜로 같은 회차를 다시 수행한다.

## 회차 순서

1. Asia/Seoul 기준 `YYYY-MM-DD`를 확정한다. `notes/trends/{날짜}.md`가 이미 있으면 먼저 읽고, 기존 사실과 출처를 보존하면서 필요한 경우에만 갱신한다. 덮어쓸 때는 새 근거가 확인된 부분만 바꾼다.
2. [paper-search](../paper-search/SKILL.md) 절차로 최신 AI/ML/CS 논문을 검색한다. 논문 3편은 공식 메타데이터와 가능하면 원문 PDF를 확인하고, 각 사실에 섹션·표·식·페이지 근거를 붙인다.
3. 최신 신뢰 출처로 시사이슈 3건을 확인한다. 회사·정부의 1차 발표와 Reuters/AP 등 권위 매체를 우선하며, 회사의 자체 주장과 독립적으로 검증된 사실을 구분한다.
4. `notes/trends/{날짜}.md`에 저장한다. 각 논문·이슈에 출처, 원문 링크, 핵심 요약, 중요한 이유를 포함하고, 한국어 본문과 원어 고유명사 표기를 유지한다.
5. 검색과 원문 확인을 모두 마친 뒤, [paper-summary](../paper-summary/SKILL.md)의 채팅 형식에 따라 논문 3편의 `초록 / 전체적인 주장 / 메소드 / 한계`와 시사이슈 3건을 사용자에게 보여준다. 파일 저장 사실만 보고하고 채팅 요약을 생략하지 않는다.
6. 링크·날짜·수치·PDF 경로와 `git diff --check`를 검증한다. 그 회차에서 만든 파일만 명시적으로 stage한다. `git add -A`나 광범위한 패턴으로 사용자의 무관한 변경을 포함하지 않는다.
7. 다음 형식으로 커밋한다.

   ```text
   chore(digest): add daily paper and news digest YYYY-MM-DD
   ```

   커밋 성공 여부와 commit hash를 채팅 최종 요약에 포함한다. 변경 사항이 없으면 빈 커밋을 만들지 않는다.

## 커밋 안전 규칙

- 실행 시작 전 `git status --short`를 확인하고, 기존 변경 파일 목록을 기록한다.
- 실행 후 기존 변경은 stage하지 않는다. 새 다이제스트, 새 PDF, 인덱스·메모리·경로 갱신, 이 스킬처럼 해당 회차에서 만든 파일만 추가한다.
- 커밋 전 `git diff --cached --name-status`로 staged 범위를 확인한다. 범위가 예상과 다르면 커밋하지 말고 원인을 보고한다.
- Git 사용자 설정이 없거나 충돌·후크 실패로 커밋할 수 없으면 변경을 보존하고, 실패 원인과 수동 실행 명령을 채팅에 알린다.
- PDF 이동·이름 변경은 날짜 폴더 규칙을 따르되, 기존 리뷰·인덱스 링크를 함께 갱신하고 깨진 링크를 검사한다.

## 종료 조건

한 회차의 종료 조건은 (a) 논문 3편과 시사이슈 3건을 출처와 함께 파일·채팅에 반영했고, (b) 검증을 마쳤으며, (c) 해당 회차 변경만 커밋한 상태다. 논문이나 이슈를 3건 확보하지 못하면 임의로 채우지 말고 부족한 수와 검색 범위를 보고하며, 그 상태를 커밋할지 여부는 사용자가 정한다.
