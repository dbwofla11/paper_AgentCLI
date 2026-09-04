# 사고실험: LatentCSI를 크로스 도메인 환경에 적용하기

- 작성일: 2026-09-04
- 상태: 가설 단계
- 출발 논문: `Real-Time Reconstruction of Physical Scenes from WiFi CSI via Latent Diffusion` / `LatentCSI`
- 관련 리뷰: [LatentCSI 심층 리뷰](../../reviews/wifi-csi/2025-ramesh-latentcsi-wifi-csi-latent-diffusion.md)

## 1. 출발점

LatentCSI는 CSI를 Stable Diffusion의 latent 표현으로 바꾼 뒤 이미지를 생성한다. 학습과 평가가 제한된 실내 환경·사람·동작 범위 안에서 이루어졌고, 다른 방·장치·AP 배치로 옮겼을 때의 성능은 검증하지 않았다 (§II-A, §III-A–B, pp.2, 4–5).

따라서 다음 문제가 예상된다.

```text
새 환경의 CSI
    ↓
학습 환경과 달라진 CSI 분포
    ↓
CSI encoder가 잘못된 latent 생성
    ↓
Diffusion이 부족한 부분을 그럴듯하게 상상
    ↓
사진처럼 보이지만 실제와 다른 결과
```

## 2. 핵심 가설

처음부터 CSI를 RGB 이미지 전체로 변환하지 않고, 먼저 환경이 바뀌어도 비교적 유지되는 물리적·구조적 특징을 추출한다. 그 뒤 diffusion model은 CSI가 확실히 관측하지 못한 시각적 세부만 생성한다.

```text
CSI sequence
    ├─ domain-invariant encoder
    │    └─ 사람 위치·자세·움직임·상대 거리·occupancy
    ├─ domain encoder
    │    └─ 방·장치·AP 배치의 특성
    └─ uncertainty/confidence map
             ↓
      structure-conditioned diffusion
             ↓
          RGB image
```

핵심은 **관측된 정보와 생성된 정보를 분리하는 것**이다. diffusion이 관측된 구조까지 덮어쓰면 크로스 도메인 문제를 해결한 것이 아니라 더 자연스러운 hallucination을 만든 것에 그친다 `[가설]`.

## 3. 무엇을 ‘근본적인 특징’으로 볼 것인가

다음 특징들은 후보이지, 현재 환경에서 자동으로 불변이라고 보장된 것은 아니다.

- **시간 변화·Doppler**: 사람이 움직이는 방향과 속도
- **안테나 간 상대 위상·진폭**: 신호가 오는 상대 방향
- **주파수별 delay/multipath 패턴**: 상대적인 거리·공간 구조
- **시간 차분 및 정규화 특징**: 장치별 절대 amplitude 차이 완화
- **CSI sequence의 변화 패턴**: 정적인 방 정보보다 사람의 동작에 집중

주의할 점은 CSI 자체가 방 구조, 벽, 가구, AP 위치의 영향을 강하게 받는다는 것이다. 따라서 완전히 환경 불변인 feature가 존재한다고 가정하면 안 된다 `[확인 필요]`.

## 4. 제안하는 모델 구조

### 4.1 구조 표현과 도메인 표현 분리

- `z_inv`: 사람 위치, pose, 움직임 등 여러 환경에서 공유되어야 하는 표현
- `z_dom`: 방 구조, 장치 특성, AP 위치 등 환경에 종속된 표현
- `c`: CSI가 각 구조 요소를 얼마나 확실하게 관측했는지 나타내는 confidence

생성기는 `z_inv`를 반드시 보존하고, `z_dom`과 diffusion prior는 배경·질감·스타일 같은 도메인 특성을 보충하는 데 사용한다.

### 4.2 추천되는 2단계 출력

```text
CSI → pose / occupancy / coarse depth / layout
    → 구조 조건부 diffusion → 자연스러운 RGB image
```

처음부터 RGB를 맞히는 것보다 pose·occupancy 같은 구조적 목표를 먼저 맞히는 편이 크로스 도메인 성능을 측정하기 쉽다 `[내 의견]`. 실제 sensing 목적이 사람 위치·자세라면 RGB 복원 자체를 최종 목표로 삼지 않아도 된다.

## 5. 새 환경에 적응하는 방법

### A. 짧은 paired calibration

LatentCSI도 카메라를 학습 단계에서만 사용할 수 있다고 설명한다 (§II-A, pp.2–3). 이 설정을 활용해 새 방에 들어갔을 때 짧은 시간 동안 CSI와 카메라를 함께 수집하고, 전체 모델이 아니라 작은 adapter 또는 `z_dom` 부분만 보정한다.

- 장점: 가장 현실적이고 안정적이다.
- 단점: 새 환경마다 초기 calibration 장비가 필요하다.

### B. 카메라 없는 self-supervised adaptation

새 환경에서 CSI의 temporal consistency, cycle consistency, known anchor의 위치 등을 이용해 encoder를 조금씩 적응시킨다.

- 장점: 배포 때 카메라가 없어도 된다.
- 단점: 잘못된 pseudo-label이 누적되면 model drift가 생길 수 있다.

### C. 다중 도메인 사전학습

여러 방·장치·AP 배치에서 학습하면서 같은 pose/action을 가진 CSI 표현이 서로 가까워지도록 contrastive loss 또는 domain-adversarial loss를 사용한다.

```text
L = L_structure
  + λ1 L_domain_invariance
  + λ2 L_latent_alignment
  + λ3 L_reconstruction
  + λ4 L_uncertainty
```

이 식은 구현된 방법이 아니라 설계 초안이다 `[가설]`.

## 6. diffusion이 맡아야 할 역할

diffusion은 다음을 생성해도 된다.

- 얼굴의 세부 묘사
- 옷의 질감과 색상
- 배경의 자연스러운 texture
- 센서가 직접 측정하기 어려운 고주파 시각 정보

반대로 다음은 diffusion이 마음대로 바꾸지 못하게 해야 한다.

- 사람의 위치
- 사람의 수
- pose와 움직임 방향
- 관측된 거리·공간 관계

이를 위해 구조 feature에 강한 conditioning을 걸고, confidence가 높은 영역에는 reconstruction/geometry loss를 적용하며, confidence가 낮은 영역에만 생성 자유도를 주는 방식이 필요하다 `[가설]`.

## 7. 반드시 필요한 평가

| 학습 도메인 | 테스트 도메인 | 확인할 것 |
|---|---|---|
| 방 A | 방 B | cross-room generalization |
| 장치 1 | 장치 2 | device shift |
| AP 위치 1 | AP 위치 2 | geometry/setup shift |
| 사람 1·2 | 사람 3·4 | subject generalization |
| 깨끗한 CSI | noise·packet loss CSI | signal robustness |

평가는 RGB 이미지 지표만으로 충분하지 않다.

- pose error
- 사람 위치·occupancy accuracy
- depth 또는 상대 거리 오차
- FID/SSIM/RMSE
- 관측 영역과 hallucinated 영역의 구분 정확도
- confidence calibration
- free-running temporal consistency

특히 FID가 좋아도 실제 사람 위치가 틀릴 수 있으므로, LatentCSI Dataset 2에서 보인 “FID는 좋지만 RMSE·SSIM은 baseline보다 나쁜” 현상을 반드시 경계해야 한다 (Table III, p.6) `[내 판단]`.

## 8. 가장 큰 이론적 한계

CSI가 새 환경의 세부 정보를 실제로 포함하지 않는다면, diffusion은 그 정보를 복원할 수 없다. 가능한 것은 학습 데이터의 prior를 이용해 가장 그럴듯한 장면을 추정하는 것뿐이다.

따라서 이 연구의 목표는 다음처럼 표현하는 것이 정직하다.

> **정확한 물리 장면 복원**이 아니라, 관측 가능한 구조는 보존하면서 관측 불가능한 시각 세부를 불확실성과 함께 생성하는 것.

절대적인 방 배치나 숨겨진 물체까지 정확히 복원할 수 있다고 주장하면 identifiability 문제가 생긴다 `[내 판단]`.

## 9. 우선순위가 높은 후속 실험

1. 같은 backbone에서 `shifted/unshifted`와 방 분할 방식을 비교한다.
2. 방·사람·장치 기준으로 완전히 분리한 leave-one-domain-out 실험을 한다.
3. CSI → pose/occupancy만 먼저 학습해 구조 표현의 cross-domain 성능을 측정한다.
4. 새 방에서 1분·5분·10분 paired calibration에 따른 성능 변화를 측정한다.
5. 구조 표현은 고정하고 diffusion 세부 생성만 켰을 때 hallucination이 얼마나 늘어나는지 본다.
6. RGB 품질보다 pose·거리·occupancy 정확도와 confidence를 함께 평가한다.

## 10. 현재 결론

이 아이디어는 충분히 연구 가능한 방향이다. 가장 설득력 있는 버전은 `domain-invariant structured representation + short calibration + structure-conditioned diffusion`이다.

단순히 “기본 특징을 뽑고 나머지를 diffusion으로 채우자”로 끝내면 새 환경에서 틀린 구조까지 자연스럽게 꾸밀 위험이 있다. 따라서 다음 원칙을 지켜야 한다.

1. CSI가 실제로 관측한 구조와 diffusion이 추정한 세부를 분리한다.
2. 새 환경에서 구조 feature가 유지되는지 별도 측정한다.
3. diffusion 출력에 confidence와 uncertainty를 함께 제공한다.
4. cross-domain 평가 없이 일반화를 주장하지 않는다.
