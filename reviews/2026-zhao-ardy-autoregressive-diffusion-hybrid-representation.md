---
title: "ARDY: Autoregressive Diffusion with Hybrid Representation for Interactive Human Motion Generation"
authors: ["Zhao, Kaifeng", "Petrovich, Mathis", "Zhang, Haotian", "Wang, Tingwu", "Tang, Siyu", "Rempe, Davis"]
venue: "ACM Transactions on Graphics (SIGGRAPH 2026), Vol. 45, No. 4, Article 86"
year: 2026
arxiv: "2607.08741"
doi: "10.1145/3811284"
code: "https://github.com/nv-tlabs/ardy"
pdf: "papers/2026-09-02/zhao-ardy-autoregressive-diffusion-hybrid-representation-interactive-human-motion-generation.pdf"
read_date: 2026-08-13
rating: 4
tags: [human motion generation, autoregressive diffusion, real-time animation, SMPL, interactive control, NVIDIA]
status: 완료
---

# ARDY: Autoregressive Diffusion with Hybrid Representation for Interactive Human Motion Generation

> **TL;DR** — 텍스트와 운동학적 제약(경로, 웨이포인트, 키프레임, 관절 위치/회전)을 실시간으로 동시에 반영하는 스트리밍 인체 모션 생성 프레임워크. 명시적 root 특성과 잠재(latent) body 임베딩을 결합한 "hybrid representation"과, root를 먼저 예측하고 이를 조건으로 body를 예측하는 2단계 자기회귀 diffusion denoiser로, 오프라인 diffusion 모델 수준의 제어력을 33ms 지연시간에 달성했다고 주장한다.

---

## 1. 문제와 동기

- **풀려는 문제**: 게임·시뮬레이션·휴머노이드 로봇 제어 같은 인터랙티브 응용에서, 텍스트 프롬프트와 운동학적 목표(경로, 키프레임, 관절 위치/회전 등)를 실시간으로 동시에 반영하며 3D 인체 모션을 스트리밍 생성하는 것 (Abstract, §1 p.1-2).
- **기존 방식의 무엇이 부족한가** (논문 주장 / §1, §2, p.2-3, Table 1): 오프라인 모션 생성(diffusion, masked modeling)은 텍스트·운동학적 제약 모두에 정밀한 제어를 제공하지만 반복적 디노이징으로 느려 인터랙티브 응용에 부적합하다. 온라인/실시간 모델은 빠르지만 제어력을 희생하거나(텍스트만 지원하고 운동학적 제약 미지원, 또는 그 반대), 짧은 context window 때문에 복잡한 텍스트 의미나 장기 목표(long-horizon goal)를 다루지 못한다. Table 1(p.3)이 경쟁 방법 7개를 실시간성·온라인 프롬프팅·제약 종류·최적화/RL 필요 여부·context 길이 축으로 비교하며 이 공백을 구체적으로 보여준다.
- **그 진단에 동의하는가** `[내 의견]`: Table 1의 비교가 각 방법의 정확한 인용과 함께 조목조목 나열돼 있어 진단 자체는 설득력 있다. 다만 "우리만 모든 항목에 체크(✓)"라는 표 구성은 저자 스스로 설계한 비교축이라, 다른 축(예: 학습 데이터 규모, 스켈레톤 일반성)을 기준으로 하면 결과가 달라질 수 있다는 점은 감안해야 한다.

## 2. 핵심 기여

논문이 §1 말미(p.2)에서 스스로 요약한 3가지 기여:

| # | 저자 주장 기여 | 위치 | 실제로 새로운가 `[내 판단]` |
|---|---|---|---|
| 1 | Hybrid latent-body explicit-root representation — root는 명시적·해석 가능한 형태로, body는 학습된 토크나이저의 압축된 latent로 표현 | §3.1, p.3-4 | 개별 요소(explicit root, latent body 토큰화)는 각각 선행 연구에 있던 아이디어이나, 이 둘을 분리해 "정밀한 root 제어 + 효율적인 body 생성"을 동시에 노리는 조합은 실용적 개선으로 보인다. |
| 2 | 2단계 자기회귀 diffusion denoiser (가변 history 길이, full-body keyframe·root waypoint·경로·end-effector까지 지원하는 장기 운동학적 제약 조건화) | §3.3-3.4, p.4-6 | root→body 순차 예측이라는 분해 아이디어는 Rempe et al.(2026, Kimodo)의 interleaved 2단계 설계를 그대로 계승한다고 본문이 명시(§3.4, "employs an interleaved, two-stage design [Rempe et al. 2026]"). 완전히 새로운 아이디어라기보다 인접 연구의 설계를 이 문제에 재적용·검증한 것에 가깝다. |
| 3 | 대규모 production-quality proprietary 데이터셋(Bones Rigplay, ~700시간)에서의 광범위한 설계 검증 | §5, p.8-11 | 데이터 규모 자체는 방법론적 기여가 아니지만, HumanML3D 같은 포화된(saturated) 공개 벤치마크의 한계(§5.1에서 "ground truth보다 높은 R-precision을 찍는 방법들이 있어 포화됐다"고 직접 지적)를 피해 더 엄밀한 설계 비교를 했다는 점은 실증적 가치가 있다. |

## 3. 방법 (Method)

### 3.1 한 문단 개요
매 프레임 인체 자세를 "명시적 root 특성 + 잠재 body 임베딩"의 hybrid token으로 표현한다. 먼저 body motion tokenizer(비대칭 conditional autoencoder, causal transformer 인코더/디코더)가 patch 단위 body 특성을 압축된 latent 토큰으로 학습하고, 이 latent를 patchify된 명시적 root 모션과 concat해 최종 hybrid token을 만든다. 생성 단계에서는 2단계 자기회귀 diffusion denoiser가 현재 윈도우의 노이즈 낀 hybrid token을 텍스트·과거 history·(윈도우 안/밖의) 운동학적 목표에 조건화해 반복적으로 디노이징하는데, 매 diffusion step마다 root transformer가 먼저 clean root를 예측하고, 이를 조건으로 body transformer가 clean latent body 토큰을 예측하는 순서로 진행한다. 학습은 텍스트·운동학적 제약을 ground-truth 모션에서 직접 샘플링해 조건으로 주고, 생성된 토큰을 다시 명시적 모션으로 디코딩한 뒤 여러 손실을 합산해 진행한다.

### 3.2 표기와 정의
| 기호 | 의미 | 형태/차원 |
|---|---|---|
| $\mathbf{m} = (\mathbf{m}_{\text{root}}, \mathbf{m}_{\text{body}}) \in \mathbb{R}^M$ | 한 프레임의 명시적(explicit) 모션 특성 | $M$은 스켈레톤 관절 수에 의존 |
| $\mathbf{m}_{\text{root}} = (\mathbf{p}, \cos\psi, \sin\psi) \in \mathbb{R}^5$ | root 특성: 전역 위치 $\mathbf{p}\in\mathbb{R}^3$, heading angle $\psi$ | Eq.1 |
| $\mathbf{m}_{\text{body}} = (\boldsymbol{\theta}, \mathbf{J}, \dot{\mathbf{J}}, \mathbf{c})$ | body 특성: 6D 관절 회전 $\boldsymbol{\theta}\in\mathbb{R}^{6j}$, 비-root 관절 위치 $\mathbf{J}\in\mathbb{R}^{3j-3}$, 관절 속도 $\dot{\mathbf{J}}\in\mathbb{R}^{3j}$, 발 접촉 라벨 $\mathbf{c}\in\mathbb{R}^4$ | Eq.1, $j$=관절 수 |
| $\mathbf{x} = (\mathbf{m}_{\text{root}}, \mathbf{x}_{\text{body}})$ | hybrid 표현: root는 명시적 그대로, body는 latent | Eq.2, $\mathbf{x}_{\text{body}}\in\mathbb{R}^L$ |
| $\mathbf{x}^{1:T} = [\mathbf{m}_{\text{root}}^{1:T}; \mathbf{x}_{\text{body}}^{1:T}] \in \mathbb{R}^{T\times D}$ | patch 단위 hybrid 토큰 시퀀스, $D=L+5P$ | Eq.3, $P$=patch 크기, $T=N/P$ |
| $\mathbf{g}^{1:(C+F)}$ | 운동학적 목표(spatial goal): 현재 윈도우 내 $C$개 + 윈도우 밖 미래 $F$개 | §3.3, masked explicit representation로 인코딩 |
| $H$ | 가변 길이 history context 토큰 수 (0~최댓값) | §3.3 |
| $k$ | diffusion 디노이징 스텝 인덱스 | Eq.5 |

### 3.3 상세

- **자기회귀 생성 목표** (§3.3, p.5, Eq.4):

  $$\mathbf{x}^{1:C} = \mathcal{F}(s, \mathbf{x}^{(-H+1):0}, \mathbf{g}^{1:(C+F)})$$

  이 수식이 하는 일 (직관): 현재 예측 윈도우의 $C$개 토큰을, 텍스트 $s$·가변 길이 history·(윈도우 안팎의) 목표 제약을 모두 조건으로 삼아 한 번에 생성하겠다는 선언. $H$를 가변으로 둔 것이 핵심 — "걷다가 멈췄다가 다시 걷기" 같은 비주기적 긴 문맥을 놓치지 않기 위함(§3.3, p.5).

- **디노이징 스텝** (§3.4, p.5, Eq.5):

  $$\hat{\mathbf{x}}_0^{1:C} = \mathcal{F}(k, s, \mathbf{x}_k^{1:C}, \mathbf{x}^{(-H+1):0}, \mathbf{g}^{1:(C+F)})$$

  이 수식이 하는 일 (직관): DDPM 프레임워크에서 스텝 $k$의 노이즈 낀 토큰을 받아 clean한 예측을 바로 내놓는 형태(x0-prediction). 내부적으로는 root transformer → body transformer 순으로 이 예측을 2단계로 쪼갠다(Fig.3).

- **손실 함수** (§3.5, p.7, Eq.6-11): 토크나이저는 재구성 손실 + foot-skating 손실 $\mathcal{L}_{\text{skate}} = \frac{\sum_{j\in S_f}\hat{c}_j\|\dot{\hat{\mathbf{J}}}_j\|_2}{\sum_{j\in S_f}\hat{c}_j}$ (Eq.6, 접촉 중인 발 관절의 속도를 벌점). 디노이저는 4개 손실의 합:
  - $\mathcal{L}_{\text{hybrid}} = \|\hat{\mathbf{x}}_0 - \mathbf{x}_0\|_1$ (Eq.7, smooth L1)
  - $\mathcal{L}_{\text{dec}} = \|\hat{\mathbf{m}}_{\text{body}} - \mathbf{m}_{\text{body}}\|_1$ (Eq.8, 디코딩된 명시적 body 손실)
  - $\mathcal{L}_{\text{goal}} = \|\mathbf{v}\odot(\hat{\mathbf{m}}_0 - \mathbf{g})\|_1$ (Eq.9, 제약 목표 정확도 강조)
  - $\mathcal{L}_{\text{consist}} = \|\hat{\mathbf{J}}_0 - \text{FK}(\hat{\boldsymbol{\theta}}_0)\|_2$ (Eq.10, 예측된 관절 위치와 예측된 관절 회전을 순방향 기구학(FK)으로 계산한 위치 간의 일관성)
  - $\mathcal{L} = \mathcal{L}_{\text{hybrid}} + \mathcal{L}_{\text{dec}} + \mathcal{L}_{\text{goal}} + \mathcal{L}_{\text{consist}}$ (Eq.11)

- **학습 절차** (§3.5, p.6-8): 토크나이저 — 8-layer causal transformer 인코더/디코더, latent dim 512, patch size 4, AdamAtan2 optimizer(lr 2e-5, batch 128), 단일 A100-SXM4-80GB에서 4M step. FSQ(Finite Scalar Quantization, 64 levels×128 dim)를 기본 토크나이저로 채택(VAE·vanilla AE 대비 학습 안정성이 높아서). 디노이저 — root/body transformer 각각 8-layer 8-head hidden dim 1024(배포 데모 모델 기준 총 ~156M 파라미터), 텍스트 인코더는 Llama-3-8B-Instruct 기반 LLM2Vec. DDPM 프레임워크, batch 512, 4×A100-SXM4-80GB에서 1M step. 기본 10 diffusion step(4 step까지 가능), classifier-free guidance를 위해 텍스트/제약을 10% 확률로 드롭. **dropout은 의도적으로 사용하지 않음**(root 제약 조건이 부분 소실되는 부작용 때문, §3.5, p.7).
- **추론 절차**: $G=40$ 프레임(2초@20fps) 단위 윈도우로 자기회귀 롤아웃하며, history/미래 제약 모두 최대 8초로 truncated sliding window 적용(§4.1, p.7-8). 실시간 인터랙션을 위해 latency-aware replanning(비차단 buffer 전략, Fig.5, p.8)을 도입해 느린 모델도 끊김 없이 재계획 가능. 데모(RTX 4090)에서 4-step 모델 평균 지연 33ms, 10-step 모델 63ms(§4.2, p.8).

### 3.4 왜 이 방법이 통한다고 저자는 말하는가
- **저자의 설명** (§3.4, p.6): body 예측을 clean root 예측에 조건화하면(2단계 분해) root와 body를 동시에(one-stage) 생성하는 것보다 "더 쉬운 하위 문제"로 쪼개져, 정밀한 제어력을 모션 충실도 손실 없이 얻을 수 있다는 가설.
- **그 설명이 실험으로 검증되는가, 아니면 사후 서사인가** `[내 판단]`: 부분적으로 검증된다. Table 2(p.10)에서 two-stage가 one-stage 대비 Waypoint error(0.024 vs 0.164)·Trajectory error(0.015 vs 0.017)에서는 크게 앞서지만, R-Precision(65.47 vs 65.84)과 Joint rotation error(2.23 vs 2.46, 오히려 ARDY가 근소하게 나음)에서는 one-stage와 거의 차이가 없거나 오히려 one-stage가 R-Precision에서 미세하게 앞선다. 즉 "정밀한 제어(waypoint/trajectory)"에서의 이득은 뚜렷하지만 "모션 충실도(R-Prec)"에서의 이득은 본문 서술("higher-fidelity text-conditioned motion")만큼 뚜렷하지 않다.

## 4. 실험 설정

| 항목 | 내용 | 위치 |
|---|---|---|
| 데이터셋 | (주 실험) **Bones Rigplay**: NVIDIA 비공개 proprietary, ~700시간, 150명+ 참가자, unified-proportion 27관절 스켈레톤으로 리타겟, 클립 1-180초→최대 10초로 클립·20fps 서브샘플링, semantic-content 기준 90/10 split(train 315k / test 35k clip, unseen action 평가). (보조 실험) **HumanML3D**: 공개, ~30시간, HumanAct12 서브셋 제외, **SMPL 원본 joint rotation을 보존하도록 자체 리타겟**(표준 HumanML3D 파이프라인과 다름) | §5.1(p.8), §6.1(p.11) |
| 태스크·지표 | text-only: Skate(m/s), Top-3 R-precision, FID. constraints-conditioned: Skate, Joint rotation error(°), Joint position error(m), Keyframe body error(m), Trajectory error(m), Waypoint error(m). HumanML3D 비교: R-Prec, FID, Skate(%), Error(cm), Latency(s). perceptual study: pairwise 선호도(%) | Table 2-6 |
| 베이스라인 | 오프라인 SOTA: MaskControl(Pinyoanuntapong et al. 2025, 조인트 제어 특화). 자기회귀 온라인: DiP(Tevet et al. 2025, CAMDM 확장) — "closest to our work"로 명시 | §6.2(Table 4), §6.3(Table 5-6) |
| 모델 규모 | 토크나이저: 8-layer, latent 512. 디노이저(root+body transformer 각각): 8-layer, 8-head, hidden 1024, 배포 데모 모델 기준 총 ~156M 파라미터 | §3.5(p.7) |
| 하이퍼파라미터 | 토크나이저: lr 2e-5, batch 128, patch size 4(기본, ablation 1/4/8), FSQ 64×128(기본, ablation 16-32/64-32/64-128/64-256). 디노이저: lr 2e-5, batch 512, diffusion steps 기본 10(ablation 1/2/3/4/10/100), generation horizon 기본 40 frames(ablation 4/8/12/20/40) | §3.5, Table 3 |
| 컴퓨트·학습 시간 | 토크나이저: 단일 A100-SXM4-80GB, 4M step. 디노이저: 4×A100-SXM4-80GB, 1M step. 추론/데모: RTX 4090 | §3.5, §4.2 |
| 시드·반복 횟수 | 성능 표(Table 2-5)의 시드·반복 횟수는 **미기재**. Perceptual study(Table 6)만 240회 pairwise 비교로 명시 | §6.3(p.12) |

## 5. 결과 — 주장과 증거의 대응

| 저자 주장 | 근거로 제시된 결과 | 위치 | 그 근거가 주장을 지지하는가 `[내 판단]` |
|---|---|---|---|
| Hybrid representation이 explicit representation보다 모션 품질·제어 정확도 모두에서 우수 | ARDY FID 0.027 vs Explicit 0.065, Joint pos error 0.025m vs 0.130m 등 대부분 지표에서 큰 격차 | Table 2(p.10) | 대체로 지지. 단 **Joint rotation error**는 Explicit(1.67°)이 ARDY(2.23°)보다 오히려 낮아 전 지표 우위는 아니다. |
| 2단계 아키텍처가 1단계보다 "정밀한 제어를 모션 충실도 손상 없이" 달성 | Trajectory/Waypoint error는 크게 개선(0.015/0.024 vs 0.017/0.164)되나 R-Prec(65.47 vs 65.84)·Joint rot error(2.23 vs 2.46)는 근소하거나 one-stage가 근소 우위인 지표 존재 | Table 2(p.10) | 부분 지지 — "공간 제약 정밀도" 개선은 뚜렷하나 "모션 충실도 손상 없음(R-Prec 유지)"이라는 부분은 one-stage가 오히려 근소하게 나아 완전히 깔끔하지는 않다. |
| 4-step 같은 적은 diffusion step에서도 "highly competitive" 성능 | step 10→4에서 FID 0.027→0.034, Traj 0.015→0.028로 소폭 저하하나 step 1-2보다는 크게 나음 | Table 3(p.10) | "step 1-2 대비 경쟁력"이라는 의미로는 지지되나, "GT 대비 경쟁력"이라는 의미로 오독될 여지가 있다. |
| HumanML3D에서 MaskControl 대비 "경쟁력 있는 text-following" + 더 낮은 skate + 3배 빠른 latency | ARDY* R-Prec 0.729 vs MaskControl* 0.760(오프라인 SOTA가 여전히 더 높음), FID 0.044 vs 0.050(ARDY 우위), Skate 6.28% vs 7.27%(ARDY 우위), Error(cm) 4.15 vs 46.18(ARDY 압도적 우위), Latency 0.15s vs 0.46s | Table 4(p.11) | R-Precision만 놓고 보면 오프라인 SOTA를 못 넘는다 — "competitive"라는 표현은 정확하지만, Abstract의 "high motion quality"라는 요약은 이 지표 하나만으로는 과장될 소지가 있다. |
| DiP 대비 in-horizon/out-of-horizon 모두 우월, 특히 장기 계획(out-of-horizon)에서 압도적 | out-of-horizon Error(cm): DiP 17.64 vs ARDY 2.92(6배 차이). Perceptual study 240회 비교에서도 Motion Quality 65.8% vs 9.2%로 사람 평가 일관 | Table 5-6(p.12) | 강하게 지지됨. 정량 지표와 사람 평가(perceptual study)가 서로 일치해 신뢰도가 높다. |

핵심 수치:
- (Table 4, §6.2) HumanML3D에서 ARDY*는 MaskControl* 대비 joint 제약 오차를 46.18cm→4.15cm로 11배 줄이면서 latency는 3배 빠르다 — "빠르면서 정확한 제어"라는 논문의 핵심 주장을 가장 강하게 뒷받침하는 수치.
- (Table 5, §6.3) out-of-horizon(장기 목표) 설정에서 DiP의 오차가 in-horizon 대비 거의 2배(9.20→17.64cm)로 급증하는 반면 ARDY는 오히려 안정적(2.48→2.92cm) — 가변 history/장기 제약 설계의 효과를 가장 직접적으로 보여주는 비교.

## 6. Ablation / 분석

| 제거·변경한 것 | 성능 변화 | 위치 | 해석 |
|---|---|---|---|
| Explicit representation으로 대체 (hybrid 미사용) | FID 0.027→0.065, R-Prec 65.47→53.90, Joint pos error 0.025→0.130m 등 대부분 악화. 단 Joint rot error는 2.23→1.67로 개선 | Table 2(p.10) | 고차원 explicit 표현이 few-step denoising 환경에서 생성 학습을 어렵게 만든다는 저자 가설과 대체로 일치. |
| Global-to-local root 변환 제거 (토크나이저 디코더가 global 좌표 그대로 사용) | Skate 0.264→0.284(text-only), 전반적으로 소폭 열화, 특히 foot skating 관련 지표 뚜렷이 나빠짐 | Table 2(p.10) | local 표현이 발 미끄러짐 억제에 실질적으로 기여함을 보여준다. |
| One-stage 아키텍처(root·body 동시 예측) | Trajectory/Waypoint error 대폭 악화(0.017/0.164 vs 0.015/0.024), R-Prec·Joint rot error는 근소하게 더 나음 | Table 2(p.10) | 공간 제약 정밀도에서는 2단계가 명확히 유리하나, 텍스트 정합·회전 정확도에서는 트레이드오프가 존재. |
| Generation horizon 4/8/12/20/40 frames | 4프레임: FID 0.224로 최악, 학습 불안정 및 "드리프트" 모션. 40프레임(기본)이 FID·R-Prec 최고 | Table 3(p.10) | horizon이 너무 짧으면 텍스트 의미를 놓친다는 저자 주장과 일치. 단, 저자 스스로 "4-frame horizon의 text-only skate 지표가 misleadingly low(모델이 텍스트에 반응 안 해서 가만히 있는 것)"라고 인정(§5.3, p.11) — skate 지표 단독 해석의 함정을 스스로 지적. |
| Diffusion steps 1/2/3/4/10(기본)/100 | 1-2 step: 큰 폭 열화(Joint rot error 25.39°, 7.96°). step 10→100: FID 0.027→0.025, Traj 0.015→0.009로 소폭 개선되나 R-Prec은 65.47→65.49로 거의 무변화 | Table 3(p.10) | step을 극단적으로 늘려도 R-Precision 이득은 체감되어, 10-step이 실용적 절충점이라는 저자 선택을 뒷받침. |
| Tokenizer patch size 1/4(기본)/8 | patch 1: 초반 학습은 빠르나 후반 불안정, 최종 성능 최악(FID 0.152). patch 8: FID·R-Prec 소폭 개선되나 skate·제약 오차 악화 | Table 3(p.10) | patch 크기가 클수록 세밀한 자세 정보 손실 → 발 미끄러짐·제약 정확도 저하라는 트레이드오프. |
| Tokenizer latent capacity(FSQ 16-32~64-256) | 대체로 성능 유사, 64-128(기본)이 여러 지표에서 균형점 | Table 3(p.10) | 용량이 너무 작으면 세부 디테일 손실, 너무 크면 학습 budget 내 수렴이 느려짐. |
| Tokenizer type(AE/VAE/FSQ) | 세 방식 성능은 대체로 유사하나, vanilla AE는 긴 horizon(40프레임)에서 학습이 발산 | §5.3(p.11) | FSQ가 학습 안정성 면에서 우위 — 저자가 FSQ를 기본으로 채택한 근거. |

- **빠진 ablation** `[내 판단]`: (1) 텍스트 인코더로 LLM2Vec(Llama-3-8B 기반)을 선택한 근거(예: CLIP 대비 얼마나 나은가)에 대한 비교 실험이 없다. (2) $\mathcal{L}_{\text{goal}}$, $\mathcal{L}_{\text{consist}}$ 등 손실 항 각각을 제거했을 때의 개별 기여도를 분리하는 손실 ablation이 없어, Eq.11의 4개 항이 각각 얼마나 기여하는지 알 수 없다. (3) latency-aware replanning(buffer 전략, Fig.5)이 실제 체감 품질에 미치는 영향을 정량화하는 ablation이 없고 정성적 설명뿐이다.

## 7. 한계와 비판

**저자가 밝힌 한계** (§7 Discussion "Limitations" 문단, p.12):
- 자기회귀 생성 시 과거 프레임 전체를 history context로 사용해, 매우 긴 horizon 작업에는 비효율적일 수 있다 — 더 구조화된 메모리 표현·갱신 메커니즘이 향후 과제.
- diffusion 모델이라 multi-step 반복 생성이 계산 비용이 크다 — shortcut diffusion 모델과의 결합이 향후 방향.
- 순수 운동학적(kinematic) 모델이라 물리적 동역학을 모른다 — foot skating·jittering 아티팩트가 발생할 수 있으며, 물리 모델링 통합이 물리 제약이 중요한 응용(로봇 등)에 필수적이라고 인정.

**내가 보는 문제**:
- **[실험]** 핵심 정량 결과 대부분(Table 2, 3, 그리고 §4의 데모)이 NVIDIA 비공개 proprietary Bones Rigplay 데이터셋 위에서 나온다(§5.1, "we leverage the large-scale **proprietary** Bones Rigplay dataset"). 외부에서 이 데이터셋에 접근할 방법이 없어, 논문이 제시한 설계 선택(hybrid representation, two-stage 등)의 우수성을 제3자가 독립적으로 재현·검증할 수 없다. 유일하게 검증 가능한 공개 벤치마크(HumanML3D, Table 4)에서는 오프라인 SOTA인 MaskControl의 R-Precision(0.760)을 ARDY*(0.729)가 넘지 못한다 — Abstract의 "high motion quality" 요약이 이 사실을 명시적으로 언급하지 않는다.
- **[실험]** Table 4에서 저자들이 SMPL 회전을 보존하려고 새로 만든 "our retarget" 방식의 ground-truth R-Precision(0.732)이 원본 HumanML3D retarget의 ground-truth R-Precision(0.739)보다 이미 더 낮다. 즉 평가 기준 자체가 원본과 달라졌는데, 이 리타겟 방식 변경이 ARDY와 베이스라인(MaskControl, DiP) 양쪽에 동등하게 적용됐는지, 혹시 ARDY의 표현(회전 보존)에 유리하게 작용했을 가능성은 없는지 논문이 논의하지 않는다 `[확인 필요]`.
- **[서술]** 저자들 스스로 "text-only 4-frame horizon의 skate 지표가 misleadingly low하다(모델이 텍스트 프롬프트에 반응하지 못해 가만히 서 있어서 낮게 나온 것)"라고 인정한다(§5.3, p.11). 이는 매우 정직한 자기비판이지만, 동시에 skate 지표를 논문 전반에서 단독으로 신뢰할 수 없다는 뜻이다. 예컨대 Table 2의 "Global root-conditioned decoder" 행에서 skate가 소폭만 나빠지는데, 이것이 실제 모션 품질 저하인지 "덜 움직여서" 생긴 착시인지 독자가 R-Prec·FID와 매번 교차 검증해야 한다.
- **[일반화]** 모델은 "purely kinematic"이라 물리적 타당성(관성, 접촉력, 균형)을 전혀 모델링하지 않는다(저자도 인정). 그런데 §1(p.1)은 이 방법의 동기로 "휴머노이드 로봇 제어(humanoid robotics)"를 명시적으로 언급한다 — 물리적으로 실행 불가능한 동작(예: 지지 없는 순간적 도약)이 로봇 제어에 그대로 쓰이면 위험할 수 있는데, 이 간극에 대한 논의가 Limitations에서 다뤄지지 않는다.
- **[방법 — 이전 대화에서 확인한 지점]** HumanML3D 실험(§6.1, p.11)에서는 SMPL 원본 관절 회전을 보존해 "비싼 IK 후처리 없이 body model을 직접 애니메이션할 수 있다"고 명시하지만, 이 이점은 **오직 이 HumanML3D 학습 세팅에서만 검증**됐다. 논문의 메인 정량 결과(§5, Table 2-3)와 실제로 GitHub에 공개된 체크포인트는 전부 Bones Rigplay의 자체 27관절 "Core" rig 기준이며, SMPL과의 호환성은 README에도 언급되지 않는다. "회전을 직접 생성해 IK를 생략한다"는 핵심 이점이 실제 배포 모델에는 적용되지 않는 비대칭성이 논문 안에서 명시적으로 논의되지 않는다.

## 8. 재현성 체크

| 항목 | 상태 | 비고 |
|---|---|---|
| 코드 공개 | ☑ 예 | GitHub(`nv-tlabs/ardy`), 코드 자체는 Apache-2.0 라이선스. |
| 학습 데이터 접근 가능 | ☐ 아니오 | 메인 데이터셋 Bones Rigplay는 비공개 proprietary(§5.1, "we leverage the large-scale proprietary Bones Rigplay dataset"). HumanML3D 실험(§6)만 공개 데이터 사용. |
| 체크포인트 공개 | ☑ 예 | GitHub에 Bones Rigplay 학습 체크포인트 공개(확인함). SMPL/HumanML3D 학습 체크포인트는 공개 목록에 없음 `[확인 필요]`. |
| 하이퍼파라미터 전부 명시 | ☑ 예 | §3.5, §5.1에 optimizer·lr·batch·GPU 대수·step 수까지 상세 기재. |
| 컴퓨트 요구량 명시 | ☑ 예 | 토크나이저(A100×1), 디노이저(A100×4), 데모(RTX 4090) 각각 명시. |
| 결과에 분산·시드 보고 | ☐ 아니오 | Table 2-5 성능 지표들의 시드·반복 횟수 미기재. Perceptual study(Table 6)만 240회 pairwise 비교로 명시. |

내가 재현한다면 가장 막힐 지점: §5의 메인 실험(Table 2, 3)은 Bones Rigplay가 비공개라 동일 스케일 재현이 원천적으로 불가능하다. §6의 HumanML3D 실험은 데이터는 공개돼 있으나, "SMPL 원본 회전을 보존하는 자체 리타겟 파이프라인"의 정확한 구현이 GitHub 코드베이스에 포함돼 있는지 확인이 필요하다 `[확인 필요]`.

## 9. 관련 연구 속 위치

- **직접 기반한 연구**: DiP(Tevet et al., 2025, CAMDM 확장) — "closest to our work"로 명시(§2, p.6), 텍스트+3D 목표 관절 조건화 자기회귀 diffusion의 직계 선행 연구; Kimodo(Rempe et al., 2026) — interleaved two-stage denoiser 설계의 출처로 명시(§3.4); CAMDM(Chen et al., 2024); SMPL(Loper et al., 2015) — HumanML3D 실험에서 원본 회전 보존에 사용.
- **경쟁·대안 접근**: MaskControl(Pinyoanuntapong et al., 2025, 오프라인 masked modeling SOTA); MotionStreamer(Xiao et al., 2025, causal latent 온라인 생성); DartControl(Zhao et al., 2025a, VAE+diffusion 온라인); UniPhys(Wu et al., 2025, 물리 기반이나 test-time guidance 의존).
- **이 논문 이후**: `[확인 필요]` — 2026년 7월 발표된 매우 최신 논문(arXiv 2607.08741, 이 리뷰 작성 시점 기준 약 1개월 전)이라 후속 인용을 추적하기엔 이르다. 필요 시 추후 `/related-work`로 재확인 권장.

한 줄 위치 규정: 오프라인 조건화 모션 diffusion(MaskControl류)의 정밀한 제어력과, 온라인 자기회귀 모션 생성(DiP·CAMDM류)의 실시간성을 hybrid representation과 2단계 디노이저로 동시에 노리는 절충·통합 연구.

## 10. 시사점과 후속 아이디어

- **내 작업에 쓸 수 있는 것**: 관절 "위치"가 아니라 "회전(rotation)"을 생성 표현에 명시적으로 포함시키는 hybrid representation 설계는, 별도 IK/fitting 없이 body model을 바로 애니메이션할 수 있게 하는 실질적 해법이다(§6.1에서 명시적으로 검증됨). 다만 공개된 실제 체크포인트는 SMPL이 아닌 자체 rig 기준이므로, 그대로 가져다 쓰기보다는 SMPL/AMASS 기반으로 직접 재학습하거나 rig 리타게팅이 필요하다 `[내 의견]`.
- **이 논문이 열어 둔 질문**: 순수 기구학적(kinematic) 모델을 물리적으로 정확해야 하는 downstream(로봇 제어, 또는 WaveVerse류의 물리 기반 시뮬레이션)과 결합했을 때, foot skating·비현실적 접촉 아티팩트가 실제로 하위 태스크 정확도에 얼마나 해를 끼치는가.
- **해볼 만한 실험** `[내 의견]`: ARDY의 hybrid representation(회전을 직접 생성 대상에 포함) 아이디어를, 앞서 리뷰한 WaveVerse의 state-aware causal transformer(관절 위치만 생성해 SMPL fitting이 병목이 되던 구조, [[2026-zheng-scalable-rf-simulation-4d-worlds]])에 이식했을 때 실행시간이 실제로 얼마나 줄어드는지 측정.

## 11. 미해결 질문

1. 공개된 Bones Rigplay 학습 체크포인트를 SMPL 캐릭터에 쓰려면 구체적으로 어떤 리타게팅 절차가 필요한가? 논문·README 어디에도 이 변환 절차가 없다.
2. Table 4에서 "our retarget" 방식의 ground-truth R-Precision(0.732)이 원본 HumanML3D retarget(0.739)보다 낮아진 이유는 무엇이며, 이 차이가 ARDY와 베이스라인(MaskControl) 비교의 공정성에 영향을 주는가?
3. §7에서 언급한 "물리 모델링 통합"은 구체적으로 어떤 방향(RL 기반 physics controller와의 결합? 자체 물리 시뮬레이터 도입?)을 염두에 둔 것인가 — 논문은 방향성만 제시하고 설계는 밝히지 않는다.

## 12. 인용

```bibtex
@misc{zhao2026ardyautoregressivediffusionhybrid,
      title={ARDY: Autoregressive Diffusion with Hybrid Representation for Interactive Human Motion Generation},
      author={Kaifeng Zhao and Mathis Petrovich and Haotian Zhang and Tingwu Wang and Siyu Tang and Davis Rempe},
      year={2026},
      eprint={2607.08741},
      archivePrefix={arXiv},
      primaryClass={cs.GR},
      doi={https://doi.org/10.1145/3811284},
      url={https://arxiv.org/abs/2607.08741},
}
```

---
*리뷰 작성: 2026-08-13 · 읽은 범위: pp.1-14 전체(본문 §1-7, 참고문헌 포함). GitHub(`nv-tlabs/ardy`) README도 WebFetch로 보조 확인(라이선스·체크포인트 학습 데이터 확인 목적). (2026-08-13 수정: 다운로드 스크립트가 만든 잘못된 중첩 디렉터리 구조를 `papers/`에서 정리함.)*
