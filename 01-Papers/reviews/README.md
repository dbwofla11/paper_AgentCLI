# 리뷰 카테고리

리뷰는 논문의 주제에 가장 가까운 카테고리 폴더에 둔다. 일일 자동 수집은 `wifi-csi`, `game-ai`, `agent-ai`, `computer-vision` 중에서만 고르며, 사용자가 직접 지정한 논문이나 네 카테고리에 맞지 않는 논문은 `other`에 둔다.

각 카테고리 폴더의 `figures/` 하위 폴더에는 리뷰 §3.0의 방법 구조도를 둔다. `{slug}-method.html`은 `diagram-design` 스킬로 만든 원본이고, `{slug}-method.svg`는 리뷰가 `![…](figures/{slug}-method.svg)`로 임베드하는 내보내기 결과다. 파일 이름은 같은 폴더의 리뷰 slug로 시작한다. 노드·간선의 원문 위치는 그림이 아니라 리뷰의 "구조도 근거" 목록이 정본이다. 리뷰 Markdown과 같이 로컬 전용이며 Git에 커밋하지 않는다.

## WiFi CSI

- [LatentCSI: Real-Time Reconstruction of Physical Scenes from WiFi CSI via Latent Diffusion](wifi-csi/2025-ramesh-latentcsi-wifi-csi-latent-diffusion.md)
- [CSI-Bench: A Large-Scale In-the-Wild Dataset for Multi-task WiFi Sensing](wifi-csi/2025-zhu-csi-bench-wifi-sensing.md)
- [Scalable RF Simulation in Generative 4D Worlds](wifi-csi/2026-zheng-scalable-rf-simulation-4d-worlds.md)

## 게임 AI

현재 리뷰 없음.

## 에이전트 AI

- [Belief-Calibrated Optimization: An Explicit World Model for Agentic Optimization](agent-ai/2026-chen-belief-calibrated-optimization.md)
- [A Multi-Agent Perception-Action Alliance for Efficient Long Video Reasoning](agent-ai/2026-xu-a4vl-long-video-reasoning.md)

## 컴퓨터 비전

- [ARDY: Autoregressive Diffusion with Hybrid Representation for Interactive Human Motion Generation](computer-vision/2026-zhao-ardy-autoregressive-diffusion-hybrid-representation.md)

## 기타

- [Fast Weight Attention for Continual Learning](other/2026-zhang-fast-weight-attention-continual-learning.md)
