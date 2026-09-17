# 논문 PDF 보관 규칙

PDF는 논문의 **주 카테고리**별 하위 디렉터리에 보관한다.

| 경로 | 포함 기준 |
|---|---|
| `wifi-csi/` | WiFi CSI와 직접 연결된 WiFi sensing·RF sensing |
| `game-ai/` | 게임 플레이·게임 agent·게임 생성·게임 분석 |
| `agent-ai/` | 자율/LLM agent, tool use, planning, agent orchestration |
| `computer-vision/` | image/video/3D visual perception·recognition·generation |
| `other/` | 위 네 범주에 속하지 않는 AI/ML/CS 논문 |

여러 범주에 걸치는 논문은 핵심 입력·task·방법을 기준으로 하나의 주 카테고리만 선택한다. 파일명은 `{연도}-{제1저자성}-{짧은슬러그}.pdf` 형식의 소문자 하이픈 표기를 따른다. 새 리뷰·즐겨찾기·노트에서는 `01-Papers/pdfs/{category}/{파일명}.pdf` 경로를 사용한다.

이전 날짜별 업로드 기록은 [UPLOAD_LOG.md](UPLOAD_LOG.md)에 보존한다.
