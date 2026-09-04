---
title: "Real-Time Reconstruction of Physical Scenes from WiFi CSI via Latent Diffusion"
authors: ["Ramesh, Eshan", "Nishio, Takayuki"]
venue: "ACM MobiCom 2025 Demo"
year: 2025
arxiv: "2506.10605"
doi: "10.1145/3680207.3765601"
code: "없음 — 논문에 공개 코드 링크 미기재"
pdf: "papers/2026-09-04/ramesh-latentcsi-wifi-csi-latent-diffusion.pdf"
read_date: 2026-09-04
rating: 4
tags: [WiFi CSI, latent diffusion, image generation, wireless sensing, privacy]
status: 완료
---

# Real-Time Reconstruction of Physical Scenes from WiFi CSI via Latent Diffusion

> **TL;DR** — 이 논문은 카메라 이미지 대신 WiFi CSI를 입력으로 받아, Stable Diffusion이 사용하는 저차원 latent 공간을 먼저 예측한 뒤 이미지를 복원하는 `LatentCSI`를 제안한다. 기존 픽셀 직접 생성 방식보다 FID와 학습 시간이 좋아졌지만, pixel 정확도는 일부 데이터셋에서 baseline이 더 좋고, 데이터 분할·test loss 선택·제한된 실내 데이터 때문에 “일반적인 환경을 잘 복원한다”까지는 증명하지 못했다.

> **버전 주의** — 공식 학회 기록은 `Real-Time Reconstruction of Physical Scenes from WiFi CSI via Latent Diffusion`이라는 ACM MobiCom ’25 Demo 논문이다. 이 리뷰에서 방법·실험의 세부 내용은 저장된 6쪽 arXiv 기술 원고 `High-resolution efficient image generation from WiFi CSI using a pretrained latent diffusion model`을 기준으로 읽었다. 두 버전은 제목과 분량이 다르다. [ACM 공식 기록](https://doi.org/10.1145/3680207.3765601)과 [arXiv 원고](https://arxiv.org/abs/2506.10605)를 함께 확인했다.

## 1. 문제와 동기

- **풀려는 문제**: WiFi 신호의 channel state information(CSI)만으로 실내 환경의 고해상도 RGB 이미지를 생성하는 문제다. 카메라는 학습 때 CSI–이미지 쌍을 만드는 데만 사용하고, 실제 배포 때는 CSI만 사용한다 (§II-A, pp.1–2).
- **기존 방식의 무엇이 부족한가**: 기존 CSI-to-image 연구는 GAN 또는 이미지 전체를 직접 예측하는 end-to-end 모델을 주로 사용한다. 저자는 이런 방식이 고해상도 픽셀 분포를 학습하기 어렵고, 학습 과정이 복잡하며, 이미지의 세밀한 개인정보를 그대로 재현할 위험이 있다고 주장한다 (§I, pp.1–2).
- **그 진단에 동의하는가** `[내 의견]`: latent 공간에서 생성하면 계산량을 줄일 수 있다는 진단은 타당하다. 그러나 latent bottleneck이 실제로 개인정보 위험을 줄인다는 주장은 별도의 재식별 실험이 없으면 설계상 기대에 머문다.

## 2. 핵심 기여

| # | 저자 주장 기여 | 위치 | 실제로 새로운가 `[내 판단]` |
|---|---|---|---|
| 1 | CSI를 Stable Diffusion의 이미지 encoder 대신 넣어 latent diffusion 기반 CSI-to-image 파이프라인을 구성한다. | §I–II, pp.1–3 | 기존 CSI-to-image에 pretrained latent diffusion을 결합한 설계가 핵심이다. 새 구성의 실용적 가치는 있지만, latent diffusion 자체와 image-to-image 파이프라인은 기존 기술이다. |
| 2 | CSI encoder만 학습하는 단순한 구조로 고해상도 생성과 낮은 학습 비용을 달성한다. | §II-C–D, §III, pp.3–5 | Table III가 FID·시간 개선을 보여주지만, 모델 파라미터 수는 baseline보다 오히려 많다. “더 작은 모델”보다는 “픽셀 출력보다 효율적인 출력 공간”이라는 표현이 정확하다 `[내 판단]`. |
| 3 | 같은 CSI 입력에 text prompt를 추가해 생성 이미지의 스타일·의미를 바꿀 수 있다. | §III-C, Table IV, pp.5–6 | 기능 자체는 Stable Diffusion에서 자연스럽게 따라오지만 CSI latent에 적용한 데 의미가 있다. 다만 정량적인 controllability 평가는 없다 `[내 판단]`. |

## 3. 방법 (Method)

### 3.1 한 문단 개요

학습 입력은 복소수 CSI 측정값이고, 학습 목표는 동시에 촬영한 RGB 이미지의 Stable Diffusion v1.5 VAE latent다. 먼저 CSI encoder가 CSI를 `4×64×64` latent로 바꾼다. 그 latent에 필요하면 Gaussian noise를 넣고 text conditioning을 사용한 Stable Diffusion denoising을 수행한 다음, pretrained VAE decoder로 `512×512` 이미지를 복원한다. 핵심은 거대한 diffusion model을 다시 학습하지 않고 CSI encoder만 학습한다는 점이다 (§II-B–D, pp.2–4).

### 3.2 표기와 정의

| 기호 | 의미 | 형태/차원 |
|---|---|---|
| $x_c$ | 복소수 CSI 측정값 | $\mathbb{C}^{s}$ |
| $x$ | CSI encoder 입력. 본문은 $\operatorname{Re}(x_c)^2+\operatorname{Im}(x_c)^2$로 계산한다고 적고 이를 amplitude 정보라고 부른다. | $s$차원 `[확인 필요]` |
| $y$ | CSI와 동시 취득한 RGB 이미지 | 전처리 후 $512×512$ |
| $q_\Phi(z\mid y)$ | pretrained VAE encoder가 이미지에서 만든 latent posterior | 평균·대각 공분산, $\mu_\Phi(y),\sigma_\Phi^2(y)\in\mathbb{R}^{4×64×64}$ |
| $\hat z=f_w(x)$ | CSI encoder가 예측한 이미지 latent 평균 | $4×64×64$ |
| $n$ | inference 때 latent에 추가하는 Gaussian noise | $n\sim\mathcal{N}(0,\sigma^2)$ |

### 3.3 상세

- **표준 latent diffusion 경로**: 일반적인 Stable Diffusion image-to-image는 $y$를 VAE encoder로 latent $z$에 매핑하고, $z+n$을 text-conditioned U-Net으로 반복 denoising한 뒤 VAE decoder로 이미지를 만든다 (§II-B.1, pp.2–3).

- **LatentCSI inference**: LatentCSI는 이미지 VAE encoder를 CSI encoder로 바꾼다. 따라서 배포 시의 경로는 다음과 같다.

  $$x \xrightarrow{f_w} \hat z \xrightarrow{+n,\;\text{text-conditioned LDM}} \tilde z \xrightarrow{\text{VAE decoder}} \hat y$$

  여기서 `strength`가 클수록 더 많은 noise를 넣고 원래 CSI latent에서 더 멀리 변형한다. strength가 낮으면 CSI encoder가 만든 이미지 구조를 더 많이 유지한다 (§II-B.1–2, pp.2–3).

- **학습 목표**: Stable Diffusion VAE의 posterior를 Gaussian으로 정의하지만, v1.5에서 variance가 매우 작다고 보고 sampling 대신 mean을 사용한다. 그래서 CSI encoder를 deterministic network로 바꾸고 다음 평균제곱오차를 최소화한다 (§II-B.2–C, p.3).

  $$\min_w\;\mathbb{E}_{(x,y)\sim D}\left[\left\|f_w(x)-\mu_\Phi(y)\right\|_2^2\right]$$

  **직관**: CSI를 보고 “이 이미지가 Stable Diffusion latent 공간에서 어느 위치에 있어야 하는가”를 맞추는 회귀 문제다. CSI encoder가 픽셀 3채널 전체를 직접 맞추는 대신, pretrained VAE가 이미 압축해 둔 표현을 맞춘다.

- **CSI 전처리**: 위상(phase)은 사용하지 않고 CSI의 실수부·허수부에서 계산한 amplitude 정보만 사용한다. 저자는 unsynchronized device에서 phase를 다루는 복잡성을 피하고, 선행연구가 amplitude만으로도 여러 sensing task를 수행했다는 점을 이유로 든다 (§II-C, p.3).

- **CSI encoder 구조**: 입력 $s$차원 CSI를 fully connected layer로 벡터화하고 $b$개 channel tensor로 reshape한다. 이후 4개 upsampling 단계에서 channel 수를 절반으로 줄이고 공간 해상도를 2배씩 늘린다. 각 단계는 residual block 2개와 transposed convolution으로 구성된다. 마지막 3개 upsampling 단계에는 cross-attention을 넣고, 마지막 convolution으로 `4×64×64` 출력을 만든다 (§II-D, Fig. 4, p.4).

- **학습 절차**: Stable Diffusion의 VAE encoder·denoising model·decoder는 고정하고 CSI encoder만 ADAM으로 학습한다. validation loss가 5개 연속 epoch 동안 개선되지 않으면 early stopping한다. learning rate는 0.0005이고, stochastic initialization과 학습 변동을 보기 위해 각 모델을 5회 학습했다 (§III, p.4).

- **추론 절차**: 정량 평가에서는 noising strength를 0으로 두어 CSI encoder의 직접 복원 결과를 측정했다. text-guided 예시는 DDIM 100 denoising steps와 strength 0.6을 사용했다 (§III, p.4; §III-C, p.6).

### 3.4 왜 이 방법이 통한다고 저자는 말하는가

- **저자의 설명**: CSI에는 사람의 위치·자세 등 환경 변화와 대응하는 정보가 있고, pretrained LDM은 저차원 latent에서 고품질 이미지의 세부 구조를 생성할 수 있다. 따라서 CSI encoder는 coarse visual structure를 제공하고, LDM이 그 표현을 자연스러운 이미지로 확장한다 (§II-A–B, pp.2–3).
- **그 설명에 대한 판단** `[내 판단]`: FID와 학습 시간 결과는 “latent 출력이 픽셀 직접 출력보다 유리할 수 있다”는 설명을 지지한다. 하지만 latent가 없는 조건, pretrained LDM을 fine-tune한 조건, CSI phase를 추가한 조건이 없어 각 요소의 기여를 분리한 검증은 아니다.

## 4. 실험 설정

| 항목 | 내용 | 위치 |
|---|---|---|
| 데이터셋 | Dataset 1: 한 사람이 작은 실내에서 왕복 보행. 10 Hz, 25분, 15,000 CSI–이미지 쌍, 1,992 subcarriers, 640×480 RGB를 512×512로 crop/resample. Dataset 2: MM-Fi의 environment 3, first two subjects, arm movement activities 13–14·17–18, 23,760 samples, 3 antennas×114 carriers=342 subcarriers. | §III-A–B, pp.4–5 |
| 태스크·지표 | CSI에서 RGB image reconstruction. 전체 이미지와 YOLOv3로 검출한 사람 crop을 평가. FID(낮을수록 좋음), pixel RMSE(낮을수록 좋음), SSIM(높을수록 좋음). | §III, p.4 |
| 베이스라인 | 동일 계열의 pixel-space baseline; CSI2Image의 supervised+adversarial hybrid GAN(K=8). | §III, p.4 |
| 모델 규모 | Dataset 1: LatentCSI 22,914,052, baseline 16,434,395 parameters. Dataset 2: LatentCSI 13,621,252, baseline 11,490,275 parameters. | §III-A–B, pp.4–5 |
| 하이퍼파라미터 | CSI encoder initial channel $b$: Dataset 1·2 모두 256, baseline은 각각 8·32. ADAM learning rate 0.0005, validation stagnation 5 epochs early stopping. text 예시는 DDIM 100 steps, strength 0.6. batch size·epoch 상한·정규화·스케줄러 등은 미기재. | §III, §III-A–C, pp.4–6 |
| 컴퓨트·학습 시간 | NVIDIA H100 1개와 AMD EPYC 9654 CPU 8 cores. Dataset 1 LatentCSI 11.9 sec/epoch, 05:02; Dataset 2 17.9 sec/epoch, 16:24. | §III, Table III, pp.4, 6 |
| 시드·반복 횟수 | 각 모델 5회 학습, 평균±표준편차 보고. 구체적인 random seed는 미기재. | §III, Table III, p.4 |

## 5. 결과 — 주장과 증거의 대응

| 저자 주장 | 근거로 제시된 결과 | 위치 | 그 근거가 주장을 지지하는가 `[내 판단]` |
|---|---|---|---|
| LatentCSI가 pixel baseline보다 perceptual quality가 좋다. | Dataset 1 전체 FID 134.23±7.18 대 268.03±4.23, Dataset 2 전체 FID 28.21±0.78 대 47.67±2.04. | Table III, §III-A–B, p.6 | FID 기준으로는 지지한다. 다만 FID가 실제 장면의 위치·형태 정확도를 직접 측정하지는 않는다. |
| LatentCSI가 pixel baseline보다 image-level accuracy도 좋다. | Dataset 1은 RMSE 18.95 대 20.45, SSIM 0.87 대 0.84로 LatentCSI가 앞선다. 그러나 Dataset 2는 RMSE 7.87 대 7.15, SSIM 0.94 대 0.97로 baseline이 앞선다. | Table III, p.6 | 데이터셋 전체에서 성립하지 않는다. 저자 결론도 latent model이 perceptual quality에서 강하고 end-to-end model이 pixel accuracy에서 나을 수 있음을 인정한다. |
| 계산 효율이 좋다. | Dataset 1 학습 시간 05:02 대 16:29, Dataset 2 16:24 대 91:09. epoch 시간도 각각 11.9 대 36.4초, 17.9 대 59.3초다. | Table III, p.6 | 학습 시간에는 강한 근거가 있다. 다만 inference latency·GPU memory·text-guided denoising 비용은 별도로 충분히 보고하지 않았다. |
| 고해상도 출력을 생성하고 text-guided control을 제공한다. | `512×512` 이미지와 같은 CSI 입력에 서로 다른 text prompt를 적용한 qualitative examples. | §III-A, §III-C, Tables I–IV, pp.4–6 | 기능 시연은 지지하지만, 해상도·prompt 충실도·재현성에 대한 정량 비교는 없다. |
| 기존 CSI2Image보다 낫다. | 두 데이터셋에서 CSI2Image의 FID/RMSE/SSIM이 LatentCSI보다 크게 나쁘다. 예: Dataset 1 FID 392.46±1.10, Dataset 2 FID 312.24±2.15. | Table III, p.6 | 수치상 지지하지만 CSI2Image가 본 실험 해상도에서 underfit했다고 저자도 분석하며, 해당 모델의 재튜닝 여부가 명확하지 않아 강한 우위 주장에는 주의가 필요하다. |

핵심 수치:

- Dataset 1에서 LatentCSI는 baseline보다 FID를 약 50% 낮추고, epoch 시간을 약 3분의 1로 줄였다 (Table III, p.6) `[계산은 표 수치에서 산출]`.
- Dataset 2에서는 FID와 학습 시간은 LatentCSI가 좋지만, RMSE와 SSIM은 baseline이 좋다 (Table III, p.6).
- crop 평가에서도 Dataset 2 LatentCSI의 FID는 27.90±0.43, baseline은 69.34±2.50이지만, RMSE는 7.90±0.03 대 7.19±0.24, SSIM은 0.92±0.00 대 0.93±0.00이다 (Table III, p.6).

## 6. Ablation / 분석

| 제거·변경한 것 | 성능 변화 | 위치 | 해석 |
|---|---|---|---|
| 전체 이미지 vs 사람 crop | 두 데이터셋 모두 crop FID와 pixel 지표를 별도로 보고한다. Dataset 2에서 FID 우위는 crop에서도 유지된다. | §III, Table III, p.6 | 사람처럼 의미 있는 영역에서 perceptual advantage가 유지되는지 확인한다. 다만 crop detector 자체의 오류 영향은 분석하지 않았다. |
| noising strength 0 vs 0.6 | 정량 평가는 strength 0, text-guided 예시는 strength 0.6이다. | §III, §III-C, pp.4, 6 | reconstruction 성능과 diffusion refinement 시연을 분리한다. strength별 연속적인 성능 곡선은 없다. |
| 별도 구성요소 제거 실험 | cross-attention 제거, latent 차원 변경, phase 추가, VAE/LDM fine-tuning 제거 실험은 보고되지 않았다. | 논문 전체 `[확인 범위: pp.1–6]` | latent-space 설계와 각 구성요소의 독립 기여를 분리할 수 없다 `[내 판단]`. |

- **빠진 ablation `[내 판단]`**: (1) pretrained LDM 없이 pixel baseline과 비교, (2) CSI phase를 포함했을 때의 변화, (3) cross-attention과 encoder 폭 $b$의 효과, (4) text prompt 없이/strength별 복원 품질, (5) 시간적으로 분리된 test split을 사용했을 때의 성능이 필요하다.

## 7. 한계와 비판

**저자가 밝힌 한계** (§II-A, §III-C–IV, pp.2, 5–6):

- CSI와 이미지 사이에 충분한 mutual information이 있어야 한다. CSI가 시각적 변화와 잘 대응하지 않으면 안정적인 mapping이 어렵다 (§II-A, p.2).
- pretrained Stable Diffusion 같은 LDM에 의존한다 (§II-A, p.2).
- latent bottleneck 때문에 얼굴 세부, fine texture, text 같은 high-frequency detail이 보존되지 않는다 (§III-C, p.6).

**내가 보는 문제** — 각 항목은 “무엇이 문제인지 + 그래서 어떤 주장이 흔들리는지” 형태로:

- **[방법] 입력 정보의 의미가 불명확하다**: 본문은 복소 CSI에서 $\operatorname{Re}(x_c)^2+\operatorname{Im}(x_c)^2$를 계산하고 이를 amplitude라고 설명하지만, 일반적인 magnitude라면 제곱근 여부가 중요하다 (§II-C, p.3). 정확한 전처리 정의가 불명확하면 재현과 phase-only 비교가 막힌다 `[확인 필요]`.
- **[실험] 모델이 baseline보다 작지 않다**: Dataset 1에서 LatentCSI는 22.9M parameters로 baseline 16.4M보다 크고, Dataset 2에서도 13.6M 대 11.5M이다 (§III-A–B, pp.4–5). 따라서 시간 단축은 “작은 모델” 때문이 아니라 pixel-space 출력보다 latent 출력이 계산에 유리하기 때문이라고 표현해야 한다.
- **[실험] test set을 모델 선택에 사용했을 가능성이 있다**: 논문은 5회 학습에서 “best test loss” 모델로 이미지를 생성했다고 적는다 (§III, p.4). 이 표현이 epoch 선택을 뜻한다면 test set이 조기 선택에 노출되어 결과가 낙관적으로 편향된다. validation loss 기반 선택이었다면 명시적으로 고쳐 써야 한다 `[확인 필요]`.
- **[실험] 데이터 분할이 시간적으로 독립인지 알 수 없다**: Dataset 1은 10 Hz로 25분 동안 수집한 연속 데이터인데 80/10/10 분할 방식이 구체적으로 적혀 있지 않다 (§III-A, p.4). 인접 프레임이 train/test에 섞였다면 새로운 위치·시간·장면에 대한 일반화 성능이 과대평가될 수 있다 `[내 판단]`.
- **[실험] FID와 실제 sensing 정확도가 충돌한다**: Dataset 2에서 FID는 LatentCSI가 크게 앞서지만 RMSE·SSIM은 baseline이 앞선다 (Table III, p.6). 즉 “더 그럴듯한 이미지”와 “실제 정답에 가까운 이미지”가 다르므로, FID 개선을 곧 sensing 정확도 개선으로 해석하면 안 된다.
- **[일반화] 데이터 범위가 좁다**: Dataset 1은 한 명의 사람이 작은 실내에서 움직이고, Dataset 2도 MM-Fi의 특정 환경·두 subject·네 활동만 사용한다 (§III-A–B, pp.4–5). 다른 방, 사람 수, WiFi 장치, 가구 배치에서 같은 성능이 나오는지는 보여주지 못한다.
- **[서술] privacy 주장이 실험보다 앞선다**: 저자는 latent bottleneck이 얼굴·의상·배경의 세부 재현 위험을 낮춘다고 설명하지만 (§I–II, pp.1–2), 재식별률, membership inference, 얼굴 복원 성공률 같은 privacy 지표는 없다. “privacy-preserving”은 검증된 결과라기보다 설계 가설로 읽어야 한다 `[내 판단]`.
- **[서술] text control은 정성 예시에 머문다**: Table IV는 prompt별 이미지 예시를 보여주지만, prompt adherence나 CSI 장면 보존 사이의 trade-off를 정량화하지 않는다 (§III-C, Table IV, p.6). 따라서 controllability가 실제 응용 수준이라고 결론 내릴 근거는 부족하다.

## 8. 재현성 체크

| 항목 | 상태 | 비고 |
|---|---|---|
| 코드 공개 | ☐ 예 ☑ 아니오 | 논문에 공식 코드 링크 미기재 |
| 학습 데이터 접근 가능 | ☐ 예 ☑ 아니오 | MM-Fi subset은 공개 데이터셋이지만 custom Dataset 1의 공개 여부·다운로드 경로는 미기재 |
| 체크포인트 공개 | ☐ 예 ☑ 아니오 | 미기재 |
| 하이퍼파라미터 전부 명시 | ☐ 예 ☑ 아니오 | learning rate·early stopping·채널 수는 있으나 batch size, epoch, 전처리 세부, diffusion scheduler 등 미기재 |
| 컴퓨트 요구량 명시 | ☑ 예 ☐ 아니오 | H100 1개와 CPU 8 cores를 명시하지만 GPU memory·총 inference 비용은 미기재 |
| 결과에 분산·시드 보고 | ☑ 예 ☐ 아니오 | 5회 평균±표준편차, 구체적인 seed는 미기재 |

내가 재현한다면 가장 막힐 지점:

1. custom CSI–image Dataset 1과 정확한 train/validation/test split을 얻을 수 없다.
2. CSI 전처리 식, normalization, batch size, diffusion scheduler, stopping 기준의 세부가 부족하다.
3. 공개 checkpoint/code가 없어 Stable Diffusion v1.5와 CSI encoder를 직접 다시 구현해야 한다.

## 9. 관련 연구 속 위치

- **직접 기반한 연구**: `CSI2Image: Image Reconstruction From Channel State Information Using Generative Adversarial Networks` (IEEE Access 2021) — CSI에서 이미지를 직접 복원하는 hybrid GAN baseline으로 비교한다 (§III, p.4).
- **경쟁·대안 접근**: `WiFi-Based Human Pose Image Generation` (MMSP 2022), `RFGAN: RF-Based Human Synthesis` (IEEE TMM 2023) — CSI에서 pose/keypoint 또는 사람 이미지를 생성하는 GAN 계열 접근이다 (References [4]–[5], p.6).
- **표현 공간의 기반**: `High-Resolution Image Synthesis with Latent Diffusion Models` (CVPR 2022) — Stable Diffusion의 latent-space diffusion 구성에 해당한다 (Reference [9], p.6).
- **이 논문 이후**: 후속 연구·인용 관계는 이 정독 범위에서 조사하지 않았으므로 `[확인 필요]`.

한 줄 위치 규정: `LatentCSI`는 CSI-to-image 문제에 pretrained latent diffusion을 연결해 perceptual quality와 학습 효율을 얻으려 한 시스템 논문이다. 핵심 결과는 “정답 픽셀을 가장 정확히 복사한다”가 아니라 “CSI가 제공하는 거친 단서를 자연스러운 이미지로 확장한다”에 가깝다 `[내 판단]`.

## 10. 시사점과 후속 아이디어

- **내 작업에 쓸 수 있는 것**: 센서 입력을 고해상도 출력에 직접 연결하기보다, pretrained generative model이 이해하는 중간 표현으로 변환하는 설계가 유용하다. 특히 CSI encoder와 pretrained decoder를 분리하면 데이터와 계산 요구량을 줄일 수 있다 `[내 의견]`.
- **이 논문이 열어 둔 질문**: CSI가 실제로 식별할 수 있는 정보와 LDM이 prior로 “상상한” 정보를 어떻게 분리할 것인가? text prompt가 CSI 관측과 충돌할 때 어느 쪽을 우선해야 하는가?
- **해볼 만한 실험 `[내 의견]`**:
  1. 시간·방·사람 기준으로 완전히 분리한 split에서 FID/RMSE/SSIM을 다시 측정한다.
  2. phase 포함/미포함, latent fine-tuning 여부, cross-attention 제거를 factorial ablation으로 비교한다.
  3. 얼굴 재식별률과 장면 위치 정확도를 함께 측정해 privacy–utility trade-off를 정량화한다.
  4. text prompt와 CSI의 일치도, diffusion strength별 장면 보존율을 평가한다.

## 11. 미해결 질문

1. Dataset 1의 80/10/10 split은 시간적으로 인접한 샘플이 서로 다른 split에 들어가지 않도록 구성했는가?
2. Table III의 각 평균은 5개 seed의 결과인가, 아니면 각 seed에서 test loss가 가장 좋은 epoch를 선택한 뒤 계산한 것인가?
3. 본문의 $\operatorname{Re}(x_c)^2+\operatorname{Im}(x_c)^2$는 magnitude squared인가, 표기 누락으로 인한 magnitude인가?
4. strength 0.6 text-guided 결과에서 이미지의 인물 위치·자세가 CSI 관측과 얼마나 보존되는가?

## 12. 인용

```bibtex
@inproceedings{ramesh2025latentcsi,
  author    = {Ramesh, Eshan and Nishio, Takayuki},
  title     = {Real-Time Reconstruction of Physical Scenes from WiFi CSI via Latent Diffusion},
  booktitle = {Proceedings of the 31st Annual International Conference on Mobile Computing and Networking},
  year      = {2025},
  pages     = {1234--1236},
  doi       = {10.1145/3680207.3765601}
}
```

---
*리뷰 작성: 2026-09-04 · 읽은 범위: PDF pp.1–6 전체(§I–IV, Tables I–IV, Fig. 1–4, References)*
