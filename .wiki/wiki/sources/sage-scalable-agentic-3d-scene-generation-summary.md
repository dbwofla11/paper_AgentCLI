---
type: summary
title: "SAGE: Scalable Agentic 3D Scene Generation for Embodied AI"
tags:
  - embodied-ai
  - 3d-scene-generation
  - simulation
  - agentic-ai
sources:
  - "[Simulation-ready scene generation](../concepts/simulation-ready-scene-generation.md)"
created: 2026-09-17
updated: 2026-09-17
source_path: ../01-Papers/pdfs/computer-vision/2026-xia-sage-agentic-3d-scene-generation.pdf
ingested: 2026-09-17
---

# SAGE: Scalable Agentic 3D Scene Generation for Embodied AI

CVPR 2026 논문. 자연어로 주어진 embodied task에 맞춰, 정책 학습에 바로 쓸 수 있는 물리적으로 유효한 3D 환경을 대규모로 생성하는 agentic framework를 제안한다.

## 핵심 아이디어

- 에이전트가 floor plan, layout, text-to-3D asset 생성기를 고정된 순서 없이 선택·조합한다.
- visual critic은 의미·공간적 일관성을, physics critic은 Isaac Sim의 중력·충돌 검증을 담당한다. 피드백을 통해 장면을 반복적으로 수정한다.
- object configuration·category·layout의 다단계 augmentation으로 다양한 task-consistent 장면을 만들고, grasp pose·collision-aware IK·navigation으로 demonstration을 합성해 Diffusion Policy를 훈련한다.

## 읽을 때 확인할 점

- critic 신호와 agent의 tool-selection 정책이 어떤 실패 사례를 실제로 줄이는지
- Isaac Sim 검증이 현실 전이에 필요한 물리 속성을 충분히 포착하는지
- SAGE-10k와 합성 demonstration의 규모 대비 정책 성능·일반화 곡선

원문: [저장소 PDF](../../../01-Papers/pdfs/computer-vision/2026-xia-sage-agentic-3d-scene-generation.pdf)
