# Daily Paper Candidates — 운영 안내

일일 후보 루프는 Orca Automation에서 예약한다. 이 저장소 문서는 권장 실행 기준을 설명하며, 실제 예약 ID·활성 상태·계정 연결 정보는 로컬 Orca 설정에서 확인한다.

## 권장 동작

- 컴퓨터 비전 1편, 멀티모달 1편, 사용자 관심 분야 1편을 후보로 찾는다.
- 최소 두 학술 출처에서 확인하고 공식 학회 발표·게재와 원문을 검증한다.
- 후보는 채팅으로만 제시한다. 사용자가 채택하기 전에는 PDF·Keep·JSON·인덱스를 수정하지 않는다.
- 뉴스 수집, 연구 파일 생성, Git commit/push를 수행하지 않는다.
- 날짜별 사용자 선정 계획은 `03-Trends/daily/YYYY-MM-DD-plan.md`에 기록한다.

## 일반 예약 예시

Orca 실행 파일은 `ORCA_CLI_COMMAND`가 설정돼 있으면 그 값을 우선한다. 그렇지 않으면 Linux에서 `orca-ide`가 PATH에 있을 때 이를 사용하고, 나머지는 `orca`를 사용한다. 아래 명령의 `orca`는 해당 환경에서 선택한 실행 파일로 바꾼다.

```bash
orca automations list --json
orca automations create --name "research-daily-candidates" \
  --trigger daily --time 09:00 --timezone Asia/Seoul \
  --provider <codex|claude|omp> --workspace path:<이 저장소 절대경로> \
  --fresh-session --disabled \
  --prompt "daily-digest-loop 스킬을 읽고 그 절차대로 오늘(KST) 후보 3편을 채팅으로만 제시하라. 파일을 만들거나 수정하지 않는다." \
  --json
orca automations run <id> --json
orca automations edit <id> --enabled --json
```

`<codex|claude|omp>`, `<이 저장소 절대경로>`, `<id>`는 실제 값으로 바꾸며 꺾쇠는 입력하지 않는다. 기존 체크아웃을 지정하고 비활성 상태로 만들어 한 번 실행한 결과를 확인한 뒤 활성화한다. 모델 지정이 필요하면 `--extra-agent-args="--model <selector>"`를 create에 추가한다. omp에는 `--effort`를 전달하지 않는다. 자동화 프롬프트는 슬래시 명령 대신 자연어로 스킬을 지정한다.

## 운영 확인

Orca Automation에서 예약 시각, 실행 작업 폴더, 연결된 스킬, 최근 실행 완료 여부를 확인한다. 변경은 기존 자동화를 검토해 반영하고 중복 예약을 만들지 않는다. 토큰·계정 식별자·개인 컴퓨터 경로는 저장소에 기록하지 않는다.
