---
name: daily-digest-loop
description: Run one repeatable daily cycle that collects three current conference-published papers from the allowed categories and three news issues, saves the dated digest, shows the result in chat, commits only that cycle's changes, and pushes the commit with git push origin master.
---

# Daily Digest Loop

이 스킬의 한 번의 실행은 **오늘의 수집·정리·채팅 보고·Git 커밋·`git push origin master`**까지 완료하는 한 회차다. 프로세스를 무한히 실행하지 않는다. 다음 호출에서는 Asia/Seoul 기준 새 날짜로 같은 회차를 다시 수행한다.

## 회차 순서

1. Asia/Seoul 기준 `YYYY-MM-DD`를 확정한다. `notes/trends/{날짜}.md`가 이미 있으면 먼저 읽고, 기존 사실과 출처를 보존하면서 필요한 경우에만 갱신한다. 덮어쓸 때는 새 근거가 확인된 부분만 바꾼다. `notes/trends/{날짜}-plan.md`가 있으면 해당 날짜에만 적용하는 사용자 지정 논문 선정 계획으로 읽고, 논문 슬롯 수와 주제 배분을 우선 준수한다. 계획 파일이 없는 날짜에는 일반적인 최신 논문 선정으로 진행한다.
2. [paper-search](../paper-search/SKILL.md) 절차로 최신 논문을 검색하되, 아래 수집 정책을 반드시 적용한다.
   - **허용 카테고리:** `WiFi CSI`, `게임 AI (Game AI)`, `에이전트 AI (Agent AI)`, `컴퓨터 비전 (Computer Vision)`만 사용한다. 매 회차는 이 목록에서 하나 이상의 카테고리를 선택해 정확히 3편을 구성하며, 카테고리별 고정 배분은 두지 않는다. 날짜별 plan이 있으면 plan의 배분을 우선하되, 이 허용 목록과 학회 발표·게재 조건은 어떤 plan도 완화하거나 덮어쓸 수 없다.
   - **학회 발표·게재 확인:** arXiv preprint만인 논문은 제외한다. 공식 conference proceedings, 출판사 논문 페이지, 또는 학회 공식 발표/accepted-paper 프로그램과 논문 원문에서 발표·게재를 교차 확인한 논문만 포함한다. `submitted`, `under review`, `accepted`, `to appear`만 적힌 arXiv 항목은 공식 발표·게재가 추가 확인되지 않으면 제외한다. 학회명·연도·논문 유형(regular/short/workshop 등)을 기록한다.
   - **카테고리 판정:** 제목·초록의 키워드만으로 분류하지 말고 원문이 실제로 다루는 입력·태스크·방법·실험을 확인한다. WiFi CSI는 WiFi channel state information 또는 그에 직접 연결된 WiFi sensing을, 게임 AI는 게임 플레이·게임 에이전트·게임 생성·게임 분석을, 에이전트 AI는 자율/LLM agent·tool use·planning·agent orchestration을, 컴퓨터 비전은 image/video/3D visual perception·recognition·generation을 뜻한다. 애매하면 `[확인 필요]`로 표시하고 목록에서 제외한다.
   - 논문 3편은 공식 메타데이터와 가능하면 원문 PDF를 확인하고, 각 사실에 섹션·표·식·페이지 근거를 붙인다. 날짜별 계획이 있으면 계획에 적힌 슬롯별 주제를 먼저 검색한다. 사용자 표현이 모호할 때는 관련 원어로 확장할 수 있지만, 논문이 실제로 다루는 범위만 채택하고 근거 없는 등치는 하지 않는다.
3. 최신 신뢰 출처로 시사이슈 3건을 확인한다. 회사·정부의 1차 발표와 Reuters/AP 등 권위 매체를 우선하며, 회사의 자체 주장과 독립적으로 검증된 사실을 구분한다.
4. `notes/trends/{날짜}.md`에 저장한다. 각 논문·이슈에 출처, 원문 링크, 핵심 요약, 중요한 이유를 포함하고, 논문마다 허용 카테고리·학회·연도·발표/게재 확인 근거를 명시한다. 한국어 본문과 원어 고유명사 표기를 유지한다.
5. 검색과 원문 확인을 모두 마친 뒤, [paper-summary](../paper-summary/SKILL.md)의 채팅 형식에 따라 논문 3편의 `초록 / 전체적인 주장 / 메소드 / 한계`와 시사이슈 3건을 사용자에게 보여준다. 파일 저장 사실만 보고하고 채팅 요약을 생략하지 않는다.
6. 링크·날짜·수치·PDF 경로와 `git diff --check`를 검증한다. 그 회차에서 만든 파일만 명시적으로 stage한다. `git add -A`나 광범위한 패턴으로 사용자의 무관한 변경을 포함하지 않는다.
7. 다음 형식으로 커밋한다.

   ```text
   chore(digest): add daily paper and news digest YYYY-MM-DD
   ```

   커밋 성공 여부와 commit hash를 채팅 최종 요약에 포함한다. 변경 사항이 없으면 빈 커밋을 만들지 않는다.
8. 커밋 직후 현재 브랜치가 `master`이고 `origin` remote가 설정되어 있는지 확인한 뒤 정확히 `git push origin master`를 실행한다. push 성공 여부와 원격 ref를 채팅 최종 요약에 포함한다. 원격이 없거나 인증·네트워크·non-fast-forward 오류가 나면 로컬 커밋은 보존하고 push 실패 원인과 재시도 명령을 보고한다. force push는 사용하지 않는다.

## 커밋 안전 규칙

- 실행 시작 전 `git status --short`를 확인하고, 기존 변경 파일 목록을 기록한다.
- 실행 후 기존 변경은 stage하지 않는다. 새 다이제스트, 새 PDF, 인덱스·메모리·경로 갱신, 이 스킬처럼 해당 회차에서 만든 파일만 추가한다.
- 커밋 전 `git diff --cached --name-status`로 staged 범위를 확인한다. 범위가 예상과 다르면 커밋하지 말고 원인을 보고한다.
- Git 사용자 설정이 없거나 충돌·후크 실패로 커밋할 수 없으면 변경을 보존하고, 실패 원인과 수동 실행 명령을 채팅에 알린다.
- push 전 `git remote -v`와 현재 브랜치를 확인한다. 현재 브랜치가 `master`가 아니면 `git push origin master`를 실행하지 않고 중단·보고한다. push 대상은 해당 회차에서 만든 커밋이며, 원격 이력을 덮어쓰지 않는다.
- 커밋 후 push가 실패해도 커밋을 되돌리거나 강제 push하지 않는다. 재시도 가능한 오류인지와 현재 로컬/원격 상태를 보고한다.
- PDF 이동·이름 변경은 날짜 폴더 규칙을 따르되, 기존 리뷰·인덱스 링크를 함께 갱신하고 깨진 링크를 검사한다.

## 종료 조건

한 회차의 종료 조건은 (a) 논문 3편과 시사이슈 3건을 출처와 함께 파일·채팅에 반영했고, (b) 검증을 마쳤으며, (c) 해당 회차 변경만 커밋했고, (d) `git push origin master`가 성공한 상태다. 논문이나 이슈를 3건 확보하지 못하면 임의로 채우지 말고 부족한 수와 검색 범위를 보고하며, 그 상태를 커밋·push할지 여부는 사용자가 정한다.
