# 02-Concepts — 공부노트

여기는 논문 요약 저장소가 아니라 **내가 공부해서 이해한 내용을 다시 설명하는 곳**이다. 한 노트는 여러 논문·강의·실험을 연결할 수 있다.

## 노트 작성 원칙

- 파일명: `주제-이름.md` (예: `multipath.md`, `transformer-attention.md`)
- 정의 → 직관 → 최소 수식/예시 → 자주 헷갈리는 점 → 연결 논문 → 내 질문 순서로 쓴다.
- 논문 사실과 내 설명을 구분한다. 논문 수치·주장은 리뷰 또는 원문 위치를 링크한다.
- 모르는 내용은 채우지 말고 `확인할 것`에 남긴다.
- 새 공부노트는 [템플릿](../90-Templates/study-note-template.md)을 복사해 시작한다.
- 개념 노트 생성·수정은 사용자가 명시적으로 요청할 때만 [concept-note 스킬](../.agents/skills/concept-note/SKILL.md)로 수행한다. 논문 리뷰의 자동 후속 작업으로 노트를 만들지 않는다.
- 논문 리뷰 후 자동으로 생긴 개념 후보는 [Inbox](../00-Inbox/README.md)의 `concept-candidates/`에만 둔다. 사용자가 자신의 이해를 확인·수정하고 승격을 요청해야 이곳의 학습 정본이 된다.
- 정본을 갱신한 뒤에는 `graphify_sync.py begin` → Graphify 스킬 `--update` → `complete`로 그래프 반영 여부를 추적한다.

## RF sensing 시작점

- `bandwidth-and-resolution.md` — 대역폭과 거리/시간 분해능
- `multipath.md` — multipath가 localization과 reconstruction에 주는 정보·혼동
- `synchronization.md` — 독립 ESP32의 시간·위상 동기화 문제
- `distributed-rf-geometry.md` — Tx/Rx 개수·간격·배치와 관측 가능성
- `inverse-reconstruction.md` — CSI forward model과 inverse problem

위 파일들은 아직 만들지 않았다. 첫 공부 때 필요한 것부터 만든다. 관련 사고실험은 [05-ideas](../05-ideas/README.md)에서 관리한다.
