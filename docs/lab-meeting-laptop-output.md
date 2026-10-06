# 노트북 랩미팅 PPT 제작 결과

Orca의 `laptop` 환경에서 Windows PowerPoint로 발표자료를 생성했다. PPT를 로컬 데스크톱에서 생성해 복사한 것이 아니라 노트북의 PowerPoint가 직접 생성·PDF 저장·장별 PNG 내보내기를 수행했다.

- 저장 폴더: `C:\Users\Asus\Desktop\research-harness-lab-meeting-20261006`
- 발표자료: `research-harness-lab-meeting.pptx`
- PDF: `research-harness-lab-meeting.pdf`
- 전체 미리보기: `gallery.html`
- 장별 미리보기: `preview/slide-01.png` ~ `preview/slide-12.png`
- 재생성 소스: `build.ps1`, `deck.json`
- 생성 기록: `creation-receipt.json`

12장, 16:9, 한국어. 도식은 수정 가능한 PowerPoint 도형과 텍스트다. 각 장에 발표자 설명을 포함했다. 세 운영 화면의 실제 캡처를 포함하고, 사용 흐름 예시와 실제 완료 성과는 구분했다. 효과 수치는 넣지 않았다.

노트북 생성 기록은 2026-10-06 15:00:20 +09:00이며 슬라이드 수는 12다. PDF와 12장 PNG 내보내기까지 완료했다. 일부 미리보기를 시각적으로 살펴보고 좁은 카드의 문구와 밝은 배경의 글자 대비를 수정했다. 새 테스트는 실행하지 않았다.

원본 내용: [슬라이드별 내용 초안](lab-meeting-slide-content.md). 구성: [발표자료 계획](lab-meeting-presentation-plan.md).

## 흰색 배경 버전

사용자 요청에 따라 2026-10-06 15:03:28 +09:00에 노트북 PowerPoint에서 흰색 배경 버전을 생성했다. 글자색은 짙은 색, 카드는 밝은 색으로 맞추고 페이지 제목을 간소화했다.

- PPT: `research-harness-lab-meeting-white.pptx`
- PDF: `research-harness-lab-meeting-white.pdf`
- 전체 미리보기: `gallery-white.html`
- 장별 미리보기: `preview-white/`
- 재생성 소스: `build-white.ps1`, `deck-white.json`

제목: 연구 작업 체계 / 도입 배경 / 전체 구성 / 논문 수집 / 논문 정독 / 학습 기록 / 아이디어 검토 / 조사와 실험 / 운영과 공유 / 사용 예시 / 구현 현황 / 평가 계획.

## 목차·범주·소제목 버전

2026-10-06 15:07:59 +09:00에 노트북 PowerPoint에서 16장 버전을 생성했다.

- 발표 제목: **논문 읽기에서 연구 검증까지**
- 표지 다음에 목차 추가.
- 중간 구분 페이지: **논문 탐색·학습 / 아이디어·검증 / 운영·평가**.
- 각 본문 상단에 현재 범주와 소주제 표시.
- 흰색 배경과 간결한 본문 제목 유지.
- PPT: `research-harness-lab-meeting-organized.pptx`
- PDF: `research-harness-lab-meeting-organized.pdf`
- 전체 미리보기: `gallery-organized.html`
- 장별 미리보기: `preview-organized/`
- 재생성 소스: `build-organized.ps1`, `deck-organized.json`

순서: 표지 → 목차 → 도입 배경 → 전체 구성 → 논문 탐색·학습(구분) → 논문 수집 → 논문 정독 → 학습 기록 → 아이디어·검증(구분) → 아이디어 검토 → 조사와 실험 → 운영·평가(구분) → 운영과 공유 → 사용 예시 → 구현 현황 → 평가 계획.
