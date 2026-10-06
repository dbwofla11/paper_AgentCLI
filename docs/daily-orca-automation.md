# Daily Paper Candidates — Orca 운영 기록

2026-10-02에 기존 자동화를 최신 `.agents/skills/daily-digest-loop/SKILL.md`에 연결했다. 이 문서는 설정 기록이며, 현재 실행 상태의 정본은 Orca Automation이다.

## 연결 설정

- 자동화: `Daily Paper Candidates`
- Automation ID: `03168daf-9499-4ca3-a6ba-2e93e65ed543`
- 주기: 매일 09:00, `Asia/Seoul`, 활성화
- Provider: `codex` (모델은 Orca 실행기 설정을 따른다)
- Workspace: `c4193deb-49d9-425d-bf23-dafb14134a51::/home/user/Desktop/논문읽기어시스트/paper_AgentCLI`
- 현재 작업 폴더에서 매번 새 세션 실행. 새 Git worktree를 만들지 않아 아직 커밋되지 않은 최신 스킬도 읽는다.
- 결과: Orca 자동화 실행 세션의 채팅. 현재 사용자의 기존 대화에 자동 삽입되는 것은 아니다.
- CV / 멀티모달 / 사용자 관심 분야 각 1편. 최소 두 학술 소스 검색, 공식 학회 게재 확인, 원문 확인.
- 뉴스, 파일 생성·수정, PDF 저장, JSON/Keep/인덱스 등록, 개념 노트, 실험, commit/push 금지. 후보 채택 후에만 별도 수집한다.
- 날짜별 주제 계획: `03-Trends/daily/YYYY-MM-DD-plan.md`.

## 점검 및 시험

기존 예약의 프롬프트는 폐기된 `notes/trends/` 저장과 뉴스 검색을 지시했다. 과거 실행 기록에는 `codex: command not found`와 완료 감지 실패가 있었다. 예약을 중복 생성하지 않고 기존 ID의 프롬프트를 교체했다.

시험 실행: `c2738ebf-4ea1-499c-b113-4508ba2b174e` (32회차). 실제 Codex 세션 실행, 스킬·관심 주제 확인 및 웹 검색 시작을 확인했다. 이 기록만으로 논문 후보 결과의 완성이나 다음 예약의 성공을 보장하지 않는다. 완료 상태는 아래 명령으로 확인한다.

```bash
orca-ide open --json
orca-ide automations show 03168daf-9499-4ca3-a6ba-2e93e65ed543 --json
orca-ide automations runs --id 03168daf-9499-4ca3-a6ba-2e93e65ed543 --json
```

수동 실행은 기존 회차가 실행 중이지 않은지 먼저 확인한 뒤 수행한다.

```bash
orca-ide automations run 03168daf-9499-4ca3-a6ba-2e93e65ed543 --json
```

로컬 실행 호스트와 Orca 런타임이 가동 중이어야 한다. PC 종료 상태의 실행, 부팅 시 자동 시작, 원격 서버 상시 실행은 이번 연결 범위에 포함하지 않는다. 놓친 실행은 현재 Orca 설정상 720분 유예 내 한 번 실행한다.
