---
title: "Belief-Calibrated Optimization: An Explicit World Model for Agentic Optimization"
authors: ["Chen, Yuhan", "Tian, Zhihua", "Dabas, Mahavir", "Peris, Charith", "Gupta, Rahul", "Jin, Ming", "Kang, Feiyang", "Zhang, Siyuan", "Wang, Nan", "Jia, Ruoxi"]
venue: "arXiv preprint"
year: 2026
arxiv: "2609.01861v1"
doi: ""
code: "없음"
pdf: "papers/2026-09-04/chen-belief-calibrated-optimization.pdf"
read_date: 2026-09-04
rating: 4
tags: [agentic optimization, world model, persistent memory, LLM agents, scaffold evolution]
status: 완료
---

# Belief-Calibrated Optimization: An Explicit World Model for Agentic Optimization

> **TL;DR** — 이 논문은 frozen LLM 자체를 학습하지 않고, coding agent가 agent scaffold를 반복 수정할 때 `world_model_calibration.md`라는 지속 문서에 “어떤 편집이 어떤 환경 반응을 낳는가”에 대한 가설·예측·관측·교정을 기록하게 한다. 다섯 벤치마크에서 vanilla보다 높은 train/held-out passrate를 얻었지만, 주 비교는 방법별 단일 최적화 trajectory이고 memory benchmark의 held-out 선택 및 안정성 스크리닝이 있어, BCO의 일반적 우월성보다 “명시적이고 교정 가능한 상태를 추가하면 이 실험 조건에서 탐색이 개선될 수 있다”는 결론이 더 안전하다.

---

## 1. 문제와 동기

- **풀려는 문제**: frozen target model 주변의 prompt·program·workflow·agent scaffold를 coding agent가 여러 iteration에 걸쳐 수정할 때, 각 edit의 효과에 대한 belief가 현재 호출의 reasoning 안에만 남고 다음 호출에서 재사용되지 않는 문제를 다룬다. 이 논문은 이를 persistent world model로 외부화한다 (§1, pp.1–2).
- **기존 방식의 무엇이 부족한가** (논문 주장 / §): 기존 propose–evaluate loop는 이전 score·trace를 보지만, “무엇이 병목이고 어떤 edit가 어떤 task에 도움이 되는가”라는 설명을 별도 상태로 유지하지 않는다. 따라서 train split의 우연한 favorable noise를 따라가는 optimizer’s curse가 생길 수 있으며, 저자는 population utility $U$와 관측 utility $\widehat U_Q=U+\varepsilon$를 구분한다 (§2, Eq. 1, p.2).
- **그 진단에 동의하는가** `[내 의견]`: 문제 설정은 설득력 있다. 다만 이후 성능 향상이 belief의 재사용 때문인지, 단순히 추가 prompt 지시·출력·주의 환기 때문인지는 persistent free-form notes 대조와 더 많은 반복 없이는 완전히 분리되지 않는다 (§4.5, Appendix F, pp.5, 13–14).

## 2. 핵심 기여

| # | 저자 주장 기여 | 위치 | 실제로 새로운가 `[내 판단]` |
|---|---|---|---|
| 1 | optimizer의 belief를 지속적인 world model 문서로 유지하고 predict–observe–correct로 갱신하는 BCO 프로토콜 | §3, pp.2–4; Appendix A–B, pp.7–11 | 자연어 persistent memory, self-reflection, agentic optimization을 명시적 falsifiable belief 구조로 결합한 프로토콜 수준의 기여로 보인다. 다만 구성요소 각각은 기존 연구와 겹친다 (§5, pp.6–7). |
| 2 | memory QA·tool-use QA·code-as-action·terminal agent의 다섯 benchmark에서 vanilla보다 높은 성능 및 world model 내용에 대한 offline 증거 | §4, pp.4–6 | 다섯 환경에 동일한 matched protocol을 적용한 실증 기여는 있다. 그러나 단일 trajectory와 일부 held-out 선택 때문에 일반적 우월성의 증거로는 제한적이다 (Appendix C, pp.11–12). |

## 3. 방법 (Method)

### 3.1 한 문단 개요

초기 artifact $x_0$와 고정된 scored task set $Q$가 주어지면, optimizer는 과거 artifact·edit·score·trace의 history $h_t$와 world model $W_t$를 읽고 parent를 고른 뒤 edit $a_t$를 제안한다. edit로 candidate $x_t$를 만들고 $Q$에서 실행해 aggregate score·task-level result·execution trace·tool output을 얻는다. BCO는 실행 전에 task subset별 예상 효과를 `prediction.md`에 쓰고, 실행 후 예상과 관측의 차이를 이용해 `world_model_calibration.md`를 갱신한다. vanilla는 동일한 evidence surface를 받지만 calibration module과 persistent world model이 없다 (§2–3.1, pp.2–3; Appendix A–B, pp.7–10).

### 3.2 표기와 정의

| 기호 | 의미 | 형태/차원 |
|---|---|---|
| $x_0, x_t$ | 초기 artifact와 $t$번째 평가 candidate | prompt·program·workflow·scaffold 중 하나 |
| $a_t$ | parent에 적용하는 edit | mechanism-level source edit |
| $Q$ | 한 run 동안 고정된 scored task set | benchmark의 train subset |
| $o_t$ | candidate 실행 결과 | aggregate score, task 결과, trace, tool output |
| $h_t$ | 이전 상호작용 history | artifact·edit·score·trace의 집합 |
| $W_t$ | $t$번째 world model | atomic belief들의 Markdown 문서 |
| $\beta_{t,i}$ | 하나의 atomic belief | $(\phi,\mathcal C,c,s,E^+,E^-,\mu)$ |

### 3.3 상세

- **핵심 수식 (§, Eq. 번호 명시):**

  $$
  \hat{x}=\arg\max_{x\in\{x_1,\ldots,x_T\}}\widehat U_Q(x),\qquad \widehat U_Q(x)=U(x)+\varepsilon_x.
  $$
  (Eq. 1, §2, p.2)

  관측된 train score만 최대화하면 split-specific noise $\varepsilon_x$가 유리한 candidate를 고를 수 있다는 optimizer’s curse를 표현한다. held-out split은 population utility $U$의 근사로 사용된다 `[논문 설정의 해석]`.

  $$
  a_t\sim\pi_{\mathrm{opt}}(\cdot\mid h_t,W_t),\qquad
  W_{t+1}=\operatorname{Update}(W_t,\widehat{\mathcal O}_t,\mathcal O_t).
  $$
  (Eq. 2–3, §3.1, p.3)

  첫 식은 history와 명시적 belief를 조건으로 edit를 제안하게 하고, 둘째 식은 실행 전 예측 $\widehat{\mathcal O}_t$와 실제 관측 $\mathcal O_t$의 discrepancy가 다음 belief update를 국소화하도록 한다.

  $$
  W_t=\{\beta_{t,i}\}_{i=1}^{m_t},\qquad
  \beta_{t,i}=(\phi_{t,i},\mathcal C_{t,i},c_{t,i},s_{t,i},E^+_{t,i},E^-_{t,i},\mu_{t,i}).
  $$
  (Eq. 4, §3.2, p.3)

  $\phi$는 반증 가능한 claim, $\mathcal C$는 적용 조건, $c\in[0,1]$는 confidence, $s$는 hypothesis/confirmed/refuted 상태, $E^+,E^-$는 지지·반대 evidence, $\mu$는 설명하는 관측 실패의 대략적 개수다.

  $$
  \Delta W_t=(\delta_1,\ldots,\delta_{k_t}),\quad
  \delta_j\in\{\mathrm{Add,Revise,Merge,Remove}\},\qquad
  W_{t+1}=\operatorname{Apply}(W_t,\Delta W_t).
  $$
  (Eq. 5, §3.3, p.4)

  **학습 목표 / 손실 함수:** 파라미터 학습이나 differentiable loss는 없다. 고정된 proposer LLM이 source edit를 생성하고, passrate와 raw trace를 근거로 자연어 belief를 수정하는 heuristic search protocol이다 (§3.1–3.3, pp.3–4; Appendix A, p.7).

- **학습 절차:**
  1. $x_0$를 $Q$에서 평가하고 history를 초기화한다.
  2. proposer가 evaluated ancestor를 parent로 선택하고 mechanism-level edit를 만든다.
  3. 평가 전에 prediction을 task subset 수준으로 기록한다.
  4. candidate를 실행한 뒤 raw tool-call output과 harness control flow를 기준으로 prediction을 채점한다. agent의 최종 답변은 belief grading 근거에서 제외한다.
  5. Add/Revise/Merge/Remove로 world model을 갱신하고 append-only History에 기록한다. 불확실한 belief를 probe하거나 지지된 belief를 활용하는 다음 edit를 고른다 (§3.3, p.4; Appendix B.1, pp.7–8).
  6. $T$번 뒤 train score가 가장 높은 evaluated candidate를 반환한다. memory benchmark는 각 방법의 train 상위 3개 candidate를 held-out에서 다시 평가해 가장 좋은 것을 보고한다 (§2, Eq. 1; §4.1, p.5).

- **추론 절차:** 별도 test-time model update는 없다. 선택된 scaffold를 held-out task에 실행하고, target swap에서는 scaffold를 고정한 채 frozen target만 교체한다 (§4.2–4.3, pp.4–6).

### 3.4 왜 이 방법이 통한다고 저자는 말하는가

- **저자의 설명 (§):** run 안에서는 target model·task·evaluation procedure가 고정되므로 각 outcome이 같은 환경 반응에 대한 evidence가 된다. 따라서 Bayes-Adaptive MDP 관점에서 다음 iteration으로 carry할 것은 response에 대한 belief이며, 이를 문서로 명시하면 실제 effect와 favorable noise를 구분할 수 있다고 설명한다 (§2–3.1, pp.2–3).
- **그 설명이 실험으로 검증되는가, 아니면 사후 서사인가 `[내 판단]`:** 다섯 benchmark의 matched 결과와 Intact > Scrambled > None 순서가 설명과 일치한다. 하지만 confidence는 통계적 posterior가 아니고, belief 작성·grading 모두 LLM heuristic이며, offline ablation은 “문서 내용이 candidate 효과를 예측하는가”를 보일 뿐 online 성능 향상의 인과 경로를 직접 식별하지 않는다 (§4.4, §7, pp.5–6; Appendix G–H, pp.14–15).

## 4. 실험 설정

| 항목 | 내용 | 위치 |
|---|---|---|
| 데이터셋 | LongMemEval-s train/test 100/400; LoCoMo 80/1449; GAIA 40/99; AppWorld 45/372; Terminal-Bench 2.0 20/66. AppWorld는 scenario-disjoint split. AppWorld·TB2.0 train subset은 초기 scaffold stability screen 뒤 고정. | §4.1, pp.4–5; Appendix C, pp.11–12 |
| 태스크·지표 | memory retrieval, tool-calling, ReAct code agent, terminal-use agent; passrate가 주 지표. offline ablation은 upside hit rate·downside precision 및 blind-judge win/loss 사용. | §4.1–4.4, pp.4–6 |
| 베이스라인 | vanilla: 같은 initial scaffold·evidence surface·budget·harness를 사용하되 calibration module만 제거. 추가 persistent-state 진단으로 자유 형식 `agent_notes.md`를 쓰는 Notes를 LongMemEval-s에서 비교. | §3.1, §4.5, pp.3, 5; Appendix F, pp.13–14 |
| 모델 규모 | target은 memory/tool/code benchmark에서 DeepSeek-V4-Flash, TB2.0에서 MiniMax-M3. proposer는 memory Kimi-K2.6, GAIA/AppWorld Kimi-K2.7, TB2.0 Codex(GPT-5.6), 모두 maximum reasoning effort. 파라미터 수는 미기재. | §4.1, p.5, 각주 1 |
| 하이퍼파라미터 | iteration budget: LongMemEval-s·LoCoMo 30, GAIA 20, AppWorld·TB2.0 10; temperature 0, benchmark별 1회 평가, TB2.0만 $k=2$. GAIA target swap은 30 iterations cap. | §4.1, pp.5–6; Appendix D, p.12 |
| 컴퓨트·학습 시간 | wall-clock, GPU/CPU, dollar cost, 총 실행 시간은 미기재. proposer token 상대 변화만 보고됨. | Appendix E, pp.12–13 |
| 시드·반복 횟수 | 주 matched 비교는 방법별 benchmark당 1 trajectory. offline ablation은 네 optimization run의 40 candidates, persistent-state 진단은 방법별 독립 3 trajectories. blind judge는 두 judge model로 반복. | §4.1, §4.4–4.5, pp.5–6; Appendix F–G, pp.13–14 |

## 5. 결과 — 주장과 증거의 대응

| 저자 주장 | 근거로 제시된 결과 | 위치 | 그 근거가 주장을 지지하는가 `[내 판단]` |
|---|---|---|---|
| BCO가 vanilla보다 높은 train passrate를 얻는다 | LME 0.710 vs 0.590, LoCoMo 0.475 vs 0.412, GAIA 0.575 vs 0.425, AppWorld 0.933 vs 0.800, TB2.0 0.550 vs 0.525 | Table 1, §4.2, p.6 | 다섯 행 모두 같은 방향이라 protocol effect의 가능성을 지지한다. 단일 trajectory라 run-to-run variance는 모른다. |
| 개선이 held-out에도 남는다 | LME 0.608 vs 0.533, LoCoMo 0.453 vs 0.375, GAIA 0.495 vs 0.343, AppWorld 0.796 vs 0.766, TB2.0 0.492 vs 0.470 | Table 1, §4.2, p.6 | 방향은 일관되지만 LME·LoCoMo는 train 상위 3개 중 held-out 최고를 보고한 best-of-three라 일반화 격차가 낙관적으로 선택될 수 있다 (§4.1, p.5; Appendix C, pp.11–12). |
| BCO scaffold가 unseen target으로 전이된다 | GAIA에서 target gpt-5.6-luna의 high/medium/low passrate가 각각 BCO 0.657/0.566/0.485로 initial·vanilla보다 높다. AppWorld common completed set에서는 high/medium/low가 0.703/0.661/0.645로 최고다. | Figure 3, Table 6, §4.3, pp.5–6; Appendix D, p.12 | GAIA와 “모든 scaffold가 완료한” AppWorld subset에서는 지지한다. 그러나 AppWorld 전체에서는 BCO가 context overrun으로 99/77/65개 task를 완료하지 못해 0.516/0.524/0.532로 vanilla 0.685/0.608/0.538보다 낮거나 비슷하다. |
| world model 문서가 재사용 가능한 predictive information을 담는다 | None/Scrambled/Intact의 upside hit rate 0.441/0.460/0.538, downside precision 0.142/0.181/0.217; blind judge도 Intact가 Scrambled와 None을 이김 | Table 2, §4.4, p.6 | 문서 형식만이 아니라 content가 유용하다는 방향의 증거다. 단, 4개 run이 독립 단위인 sign test의 양측 $p=0.125$라 강한 통계적 확정은 아니다. |
| persistence만으로는 BCO 효과를 설명할 수 없다 | vanilla/Notes/BCO 평균 train passrate 0.430/0.427/0.467, 방법별 범위 0.11/0.07/0.13 | Table 3, §4.5, p.6; Appendix F, pp.13–14 | BCO가 평균상 높지만 세 trajectory와 큰 분산만으로 Notes의 무효나 BCO의 신뢰할 만한 우위를 확정할 수 없다고 논문 스스로 인정한다. |

**핵심 수치:** Table 1의 held-out 개선 폭은 LME +0.075, LoCoMo +0.078, GAIA +0.152, AppWorld +0.030, TB2.0 +0.022다 (§4.2, Table 1, p.6). BCO의 proposer token 총량은 vanilla 대비 LME −27.4%, LoCoMo −24.7%, GAIA −12.4%, AppWorld +5.2%, TB2.0 +26.2%이고 raw-trace read는 각각 −20%, −69%, −46%, −23%, −42%다 (Appendix E, Table 7, pp.12–13). 즉 BCO가 항상 더 싸지는 않으며, bulky trajectory 환경에서는 belief write 비용이 re-reading 절감보다 크다 `[내 해석]`.

## 6. Ablation / 분석

| 제거·변경한 것 | 성능 변화 | 위치 | 해석 |
|---|---|---|---|
| world model 조건: None → Scrambled → Intact | upside hit rate 0.441 → 0.460 → 0.538; downside precision 0.142 → 0.181 → 0.217 | Table 2, §4.4, p.6 | 구조·명명 효과는 Scrambled가 일부 설명하지만, Intact의 추가 상승은 내용 정보와 일치한다. |
| BCO calibration을 제거하고 자유 형식 persistent `agent_notes.md` 추가 | 평균 0.430 (vanilla), 0.427 (Notes), 0.467 (BCO); within-method ranges 0.11/0.07/0.13 | Table 3, §4.5, p.6; Appendix F, pp.13–14 | BCO protocol의 가능성을 시사하지만, 짧은 3-run 진단으로는 결론 불충분하다. |
| target model swap | GAIA에서는 BCO가 모든 effort tier에서 최고. AppWorld 전체에서는 context overrun으로 저하, common subset에서는 최고 | Figure 3, Table 6, §4.3, pp.5–6; Appendix D, p.12 | 전략의 transfer와 resource-envelope 문제를 동시에 드러낸다. |
| online prediction score를 직접 belief-fidelity 지표로 사용하지 않고 offline fixed-candidate 비교 | online upside hit rate는 run 후반에 하락하지만 base rate도 감소; offline은 같은 candidate·base rate에서 비교 | Appendix H, Table 10, p.15 | 논문이 online score의 drift를 진단하고 offline 평가를 택한 것은 타당하다. 다만 offline judge 자체의 variance는 남는다. |

- **빠진 ablation `[내 판단]`:** (a) BCO가 쓰는 169-line calibration module의 지시문 길이·추가 context만 넣고 belief content를 비워 두는 control, (b) 동일한 structured belief를 사람이 아닌 자동 score-delta 규칙으로 갱신하는 control, (c) 여러 target model을 섞어 world model이 target-specific인지 검사하는 ablation이 없다. 따라서 “calibration-tracked belief”의 어느 요소가 성능을 만들었는지는 아직 분해되지 않았다 `[추론]`.

## 7. 한계와 비판

**저자가 밝힌 한계** (§7, pp.6–7):

- world model은 statistically calibrated posterior가 아니라 LLM의 자연어 요약이며, single-task pass/fail은 noise floor 아래라 subset-averaged behavior를 중심으로 분석한다.
- run 안의 environment response를 고정한다고 가정한다. target model이나 external tool이 drift하면 오래된 evidence를 discount하는 기능이 없다. scaffold가 target에 overfit할 수도 있다.
- 다섯 개 screened benchmark, proposer family 하나가 공유되는 네 benchmark, 방법별 matched comparison당 한 trajectory라는 제약이 있다. AppWorld·TB2.0의 초기 stability screen은 score-guided optimization이 쉬운 환경으로 claim을 좁힐 수 있다.

**내가 보는 문제** — 각 항목은 “무엇이 문제인지 + 그래서 어떤 주장이 흔들리는지” 형태로:

- **[방법] belief calibration이 이름만 calibration일 수 있다:** $c\in[0,1]$ confidence는 calibration curve나 proper scoring rule로 검증되지 않고 proposer LLM이 자연어로 정한다. 따라서 BCO가 uncertainty를 실제로 정량 보정한다고 말하기보다, falsifiable claim을 추적하는 기록 프로토콜로 한정해야 한다 (§3.2–3.3, §7, pp.3–4, 6–7).
- **[실험] main comparison의 분산이 없다:** 각 matched pair가 방법별 한 trajectory라 다섯 benchmark의 일관된 방향이 seed·proposer stochasticity에도 유지되는지 알 수 없다. “일관된 across-benchmark gain”은 지지하지만 “reliable improvement”라는 강한 주장은 흔들린다 (§4.1, §7, p.5–7).
- **[실험] held-out selection leakage가 있다:** LME와 LoCoMo에서 각 방법의 train 상위 3개 candidate를 held-out에 평가하고 그중 최고를 Table 1에 보고한다. 두 방법에 같은 규칙을 적용했어도 held-out이 candidate 선택에 사용되므로 reported gap은 단일 고정 candidate 비교보다 낙관적이다. 부록에서 BCO LME의 비선정 candidate가 held-out 0.6300을 기록한 사실도 selection sensitivity를 보여준다 (Appendix C, Table 4, pp.11–12).
- **[실험] benchmark/split construction이 결과를 유리하게 만들 수 있다:** TB2.0은 89-task 기록에서 초기 불안정·timeout task를 확인한 뒤 20-task train subset을 골랐고, AppWorld와 함께 initial-scaffold stability screen을 적용했다. 이 절차는 재현 가능한 failure mass가 있고 score-guided optimization이 작동하는 subset에 결과를 조건부로 만든다 (Appendix C, p.12).
- **[실험] target swap의 transfer 주장이 조건부다:** AppWorld의 BCO는 매 turn 전체 natural-language scratchpad를 재주입해 새 target의 verbose output에서 context window를 초과했다. common completed-task set의 우위는 “완료 가능한 task에 대한 전략”만 보여주며, 배포 가능한 scaffold의 전체 성능 우위는 보여주지 못한다 (Appendix D, Table 6, p.12).
- **[실험] offline content ablation의 독립 표본이 작다:** 40 candidates가 네 optimization run에 nested되어 있고 independent unit은 run이다. 모든 run이 같은 방향이어도 sign test $p=0.125$이며, 새 trajectory로 world model이 transfer되는지 검증하지 않는다 (§4.4, p.6; Appendix G, pp.14–15).
- **[재현성] 구현 접근성이 낮다:** 논문은 calibration module과 artifact 예시 일부를 Appendix B에 제시하지만 외부 runnable code, checkpoint, full benchmark execution package 링크가 없다. 따라서 169-line module의 정확한 prompt assembly, proposer 호출 방식, stability-screen 구현을 그대로 재현하기 어렵다 (Appendix B.1–B.3, pp.7–11).
- **[비용] 성능–비용 trade-off가 benchmark 의존적이다:** memory/GAIA에서는 raw-trace 재읽기 감소로 total proposer token이 줄지만 AppWorld는 +5.2%, TB2.0은 +26.2% 증가한다. world model이 항상 효율을 개선한다는 해석은 성립하지 않는다 (Appendix E, Table 7, pp.12–13).

## 8. 재현성 체크

| 항목 | 상태 | 비고 |
|---|---|---|
| 코드 공개 | ☐ 예 ☑ 아니오 | 논문 본문·부록에 artifact와 calibration module 설명/발췌는 있으나 외부 repository 링크는 없음. |
| 학습 데이터 접근 가능 | ☐ 예 ☐ 아니오 | benchmark 이름과 split 수는 명시됐지만 각 benchmark 접근 조건은 이 논문에서 체계적으로 정리하지 않음 `[확인 필요]`. |
| 체크포인트 공개 | ☐ 예 ☑ 아니오 | BCO는 새 parameter checkpoint를 학습하지 않으며, 완성 scaffold artifact도 다운로드 링크로 공개되지 않음. |
| 하이퍼파라미터 전부 명시 | ☐ 예 ☑ 아니오 | iteration budget·temperature·repeat는 명시되지만 전체 prompt/runtime 설정은 미기재. |
| 컴퓨트 요구량 명시 | ☐ 예 ☑ 아니오 | 상대 proposer token 변화는 Table 7에 있으나 절대 token·GPU·시간·비용은 미기재. |
| 결과에 분산·시드 보고 | ☐ 예 ☑ 아니오 | main matched run은 방법별 1 trajectory. 보조 진단만 3–4 run이며 분산·유의성 해석도 제한적. |

**내가 재현한다면 가장 막힐 지점:** benchmark별 원본 scaffold와 full `SKILL.md` assembly, proposer API/model version, 초기 stability-screen 코드, 그리고 “raw trace와 harness control flow만으로 prediction을 grade”하는 구체적 parser가 공개되지 않은 점이다.

## 9. 관련 연구 속 위치

- **직접 기반한 연구:** `Large Language Models as Optimizers` (Yang et al., 2023)는 LLM을 optimizer로 사용한다는 기본 propose–evaluate 관점을 제공한다 (§1–2, References). `Automated Design of Agentic Systems` (Hu, Lu, and Clune, 2024), `AFlow` (Zhang et al., 2024), `DSPy` (Khattab et al., 2023)는 scaffold·workflow·instruction을 관측 결과로 최적화한다.
- **경쟁·대안 접근:** `Reflexion` (Shinn et al., 2023), `Self-Refine` (Madaan et al., 2023), `Voyager` (Wang et al., 2023)는 자연어 reflection 또는 persistent memory로 경험을 유지한다. BCO는 자유 형식 회고 대신 prediction, observation, revision과 belief status를 명시한다 (§5, pp.6–7).
- **이 논문 이후:** 이 리뷰에서 확인한 원문은 arXiv `v1`이며, 후속 확장·반박 연구는 확인하지 못했다 `[확인 필요]`.

**한 줄 위치 규정:** BCO는 LLM-driven scaffold evolution에 Bayesian belief-state라는 해석을 부여하고, 이를 자연어 persistent document와 predict–observe–correct protocol로 operationalize한 논문이다. 새 optimizer architecture라기보다, 기존 agentic optimization loop의 cross-iteration state 설계를 실험한 방법론적 제안에 가깝다 `[내 판단]`.

## 10. 시사점과 후속 아이디어

- **내 작업에 쓸 수 있는 것:** 에이전트 개선 로그를 단순 회고문이 아니라 `claim / condition / confidence / status / positive-negative evidence / mass` 단위로 관리하고, 다음 edit 전에 명시적 prediction을 남기는 설계.
- **이 논문이 열어 둔 질문:** 여러 target model·변동하는 tool environment에서 오래된 belief를 언제 폐기할 것인가? confidence가 실제 성공 확률과 일치하는가? persistent memory의 형식·내용·update discipline 중 어느 요소가 대부분의 gain을 만드는가?
- **해볼 만한 실험 `[내 의견]`:** 동일한 scaffold와 candidate sequence를 고정하고 `vanilla`, free-form notes, structured-but-ungraded beliefs, full BCO를 여러 seed로 비교한다. 각 조건에서 held-out은 후보 선택과 완전히 분리하고, target model별·context token budget별 성능과 비용을 함께 보고해야 한다.

## 11. 미해결 질문

원문을 읽고도 답을 못 얻은 것들. 저자에게 물어볼 질문 형태로.

1. BCO의 `confidence` 값은 어떤 일관된 calibration rule 또는 scoring protocol로 결정되며, 실제 belief accuracy와 비교된 적이 있는가?
2. memory benchmark에서 train 상위 3개 중 held-out 최고를 고르는 절차를 제거하고, train에서만 결정된 단일 candidate를 평가하면 gain은 얼마나 남는가?
3. AppWorld target swap에서 scratchpad 길이 제한·요약·sliding window를 추가하면 BCO의 전체-set 성능 저하가 사라지는가?
4. 다섯 benchmark를 각각 여러 seed로 반복했을 때 BCO–vanilla 차이의 신뢰구간과 비용 대비 효과는 무엇인가?

## 12. 인용

```bibtex
@misc{chen2026beliefcalibrated,
  title = {Belief-Calibrated Optimization: An Explicit World Model for Agentic Optimization},
  author = {Yuhan Chen and Zhihua Tian and Mahavir Dabas and Charith Peris and Rahul Gupta and Ming Jin and Feiyang Kang and Siyuan Zhang and Nan Wang and Ruoxi Jia},
  year = {2026},
  eprint = {2609.01861},
  archivePrefix = {arXiv},
  primaryClass = {cs.AI},
  url = {https://arxiv.org/abs/2609.01861}
}
```

---
*리뷰 작성: 2026-09-04 · 읽은 범위: PDF 전체 15쪽(§1–7, References, Appendix A–H)*
