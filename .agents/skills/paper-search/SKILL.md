---
name: paper-search
description: 논문 검색·업로드 자료의 메타데이터를 확인하고 PDF, Keep 대기열, 구조화 JSON으로 수집한다. 논문 검색 요청이나 PDF·링크를 대화에 올렸을 때 사용.
---

# 논문 검색과 수집

사용자가 제목·링크·arXiv ID를 주거나 대화에 PDF를 첨부하면 이 스킬이 논문 목록 수집을 담당한다. 사용자가 직접 올린 논문은 자동으로 읽기 대기열에 넣는다. 검색 결과만 요청한 경우에는 후보를 제시하고, 사용자가 채택한 논문만 저장한다.

전체 프로토콜(질의 분해 기준, 소스 우선순위, 스노우볼링 절차, 포화 판정, 실패 처리)은 `.scripts/docs/search-protocol.md`가 원본이다. 이 파일은 그 요약이다 — 절차가 헷갈리면 그 문서를 먼저 확인한다.

## 도구

`.scripts/bin/paper.py` (Python 표준 라이브러리만 사용, 설치 불필요):

```bash
python3 .scripts/bin/paper.py search "query" --source arxiv --limit 10   # arXiv 검색
python3 .scripts/bin/paper.py search "query" --source s2 --limit 10      # Semantic Scholar (인용수 포함)
python3 .scripts/bin/paper.py meta 1706.03762                             # arXiv ID / DOI / S2 ID → 메타데이터 + BibTeX
python3 .scripts/bin/paper.py pdf 1706.03762 --out 01-Papers/pdfs/other   # 지정 카테고리로 PDF 다운로드
python3 .scripts/bin/paper.py refs 1706.03762 --limit 30                  # 이 논문이 인용한 문헌
python3 .scripts/bin/paper.py cites 1706.03762 --limit 30                 # 이 논문을 인용한 문헌
```

API가 막히거나 결과가 빈약하면 웹 검색 후 URL 본문을 읽어 보완한다. 호스트별 도구는 AGENTS.md 어휘표를 따르고, 허용 도메인은 `.scripts/docs/search-protocol.md`를 참고한다.

## 검색 전략 (요약 — 상세는 `.scripts/docs/search-protocol.md`)

학술대회 후보와 venue 확인에 `01-Papers/reference/cs-conferences.csv`를 참고한다. 목록 밖 논문도 관련성이 있으면 포함하고, 실제 게재 여부는 공식 출처로 확인한다.

1. **질의를 분해한다.** 사용자의 한 문장을 (a) 방법 용어, (b) 태스크·도메인 용어, (c) 동의어·이전 세대 용어로 나눈다. 분야 용어는 몇 년 단위로 바뀌므로 한 표현만 쓰면 놓친다.
2. **영어로 검색한다.** 사용자가 한국어로 물어도 질의는 영어로 만든다.
3. **최소 2개 소스**를 돌린다. arXiv는 최신·프리프린트에 강하고, Semantic Scholar는 인용수·피어리뷰 게재 정보에 강하다. S2가 429(rate limit)면 arXiv/OpenAlex로 수동 전환한다 — `search` 명령엔 자동 폴백이 없다.
4. **앵커 논문에서 확장한다(스노우볼링).** 좋은 논문 1~3편을 찾으면 `refs`(후방)와 `cites`(전방)로 넓히는 게 키워드 검색보다 효율이 높다 — 용어가 달라졌거나 초록에 핵심어가 없는 논문은 여기서 잡힌다. 관련 연구 맵이 필요하면 `related-work` 스킬로 넘긴다.
5. **포화하면 멈춘다.** 새 질의·앵커를 돌려도 이미 나온 논문만 반복되면 그 방향은 종료한다.
6. **한계를 보고한다.** 실제 사용한 질의·소스, 스노우볼링에 쓴 앵커, 검색이 특정 연도·용어에 치우친 지점을 결과와 함께 말한다. 빈약한 결과를 그럴듯하게 포장하지 않는다.

## 결과 제시

표로 준다 — 제목 / 저자(제1저자 외 n인) / venue·연도 / 인용수 / arXiv ID / 한 줄 요지 / **왜 이 요청에 관련되는가**.

관련도 순으로 정렬하고, 관련 없어 보이는 것은 목록에서 뺀 뒤 뺐다고 말한다. 인용수는 정보일 뿐 품질 판정이 아니다 — 최신 논문은 구조적으로 인용수가 낮다.

**모든 항목은 실제 검색 결과여야 한다.** 기억으로 논문을 채워 넣지 않는다. 존재를 확인하지 못한 논문은 목록에 올리지 않는다.

## WebUI 탐색 검색

WebUI `#/discover` 검색 작업(`discovery.search`)은 `paper-searcher` 역할이 이 프로토콜을 그대로 실행한다. 저장소가 아닌 임시 작업 공간에 `paper.py`, `search-protocol.md`, 이 파일, `cs-conferences.csv`, 라이브러리 목록, 요청·기준 논문 JSON을 복사해 두고 실행하며, 에이전트는 파일을 저장하지 않고 `.scripts/docs/discovery-search.schema.json` 형식의 JSON(검색 보고와 후보)만 돌려준다. 서버가 그 결과를 검증해 Git에서 제외된 캐시 `00-Inbox/discovery/searches/`에 기록한다. 캐시 후보는 채택 전 검색 결과다. PDF·Keep·인덱스·논문 JSON 저장은 사용자가 채택한 뒤에만 한다.

## WebUI 채택: Keep에 담기와 등록

WebUI 후보 카드의 채택 버튼은 두 가지다. 정본 파일(`keep.md`, `01-Papers/library/*.json`, `01-Papers/pdfs/`, `01-Papers/index.md`, 위키 로그)은 에이전트가 아니라 **서버가** 고정된 형식으로 쓴다. 채팅에서 같은 후보를 다시 수집하지 않는다.

| 동작 | 쓰는 파일 | 하지 않는 것 |
|---|---|---|
| **Keep에 담기** (가벼움, 에이전트 없음) | `keep.md` 항목(`상태: 킵`, `PDF: 없음`, 이유는 관련 이유로 미리 채운 입력값) + `library/{slug}.json`(`reading_status: keep`, `metadata_status: partial`) | PDF 다운로드, `index.md` 행, 위키 로그 |
| **등록** (완전 등록, `discovery.register` 작업) | 카테고리 선택 후 `pdfs/{category}/{slug}.pdf`(구했을 때만) + `library/{slug}.json` + `keep.md` 항목 + `index.md` `읽을 예정` 행 + `wiki.py index`·`log --op ingest` | 페이월 우회, 리뷰 작성 |

- **slug**는 `{연도}-{제1저자 성}-{제목 슬러그}`(연도가 없으면 `0000`)이고, `keep.md` 항목 형식은 `keep-list` 스킬의 "논문 항목 형식"(정본은 `webui/discovery.py`의 `KEEP_ENTRY`)이다.
- **중복**: 라이브러리에 같은 arXiv id·DOI·S2 id나 정규화 제목이 있으면 두 동작 모두 거부한다(`already_in_library`). Keep은 `keep.md`에 같은 제목·식별자가 있어도 거부한다(`already_in_keep`). 예외로 Keep만 한 논문(레코드가 `reading_status: keep`, PDF 없음, 리뷰 전)은 등록할 수 있으며, 같은 slug·JSON을 보강하고 기존 `keep.md` 항목의 `PDF:` 줄만 고치고, 같은 제목의 `index.md` 행이 없을 때만 행을 넣는다.
- **등록 에이전트 규칙**(`paper-searcher` 등록 모드, 제한 10분): 임시 작업 공간의 `candidate.json`, `paper.py`, `search-protocol.md`만 쓰고 결과 파일은 작업 공간의 `out/`에만 둔다. arXiv 후보는 `python3 paper.py pdf <id> --out out`으로, 그 밖에는 허용 도메인의 **공식 또는 오픈액세스** PDF만 내려받는다. 페이월·로그인·우회 사이트는 쓰지 않고, 구하지 못하면 PDF를 `null`로 둔다. 게재 정보는 공식 출처로 다시 확인하고, 주제 키워드와 초록 기반 한 줄 요지(판단 금지)를 `.scripts/docs/discovery-register.schema.json` 형식 JSON으로만 돌려준다.
- **서버 게시**: 서버가 리뷰 큐를 다시 확인하고, PDF를 검사(`out/` 아래의 비어 있지 않은 일반 파일, `%PDF` 시작, 50 MiB 이하)한 뒤 정본 경로에 복사하고(같은 경로의 기존 파일은 덮어쓰지 않고 재사용), `paper_record.py init`·`validate`로 JSON을 만들고, `keep.md`·`index.md`·위키를 갱신한다. 중간에 실패하면 이번에 만든 JSON·PDF를 지운다. 위키 갱신 실패는 등록을 되돌리지 않고 경고로만 남긴다.
- **메타데이터만 등록**: PDF를 구하지 못했거나 받은 파일이 검사를 통과하지 못하면 등록을 실패시키지 않고 `pdf_path: null`로 등록하며 `keep.md`는 `PDF: 없음`이다. 라이브러리 카드에 "PDF 필요"가 표시되며, 원문은 나중에 사용자가 직접 넣는다.
- **리뷰 큐 보호**: 리뷰 큐에 대기·진행 중 작업이 있으면 등록은 `index.md`를 보호하려고 거부된다(409 `review_active`). Keep은 `index.md`를 건드리지 않으므로 리뷰 중에도 된다.
- 리뷰는 등록 뒤 라이브러리의 "리뷰 시작"으로 한다. Keep만 한 논문은 `index.md` 행이 없으므로 리뷰 전에 등록하거나 `review-index`로 인덱스를 보완한다.

## 업로드·채택 논문 수집 (채팅)

채팅에서 업로드하거나 채택한 논문은 아래 절차로 수집한다. WebUI 채택은 위 절을 따르며 서버가 저장한다. PDF 첫 페이지에서 제목·저자·연도·venue를 확인하고, 가능하면 DOI/arXiv ID로 교차 확인한다. 출처가 불명확한 값은 지어내지 않고 `unknown` 또는 `[확인 필요]`로 표시한다.

1. 기존 `01-Papers/library/*.json`, 인덱스, PDF를 paper ID와 정규화한 제목으로 확인한다. 중복이면 레코드를 추가하지 말고 출처와 PDF 경로만 보강한다.
2. PDF를 `01-Papers/pdfs/{category}/{연도}-{제1저자성}-{짧은슬러그}.pdf`에 보관한다. 기존 원본은 임의로 삭제하지 않는다.
3. `01-Papers/keep.md`에 `상태: 킵`(형식은 `keep-list` 스킬의 "논문 항목 형식"), `01-Papers/index.md`에 `읽을 예정`으로 등록한다.
4. `01-Papers/library/{slug}.json`을 만든다. 기본 레코드는 `.scripts/bin/paper_record.py init`으로 생성하고 확인된 메타데이터·초록·태그·출처·PDF 경로를 채운다. 새 파일은 `python3 .scripts/bin/paper_record.py validate <path>`로 검증한다. 기존 JSON은 덮어쓰지 않는다.
5. PDF·Keep·인덱스·JSON 저장이 끝나면 `python3 .scripts/bin/wiki.py index`로 위키 인덱스를 갱신하고 `python3 .scripts/bin/wiki.py log --op ingest --title "<논문 제목>" --path <JSON 경로>`로 기록한다.

검색 결과를 채팅으로만 제시해 달라는 경우에는 PDF 다운로드, Keep 등록, JSON 생성을 하지 않는다. 사용자가 채팅에서 검색 후보를 채택하면:

1. 메타데이터와 내용을 바탕으로 주 카테고리(`wifi-csi`, `game-ai`, `agent-ai`, `computer-vision`, `other`)를 먼저 정한다. `python3 .scripts/bin/paper.py pdf <id> --out 01-Papers/pdfs/{category}`로 PDF를 정본 경로에 저장한다.
2. `meta`로 BibTeX를 확보해 리뷰 프론트매터에 쓸 필드를 정리한다.
3. arXiv 버전이 있고 최종 게재본이 따로 있으면 둘 다 기록하고 어느 쪽을 읽는지 명시한다 (버전 간 내용이 다를 수 있다).
4. PDF가 페이월이면 다운로드를 시도하지 말고 사용자에게 알린다. 우회하지 않는다.
5. Keep 목록, 인덱스, 논문 JSON을 `읽을 예정` 상태로 등록한다. JSON 구조는 [.scripts/docs/paper-record.schema.json](../../../.scripts/docs/paper-record.schema.json)을 따른다.
6. 저장을 마치면 위 5번과 같이 `wiki.py index`와 `wiki.py log --op ingest`를 실행한다.
