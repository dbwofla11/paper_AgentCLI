---
name: paper-search
description: arXiv / Semantic Scholar / OpenAlex에서 논문을 검색하고 메타데이터를 확정한 뒤 PDF를 papers/에 내려받는다. "논문 찾아줘", "이 주제 서베이 해줘", "이 arXiv 받아줘" 같은 요청에 사용.
---

# 논문 검색과 수집

전체 프로토콜(질의 분해 기준, 소스 우선순위, 스노우볼링 절차, 포화 판정, 실패 처리)은 `docs/search-protocol.md`가 원본이다. 이 파일은 그 요약이다 — 절차가 헷갈리면 그 문서를 먼저 확인한다.

## 도구

`scripts/paper.py` (Python 표준 라이브러리만 사용, 설치 불필요):

```bash
python scripts/paper.py search "query" --source arxiv --limit 10   # arXiv 검색
python scripts/paper.py search "query" --source s2 --limit 10      # Semantic Scholar (인용수 포함)
python scripts/paper.py meta 1706.03762                            # arXiv ID / DOI / S2 ID → 메타데이터 + BibTeX
python scripts/paper.py pdf 1706.03762                             # papers/ 로 PDF 다운로드
python scripts/paper.py refs 1706.03762 --limit 30                 # 이 논문이 인용한 문헌
python scripts/paper.py cites 1706.03762 --limit 30                # 이 논문을 인용한 문헌
```

API가 막히거나 결과가 빈약하면 WebSearch → WebFetch로 보완한다. 허용된 도메인은 `.Codex/settings.json` 참고 (arXiv, Semantic Scholar, OpenAlex, OpenReview, ACL Anthology, PMLR, NeurIPS Proceedings, CVF, DBLP).

## 검색 전략 (요약 — 상세는 `docs/search-protocol.md`)

1. **질의를 분해한다.** 사용자의 한 문장을 (a) 방법 용어, (b) 태스크·도메인 용어, (c) 동의어·이전 세대 용어로 나눈다. 분야 용어는 몇 년 단위로 바뀌므로 한 표현만 쓰면 놓친다.
2. **영어로 검색한다.** 사용자가 한국어로 물어도 질의는 영어로 만든다.
3. **최소 2개 소스**를 돌린다. arXiv는 최신·프리프린트에 강하고, Semantic Scholar는 인용수·피어리뷰 게재 정보에 강하다. S2가 429(rate limit)면 arXiv/OpenAlex로 수동 전환한다 — `search` 명령엔 자동 폴백이 없다.
4. **앵커 논문에서 확장한다(스노우볼링).** 좋은 논문 1~3편을 찾으면 `refs`(후방)와 `cites`(전방)로 넓히는 게 키워드 검색보다 효율이 높다 — 용어가 달라졌거나 초록에 핵심어가 없는 논문은 여기서 잡힌다. 관련 연구 맵이 필요하면 `/related-work`로 넘긴다.
5. **포화하면 멈춘다.** 새 질의·앵커를 돌려도 이미 나온 논문만 반복되면 그 방향은 종료한다.
6. **한계를 보고한다.** 실제 사용한 질의·소스, 스노우볼링에 쓴 앵커, 검색이 특정 연도·용어에 치우친 지점을 결과와 함께 말한다. 빈약한 결과를 그럴듯하게 포장하지 않는다.

## 결과 제시

표로 준다 — 제목 / 저자(제1저자 외 n인) / venue·연도 / 인용수 / arXiv ID / 한 줄 요지 / **왜 이 요청에 관련되는가**.

관련도 순으로 정렬하고, 관련 없어 보이는 것은 목록에서 뺀 뒤 뺐다고 말한다. 인용수는 정보일 뿐 품질 판정이 아니다 — 최신 논문은 구조적으로 인용수가 낮다.

**모든 항목은 실제 검색 결과여야 한다.** 기억으로 논문을 채워 넣지 않는다. 존재를 확인하지 못한 논문은 목록에 올리지 않는다.

## 수집

사용자가 읽을 논문을 고르면:

1. `python scripts/paper.py pdf <id>` 로 `papers/{연도}-{제1저자성}-{슬러그}.pdf` 저장.
2. `meta`로 BibTeX를 확보해 리뷰 프론트매터에 쓸 필드를 정리한다.
3. arXiv 버전이 있고 최종 게재본이 따로 있으면 둘 다 기록하고 어느 쪽을 읽는지 명시한다 (버전 간 내용이 다를 수 있다).
4. PDF가 페이월이면 다운로드를 시도하지 말고 사용자에게 알린다. 우회하지 않는다.
5. `/review-index`로 인덱스에 `읽을 예정` 상태로 등록한다.
