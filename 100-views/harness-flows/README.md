# 발표용 하네스 흐름도

흰 배경 16:9 HTML 도식이다. Notion에서 좁은 화면에 맞춰 축소해 표시하며, PPT에는 `assets/`의 3200×1800 PNG를 사용할 수 있다.

| 파일 | 내용 |
|---|---|
| `01-overview.html` | 규칙·문서·스킬이 논문 읽기에서 실험 설계로 이어지는 흐름 |
| `02-thought-experiment.html` | Grill-me·기획 승인·동일 근거·세 심사·사용자 결정 |
| `03-data-flow.html` | PDF·리뷰·JSON·목록·가설·심사·실행 증거의 저장 |
| `04-operation-loops.html` | 일일 후보 루프와 HTML 리뷰 브리지 실행 |

생성기는 `.scripts/bin/notion_harness_docs.py`, 이미지·PDF 출력은 `.scripts/bin/render_harness_flows.py`다. 상세 운영과 Notion 페이지 목록은 `docs/notion-harness/README.md`에 있다.

설명 도식이며 실시간 실행 상태 화면은 아니다. 새 실행을 시작하는 버튼은 제공하지 않는다.

## 디자인

[DESIGN-figma.md](../../docs/design/DESIGN-figma.md)의 흰 배경·검은 글자·파스텔 패널을 적용한다. 공통 도식 CSS는 `../assets/harness-flow.css`이며 생성기가 HTML에 포함한다. HTML만 옮겨도 도식 디자인을 유지한다.
