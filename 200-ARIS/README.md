# ARIS 설치 안내

[Auto-Research-In-Sleep (ARIS)](https://github.com/wanshuiyin/auto-claude-code-research-in-sleep)의 Codex용 연구 스킬을 이 프로젝트에서 사용할 수 있도록 설치했다.

- 원본 스냅샷: `upstream/` (MIT 라이선스, 원본 `upstream/LICENSE`)
- 원본 커밋: `2927b40b2ea37774de53763338c5e8f91a7601e6`
- Codex용 스킬과 공통 참조: `upstream/skills/skills-codex/`
- 프로젝트 스킬 검색 경로: `.agents/skills/`에서 위 스냅샷으로 연결 (87개 스킬과 `shared-references`)
- 설치 기록: `.aris/installed-skills-codex.txt`; 설치 도구가 `~/.aris/repo`에도 원본 경로를 기록했다.

Codex 세션을 새로 시작하면 스킬 목록이 다시 로드된다. 예를 들어 `$research-lit`, `$idea-creator`, `$experiment-plan`, `$citation-crosscheck`를 명시해 사용할 수 있다. 전체 목록은 `upstream/skills/skills-codex/README.md`와 각 스킬의 `SKILL.md`를 참고한다.

## 기존 연구 하네스와 함께 사용

논문을 검색하거나 추천할 때 `01-Papers/reference/cs-conferences.csv`의 학술대회 목록을 참고한다. 목록 밖 논문도 관련성이 있으면 포함하며, 실제 발표·게재와 학회 트랙은 공식 출처로 확인한다.

이 저장소의 `AGENTS.md`와 사용자의 지시가 우선이다. 논문 PDF·리뷰·JSON과 아이디어의 정본 경로, 개념 노트 승격 조건, 근거 및 아이디어 검증 규칙을 그대로 따른다. ARIS의 예시 `papers/`, `research-wiki/` 등의 경로가 이 저장소의 정본을 대체하지 않는다. 같은 모델 계열의 검토를 독립적인 교차 모델 심사로 표시하지 않는다. 외부 서비스·API·GPU·별도 심사 모델은 해당 스킬이 요구할 때 가용성과 설정을 확인해야 한다.

원본은 Git 작업 트리가 아닌 고정 스냅샷이다. 업데이트할 때는 먼저 새 원본을 검토하고 이 폴더의 스냅샷을 갱신한 뒤 `bash 200-ARIS/upstream/tools/install_aris_codex.sh . --reconcile --no-doc`로 연결을 점검한다. 스킬 심볼릭 링크는 저장소 내 상대 경로다. 설치 기록은 기기별 절대 경로를 포함하므로 저장소를 다른 위치로 옮기면 설치 도구로 설치 기록을 다시 만든다. 기존 연구자료와 원격 저장소에는 자동으로 쓰거나 푸시하지 않는다.
