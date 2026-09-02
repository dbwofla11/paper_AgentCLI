# Can LLMs Discover Scientific Laws in Real and Parallel Worlds? — 분석 메모

- 대상: [arXiv:2609.01552](https://arxiv.org/abs/2609.01552), [원문 HTML](https://arxiv.org/html/2609.01552v1), [PDF](../papers/2026-09-02/huang-can-llms-discover-scientific-laws-real-parallel-worlds.pdf), [프로젝트 페이지](https://yiyihum.github.io/SciLaws-Bench/)
- 저자: Yiming Huang, Ziche Liu, Zhuohang Wu 외 11인
- 연도: 2026 (arXiv v1, 2026-09-01 제출)
- 조사일: 2026-09-02
- 상태: 원문 기반 요약 완료; 심층 리뷰 미작성

## 초록

논문은 LLM의 과학 법칙 발견 능력을 평가하는 `SciLaws-Bench`를 제안한다. benchmark는 381개 과학 논문에서 만든 118개 문제, 291개 후보 법칙, 약 8M real data points를 6개 과학 분야에 걸쳐 포함한다. `SciLaws-Real`은 실제 관측에서 법칙을 제안하고 held-out predictive fit과 scientific validity를 평가하며, `SciLaws-Parallel`은 residual-calibrated world를 능동적으로 질의해 합성된 hidden law의 구조를 회복하게 한다. (Abstract; §2.1)

## 전체적인 주장과 근거

- 예측 적합도와 과학적 타당성은 분리될 수 있다. 실제 데이터에서 fit–validity tie-aware concordance는 54.9%였다. (논문 §3.2)
- 모델은 이미 알려진 법칙을 기억해 재현할 수 있지만, 새로운 구조 발견은 드물다. 118개 문제 중 11.9%는 모든 모델이 cold-recall했고, 47.5%는 어떤 모델도 recall하지 못했다. (논문 §3.3)
- best-of-N 후보 집합에는 더 좋은 법칙이 포함될 수 있지만 모델의 self-selection이 그 이득을 충분히 회수하지 못한다. (논문 §1; §5)
- 9개 모델의 aggregate 평가에서 `GPT-5.5`가 `S_N` 50.77%, `S_V` 81.84%, `S_S` 58.26%로 세 지표 모두 가장 높았다. (논문 §3.2, Table 2)

## 메소드

`SciLaws-Real`은 실제 연구 논문과 데이터에서 fixed-record 문제를 구성하고, 모델이 제안한 식을 held-out predictive fit `S_N`과 source-literature 기반 validity `S_V`로 평가한다. `SciLaws-Parallel`은 출판된 기준식에서 structural variant를 만들고, 실제 데이터의 residual을 보정한 simulator를 통해 hidden law를 합성한다. 모델은 관측 없이 시작해 제한된 입력 질의로 데이터를 모으고 hidden structure recovery `S_S`를 평가받는다. (논문 §2.2–§2.4)

모든 모델은 같은 ReAct-style agent framework를 사용한다. Python sandbox에서 데이터 조사·계산·식 적합을 수행하고, `SciLaws-Parallel`에서는 experiment interface로 추가 데이터를 얻으며, trial당 최대 30 interaction turns를 허용한다. (논문 §3.1)

수치 적합도는 closed-form으로 계산하고, validity·structure·memorization 일부는 LLM judge로 평가했다. 다섯 명의 과학 분야 전문가 다수결과 비교한 Cohen’s κ는 memorization 0.77, validity 0.82, structure 0.84였다. (논문 §3.1; Appendix D)

## 한계

- 논문이 실제로 검증한 것은 benchmark 안의 법칙 발견이며, 실제 연구 현장에서 독립적인 과학적 발견을 수행했다는 증거는 아니다 `[추론]`.
- `SciLaws-Parallel`의 hidden law는 published form에서 합성된 구조이므로, 자연에서 완전히 새로운 법칙을 발견하는 상황과는 다르다. (논문 §2.4)
- validity·structure 평가는 LLM judge에 의존하며, 인간 검증은 전체 결과가 아니라 validation sample에 대한 검증이다. (논문 §3.1; Appendix D)
- 6개 분야·118개 문제·9개 모델이라는 평가 범위를 넘어 실제 과학 연구의 다양한 데이터·실험 제약으로 일반화된다고 볼 근거는 없다 `[추론]`.

## 확인 필요

모델별 비용, 전체 실행 시간, 실제 재현용 코드와 데이터 공개 범위는 이 요약에서 확정하지 않았으며 후속 확인이 필요하다 `[확인 필요]`.
