---
name: thought-experiment-critique
description: "연구 아이디어와 사고실험을 전제·반증조건·누수·평가설계까지 비판적으로 검증한다."
---

# Thought Experiment Critique

연구 아이디어, 모델 파이프라인, 시스템 가설을 실제로 성립하는 주장과 아직 검증되지 않은 가설로 분리해 비판적으로 점검한다. 특히 `성능이 좋아질 것 같다`, `foundation model을 붙이면 보정될 것 같다`, `라벨을 조건으로 생성하면 된다`처럼 자연스럽지만 검증되지 않은 연결을 그대로 승인하지 않는다.

## 적용 범위

- 사용자가 사고실험, 연구 아이디어, 아키텍처 가설의 타당성·한계·반증 가능성을 묻는 경우 사용한다.
- 사용자가 지정한 `notes/thought-experiments/` 파일을 읽고 검증할 수 있다.
- 사용자가 명시하지 않은 외부 구현·논문 다운로드·코드 작성은 하지 않는다. 최신 문헌 확인이 결론에 영향을 주면 `paper-search` 또는 웹 검색을 별도로 사용한다.

## 검증 절차

1. **주장과 목표를 분리한다.** 최종 목표가 분류인지, 실제 pose 복원인지, 시각화인지, 자연어 설명인지 적는다. 목표가 분류뿐이면 중간 skeleton 생성이 정말 필요한지 먼저 묻는다.
2. **파이프라인을 명시한다.** 입력, 중간표현, 조건, 출력, 학습 시에만 존재하는 정보와 추론 시 사용할 수 있는 정보를 구분한다.
3. **전제를 표로 만든다.** 각 전제에 대해 근거, 불확실성, 깨졌을 때의 결과를 적는다. 논문에 없는 것은 `[가설]`, 분석자의 판단은 `[내 판단]`, 확인하지 못한 것은 `[확인 필요]`로 표시한다.
4. **식별가능성을 점검한다.** 입력이 실제로 출력의 세부를 결정할 수 있는지 확인한다. 여러 상태가 같은 관측을 만들 수 있으면 생성 결과는 복원인지 prior 기반 추정인지 구분한다.
5. **정보 누수와 순환성을 찾는다.** ground-truth label, RGB teacher, 생성 caption, future frame, calibration 정보가 학습·추론에서 어떻게 쓰이는지 확인한다. 예측한 label을 조건으로 다시 생성해 평가하는 경우 label error propagation과 label leakage를 분리한다.
6. **대안과 최소 기준을 비교한다.** 단순 temporal filter, GRU/Transformer refiner, deterministic residual head, kinematic optimization 같은 더 싼 기준선을 제시한다. diffusion이 이 기준선보다 필요한 이유가 없으면 “가능하지만 과설계”로 판정한다.
7. **실험을 반증 가능하게 만든다.** in-domain 성능만 보지 말고 cross-subject, cross-room, device/layout shift, noise, missing joints를 분리한다. 정확도 외에 temporal jerk, bone-length violation, action consistency, input/data consistency를 본다.
8. **결론을 등급화한다.** `타당성 높음`, `조건부 타당`, `아이디어는 가능하나 현재 근거 부족`, `핵심 전제가 반증됨` 중 하나로 결론을 내리고, 다음 실험 한두 개를 지정한다.

## 생성 모델·후처리 아이디어에 대한 추가 점검

- diffusion은 관측에 없는 정보를 복구하지 못한다. 조건이 약하면 plausible hallucination을 만들 수 있다.
- 행동 label만 조건으로 넣은 skeleton은 실제 instance pose가 아니라 canonical motion일 수 있다. 실제 동작 복원을 주장하려면 raw signal 또는 coarse pose 조건과 data-consistency 항이 필요하다.
- frame별 독립 생성은 flicker를 만든다. frame-level output이라도 temporal window, velocity/acceleration condition, overlap consistency가 필요하다.
- skeleton 출력에는 image latent보다 graph/pose/motion latent가 기본 선택이다. RGB·avatar 생성이 목적일 때만 image latent를 추가한다.
- residual diffusion을 우선 검토한다: `refined = coarse + correction`. confidence가 높은 관절은 보존하고 낮은 관절에만 생성 자유도를 준다.

## 산출물 형식

노트를 만들거나 갱신할 때는 다음 순서를 권장한다.

```markdown
# 사고실험: 제목
- 작성일:
- 상태: 가설 단계 / 검증 중 / 보류

## 핵심 질문
## 제안 파이프라인
## 성립하는 이유
## 전제와 취약점
## 누수·환각·식별가능성 점검
## 최소 실험과 비교 기준
## 반증 조건
## 현재 결론
## 다음 행동
```

사실 진술에는 논문 링크와 가능한 경우 `§`, `p.`, `Fig.`, `Table` 위치를 붙인다. 검색 결과만으로 방법을 확정하지 말고, 원문을 읽지 못한 세부는 `[확인 필요]`로 남긴다.
