# Claude Code 안내

저장소의 공통 작업 규칙과 연구 하네스 정본은 [`AGENTS.md`](AGENTS.md)다. Claude Code는 아래 내용을 포함해 동일한 규칙을 따른다.

@AGENTS.md

## Claude 전용 설정

- Claude Code 전용 권한과 도구 허용목록은 [`.claude/settings.json`](.claude/settings.json)에서 관리한다.
- 공통 스킬의 유일한 정본은 [`.agents/skills/`](.agents/skills/)다. Claude Code가 자동 탐색하는 [`.claude/skills/`](.claude/skills/) 항목은 정본을 가리키는 심볼릭 링크로만 둔다. 별도 정의나 복사본을 만들지 않는다.
- Claude 전용 스킬만 `.claude/skills/`에 실제 파일로 둔다 (현재 `math-derivation`).

여기에 공통 워크플로·근거 규칙을 복사하지 않는다. 공통 규칙을 바꿀 때는 `AGENTS.md`만 수정한다.
