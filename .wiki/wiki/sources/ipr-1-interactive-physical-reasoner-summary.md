---
type: summary
title: "IPR-1: Interactive Physical Reasoner"
tags:
  - embodied-ai
  - physical-reasoning
  - world-models
  - game-ai
sources:
  - "[Physical reasoning](../concepts/physical-reasoning.md)"
created: 2026-09-17
updated: 2026-09-17
source_path: ../01-Papers/pdfs/game-ai/2026-zhang-ipr-interactive-physical-reasoner.pdf
ingested: 2026-09-17
---

# IPR-1: Interactive Physical Reasoner

CVPR 2026 논문. 서로 다른 외관·조작 방식을 지닌 1,000개 이상 게임에서 상호작용 경험을 축적해, 보지 못한 게임으로 물리·인과 추론을 전이하는 **Game-to-Unseen (G2U)** 문제를 제안한다.

## 핵심 아이디어

- VLM 정책과 latent world model을 결합한다. world-model rollout이 행동의 물리적 결과를 예측·채점하고, 그 신호로 VLM 정책을 강화한다.
- **PhysCode**는 행동의 의미와 시각적 동역학을 함께 표현하는 물리 중심 action code다. 게임마다 달라지는 키 입력의 표면적 차이를 줄여, 예측과 추론이 공유할 행동 공간을 만든다.
- 평가는 생존(Survival)·새로운 상태 탐색(Curiosity)·목표 달성(Utility)의 3단계다. 논문은 훈련 게임 수와 상호작용 단계가 늘수록 성능이 좋아지고, 미지 게임에도 zero-shot 전이된다고 보고한다.

## 읽을 때 확인할 점

- G2U의 게임 분할과 baseline 비교가 진짜 물리·인과 일반화를 측정하는지
- PhysCode의 학습 신호·표현이 새 조작 인터페이스에서 어떻게 정렬되는지
- 게임 환경에서의 scaling 결과가 로봇 환경으로 얼마나 이전될 수 있는지

원문: [저장소 PDF](../../../01-Papers/pdfs/game-ai/2026-zhang-ipr-interactive-physical-reasoner.pdf) · [프로젝트 페이지](https://mybearyzhang.github.io/ipr-1)
