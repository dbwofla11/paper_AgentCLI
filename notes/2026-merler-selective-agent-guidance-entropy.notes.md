# Selective Agent Guidance via Entropy — 분석 메모

- 대상: [arXiv:2609.01567](https://arxiv.org/abs/2609.01567), [원문 HTML](https://arxiv.org/html/2609.01567v1), [PDF](../papers/2026-09-01/merler-selective-agent-guidance-entropy-learning-autonomous-policies.pdf)
- 저자: Matteo Merler, Giovanni Bonetta, Davide Zago, Rossella Cancelliere, Bernardo Magnini
- venue / 연도: `EMNLP 2026 Findings` / 2026 (arXiv v1, 2026-09-01 제출)
- 조사일: 2026-09-02
- 상태: 원문 기반 요약 완료; 심층 리뷰 미작성

## 초록

VLM을 매 결정 단계의 정책으로 사용하면 비용이 크고, 환경 상호작용을 통해 개선되지 않으며, 체계적인 오류를 반복할 수 있다. `SAGE (Selective Agent Guidance via Entropy)`는 학생 정책의 엔트로피가 높을 때만 VLM 교사에게 행동을 질의하고, 교사 행동을 환경 보상과 함께 경량 RL 정책에 증류한다. 평가는 배포 시 VLM 호출 없이 수행되며, 여러 sparse-reward 시각 의사결정 환경에서 unguided RL보다 높은 성능을 보였다고 보고한다. (Abstract; §1)

## 전체적인 주장과 근거

- VLM은 고정된 실행 정책이 아니라 학습 중 임시 탐색 교사로 사용될 수 있다. `CardMaze`에서 SAGE는 1.000, VLM-as-Policy는 0.000의 mean peak episodic return을 기록했다. (논문 §5.1, Table 1)
- SAGE는 통제 환경에서 학습 단계의 VLM 질의를 1.2–13.3%로 줄였고, 배포 시 VLM 호출이 없다. 비교한 VLM-as-Policy, LVLM2P, DAgger는 학습 중 100% 질의로 보고됐다. (논문 §5.1)
- 교사 행동을 실행하는 것만으로는 부족하다. BC를 제거한 SAGE는 여섯 환경에서 성능이 붕괴했고, AWBC 제거는 일관된 손실이나 이득을 보이지 않았다. (논문 §5.3, Table 3)

## 메소드

상태는 RGB 이미지와 사용 가능한 경우 텍스트 태스크 정보이며, 행동 공간은 discrete action space다. 학생 정책의 정규화 엔트로피가 임계값 `ν`보다 높으면 VLM 행동을 실행하고, 그렇지 않으면 학생 정책에서 샘플링한다. (논문 §3.1–§3.2, Eq. 1–2)

교사 전이 집합 `B_T`와 학생 전이 집합 `B_π`를 나눈다. `B_π`에는 PPO 정책 손실을 적용하고, `B_T`에는 behavioral cloning을 적용하며, 가치함수는 전체 버퍼 `B`에서 환경 보상으로 학습한다. 선택적 `AWBC`는 teacher action의 advantage에 따라 BC weight를 `exp(A/τ)`로 계산하고 안정성을 위해 20으로 clip한다. (논문 §3.3–§3.4, Eq. 3–6)

실험은 `FrozenLake`, `MiniGrid`, `EZPoints`, `CardMaze`, `ALFWorld`에서 진행했다. VLM 기반 방법은 주로 `Qwen3.5-27B`를 사용했고, 일반 환경은 100k steps, `ALFWorld`는 40k steps 학습했으며, 결과는 3 seeds의 mean peak episodic return이다. (논문 §4.1–§5.1, Table 1)

## 한계

- 저자 명시: 엔트로피는 실제 불확실성과 action multimodality를 구분하지 못할 수 있고, 교사가 유용한지 직접 추정하지 않는다. (논문 Limitations)
- 저자 명시: discrete action 실험 중심이며, continuous control 확장은 검증되지 않았다. (논문 Limitations)
- 저자 명시: 무작위이거나 체계적으로 잘못된 교사에 대한 robustness를 보장하지 않는다. (논문 §5.2; Limitations)
- 저자 명시: `ALFWorld`는 작은 학습 예산을 사용한 예비적 stress test다. (논문 §5.1; Limitations)
- [내 판단] Table 3에서 AWBC의 일관된 이득이 확인되지 않아, 현재 근거는 “advantage weighting”보다 “선택적 교사 행동의 BC 증류”에 더 직접적으로 대응한다. (논문 §5.3, Table 3)

## 확인 필요

연속 제어, 실제 로봇 환경, 장기적인 분포 이동에서 SAGE가 동일한 비용·성능 이점을 유지하는지는 이 원문 실험만으로 확인되지 않는다 `[확인 필요]`.
