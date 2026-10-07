# Daily Paper 후보·계획 계약

- `daily-digest-loop`의 새 회차는 논문 후보 3편을 채팅에만 제시한다. 일일 후보 보고서를 날짜별 Markdown 파일로 저장하지 않는다.
- 과거 날짜별 다이제스트는 기록으로 보존한다. 새 논문 선정 계획은 `03-Trends/daily/{YYYY-MM-DD}-plan.md`에만 쓴다.
- 매일 09:00 KST 예약은 Orca Automation에서 관리하며, 이 디렉터리의 plan 파일은 해당 일자의 주제 선정만 제어한다.
- 과거 다이제스트와 날짜별 선정 계획의 정본은 모두 이 디렉터리다. `notes/trends/` 경로는 폐기했으며 새 산출물·링크 대상으로 사용하지 않는다.
- 일일 후보는 공식 학회 발표·게재를 검증하고, 미확인 슬롯은 임의로 채우지 않는다.
- 사용자가 후보를 채택한 뒤에만 `paper-search`가 정본 PDF·Keep·인덱스·JSON에 등록한다.

실제 Orca 예약 ID, 연결 설정, 시험 실행 및 상태 확인 명령은 [운영 기록](../../docs/daily-orca-automation.md)을 참고한다.
