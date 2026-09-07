---
title: "A Multi-Agent Perception-Action Alliance for Efficient Long Video Reasoning"
authors: ["Xu, Yichang", "Liu, Gaowen", "Kompella, Ramana Rao", "Huang, Tiansheng", "Hu, Sihao", "Ilhan, Fatih", "Tekin, Selim Furkan", "Yahn, Zachary", "Liu, Ling"]
venue: "Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR) 2026"
year: 2026
arxiv: "2603.14052"
doi: "공식 CVF 페이지에 DOI 미기재"
code: "https://github.com/git-disl/A4VL"
pdf: "papers/2026-xu-a4vl-long-video-reasoning.pdf"
read_date: 2026-09-07
rating: 4
tags: [agent AI, video reasoning, VideoQA, multi-agent, frame selection, VLM]
status: 완료
---

# A Multi-Agent Perception-Action Alliance for Efficient Long Video Reasoning

> **TL;DR** — `A4VL`은 여러 vision-language model(VLM) agent가 질의에 맞는 perception clue를 만들고, 영상 block을 선택하고, 답변 불일치 시 서로를 평가해 낮은 점수의 agent를 제거하면서 최대 3라운드 재탐색하는 training-free long-video VideoQA framework다 (§1–2.3, pp.1–6). 다섯 benchmark에서 높은 정확도와 짧은 평균 지연시간을 보였지만, agent 선택이 정답이 아니라 agent 간 다수 합의에 기반하고, baseline별 실행 조건이 완전히 통제됐는지 불명확하며, Video-MME 결과의 본문 서술과 표에도 수치 해석 불일치가 있다.

## 1. 문제와 동기

- **풀려는 문제**: 긴 영상 전체를 VLM에 넣을 때 발생하는 frame redundancy, 메모리·시간 증가, 질의와 무관한 시각 정보로 인한 attention 분산을 줄이면서 VideoQA 정확도를 유지하는 문제다 (§1, pp.1–2).
- **기존 방식의 무엇이 부족한가**: 기존 long-video agent는 한 agent에 의존하거나, video grounding model에 의존하거나, 영상 전체를 오래 처리한다는 것이 저자들의 진단이다. 논문은 VideoAgent가 1시간 영상에서 10분 이상 걸릴 수 있고, MoReVQA가 긴·복잡한 benchmark에서 정확도 한계를 보인다고 예시한다 (§1, p.2).
- **그 진단에 동의하는가** `[내 의견]`: 질의 관련 구간을 먼저 찾고 답변 단계의 frame 수를 제한하는 방향은 타당하다. 다만 agent를 늘리는 것은 각 agent의 VLM 호출과 cross-review 호출을 추가하므로, “multi-agent = 효율적”이 아니라 “전체 영상을 매 agent가 보지 않는 경우에만 효율적”이라는 조건부 주장으로 읽어야 한다.

## 2. 핵심 기여

| # | 저자 주장 기여 | 위치 | 실제로 새로운가 `[내 판단]` |
|---|---|---|---|
| 1 | multi-agent perception–action exploration alliance인 A4VL을 제안한다. | Abstract, §1–2.1, pp.1–3 | frame selection, multi-agent debate, iterative pruning을 하나의 training-free VideoQA loop로 결합한 것이 핵심 설계다. 각 요소 자체가 모두 새롭다고 보기는 어렵다. |
| 2 | unlabeled video-question pair에서 agent 간 답 일치도를 계산해 task-specific top-3 agent team을 고른다. | §2.1, Fig. 3, p.3 | label 없이 agent pool을 줄이는 실용적 장치다. 그러나 일치도는 정확도가 아니라 상관된 오류와 다수 의견을 측정한다. |
| 3 | 소수의 preview frame → perception clue → event-based block alignment → action frame sampling pipeline을 사용한다. | §2.1–2.2, Eq. (1)–(3), pp.2–5 | coarse-to-fine frame selection의 구체적 조합은 유용하지만, event segmentation과 CLIP alignment의 조합이 핵심 원인인지 분해 실험은 제한적이다. |
| 4 | 불일치 시 cross-review, agent pruning, clue refinement를 반복해 정확도와 latency를 함께 개선한다. | §2.3, Eq. (5)–(12), Tables 4, 6–7, pp.5–8 | EgoSchema ablation에서 pruning과 full consensus의 이점은 보이지만, 세 agent의 self/peer 평가가 실제 신뢰도 평가인지 직접 검증하지 않았다. |

## 3. 방법 (Method)

### 3.1 한 문단 개요

A4VL은 agent library에서 task-specific agent 3개를 고른 뒤, 각 agent가 영상 전체에서 4개 preview frame을 무작위로 보고 질의별 perception clue를 만든다. 영상은 scene change·motion·sharpness 등을 이용한 event-based block으로 나누고, CLIP으로 clue와 block의 유사도를 계산한다. 유사도에 따라 각 agent가 최대 16개의 action frame을 다르게 샘플하고, 각 agent가 답과 근거를 생성한다. 답이 모두 같으면 summarizer가 최종 답을 만들고, 다르면 agent들이 서로 1–10점으로 평가해 최저 점수 agent를 제거한 뒤 clue를 갱신해 다음 라운드로 넘어간다 (§2.1–2.3, pp.2–6).

### 3.2 표기와 정의

| 기호 | 의미 | 형태/차원 |
|---|---|---|
| $V=\{v_1,\ldots,v_n\}$ | 입력 영상의 frame 집합 | $n$개 frame (§2.2, p.4) |
| $Q,O$ | 질의와 answer choices | VideoQA 입력 (§2.2, p.4) |
| $A_i$ | agent $i$의 VLM | 선택된 team은 기본 $m=3$ (§2.1, §3.1, pp.3, 6) |
| $N_1$ | preview perception frame 수 | 기본 $N_1=4$ (§2.1–2.2, pp.2, 5) |
| $N_2$ | action reasoning frame 수 | 기본 $N_2=16$ (§2.1–2.2, pp.2, 5) |
| $P_{i,j}$ | agent $i$가 round $j$에서 만든 perception clue | 질의 관련 사건을 설명하는 텍스트/단서 (§2.2, p.5) |
| $B_k$ | event-based로 분할한 video block | 최대 $B$개 (§2.2, p.5) |
| $s^{(i)}_k$ | agent $i$ clue와 block $k$의 CLIP similarity | block별 score (§2.2, p.5) |
| $\rho$ | 모든 block score가 낮을 때의 threshold | 기본 $\rho=0.8$ (§2.2, §3.1, pp.5–6) |

### 3.3 상세

- **Agent teaming**: $M$개 agent와 unlabeled video-question pair $K$개를 준비한다. question $q$에서 choice $r$를 고른 agent 비율을 $f_{qr}$라 하고, agent가 고른 choice를 $r_q$라 하면 agent 점수는 다음과 같다 (§2.1, p.3).

  $$score(A_i)=\frac{1}{K}\sum_{q=1}^{K} f_{q r_q}$$

  점수가 높은 top 3 agent를 이후 해당 task의 agent pool로 고정한다. label을 사용하면 더 정확할 수 있지만, 저자들은 실사용을 위해 unlabeled pair를 사용한다고 설명한다 (§2.1, p.3).

- **Preview clue 생성**: 각 agent는 첫 라운드에 영상 전체에서 $N_1=4$개 frame을 무작위 샘플링한다.

  $$\hat v_{A_i}=p_1(V,N_1),\qquad P_{i,1}=A_{i,clue}(\hat v_{A_i},Q,O)$$

  영상 전체를 block별로 나눠 각 block에서 preview frame을 뽑는 방식도 시험했지만, 저자들은 전체 영상에서 무작위로 뽑는 방식이 temporal coverage와 clue 다양성에서 더 좋다고 선택했다 (§2.2, Eq. (1)–(2), p.5).

- **Event-based block partition**: scene change는 DINOv2 embedding과 HSV·motion·sharpness pixel cue로 후보를 만들고, KTS·PELT·SSM-based novelty로 change point를 찾은 뒤 NMS로 경계를 합친다. 이 과정에서 최대 $B$개 block을 만든다. 저자들은 대부분 benchmark video를 약 2초에 처리한다고 보고한다 (§2.2, p.5).

- **Clue-guided action frame sampling**: 각 agent의 clue와 block 간 CLIP score를 계산한다. 모든 score가 $\rho=0.8$보다 낮으면 최고 score block 하나에서 $N_2=16$개 frame을 뽑는다. 그 외에는 score를 최대값으로 정규화한 뒤 softmax로 allocation을 계산한다.

  $$c^{(i)}_k=\left\lfloor N_2\,\mathrm{SoftMax}(s^{(i)})_k\right\rfloor$$

  합계가 16보다 작으면 남은 frame을 block에 무작위로 분배하고, 각 block에서 $c^{(i)}_k$개를 샘플링해 agent별 action frame set $V^{(i)}_{act}$를 만든다 (§2.2, Eq. (3), p.5).

- **Answer와 reason 생성**: 각 agent는 자기 frame set으로 answer와 reason을 생성한다.

  $$a_{i,j}=A_{i,act}(V^{(i)}_{act},Q,O),\qquad R_{i,j}=A_{i,reason}(V^{(i)}_{act},a_{i,j},Q)$$

  이후 full consensus, 즉 모든 agent가 같은 choice를 내면 모든 clue·answer·reason을 summarizer에 넣어 최종 답과 설명을 만든다. majority consensus도 시험했지만 기본값은 full consensus다 (§2.3, Table 6, pp.5, 8).

- **Cross-review와 pruning**: consensus가 아니면 모든 agent가 자기 자신과 다른 agent의 답·근거를 1–10점으로 평가한다. agent $A_i$의 총점은 다른 agent들이 준 평가의 합으로 계산하고, 최저 총점 agent를 제거한다.

  $$s_{A_i}=\sum_{A_k\in\mathbb A}s_{k,A_i},\qquad A_{min}=\arg\min_{A\in\mathbb A}s_A$$

  살아남은 agent는 현재 clue·답·근거·제거된 agent 정보를 사용해 새 clue $P_{i,j+1}$을 만들고 다음 round에서 block을 다시 고른다 (§2.3, Eq. (8)–(12), pp.5–6). 기본 agent가 3개이므로 최대 3 round를 실행한다 (§3.3, p.7).

- **학습 방식**: A4VL 자체는 task-specific parameter update가 없는 training-free framework다. 다만 DINOv2, CLIP, LLaVA-Video, Qwen-VL, InternVL 등 사전 학습 모델의 가중치와 prompt·agent 구성에 의존한다. 따라서 “training-free”는 이 논문이 새 모델을 fine-tune하지 않는다는 뜻이지, 학습된 모델이나 대규모 inference compute가 필요 없다는 뜻은 아니다 `[내 판단]`.

### 3.4 왜 이 방법이 통한다고 저자는 말하는가

- **저자의 설명**: preview frame은 영상 전체의 coarse clue를 만들고, event block과 CLIP alignment가 질의와 관련된 구간을 좁힌다. 서로 다른 agent의 관점은 독립적인 단서를 제공하고, cross-review·pruning·추가 round가 초기 disagreement를 수정한다고 설명한다 (§1–2.3, pp.1–6).
- **그 설명이 실험으로 검증되는가** `[내 판단]`: RESampling, full consensus, pruning 비교가 EgoSchema에서 각각의 선택을 지지한다. 그러나 agent 간 오류 상관, clue 품질, cross-review의 calibration은 측정되지 않았다. 결과적으로 “프레임 선택과 반복 협력이 도움이 된다”는 것은 보이지만, 각 agent의 독립성이 실제 원인인지는 아직 분리되지 않았다.

## 4. 실험 설정

| 항목 | 내용 | 위치 |
|---|---|---|
| 데이터셋 | NeXT-QA test에서 question type별 200개를 무작위로 뽑은 1,493 QA; EgoSchema test 500 QA; LongVideoBench 1,337 QA, 약 3분–2시간 영상·자막 포함; MLVU-Test 약 500 video, 3분–2시간; Video-MME 2,700 QA, short/medium/long 각 900개. | §3.1, pp.6–7 |
| 태스크·지표 | 객관식 VideoQA 정확도; Video-MME는 자막 사용/미사용을 나눠 보고. 평균 sample latency도 NeXT-QA·EgoSchema·MLVU에서 측정. | §3.1–3.2, Tables 1, 3, pp.6–7 |
| 베이스라인 | GPT-4o, Gemini 1.5 Pro, 16 open-source MLLM, VideoAgent, TraveLER, LVAgent, VideoRAG, BOLT, DYTO 등 총 28개 비교 대상. 별표(*) 결과는 model paper 또는 leaderboard에서 가져온 값. | Table 1, pp.7–8 |
| 모델·agent pool | LLaVA-Video-7B-Qwen2, QwenVL-2.5-7B/32B/72B, InternVL3.5-8B/38B, InternVL3-78B 등 8개 pool에서 benchmark별 top 3을 선택. | §3.1, Table 2, pp.6–7 |
| 주요 hyperparameter | $m=3$, $N_1=4$, $N_2=16$, 최대 round 3, CLIP threshold $\rho=0.8$. | §2.1–2.3, §3.1, pp.3, 5–6 |
| 컴퓨트 | A4VL 실험은 H200 GPU 6개에서 수행. event-based partition은 대부분 영상에서 약 2초라고 보고. baseline별 하드웨어·parallelism·API 비용은 완전히 동일하게 명시되지 않음. | §3.1, §2.2, pp.5–6 |
| 시드·반복 횟수 | 정확도 평균·표준편차나 random seed는 보고되지 않음. | Tables 1, 4–7, pp.7–8 |
| Task-specific selection data | unlabeled video-question pair의 크기와 train/test와의 관계는 미기재. | §2.1, p.3 |

## 5. 결과 — 주장과 증거의 대응

| 저자 주장 | 근거로 제시된 결과 | 위치 | 그 근거가 주장을 지지하는가 `[내 판단]` |
|---|---|---|---|
| A4VL이 다섯 benchmark에서 기존 방법보다 높은 정확도를 낸다. | NeXT-QA 85.1, EgoSchema 82.2, LongVideoBench 72.2, MLVU 58.0; Video-MME 평균 77.2/82.8 (with/without subtitle). | Table 1, §3.2, p.7 | 표에 있는 비교 대상과는 지지된다. 다만 일부 baseline은 별표로 외부 논문·leaderboard 수치이고, 모든 방법을 같은 코드·GPU에서 재실행한 비교는 아니다. |
| open-source agent alliance가 큰 단일 MLLM보다 강하다. | LongVideoBench에서 A4VL 72.2, GPT-4o 66.7; Video-MME no-subtitle 평균에서 A4VL 82.8, Gemini 1.5 Pro 81.3. | Table 1, p.7 | 일부 설정에서는 지지된다. 그러나 agent pool과 baseline model family, subtitle 사용 여부가 섞여 있으므로 “모든 강한 단일 모델보다 우월”로 일반화하면 안 된다. |
| A4VL이 긴 영상에서 latency를 줄인다. | 평균 latency: NeXT-QA 18s, EgoSchema 37s, MLVU 74s; GPT-4o 23/54/127s, InternVL3-78B 15/50/204s, VideoAgent 20/83/175s, TraveLER 101/94/450s. | Table 3, §3.2, p.7 | medium·long setting에서 강한 근거가 있다. NeXT-QA에서는 InternVL3-78B가 15초로 A4VL보다 빠르며, 비용·GPU 수·API latency까지 포함한 공정 비교는 아니다. |
| multi-round collaboration이 정확도를 높인다. | 최대 round를 늘릴수록 다섯 benchmark 정확도가 상승하는 Figure 5; EgoSchema에서 majority 81.4/26s, full consensus 82.2/37s. | Fig. 5, Table 6, §3.3, p.8 | round 증가와 full consensus의 효과는 보이지만, Figure 5의 정확한 수치·분산이 없고, 추가 VLM 호출 비용과 정확도 간 trade-off만 제한적으로 보고된다. |
| RESampling과 pruning이 핵심이다. | EgoSchema: RRSampling 80.2/35s, RESampling 82.2/37s, ERSampling 79.6/37s; pruning 없음은 80.8 또는 79.4/60s, A4VL은 82.2/37s. | Tables 5, 7, pp.7–8 | 해당 ablation에서는 지지된다. 다만 한 benchmark의 한 agent pool에 집중된 결과라 모든 task·pool에 대한 필수성까지 입증하지는 않는다. |

핵심 수치:

- A4VL의 Video-MME 결과는 표의 표기대로 short 86.6/87.3, medium 76.8/83.2, long 68.3/77.9, average 77.2/82.8이며 순서는 with subtitle/without subtitle이다 (Table 1, p.7).
- EgoSchema에서 full consensus는 majority consensus보다 정확도 0.8 percentage point 높지만 sample latency는 26초에서 37초로 증가한다 (Table 6, p.8).
- pruning을 제거하면 latency가 37초에서 60초로 늘고 정확도도 82.2에서 80.8 또는 79.4로 떨어진다 (Table 7, p.8).

## 6. Ablation / 분석

| 제거·변경한 것 | 성능 변화 | 위치 | 해석 |
|---|---|---|---|
| maximum round 1→2→3 | 다섯 benchmark 모두 round가 늘수록 정확도가 상승하는 경향 | Fig. 5, p.8 | 추가 deliberation이 도움이 되지만, round별 정확한 수치와 분산이 없어 증가 폭의 안정성은 판단하기 어렵다. |
| perception $p_1$·action $p_2$ sampling | RRSampling 80.2, RESampling 82.2, ERSampling 79.6; latency 35–37초 | Table 5, p.8 | preview는 uniform random, action은 event-based가 가장 좋다는 선택을 지지한다. |
| majority vs full consensus | 81.4→82.2 accuracy, 26→37초 | Table 6, p.8 | full consensus가 더 보수적인 종료 기준으로 정확도를 높인다. |
| pruning 제거 | NoPruneSum 80.8/60초, NoPruneMaj 79.4/60초, A4VL 82.2/37초 | Table 7, p.8 | pruning이 정확도와 latency를 동시에 개선하는 것으로 보인다. |

- **빠진 ablation `[내 판단]`**:
  1. agent 수 1·2·3·4 이상을 동일 budget에서 비교하지 않았다.
  2. agent teaming 없이 고정 agent 조합을 쓰는 조건과, labeled validation으로 고르는 조건이 없다.
  3. CLIP alignment 없이 uniform block/frame sampling만 사용하는 강한 baseline이 없다.
  4. DINOv2·KTS·PELT·SSM 기반 event segmentation을 각각 제거한 분석이 없다.
  5. peer review를 외부 verifier 또는 confidence calibration과 비교하지 않았다.
  6. $N_1$, $N_2$, $\rho$, 최대 round 변화에 대한 종합적인 accuracy–latency 곡선이 없다.
  7. agent pool과 dataset을 바꿨을 때 pruning이 잘못된 agent를 제거하는지 분석하지 않았다.

## 7. 한계와 비판

**저자가 인정한 한계** (Conclusion, p.8):

- audio–text–video tri-modal input, 더 풍부한 task-conditioned similarity, neuro-symbolic technique으로의 확장을 후속 과제로 남긴다.
- 현재 framework는 주로 video frame과 text question을 사용하며, CLIP 기반 similarity가 가장 빠른 선택이지만 더 발전된 similarity 계산은 향후 과제라고 말한다 (§2.2, p.5).

**내가 보는 문제** — 각 항목은 “무엇이 문제인지 + 그래서 어떤 주장이 흔들리는지” 형태로:

- **[방법] agent teaming이 정확도가 아니라 합의를 최적화한다**: score는 각 agent가 고른 choice가 다른 agent들과 얼마나 자주 일치하는지를 계산한다 (§2.1, Eq. 4, p.3). 모든 agent가 같은 shortcut으로 오답을 고르면 높은 점수를 받으므로, top-3 선택이 “가장 정확한 agent” 또는 “가장 상보적인 team”을 보장하지 않는다. unlabeled selection의 실용성은 있지만 정답 성능과의 상관을 별도로 검증해야 한다.
- **[방법] peer review의 오류가 독립적이지 않다**: 답을 만든 동일한 VLM agent들이 서로의 답과 근거를 평가한다 (§2.3, Eq. 8–11, pp.5–6). 같은 시각적 오해를 공유하면 잘못된 agent를 제거하지 못하거나, 다수 오류에 맞지 않는 정답 agent를 제거할 수 있다. pruning이 실제 confidence calibration을 수행한다는 근거는 없다.
- **[실험] latency 비교가 완전히 공정한지 불명확하다**: A4VL은 3개 VLM의 여러 round 호출, CLIP, event segmentation을 사용하고 H200 6개에서 실행하지만, 표의 GPT-4o·Gemini·외부 agent 결과가 동일한 GPU 수·batching·네트워크·API 대기시간 조건에서 측정됐는지 밝히지 않는다 (§3.1, Table 3, pp.6–7). 따라서 “더 빠르다”는 결과는 보고된 실행 설정 안에서만 유효하다.
- **[실험] baseline의 출처가 혼합되어 있다**: Table 1의 별표 결과는 해당 model paper 또는 leaderboard에서 가져온 값이고, missing entry도 많다 (Table 1, p.7). 같은 benchmark split·prompt·영상 전처리·subtitle 설정으로 모든 baseline을 재실행하지 않았으므로 28개 방법에 대한 순위 비교에는 이질성이 있다.
- **[실험] agent team 선택에 test-distribution 노출 가능성이 있다**: agent teaming은 task dataset에서 뽑은 unlabeled video-question pair를 사용한다고만 적고, 이 pair가 train/validation인지 test인지, 한 번 선택한 team을 모든 test에 고정했는지 명시하지 않는다 (§2.1, p.3). test 질문의 분포를 보고 team을 골랐다면 label 없이도 model selection이 test distribution에 맞춰지는 문제가 생긴다 `[확인 필요]`.
- **[평가] 문제 유형이 객관식에 편중된다**: 다섯 benchmark의 주요 지표가 answer choice accuracy이고, reason은 summarizer 출력으로 제시되지만 explanation correctness를 별도 평가하지 않는다 (§3.1, Tables 1–3, pp.6–7). 따라서 open-ended temporal grounding이나 실제 사용자의 자연어 질문으로 일반화하는 근거는 부족하다.
- **[평가] subtitle 의존성이 시각적 reasoning 주장을 흐린다**: LongVideoBench는 많은 질문이 subtitle-related이고, Video-MME는 subtitle 사용/미사용 결과가 크게 다르다 (§3.1, Table 1, pp.6–7). A4VL의 핵심인 frame selection이 시각적 단서 때문인지 텍스트 단서 때문인지 분리한 분석이 없다.
- **[서술] Video-MME 결과의 본문과 표가 불일치한다**: Table 1은 A4VL 평균을 with/without subtitle 순서로 77.2/82.8, Gemini 1.5 Pro를 75.0/81.3으로 제시한다. 그런데 본문은 A4VL 77.2를 “without subtitles” 성능으로 설명하고 Gemini 75.0보다 2.2 높다고 말한다 (§3.2, p.7). 표 기준으로 +2.2는 with-subtitle 비교이고, without-subtitle 비교는 82.8 대 81.3으로 +1.5다 `[내 판단]`.
- **[일반화] real-world long video로의 범위가 좁다**: benchmark는 curated VideoQA test set이며, 실시간 stream, camera motion, audio, open-ended instruction, 질문 분포 변화, 영상 domain 변화는 평가하지 않는다 (§3.1, Conclusion, pp.6, 8). “real world long videos”라는 표현은 benchmark 내 영상에 대한 주장으로 제한해야 한다.
- **[재현성] 최신 코드와 논문 결과의 상태를 구분해야 한다**: 공식 저장소는 current code의 JSON 구조가 최적화로 달라졌지만 정확도는 맞을 것이라고 설명하고, 현재 `nextqa_results.json`만 current code 결과이며 다른 benchmark는 검증 중이라고 적는다 ([공식 저장소 README](https://github.com/git-disl/A4VL#results), 확인일 2026-09-07). 따라서 논문의 다섯 benchmark 전체 수치를 최신 코드로 재현했다고 보기는 어렵다 `[확인 필요]`.

## 8. 재현성 체크

| 항목 | 상태 | 비고 |
|---|---|---|
| 코드 공개 | ☑ 예 ☐ 아니오 | 공식 GitHub 저장소가 있고 NextQA·EgoSchema·MLVU pipeline과 unified launcher를 제공한다. |
| 학습 데이터 접근 가능 | ☑ 예 ☐ 아니오 | benchmark 영상·annotation은 각 dataset에서 별도로 준비해야 한다. 논문이 새 학습 데이터셋을 공개하는 연구는 아니다. |
| 체크포인트 공개 | ☐ 예 ☑ 아니오 | A4VL 학습 checkpoint가 아니라 ASP-CLIP checkpoint와 실행 코드가 중심이다. VLM backbone은 별도 준비가 필요하다 `[확인 필요]`. |
| 하이퍼파라미터 전부 명시 | ☐ 예 ☑ 아니오 | $m$, $N_1$, $N_2$, $\rho$, 최대 round는 있으나 prompt 전문, decoding parameter, agent teaming pair 수, API/model serving 설정, block 수 $B$의 benchmark별 값은 미기재다. |
| 컴퓨트 요구량 명시 | ☐ 예 ☑ 아니오 | A4VL에 H200 6개를 사용한다고는 하지만 GPU memory, per-agent GPU placement, 총 비용·전력, baseline별 동일 조건은 미기재다. |
| 결과에 분산·시드 보고 | ☐ 예 ☑ 아니오 | 표에 mean±std와 random seed가 없고, 정확도·latency가 단일 수치다. |

내가 재현한다면 가장 막힐 지점:

1. benchmark별 영상·annotation 경로와 대형 VLM checkpoint를 별도로 준비해야 한다.
2. 논문에 prompt, generation 설정, agent teaming sample 수, API/serving 조건이 모두 공개되어 있지 않다.
3. Table 3의 latency를 같은 GPU·동일한 parallelism·네트워크 조건에서 다시 측정해야 한다.
4. current code가 다섯 benchmark 전부의 paper JSON을 동일하게 재현하는지 아직 저장소 README상 검증 중이다.

## 9. 관련 연구 속 위치

- **직접 기반한 연구**: `VideoAgent`는 memory-augmented multimodal agent로 비교 대상이며, `TraveLER`는 modular multi-LLM agent framework로 latency·정확도 비교에 포함된다 (References [5], [32], Table 1, pp.7, 10).
- **경쟁·대안 접근**: `LVAgent`의 multi-round dynamical collaboration, `VideoRAG`의 retrieval augmentation, `BOLT`·`DYTO`·`DynFocus`의 frame/token 효율화가 각각 다른 방식의 long-video 처리 대안이다 (Table 1, References [2], [8], [20], [21], [55], pp.7, 10–11).
- **이 논문 이후**: 이 리뷰에서는 A4VL 이후의 후속 연구·반박 관계를 조사하지 않았다 `[확인 필요]`.

한 줄 위치 규정: A4VL은 새 VLM을 학습한 논문이 아니라, heterogeneous VLM을 질의별 frame selection·cross-review·pruning으로 조정하는 inference-time orchestration 논문이다. 성능의 핵심은 “agent 수”보다 “관련 구간만 각 agent에 보여주는 탐색 정책”과 “불일치 시 계산을 추가하는 선택적 deliberation”에 있다.

## 10. 시사점과 후속 아이디어

- **내 작업에 쓸 수 있는 것**: 긴 영상 agent를 만들 때 처음부터 모든 frame을 넣기보다, 질의별 coarse clue를 만든 뒤 event block을 검색하고 작은 frame budget으로 reasoning하는 2단계 구조를 사용할 수 있다 `[내 의견]`.
- **이 논문이 열어 둔 질문**:
  1. agent 간 합의와 실제 정답 확률을 어떻게 분리·보정할 것인가?
  2. disagreement가 높은 경우에만 추가 계산을 쓰는 것이 언제 가장 이득인가?
  3. CLIP similarity가 질의 사건의 시간적 인과관계까지 보존할 수 있는가?
  4. subtitle·audio·visual evidence가 충돌할 때 어느 modality를 우선해야 하는가?
- **해볼 만한 실험 `[내 의견]`**:
  1. unlabeled agreement score, peer-review score, 실제 validation accuracy의 calibration curve를 그린다.
  2. agent teaming을 majority agreement, validation accuracy, diversity-aware selection으로 비교한다.
  3. 1/2/3 agent와 1/2/3 round를 고정 API-call budget 아래에서 비교한다.
  4. uniform sampling, CLIP-only, DINO/event-only, A4VL을 같은 frame·token budget으로 비교한다.
  5. subtitle 제거·audio 추가·open-ended answer를 포함해 visual grounding과 language shortcut을 분리한다.
  6. 정확도뿐 아니라 wall-clock, GPU memory, token 수, API 비용, CO2e를 함께 보고한다.

## 11. 미해결 질문

1. agent teaming에 사용한 unlabeled pair의 수와 test split과의 중복 여부는 무엇인가?
2. task-specific top-3 agent 선택이 validation accuracy 또는 ensemble diversity와 실제로 얼마나 상관되는가?
3. cross-review 점수의 temperature·prompt·출력 형식은 무엇이며, peer score가 calibration된 confidence인가?
4. benchmark별 $B$, CLIP model/version, block feature aggregation 방식은 무엇인가?
5. Table 3의 baseline latency는 동일한 H200·GPU 수·batching·network 조건에서 측정했는가?
6. Video-MME 표의 with/without subtitle 수치와 본문 설명 중 어느 해석이 저자의 의도인가?
7. current GitHub code의 모든 benchmark 결과가 논문 Table 1을 그대로 재현하는가?

## 12. 인용

```bibtex
@InProceedings{Xu_2026_CVPR,
  author    = {Xu, Yichang and Liu, Gaowen and Kompella, Ramana Rao and Huang, Tiansheng and Hu, Sihao and Ilhan, Fatih and Tekin, Selim Furkan and Yahn, Zachary and Liu, Ling},
  title     = {A Multi-Agent Perception-Action Alliance for Efficient Long Video Reasoning},
  booktitle = {Proceedings of the IEEE/CVF Conference on Computer Vision and Pattern Recognition (CVPR)},
  month     = {June},
  year      = {2026},
  pages     = {19497--19507}
}
```

---
*리뷰 작성: 2026-09-07 · 읽은 범위: PDF pp.1–11 전체(§1–4, Tables 1–7, Fig. 1–5, References)*
