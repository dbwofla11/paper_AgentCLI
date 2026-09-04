---
title: "Code World Models for General Game Playing"
authors: ["Lehrach, Wolfgang", "Hennes, Daniel", "Lázaro-Gredilla, Miguel", "Lou, Xinghua", "Wendelken, Carter", "Li, Zun", "Dedieu, Antoine", "Grau-Moya, Jordi", "Lanctot, Marc", "Iscen, Atil", "Schultz, John", "Chiam, Marcus", "Gemp, Ian", "Zielinski, Piotr", "Singh, Satinder", "Murphy, Kevin P."]
venue: "ICLR 2026 (PDF는 arXiv preprint v1)"
year: 2026
arxiv: "2510.04542"
doi: ""
code: "논문 내 코드 저장소 링크 미기재"
pdf: "papers/2026-09-04/lehrach-code-world-models-general-game-playing.pdf"
read_date: 2026-09-04
rating: 4
tags: ["general game playing", "code world model", "LLM", "MCTS", "ISMCTS", "imperfect information"]
status: 완료
---

# Code World Models for General Game Playing

> **TL;DR** — 이 논문은 LLM에게 매번 수를 직접 고르게 하는 대신, 자연어 규칙과 짧은 플레이 궤적을 Python 게임 엔진(CWM)으로 번역하게 하고 그 엔진 위에서 MCTS/ISMCTS로 탐색한다. 10개 게임에서 Gemini 2.5 Pro를 대체로 이겼지만, 이는 “임의의 게임을 사람처럼 이해한다”는 증거라기보다, 제한된 규칙 기반 게임에서 LLM의 언어 이해와 고전적 탐색을 결합할 수 있다는 증거다.

## 먼저 답하는 7가지

1. **기존 게임 AI와 다른 점**: 기존 LLM-as-policy는 관측을 읽고 다음 수를 직접 생성한다. 이 논문은 LLM의 역할을 규칙·데이터→실행 코드 변환으로 옮기고, 실제 수 선택은 탐색 알고리즘에 맡긴다(§1, p.1–2).
2. **CWM이란 무엇인가**: 상태 전이, 합법 수 열거, 관측, chance 분포, 보상, 종료 판정을 담은 실행 가능한 근사 게임 엔진이다(§4.1, p.4).
3. **자연어→코드→전략**: 규칙+5개 offline trajectory+OpenSpiel API+자동 unit test를 LLM에 주고, 실패 stack trace를 이용해 코드를 반복 수정한다. 완성된 코드에서 value function과 숨은 history 추론 함수도 합성한 뒤, MCTS/ISMCTS가 수를 고른다(§4, p.3–6; Appendix G, p.29–34).
4. **MCTS/ISMCTS**: 완전정보 게임은 현재 상태 하나에서 MCTS를 돌리고, 불완전정보 게임은 가능한 숨은 상태를 샘플링해 정보집합별 통계를 합치는 ISMCTS를 쓴다(Appendix B, p.14; §5, p.6).
5. **실험 결과**: 완전정보 5종에서는 CWM-MCTS가 Gemini 2.5 Pro를 모두 이겼고, 불완전정보에서는 Hand of war를 제외하면 대체로 이기거나 비겼다(§5.2, p.8–9). 그러나 Gin rummy 대결은 Gemini의 높은 forfeiture에 크게 의존한다(표 14, p.22).
6. **실제로 일반 게임 플레이인가**: “10개, 그중 4개 OOD인 정해진 게임 묶음에 적응”이라는 좁은 의미에서는 가능성을 보인다. 시각 인터페이스·자유형 텍스트·온라인 능동 학습·임의 규칙으로 확장됐다는 증거는 없다(§6, p.9).
7. **가장 중요한 한계**: CWM의 정확성은 관측된 transition을 통과하는지에 대한 검사이지 게임 의미 전체의 동치 증명이 아니다. 특히 closed-deck 추론은 관측을 재구성해도 올바른 belief 확률을 학습했다는 뜻이 아니며, 실험 승리는 약한 baseline의 illegal move/forfeit에 영향을 받는다(§4.2, §4.4, p.5–6; Appendix C, p.18–22).

## 1. 문제와 동기

- **풀려는 문제**: 새로운 보드·카드 게임의 규칙 설명과 소수의 플레이 기록만 보고, 해당 게임에서 합법적이고 전략적인 행동을 선택하는 일반 게임 플레이 에이전트를 만드는 문제다(§1, p.1–2; §4, p.3).
- **기존 방식의 무엇이 부족한가**: LLM-as-policy는 trajectory와 규칙 설명을 prompt에 넣고 수를 직접 출력하므로 illegal move가 발생할 수 있고, 긴 lookahead가 필요한 전술에서 얕은 플레이를 보일 수 있다. 학습 데이터에 없던 novel game에도 약하다는 것이 저자들의 진단이다(§1, p.1–2).
- **기존 게임 AI와의 차이**: AlphaZero류의 전문 게임 AI처럼 게임별로 학습된 정책·가치망을 만드는 것이 아니라, LLM은 일회성 프로그램 합성기 역할을 하고 이후 계산은 일반 solver가 담당한다. [추론] 따라서 핵심 병목은 정책망의 표현력이 아니라 “규칙을 틀리지 않게 코드화했는가”와 “탐색 예산을 얼마나 줄 수 있는가”로 이동한다(§1, §4, p.1–4).
- **그 진단에 동의하는가** `[내 의견]`: 합법성 검증과 lookahead를 분리하는 문제 설정은 설득력 있다. 다만 직접 policy baseline을 Gemini 2.5 Pro 하나로만 두고, 전문 게임 solver·강한 게임별 baseline과 비교하지 않았으므로 “기존 게임 AI보다 낫다”가 아니라 “직접 수 생성보다 이 실험 조건에서 낫다”로 읽어야 한다(§5, p.6; Appendix C, p.18–22).

## 2. 핵심 기여

| # | 저자 주장 기여 | 위치 | 실제로 새로운가 `[내 판단]` |
|---|---|---|---|
| 1 | LLM이 자연어 규칙과 trajectory에서 Python 기반 CWM을 합성하고, iterative refinement로 수정한다. | §1, §4.1, p.2–4 | WorldCoder·GIF-MCTS와 이어지는 계열이므로 CWM 자체는 완전히 새롭다기보다, multi-agent game에 적용한 확장이다(§3, p.3). |
| 2 | value function을 코드로 합성해 MCTS/ISMCTS의 leaf 평가를 보조한다. | §1, §4.3, p.2, 5 | 이 논문이 게임 플레이 CWM에 추가한 구성요소라는 주장은 타당하지만, 개선은 Gen. tic-tac-toe와 Bargaining에서만 관찰됐다(§5.2, Appendix C.4, p.8, 23). |
| 3 | 불완전정보 게임을 위해 hidden history/state inference를 “코드”로 합성한다. | §1, §4.2, p.2, 4–5 | 불완전정보를 CWM+ISMCTS에 연결한 점은 유의미하다. 다만 posterior의 정확한 분포가 아니라 관측과 양립 가능한 상태를 주로 검증한다. |
| 4 | hidden state를 offline에서도 볼 수 없는 closed-deck CWM 학습을 code-based autoencoder로 제안한다. | §4.4, p.5–6 | 논문이 새 paradigm으로 제시하며, 관측 가능한 재구성 테스트만으로 latent game model을 찾는다는 점이 구별된다. 동시에 식별 불가능성 문제가 남는다(§4.4, p.6). |

## 3. 방법 (Method)

### 3.1 한 문단 개요

에이전트는 먼저 새 게임을 random policy로 몇 판 끝까지 플레이해 trajectory를 수집한다. trajectory와 자연어 규칙을 Gemini 2.5 Pro에 넣어 OpenSpiel API를 따르는 CWM을 만들고, transition·legal action·observation·reward·termination에 대한 unit test 실패를 stack trace로 되먹임해 코드를 수정한다. 완전정보 게임에서는 합성 CWM 위에서 MCTS, 불완전정보 게임에서는 숨은 history를 복원하는 inference function과 CWM 위에서 ISMCTS를 실행한다. 필요할 때 LLM이 별도의 heuristic value function도 작성한다(§4–§4.3, p.3–5).

전체 흐름은 다음과 같다.

`규칙 설명 + 5개 trajectory → LLM 코드 생성 → unit-test 기반 refinement → CWM(+ inference/value) → MCTS/ISMCTS → 행동`

여기서 LLM이 직접 최종 행동을 출력하는 경로는 baseline인 Gemini 2.5 Pro이고, 제안 방식의 온라인 행동은 주로 탐색기가 출력한다(§5, p.6; Appendix F, p.28–29).

### 3.2 표기와 정의

| 기호 | 의미 | 형태/차원 |
|---|---|---|
| $h\in H$ | chance와 모든 플레이어의 action을 포함한 history | action sequence |
| $s_t$ | 시점 $t$의 ground-truth state | 게임별 dictionary |
| $o_t^i$ | 플레이어 $i$가 보는 observation | 게임별 dictionary/tensor |
| $A(h)$ | history에서 합법적인 action 집합 | discrete set |
| $\tau(h)$ | 현재 행동할 player 또는 chance | $N\cup\{c\}$ |
| $M$ | LLM이 만든 CWM | 실행 가능한 Python 함수 묶음 |
| $V(s)$ | leaf state의 heuristic value | scalar float |
| $p_M(s_t\mid o_{1:t}^i,a_{1:t}^i)$ | CWM 기준 플레이어 $i$의 hidden-state belief | posterior/sample distribution |

이 formalization은 extensive-form game의 history, terminal history, chance player, legal action으로 정의된다(§2, p.2–3).

### 3.3 상세

#### CWM의 정확한 내용

CWM은 “게임 규칙을 설명하는 문서”가 아니라 실제로 호출할 수 있는 approximate game copy다. 논문과 Appendix G의 API에 따르면 핵심 함수는 다음과 같다(§4.1, p.4; Appendix G.2, p.29–30).

| 함수 | 하는 일 | 왜 필요한가 |
|---|---|---|
| `apply_action(state, action)` | action 뒤의 새 state를 계산하고 종료를 반영 | 탐색 트리의 edge/transition |
| `get_current_player(state)` | 현재 player, chance 또는 terminal 반환 | 누가 행동할지 결정 |
| `get_legal_actions(state)` | 현재 합법 action 열거 | illegal move 차단 및 branching 생성 |
| `get_observations(state)` | 각 player의 관측 생성 | 완전/불완전정보 구분 |
| `get_rewards(state)` | player별 보상 반환 | rollout과 terminal 평가 |
| `get_player_name(player_id)` | player/chance/terminal 식별 | API 호환성 |

함수 자체는 deterministic이고 randomness는 chance player의 action으로만 들어간다(§4.1, p.4). 예를 들어 Tic-tac-toe의 샘플 CWM은 board와 현재 mark를 state로 두고, 빈 칸을 legal action으로 열거하며, 승리 line 또는 board full이면 terminal로 바꾼다(Appendix I.1, p.47–48).

#### 자연어 게임 규칙이 코드와 플레이 전략으로 바뀌는 과정

1. **탐색 데이터 수집**: 에이전트가 random policy로 게임을 몇 판 끝까지 플레이한다. 각 trajectory에는 observation, reward, legal actions, state가 포함된다. 논문의 기본 실험은 모든 방법에 규칙 텍스트와 5개 offline trajectory를 제공한다(§4, §5, p.3, 6).
2. **API와 테스트가 있는 코드 생성**: LLM은 규칙 설명, trajectory, OpenSpiel 스타일 function signature, 자동 생성 unit test를 prompt로 받는다. perfect-information 예시 test는 특정 state에서 current player, rewards, observations, legal actions, `apply_action` 결과를 동시에 검사한다(Appendix G.1–G.2, p.29–30).
3. **실패 기반 refinement**: 한 번에 만든 코드가 틀리면 transition마다 state·observation·reward·legal action·실행 오류를 검사하고 stack trace를 LLM에 돌려준다. 대화식 refinement는 이전 대화에 실패를 붙이고, tree search refinement는 여러 후보 CWM을 유지하면서 Thompson sampling으로 다음 후보를 고른다(§4.1, p.4; Appendix G.1, p.29). 목표는 accuracy 1.0 또는 refinement budget 소진이다(§4.1, p.4).
4. **불완전정보 보강**: 플레이어 자신의 observation/action만으로 숨은 history 또는 state를 샘플링하는 `resample_history`/`resample_state`를 만든다. hidden history 방식은 샘플한 action history를 CWM에 다시 실행해 valid hidden state와 현재 observation을 재구성하므로, inference test를 통과하면 적어도 CWM posterior의 support에 속한다고 주장할 수 있다(§4.2, p.4–5; Appendix G.3–G.6, p.30–33).
5. **전략으로 변환**: LLM이 만든 CWM은 그 자체가 전략이 아니다. value function이 있으면 leaf에서 rollout 대신 heuristic을 사용하고, 최종 행동은 MCTS/ISMCTS가 탐색 통계에 따라 선택한다(§4.3, §5, p.5–6).

#### Value function 합성

LLM은 CWM과 게임 설명을 보고 terminal에서는 실제 reward를, non-terminal에서는 승리 가능성의 heuristic을 반환하는 deterministic `value_function`을 한 번 생성한다. ground truth 정답이 없어서 CWM처럼 unit-test refinement를 할 수 없고, 여러 후보를 tournament로 비교해 선택한다(§4.3, p.5; Appendix G.7, p.33–34). 따라서 이 함수는 학습된 가치 추정기라기보다 LLM이 만든 게임별 휴리스틱이다 `[추론]`.

#### MCTS와 ISMCTS

- **MCTS**: 완전정보에서는 현재 CWM state를 root로 삼아 여러 번 simulation한다. 트리 안에서 UCB로 action을 선택하고, 아직 확장하지 않은 leaf를 추가한 뒤 value function 또는 모든 player가 random으로 행동하는 rollout으로 값을 얻고, 그 결과를 방문 수와 action-value 통계에 backpropagation한다. 이 논문은 매 행동 전에 1,000 simulations를 사용하고, value function이 없으면 10 rollouts로 새 leaf를 평가한다(§5, p.6; Appendix B, p.14). [MCTS의 선택–확장–평가–역전파 설명은 논문의 표준 MCTS 설명을 풀어 쓴 것이다.]
- **ISMCTS**: 불완전정보에서는 현재 state 하나를 안다고 가정하면 안 된다. 먼저 inference function으로 현재 관측과 양립하는 ground-truth history/state 하나를 샘플하고, 그 상태에서 simulation을 진행한다. 통계는 서로 다른 hidden history를 player가 구분하지 못하는 정보집합(information set) 수준에서 합친다. Appendix B의 간단한 poker 예에서는 자신의 King은 알지만 상대가 Jack인지 Queen인지는 모르는 두 ground-truth 상태를 번갈아 샘플한다(Appendix B, p.14).
- **분포의 약점**: 논문은 inference가 정확한 posterior sample을 보장한다고 말하지 않는다. hidden history가 inference test를 통과하면 valid state이고 posterior support에 들어간다는 보장은 가능하지만, 샘플 빈도/확률이 올바른 posterior라는 보장은 없다(§4.2, p.5). 상대 player 행동의 prior는 CWM이 허용하는 legal action에 uniform하게 둔다(§4.2 각주 3, p.5).
- **실패 처리**: 실제 플레이에서 resampled state가 현재 observation을 재현할 때까지 최대 10번 시도하고, ISMCTS가 termination 이해 실패 등으로 중단되면 state에서 uniform legal action으로 fallback한다(Appendix G.6, p.32–33). 이 fallback은 안전장치이지만 전략적 성공은 아니다 `[내 의견]`.

#### Closed deck autoencoder

open deck에서는 offline trajectory에 hidden state와 다른 player/chance action까지 들어간다. closed deck에서는 플레이어 자신의 observation/action만 있으므로, LLM에게 hidden history inference를 encoder, CWM을 decoder처럼 만들게 한다. hidden state transition을 직접 검사할 수 없기 때문에 관측 재구성 테스트와 random play의 실행·종료 여부만 남긴다(§4.4, p.5–6; Appendix G.5, p.31–33).

저자들은 게임 규칙과 OpenSpiel API가 trivial latent representation을 막는 regularizer처럼 작동한다고 설명하고, 관측을 재현하는 history $\tilde h_t$에 대해 다음 lower bound를 제시한다(§4.4, p.6).

$$
p_M(o_{1:t}^i)=\sum_{h_t}p_M(o_{1:t}^i\mid h_t)p_M(h_t)
\le p_M(o_{1:t}^i\mid\tilde h_t)p_M(\tilde h_t)=p_M(\tilde h_t).
$$

직관은 “관측을 설명하는 하나의 가능한 latent history를 찾으면 CWM likelihood의 하한은 얻는다”는 것이다. 하지만 여러 latent history가 같은 관측을 만들 수 있으므로, 이 하한을 최대로 만드는 것과 실제 게임의 숨은 원인을 식별하는 것은 다르다 `[내 판단]`.

## 4. 실험 설정

| 항목 | 내용 | 위치 |
|---|---|---|
| 데이터셋 | 10개 게임: perfect 5종과 imperfect 5종. 그중 Gen. tic-tac-toe, Gen. chess, Quadranto, Hand of war 4종은 OOD이며 논문을 위해 만든 게임이다. | §5, p.6; Table 3, p.13 |
| 게임 규모 | Backgammon 1,352 actions, Connect four 7, Tic-tac-toe 9, Gen. tic-tac-toe 36, Gen. chess 5,555; imperfect는 Bargaining 121, Leduc poker 3, Gin rummy 241, Quadranto 5, Hand of war 16 actions. | Table 3, p.13 |
| 태스크·지표 | CWM transition/inference accuracy; arena의 W/L/D 또는 player/opponent payoff; forfeit rate | §5.1–5.2, p.6–9; Appendix C, p.18–22 |
| 기본 입력 | 규칙 텍스트와 5개 offline trajectory | §5, p.6 |
| 합성 모델 | Gemini 2.5 Pro | §5.1, p.6 |
| 베이스라인 | Random legal-action executor; ground-truth 게임 코드에 접근하는 GT-(IS)MCTS; direct-policy Gemini 2.5 Pro | §5, p.6 |
| 탐색 예산 | 모든 (IS)MCTS가 행동당 1,000 simulations; 새 leaf는 synthetic value function 또는 random rollout 10회로 평가 | §5, p.6 |
| 평가 transition | 100 games에서 무작위 policy 또는 ground-truth MCTS를 섞어 뽑은 10,000 transitions; synthesis에는 사용하지 않음 | §5.1, p.6 |
| arena 반복 | 합성 stochasticity를 고려해 5개 CWM을 만들고 bad sample을 거른 뒤, 평균 100 matches를 보고 | §5.2, p.8; Appendix E, p.28 |
| refinement 설정 | tree search에서 heuristic weight 5.0, retry 500, 초기 test/type 5, error 시 test/type 1 등 | Appendix C.1.3, p.17 |
| 모델 규모 | Gemini 2.5 Pro의 parameter 수 미기재 | 논문에서 확인되지 않음 |
| LLM 비용·학습 시간·컴퓨트 | GPU/TPU, wall-clock, token 비용은 미기재. game별 LLM call 수만 보고됨 | Table 1–2, 4–6, p.7–8, 15–16 |
| 시드·통계 | 합성 5회와 arena 100 matches는 보고되지만, 주 결과의 confidence interval·유의성·전체 random seed는 미기재 | §5.2, p.8; Appendix C, p.18–22 |

## 5. 결과 — 주장과 증거의 대응

| 저자 주장 | 근거로 제시된 결과 | 위치 | 그 근거가 주장을 지지하는가 `[내 판단]` |
|---|---|---|---|
| 완전정보 게임에서 CWM을 정확하게 합성할 수 있다. | tree-search refinement의 test transition accuracy가 Backgammon 0.99932, 나머지 4종 1.00000이며 online은 모두 1.00000이다. | Table 4, p.15 | 해당 sampled transition에 대해서는 강하게 지지한다. 그러나 전체 state space의 의미적 동치는 아니다. |
| 불완전정보 open deck에서도 CWM과 inference를 학습할 수 있다. | Bargaining/Leduc/Quadranto는 transition·inference test가 대체로 0.98–1.00이다. Gin rummy는 transition train/test 0.7816/0.7455, inference train/test 0.5857/0.5376이고 Hand of war inference test는 0.9357이다. | Table 1, §5.1.2, p.7 | 게임 복잡도가 커지면 급격히 약해진다는 사실까지 포함하면 부분적으로 지지한다. |
| closed-deck에서도 hidden state 없이 학습 가능하다. | inference test accuracy는 Bargaining 0.67359, Leduc 0.97080, Gin rummy 0.09523, Quadranto 0.95183, Hand of war 0.82130이다. | Table 2, §5.1.3, p.8 | 실행 가능한 모델을 만들 수 있다는 증거는 된다. Gin rummy와 Bargaining의 낮은 test accuracy는 강한 일반성 주장을 제한한다. |
| 완전정보에서는 CWM-MCTS가 Gemini보다 강하다. | CWM-MCTS는 5개 게임 모두 Gemini보다 높은 W/L/D 결과를 냈다고 보고한다. 예를 들어 Backgammon과 Gen. chess는 두 player 순서 모두 CWM 승률 1.00이다. | §5.2.1, p.8; Table 7, p.18 | 지지하지만 Backgammon 승리 100/100, Gen. chess 승리의 92/100·97/100이 상대 forfeiture에 의한 결과로 표시된다. 전략적 우월성과 분리해야 한다. |
| CWM의 탐색 품질은 ground-truth solver에 가깝다. | CWM-MCTS와 GT-MCTS 사이에서 어느 한쪽이 모든 게임을 명확히 이기지 않았다고 보고한다. | §5.2.1, p.8; Fig. 2, p.8 | 규칙 엔진 합성 품질에는 긍정적이다. 단, GT-MCTS는 value function을 쓰지 않고 CWM 쪽은 일부 게임에서 썼으므로 완전히 동일한 조건은 아니다(§5.2, p.6, 8). |
| imperfect-information에서도 Gemini를 대체로 이긴다. | open deck hidden-history 기준 CWM은 Bargaining payoff 8.90/8.80, Leduc payoff  -0.03/1.55, Gin payoff 120.54/123.00을 얻었고, Quadranto 승률 .91/.75, Hand of war .35/.33을 보였다. | Table 8–9, p.19 | Hand of war에서는 명확히 밀린다. Leduc은 player 순서에 따라 부호가 바뀌며 variance가 높고, Gin은 Gemini의 99–100% opponent forfeit가 있어 payoff 비교가 오염된다(Table 14, p.22). |
| closed deck 성능은 synthesis가 나빠져도 크게 무너지지 않는다. | closed-deck CWM-ISMCTS는 Quadranto에서 Gemini 상대 승률 .69/.71, Hand of war .41/.54를 냈고, Gin은 29.52/-63.96 payoff로 player 순서에 따라 크게 흔들린다. | §5.2.3, p.9; Table 12–13, p.21 | 일부 게임에서는 가능성을 보이지만, Gin의 불안정성과 표본 100 matches만으로 “크게 degrade하지 않는다”를 일반 명제로 확대하기 어렵다. |

### 핵심 수치 해석

- 저자들의 초록 요약인 “10개 중 9개에서 Gemini 2.5 Pro를 outperform 또는 match”는 전체 게임을 하나의 판정으로 압축한 것이다(초록, p.1). 실제 표에서는 player 순서, payoff 게임, draw, forfeit가 섞여 있어 9/10의 판정 규칙이 명확히 수식화되어 있지 않다 `[확인 필요]`.
- 특히 Gin rummy에서 open-deck CWM-ISMCTS가 Gemini를 상대로 크게 앞선 것처럼 보이지만, Gemini가 opponent일 때 forfeit rate가 0.99 또는 1.00으로 기록된다(표 14, p.22). 따라서 이는 “Gin rummy 전략을 배웠다”보다 “상대 direct-policy 구현이 게임 API를 자주 위반했다”는 설명과도 양립한다 `[내 판단]`.
- OOD 게임에서도 작동했다는 점은 의미가 있다. 그러나 OOD는 저자들이 만든 4개 게임이고 규칙 텍스트가 Appendix H에 명시되어 있으며, 자유형 인터페이스나 새 규칙을 온라인에서 발견한 것은 아니다(§5, p.6; Appendix H, p.35–46).

## 6. Ablation / 분석

| 제거·변경한 것 | 성능 변화 | 위치 | 해석 |
|---|---|---|---|
| Conversation refinement ↔ tree-search refinement | 두 방식 모두 perfect game에서 거의 정확했다. Tree search 표의 LLM call 수는 Backgammon 16.8, Connect four 2.0, Tic-tac-toe 2.0, Gen. tic-tac-toe 2.4, Gen. chess 5.2다. | Table 4–5, p.15 | tree search가 후보를 backtrack할 수 있어 어려운 설정에 더 resilient하다는 저자 설명은 타당하다(§5.1.1, p.7). 다만 Backgammon test accuracy는 conversation .99944가 tree .99932보다 높아 모든 축에서 tree가 우월한 것은 아니다. |
| hidden history inference ↔ hidden state inference | 논문 본문은 hidden history가 조금 더 좋아 기본 선택이라고 하지만, Gin rummy inference test는 hidden history .5376 대 hidden state .9513으로 hidden state가 훨씬 높다. | Table 1, Table 6, p.7, 15 | 본문 서술과 표의 Gin rummy 수치가 긴장 관계에 있다. 평균·게임플레이 기준인지 명시가 부족하다 `[확인 필요]`. |
| synthetic value function 제거 | 개선은 Gen. tic-tac-toe와 Bargaining에서만 관찰되어 해당 게임에만 사용했다. | Appendix C.4, Fig. 9, p.23; §5.2, p.8 | value function이 항상 유효한 것은 아니다. 다만 Fig. 9의 정확한 수치 표가 없어 효과 크기를 재계산하기 어렵다. |
| open deck ↔ closed deck | closed deck inference test가 대체로 낮아졌다. Gin rummy는 .09523까지 내려갔지만 online은 .53953으로 보고됐다. | Table 1–2, p.7–8 | closed-deck encoder가 관측만으로 latent history를 만들 수 있다는 가능성은 보이지만, reconstruction과 실제 belief quality를 분리하지 않았다. |
| MCTS ↔ PPO-CWM | PPO도 Random과 Gemini를 일부/대체로 이기지만, perfect game에서는 대체로 CWM-MCTS에 졌고 imperfect game에서는 게임별로 승패가 갈렸다. | Appendix D, p.24–27, Tables 18–24 | CWM이 반드시 online search를 요구하는 것은 아니지만, reactive policy로 planning을 amortize할 때 품질 손실이 생길 수 있다. |

- **빠진 ablation `[내 판단]`**:
  - CWM이 틀린 상태 전이, legal-action mask, termination, value function 중 어느 요소가 성능을 얼마나 좌우하는지 분리하지 않았다.
  - 1,000 simulations를 10/100/1,000/10,000으로 바꾸는 compute–performance 곡선이 없다. 따라서 “계산을 더 주면 성능이 가까워진다”는 조건부 설명(§4, p.3)의 실증 범위가 제한된다.
  - 5개 trajectory의 수와 구성, random policy와 MCTS trajectory의 비율이 결과에 미치는 영향을 보이지 않았다.
  - Gemini direct policy와 CWM synthesis가 같은 LLM call/token budget인지, 혹은 CWM 쪽이 훨씬 많은 LLM 호출을 사용했는지 비용 정규화가 없다.

## 7. 한계와 비판

**저자가 밝힌 한계** (§6, p.9):

- Gin rummy처럼 논리·절차가 복잡한 게임, 특히 closed deck에서 규칙 학습이 어렵다.
- 현재 방식은 active/online world-model learning을 하지 않는다.
- 향후 free-form text와 visual interface를 가진 open-world game으로 확장해야 한다.

**내가 보는 문제** — 각 항목은 “무엇이 문제인지 + 그래서 어떤 주장이 흔들리는지” 형태로:

- **[방법] posterior를 맞추지 않고 support만 맞춘다**: hidden history inference가 관측과 양립하는 history를 찾는 것은 실제 hidden state의 확률을 올바르게 추정하는 것과 다르다. ISMCTS가 드문 숨은 상태를 지나치게 자주 샘플하면 전략 가치가 틀릴 수 있으므로, “불완전정보를 해결했다”보다 “유효한 후보 상태를 생성해 탐색했다”가 정확한 주장이다(§4.2, p.4–5).
- **[방법] closed-deck latent model은 식별되지 않는다**: 관측 sequence와 같은 결과를 내는 여러 CWM/hidden history가 존재할 수 있다. API·규칙 regularizer가 있어도 유일한 실제 causal state를 복구한다는 보장은 없으므로, closed-deck에서의 성공은 행동에 필요한 충분한 모델일 수는 있어도 진짜 게임 메커니즘을 발견했다는 뜻은 아니다(§4.4, p.6).
- **[실험] unit-test accuracy와 게임 정확성은 다르다**: transition test는 관측된 5개 trajectory 및 별도 sampled transition에 대한 함수 일치율이다. 희귀한 카드 조합, 거의 나오지 않는 termination branch, 긴 procedural scoring을 놓쳐도 평균 accuracy가 높을 수 있다(§4.1, §5.1, p.4, 6). Gin rummy의 train/test 저하는 이 위험을 실제로 드러낸다(Table 1, p.7).
- **[실험] baseline forfeit가 결과를 부풀린다**: Backgammon·Gen. chess·Gin rummy 결과에서 Gemini의 illegal action/exception이 승리로 집계된다. 그러면 CWM의 전략적 깊이와 API 준수 능력을 분리할 수 없다(Table 7, Table 14, p.18, 22).
- **[실험] 비교 비용이 불공정할 수 있다**: CWM은 합성 단계에서 최대 500 retry까지 사용하고, arena 전 5개 후보를 경쟁시켜 나쁜 후보를 버린다. 반면 Gemini direct policy의 prompt 호출 수·추론 비용은 같은 기준으로 보고되지 않았다(Table 1–2, Appendix C.1.3, Appendix E, p.7–8, 17, 28). [추론] 평균 행동 latency와 달러 비용을 맞추면 결론이 약해질 가능성이 있다.
- **[실험] GT-MCTS 비교도 완전한 상한이 아니다**: GT-(IS)MCTS는 ground-truth code를 쓰지만 value function은 쓰지 않는다. CWM agent는 Gen. tic-tac-toe와 Bargaining에서 synthetic value function을 사용했다. 따라서 CWM-MCTS가 GT-MCTS와 비슷하거나 이겼다는 결과는 CWM 규칙 코드의 품질뿐 아니라 평가 함수 차이도 포함한다(§5, Appendix C.4, p.6, 23).
- **[일반화] “general”의 범위가 작다**: 평가 게임은 10개뿐이고, OOD 4개도 저자들이 만든 명시적 규칙 게임이다. 논문이 주장하는 향후 과제 자체가 visual/free-form open-world game이므로, 현재 결과만으로 임의의 새 게임·앱·규칙을 처리한다고 볼 수 없다(§5, §6, p.6, 9).
- **[일반화] 5개 trajectory로 희귀 규칙을 보기 어렵다**: trajectory 수는 5개로 고정됐고, game별 길이·분포·rare branch coverage는 충분히 보고되지 않았다(§5, p.6). [추론] 카드 공개·특수 scoring·긴 종료 절차가 있는 게임에서는 “규칙을 읽었다”보다 “샘플에 실제로 나타난 규칙을 코드화했다”는 쪽으로 결과가 편향될 수 있다.
- **[서술] 9/10 주장은 세부 결과보다 강하다**: payoff, first-player advantage, draw, forfeit가 다른 게임을 하나의 승패 숫자로 묶었고, Leduc은 player 순서에 따라 결과가 크게 달라진다(Table 8–9, p.19). 어떤 집계 규칙으로 9/10을 산출했는지 본문에서 명확히 재현할 수 없다 `[확인 필요]`.
- **[서술] “compute가 optimality로 바뀐다”는 조건부다**: 저자도 모든 합성 요소가 정확할 때라는 조건을 붙인다(§4, p.3). 실제 불완전정보·다중 agent·stochastic game에서는 CWM 오류와 inference bias가 남아 있으므로, simulation 수 증가만으로 실제 게임의 최적성에 수렴한다고 읽으면 안 된다(§4, Appendix B, p.3, 14).

## 8. 재현성 체크

| 항목 | 상태 | 비고 |
|---|---|---|
| 코드 공개 | ☐ 예 ☑ 아니오 | 논문 본문에 저장소 링크가 미기재. OOD 게임은 논문을 위해 만든 게임이라고만 설명됨(§5, p.6). |
| 학습 데이터 접근 가능 | ☐ 예 ☑ 아니오 | 규칙과 5개 trajectory라는 설명은 있으나 trajectory 원본·생성 seed·분할 파일은 제공되지 않음. |
| 체크포인트 공개 | ☐ 예 ☑ 아니오 | CWM Python 샘플은 Appendix I에 일부 있지만 Gemini checkpoint는 없음. |
| 하이퍼파라미터 전부 명시 | ☐ 예 ☑ 아니오 | MCTS simulations, rollout, tree-search 일부 설정은 있으나 LLM generation 설정·전체 budget은 미기재. |
| 컴퓨트 요구량 명시 | ☐ 예 ☑ 아니오 | wall-clock, GPU/TPU, token 비용 미기재. |
| 결과에 분산·시드 보고 | ☐ 예 ☑ 아니오 | 100 matches와 5회 synthesis는 있으나 confidence interval·유의성·주 결과 seed는 없음. |

내가 재현한다면 가장 막힐 지점: OpenSpiel 원본 게임 코드, 5개 offline trajectory, 정확한 synthesis prompt 실행 설정, bad-CWM rejection의 payoff 비교 절차를 모두 복원해야 한다. Appendix G는 prompt 구조를 보여주지만 실제 trajectory와 모든 함수별 test fixture를 제공하지 않는다(Appendix E–G, p.28–34).

## 9. 관련 연구 속 위치

- **직접 기반한 연구**: WorldCoder는 LLM으로 여러 CWM 가설을 만들고 refinement tree와 Thompson sampling을 사용한다. 이 논문은 이를 strategic multi-agent game, value function, imperfect-information inference로 확장한다(§3, p.3).
- **경쟁·대안 접근**: GIF-MCTS도 synthesized model 위에서 MCTS를 사용하지만, 이 논문은 multi-agent strategic environment와 hidden information을 다룬다고 구분한다. POMDP Coder는 hidden state를 hindsight에서 볼 수 있다고 가정하고 determinized belief planner를 사용하며, 이 논문은 closed deck과 ISMCTS/PPO를 추가한다(§3, p.3).
- **또 다른 근접 연구**: Deng et al.은 자연어에서 imperfect-information extensive-form tree를 만들지만 규칙만 사용하고 최대 25 decision nodes의 Kuhn Poker에 적용했다고 논문은 비교한다(§3, p.3).
- **이 논문 이후**: 후속 논문·반박 연구는 이 PDF와 로컬 metadata만으로 확인하지 않았으므로 `[확인 필요]`다.

한 줄 위치 규정: **LLM을 게임 정책이 아니라 실행 가능한 규칙·추론 프로그램 합성기로 사용하고, 고전 탐색기를 붙인 general-game-playing framework다.** 다만 현재 실증은 “제한된 text-rule benchmark에서의 model-based LLM agent” 수준이다.

## 10. 시사점과 후속 아이디어

- **내 작업에 쓸 수 있는 것**: 자연어 이해와 행동 최적화를 한 모델에 몰아넣지 말고, `규칙 컴파일러 → 검증 가능한 simulator → planner`로 분리하는 설계가 유용하다. 특히 legal-action enumeration을 별도 함수로 만들면 illegal output을 구조적으로 줄일 수 있다(§4.1, p.4).
- **이 논문이 열어 둔 질문**: 관측 재구성만으로 hidden-state belief를 calibration할 수 있는가? CWM 여러 가설의 불확실성을 MCTS가 어떻게 유지해야 하는가? value function과 search budget을 어떤 비용 기준으로 선택해야 하는가?
- **해볼 만한 실험 `[내 의견]`**:
  - 동일한 LLM token/latency budget에서 direct policy, CWM synthesis, 전문 solver를 비교한다.
  - CWM transition accuracy가 같은 두 모델을 hidden-state calibration, rare-rule coverage, exploitability로 구분한다.
  - inference sampler의 empirical posterior를 ground-truth belief와 비교하고 Brier score/로그우도/strategy exploitability를 보고한다.
  - 5개에서 5·20·100개로 trajectory 수를 늘리며 Gin rummy와 새 procedural game의 성능 곡선을 측정한다.
  - opponent forfeit를 즉시 승리로 처리하는 평가와, illegal action을 별도 metric으로 분리하는 평가를 함께 보고한다.

## 11. 미해결 질문

1. 초록의 “10개 중 9개에서 Gemini를 outperform 또는 match”는 payoff·W/L/D·first-player advantage·forfeit를 어떤 단일 규칙으로 합산한 결과인가?
2. hidden history가 전반적으로 hidden state보다 낫다는 본문 설명과, Gin rummy에서 hidden state inference test .9513이 hidden history .5376보다 높은 표가 어떻게 양립하는가?
3. CWM synthesis와 direct Gemini policy에 사용된 총 LLM token 수, wall-clock latency, 비용은 각각 얼마인가?
4. closed-deck에서 reconstruction을 만족하는 여러 latent history 중 어떤 기준으로 하나를 샘플하며, 그 샘플 분포가 실제 chance/card posterior와 얼마나 일치하는가?
5. 5개 offline trajectory가 각 게임의 rare terminal/scoring branch를 얼마나 포함하는가? branch coverage 또는 state-space coverage를 보고할 수 있는가?

## 12. 인용

```bibtex
@misc{lehrach2025codeworldmodelsgeneral,
  title={Code World Models for General Game Playing},
  author={Wolfgang Lehrach and Daniel Hennes and Miguel Lazaro-Gredilla and Xinghua Lou and Carter Wendelken and Zun Li and Antoine Dedieu and Jordi Grau-Moya and Marc Lanctot and Atil Iscen and John Schultz and Marcus Chiam and Ian Gemp and Piotr Zielinski and Satinder Singh and Kevin P. Murphy},
  year={2025},
  eprint={2510.04542},
  archivePrefix={arXiv},
  primaryClass={cs.AI},
  url={https://arxiv.org/abs/2510.04542}
}
```

---
*리뷰 작성: 2026-09-04 · 읽은 범위: 본문 §1–6, Appendix A–I(게임 규칙·샘플 코드 포함) · 3패스 완료*
