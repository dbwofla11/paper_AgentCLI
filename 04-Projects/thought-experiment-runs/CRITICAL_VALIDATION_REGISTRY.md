# 비판 검증 레지스트리

사고실험·연구 기획의 `grill-me` 및 독립 심사 진행 상황을 한곳에서 본다. 세부 근거와 결정은 각 `{slug}/` 폴더의 `brief.md`, `critique-*.md`, `critique.md`에 남긴다.

현재 `PROGRESS_BACKEND.md`는 Notion을 정본으로 선택했지만 대상이 아직 연결되지 않았다. 연결 전에는 이 파일을 임시 로컬 레지스트리로 사용한다. 연결 후에는 Notion의 동일 항목이 정본이며, 이 표는 그 링크와 최신 상태를 가리키는 인덱스다.

## 상태 범례

- 전체 상태: `미심사` → `grill-me` → `심사 대기` → `심사 중` → `보완 필요` / `실험 가능` / `보류` / `폐기`
- 역할 상태: `대기` / `진행` / `통과` / `조건부` / `치명적 결함` / `해당 없음`
- `실험 가능`은 세 역할의 치명적 결함이 해소되고 사용자가 승인했을 때만 쓴다. 이 상태도 실험 성공이나 논문 기여를 뜻하지 않는다.

## 기획 목록

| slug | 기획 | 원본 노트 | grill-me | method | repro | novelty | 전체 상태 | 사용자 결정 | 정본/증거 | 갱신일 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| csi-action-conditioned-latent-diffusion | CSI action-conditioned latent diffusion | `05-ideas/thought-experiments/2026-09-04-csi-action-conditioned-latent-diffusion.md` | 대기 | 대기 | 대기 | 대기 | 미심사 | 미결정 | 로컬 임시 | 2026-09-18 |
| latentcsi-cross-domain | LatentCSI cross-domain | `05-ideas/thought-experiments/2026-09-04-latentcsi-cross-domain.md` | 대기 | 대기 | 대기 | 대기 | 미심사 | 미결정 | 로컬 임시 | 2026-09-18 |
| rf-room-sensing-easy | RF room sensing | `05-ideas/thought-experiments/2026-09-07-rf-room-sensing-easy.md` | 대기 | 대기 | 대기 | 대기 | 미심사 | 미결정 | 로컬 임시 | 2026-09-18 |
| room-aware-distributed-rf-configuration | Room-aware distributed RF configuration | `05-ideas/thought-experiments/2026-09-07-room-aware-distributed-rf-configuration.md` | 대기 | 대기 | 대기 | 대기 | 미심사 | 미결정 | 로컬 임시 | 2026-09-18 |
| agents-api-rf-simulation-loop | Agents API RF simulation loop | `05-ideas/thought-experiments/2026-09-15-agents-api-rf-simulation-loop.md` | 대기 | 대기 | 대기 | 대기 | 미심사 | 미결정 | 로컬 임시 | 2026-09-18 |

## 갱신 규칙

1. 기획을 새로 등록할 때 slug, 원본 노트, 전체 상태 `미심사`, 각 역할 상태 `대기`를 넣는다.
2. 사용자가 grill-me 결과를 승인하면 `brief.md` 링크를 추가하고 전체 상태를 `심사 대기`로 바꾼다.
3. 각 독립 심사 결과가 확정될 때 해당 역할 상태와 `critique-{role}.md` 증거 링크를 갱신한다.
4. 세 심사가 끝나면 `critique.md`의 사용자 결정만 전체 상태에 반영한다. 심사자나 주 에이전트가 임의로 `실험 가능`을 확정하지 않는다.
5. Notion 대상이 정해진 뒤에는 같은 필드를 Notion에도 유지하고, 이 파일의 `정본/증거` 열에 해당 Notion 링크를 기록한다.
