# Notion 연구 하네스 안내

[Notion 문서 허브](https://app.notion.com/p/3e394f51302781e8b175fdb400f7c3e3)에 2026-10-07 기준으로 기능별 설명을 정리했다.

- 7개 상위 안내와 기능별 하위 페이지: 총 52개
- 설치된 프로젝트 스킬 15개, 운영 문서·템플릿·페르소나·검증 계약
- HTML 도식 4개: 전체 실행, 사고실험, 데이터 관리, 운영 루프
- PPT용 3200×1800 PNG, 개별·통합 PDF, 발표용 ZIP
- 문서 원본 50개 ZIP과 SHA-256 목록

## 정본과 범위

이 폴더는 설명 자료의 로컬 사본이다. 실제 연구 상태는 기존 논문 JSON, 기획·실험 기록, 작업 대기열과 지정 진척 backend를 따른다. Notion 안내 페이지를 수정해도 실행 지침이나 연구 상태가 자동으로 변경되지 않는다.

개별 논문 PDF·연구 원자료·개인 인증 파일은 업로드하지 않았다. 기존 Jev 승인 상태와 Notion 연결 안내의 불일치는 운영 페이지에서 확인 대상으로 남겼다. 기존 원장을 수정하거나 자동화를 실행하지 않았다.

## 생성·갱신

저장소 루트에서:

```sh
python3 .scripts/bin/notion_harness_docs.py
uv run --with playwright python .scripts/bin/render_harness_flows.py
```

첫 명령은 설명 사본·도식·문서 ZIP을 만든다. 두 번째는 선택 발표 도구인 Playwright/Chromium으로 PNG·개별 PDF를 만든다. 연구 실행기의 필수 의존성을 추가하지 않는다. 통합 PDF는 개별 PDF를 순서대로 합친 결과다.

Notion 업로드는 위 생성기가 수행하지 않는다. 페이지 ID·URL은 `notion-publication.json`, 원본 해시는 `source-manifest.json`에 기록했다. 갱신할 때 기존 페이지를 확인하고 필요한 내용만 수정한다. 같은 페이지를 중복 생성하지 않는다.

도식은 [HTML 흐름도 목록](../../100-views/harness-flows/index.html)에서 열 수 있다.

## 확인 범위

브라우저 렌더링에서 네 도식의 카드 텍스트 넘침이 없음을 확인하고 PNG를 직접 열어 확인했다. Notion 상위·하위 페이지 구조와 HTML·PNG·PDF·ZIP 첨부는 API 재조회로 확인했다. Notion 앱의 iframe 내부 화면은 GUI에서 별도로 확인하지 않았다.
