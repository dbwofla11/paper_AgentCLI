---
title: "CSI-Bench: A Large-Scale In-the-Wild Dataset for Multi-task WiFi Sensing"
authors: ["Zhu, Guozhen", "Hu, Yuqian", "Gao, Weihang", "Wang, Wei-Hsiang", "Wang, Beibei", "Liu, K. J. Ray"]
venue: "Advances in Neural Information Processing Systems 38 (NeurIPS 2025), Datasets and Benchmarks Track"
year: 2025
arxiv: "2505.21866"
doi: "10.52202/085713-5648"
code: "https://github.com/guozhen-jenn-zhu/CSI-Bench-Real-WiFi-Sensing-Benchmark"
pdf: "papers/2025-zhu-csi-bench-wifi-sensing.pdf"
read_date: 2026-09-07
rating: 4
tags: [WiFi CSI, dataset, multi-task learning, domain generalization, wireless sensing]
status: 완료
---

# CSI-Bench: A Large-Scale In-the-Wild Dataset for Multi-task WiFi Sensing

> **TL;DR** — `CSI-Bench`는 26개 실내 환경, 35명 사용자, 16종 상용 WiFi edge device에서 461시간 이상의 Channel State Information(CSI)을 수집하고, 7개 분류 태스크와 표준 split·baseline을 제공하는 benchmark다 (§1, Table 2, pp.1–7). 데이터 다양성과 OOD 평가를 갖춘 점은 강하지만, multi-task 성능 향상은 Transformer 하나의 비교에 의존하고, cross-user·cross-environment·cross-device 분할이 각각 한정된 도메인만 홀드아웃하므로 “현실 배포에 일반화한다”는 주장은 아직 데이터셋이 제시한 문제 정의보다 좁은 실험으로만 뒷받침된다.

## 1. 문제와 동기

- **풀려는 문제**: 통제된 실험실과 단일 하드웨어에 의존하는 기존 WiFi sensing dataset의 한계를 넘어, 사용자·환경·장치가 바뀌는 실제 실내 조건에서 학습·평가할 수 있는 대규모 benchmark를 만드는 문제다 (§1–2.2, pp.1–3).
- **기존 방식의 무엇이 부족한가**: 저자들은 기존 데이터셋이 homogeneous hardware, 사전 정의된 짧은 session, single-task 설정에 치우쳐 새로운 사용자·장치·환경으로 일반화하기 어렵다고 진단한다. 특히 Intel 5300 기반 데이터는 continuous CSI recording을 지원하지 않아 자연스러운 일상 활동을 충분히 담기 어렵다고 주장한다 (§2.2, p.3, Table 1).
- **그 진단에 동의하는가** `[내 의견]`: 데이터셋의 가장 중요한 축을 모델 정확도가 아니라 domain shift로 잡은 것은 타당하다. 다만 “in-the-wild”라는 수집 환경의 현실성만으로 학습·테스트가 도메인 독립적이 되지는 않는다. 실제 split이 session·사용자 단위로 완전히 분리되는지까지 공개되어야 진단과 평가가 연결된다.

## 2. 핵심 기여

논문이 스스로 주장하는 기여를 먼저 적고, 각각이 실제로 새로운지 판정한다.

| # | 저자 주장 기여 | 위치 | 실제로 새로운가 `[내 판단]` |
|---|---|---|---|
| 1 | 461시간 이상, 35명 사용자, 26개 환경, 16종 device type을 포함하는 large-scale in-the-wild CSI dataset을 제공한다. | §1, §3.1, Appendix A.1–A.3, pp.1, 3–4, 17–19 | WiFi sensing에서 여러 chipset과 생활 환경을 한 benchmark에 묶은 점은 실질적으로 새롭다. 다만 “가장 큰 데이터셋”이라는 표현은 비교 표의 범위와 정의에 의존한다. |
| 2 | fall, breathing, localization, motion source recognition의 single-task dataset과 activity·user·proximity의 co-labeled multi-task dataset을 제공한다. | §3.1, §5.1, Table 2, pp.3, 5, 7 | 단일 태스크 데이터의 단순 합보다 co-labeled multi-task 설계가 유용한 기여다. 그러나 태스크별 사용자·환경 범위가 크게 다르므로 하나의 균질한 benchmark로 해석하면 안 된다. |
| 3 | 70/15/15 split, Easy/Medium/Hard tier, cross-user·cross-environment·cross-device OOD split과 baseline을 표준화한다. | §5.2, Appendix A, pp.7, 17–21 | 평가 프로토콜을 함께 배포한 점은 benchmark 기여로 타당하다. 다만 OOD 홀드아웃의 수가 적어 domain generalization의 통계적 범위를 충분히 대표하지는 않는다. |
| 4 | shared Transformer와 task-specific adapter를 사용하면 task-specific training보다 성능과 parameter efficiency가 좋아진다. | §5.3–5.5, Tables 4–5, pp.7–9 | multi-task 비교는 흥미롭지만 Transformer 한 backbone의 한 비교다. adapter·shared backbone·학습 샘플 구성의 독립 기여가 분리되지 않아 일반적인 방법론 기여로 확대하기 어렵다. |

## 3. 방법 (Method)

### 3.1 한 문단 개요

CSI-Bench는 5개 chipset vendor의 상용 WiFi router와 edge IoT device에서 CSI를 수집하고, timestamp·amplitude·dropout 품질 검사를 거친 뒤 amplitude-only CSI를 고정 길이 tensor로 변환한다. 대부분의 태스크는 5초 non-overlapping window, breathing은 10초 window를 사용하며, subcarrier 수가 다른 장치는 zero-padding 또는 clipping으로 표준화한다 (§3.2–4.2, pp.3–7). 입력은 $\mathbf{X}\in\mathbb{R}^{C\times K\times T}$이고 출력은 태스크별 class다. baseline은 MLP, Bi-LSTM, ResNet-18, ViT, Transformer, PatchTST, TimeSformer-1D이며, multi-task 실험에서는 shared backbone 위에 task-specific LoRA adapter·bottleneck adapter·classification head를 붙인다 (§5.1–5.3, Appendix B.1–B.2, pp.7–8, 21–22).

### 3.2 표기와 정의

| 기호 | 의미 | 형태/차원 |
|---|---|---|
| $H(f,t)$ | 시간 $t$, subcarrier frequency $f$의 복소 CSI | device에 따라 subcarrier·antenna 수가 다름 (§3.2, p.4) |
| $|H(f,t)|$ | phase를 제거한 CSI amplitude 입력 | raw CSI에서 amplitude로 변환 (§4.2, p.6) |
| $\hat H(f_k,t)$ | sample 전체 평균·표준편차로 정규화한 amplitude | $\hat H(f_k,t)=\frac{H(f_k,t)-\mu_H}{\sigma_H+\epsilon}$ (§4.2, p.7) |
| $\mathbf{X}$ | 모델 입력 CSI tensor | $\mathbb{R}^{C\times K\times T}$; 대부분 5초, breathing 10초 (§5.1, p.7) |
| $C,K,T$ | channel 수, 표준화한 subcarrier 차원, 시간 길이 | device별 입력을 zero-padding/clipping으로 맞춤 (§4.2, p.7) |

### 3.3 상세

- **수집과 동기화**: IoT client가 일반 sensing에는 100 Hz, breathing에는 30 Hz로 CSI packet을 전송한다. router가 정해진 시간 창을 batch request로 요청하고, 각 device의 system-clock timestamp를 사용해 software에서 stream을 정렬한다 (§3.2, p.4).

- **품질 검증**: timestamp irregularity, unstable 또는 flat amplitude, signal dropout이 있는 sample을 필터링한다. 검증 도구는 MATLAB으로 구현되며, device별 sampling interval·time–subcarrier heatmap·amplitude response를 확인한다 (§4.1, pp.5–6, Fig. 3).

- **전처리**: phase instability를 이유로 phase cleaning 대신 phase elimination을 선택한다. 이후 5초 또는 10초의 고정 길이·non-overlapping sample로 자르고, sample 전체 subcarrier·time 축의 평균과 표준편차로 amplitude를 정규화한다. 하드웨어별 subcarrier 차이는 fixed dimension에 맞춰 zero-padding 또는 clipping한다 (§4.2, pp.6–7).

- **태스크 구성**:
  - single-task: Fall Detection 2-class, Breath Detection 2-class, Motion Source Recognition 4-class, Room-level Localization 6-class.
  - multi-task: Human Activity Recognition 5-class, User Identification 6-class, Proximity Recognition 4-class. 세 태스크는 같은 multi-task sample에 공동 label을 가진다 (§5.1, Table 2, p.7).

- **multi-task 모델**: shared backbone에 task별 LoRA adapter(rank $=8$, $\alpha=32$, dropout $=0.05$), residual two-layer bottleneck adapter, classification head를 둔다. 한 번에 하나의 task를 활성화해 shared backbone과 해당 task의 adapter·head를 업데이트한다 (Appendix B.2, p.22). 논문은 task별 loss의 구체적인 weighting 또는 task sampling 비율은 명시하지 않는다 `[미기재]`.

- **학습 목표와 절차**: 모든 모델은 categorical cross-entropy를 사용하고, AdamW·batch size 128·초기 learning rate $10^{-3}$·cosine decay·5 warm-up epoch·weight decay $10^{-5}$를 적용한다. 최대 100 epoch, validation loss 기준 patience 15 early stopping이며, validation accuracy로 hyperparameter를 조정한다 (Appendix B.3, p.23). NVIDIA RTX 4090과 AWS SageMaker `ml.g5.12xlarge`를 사용하고, 세 random seed로 학습한다 (Appendix B.3, p.23).

- **추론·평가 절차**: accuracy와 class-frequency weighted F1을 보고한다. 기본 split은 70% train, 15% validation, 15% test이며 class balance와 environment distribution을 보존한다고 설명한다. single-task test는 Easy/Medium/Hard, multi-task test는 cross-user·cross-environment·cross-device OOD split으로 나눈다 (§5.1–5.2, p.7).

### 3.4 왜 이 방법이 통한다고 저자는 말하는가

- **저자의 설명**: 여러 장치·환경에서 수집한 CSI와 co-labeled task를 공유하면 task 간 공통 표현을 학습하고, adapter로 task-specific specialization을 유지하면서 edge deployment에 필요한 parameter 수와 training cost를 줄일 수 있다고 설명한다 (§1, §5.3–5.6, pp.2, 7–9).
- **그 설명이 실험으로 검증되는가** `[내 판단]`: Table 4는 HAR와 proximity의 in-distribution 성능 향상과 Table 5는 OOD 하락을 동시에 보여주므로 “multi-task가 일부 seen-domain 태스크를 돕지만 domain shift를 해결하지는 못한다”는 해석은 지지한다. 반면 parameter 감소가 실제 inference latency·peak memory·energy 감소로 이어지는지는 측정하지 않았으므로 edge deployment 적합성은 부분적으로만 검증됐다.

## 4. 실험 설정

| 항목 | 내용 | 위치 |
|---|---|---|
| 데이터셋 | 전체 461시간 이상, 35명 사용자, 26개 환경, 16종 device type. Table 2 기준 Fall 6.7k, Breath 100k, Motion Source 60.9k, Localization 7.1k, Proximity 20.3k, HAR 41.5k, UID 20.3k samples. | §3.1, Table 2, Appendix A.4, pp.3, 5, 17–18 |
| 태스크·지표 | 7개 supervised classification task; accuracy와 weighted F1. | §5.1, p.7 |
| 베이스라인 | MLP, Bi-LSTM, ResNet-18, ViT, Transformer, PatchTST, TimeSformer-1D. multi-task는 shared Transformer와 task-specific adapter 비교. | §5.3, Appendix B.1–B.2, pp.7–8, 21–22 |
| 모델 규모 | MLP 3-layer, Bi-LSTM 2-layer·hidden 256, ViT 6-layer·dim 128·4 heads, Transformer 4-layer·dim 256·8 heads, PatchTST 4-layer·dim 128·4 heads, TimeSformer-1D 4-layer·dim 128·8 heads. | Appendix B.1, pp.21–22 |
| 하이퍼파라미터 | batch 128, AdamW, initial LR $10^{-3}$, cosine decay, warm-up 5 epoch, weight decay $10^{-5}$, 최대 100 epoch, patience 15. LoRA rank 8, $\alpha=32$, dropout 0.05. | Appendix B.2–B.3, pp.22–23 |
| 컴퓨트·학습 시간 | RTX 4090 및 AWS `ml.g5.12xlarge`(A10G 4개); 태스크별 학습 시간 0.5–13시간. multi-task가 separate model 대비 wall-clock training time을 nearly 3× 줄였다고 보고한다. | §5.4, Appendix B.3, pp.8, 23 |
| 시드·반복 횟수 | Tables 3–5의 평균±표준편차는 세 random seed 기준이다. seed 값 자체는 미기재. | §5.3, Tables 3–5, pp.7–9; Appendix B.3, p.23 |
| OOD split | multi-task dataset에서 cross-user는 U02, cross-environment는 E05, cross-device는 Amazon Plug와 Echo Spot을 hold-out한다. | Appendix A.9, p.21 |

## 5. 결과 — 주장과 증거의 대응

| 저자 주장 | 근거로 제시된 결과 | 위치 | 그 근거가 주장을 지지하는가 `[내 판단]` |
|---|---|---|---|
| CSI-Bench가 기존 데이터셋보다 규모·장치·환경·태스크 다양성이 크다. | Table 1은 CSI-Bench를 16 device type, 231.6k samples, 7 tasks, 26 environments, 35 users, in-the-wild로 정리한다. | Table 1, p.3 | 비교 기준에서 지지된다. 단, “largest available”은 표에 포함한 데이터셋과 sample-count 정의에 한정해 읽어야 한다. |
| standard supervised baseline은 네 single-task에서 높은 성능을 낸다. | 최고 F1은 Fall 94.92(ResNet-18/LSTM 근접), Breath 98.84(PatchTST), Localization 100.00(ResNet-18/TimeSformer-1D), Motion Source 98.86(PatchTST)다. | Table 3, p.8 | seen-domain benchmark 성능은 지지하지만, 일부 태스크가 매우 쉽게 분리되는지와 domain-independent 성능은 별도 문제다. |
| multi-task learning이 task-specific training보다 좋다. | HAR는 accuracy 75.40→88.06, weighted F1 75.49→86.00; Proximity는 accuracy 77.52→86.41, F1 77.35→87.09; UID 증가는 accuracy 99.51→99.55에 그친다. | Table 4, §5.4, p.8 | HAR·Proximity에서는 지지되지만 UID에는 거의 변화가 없다. 또한 adapter와 shared backbone의 효과를 분리한 실험은 아니다. |
| multi-task 모델은 edge deployment에 효율적이다. | 세 개의 Transformer를 하나의 shared backbone과 task-specific adapter로 통합해 parameter count를 60% 이상 줄이고 training wall-clock time을 nearly 3× 줄였다고 보고한다. | §5.4, p.9 | parameter 수와 학습 시간에는 근거가 있다. 하지만 inference latency·memory·energy를 측정하지 않아 “deployment cost” 전체를 검증한 것은 아니다. |
| CSI-Bench가 현실적 domain shift를 드러낸다. | Transformer OOD 성능: HAR F1이 cross-device 57.80, cross-environment 47.17, cross-user 46.67; Proximity F1은 각각 28.76, 27.12, 25.97이다. | Table 5, §5.5, p.9 | 강하게 지지한다. 이 논문의 가장 설득력 있는 결과는 높은 평균 정확도보다 이 하락 폭이다. |

핵심 수치:

- Multi-task joint training의 HAR F1은 task-specific 대비 $+10.51$ percentage points, Proximity는 $+9.74$ points지만 UID는 $+0.19$ points다 (Table 4, p.8).
- Fall Detection은 Easy F1 약 97%에서 Hard F1 61.19–68.08 범위로 하락한다. ResNet-18이 Hard F1 68.08로 가장 높지만, TimeSformer-1D의 표준편차는 17.16으로 크다 (Appendix C.1, Table 9, p.23).
- Proximity OOD에서는 최고 모델 ViT도 F1 26.94–30.11 수준이다 (Appendix C.2, Table 15, p.26). 네 class의 균등 무작위 기준이 약 25%라는 점을 감안하면, 이 결과는 실사용 가능한 proximity estimation과 거리가 있다 `[내 판단]`.

## 6. Ablation / 분석

| 제거·변경한 것 | 성능 변화 | 위치 | 해석 |
|---|---|---|---|
| task-specific training → multi-task joint training | HAR와 Proximity는 크게 향상, UID는 거의 동일 | Table 4, p.8 | 공동 label이 task 간 표현 공유에 도움을 줄 가능성은 보이지만, adapter 구조 자체의 효과는 분리되지 않는다. |
| in-distribution → cross-device/cross-env/cross-user | HAR와 Proximity 성능이 크게 하락 | Table 5, p.9; Tables 13–15, pp.25–26 | dataset의 현실적 난이도와 domain shift를 보여주는 분석이다. |
| Easy → Medium → Hard | Fall Detection은 Hard에서 약 61–68 F1로 하락; Breath와 Localization은 상대적으로 높음 | Appendix C.1, Tables 9–12, pp.23–24 | 태스크별 난이도와 신호 품질 영향이 다름을 보인다. |

- **빠진 ablation `[내 판단]`**:
  1. shared backbone만, LoRA만, bottleneck adapter만, 둘 다 사용하는 경우를 분리하지 않았다.
  2. multi-task loss weight와 task sampling 비율을 바꿔본 결과가 없다.
  3. amplitude-only 선택과 phase-cleaning 또는 calibrated phase의 비교가 없다.
  4. zero-padding과 clipping이 device generalization에 미치는 영향을 분석하지 않았다.
  5. sample-level random split과 session/user/environment-grouped split의 차이를 보여주지 않았다.
  6. parameter count 감소가 실제 inference time·peak memory·energy로 이어지는지 측정하지 않았다.

## 7. 한계와 비판

**저자가 인정한 한계** (§6, p.9):

- 플랫폼 간 phase instability 때문에 amplitude-only CSI를 사용해 calibrated phase와 angle-of-arrival 정보를 다루지 못한다.
- 현재 benchmark가 classification 중심이라 continuous regression, 예를 들면 continuous sign estimation, 과 long-term activity tracking을 포함하지 않는다.

**내가 보는 문제** — 각 항목은 “무엇이 문제인지 + 그래서 어떤 주장이 흔들리는지” 형태로:

- **[방법] 하드웨어 표준화가 domain signal을 보존한다**: subcarrier 수가 다른 CSI를 fixed dimension에 zero-padding 또는 clipping하고, sample 내부에서 정규화한다 (§4.2, p.7). 이 전처리는 입력을 통일하지만 device-specific structure를 제거하거나 보존하는 방식이 명확하지 않다. 특히 device shift에서 성능이 낮은 이유가 모델의 표현력인지 전처리의 정보 손실인지 분리할 수 없다.
- **[실험] multi-task 향상의 원인을 분리하지 못한다**: Table 4는 Transformer task-specific과 joint training만 비교한다. shared backbone, LoRA, bottleneck adapter, task sampling, 공동 데이터의 상관 구조를 각각 제거한 조건이 없으므로 “adapter 기반 multi-task가 효과적”이라는 결론은 “이 하나의 joint training recipe가 이 데이터에서 효과적”보다 강하게 말하기 어렵다.
- **[실험] OOD 표본의 domain 수가 작다**: Appendix A.9에서 cross-user는 U02 한 명, cross-environment는 E05 한 곳, cross-device는 Amazon Plug와 Echo Spot으로 정의된다 (§A.9, p.21). 이 설정은 명확하지만, 한 사용자·한 환경·두 장치에 대한 holdout 결과를 새로운 사용자·환경·장치 전체의 일반화율로 해석할 수는 없다.
- **[실험] in-distribution split의 독립성이 불명확하다**: 5초 non-overlapping window와 70/15/15 split은 제시되지만, train/validation/test가 session·사용자·시간 구간 단위로 그룹 분리되었는지는 명시되지 않는다 (§3.3, §4.2, §5.2, pp.4, 6–7). 연속 기록에서 인접 window가 다른 split에 섞였다면 Table 3·4 성능이 실제 새로운 session 성능보다 높을 수 있다 `[확인 필요]`.
- **[일반화] 태스크별 수집 범위가 비대칭이다**: Breath는 3명·3환경, multi-task는 6명·6환경, Fall은 17명·6환경이다 (Table 2, Appendix A.4–A.9, pp.5, 17–21). 35명·26환경이라는 전체 수치가 모든 태스크의 일반화를 의미하지 않으므로, 각 태스크의 사용자·환경 수를 기준으로 결론을 제한해야 한다.
- **[일반화] “in-the-wild”와 label protocol 사이에 긴장이 있다**: 사용자가 Google Spreadsheet에서 활동 시작·종료를 누르는 방식이고, 일부 활동 label은 optional이다 (Appendix A.10, p.21). 자연스러운 환경에서 수집했다는 장점은 있지만, label 누락·반응 지연·활동 경계 오차가 class별로 다를 가능성을 정량화하지 않았다.
- **[서술] edge deployment 주장이 측정 범위를 넘는다**: parameter count와 training time은 보고하지만, inference latency, peak RAM, energy, packet loss 상황의 online performance는 보고하지 않는다 (§5.4, Appendix B.3, pp.9, 23). 따라서 “resource-constrained edge에 적합”은 가능성에 대한 주장이지 배포 조건의 직접 검증은 아니다.
- **[재현성] 논문 버전과 현재 공개 배포물의 버전 차이를 확인해야 한다**: 공개 코드 저장소 README는 dataset과 code가 “previously identified data issues”를 수정하도록 업데이트되었고, 최신 Kaggle Version 12로 benchmark를 재실행했다고 적는다 ([공개 코드 저장소 README](https://github.com/guozhen-jenn-zhu/CSI-Bench-Real-WiFi-Sensing-Benchmark#overview), 확인일 2026-09-07). 따라서 논문 Table 3–5 수치와 현재 다운로드 가능한 데이터·코드의 결과가 동일한지 별도 검증이 필요하다 `[확인 필요]`.
- **[사회적 영향] privacy와 user identification의 긴장을 검증하지 않는다**: 논문은 consent·anonymization과 privacy-preserving 활용을 강조하지만 (§3.5, §7, pp.5, 10), 공개 CSI에서 사용자 재식별 위험이나 공격 가능성을 평가하지 않는다. User Identification 태스크와 proximity·activity 데이터가 공개될 때의 privacy–utility trade-off는 긍정적 impact 서술만으로 해소되지 않는다 `[내 의견]`.

## 8. 재현성 체크

| 항목 | 상태 | 비고 |
|---|---|---|
| 코드 공개 | ☑ 예 ☐ 아니오 | 논문 abstract의 GitHub 링크와 공개 저장소가 있다. |
| 학습 데이터 접근 가능 | ☑ 예 ☐ 아니오 | 논문은 Kaggle dataset 링크를 제공한다. 다만 현재 저장소 README가 data issue 수정과 Kaggle Version 12 재실행을 언급하므로 논문 수치와 버전 정합성을 확인해야 한다. |
| 체크포인트 공개 | ☐ 예 ☑ 아니오 | 논문과 저장소 README에서 benchmark checkpoint 공개 여부를 확인하지 못했다 `[확인 필요]`. |
| 하이퍼파라미터 전부 명시 | ☐ 예 ☑ 아니오 | 주요 optimizer·LR·batch·schedule·architecture는 명시하지만 task sampling, loss weighting, 정확한 input mapping과 일부 split 생성 세부는 미기재다. |
| 컴퓨트 요구량 명시 | ☑ 예 ☐ 아니오 | RTX 4090, SageMaker `ml.g5.12xlarge`, task별 0.5–13시간을 명시한다. GPU memory·inference cost는 미기재다. |
| 결과에 분산·시드 보고 | ☑ 예 ☐ 아니오 | 세 random seed의 mean±std를 보고하지만 seed 값은 미기재다. |

내가 재현한다면 가장 막힐 지점:

1. 최신 공개 데이터 버전과 논문 PDF가 사용한 데이터 버전이 다를 수 있다.
2. 70/15/15 in-distribution split이 session·시간·사용자 단위로 어떻게 생성됐는지 확인해야 한다.
3. multi-task task sampling·loss weighting·adapter 적용 위치를 코드와 대조해야 한다.
4. amplitude normalization과 subcarrier padding/clipping의 실제 구현이 본문 수식과 같은지 확인해야 한다.

## 9. 관련 연구 속 위치

- **직접 기반한 연구**: `Widar3.0`, `MM-Fi`, `XRF55`, `WiMANs` 등 WiFi/RF sensing dataset을 Table 1에서 비교한다. CSI-Bench는 이 계열의 single-task·controlled dataset을 여러 장치와 in-the-wild 환경·multi-task label로 확장한다 (§2.2, Table 1, pp.2–3).
- **경쟁·대안 접근**: Intel 5300 기반의 기존 CSI dataset은 장치가 균일하지만, CSI-Bench는 상용 edge device의 heterogeneous CSI와 continuous recording을 선택한다 (§2.2–3.2, pp.3–4).
- **방법 기반**: `Multitask learning`과 `LoRA`를 shared backbone·task-specific adapter 설계에 사용한다 (§5.3, Appendix B.2, pp.7–8, 22).
- **이 논문 이후**: 현재 공개 저장소 README에는 data issue를 수정한 최신 release와 재실행 결과가 언급되지만, 이 리뷰에서는 그 변경의 원인·차이·독립 검증까지 추적하지 않았다 `[확인 필요]`.

한 줄 위치 규정: `CSI-Bench`는 새 sensing model보다 “현실적 domain shift를 숨기지 않는 WiFi CSI benchmark”로서 가치가 큰 논문이다. Table 4의 multi-task 개선보다 Table 5의 OOD 붕괴가 이 데이터셋이 후속 연구에 던지는 핵심 과제다.

## 10. 시사점과 후속 아이디어

- **내 작업에 쓸 수 있는 것**: WiFi CSI 모델을 평가할 때 평균 accuracy 하나보다 device·environment·user를 명시적으로 holdout하고, in-distribution과 OOD를 분리해 보고해야 한다. 또한 multi-task 학습을 도입할 때 parameter 수뿐 아니라 inference latency와 memory를 함께 측정해야 한다 `[내 의견]`.
- **이 논문이 열어 둔 질문**:
  1. amplitude-only CSI의 OOD 붕괴가 phase 손실 때문인가, device-specific calibration 차이 때문인가?
  2. 서로 다른 task의 공동 label이 실제 공통 물리 표현을 학습하게 하는가, 아니면 특정 사용자·환경 shortcut을 공유하게 하는가?
  3. 공개 CSI에서 user identification을 수행하면서 privacy를 보장할 수 있는가?
- **해볼 만한 실험 `[내 의견]`**:
  1. 사용자·환경·session을 동시에 group holdout한 nested split을 구성하고, 현재 결과와 leakage 가능성을 비교한다.
  2. amplitude-only, phase-cleaned, calibrated phase, device-invariant normalization을 비교한다.
  3. shared backbone, LoRA, bottleneck adapter, loss weighting을 factorial ablation으로 분해한다.
  4. device metadata를 가린 상태와 제공한 상태를 비교해 모델이 activity가 아니라 device identity를 shortcut으로 쓰는지 검사한다.
  5. OOD에서 calibration 없이 동작하는 domain generalization·test-time adaptation 방법을 평가한다.
  6. inference latency·RAM·energy와 privacy attack 성능을 함께 측정해 edge utility와 privacy를 Pareto frontier로 제시한다.

## 11. 미해결 질문

1. 논문의 70/15/15 split은 raw recording 또는 session 단위로 group split되었는가? 아니면 5초 sample 단위인가?
2. Appendix A.9의 U02, E05, Amazon Plug/Echo Spot holdout을 선택한 이유와, 여러 가능한 holdout 중 이 결과를 보고한 사전 기준은 무엇인가?
3. multi-task 학습에서 task별 batch sampling 비율과 loss weighting은 무엇인가?
4. “parameter count 60% 이상 감소”가 three separate Transformer 대비인지, adapter parameter까지 포함한 전체 모델 수인지?
5. 현재 Kaggle Version 12에서 수정된 data issue가 논문 Table 2–5의 어떤 수치를 바꾸는가?
6. 공개 데이터에서 user identification·proximity recognition을 수행할 때 어떤 재식별·감시 위험 평가와 access control을 적용했는가?

## 12. 인용

```bibtex
@misc{zhu2025csibench,
  title = {CSI-Bench: A Large-Scale In-the-Wild Dataset for Multi-task WiFi Sensing},
  author = {Guozhen Zhu and Yuqian Hu and Weihang Gao and Wei-Hsiang Wang and Beibei Wang and K. J. Ray Liu},
  year = {2025},
  eprint = {2505.21866},
  archivePrefix = {arXiv},
  primaryClass = {eess.SP},
  url = {https://arxiv.org/abs/2505.21866}
}
```

---
*리뷰 작성: 2026-09-07 · 읽은 범위: PDF pp.1–26 전체(§1–7, Tables 1–5, Appendix A–C, NeurIPS Paper Checklist)*
