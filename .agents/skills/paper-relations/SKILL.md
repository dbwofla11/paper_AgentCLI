---
name: paper-relations
description: 저장소 논문들의 계보·공유 방법·데이터·확장·반박 관계를 Graphify와 원문으로 확인한다. 논문 간 연결이나 연구 지형 요청에 사용.
---

# Paper Relations

Graphify는 관계 후보를 탐색하는 지도다. 그래프 경로만으로 인용·영향·확장·반박을 확정하지 않는다. 확정 관계는 양쪽 논문의 원문으로 확인하고 각 논문의 `01-Papers/library/{slug}.json`에 근거와 함께 기록한다.

## 자료와 탐색

1. 대상 논문을 JSON paper ID, `01-Papers/index.md`, PDF, 리뷰와 대조한다. JSON이 아직 없으면 확인된 메타데이터만으로 먼저 만든다.
2. 저장소 그래프가 있으면 `$graphify` 규칙에 따라 `graphify query`, `path`, `explain`으로 논문·주장·방법·데이터 관계 후보를 찾는다. 문서 변경 뒤 갱신할 때는 `graphify_sync.py begin` 후 Graphify 스킬 `.` `--update`를 실행한다. 단순 `graphify update .` CLI는 AST 변경만 반영할 수 있으므로 문서 의미 추출 완료로 취급하지 않는다.
3. 각 후보의 논문 양쪽에서 PDF 원문과 인용을 확인한다. 필요하면 `.scripts/bin/paper.py refs <id>` 및 `cites <id>` 결과를 교차 확인한다.
4. 확정 가능한 관계만 JSON `relationships`에 추가한다. 관계 유형은 `supports`, `contradicts`, `extends`, `compares`, `uses`, `cites`, `related_to` 중에서 고르고 `statement`와 출처 위치를 보존한다.
5. Graphify만 제안했거나 한쪽 원문만 확인한 관계는 JSON에 확정 사실로 저장하지 않는다. 채팅에서는 `INFERRED` 또는 `AMBIGUOUS`로 표시하고 `[추론]` / `[확인 필요]`를 붙인다.
6. 수정한 JSON은 `python3 .scripts/bin/paper_record.py validate <path>`로 검사한다. Graphify update 성공 뒤 `graphify_sync.py complete`로 기록하고, 실패하면 `fail`로 pending 사유를 남긴다.

## 근거 판정

| 관계 | 확인 기준 |
|---|---|
| `cites` | 참고문헌 또는 본문에서 직접 인용 확인 |
| `extends` | 후속 논문이 선행 방법을 기반으로 삼고 바꾼 점을 명시 |
| `contradicts` | 같은 주장·조건에 대한 명시적 반박 또는 반대 결과 확인 |
| `uses` | 같은 모델·절차·데이터를 실제로 사용한다고 양쪽 원문에서 확인 |
| `compares` | 논문이 해당 방법을 비교 기준으로 실험에 사용 |
| `supports` | 관계된 주장을 지지하는 원문 결과와 위치 확인 |
| `related_to` | 주제상 연관은 확인했으나 위의 구체 관계는 확인되지 않음 |

모든 evidence에는 `locator`(예: `§3.2`, `p.7, Table 4`)와 `source`(PDF 상대 경로 또는 공식 URL)를 넣는다. Graphify의 추출 상태와 원문 검증 상태를 혼동하지 않는다.

## 보고

채팅에 `논문 A → 관계 → 논문 B`, 검증 상태, 근거 위치, 연구상 의미를 간결하게 보고한다. 추가 Markdown 관계 노트나 Git commit/push는 만들지 않는다.
