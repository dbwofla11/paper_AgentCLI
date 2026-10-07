# 연구 하네스 온보딩 도구

이 문서는 **다른 저장소에 공통 스킬을 옮기는 도구**를 설명한다. 이 논문 저장소를 처음 사용하는 사람은 [노트북 온보딩 안내](onboarding.md)에서 에이전트 설치·로그인·첫 실행을 시작한다. 설치기를 이 저장소 자체에 실행할 필요는 없다.

`.scripts/bin/install_research_harness.py`는 다른 저장소에 공통 스킬과 최소 안내를 설치한다. PDF, 논문 JSON, 리뷰 규칙 전용 경로, MCP 서버 주소·비밀값은 복사하지 않는다. 공통 스킬의 정본은 대상 저장소의 `.agents/skills/`다.

## 사용

```bash
python3 /path/to/paper_AgentCLI/.scripts/bin/install_research_harness.py /path/to/repo --host codex --host claude
python3 /path/to/paper_AgentCLI/.scripts/bin/install_research_harness.py /path/to/repo --host codex --host claude --apply
python3 /path/to/repo/.scripts/bin/research_harness_check.py
python3 /path/to/paper_AgentCLI/.scripts/bin/install_research_harness.py /path/to/repo --remove
```

기본값은 dry-run이다. 기존 `AGENTS.md`, `CLAUDE.md`, 파일, 스킬, 심볼릭 링크는 덮어쓰지 않고 충돌로 보고한다. `--conflict append`는 `AGENTS.md`와 `CLAUDE.md`에만 관리 마커가 있는 안내 블록을 추가하며, 원본 백업을 만든다. `--remove`는 manifest에 기록된 파일의 현재 해시 또는 링크 대상이 설치 시점과 일치할 때만 삭제한다.

`--link-mode auto`는 심볼릭 링크를 만들고 운영체제가 이를 허용하지 않으면 복사로 대체한다. `--link-mode copy`는 호스트 디렉터리에 스킬 사본을 만든다. 복사 방식은 `.agents/skills/`와 동기화가 자동 유지되지 않으므로 업데이트 때 재설치하고 충돌을 확인해야 한다.

## 논문 화면·리뷰 실행기도 함께 설치

빈 대상 저장소에 `papers` 프로필을 설치하면 실행기·생성기·템플릿·화면 자산·스킬을 설치하고 본인의 에이전트를 자동 연결한다. 개인 논문 PDF·JSON·리뷰·계정 설정은 복사하지 않는다.

```bash
python3 .scripts/bin/install_research_harness.py /path/to/new-repo --profile papers --apply
cd /path/to/new-repo
python3 .scripts/bin/onboard_research.py
```

설치 시 로그인하지 않았거나 CLI가 없으면 파일 설치는 유지하고 연결 실패를 보고한다. 본인의 CLI 설치·로그인 후 마지막 명령을 다시 실행한다. `--agent claude` 또는 `--agent codex`로 선택할 수 있다. 기본 `skills` 프로필은 기존의 공통 스킬 설치 동작을 유지한다. 기존 파일 충돌은 보존하며, 관리 블록 추가는 `--conflict append`로 요청한다.

## 지원 및 한계

- Codex CLI: `.agents/skills/`에서 저장소 스킬을 탐색한다. `.codex/skills/` 링크는 이 설치기의 호환성 미러이며, 현재 Codex 공식 경로의 필수 요건은 아니다.
- Claude Code: `.agents/skills/` 공통 소스와 `.claude/skills/` 진입점 링크를 만든다.
- 기본 skills 프로필은 스킬 디렉터리 탐색 여부만 구성한다. 대상 저장소에서 Codex/Claude 실행, MCP 접근, PDF 페이지 읽기 또는 특정 도구 호출이 실제로 작동하는지는 보장하지 않는다.
- generic routing 파일은 orientation/implementation/review/validation을 안내하고 대상 저장소의 자체 빌드·테스트를 그대로 사용한다. 논문 전용 폴더와 검증 규칙은 만들지 않는다.
- `--diagnose` 또는 설치된 `research_harness_check.py`는 manifest, 파일, 스킬 경로만 확인하며 프로젝트 테스트를 실행하지 않는다.
- 기존 설정 파일이나 스킬을 병합하지 않는다. 충돌 파일은 먼저 보여주며 기본 정책은 보존이다. 사용자는 dry-run 결과를 검토한 뒤 명시적으로 `--apply`해야 한다.
- 설치 manifest `.research-harness-manifest.json`은 생성·수정 파일의 소유권과 해시를 추적한다. 자격 증명이나 API 키를 저장하지 않는다.

Skills use the `SKILL.md` directory format described by [Codex](https://developers.openai.com/codex/skills) and [Claude Code](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview). Codex scans repository `.agents/skills/`; Claude Code discovers repository skills under `.claude/skills/`. The installer exposes one canonical source through these host-specific locations; it does not configure credentials or assert that an agent runtime is available.
