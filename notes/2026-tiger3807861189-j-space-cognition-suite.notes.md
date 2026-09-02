# J-Space Cognition Suite V3.6 — 저장소 분석 메모

- 대상: [github.com/Tiger3807861189/J-Space-Cognition-Suite-V3.6](https://github.com/Tiger3807861189/J-Space-Cognition-Suite-V3.6)
- 논문 아님(코드/문서 저장소). arXiv/DBLP 등록 없음. Zenodo DOI는 저자 자체 등록.
- 분석일: 2026-08-18. GitHub API + raw 파일(README.md, `j-space/SKILL.md`, `j-space/scripts/jspace.py` 전문, `j-space/references/j-space-science.md` 인용부)을 직접 읽고 확인함.

## 정체

Claude Code 등에서 쓰는 "Skill" 형식으로 배포된 **추론시(inference-time) 프롬프트 스캐폴딩**. 모델 가중치 변경·파인튜닝·표현 학습 전혀 없음. `jspace.py`(657줄)는 `argparse, codecs, json, os, re, sys, tempfile, time`만 사용하는 순수 stdlib 코드 — ML 의존성 없음.

## 구성 (근거: repo git tree)

- `j-space/SKILL.md` — 단일 진입점. 과제를 `fast`/`full`/`loop`로 라우팅(§"The gate").
- `j-space/modules/*.md` (9개) — broadcast, capacity, deep-reasoning, directed-focus, empirics, introspection, markers, self-monitoring, shorthand. 필요할 때만 선택 로드.
- `j-space/references/*.md` — j-space-science(과학적 근거 주장), induction-playbook, exemplars.
- `j-space/scripts/jspace.py` — 선택적 상태 관리 CLI.
- `tests/test_jspace.py` — jspace.py 회귀 테스트.

## 핵심 메커니즘 (README §Core mechanisms, SKILL.md 전문 확인)

1. 작업 난이도 게이트(fast/full/loop) — 과제 복잡도에 따라 아래 장치를 얼마나 로드할지 결정.
2. 용량 관리(capacity/broadcast) — 활성 스테이지에 1~2개 개념만 유지, 나머지는 외부 ledger로 externalize.
3. Dense Track — `✓`(검증) `✗`(반증) `?`(미검증) `??`/`?!` 같은 **약자/기호**로 내부 추론에 인식론적 상태를 태깅. 무손실로 자연어 전개 가능해야 함(SKILL.md §"The three registers").
4. Bridge-before-conclusion — 결론이 나오기 전에 중간 개념이 먼저 명시돼야 함(post-hoc rationalization 방지).
5. 메타인지 제어 — 신뢰/진단 동반 재시도/독립 경로/경험적 검증 중 하나를 반드시 선택.
6. 경험적 이스케이프 — 추론이 막히면 미지수를 유한 후보집합으로 바꿔 차등 테스트.
7. 1인칭 에이전시 언어("I"/"we") — 상태 서술을 다음 행동에 결속시키는 통제 문법(README: "consciousness에 대한 주장 아님"이라고 명시).

## jspace.py 상세 (전문 확인, 657줄)

- 저장: `.jspace/WORKSPACE.md`(사람이 읽는 5섹션 markdown: Goal/Core/Verified/Open/Next) + `.jspace/history.json`(최근 20개 seam 스냅샷). `tempfile`+`os.replace`로 원자적 쓰기.
- 서브커맨드: `note`(ledger 갱신, 필드별 엄격한 형식 검증 — 예: `--check`는 `--by`에 커버리지 단어(all/each/n≤5 등)가 없으면 거부), `seam`(요약 출력 + 정체 패턴 3가지를 "사실만" 보고, 판단은 안 함), `resume`(30분 이상 공백 후 premise+invariants+전체 ledger 재출력), `ship`(내보낼 텍스트에 내부 전용 기호/마커/근거 없는 "verified"/반복 루프 징후가 남았는지 스캔, 항상 exit 0, 차단 아님).
- **스크립트 자체는 어떤 판단도 하지 않음.** Goal/Core/Verified/Next 값은 전부 호출자(LLM)가 인자로 채워야 하며, 스크립트는 형식 검증 + 저장/재출력만 함.

## 결론 — 사용자 질문("월드모델/표현학습과 유사한가")에 대한 답

아니다. "workspace", "broadcast", "representation" 같은 어휘는 Global Workspace Theory(Baars 1988; Dehaene & Naccache 2001)와 이를 LLM에 적용했다고 주장하는 해석가능성 논문(Gurnee et al., Anthropic, 2026 — `j-space-science.md`에 인용, transformer-circuits.pub)에서 빌려온 은유. 실제로는:

- 학습된 연속 latent vector가 아니라 **사람이 정의한 텍스트 기호(✓/✗/?)를 markdown 문서에 적어넣는 것**.
- world model의 encoder처럼 손실함수로 압축을 학습하는 게 아니라, "무손실로 자연어 전개 가능해야 한다"는 규칙이 붙은 **인간이 만든 약어 표기법**.
- 가중치도, 표현 공간도 건드리지 않는 **prompt engineering + 파일 기반 외부 메모리(externalized agent memory)** — ReAct/Reflexion/scratchpad prompting과 같은 계열.

## 주의할 점 [확인 필요]

- README의 벤치마크 표(DeepSeek V4-Flash-0731+J-Space vs GLM-5.3/Kimi-K3/Opus-4.8/Fable 5 등)는 근거가 자체 계정 소유의 "companion evaluation report" 저장소뿐 — 제3자 검증 없음.
- "based on Anthropic's J-space global workspace research"라는 문구는 Anthropic 공식 저장소가 아닌 제3자 저장소인데도 마치 Anthropic이 직접 만든 것 같은 인상을 줌. 인용된 2026년 논문(Gurnee et al., transformer-circuits.pub)이 실제로 그 내용대로 존재하는지 별도 검증 못함.
- Zenodo DOI는 저자 자체 등록 가능 — 동료심사·신뢰성 보증과 무관.
