---
title: "Large Language Models and Games: A Survey and Roadmap"
authors: ["Gallotta, Roberto", "Todd, Graham", "Zammit, Marvin", "Earle, Sam", "Liapis, Antonios", "Togelius, Julian", "Yannakakis, Georgios N."]
venue: "IEEE Transactions on Games"
year: 2024
arxiv: "2402.18659"
doi: "10.1109/TG.2024.3461510"
code: "없음"
pdf: "01-Papers/pdfs/game-ai/2024-gallotta-large-language-models-and-games-survey.pdf"
read_date: 2026-09-18
rating: 4
tags: [game AI, LLM, survey, NPC, game design, Game Master, procedural content generation]
status: 완료
---

# Large Language Models and Games: A Survey and Roadmap

> **TL;DR** — 이 논문은 LLM을 게임 안팎에서 맡는 역할로 분류해 player, NPC, player assistant, commentator/reteller, analyst, Game Master, game mechanic, automated designer, design assistant의 지도를 제시한다 (§3, pp.3–10). Game AI 연구의 입구로는 유용하지만, 저자 전문성과 수작업 proceedings 검토에 의존한 top-down survey라 검색 범위·선정 기준·역할 간 경계가 재현 가능하게 검증되지 않는다 (§1, pp.1–2).

---

## 1. 문제와 동기

- **풀려는 문제**: LLM이 game playing, NPC, design, commentary 등 여러 게임 역할에 빠르게 도입되는 상황에서, 적용 사례와 아직 비어 있는 연구 방향을 역할 단위로 정리하는 문제다 (Abstract, §1, pp.1–2).
- **기존 방식의 무엇이 부족한가** (논문 주장 / §1): LLM 일반 survey는 있으나 게임에서 LLM이 맡는 역할과 게임 도메인 고유의 기술·윤리 제약을 함께 정리하는 지도가 필요하다고 주장한다 (Abstract, §1, pp.1–2).
- **그 진단에 동의하는가** `[내 의견]`: 대체로 동의한다. `NPC 대화`만으로 LLM-in-games를 환원하면 tool/API 기반 player, GM, design assistant, game telemetry analyst의 설계 제약을 놓친다. 다만 이 논문은 문헌검색 protocol보다 역할 체계를 우선한다.

## 2. 핵심 기여

| # | 저자 주장 기여 | 위치 | 실제로 새로운가 `[내 판단]` |
|---|---|---|---|
| 1 | LLM과 games의 교차점에 대한 comprehensive survey·roadmap을 제시한다. | Abstract, §1, p.1 | 게임 AI의 역할 언어로 LLM 사례를 묶은 점은 유용하다. 그러나 포괄성은 체계적 검색·선정 절차로 검증되지 않는다. |
| 2 | 게임 안팎에서 LLM이 맡는 9개 역할을 분류한다. | §3, pp.2–10 | `player / designer / player model`의 기존 Game AI 역할을 확장한 taxonomy다 (§3, p.2). 독립 방법론보다 분류·해석 기여에 가깝다. |
| 3 | player assistance, commentator/reteller, analyst, procedural design assistance 등을 연구 공백으로 제시한다. | §4, pp.10–12 | 후속 과제의 목록으로는 구체적이지만, 우선순위나 실증 검증은 제공하지 않는다. |

## 3. 방법 (Method)

### 3.1 한 문단 개요

이 논문은 학습 모델이나 새로운 알고리즘을 제안하지 않는 서술형 survey다. 저자들은 게임 AI의 기존 역할 구분을 출발점으로 삼고, 주요 AI-and-games venue와 IEEE Transactions on Games의 최근 proceedings를 수작업으로 검토해 LLM 사례를 9개 역할로 분류한다 (§1, pp.1–2; §3, pp.2–10). 각 역할마다 대표 사례, 적용 조건, 한계와 향후 질문을 연결한다.

### 3.2 표기와 정의

| 기호 | 의미 | 형태/차원 |
|---|---|---|
| LLM | 텍스트를 입력·출력하는 대규모 언어 모델. 본문은 GPT-2 규모를 느슨한 하한으로 두고 LMM도 텍스트 입출력 능력이 있으면 포함한다. | 개념 정의 (§2, p.2) |
| role | 게임 안 또는 개발·시청 맥락에서 LLM에 부여되는 기능적 위치. | player, NPC, assistant 등 taxonomy (§3, pp.2–10) |

### 3.3 상세

- 핵심 수식 (§, Eq. 번호 명시): 해당 없음. Survey이며 새 수식·손실 함수를 제안하지 않는다.
- 이 방법이 하는 일 (직관): 모델·태스크 기준이 아니라 **LLM이 누구를 위해 무엇을 하는가**로 사례를 재배열한다. 예를 들어 player는 action space와 game state를 LLM 입출력으로 변환해야 하고, NPC는 dialogue와 behavior를 구분하며, design assistant는 conceptual/procedural/production assistance의 인간 통제 정도로 나눈다 (§3.1–§3.3, §3.8–§3.9, pp.3–10).
- 학습 목표 / 손실 함수: 해당 없음.
- 학습 절차: 해당 없음. 문헌 검토 절차는 저자 전문성과 주요 venue의 수작업 검토라고만 기재돼 있으며, 검색식·포함/제외 기준·검토자 수는 미기재 (§1, pp.1–2).
- 추론 절차: 해당 없음.

### 3.4 왜 이 방법이 통한다고 저자는 말하는가

- 저자의 설명 (§): 역할 중심 taxonomy는 게임 내 player·NPC·GM과 게임 밖 designer·analyst·commentator를 같은 지도에 놓고, 각 역할의 아직 덜 연구된 지점을 드러낸다고 설명한다 (§3–§4, pp.2–12).
- 그 설명이 실험으로 검증되는가, 아니면 사후 서사인가 `[내 판단]`: 사례 정리와 논증이지 실험 검증은 아니다. taxonomy가 다른 분류보다 더 완전하거나 연구 의사결정을 개선한다는 비교 평가는 없다.

## 4. 실험 설정

| 항목 | 내용 | 위치 |
|---|---|---|
| 데이터셋 | 실험 데이터셋 없음. 주요 AI-and-games venue와 IEEE Transactions on Games의 최근 논문을 수작업 검토했다고만 서술. | §1, pp.1–2 |
| 태스크·지표 | survey와 roadmap 제시. 정량 평가 지표 없음. | Abstract, §1, p.1 |
| 베이스라인 | 없음. | 미기재 |
| 모델 규모 | 자체 모델 없음. | 해당 없음 |
| 하이퍼파라미터 | 해당 없음. | 해당 없음 |
| 컴퓨트·학습 시간 | 해당 없음. | 해당 없음 |
| 시드·반복 횟수 | 해당 없음. | 해당 없음 |

## 5. 결과 — 주장과 증거의 대응

| 저자 주장 | 근거로 제시된 결과 | 위치 | 그 근거가 주장을 지지하는가 `[내 판단]` |
|---|---|---|---|
| LLM은 게임에서 단일 NPC 도구 이상으로 여러 역할을 맡을 수 있다. | player, NPC, assistant, commentator/reteller, analyst, GM, mechanic, automated designer, design assistant의 사례와 역할별 조건을 정리한다. | §3, pp.2–10 | 사례 지도라는 주장에는 충분하다. 실제 배포 가능성이나 역할별 효과의 크기를 증명하지는 않는다. |
| player와 automated designer는 상대적으로 많이 연구됐고 다른 역할은 연구 공백이다. | §4에서 player assistant, commentator/reteller, player analysis, iterative design assistance를 특히 덜 탐색된 방향으로 논한다. | §4, pp.10–12 | 저자 검토 범위 안에서는 설득력 있으나, 체계적 검색 count나 분야별 비교가 없어 공백의 크기는 검증 불가다. |
| 게임은 LLM의 계획·공간추론·장기기억·제약 충족을 시험할 좋은 testbed다. | 게임의 multimodal data, 긴 상호작용, hard/soft constraint를 연결해 benchmark 필요성을 논증한다. | §4, pp.11–12 | 연구 의제로는 타당하다. 어떤 benchmark가 능력을 분리해 측정하는지는 후속 설계가 필요하다. |

핵심 수치:

- 정량 비교·benchmark 수치는 제시하지 않는다. 이 논문의 결과는 역할별 사례와 roadmap의 질적 정리다 (Abstract, §3–§4, pp.1–12).

## 6. Ablation / 분석

| 제거·변경한 것 | 성능 변화 | 위치 | 해석 |
|---|---|---|---|
| 해당 없음 | Survey는 제안 모델의 ablation을 수행하지 않는다. | 해당 없음 | taxonomy의 안정성·포괄성을 검증하는 대체 분류 비교도 없다. |

- 빠진 ablation `[내 판단]`: 역할을 합치거나 나눈 대안 taxonomy, independent reviewer 간 일치도, 검색 DB·기간을 바꿨을 때 사례와 roadmap이 얼마나 달라지는지 분석이 필요하다.

## 7. 한계와 비판

**저자가 밝힌 한계** (§5–§6):

- LLM application에는 hallucination, user-intent 오해, context·continuity 제한, 비용·latency가 있으며, 게임에서는 NPC quest 오류, 장기 GM의 일관성 저하, 실시간성 실패로 나타날 수 있다 (§5, pp.12–13).
- copyright, explainability, 재현성, privacy, bias·toxicity 문제가 게임 도입을 제한한다 (§6, pp.13–14).

**내가 보는 문제** — 각 항목은 "무엇이 문제인지 + 그래서 어떤 주장이 흔들리는지" 형태로:

- **[방법]** 문헌 선택이 top-down·저자 전문성 중심이다. 저자도 keyword search가 다른 종류의 survey를 낳는다고 명시하지만, 검색식·DB·포함/제외 기준·중복 처리·coverage cutoff가 없어 “comprehensive”라는 범위 주장을 독립적으로 재현하거나 반증할 수 없다 (§1, pp.1–2).
- **[방법]** 9개 역할은 상호 배타적이지 않다. 예를 들어 tool-using NPC는 player처럼 action API를 쓰고, GM은 assistant·reteller 기능을 겸한다. 분류가 설계 checklist로 쓰이려면 입력 상태, action 권한, 인간 감독, 실패 비용 같은 축이 추가되어야 한다. `[내 의견]`
- **[실험]** role별 사례가 성공했다는 서술과 실제 production deployment 가능성을 분리하지 않는다. §5의 비용·latency 경고는 강하지만, 각 role에서 요구되는 response-time·state consistency·moderation 조건을 측정하는 공통 평가표는 없다 (§5, pp.12–13).
- **[일반화]** game 분야 밖의 LLM 연구와 2024년 이후 tool use·memory·multimodal agent 발전을 직접 평가하지 않는다. 따라서 roadmap을 현재 시스템의 실증적 우선순위로 읽으면 안 된다. `[추론]`
- **[서술]** “first comprehensive survey”는 abstract의 자기 주장이다. 방법 protocol이 없으므로 이 표현은 scope 선언으로 해석해야 하며, coverage 검증 결과로 읽을 근거는 없다 (Abstract, §1, pp.1–2).

## 8. 재현성 체크

| 항목 | 상태 | 비고 |
|---|---|---|
| 코드 공개 | ☒ 아니오 | Survey 자체의 코드·검색 corpus는 본문에 미기재. |
| 학습 데이터 접근 가능 | ☒ 아니오 | 학습 과제 없음. 문헌 목록은 references로 제공되나 selection corpus는 미기재. |
| 체크포인트 공개 | ☒ 아니오 | 해당 없음. |
| 하이퍼파라미터 전부 명시 | ☒ 아니오 | 해당 없음. |
| 컴퓨트 요구량 명시 | ☒ 아니오 | 해당 없음. |
| 결과에 분산·시드 보고 | ☒ 아니오 | 해당 없음. |

내가 재현한다면 가장 막힐 지점: 동일한 역할 taxonomy를 적용할 문헌 corpus와 선정 규칙이 없다. 검색 기간·venue 목록·키워드·역할 판정 기준을 새로 정해야 한다.

## 9. 관련 연구 속 위치

- **직접 기반한 연구**: *Artificial Intelligence and Games* — player, designer, player model이라는 기존 역할 관점을 출발점으로 삼는다 (§3, p.2; Reference [8]).
- **경쟁·대안 접근**: Yang et al., *GPT for Games: A Scoping Review (2020–2023)* — keyword search 기반 bottom-up review의 대안적 survey 방법으로 언급된다 (§1–§2, pp.1–2; Reference [14]).
- **이 논문 이후**: 이 리뷰 범위 밖의 후속 survey·benchmark 정리는 [확인 필요].

한 줄 위치 규정: Game AI의 역할 vocabulary로 LLM 사례를 재배치해 연구 공백을 드러내는 지도이며, 성능 비교나 체계적 evidence synthesis를 제공하는 survey는 아니다.

## 10. 시사점과 후속 아이디어

- 내 작업에 쓸 수 있는 것: LLM Game AI를 설계할 때 "무슨 모델을 쓸까"보다 **어떤 역할에 어떤 state·action 권한·실패 비용을 줄까**를 먼저 표로 명세하는 checklist로 쓸 수 있다.
- 이 논문이 열어 둔 질문: NPC·GM·assistant에서 RAG/state database·규칙 엔진·moderation을 어디까지 LLM 밖으로 분리해야 consistency와 latency를 보장할 수 있는가?
- 해볼 만한 실험 `[내 의견]`: 동일한 RTS 또는 NPC sandbox에서 (a) pure prompt NPC, (b) state retrieval NPC, (c) function-constrained NPC를 비교하고, quest/state factuality, action validity, p95 latency, 인간 평가의 몰입도를 함께 측정한다.

## 11. 미해결 질문

1. 9개 role 간 중첩을 판정할 annotation guideline과 reviewer agreement는 어떻게 정의할 수 있는가?
2. production game에서 역할별로 허용 가능한 hallucination rate·latency·운영비의 상한은 무엇인가?

## 12. 인용

```bibtex
@article{Gallotta_2024,
  title={Large Language Models and Games: A Survey and Roadmap},
  ISSN={2475-1510},
  url={http://dx.doi.org/10.1109/TG.2024.3461510},
  DOI={10.1109/tg.2024.3461510},
  journal={IEEE Transactions on Games},
  publisher={Institute of Electrical and Electronics Engineers (IEEE)},
  author={Gallotta, Roberto and Todd, Graham and Zammit, Marvin and Earle, Sam and Liapis, Antonios and Togelius, Julian and Yannakakis, Georgios N.},
  year={2024},
  pages={1–18}
}
```

---
*리뷰 작성: 2026-09-18 · 읽은 범위: 본문 pp.1–14, 저자 약력 p.19; references pp.14–18은 인용 확인에 필요한 범위만 읽음*
