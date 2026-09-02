# EvoSCM — 분석 메모

- 대상: [arXiv:2609.01526](https://arxiv.org/abs/2609.01526), [원문 HTML](https://arxiv.org/html/2609.01526v1), [PDF](../papers/2026-09-02/zhao-evoscm-scientific-belief-revision-causal-model-evolution-experimentation.pdf)
- 저자: Qing Zhao, Haowei Li, Weijian Deng, Pengxu Wei, Liang Lin
- 연도: 2026 (arXiv v1, 2026-09-01 제출)
- 조사일: 2026-09-02
- 상태: 원문 기반 요약 완료; 심층 리뷰 미작성

## 초록

기존 LLM 에이전트는 과학적 가설을 자유 형식 텍스트로 표현해 새 증거에 따라 믿음을 검증·수정하기 어렵다. `EvoSCM`은 여러 경쟁 `SCM (Structural Causal Model)` 가설을 명시적인 epistemic state로 유지하고, 실험 결과와 예측의 차이에 따라 causal structure와 mechanism을 반복적으로 수정한다. `DiscoverPhysics`에서 baseline보다 더 정확한 설명·예측과 더 적은 실험 episode를 얻었다고 보고한다. (Abstract; §1)

## 전체적인 주장과 근거

- 과학 에이전트는 절차적 추론뿐 아니라 세계에 대한 구조화된 믿음도 갱신해야 한다. EvoSCM은 가설 population을 유지하면서 abduction → intervention → induction → deduction 루프를 수행한다. (논문 §2.1–§2.3)
- `DiscoverPhysics`의 `GPT-5.5` 실험에서 explanation score는 0.516에서 0.751로, normalized MSE는 $2.833\times10^{-2}$에서 $2.770\times10^{-4}$로 바뀌었다. `pass@5`는 27.27%에서 63.64%로 증가했고 episode 수는 2,206에서 1,685로 줄었다. (논문 §3, Table 1)
- 명시적 SCM은 다른 backbone으로 이전할 수 있다. `Qwen3.6`에 `GPT-5.6-Sol SCM`을 주입한 경우 `pass@5` 63.64%, explanation 0.740을 기록했다. (논문 §3, Table 2)

## 메소드

환경은 관측 변수·latent exogenous variables·DAG·structural equations·parameters로 표현되는 true SCM을 따르며, 에이전트는 관측 변수는 알지만 나머지는 모른다고 설정한다. 각 라운드에 intervention을 선택하고 결과를 관측한다. (논문 §2.1)

각 가설은 누적 증거에서 latent mechanism을 추론하고, 서로 다른 가설을 구분할 수 있는 intervention과 falsifiable prediction을 만든다. prediction–observation discrepancy는 correction rule로 바뀌며, 수정 연산은 causal edge 추가·삭제, latent variable 추가·삭제, mechanism 변경, parameter 갱신이다. (논문 §2.2–§2.3)

수정된 가설은 누적된 과거 관측을 모두 설명해야 하고, causal graph가 유효한 DAG인지, structural equations가 정의되는지, 변수 역할이 상호 일관적인지 검사한다. 검사를 통과한 가설만 다음 라운드 population에 남는다. 최종 population은 새로운 intervention을 예측하고, 복수 가설이 남으면 예측을 집계한다. (논문 §2.3–§2.4)

## 한계

- 저자 명시: 원문은 preliminary version이며 추가 세부사항과 결과가 이어질 수 있다. (arXiv 메타데이터)
- 실험은 비정규 물리 세계를 다루는 `DiscoverPhysics`에 집중되어 있다. 실제 과학 데이터·실험실 환경으로의 일반화는 검증되지 않았다 `[추론]`. (논문 §3)
- SCM transfer 결과는 이미 진화한 구조 모델을 다른 backbone에 주입한 실험이며, 작은 모델이 처음부터 독립적으로 법칙을 발견했다는 결과와는 다르다 `[추론]`. (논문 §3, Table 2)
- 복잡한 관측 잡음, 실제 실험 비용, 장기적인 구조 변경에 대한 robustness는 제시된 실험만으로 확인되지 않는다 `[확인 필요]`.

## 확인 필요

전체 hyperparameter, SCM population 크기, 실험별 compute와 코드 공개 범위는 이 분석에서 확정하지 않았다 `[확인 필요]`.
