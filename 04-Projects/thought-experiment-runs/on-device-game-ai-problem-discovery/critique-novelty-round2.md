# Novelty critic — Round 2

## A: 유지

Nair의 단일 global 5초 tag, MASMP의 단일 agent state/memory, PCSP의 LLM 없는 shared policy는 독립 NPC 요청의 shared local LLM 경쟁을 직접 다루지 않는다. 다만 일반 큐잉의 재표현이 되지 않도록 game staleness·NPC별 quality floor를 context/retrieval/admission/order와 공동 제어해야 한다. FIFO·round-robin뿐 아니라 EDF, weighted-EDF, admission control과 비교가 필수다.

## B: 보류

calibrated escalation 자체의 직접 선행은 보관 자료에 없지만, MASMP의 state-action mapping, Nair의 LLM+RL hybrid, PCSP의 urgency preemption/BT를 결합한 자연스러운 확장이다.

학계 전체 신규성은 외부 문헌 확인 전 `[확인 필요]`다.
