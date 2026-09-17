# 사고실험: Agents API로 관리하는 RF configuration 영향도 실험 루프

- 작성일: 2026-09-15
- 상태: 가설 단계 — 구현 전
- 출발점: [저가 분산 Wi-Fi CSI reconstruction 정확도의 영향 요인 분석](./2026-09-07-room-aware-distributed-rf-configuration.md), [OpenAI Agents API 조사 메모](../2026-openai-agents-api.notes.md)
- 범위: Agents API는 실험 실행·기록 보조자다. RF forward model, inverse reconstruction, ESP32 동기화의 물리적 타당성을 대신 검증하지 않는다.

## 핵심 질문

Agents API를 이용하면 “방·bandwidth·Tx/Rx 배치·동기화 오차가 Wi-Fi CSI reconstruction 정확도에 미치는 영향”을 사람이 매번 손으로 실행할 때보다 **더 재현 가능하고 덜 누수되게** 분석할 수 있는가?

여기서 성공은 에이전트가 좋은 configuration을 알아내는 것이 아니다. 사람이 사전에 정한 조건표를 빠짐없이 실행하고, 모든 결과에 입력·seed·소프트웨어 버전·실패 원인을 남겨, 영향도 분석을 감사 가능하게 만드는 것이다.

## 먼저 구분할 것: 과학 문제와 자동화 문제

| 층 | 질문 | Agents API가 할 수 있는 일 | Agents API가 해결하지 못하는 일 |
|---|---|---|---|
| RF 물리 | 주어진 방·재질·장치에서 CSI가 어떻게 생기는가? | simulator 실행을 요청하고 결과를 저장한다. | WaveVerse/forward model의 재질, 안테나, multipath 모델이 실제와 맞는지 증명하지 못한다. |
| 역문제 | CSI로 표적 위치·점유·구조를 어느 정도 식별할 수 있는가? | 고정된 inverse solver를 반복 실행하고 지표를 계산한다. | 관측에 없는 정보를 복원하지 못한다. 그럴듯한 결과가 정답이라는 보장도 없다. |
| 실험 설계 | 어떤 요인이 영향이 큰가? | 사전 작성 manifest의 조건을 전수 실행·집계한다. | 실행 뒤에 유리한 조건만 고르는 편향을 막지 못한다. |
| 실제 장치 | 독립 ESP32에서도 순서가 유지되는가? | 로그 정리·재현 명령 생성은 가능하다. | 공통 clock, phase calibration, antenna/AGC 차이를 자동 보정하지 못한다. |

따라서 연구의 중심은 여전히 $F$와 $R$이다. 환경·물체 상태를 $x$, configuration을 $c$, 장치 오차를 $e$, CSI 관측을 $y$라 두면,

$$
y = F(x, c, e) + n, \qquad \hat{x} = R(y, c)
$$

이다. 이번 분석의 대상은 $c$와 $e$가 손실 $L(\hat{x}, x)$에 주는 효과다. Agent는 이 식 밖에서 `$c$를 넣어 실행하고 결과를 기록하는 controller`일 뿐이다.

## 물리적으로 가장 큰 병목

### 1. simulator-to-real gap이 configuration 효과를 뒤집을 수 있다

WaveVerse 같은 simulator가 이상적 위치·재질·안테나·동기를 안다면, simulator 안에서는 bandwidth나 aperture의 효과가 선명해질 수 있다. 그러나 실제 ESP32 CSI에는 packet timing, CFO/SFO, AGC, antenna pattern, quantization, missing packet, per-device phase/delay offset이 얹힌다. 이 오차가 충분히 크면 simulator에서 관찰한 `Rx 추가 → 성능 향상` 순서가 실제에서는 사라질 수 있다.

따라서 **simulator 결과는 configuration의 가능성(possibility)을 보일 뿐, 장치 효과의 크기를 확정하지 않는다.** 이 차이는 실패가 아니라 별도 요인으로 모델링해야 한다.

### 2. phase/time error는 독립 요인이 아니라 geometry 이득의 상한을 만든다

여러 Rx를 coherent하게 합치려면 link 간 상대 위상·지연 기준이 필요하다. 이를 잃으면 새 Rx가 주는 관측은 완전히 쓸모없어지는 것이 아니라, coherent aperture/angle 정보가 약해지고 non-coherent diversity에 가까워진다. 따라서 실험은 `완전 동기 vs 약한 drift vs 독립 offset`을 하나의 noise level로 뭉치지 말고, 다음을 분리해야 한다.

- 고정된 link별 phase offset
- 시간에 따라 변하는 phase drift
- link별 delay offset
- packet timestamp misalignment
- amplitude/AGC 변화

이들을 하나의 “phase noise”로 합치면 어떤 보정이 필요한지 알 수 없다. 특히 delay offset은 bandwidth 효과와, phase drift는 긴 aperture/다중 링크 fusion 효과와 상호작용할 가능성이 크다 `[가설]`.

### 3. bandwidth의 효과는 task와 관측 모델에 조건부다

이상적인 delay-resolution 직관에서는 bandwidth $B$가 커질수록 대략적인 delay 분해능이 $c_0/(2B)$로 좋아진다. 그러나 Wi-Fi CSI에서 이것이 곧 voxel/물체 해상도 향상을 뜻하지는 않는다.

- 관측한 subcarrier의 유효 주파수 범위·개수와 phase calibration이 충분해야 한다.
- 다중경로를 분리할 SNR과 모델이 필요하다.
- 위치 측정에는 baseline/aperture·시야·경로 diversity가 더 지배적일 수 있다.
- room size 자체가 아니라 벽·가구·가림이 만든 path geometry가 효과를 바꾼다.

그러므로 “큰 방에는 넓은 bandwidth가 최적”은 아직 주장할 수 없다. 검증 가능한 가설은 더 약하다: **고정된 task와 solver에서 room/path 조건에 따라 bandwidth의 한계효용 곡선이 달라지는가?**

## 식별가능성·누수 점검

### reconstruction task를 섞으면 안 된다

| task | 최소 정답 | 첫 단계에서 가능한 주장 | 현재 위험 |
|---|---|---|---|
| 단일 이동 표적 localization | 2D/3D 위치 | configuration이 위치 오차에 미치는 영향 | 가장 먼저 시작 가능 |
| coarse occupancy | voxel/영역 점유 | 큰 물체의 대략적 위치·크기 | material/scene prior 의존 증가 |
| 가구/벽 구조 reconstruction | 정적 geometry·재질 | 별도 calibration 조건에서의 구조 추정 | static CSI가 hardware offset·배경과 섞여 식별 불가 가능성이 큼 |

첫 PoC는 빈 방 baseline을 뺀 단일 이동 표적 localization으로 한정한다. 정적 벽·가구 reconstruction을 같은 지표에 넣으면, simulator가 제공하는 정확한 room mesh/material이 inverse solver의 prior로 새어 들어갈 수 있다.

### 절대 금지할 정보 누수

- solver나 Agent prompt에 정답 target position, 정답 room mesh, true material parameter를 제공하지 않는다.
- reconstruction은 test scene의 정답 geometry가 아니라, 실제 배치에서 알 수 있는 Tx/Rx pose와 사전 정의된 관측 모델만 쓴다.
- 동일한 scene seed를 train/parameter-tuning/test에 재사용하지 않는다.
- bandwidth·배치별로 solver hyperparameter를 따로 최적화하지 않는다. 그러면 configuration 효과와 solver tuning 효과가 섞인다.
- Agent가 결과를 읽고 조건표를 조용히 바꾸게 하지 않는다. 새 가설은 새 manifest와 새 run으로 분리한다.

## Agent의 권한을 좁힌 실행 구조

```text
사람이 고정한 experiment manifest + simulator/inverse solver
        │                         │
        │                     self-hosted executor
        ▼                         │
Agents API session ── 제한된 run/status/fetch 도구 ──► 결과 artifact
        │
        └── manifest 검증 · 누락 run 재시도 · 표/plot 초안 · 실패 로그 요약
```

### 왜 기본 선택은 self-hosted인가

OpenAI-hosted sandbox는 Python/Node/CLI와 입력 파일을 제공하므로 작은 synthetic dataset의 집계·plot에는 편하다. 다만 WaveVerse의 GPU/driver/의존성 요구는 이 문서에서 확인하지 않았고, OpenAI-hosted 환경의 GPU 가용성도 공식 문서가 보장하지 않는다 `[확인 필요]`. 실제 simulator와 ESP32 로그에 연결하려면 private network/custom software가 필요한 가능성이 높으므로, 본 실행은 `self_hosted` executor를 기본 후보로 둔다.

OpenAI Docs는 self-hosted 환경에서 사용자가 compute provisioning, connection, reconnection, shutdown, 파일 보존을 관리한다고 명시한다. 반대로 OpenAI-hosted sandbox는 session별 workspace이고 유휴 상태 뒤 삭제될 수 있으며, 산출물은 artifact로 회수해야 한다. [Architecture](https://developers.openai.com/api/docs/guides/agents-api/architecture), [OpenAI-hosted sandboxes](https://developers.openai.com/api/docs/guides/agents-api/environments/openai-hosted)

### Agent에 허용할 도구 [제안]

| 도구 | 입력 | 출력 | 권한 |
|---|---|---|---|
| `validate_manifest` | YAML/JSON manifest | schema error, 예상 run 수 | 읽기 전용 |
| `run_condition` | 불변 condition ID | run ID, status, artifact path | allowlist된 실행 명령만 |
| `get_run_status` | run ID | queued/running/succeeded/failed | 읽기 전용 |
| `fetch_metrics` | run ID | 미리 정의한 JSON metrics | 읽기 전용 |
| `render_report` | metrics table | plot/Markdown artifact | 출력 폴더만 쓰기 |

금지할 권한은 임의 shell, git, credential 조회, simulator source 수정, manifest overwrite, 외부 웹 탐색이다. 실제로 agent-generated code는 환경에 있는 파일·credential·network에 접근할 수 있으므로, API key와 제3자 credential을 agent 환경에 넣지 말아야 한다. network는 기본 `disabled`, 필요한 경우에만 정확한 allowlist를 적용한다. [Sandbox security](https://developers.openai.com/api/docs/guides/agents-api/environments/security)

## 실험 manifest: Agent보다 먼저 고정할 산출물

```yaml
study_id: rf-config-factorial-v0
task: differential_single_target_localization
forward_model_version: <immutable git SHA or release>
inverse_solver_version: <immutable git SHA or release>
seeds: [101, 102, 103, 104, 105]
factors:
  room_layout: [square_small, square_large, corridor]
  clutter: [empty, furnished]
  bandwidth_mhz: [20, 40, 80]
  rx_geometry: [line, perimeter, clustered]
  rx_count: [2, 4, 6]
  phase_model: [ideal, fixed_offset, drift, delay_offset]
fixed:
  tx_power: <value>
  carrier_frequency: <value>
  target_material: <value>
metrics: [position_error_m, failure_rate, ghost_rate, uncertainty_coverage]
split:
  tuning_scenes: <IDs>
  heldout_scenes: <IDs>
```

위 값은 예시이며 아직 실제 parameter가 아니다. 중요한 것은 모든 run이 `(study_id, condition_id, seed, forward_model_version, inverse_solver_version)`로 재현된다는 점이다. `room_layout`, `clutter`, `bandwidth`, `geometry`, `phase_model`을 동시에 무작정 전수하면 조합 수가 폭발하므로, 처음에는 fractional factorial 또는 사전 정의한 2수준 screening으로 주효과를 보고, 이후 유의한 interaction만 확장한다 `[방법 제안]`.

## 무엇을 고정하고 무엇을 바꿀 것인가

1. **forward model 고정, solver 고정**: configuration 요인의 순수 효과를 먼저 본다.
2. **solver만 교체**: 같은 CSI에서 solver 민감도를 따로 측정한다. 이 결과를 configuration 효과 표와 합치지 않는다.
3. **hardware error model만 주입**: ideal→offset→drift→delay의 성능 붕괴 곡선을 기록한다.
4. **simulator와 실측을 같은 condition ID로 연결**: 실측에는 대응하는 error class를 추정해 붙이되, 억지로 일치시키지 않는다.

이 분리가 없으면 “배치가 중요하다”라는 결론이 사실은 특정 inverse solver가 해당 배치에 유리했다는 결론일 수 있다.

## 최소 PoC와 평가 기준

### Phase 0 — Agent 없이 과학 루프를 먼저 검증

- 방 하나, 단일 표적, 두 Rx geometry, 두 bandwidth, ideal/fixed-offset의 작은 $2\times2\times2$ 조건을 손으로 실행한다.
- 동일 seed 재실행 시 CSI와 metrics가 허용 오차 안에서 재현되는지 확인한다.
- GT 비노출 evaluator가 position error를 계산하도록 분리한다.

이 단계가 실패하면 Agent를 붙여도 실패를 더 빨리 반복할 뿐이다.

### Phase 1 — Agent는 수동 실행을 그대로 재현

- Agent가 manifest를 읽고 누락 없는 run 목록을 만든다.
- 각 run은 narrow function tool 하나로만 실행한다.
- 사람이 만든 기준 결과와 Agent workflow의 condition 수, 실패 분류, metric JSON hash가 같은지 비교한다.

### Phase 2 — 집계·감사 자동화

- Agent가 효과 크기, confidence interval, 결측 run, 재시도 횟수를 표로 만든다.
- 결론 문장은 사람이 승인한다. Agent는 “가설 지지/반증” 대신 수치와 누락만 보고한다.

### 통과 기준 [제안]

- 동일 manifest 재실행에서 condition 누락 0건
- 실제 실행에 사용한 version·seed·입력 hash 기록률 100%
- Agent workflow와 수동 기준의 metric 값 일치(사전 정의한 tolerance 이내)
- 실패 run이 성공으로 잘못 집계된 건 0건
- held-out scene에서 simulator의 요인 순서가 유지되는지 보고. 유지되지 않으면 configuration claim을 보류

## 반증 조건

- phase/delay error의 현실적 범위를 넣자마자 bandwidth·Rx geometry 효과가 모든 조건에서 사라진다. 이때 주제는 configuration selection이 아니라 synchronization/calibration 한계 분석으로 좁혀야 한다.
- forward model 또는 inverse solver version을 조금 바꾸면 요인 순위가 뒤집힌다. 이때 “환경별 최적 configuration” 주장은 아직 불안정하다.
- simulator에서만 효과가 있고, 대응한 ESP32 측정에서 방향조차 재현되지 않는다. simulator gap을 모델링하기 전에는 자동 선택기를 학습시키면 안 된다.
- Agent를 붙인 뒤에도 누락·잘못된 재시도·재현 불가 run이 줄지 않는다. 이 경우 Agents API는 연구 도구로서의 이득이 없다.

## 현재 결론

**조건부 타당.** Agent를 실험 runner·기록자로 제한하면, 영향도 분석의 운영 부담과 누락을 줄일 가능성은 있다. 하지만 이 연구의 차별성이나 물리적 타당성은 Agent 사용에서 나오지 않는다. 차별성은 저가·비동기 distributed Wi-Fi CSI에서 environment, bandwidth, geometry, synchronization의 **상대 효과와 상호작용을 누수 없이 측정**하는 데 있다.

다음 행동은 Agents API 구현이 아니라 Phase 0의 작은 deterministic forward/inverse benchmark를 정의하는 것이다. 그 결과가 재현될 때에만 self-hosted executor를 연결한다.
