# Novelty critic — Round 1

## 보관 논문 기준 판정

- 후보 1: 축소. Nair & Karim의 고정 5초 selector와 실질 차이가 호출 간격에 가깝다.
- 후보 2: 유지. Nair는 한 전술 태그를 5 NPC에 방송하고, MASMP는 단일 RTS agent, PCSP는 shared RL policy를 다룬다. 다수 NPC의 독립 LLM 요청에 대한 deadline·persona/과업 품질 SLO·context 공동 배분은 직접 다루지 않는다.
- 후보 3: 보류. MASMP memory와 PCSP persona conditioning의 자연스러운 결합이다.
- 후보 4: 축소. Nair의 LLM+PPO와 PCSP의 urgency-driven preemption을 넘어서는 risk calibration이 필요하다.
- 후보 5: 보류. PTQ와 일반 model routing의 응용 재조합으로 남을 위험이 높다.

## 한계

위 판단은 보관 자료에 한정한다. 학계 전체 신규성은 외부 문헌 확인 전 `[확인 필요]`다.
