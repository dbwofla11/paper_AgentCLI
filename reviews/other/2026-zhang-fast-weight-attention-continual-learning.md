---
title: "Fast Weight Attention for Continual Learning"
authors: ["Zhang, Yifan", "Ta, Steve", "Zhang, Jasper", "Feng, Jichen", "Li, Shuzhen", "Zhang, Yongxin", "Liu, Yifeng", "Yuan, Huizhuo", "Wang, Mengdi", "Gu, Quanquan", "Yao, Andrew Chi-Chih"]
venue: "arXiv preprint"
year: 2026
arxiv: "2608.27763"
doi: "10.48550/arXiv.2608.27763"
code: "https://github.com/yifanzhang-pro/fast-weight-attention"
pdf: "papers/2026-09-04/zhang-fast-weight-attention-continual-learning.pdf"
read_date: 2026-09-04
rating: 4
tags: [continual learning, fast weights, linear attention, DeltaNet, state space models]
status: 완료
---

# Fast Weight Attention for Continual Learning

> **TL;DR** — 이 논문은 긴 문맥을 전부 저장하는 Transformer 대신, 고정 크기 행렬을 토큰마다 조금씩 업데이트하는 fast-weight attention을 “온라인 학습” 문제로 다시 설명한다. 핵심은 현재 토큰의 정답을 현재 key가 아니라 정답을 예측할 때 이미 보였던 prefix feature에 연결하는 것이며, 이 원칙으로 Falcon 계열 업데이트를 만들었다. 언어 모델링 성능은 경쟁력 있지만, 핵심인 시간 정렬의 효과를 직접 비교한 실험과 실제 긴 문맥에서의 속도·메모리 측정은 부족하다.

원문: [arXiv 공식 페이지](https://arxiv.org/abs/2608.27763) · [공식 코드·프로젝트 페이지](https://github.com/yifanzhang-pro/fast-weight-attention)

## 1. 문제와 동기

- **풀려는 문제**: 표준 Transformer attention은 길이 $N$인 문맥에서 attention matrix를 만들기 때문에 계산·메모리가 대체로 $O(N^2)$로 증가한다. KV cache도 토큰이 늘수록 커진다 (§1, p.1).
- **기존 방식의 무엇이 부족한가**: Linear Attention, SSM, DeltaNet 계열은 문맥을 고정 크기 recurrent state에 압축해 $O(N)$ 순차 처리와 $O(1)$ 상태 추론을 노린다. 하지만 이 논문은 기존 update 식이 “무엇을 학습하는지”와 “어느 시점의 feature가 정답을 써야 하는지”를 충분히 명시하지 않았다고 지적한다 (§1, pp.1–2).
- **그 진단에 동의하는가** `[내 의견]`: recurrent state를 “토큰이 들어올 때마다 수행하는 작은 온라인 학습기”로 보는 관점은 유용하다. 다만 시간 정렬이 실제 성능을 높인다는 것은 정의만으로 결정되지 않으며, 같은 모델에서 shifted/unshifted를 직접 비교해야 한다.

## 2. 핵심 기여

| # | 저자 주장 기여 | 위치 | 실제로 새로운가 `[내 판단]` |
|---|---|---|---|
| 1 | read-after-write autoregressive semantics에서 prefix-aligned pair $(\phi(k_{t-1}),v_t)$가 fast-memory의 올바른 학습 예시라고 정식화한다. | §1, §3, pp.2, 6–8 | 기존 update의 인덱싱을 명시적으로 분석한 점은 분명한 기여다. 그러나 이것이 성능상 우월한지는 실험으로 별도 검증되지 않았다. |
| 2 | squared-error regression에 NLMS 정규화를 적용한 Falcon-1/2/3을 제안한다. 각각 scalar gain, per-column gain, sliding-window mini-batch update다. | §3–4, pp.6–13, 19–22 | Delta rule와 online regression의 결합·확장이다. 새 이름을 붙인 전체 계열이 모두 새 알고리즘이라고 보기는 어렵고, 정렬·정규화·병렬화 조합이 핵심이다 `[내 판단]`. |
| 3 | negative inner-product objective에 기반한 Falcon-1A/2A/3A를 제안하고 recurrent·masked-parallel·chunk-parallel 형태를 유도한다. | §4.3–4.6, pp.14–25 | 기존 Linear Attention/Mamba-2와 연결되는 update를 다른 objective와 next-latent 정렬 아래 묶은 점이 기여다. 구현의 실제 이득은 실험 규모가 제한적이다. |
| 4 | language modeling과 variable-length addition에서 대표 Falcon 변형을 평가한다. | §5, pp.25–28 | 언어 모델링은 경쟁력을 보이고, 산술 길이 외삽에서 강한 결과를 보인다. 다만 전체 Falcon family를 검증한 것은 아니다. |

## 3. 방법 (Method)

### 3.1 한 문단 개요

각 token에서 나온 key·value를 모두 저장하지 않고, 고정 크기 행렬 $S_t$를 메모리로 유지한다. 이 행렬은 write feature $x_t$를 입력받아 value $y_t$를 예측하는 작은 선형 모델이다. token $t$를 예측할 때는 아직 $v_t$를 보지 못했으므로, $v_t$가 관측된 뒤 그 값을 당시 prefix에서 사용 가능했던 $\phi(k_{t-1})$에 연결한다. 이후 gradient descent 한 번으로 $S_t$를 갱신하고, 갱신된 state로 다음 출력을 읽는다 (§3, pp.6–8).

### 3.2 표기와 정의

| 기호 | 의미 | 형태/차원 |
|---|---|---|
| $k_t,q_t,v_t$ | token $t$의 key, query, value | key/query는 feature 차원 $d_x$, value는 $d_v$ |
| $\phi(\cdot)$ | key/query feature map | feature 차원 $d_x$ |
| $x_t$ | next-latent 정렬의 write feature | $x_t=\phi(k_{t-1})$ |
| $y_t$ | 새로 관측된 target | $y_t=v_t$ |
| $S_t$ | fast-weight state | $\mathbb{R}^{d_x\times d_v}$ |
| $\eta_t$ | 실제 update step size | $\beta_t/(\|x_t\|_2^2+\lambda_t+\epsilon)$ |
| $\beta_t$ | 정규화 전 dimensionless plasticity gain | 논문 분석에서는 $0<\beta_t<2$ |
| $\lambda_t$ | ridge regularization 및 forgetting 계수 | $\lambda_t\ge 0$ |

### 3.3 상세

- **시간 정렬**: 논문은 read-after-write(RAW)를 쓴다. token $t$가 관측되어 state에 기록된 뒤 $S_t$를 읽어 token $t+1$을 예측한다. 따라서 $v_t$를 쓰는 feature는 $v_t$를 예측할 때 이미 존재했던 $\phi(k_{t-1})$다. 같은 시점 pair $(\phi(k_t),v_t)$도 인과적이지만, 이는 다른 내부 objective를 학습한다 (§3, pp.6–8; Appendix C.5, pp.36–37).

- **온라인 ridge-regression objective**:

  $$\ell_t(S)=\frac{1}{2}\left\|S^\top x_t-y_t\right\|_2^2+\frac{\lambda_t}{2}\|S\|_F^2. \tag{3.1}$$

  state가 현재 write feature에서 target을 얼마나 잘 복원하는지 측정한다. 두 번째 항은 state가 계속 커지는 것을 막고 오래된 정보를 줄이는 역할을 한다.

- **gradient update**:

  $$\nabla_S\ell_t(S)=x_t(S^\top x_t-y_t)^\top+\lambda_tS. \tag{3.2}$$

  residual $r_t=y_t-S_{t-1}^\top x_t$를 쓰면 한 번의 gradient step은 다음이 된다.

  $$S_t=(1-\eta_t\lambda_t)S_{t-1}+\eta_t x_t r_t^\top. \tag{3.3}$$

  **직관**: 기존 state가 틀린 만큼만 $x_t$ 방향에 새 정보를 쓰고, 동시에 전체 state를 조금 줄인다. 그래서 새 정보 반영(plasticity)과 오래된 정보 삭제(forgetting)가 한 식 안에 있다.

- **정규화된 step size**:

  $$\eta_t=\frac{\beta_t}{\|x_t\|_2^2+\lambda_t+\epsilon},\qquad 0<\beta_t<2. \tag{3.4}$$

  입력 feature의 크기가 커졌다고 update가 과도하게 커지지 않도록 분모로 보정한다. 논문은 이 선택이 instantaneous objective에 대해 한 step의 descent를 보장한다고 보인다. 단, 이는 각 시점의 local loss가 줄어든다는 뜻이지 전체 sequence loss가 계속 줄거나 최종 language-model loss가 좋아진다는 뜻은 아니다 (§3.2, pp.7–8).

- **Falcon 변형**:

  - `Falcon-1`: 모든 value channel에 같은 scalar $\eta_t$를 사용한다.
  - `Falcon-2`: value channel마다 다른 $\eta_{j,t}$를 사용한다. write feature와 residual은 공유한다 (§4.2, pp.10–13).
  - `Falcon-3`: 최근 $B$개의 causal pair에 대해 residual을 평균한 sliding-window mini-batch update를 사용한다 (§4.4, pp.19–22).
  - 뒤의 `A`가 붙은 `Falcon-1A/2A/3A`는 regression residual 대신 inner-product objective를 사용한다.

- **Inner-product objective**:

  $$\ell_t^{ip}(S)=-\langle Sx_t,y_t\rangle+\frac{\lambda_t}{2}\|S\|_F^2. \tag{4.5}$$

  gradient step은 대략 $S_t=(1-\eta_t\lambda_t)S_{t-1}+\eta_tx_ty_t^\top$가 된다 (§4.3, pp.14–16). 즉 예측 오차를 빼는 Delta update가 아니라 target을 직접 더하는 additive write다. $\lambda_t=0$이면 유한한 최적점이 없는 선형 objective이므로, 이때 정규화는 최적화 보장보다는 write 크기 안정화로 해석해야 한다 (§4.3, p.14).

- **병렬화**: recurrent scan은 $O(N)$ 시간·고정 state로 동작한다. 같은 recurrence를 causal masked attention으로 풀면 sequence 전체를 병렬 처리할 수 있지만 $O(N^2)$ 계산이 된다. 논문은 chunk 내부를 병렬 계산하고 chunk 사이 state만 전달하는 chunk-parallel 형태를 제시해 두 장점을 절충한다 (§2.2, §4, Figs. 2, 4, pp.3–5, 12–13).

- **수치 안정화**: query/key projection에 RMSNorm을 쓰고, decay factor $\gamma_t=1-\eta_t\lambda_t$가 양수가 되도록 clamp한다. 긴 sequence에서 decay 곱이 underflow하지 않게 log-space로 chunk 내부를 계산한다 (§4.1, Appendix C.1, C.6, pp.9–10, 35, 38).

### 3.4 왜 이 방법이 통한다고 저자는 말하는가

- **저자의 설명**: fast-weight state는 단순 cache가 아니라 stream에서 계속 학습되는 선형 predictor다. 올바른 prefix-aligned pair를 쓰면 state가 실제 예측 시점에 이용 가능했던 정보로 target을 학습하게 된다. NLMS 정규화는 feature scale 변화에 안정적이고, sliding window는 제한된 rehearsal을 제공한다 (§1, §3, §4, pp.1–2, 6–25).
- **그 설명에 대한 판단** `[내 판단]`: local ridge objective에서의 안정성과 산술 외삽 결과는 설명과 일치한다. 그러나 shifted alignment 자체의 효과, window 크기 효과, normalization 효과가 한 실험에서 분리되지 않아 원인까지 입증했다고 보기는 어렵다.

## 4. 실험 설정

| 항목 | 내용 | 위치 |
|---|---|---|
| 데이터셋 | 언어 모델링: FineWeb-Edu. 산술: 1–32자리 덧셈으로 학습, 33–48자리 target suffix로 길이 외삽 평가. | §5.1–5.2, pp.25–28 |
| 태스크·지표 | FineWeb-Edu validation perplexity, WikiText·LMB perplexity, 8개 downstream task zero-shot/one-shot accuracy. 산술은 validation accuracy와 teacher-forced target-suffix accuracy. | §5, Tables 1–3, pp.25–28 |
| 베이스라인 | 124M Transformer with RoPE, RetNet/LightningAttn, Mamba-2, DeltaNet, Gated DeltaNet. | §5.1, Table 1–2, pp.25–27 |
| 모델 규모 | Transformer 124M, recurrent 및 Falcon 계열 130M 전후. | §5.1, Tables 1–2, pp.25–27 |
| 학습 설정 | 100,000 steps, sequence length 1,024, global batch 480, 약 49.2B tokens(본문은 50B budget으로도 표기). | §5.1, p.26 |
| 최적화 | bfloat16, AdamW, tied input/output embeddings, Pre-Norm RMSNorm, no bias/dropout, µP-style width scaling, base LR $10^{-3}$ cosine decay, 2,000 warmup, $(\beta_1,\beta_2)=(0.9,0.95)$, weight decay 0.1, gradient clipping 1.0. | Appendix B.1, p.35 |
| 컴퓨트 | NVIDIA H100 또는 H200 4-GPU node 1개. | Appendix B.1, p.35 |
| 시드·반복 횟수 | 논문에 여러 random seed 반복 평균·표준편차는 보고되지 않음. | §5, Tables 1–3 `[미기재]` |

## 5. 결과 — 주장과 증거의 대응

| 저자 주장 | 근거로 제시된 결과 | 위치 | 그 근거가 주장을 지지하는가 `[내 판단]` |
|---|---|---|---|
| Falcon 계열은 언어 모델링에서 경쟁력 있다. | FineWeb-Edu perplexity: Falcon-1.3 17.10, Gated DeltaNet 17.32, Falcon-1A.3 17.40. | Table 1, §5.1, p.26 | 지지한다. Falcon-1.3은 recurrent baseline 중 가장 낮지만 Transformer 17.38보다도 낮다. 다만 모든 Falcon 변형이 우수한 것은 아니다. |
| Falcon이 downstream task에서도 강하다. | Zero-shot 평균은 Falcon-1A.2 49.30, one-shot에서 recurrent 모델 중 Falcon-1.3 49.54. | Table 2, §5.1, pp.26–27 | 제한적으로 지지한다. one-shot 전체 최고는 Transformer 49.67이므로 “전체 최고”가 아니라 “recurrent 모델 중 최고”다. |
| 제안 update가 길이 외삽에 강하다. | 33–48자리 teacher-forced 평균 정확도: Falcon-3A.3 87.2, Falcon-1A.3 85.9, RetNet 82.9, Transformer 65.8. | Table 3, §5.2, p.28 | 지지한다. 하지만 teacher forcing이므로 모델이 앞에서 틀린 뒤 오류를 누적하는 free-running 생성 성능은 보여주지 않는다. |
| sliding-window inner-product update가 useful하다. | Falcon-3A.3이 Falcon-1A 계열보다 산술 평균 정확도 87.2로 높다. | Table 3, p.28 | 가능성을 보여주지만 window size와 compute를 바꾼 직접적인 sweep이 없어 window 자체의 원인 효과는 분리되지 않는다. |
| chunk-parallel 구현이 효율적이다. | recurrent·masked-parallel·chunk-parallel 수식과 알고리즘을 제시한다. | §2.2, §4.2, §4.4–4.6, pp.3–5, 12–25 | 알고리즘 가능성은 제시하지만 실제 GPU throughput, memory, wall-clock speedup은 실험하지 않았다. |

핵심 수치:

- FineWeb-Edu validation perplexity에서 Falcon-1.3은 17.10, Gated DeltaNet은 17.32, Falcon-1A.3은 17.40이다 (Table 1, p.26).
- Downstream zero-shot 평균은 Falcon-1A.2 49.30이고, one-shot에서는 Transformer 49.67, Falcon-1.3 49.54다 (Table 2, pp.26–27).
- 길이 외삽 산술에서 Falcon-3A.3은 학습 범위 1–32자리를 넘어 33–48자리에서 평균 87.2를 기록했다 (Table 3, p.28).

## 6. Ablation / 분석

| 제거·변경한 것 | 성능 변화 | 위치 | 해석 |
|---|---|---|---|
| QK-$\ell_2$ normalization → QK-RMSNorm | Falcon-1A.2의 FineWeb-Edu 17.70에서 Falcon-1A.3 17.40으로 개선. Zero-shot 평균은 49.30에서 48.95로 낮아지고 one-shot은 49.20에서 48.89로 낮아진다. | Table 1–2, pp.26–27 | perplexity와 downstream accuracy에서 효과 방향이 다르다. 특정 지표 하나로 normalization의 우위를 단정하기 어렵다. |
| context-conditioned $\beta$ → context-conditioned $\eta$ | Falcon-1A.1 대비 Falcon-1A.2에서 zero-shot 평균 48.86→49.30, one-shot 49.08→49.20. FineWeb-Edu는 둘 다 17.70. | Table 1–2, pp.26–27 | learned gain을 실제 normalized step에 직접 조건화하는 것이 downstream에는 유리할 수 있다. |
| inner-product Falcon-1A → regression Falcon-1.3 | FineWeb-Edu 17.40→17.10, arithmetic 평균 85.9(Falcon-1A.3)→68.8(Falcon-1.3). | Tables 1, 3, pp.26, 28 | regression과 inner-product objective가 태스크별로 다르게 작동한다. 제안 family 전체에 단일한 우열은 없다. |
| Falcon-1A → Falcon-3A sliding window | arithmetic 평균 85.9→87.2, d48 정확도 69→69. | Table 3, p.28 | 평균 외삽은 좋아졌지만 가장 긴 길이의 수치는 같아, 모든 길이에서 개선됐다고 말할 수 없다. |

- **빠진 ablation `[내 판단]`**:
  1. shifted pair $(\phi(k_{t-1}),v_t)$와 same-step pair $(\phi(k_t),v_t)$의 직접 비교;
  2. RAW와 RBW timing의 2×2 조합별 성능 비교;
  3. Falcon-3의 window size $B$ sweep;
  4. QK normalization, short convolution, decay, gain conditioning을 한 번에 하나씩 제거한 통제 실험;
  5. chunk-parallel과 recurrent implementation의 수치·속도 일치 검증.

## 7. 한계와 비판

**저자가 밝힌 한계**:

- 논문은 산술 실험을 primary result가 아닌 controlled supporting evidence로 규정한다 (§5.2, p.28).
- signed feature를 쓰는 normalized linear-attention read는 denominator가 0 또는 음수가 될 수 있어 주의가 필요하다고 설명한다 (Appendix C.2, p.35).
- $\lambda_t=0$인 inner-product objective는 아래로 유계가 아니므로 descent guarantee가 아니라 magnitude stabilization으로 해석해야 한다 (§4.3, p.14).

**내가 보는 문제** — 각 항목은 “무엇이 문제인지 + 그래서 어떤 주장이 흔들리는지” 형태로:

- **[방법] 핵심 정렬 가설을 직접 검증하지 않았다**: 논문의 중심 주장은 prefix-aligned write가 올바른 내부 objective라는 것인데, 결과 표에는 shifted/unshifted pair를 같은 조건에서 비교한 실험이 없다. 따라서 이론적 정합성과 실제 성능 향상을 구분해야 한다.
- **[실험] 긴 문맥 효율성을 직접 측정하지 않았다**: 논문은 $O(N)$ recurrent 및 chunk-parallel 계산을 제시하지만, 주된 LM 학습 sequence length는 1,024다 (§5.1, p.26). 길이별 throughput, peak memory, decoding latency를 보고하지 않아 “긴 문맥에서 효율적”이라는 시스템 주장이 정량적으로 비어 있다.
- **[실험] 산술 성능이 teacher-forced다**: 33–48자리 결과는 target suffix의 gold prefix를 제공하는 방식이다 (§5.2, p.28). 실제 autoregressive 생성처럼 앞자리 오류를 다음 입력에 다시 넣었을 때도 87.2가 유지되는지는 알 수 없다 `[내 판단]`.
- **[실험] Falcon family의 검증 범위가 좁다**: Falcon-2·2A·3 regression은 정의되어 있지만 main table에서 별도로 benchmark하지 않는다 (§5, p.25). 대표 variant 몇 개의 결과로 전체 계열의 우수성을 일반화할 수 없다.
- **[실험] 통계적 안정성 정보가 없다**: LM 결과에 여러 seed의 평균·표준편차, confidence interval, 유의성 검정이 보고되지 않았다. 작은 perplexity 차이 17.10 대 17.32가 seed에 대해 안정적인지는 `[확인 필요]`다.
- **[방법] decay clamp는 이론 update와 실제 update를 다르게 만들 수 있다**: $\gamma_t$가 양수가 되도록 clamp하면 unclamped ridge gradient step과 같은 update가 아닐 수 있다 (Appendix C.6, p.38). 따라서 local descent 보장이 실제 구현 전체에 그대로 적용된다고 읽으면 안 된다.
- **[일반화] 하나의 모델 크기·하나의 텍스트 학습 조건**: 124M–130M 모델과 FineWeb-Edu 50B-token 조건만 평가했다 (§5.1, pp.25–27). 큰 모델, 다른 데이터 분포, 실제 수백만 token context에서의 동작은 확인되지 않았다.
- **[서술] continual learning의 의미가 제한적이다**: state가 token stream에서 online update되는 것은 continual learning 관점으로 볼 수 있지만, task 전환·분포 변화·catastrophic forgetting을 독립적인 continual-learning benchmark로 측정하지는 않았다 `[내 판단]`.

## 8. 재현성 체크

| 항목 | 상태 | 비고 |
|---|---|---|
| 코드 공개 | ☑ 예 ☐ 아니오 | [공식 GitHub 프로젝트](https://github.com/yifanzhang-pro/fast-weight-attention) 링크가 arXiv와 저장소에 있음 |
| 학습 데이터 접근 가능 | ☑ 예 ☐ 아니오 | FineWeb-Edu는 공개 데이터셋으로 명시되지만, 정확한 전처리·샘플링은 추가 확인 필요 |
| 체크포인트 공개 | ☐ 예 ☑ 아니오 | 공개 여부를 이 정독에서 확인하지 못함 `[확인 필요]` |
| 하이퍼파라미터 전부 명시 | ☐ 예 ☑ 아니오 | 주요 optimizer·token budget은 있으나 Falcon별 gain/decay·short convolution·chunk size 등 전체 설정은 분산되어 있거나 미기재 |
| 컴퓨트 요구량 명시 | ☑ 예 ☐ 아니오 | H100/H200 4-GPU node 명시. 실제 총 학습 시간·전력·memory는 미기재 |
| 결과에 분산·시드 보고 | ☐ 예 ☑ 아니오 | 반복 수와 seed별 분산 미기재 |

내가 재현한다면 가장 막힐 지점:

1. Falcon별 context-conditioned $\beta,\eta,\lambda$ 생성 방식과 short convolution의 정확한 구현을 맞추기 어렵다.
2. shifted boundary $x_1=0$, decay clamp, log-space renormalization을 recurrent·chunk-parallel 코드에서 동일하게 구현해야 한다.
3. 논문 표의 모델별 결과를 만들려면 공개 checkpoint와 exact data pipeline이 필요하지만, checkpoint 접근성은 확인되지 않았다.

## 9. 관련 연구 속 위치

- **직접 기반한 연구**: `Linear Transformers Are Secretly Fast Weight Programmers` (ICML 2021) — Delta Network의 fast-weight·gradient-update 관점을 계승한다 (Reference [30], p.30).
- **경쟁·대안 접근**: `Mamba-2`의 Structured State Space Duality, `RetNet`, `Gated Delta Networks`, `RWKV`, `Kimi Linear` — recurrent state와 linear attention을 효율적으로 구현하는 대안이다 (§2, §6, pp.3–5, 28–30).
- **내부 학습 관점**: `Titans`, `ATLAS`, `Test-Time Training`, `MesaNet` — state 또는 일부 parameter를 stream에서 내부 objective로 업데이트한다 (§3, §6, Appendix C.4, pp.6–8, 30, 36).
- **이 논문 이후**: arXiv 제출 직후의 후속 연구·인용 관계는 이 정독에서 조사하지 않았으므로 `[확인 필요]`.

한 줄 위치 규정: `Fast Weight Attention for Continual Learning`은 새로운 거대 모델을 제시하기보다, linear attention/DeltaNet류의 recurrent state update를 “prefix를 보고 다음 target을 맞추는 온라인 회귀”로 재정의하고 그에 맞는 정규화·병렬화 family를 제안한 논문이다. 가장 설득력 있는 결과는 길이 외삽 산술이고, 가장 비어 있는 검증은 정렬 가설과 실제 긴 문맥 시스템 효율성이다 `[내 판단]`.

## 10. 시사점과 후속 아이디어

- **내 작업에 쓸 수 있는 것**: recurrent memory를 설계할 때 “무엇을 저장할까”뿐 아니라 “그 정보가 예측 시점에 이미 보였는가”를 명시해야 한다. state update를 내부 loss의 gradient step으로 쓰면 plasticity·forgetting을 분리해 설계할 수 있다 `[내 의견]`.
- **이 논문이 열어 둔 질문**: 실제 장기 대화나 agent memory에서 shifted write가 retrieval 품질을 높이는가? sliding window가 stale memory를 줄이지만 유용한 장기 정보를 얼마나 잃는가?
- **해볼 만한 실험 `[내 의견]`**:
  1. 같은 130M backbone에서 shifted/unshifted × RAW/RBW 2×2를 비교한다.
  2. 1k, 4k, 16k, 64k sequence length에서 perplexity·tokens/s·peak memory·decode latency를 함께 측정한다.
  3. teacher-forced와 free-running variable-digit addition을 모두 평가한다.
  4. task distribution이 바뀌는 continual-learning stream에서 Falcon-1/2/3의 forgetting과 recovery를 측정한다.

## 11. 미해결 질문

1. shifted alignment가 unshifted alignment보다 좋아지는 실험 수치가 어디에 있는가? Appendix의 2×2 pairing 도식만으로는 판단할 수 없다.
2. main table의 각 Falcon variant에서 context-conditioned $\beta,\eta,\lambda$가 어떤 네트워크와 초기값으로 생성되는가?
3. chunk-parallel 구현과 recurrent 구현의 출력이 decay clamp·finite precision에서도 어느 오차 범위로 일치하는가?
4. arithmetic 87.2%가 free-running 생성에서도 유지되는가?
5. 공개 GitHub 코드에 논문 표의 모든 variant와 정확한 학습 설정·checkpoint가 포함되어 있는가?

## 12. 인용

```bibtex
@misc{zhang2026fast,
  title = {Fast Weight Attention for Continual Learning},
  author = {Yifan Zhang and Steve Ta and Jasper Zhang and Jichen Feng and Shuzhen Li and Yongxin Zhang and Yifeng Liu and Huizhuo Yuan and Mengdi Wang and Quanquan Gu and Andrew Chi-Chih Yao},
  year = {2026},
  eprint = {2608.27763},
  archivePrefix = {arXiv},
  primaryClass = {cs.LG},
  url = {https://arxiv.org/abs/2608.27763}
}
```

---
*리뷰 작성: 2026-09-04 · 읽은 범위: PDF pp.1–30 전체 본문·References 및 Appendix B.1, C.1–C.6(pp.35–38); 나머지 부록의 구현 세부는 미정독*
