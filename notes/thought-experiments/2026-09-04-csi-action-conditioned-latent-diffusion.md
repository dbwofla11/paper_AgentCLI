# 사고실험: CSI 행동 조건부 latent diffusion으로 pose를 보정하기

- 작성일: 2026-09-04
- 상태: 가설 단계
- 출발 메모: [LatentCSI 크로스 도메인 사고실험](./2026-09-04-latentcsi-cross-domain.md)
- 관련 연구: [WiFi-JEPA](https://arxiv.org/abs/2607.11064), [Person-in-WiFi 3D](https://openaccess.thecvf.com/content/CVPR2024/papers/Yan_Person-in-WiFi_3D_End-to-End_Multi-Person_3D_Pose_Estimation_with_Wi-Fi_CVPR_2024_paper.pdf), [MotionBERT](https://arxiv.org/abs/2210.06551)

## 1. 핵심 질문

CSI에서 완벽한 skeleton을 직접 회귀하려 하면 관절이 평균화되거나 뭉개질 수 있다. 그렇다면 먼저 CSI representation과 행동 의미를 추정하고, 그 결과를 조건으로 latent diffusion이 temporal·kinematic하게 일관된 skeleton을 생성하도록 만들 수 있는가?

최종 목표가 정확한 관절 좌표 자체가 아니라 행동 인식·시각화·avatar 제어라면, 모든 관절의 물리적 위치를 완벽하게 복원할 필요가 없을 수 있다 `[가설]`.

## 2. 제안 파이프라인

```text
CSI sequence
    ↓
WiFi-JEPA encoder
    ↓
coarse pose sequence + joint confidence + CSI embedding
    ↓
action posterior p(y | CSI)
    ↓
pose/motion latent encoder
    ↓
action-conditioned residual diffusion
    ↓
refined skeleton sequence
    ↓
action recognition / visualization / avatar control
```

프레임별 결과를 출력하더라도 diffusion은 각 프레임을 독립적으로 처리하지 않는다. 주변 시간 구간의 CSI, coarse pose, velocity와 action posterior를 함께 조건으로 사용한다.

\[
p(S_{1:T}\mid C_{1:T}, z_{\mathrm{JEPA}}, p(y\mid C), G)
\]

여기서 $C$는 CSI, $z_{\mathrm{JEPA}}$는 CSI representation, $G$는 skeleton graph·신체 구조·장치 geometry다.

## 3. diffusion이 생성할 것

전체 skeleton을 pure noise에서 재생성하기보다 JEPA pose에 대한 correction을 생성한다.

\[
\hat S_t = S^{\mathrm{coarse}}_t + \Delta S^{\mathrm{diff}}_t
\]

- confidence가 높은 관절: coarse pose를 강하게 보존한다.
- confidence가 낮은 관절: diffusion이 주변 관절·시간 문맥·행동 prior를 이용해 보정한다.
- 빠른 움직임: 위치만 평활화하지 말고 velocity/acceleration을 함께 조건화한다.
- action label: 가능한 motion manifold를 좁히는 prior로 사용한다.

행동 label만 diffusion에 넣으면 실제 instance pose가 아니라 canonical motion이 생성될 수 있다. 따라서 실제 동작의 세부를 유지하려면 action posterior만으로 충분하지 않고 CSI embedding 또는 coarse pose를 함께 넣어야 한다 `[내 판단]`.

## 4. 타당성을 지지하는 근거

1. [WiFi-JEPA](https://arxiv.org/abs/2607.11064)는 raw CSI 재구성 대신 masked latent embedding prediction으로 CSI-native representation을 학습하고 downstream 3D pose estimation에 사용한다. 따라서 첫 단계의 CSI representation encoder로 자연스럽다.
2. [Person-in-WiFi 3D](https://openaccess.thecvf.com/content/CVPR2024/papers/Yan_Person-in-WiFi_3D_End-to-End_Multi-Person_3D_Pose_Estimation_with_Wi-Fi_CVPR_2024_paper.pdf)는 초기 pose 뒤에 `Refine Decoder`를 두고 관절 offset을 반복 예측한다. coarse pose→refinement라는 구조 자체는 이미 타당한 설계 전례가 있다.
3. [MotionBERT](https://arxiv.org/abs/2210.06551)는 noisy·partial skeleton에서 정상적인 3D motion을 복원하도록 사전학습된다. skeleton/motion prior를 별도 모델로 학습할 수 있다는 근거가 된다.
4. 조건부 diffusion을 pose sequence denoising에 사용하는 연구도 초기 pose prediction을 조건으로 temporal inconsistency를 보정한다. 다만 이번에 확인한 사례는 WiFi CSI가 아닌 영상 기반 pose이며, CSI 특유의 오류 분포는 별도로 학습해야 한다 `[확인 필요]`.

## 5. 취약한 전제

### 5.1 CSI가 결정하지 못하는 정보

CSI는 환경·multipath·장치 배치의 영향을 받으며, 하나의 CSI가 하나의 pose를 유일하게 결정한다고 보장하기 어렵다. diffusion이 관측되지 않은 세부를 복원하는 것이 아니라 training prior로 plausible pose를 hallucinate할 위험이 있다 `[내 판단]`.

### 5.2 행동 label의 정보량

`sit down`이나 `walk`는 동작 의미는 제한하지만 방향, 속도, limb 선택, phase, 사람 위치를 결정하지 않는다. 따라서 label-conditioned generation은 실제 pose reconstruction보다는 행동 일관성 있는 motion generation에 가깝다.

### 5.3 label error propagation

CSI로 예측한 action label이 틀리면 diffusion이 잘못된 motion manifold에 갇힐 수 있다. hard argmax label보다 action posterior를 조건으로 사용하고, label을 제거한 ablation과 비교해야 한다.

### 5.4 독립 프레임 생성

각 프레임을 독립적으로 latent diffusion하면 spatial pose는 좋아져도 frame-to-frame jitter가 생긴다. temporal window, overlapping-window consistency, velocity·acceleration loss가 필요하다.

### 5.5 과설계 가능성

목표가 행동 분류뿐이면 diffusion skeleton 생성은 필요하지 않을 수 있다. 먼저 `CSI→action` 성능을 고정하고, diffusion이 분류·설명·시각화에 추가 가치를 주는지 확인해야 한다.

## 6. 권장 학습 목적

```text
L = L_diffusion
  + λ1 L_joint
  + λ2 L_bone
  + λ3 L_temporal
  + λ4 L_action
  + λ5 L_CSI-consistency
```

- `L_diffusion`: coarse pose 조건부 residual denoising
- `L_joint`: ground-truth joint 좌표와의 오차
- `L_bone`: bone length와 skeleton graph 제약
- `L_temporal`: velocity·acceleration·jerk 일관성
- `L_action`: refined pose가 예측 action과 일치하는지 평가
- `L_CSI-consistency`: refined pose가 CSI observation과 모순되지 않는지 평가

`L_CSI-consistency`는 differentiable wireless forward model 또는 CSI feature consistency로 구현할 수 있지만, 구체적 forward model은 데이터·장치 설정을 확인하기 전에는 미정이다 `[확인 필요]`.

## 7. 반드시 필요한 비교 실험

| 모델 | 목적 |
|---|---|
| JEPA pose head | coarse pose 기준선 |
| JEPA + EMA/Kalman/Savitzky–Golay | 단순 smoothing 기준선 |
| JEPA + deterministic Transformer/GRU refiner | diffusion 필요성 검증 |
| JEPA + unconditional diffusion | action/CSI 조건의 효과 검증 |
| JEPA + action-conditioned diffusion | 제안 모델 |
| JEPA + action posterior + CSI consistency diffusion | 최종 모델 |

평가 지표는 MPJPE만으로 부족하다.

- MPJPE / PCK
- velocity error, acceleration error, jerk
- bone-length violation
- action recognition accuracy와 action consistency
- CSI consistency
- cross-subject / cross-room / cross-device / cross-layout 성능
- uncertainty calibration

## 8. 반증 조건

다음 중 하나가 나타나면 현재 가설을 약화하거나 수정해야 한다.

1. diffusion이 deterministic refiner보다 MPJPE·temporal error를 개선하지 못한다.
2. action label을 넣었을 때 in-domain 성능만 오르고 unseen action·cross-room 성능이 하락한다.
3. refined pose의 action consistency는 높지만 CSI consistency가 낮다.
4. 관측된 coarse pose보다 diffusion 결과가 ground truth에서 멀어지는 관절이 많다.
5. 독립 frame 생성이 temporal window 모델보다 유의미하게 빠르지 않으면서 flicker를 만든다.

## 9. 현재 결론

**조건부 타당하다.** `WiFi-JEPA → action posterior → action-conditioned latent diffusion`은 CSI pose의 평균화·jitter·일부 관절 누락을 보정할 수 있는 합리적인 연구 가설이다.

다만 diffusion은 물리적으로 관측되지 않은 정보를 보장해서 복원하지 않는다. 따라서 논문의 주장은 “정확한 skeleton 복원”보다 다음처럼 제한하는 편이 타당하다.

> CSI가 제공한 coarse motion structure를 보존하면서, 행동 prior와 temporal·kinematic constraints를 사용해 안정적인 skeleton sequence를 생성한다.

가장 먼저 해야 할 실험은 diffusion이 실제로 필요한지 확인하는 것이다. `WiFi-JEPA + deterministic temporal refiner`와 비교해 diffusion이 다중 가설·불확실성·cross-domain robustness에서 추가 이점을 주는지부터 검증해야 한다.
