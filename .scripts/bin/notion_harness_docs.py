#!/usr/bin/env python3
"""Build source-backed Notion reference pages and presentation diagrams (no network writes)."""
from pathlib import Path
import hashlib
import html
import json
import re
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/notion-harness'
VIEWS = ROOT / '100-views/harness-flows'
DATE = '2026-10-07'
PAGES = []


def add(key, parent, title, body, sources=(), diagram=None):
    source_text = '\n'.join(f'- `{p}`' for p in sources)
    content = f'## 역할\n\n{body}\n\n## 근거 문서\n\n{source_text or "상위 페이지에 연결된 공통 규칙과 실행 지도"}\n\n기준일: {DATE}. 이 페이지는 저장소 설정을 설명하는 안내이며 실행 상태의 정본을 대체하지 않습니다.'
    PAGES.append(dict(key=key, parent=parent, title=title, content=content,
                      sources=list(sources), diagram=diagram))


def node(x, y, title, desc, source='', tone='blue', w=330, h=160):
    return f'<article class="node {tone}" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px"><h3>{html.escape(title)}</h3><p>{html.escape(desc)}</p><code>{html.escape(source)}</code></article>'


def arrow(points, label='', x=0, y=0, dashed=False):
    path = ' '.join(f'{a},{b}' for a, b in points)
    return f'<polyline points="{path}" class="edge {"dashed" if dashed else ""}" marker-end="url(#tip)"/>' + (f'<text x="{x}" y="{y}" class="edge-label">{html.escape(label)}</text>' if label else '')


def diagram(key, title, subtitle, nodes, edges, bands, foot):
    css = '''*{box-sizing:border-box}body{margin:0;background:#edf1f7;font-family:"Noto Sans CJK KR","Malgun Gothic",sans-serif;color:#142638}.slide{width:1600px;height:900px;background:#fff;position:relative;overflow:hidden;margin:0 auto}.head{position:absolute;left:58px;top:36px;right:58px}.eyebrow{font-size:18px;font-weight:700;letter-spacing:2px;color:#536be6}h1{font-size:42px;line-height:1.2;margin:10px 0 12px;letter-spacing:-1.5px}.sub{font-size:21px;color:#5a6879;margin:0}.band{position:absolute;left:42px;right:42px;border-radius:20px;background:#f5f7fc;border:1px solid #e6ebf3;padding:15px 18px;color:#63728a;font-size:17px;font-weight:700}.node{position:absolute;background:#fff;border:2px solid #cfdaf1;border-top:6px solid #536be6;border-radius:16px;padding:14px 18px;box-shadow:0 5px 15px #253c6510}.node h3{font-size:25px;line-height:1.35;margin:0 0 8px;letter-spacing:-.7px}.node p{font-size:18px;line-height:1.4;margin:0 0 8px;color:#46556a;word-break:keep-all}.node code{font-family:inherit;font-size:14px;line-height:1.3;color:#718197;display:block;overflow-wrap:anywhere}.green{border-color:#b7dcd2;border-top-color:#208b70;background:#f8fffc}.purple{border-color:#d4c7eb;border-top-color:#8a5ac4;background:#fdfbff}.amber{border-color:#ebd0a0;border-top-color:#cd8e22;background:#fffdf6}.gray{border-color:#d5dde7;border-top-color:#60748c}.links{position:absolute;inset:0;width:1600px;height:900px;pointer-events:none}.edge{fill:none;stroke:#7c8ba4;stroke-width:3;stroke-linejoin:round}.dashed{stroke-dasharray:9 7;stroke:#ae8040}.edge-label{font-family:inherit;font-size:16px;fill:#50617b;paint-order:stroke;stroke:#fff;stroke-width:7px;stroke-linejoin:round}.footer{position:absolute;left:58px;right:58px;bottom:27px;border-top:1px solid #e5eaf2;padding-top:14px;font-size:16px;color:#4f6075;line-height:1.5;display:flex;gap:24px}.number{margin-left:auto;white-space:nowrap;flex-shrink:0;color:#8b96a7;font-size:14px}@media print{@page{size:1600px 900px;margin:0}body{background:#fff}.slide{margin:0;break-after:page}}'''
    band_html = ''.join(f'<div class="band" style="top:{y}px;height:{h}px">{html.escape(label)}</div>' for y, h, label in bands)
    body = f'<main class="slide" aria-label="{html.escape(title)}"><header class="head"><div class="eyebrow">RESEARCH HARNESS · DOCUMENT FLOW</div><h1>{html.escape(title)}</h1><p class="sub">{html.escape(subtitle)}</p></header>{band_html}<svg class="links" viewBox="0 0 1600 900"><defs><marker id="tip" markerWidth="10" markerHeight="10" refX="8" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#7c8ba4"/></marker></defs>{"".join(edges)}</svg>{"".join(nodes)}<footer class="footer">{html.escape(foot)}<span class="number">{DATE} · {key}</span></footer></main>'
    responsive = '<script>function fit(){const s=Math.min(1,innerWidth/1600);const e=document.querySelector(".slide");e.style.transform="scale("+s+")";e.style.transformOrigin="top left";document.body.style.height=900*s+"px"}addEventListener("resize",fit);fit()</script>'
    document = f'<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><style>{css}</style>{body}{responsive}</html>'
    (VIEWS / f'{key}.html').write_text(document, encoding='utf-8')


def build_diagrams():
    diagram('01-overview', '논문 읽기에서 실험 설계까지', '규칙 문서가 방향을 정하고, 스킬이 작업을 수행하고, 사용자가 다음 단계를 결정한다.', [
        node(60, 235, '논문 수집', '출처·중복을 확인하고 원문과 기록을 등록', 'paper-search · search-protocol.md'),
        node(440, 235, '읽기 범위 결정', '1패스로 읽을 가치와 확인할 부분을 정함', 'triage-template.md'),
        node(820, 235, '심층 리뷰', '3패스 정독 · 5축 분석 · 주장과 근거 연결', 'paper-review · review-template.md'),
        node(1200, 235, '목록·문헌 정리', '완료 상태 확인 · 필요할 때 선행·후속 연구', 'review-index · related-work'),
        node(60, 535, '공부노트', '개념 후보를 읽고 이해를 확인한 뒤 승격 요청', 'concept-note · study-note-template.md', 'green'),
        node(440, 535, '사고실험', '질문으로 가설을 구체화하고 독립 심사', 'critical-validation · 3 critic personas', 'purple'),
        node(820, 535, '실험 설계·실행', '사용자 승인 후 작은 실험 · 조건과 결과 기록', 'thought-experiment-runner · manifest/results', 'green'),
        node(1200, 535, '결과·다음 질문', '관측값과 해석을 구분하고 다음 방향 결정', '사용자 결정 · 가설 보완', 'amber'),
    ], [
        arrow([(390,315),(440,315)]), arrow([(770,315),(820,315)]), arrow([(1150,315),(1200,315)]),
        arrow([(965,395),(965,460),(605,460),(605,535)], '연구 질문이 생기면', 650,451),
        arrow([(850,395),(850,420),(225,420),(225,535)], '개념 후보 + 이해 확인', 280,410,True),
        arrow([(770,615),(820,615)], '승인', 777,600), arrow([(1150,615),(1200,615)]),
        arrow([(1365,695),(1365,760),(605,760),(605,695)], '결과를 보고 가설·기획을 다시 보완', 790,749,True),
    ], [(175,245,'방향을 정하는 문서: AGENTS.md → docs/Harness-Graph.md → research_workflow.py / research-workflow-map.json'),
        (490,225,'리뷰 이후 선택 경로: 공부노트는 이해 확인 후 · 사고실험은 기획과 심사 후')],
        '검증된 논문 JSON·승인된 지식은 Graphify로 연결한다. HTML은 이 기록을 보여주는 화면이다.')
    diagram('02-thought-experiment', '사고실험: 질문에서 반증 가능한 기획으로', '현재 required 정책: 기획 승인과 세 독립 심사, 사용자 최종 결정을 거친 뒤 실험으로 진행한다.', [
        node(60,230,'아이디어 점검','전제·대체 설명·누수 위험을 먼저 확인','thought-experiment-critique','purple'),
        node(440,230,'Grill-me','문제·가설·성공 기준·반증 조건을 질문','critical-validation §1','amber'),
        node(820,230,'기획 승인','사용자 답변을 brief에 반영하고 확인','brief.md · 사용자 승인','amber'),
        node(1200,230,'문헌·근거 고정','지지·대안·반대 문헌 검색 후 해시 동결','analysis.json · evidence bundle','blue'),
        node(440,470,'방법 심사','인과 연결·대조군·반증 가능성','personas/method-critic.md','purple',h=145),
        node(820,470,'재현성 심사','데이터·seed·평가·정보 누수','personas/repro-critic.md','purple',h=145),
        node(1200,470,'새로움 심사','선행연구·단순한 대안·기여 범위','personas/novelty-critic.md','purple',h=145),
        node(60,690,'종합·상태 검사','세 결과·동일 해시·미해결 결함 확인','idea_analysis.py · critique.md','blue',w=430,h=125),
        node(585,690,'사용자 결정','진행 / 보완 / 보류 / 폐기','Grill-me로 돌아가 기획 수정','amber',w=430,h=125),
        node(1110,690,'작은 실험으로','승인 범위에서 조건·대조군을 실행','thought-experiment-runner','green',w=430,h=125),
    ], [
        arrow([(390,310),(440,310)]),arrow([(770,310),(820,310)]),arrow([(1150,310),(1200,310)]),
        arrow([(1365,390),(1365,455),(605,455),(605,470)]),arrow([(1365,455),(985,455),(985,470)]),arrow([(1365,455),(1365,470)]),
        arrow([(605,615),(605,648),(275,648),(275,690)]),arrow([(985,615),(985,648),(605,648)]),arrow([(1365,615),(1365,648),(985,648)]),
        arrow([(490,752),(585,752)]),arrow([(1015,752),(1110,752)],'승인',1040,739),
        arrow([(800,815),(800,833),(30,833),(30,220),(605,220),(605,230)],'보완: 사용자 답변 반영 → 새 근거 동결 → 세 심사 재실행',160,824,True),
    ], [(175,235,'준비: 진척 backend 확인 → mode 확인 · 최소 2개 문헌 소스 · brief 승인 전에는 심사하지 않음'),
        (420,220,'세 역할은 같은 근거 묶음을 독립·읽기 전용으로 검토한다. 서로의 초안과 사용자 선호는 보지 않는다.')],
        '조건부·치명 판정 또는 역할 누락이면 실험 후보로 올리지 않는다. 독립 실행이 불가능하면 심사 대기다.')
    diagram('03-data-flow','연구 자료는 어디에 저장되는가','원문·분석·기획·실행 증거를 분리하고, 파일 경로와 논문 ID로 연결한다.',[
        node(60,235,'PDF 원문','분야별 보관 · 원본은 수정하지 않음','01-Papers/pdfs/{category}/','gray'),
        node(440,235,'읽기 메모·리뷰','트리아지와 심층 리뷰를 별도 파일로 작성','01-Papers/triage/ · reviews/{category}/'),
        node(820,235,'논문 JSON','메타데이터 + 5축 분석 + 근거 + 관계','01-Papers/library/{slug}.json'),
        node(1200,235,'사람용 목록','읽기 상태 / 나중에 읽기 / 선호 논문','index.md · keep.md · favorites.md','green'),
        node(60,535,'가설 노트','핵심 질문·전제·반증 조건','05-ideas/thought-experiments/','purple'),
        node(440,535,'기획·심사 기록','brief · analysis · 근거 묶음 · critique','04-Projects/thought-experiment-runs/{slug}/','purple'),
        node(820,535,'실행 증거','조건·seed·환경·지표·실패·원자료 경로','같은 run 폴더의 manifest.md / results.md','green'),
        node(1200,535,'상태·작업 대기열','Notion 진척 또는 progress · 조사/리뷰 작업','research-todo/queue.json · review-queue/','amber'),
    ],[
        arrow([(390,315),(440,315)],'원문 읽기',390,224),arrow([(770,315),(820,315)],'분석 반영',770,224),arrow([(1150,315),(1200,315)],'상태·링크',1147,224),
        arrow([(605,395),(605,453),(225,453),(225,535)],'리뷰에서 생긴 연구 질문',255,443,True),
        arrow([(985,395),(985,470),(605,470),(605,535)],'원문 근거 연결',650,461),
        arrow([(390,615),(440,615)]),arrow([(770,615),(820,615)],'승인',777,600),arrow([(1150,615),(1200,615)]),
    ],[(175,245,'논문 자료: 사용자 업로드 / 후보 채택 → 메타데이터·중복 확인 → PDF + Keep + 인덱스 + JSON 등록'),
        (490,225,'사고실험 자료: 아이디어 정본과 실행 증거는 분리 · Notion 선택 시 로컬 progress는 상태 정본이 아님')],
        '검증된 정본 → Graphify 의미 동기화 · 정본 파일 → HTML 재생성. HTML과 그래프는 원문을 대체하지 않는다.')
    diagram('04-operation-loops','루프와 HTML 실행은 어떻게 연결되는가','예약 탐색, 사용자 선택, 리뷰 실행, 지식 갱신은 서로 다른 동작이다.',[
        node(60,235,'예약 시각·주제','Orca 매일 09:00 KST · 날짜별 주제 계획','daily-orca-automation.md · paper-scheduler','amber'),
        node(440,235,'후보 3편 검색','CV 1 · 멀티모달 1 · 관심 분야 1','daily-digest-loop'),
        node(820,235,'채팅으로 제시','공식 게재·원문 확인 · 채택 전 저장 없음','paper-summary 형식'),
        node(1200,235,'사용자가 채택','선택한 논문만 PDF·Keep·JSON 등록','paper-search','green'),
        node(60,535,'HTML 리뷰 요청','논문 하나를 선택하고 리뷰 시작','100-views/paper-library.html'),
        node(440,535,'본인 에이전트 연결','온보딩이 CLI·로그인·지원 옵션 확인','onboard_research.py · research_agent.py','amber'),
        node(820,535,'로컬 리뷰 실행','연결된 에이전트가 임시 폴더에서 정독','paper_review_bridge.py · paper-review'),
        node(1200,535,'검증 후 저장','리뷰·JSON·인덱스 저장 · 화면 재생성','paper_record.py · review queue','green'),
    ],[
        arrow([(390,315),(440,315)]),arrow([(770,315),(820,315)]),arrow([(1150,315),(1200,315)]),
        arrow([(390,615),(440,615)]),arrow([(770,615),(820,615)]),arrow([(1150,615),(1200,615)]),
        arrow([(1365,695),(1365,760),(225,760),(225,695)],'완료·실패·진행 상태를 HTML에서 다시 확인',480,747),
    ],[(175,245,'일일 후보 루프: 현재 예약 enabled=true / Asia/Seoul / 새 세션 · 실행 결과는 Orca 회차 채팅'),
        (490,225,'리뷰 실행 경로: 초기 온보딩 후 localhost 서버를 사용 · HTML 파일을 열기만 해서는 에이전트가 실행되지 않음')],
        '정본 변경 → graphify_sync begin → Graphify 의미 추출 → complete. 실패는 pending으로 남기고 재시도한다.')


def build_pages():
    add('reading',None,'논문 읽기','논문을 고르는 단계와 정독하는 단계를 연결한다. 검색 요약으로 리뷰를 쓰지 않고 실제 원문 위치를 근거로 남긴다.\n\n## 실행 흐름\n\n1. paper-search: 업로드·채택 논문 메타데이터와 중복 확인\n2. triage-template: 1패스 판정과 읽을 범위 결정\n3. paper-review: 3패스 정독, 방법 구조도와 5축 분석\n4. review-index: 리뷰·JSON·인덱스 경로와 완료 상태 정리\n5. 필요할 때 related-work 또는 paper-relations로 원문 관계 검증\n6. 검증된 정본을 Graphify에 동기화\n\n## 왜 만들었는가\n\n읽은 내용을 다시 찾고, 저자의 주장과 실제 증거를 분리하고, 재현에 필요한 방법·평가 조건을 빠뜨리지 않기 위해서다.', ['AGENTS.md','docs/Harness-Graph.md','90-Templates/paper/review-template.md'])
    add('thought',None,'사고실험','아이디어를 질문과 반증 조건이 있는 기획으로 바꾼다. 비판적 사고, Grill-me, 독립 심사, 사용자 의견 반영을 이 페이지 아래에서 관리한다.\n\n## 각 하네스가 하는 일\n\n- thought-experiment-critique: 전제·누수·식별가능성·대체 설명을 처음 점검한다.\n- critical-validation: Grill-me로 사용자 답변을 brief에 반영하고, 문헌과 동일 근거 묶음을 준비한다.\n- method / repro / novelty critic: 같은 근거를 각 관점에서 독립적으로 비판한다.\n- idea_analysis.py: 근거 해시·역할 완결성·판정·사용자 결정 일관성을 검사한다.\n- thought-experiment-runner: 승인된 계획만 작은 실험과 실행 증거로 연결한다.\n\n## 사용자 의견 반영\n\n핵심 가설·성공/반증 조건은 사용자 승인 뒤 심사한다. 보완 요청은 다시 Grill-me로 돌아간다. 근거가 변경되면 동결 버전과 기존 심사를 갱신한다. 최종 진행·보류·폐기는 사용자가 결정한다. 매 실험마다 자동 질문하는 주기는 별도로 정의되어 있지 않다.\n\n## 현재 적용 범위\n\nmode는 required다. 세 페르소나는 분야 공통이며 분야별 전문 페르소나는 없다. 일반 논문 리뷰에 세 독립 심사가 자동 적용되는 상태도 아니다.', ['.agents/skills/critical-validation/SKILL.md','04-Projects/thought-experiment-runs/CRITICAL_VALIDATION_SETTINGS.md'], '02-thought-experiment')
    add('experiment',None,'실험 설계','실험을 시작하기 전에 성공·반증 기준, 최소 대조군, 데이터·seed·정보 경계·컴퓨트를 고정한다. 결과를 본 뒤 기준을 임의로 바꾸지 않고 관측값과 해석을 구분한다.\n\n## 실행과 기록\n\n1. 승인된 brief와 심사 결과를 확인한다.\n2. 기본 범위는 단일 가설, 12개 이하 condition, 고정 seed의 작은 결정론적 실험이다.\n3. manifest.md에 조건 ID·입력·환경·버전·기준을 남긴다.\n4. results.md에 criterion별 측정·누락·실패·원자료 경로를 남긴다.\n5. 사람이 결과를 보고 가설 채택·변경과 다음 실험을 결정한다.\n\n## 실행 조건\n\n기존 실행 가능한 코드·데이터가 있어야 한다. 새 의존성·대규모 다운로드·장시간 학습·유료 API는 기본 소규모 실행 범위에 포함되지 않는다. Paper2Agent는 준비성을 점검하며 실제 agentification은 별도 생성 요청이 필요하다.', ['.agents/skills/thought-experiment-runner/SKILL.md'])
    add('data',None,'데이터 저장·관리','원문 PDF, 사람용 리뷰, 기계 판독 JSON, 가설, 실행 증거를 각각 정본 경로에 보관한다. 이 Notion 공간에는 운영 안내와 도식을 정리하며 개별 논문 PDF나 연구 데이터 전체를 복제하지 않는다.\n\n## 논문 저장\n\n- 원문: 01-Papers/pdfs/{category}/\n- 리뷰: 01-Papers/reviews/{category}/ · 한 논문 한 파일\n- 첫 판정: 01-Papers/triage/\n- 구조화 기록: 01-Papers/library/{slug}.json\n- 읽기 상태: index.md · 읽기/조사 대기열: keep.md · 선호: favorites.md\n\n분야는 wifi-csi / game-ai / agent-ai / computer-vision / other다. 파일명은 연도-제1저자성-짧은슬러그를 따른다. JSON은 수집 시 메타데이터를 기록하고 리뷰 후 근거가 있는 5축 분석을 보강한다.\n\n## 사고실험 저장\n\n- 가설·반증 조건: 05-ideas/thought-experiments/\n- 기획·심사·실행 증거: 04-Projects/thought-experiment-runs/{slug}/\n- 문헌 조사 작업: 04-Projects/research-todo/queue.json\n- 자동 리뷰 작업: 04-Projects/review-queue/queue.json\n- 현재 진척 backend: notion · repository 선택 시 progress.md가 상태 정본\n\n## 재생성\n\nHTML은 정본에서 다시 만든다. Graphify는 검증된 정본에서 관계를 추출한다. 개념 후보는 사용자가 이해를 확인하고 승격 요청하기 전에는 학습 정본·지식 그래프로 들어가지 않는다.', ['AGENTS.md','.scripts/docs/paper-record.schema.json','.scripts/docs/idea-analysis.schema.json','04-Projects/thought-experiment-runs/PROGRESS_BACKEND.md'], '03-data-flow')
    add('ops',None,'루프·운영 설정','시각 예약, 날짜별 선정 기준, 에이전트 연결, 작업 대기열, 지식 동기화를 나누어 운영한다.\n\n## 일일 후보 루프 — 현재 런타임 조회\n\n- Automation: Daily Paper Candidates\n- ID: 03168daf-9499-4ca3-a6ba-2e93e65ed543\n- 활성화: true · 매일 09:00 · Asia/Seoul\n- Provider: codex · 기존 저장소에서 매번 새 세션\n- 후보: CV 1 + 멀티모달 1 + 관심 분야 1\n- 최소 두 학술 소스, 공식 게재·원문 확인\n- 결과는 자동화 회차의 채팅이며 채택 전에는 PDF·Keep·JSON을 저장하지 않음\n\n2026-10-07 Orca automations show로 예약 설정을 읽어 확인했다. 예약이 켜져 있다는 사실만으로 모든 회차의 결과 완성을 보장하지 않는다.\n\n## 사용자 확인 지점\n\n후보 채택, 개념 승격, 사고실험 기획 승인, 독립 심사 후 진행 결정은 사용자에게 있다. 문헌 TODO dispatch는 명시적 실행 요청이 필요하다.\n\n## 기존 기록에서 확인된 차이\n\nJev 사례는 레지스트리와 brief의 승인 상태가 다르고 현재 계약의 analysis.json이 없다. Notion backend 설정에는 링크가 있으나 레지스트리에는 미연결 안내가 남아 있다. 이 페이지는 차이를 기록하며 원장 상태를 임의로 변경하지 않는다.', ['docs/daily-orca-automation.md','docs/onboarding.md','docs/agent-research-todo.md','04-Projects/thought-experiment-runs/CRITICAL_VALIDATION_REGISTRY.md'], '04-operation-loops')
    add('views',None,'HTML 화면','저장소의 기록을 찾고 읽는 세 화면이다. 개별 HTML은 정본 데이터를 대체하지 않으며 생성기로 갱신한다. 리뷰 시작은 본인 에이전트와 로컬 브리지가 연결되어 있어야 한다.', ['100-views/README.md'])
    add('skills',None,'스킬 목록','스킬은 특정 요청을 처리하는 작업 지침이다. 공통 정본은 .agents/skills/이며 Codex·Claude 호스트 진입점에서 참조한다. 아래 스킬은 모두 순서대로 실행하는 목록이 아니다. 현재 작업의 단계와 사용자 요청에 따라 선택한다.\n\n## 실행 순서를 정하는 곳\n\nAGENTS.md와 docs/Harness-Graph.md, research_workflow.py, research-workflow-map.json이 단계와 조건을 안내한다. Skill-Catalog.md는 찾기 위한 목록이다.', ['docs/Skill-Catalog.md','.scripts/docs/research-workflow-map.json'])

    specs = {
      'paper-search':('논문 검색·수집','reading','PDF·제목·링크·arXiv ID 또는 채택한 후보','출처·중복·분야를 확인하고 PDF·Keep·인덱스·JSON으로 등록','검색 후보만 요청하면 저장하지 않는다. 원문과 공식 메타데이터를 우선하고 검색 한계를 보고한다.'),
      'paper-review':('논문 심층 리뷰','reading','원문 PDF와 필요할 때 트리아지 메모','3패스 정독 → 방법 구조도 → 5축 리뷰와 JSON → 인덱스·그래프 갱신','배경·기여·방법·실험·주장/근거·ablation·한계·재현성·관련 연구를 템플릿에 기록한다. 모든 수치에는 원문 위치를 붙인다.'),
      'review-index':('논문 인덱스 정리','reading','완료 리뷰·논문 JSON·PDF 경로','01-Papers/index.md의 한 논문 한 행과 상태·경로 점검','목록을 갱신한다. PDF·리뷰 파일의 이동·삭제를 임의로 하지 않는다.'),
      'related-work':('선행·후속 연구 조사','reading','앵커 논문 ID와 원문','references/citations 추적 → 양쪽 원문 확인 → JSON relationships','API 인용 연결이나 유사 제목만으로 연구 관계를 확정하지 않는다.'),
      'paper-relations':('저장소 논문 관계','reading','논문 ID·저장소 그래프·양쪽 원문','Graphify에서 관계 후보 탐색 후 원문으로 검증','지지·반박·확장·사용·비교·인용 등 관계에 원문 위치를 연결한다.'),
      'concept-note':('개념 공부노트','skills','사용자가 설명·수정한 개념과 명시적 작성/승격 요청','02-Concepts/에 정의·직관·예시·수식·혼동점·근거를 기록','논문 요약과 사용자가 이해한 내용을 구분한다. 리뷰만 요청된 경우 실행하지 않는다.'),
      'keep-list':('읽기·조사 대기열','skills','킵 추가·조회·해제·검증 요청','01-Papers/keep.md에서 논문과 다시 조사할 주제를 관리','즐겨찾기와 독립 목록이다. 목록 해제가 PDF·리뷰 삭제를 뜻하지 않는다.'),
      'paper-favorites':('선호 논문 기록','skills','사용자가 명시한 즐겨찾기 요청','01-Papers/favorites.md에 이유와 자료 경로를 기록','사용자 선호만 반영하며 논문 내용·평점을 임의로 변경하지 않는다.'),
      'paper-summary':('논문 3편 요약','skills','정확히 세 논문과 실제 확인한 원문','초록·전체 주장·방법·한계를 채팅으로 요약','심층 리뷰와 별도 작업이다. PDF를 못 읽었으면 확인 범위를 명시한다. 기존 papers/ 표기는 호환 경로이며 새 저장은 canonical 경로를 따른다.'),
      'daily-digest-loop':('일일 논문 후보','ops','오늘 날짜·선정 계획·사용자 관심 맥락','CV·멀티모달·관심 분야 각 후보 한 편을 채팅으로 제시','스킬 호출당 탐색만 수행한다. 반복 실행 시각은 Orca, 날짜별 주제는 paper-scheduler가 관리한다.'),
      'paper-scheduler':('날짜별 선정 계획','ops','날짜·주제·슬롯·선정 제약','03-Trends/daily/YYYY-MM-DD-plan.md 생성·조회·수정·취소','실제 예약 시각을 설정하지 않는다. 기본 3편과 학회 발표·게재 검증 조건을 유지한다.'),
      'thought-experiment-critique':('사고실험 전제 점검','thought','연구 질문·가설·제안 파이프라인','전제·식별가능성·누수·대조군·반증 조건을 분석','초기 단일 분석이다. 세 독립 페르소나 심사와는 다른 작업이다.'),
      'critical-validation':('Grill-me·독립 비판 검증','thought','연구 아이디어·backend/mode·원문 근거','Grill-me → brief 승인 → 문헌 검색 → 근거 동결 → 세 독립 심사 → 사용자 결정','동일 SHA-256의 근거 묶음을 사용한다. 보완 시 다시 질문·동결·심사하며 독립 실행 불가 시 대기한다.'),
      'thought-experiment-runner':('승인된 작은 실험','experiment','승인된 기획·대조군·성공/반증 기준·기존 코드','manifest와 condition별 results를 남기는 작은 재현 실험','현재 required 정책에서는 critical-validation과 사용자 결정이 먼저다. 결과가 가설의 자동 승인은 아니다.'),
      'graphify':('지식 그래프 탐색·동기화','data','논문 JSON·승인된 개념/아이디어·저장소 관계 질문','query/path/explain으로 탐색하고 변경된 정본의 의미 관계를 갱신','그래프 관계는 원문 증거가 아니다. 코드 AST update와 문서 의미 추출을 구분하고 실패는 pending으로 기록한다.'),
    }
    for name,(title,parent,inp,operation,rule) in specs.items():
        add('skill-'+name,parent,f'{title} · {name}',f'{operation}\n\n## 입력\n\n{inp}\n\n## 작동 조건·결과\n\n{rule}\n\n## 관리\n\n실행 지침의 정본은 아래 SKILL.md다. 호스트 연결과 순서 안내는 상위 스킬 목록·운영 문서에서 확인한다.', [f'.agents/skills/{name}/SKILL.md'])

    documents = [
      ('rules','ops','공통 실행 규칙 · AGENTS.md','AGENTS.md','폴더·근거·한국어 서술·라우팅·사용자 승인·하지 말아야 할 작업을 규정한다.'),
      ('home','ops','전체 탐색 지도 · Home','docs/Home.md','사람이 문서와 정본 경로를 찾는 전체 목차다.'),
      ('graph','ops','실행 순서 · Harness-Graph','docs/Harness-Graph.md','입력부터 심사·실험까지 연결 조건과 운영 경계를 설명한다.'),
      ('catalog','skills','스킬 찾기 · Skill-Catalog','docs/Skill-Catalog.md','스킬과 운영 도구의 역할을 찾는 보기 전용 목록이다. 실행 순서를 결정하지 않는다.'),
      ('onboarding','ops','본인 에이전트 연결 · 온보딩','docs/onboarding.md','onboard_research.py가 설치된 Codex·Claude 로그인과 비대화형 옵션을 확인하고 준비된 에이전트를 선택한다. 본인 브라우저 로그인은 사용자가 완료한다. 이름만 설정에 저장하고 로컬 서버와 화면을 연다. 실제 Claude 모델 응답·신규 OAuth는 기존 검증 범위 밖이다.'),
      ('installer','ops','다른 저장소에 설치','docs/research-harness-installer.md','skills / papers 프로필, dry-run, manifest, 충돌 보존·안전한 제거를 관리한다. 개인 PDF·리뷰·계정·MCP 비밀 설정을 복사하지 않는다.'),
      ('bridge','ops','HTML에서 리뷰 실행 · 로컬 브리지','docs/paper-review-bridge.md','선택 논문 한 편을 queue에 넣고 연결된 에이전트로 임시 작업 폴더에서 리뷰한다. 산출물 검증·충돌 확인 후 저장하고 HTML을 재생성한다. 공유 그래프 충돌은 pending, 리뷰 정본 충돌은 저장 중단이다.'),
      ('daily','ops','일일 예약 운영','docs/daily-orca-automation.md','Orca가 시간과 새 세션을 관리하고 daily-digest-loop가 후보를 채팅으로 제시한다. 현재 설정은 별도 런타임 조회로 확인했다.'),
      ('todo','ops','에이전트 문헌 조사 TODO','docs/agent-research-todo.md','queue.json에 질문·brief 해시·예산을 고정한다. 명시적 dispatch 요청 후 솔루션·레퍼런스·반대 근거 탐색을 병렬 수행하고 별도 verifier로 원문을 확인한다. publish 검증 뒤에만 completed다. 이 조사 역할은 비판 심사 페르소나와 다르다.'),
      ('handoff','ops','구현 요구사항·작업 인계','docs/handoff-paper-harness.md','대시보드, 리뷰 버튼, 온보딩, 사고실험 화면, 문헌 TODO의 구현 요구사항과 범위를 보관한다. 최초 요청 기록이므로 현재 구현 상태는 실제 코드·원장을 우선한다.'),
      ('search-protocol','reading','문헌 검색 프로토콜','.scripts/docs/search-protocol.md','질의 분해·소스 우선순위·스노우볼링·포화·검색 한계를 규정한다.'),
      ('review-template','reading','심층 리뷰 작성 양식','90-Templates/paper/review-template.md','문제와 동기·기여·방법 구조도/수식/학습·실험 설정·주장과 증거·ablation·한계·재현성·관련 연구·아이디어·남은 질문·BibTeX·읽은 범위를 채운다.'),
      ('triage-template','reading','1패스 판정 양식','90-Templates/paper/triage-template.md','심층 리뷰 전에 핵심 주장·문제·관련도·확인할 지점과 판정을 정리한다. 별도 실행 스킬은 아니다.'),
      ('study-template','skills','공부노트 작성 양식','90-Templates/study-note-template.md','정의·필요성·직관·예시/수식·혼동점·연결 자료를 사용자의 이해와 함께 기록한다.'),
      ('critique-template','thought','독립 심사 종합 양식','04-Projects/thought-experiment-runs/CRITIQUE_TEMPLATE.md','세 역할의 결함·근거·대체 설명·필수 비교와 미해결 문제, 다시 답할 질문, 사용자 결정을 남긴다.'),
      ('idea-persona','thought','아이디어 검토 관점 · Research Design Skeptic','04-Projects/validation/idea-review-persona.md','문제 정의·기여·반증·재현·문헌 근거를 의심하는 공통 검토 지침이다. 최종 채택은 사용자가 결정한다.'),
      ('draft-auditor','experiment','논문 초안 검토 · Argument Auditor','04-Projects/validation/paper-draft-logic-review.md','초안 제출·공유 전에 주장 → 근거 → 누락/대체 설명 → 수정 요구를 표로 정리한다. 설치 스킬이 아닌 검토 지침이다.'),
      ('settings','thought','비판 검증 정책','04-Projects/thought-experiment-runs/CRITICAL_VALIDATION_SETTINGS.md','현재 mode: required. 모든 새 기획에 Grill-me·독립 3심사·사용자 결정을 요구한다. on-request / off는 사용자 설정 변경 때만 적용한다.'),
      ('backend','ops','진척 상태 저장 설정','04-Projects/thought-experiment-runs/PROGRESS_BACKEND.md','현재 backend: notion. 기존 Todo 링크가 지정되어 있다. 설정 링크는 실제 연결·동기화 성공을 보장하지 않는다. 이번 문서 허브와 기존 진척 원장은 목적이 다르다.'),
      ('registry','thought','비판 검증 레지스트리','04-Projects/thought-experiment-runs/CRITICAL_VALIDATION_REGISTRY.md','Grill-me·역할별 심사·사용자 결정·근거 링크를 추적한다. 기존 기록 간 충돌은 자동 승인으로 정리하지 않고 확인 대상으로 표시한다.'),
    ]
    for key,parent,title,source,desc in documents:
        add('doc-'+key,parent,title,desc,[source])

    for role,desc in [('method','주장과 관측의 연결, 식별가능성, 대조군과 반증 가능성을 검토한다.'),('repro','데이터 split·seed·환경 버전·정보 누수·평가 재현성을 검토한다.'),('novelty','선행연구 대비 차이와 자명한 조합, 더 단순한 대안을 검토한다.')]:
        add('persona-'+role,'thought',f'{role} critic · 심사 페르소나',desc+' 세 역할은 동일 근거와 해시를 받으며 다른 심사자의 결과를 보지 않는다. 근거가 부족하면 추가 확인을 요청한다.',[f'04-Projects/validation/personas/{role}-critic.md','04-Projects/validation/critic-output.schema.json'])

    for key,title,path,desc,generator in [
      ('dashboard','하네스 안내 화면','100-views/harness-dashboard.html','흐름·단계를 선택해 역할·입력·결과·다음 조건을 확인하고 스킬과 설정 상태를 찾는다. 안내 순서는 현재 작업 진척 상태와 별개다.','harness_dashboard.py'),
      ('library','논문 라이브러리 화면','100-views/paper-library.html','논문 JSON에서 검색·필터·원문·리뷰를 보여준다. 새 리뷰는 localhost 브리지와 준비된 본인 CLI가 필요하다.','paper_catalog_html.py'),
      ('ideas','사고실험 목록 화면','100-views/thought-experiments.html','가설·반증 조건·문헌·심사·실험·TODO 상태와 근거를 찾아본다. 출처끼리 충돌하면 표시하며 자동 조정하지 않는다.','thought_experiments_html.py')]:
        add('view-'+key,'views',title,desc+f'\n\n## 갱신\n\n생성기: .scripts/bin/{generator}. 공통 CSS: 100-views/assets/research-ui.css. 화면은 정본에서 다시 생성하므로 상태를 HTML에 직접 관리하지 않는다.',[path,f'.scripts/bin/{generator}','100-views/README.md'])
    add('view-graph','views','지식 그래프 탐색 화면','논문·개념·주장 사이 관계 후보를 찾아보는 Graphify의 시각화다. 자체 출력 정본은 graphify-out/graph.html이며 직접 만든 세 운영 화면과 저장 위치가 다르다. 그래프 연결은 원문 증거를 대신하지 않는다. 관계 확정은 paper-relations와 원문 확인을 따른다.', ['graphify-out/graph.html','.agents/skills/graphify/SKILL.md','.agents/skills/paper-relations/SKILL.md'])
    add('contracts','data','구조화 데이터·검증 계약','논문 JSON은 paper_record.py로 필수 필드와 5축 근거를 검사한다. 아이디어 analysis.json은 idea_analysis.py로 동일 근거·세 심사·사용자 결정을 검사한다. 문헌 TODO는 literature-investigation / research-todo 스키마를 따른다.\n\n## 검증 도구\n\n- verify_harness.py: 정본·스킬 연결·라우팅 참조 검사\n- onboarding_check.py: 실행 환경 준비 확인\n- graphify_sync.py: 의미 동기화 begin / complete / fail 상태 기록\n\n형식 검사 통과가 내용의 과학적 타당성이나 실제 에이전트 실행 성공을 보장하지는 않는다.', ['.scripts/docs/paper-record.schema.json','.scripts/docs/idea-analysis.schema.json','.scripts/docs/literature-investigation.schema.json','.scripts/docs/research-todo.schema.json','04-Projects/validation/critic-output.schema.json'])
    add('routing','ops','단계 라우터·화면 흐름 지도','research_workflow.py는 현재 단계에서 다음 진입점을 안내한다. research-workflow-map.json은 논문·일일 후보·개념·아이디어·문헌·독립 도구 여섯 흐름에 선택 단계, 병렬 역할, 사용자 확인 조건을 기록한다. 대시보드가 같은 지도를 읽는다. 모든 스킬을 한꺼번에 실행하는 자동 파이프라인은 아니다.', ['.scripts/bin/research_workflow.py','.scripts/docs/research-workflow-map.json'])
    add('archive','ops','발표·디자인·문서 원본 묶음','설계 배경과 발표자료 계획·페이지별 내용·노트북 출력 기록, 적용한 디자인 안내는 원본 묶음에 포함한다. 운영 방법은 위 기능별 페이지와 현재 정본을 우선한다. 원본 묶음은 안내 문서·스킬·템플릿·스키마만 포함하며 개인 인증, 논문 PDF, 연구 결과 데이터는 포함하지 않는다.', ['docs/lab-meeting-presentation-plan.md','docs/lab-meeting-slide-content.md','docs/lab-meeting-laptop-output.md','docs/design/DESIGN-discord.md'])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    VIEWS.mkdir(parents=True, exist_ok=True)
    build_diagrams()
    build_pages()
    for page in PAGES:
        (OUT / (page['key']+'.md')).write_text('# '+page['title']+'\n\n'+page['content']+'\n',encoding='utf-8')
    sources = set(p for page in PAGES for p in page['sources'] if p.endswith(('.md','.json')))
    sources.update(str(p.relative_to(ROOT)) for p in (ROOT/'docs').rglob('*.md') if OUT not in p.parents)
    source_manifest = []
    with zipfile.ZipFile(OUT/'harness-documentation-sources.zip','w',zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(sources):
            path=ROOT/source
            if path.exists():
                archive.write(path,source)
                source_manifest.append(dict(path=source,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (OUT/'pages.json').write_text(json.dumps(PAGES,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'source-manifest.json').write_text(json.dumps(source_manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    links=''.join(f'<a href="{p.name}"><strong>{p.stem}</strong><span>HTML 도식 열기</span></a>' for p in sorted(VIEWS.glob('0*.html')))
    (VIEWS/'index.html').write_text('<!doctype html><html lang="ko"><meta charset="utf-8"><title>연구 하네스 흐름도</title><style>body{font-family:"Noto Sans CJK KR",sans-serif;background:#f4f7fc;color:#142638;padding:56px}h1{font-size:38px}p{color:#596b83}a{display:block;background:white;border:1px solid #dce4f1;border-radius:14px;padding:24px;margin:16px 0;color:#273c75;text-decoration:none}span{float:right}</style><h1>연구 하네스 흐름도</h1><p>16:9 · 흰 배경 · PPT용 PNG와 PDF는 assets/에서 확인합니다.</p>'+links+'</html>',encoding='utf-8')
    print(f'Built {len(PAGES)} reference pages, 4 HTML diagrams, {len(source_manifest)} source snapshots.')


if __name__=='__main__':
    main()
