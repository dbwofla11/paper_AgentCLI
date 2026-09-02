---
name: paper-relations
description: Use Graphify to discover and verify relationships among the paper PDFs in this repository, then report an evidence-grounded research map in chat and notes. Trigger for requests about paper connections, lineage, shared methods or datasets, extensions, contradictions, or research landscape.
---

# Paper Relations

저장소의 `papers/**/*.pdf`를 Graphify 지식 그래프로 연결하고, 논문 간 관계를 원문 근거와 함께 검증한다. Graphify의 그래프는 탐색 후보를 만드는 도구이며, 그래프 경로만으로 인용·영향·확장 관계를 단정하지 않는다.

## 전제와 설치

- 프로젝트에 설치된 Graphify 스킬(`.codex/skills/graphify/SKILL.md`)을 먼저 따른다. Graphify는 PDF를 포함한 문서에서 관계를 추출하고 `graphify query`, `graphify path`, `graphify explain`으로 그래프를 질의한다.
- 설치가 빠졌으면 공식 패키지와 Codex 프로젝트 등록을 사용한다.

  ```bash
  uv tool install 'graphifyy[pdf]'
  graphify install --project --platform codex
  ```

- Codex에서는 Graphify의 `$graphify` 흐름을 사용한다. 논문만 대상으로 첫 그래프를 만들 때는 프로젝트 루트에서 `$graphify papers --mode deep --directed --no-viz`를 사용하고, 기존 그래프에는 `$graphify papers --update --mode deep --directed --no-viz`를 사용한다.
- PDF 의미 추출은 모델 호출이 필요할 수 있다. 추출이 비어 있거나 실패하면 API 키나 내용을 추측하지 말고 `원문 PDF 의미 추출 실패`를 보고한다. 그래프에 없는 관계를 채우지 않는다.

## 분석 절차

1. **대상 확정** — 사용자가 지정한 논문을 `papers/`, `library/index.md`, `reviews/`, `notes/`의 메타데이터와 대조한다. 모호하면 제목만으로 고르지 않고 `[확인 필요]`로 남긴다. 전체 관계를 요청하면 `papers/**/*.pdf`를 대상으로 한다.

2. **그래프 생성·갱신** — Graphify를 논문 PDF 폴더에만 적용한다. 출력 그래프가 이미 있으면 변경 파일만 갱신하고, 첫 실행이면 `--mode deep`로 간접적인 관계 후보도 수집한다. 생성된 `graphify-out/graph.json`의 `source_file`, `source_location`, `confidence`를 보존한다.

3. **관계 후보 질의** — 다음 질의를 조합한다.

   ```bash
   graphify query "which papers cite or build on each other"
   graphify query "which papers share methods datasets assumptions or evaluation metrics"
   graphify path "<논문 A 노드>" "<논문 B 노드>"
   graphify explain "<논문 노드>"
   ```

   `query`가 노드명을 찾지 못하면 Graphify의 실제 vocabulary를 먼저 확인한다. 없는 동의어·노드명을 만들어 질의하지 않는다. `path`는 연결 경로를 보여주는 것일 뿐 관계의 방향이나 인과를 보장하지 않는다.

4. **원문 검증** — 후보 관계마다 양쪽 논문의 공식 메타데이터와 PDF 본문을 확인한다. 필요하면 `python scripts/paper.py refs <id>`와 `python scripts/paper.py cites <id>`로 인용망을 교차 확인한다. 관계를 다음처럼 판정한다.

   | 관계 | 판정 기준 |
   |---|---|
   | 선행 인용 (`cites` / `references`) | 본문 또는 참고문헌에 직접 확인된 인용. 위치를 붙인다. |
   | 방법 확장 (`extends`) | 후속 논문이 선행 방법을 명시적으로 기반으로 삼고 무엇을 바꿨는지 원문에서 확인한다. |
   | 반박·불일치 (`contradicts`) | 후속 논문이 선행 주장·결과와 다르다고 명시하거나 동일 조건의 반대 결과를 제시할 때만 사용한다. |
   | 공유 방법·데이터 (`shares_method` / `shares_data`) | 두 논문이 같은 모델·학습 절차·데이터셋을 실제로 사용한다고 각 원문에서 확인한다. 이름이 비슷한 경우는 제외한다. |
   | 개념적 유사 (`semantically_similar_to`) | Graphify가 공통 개념을 추론했지만 직접 인용·영향은 원문에서 확인되지 않은 경우. 반드시 `INFERRED`와 `[확인 필요]`를 붙인다. |

5. **근거와 확신 표시** — `EXTRACTED`는 출처에 관계가 명시된 경우, `INFERRED`는 Graphify가 추론한 후보, `AMBIGUOUS`는 판정 불가로만 사용한다. 모든 행에 원문 링크와 PDF 위치(`§`, `p.`, `Table`, `Eq.` 등)를 붙인다. Graphify 위치만 있고 원문 검증이 안 된 관계는 확정 문장으로 쓰지 않는다.

## 산출물

관계 분석을 요청받은 날짜 기준으로 `notes/paper-relations/{YYYY-MM-DD}.md`에 저장한다. 기존 파일이 있으면 새 근거가 확인된 부분만 갱신하고 기존 출처를 보존한다.

```markdown
# 논문 관계 맵 — YYYY-MM-DD

## 분석 범위
- 대상 PDF:
- Graphify 버전·실행:
- 원문 검증 범위:

## 관계 요약
| 논문 A | 관계 | 논문 B | 확신 | 근거 |
|---|---|---|---|---|

## 관계별 해석
### 선행·후속
### 방법·데이터·평가의 공유
### 개념적 유사성 및 확인 필요 항목

## 그래프 한계
- 그래프가 보여주지만 원문에서 확인하지 못한 것
- 인용 방향·인과·영향으로 오해하면 안 되는 것
```

## 채팅 보고

파일만 만들고 끝내지 않는다. 분석 후 채팅에 핵심 관계를 표 또는 짧은 목록으로 보여준다. 각 관계에 `논문 A → 관계 → 논문 B`, `EXTRACTED/INFERRED/AMBIGUOUS`, 원문 위치, 왜 중요한지를 포함한다. Graphify가 제시한 `INFERRED` 관계는 반드시 `[추론]` 또는 `[확인 필요]`로 표시한다.

## 저장소·Git 규칙

- 원문 PDF는 수정하지 않는다. 관계 맵과 Graphify 설정·스킬만 해당 회차의 변경으로 취급한다.
- 기존 사용자 변경사항을 stage하지 않는다. Graphify 산출물(`graphify-out/`)은 관계 맵 재현에 필요할 때만 포함하고, 대형 HTML은 기본적으로 커밋하지 않는다.
- 사용자에게 관계 분석을 보여준 뒤 현재 회차 변경만 명시적으로 stage하고, 검증 후 커밋한다. 이 저장소의 push 규칙에 따라 성공한 커밋은 `git push origin master`로 올린다. 인증·네트워크 오류가 나면 커밋을 보존하고 실패 원인을 보고한다.

## 금지 사항

- 제목·공통 키워드·같은 커뮤니티만으로 인용, 영향, 확장, 반박을 단정하지 않는다.
- Graphify의 `INFERRED` edge를 원문에 명시된 사실처럼 바꾸지 않는다.
- PDF를 읽지 못한 상태에서 메소드·데이터셋·결과·관계를 채우지 않는다. 필요한 경우 `[확인 필요]`로 남긴다.
