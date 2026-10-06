#!/usr/bin/env python3
"""Build a searchable thought-experiment index from idea notes and run records."""
from __future__ import annotations

import html
import json
import re
from datetime import date
from pathlib import Path

from research_ui import STYLESHEET, page_header

ROOT = Path(__file__).resolve().parents[2]
IDEAS = ROOT / "05-ideas/thought-experiments"
RUNS = ROOT / "04-Projects/thought-experiment-runs"
OUTPUT = ROOT / "100-views" / "thought-experiments.html"
REGISTRY = RUNS / "CRITICAL_VALIDATION_REGISTRY.md"
TODO_QUEUE = ROOT / "04-Projects/research-todo/queue.json"


def section(text: str, heading: str) -> str:
    match = re.search(rf"^##\s+{re.escape(heading)}\s*$\n(.*?)(?=^##\s|\Z)", text, re.M | re.S | re.I)
    if not match:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"[#*`]", "", match.group(1))).strip()


def registry_rows() -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    if not REGISTRY.is_file():
        return rows
    for line in REGISTRY.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or "thought-experiments/" not in line:
            continue
        cells = [cell.strip().strip("`") for cell in line.strip("|").split("|")]
        if len(cells) < 11:
            continue
        rows[cells[2]] = {
            "slug": cells[0], "grill": cells[3], "method": cells[4], "repro": cells[5],
            "novelty": cells[6], "overall": cells[7], "decision": cells[8], "evidence": cells[9],
            "updated": cells[10],
        }
    return rows


def scan() -> list[dict]:
    items = []
    registry = registry_rows()
    paper_paths: dict[str, str] = {}
    for record_path in (ROOT / "01-Papers/library").glob("*.json"):
        try:
            paper = json.loads(record_path.read_text(encoding="utf-8"))
            paper_paths[paper.get("paper_id", "")] = record_path.relative_to(ROOT).as_posix()
        except (OSError, json.JSONDecodeError):
            continue
    todo_data = json.loads(TODO_QUEUE.read_text(encoding="utf-8")) if TODO_QUEUE.is_file() else {"tasks": []}
    todo_by_idea: dict[str, list[dict]] = {}
    for task in todo_data.get("tasks", []):
        todo_by_idea.setdefault(task.get("idea_path", ""), []).append(task)
    for path in sorted(IDEAS.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = next((line.lstrip("# ").strip() for line in text.splitlines() if line.startswith("# ")), path.stem)
        hypothesis = section(text, "핵심 가설") or section(text, "축소된 핵심 가설") or section(text, "가설") or "미기록"
        falsification = section(text, "반증 조건") or "미기록"
        run_dir = None
        for href in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            candidate = (path.parent / href.split("#", 1)[0]).resolve()
            try:
                candidate.relative_to(RUNS.resolve())
            except ValueError:
                continue
            run_dir = candidate if candidate.is_dir() else candidate.parent
            break
        if run_dir is None:
            direct = RUNS / path.stem
            run_dir = direct if direct.is_dir() else None
        registry_entry = registry.get(path.relative_to(ROOT).as_posix(), {})
        if run_dir is None and registry_entry.get("slug"):
            candidate = RUNS / registry_entry["slug"]
            run_dir = candidate if candidate.is_dir() else None
        analyses = list(run_dir.glob("analysis.json")) if run_dir and run_dir.is_dir() else []
        analysis = json.loads(analyses[0].read_text(encoding="utf-8")) if analyses else {}
        brief = run_dir / "brief.md" if run_dir and run_dir.is_dir() else None
        results = run_dir / "results.md" if run_dir and run_dir.is_dir() else None
        critics = analysis.get("critics", {})
        review_status = ", ".join(
            f"{k}: {critics.get(k, {}).get('status', registry_entry.get(k, '미기록'))}"
            for k in ("method", "repro", "novelty")
        )
        decision = analysis.get("user_decision", {}).get("decision", registry_entry.get("decision", "미기록"))
        search = analysis.get("literature_search", {}).get("status", "미기록")
        note_decision_match = re.search(r"(?:[-*]\s*)?사용자 결정:\s*(.+)", text)
        note_decision = note_decision_match.group(1).strip() if note_decision_match else "미기록"
        decision_conflict = bool(registry_entry and note_decision != "미기록" and registry_entry.get("decision") != note_decision)
        note_status_match = re.search(r"(?:[-*]\s*)?상태:\s*(.+)", text)
        note_status = note_status_match.group(1).strip() if note_status_match else "미기록"
        status_conflict = bool(registry_entry and note_status != "미기록" and registry_entry.get("overall") not in note_status)
        update = max(date.fromtimestamp(path.stat().st_mtime).isoformat(), registry_entry.get("updated", ""))
        evidence_links = []
        if registry_entry:
            for label, target in re.findall(r"\[([^]]+)\]\(([^)]+)\)", registry_entry.get("evidence", "")):
                candidate = (REGISTRY.parent / target).resolve()
                try:
                    relative = candidate.relative_to(ROOT.resolve()).as_posix()
                except ValueError:
                    continue
                if candidate.is_file():
                    evidence_links.append(relative)
        run_files = {p.name: p.relative_to(ROOT).as_posix() for p in run_dir.iterdir()} if run_dir and run_dir.is_dir() else {}
        artifacts = sorted(p.relative_to(ROOT).as_posix() for p in run_dir.rglob("*") if p.is_file() and p.suffix in {".json", ".csv", ".png", ".svg"}) if run_dir else []
        criticisms = sorted(p.relative_to(ROOT).as_posix() for p in run_dir.glob("critique*.md")) if run_dir else []
        related_papers = [p.get("paper_id", "") for p in analysis.get("literature_search", {}).get("included_papers", []) if p.get("paper_id")]
        related_paper_paths = [paper_paths[p] for p in related_papers if p in paper_paths]
        linked_todos = todo_by_idea.get(path.relative_to(ROOT).as_posix(), [])
        todo_status = ", ".join(task.get("status", "unknown") for task in linked_todos) or "미기록"
        items.append({
            "id": path.stem, "title": title, "hypothesis": hypothesis, "falsification": falsification,
            "topics": "미기록", "updated": update, "literature": search, "review": review_status,
            "decision": decision, "experiment": "기록 있음" if results and results.is_file() else "미기록",
            "note": path.relative_to(ROOT).as_posix(),
            "brief": brief.relative_to(ROOT).as_posix() if brief and brief.is_file() else "",
            "results": results.relative_to(ROOT).as_posix() if results and results.is_file() else "",
            "todo": "docs/agent-research-todo.md",
            "registry": registry_entry, "validation": registry_entry.get("overall", "미기록"),
            "noteDecision": note_decision, "noteStatus": note_status,
            "decisionConflict": decision_conflict, "statusConflict": status_conflict,
            "manifest": run_files.get("manifest.md", ""), "analysis": analyses[0].relative_to(ROOT).as_posix() if analyses else "",
            "critiques": criticisms, "evidence": evidence_links, "papers": related_papers,
            "paperPaths": related_paper_paths, "artifacts": artifacts,
            "todoStatus": todo_status, "todoTasks": [task.get("task_id", "") for task in linked_todos],
            "todoResults": [task.get("result_path", "") for task in linked_todos],
        })
    return items


HTML = r'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>사고실험 목록</title>
<style>body{margin:0;background:#f3f6f2;color:#1e2c25;font:15px system-ui,sans-serif}header{background:#173c32;color:white;padding:25px max(20px,calc((100vw - 1080px)/2))}main{max-width:1080px;margin:22px auto;padding:0 16px 45px}nav a{color:white;margin-right:16px}.filters{display:grid;grid-template-columns:2fr repeat(3,1fr);gap:9px;background:#fff;padding:12px;border:1px solid #dce5dd;border-radius:10px}input,select{padding:10px;border:1px solid #d2ddd4;border-radius:7px;font:inherit}.card{background:#fff;border:1px solid #dce5dd;border-radius:10px;padding:16px;margin:9px 0}.card h2{font-size:18px;margin:0 0 8px}.meta{color:#637169;font-size:13px}.hyp{line-height:1.55}.links a{margin-right:12px;color:#267052}.muted{color:#68766e}.empty{padding:30px;text-align:center}.conflict{color:#a33}@media(max-width:700px){.filters{grid-template-columns:1fr 1fr}}</style>
__SHARED_STYLE__</head><body class="ideas-page">__PAGE_HEADER__
<main><section class="filters"><input id="q" aria-label="제목·가설 검색" placeholder="제목·가설 검색"><select id="validation" aria-label="심사 상태"><option value="">심사 상태 전체</option></select><select id="review" aria-label="역할 심사"><option value="">역할 심사 전체</option></select><select id="literature" aria-label="문헌 상태"><option value="">문헌 상태 전체</option></select><select id="decision" aria-label="사용자 결정"><option value="">사용자 결정 전체</option></select><select id="experiment" aria-label="실험 상태"><option value="">실험 상태 전체</option></select><select id="todo" aria-label="조사 TODO"><option value="">조사 TODO 전체</option></select><select id="sort" aria-label="정렬"><option value="date">갱신일 최신순</option><option value="title">제목순</option></select></section><p id="count"></p><section id="items"></section></main>
<script id="data" type="application/json">__DATA__</script><script>
const items=JSON.parse(document.querySelector('#data').textContent),$=x=>document.getElementById(x),opts=(id,key)=>{for(const v of [...new Set(items.map(i=>i[key]))].sort()){const o=document.createElement('option');o.value=v;o.textContent=v;$ (id).append(o)}};
opts('validation','validation');opts('review','review');opts('literature','literature');opts('decision','decision');opts('experiment','experiment');opts('todo','todoStatus');
function render(){const q=$('q').value.toLocaleLowerCase(),v=$('validation').value,r=$('review').value,l=$('literature').value,d=$('decision').value,e=$('experiment').value,t=$('todo').value;let rows=items.filter(i=>(!q||`${i.title} ${i.hypothesis} ${i.topics}`.toLocaleLowerCase().includes(q))&&(!v||i.validation===v)&&(!r||i.review===r)&&(!l||i.literature===l)&&(!d||i.decision===d)&&(!e||i.experiment===e)&&(!t||i.todoStatus===t));rows.sort((a,b)=>$('sort').value==='title'?a.title.localeCompare(b.title):b.updated.localeCompare(a.updated));$('count').textContent=`${rows.length} / ${items.length}개 표시`;const root=$('items');root.replaceChildren();if(!rows.length){const empty=document.createElement('p');empty.textContent='조건에 맞는 아이디어가 없습니다.';root.append(empty);}for(const i of rows){const card=document.createElement('article');card.className='card';const title=document.createElement('h2');title.textContent=i.title;card.append(title);const meta=document.createElement('div');meta.className='meta';meta.textContent=`주제 ${i.topics} · 갱신 ${i.updated} · 문헌 ${i.literature} · 심사 ${i.review} · 결정 ${i.decision} · 실험 ${i.experiment} · 조사 ${i.todoStatus}`;card.append(meta);if(i.decisionConflict||i.statusConflict){const conflict=document.createElement('p');conflict.className='conflict';conflict.textContent=`상태 충돌: 노트 상태 “${i.noteStatus}” / 레지스트리 상태 “${i.registry.overall}”; 노트 결정 “${i.noteDecision}” / 레지스트리 결정 “${i.registry.decision}”. 어느 쪽도 자동으로 적용하지 않았습니다.`;card.append(conflict)}const p=document.createElement('p');p.className='hyp';p.textContent=i.hypothesis;card.append(p);const f=document.createElement('p');f.textContent=`반증 조건: ${i.falsification}`;card.append(f);const links=document.createElement('p');links.className='links';for(const [label,path] of [['원문',i.note],['분석 brief',i.brief],['분석 JSON',i.analysis],['manifest',i.manifest],['실험 결과',i.results],['조사 TODO',i.todo]])if(typeof path==='string'&&path){const a=document.createElement('a');a.href="../"+path;a.textContent=label;links.append(a)}for(const path of [...i.paperPaths,...i.artifacts,...i.todoResults,...i.critiques,...i.evidence]){if(!path)continue;const a=document.createElement('a');a.href="../"+path;a.textContent=path.split('/').pop();links.append(a)}card.append(links);root.append(card)}}
for(const id of ['q','validation','review','literature','decision','experiment','todo','sort'])$(id).addEventListener('input',render);document.querySelectorAll('select').forEach(el=>el.addEventListener('change',render));render();</script><footer class="page-footer"><p>아이디어 노트와 실험 기록에서 생성 · 갱신: <code>python3 .scripts/bin/thought_experiments_html.py</code></p><div class="footer-wordmark" aria-hidden="true">PAPER AGENT</div></footer></body></html>'''


def main() -> None:
    data = json.dumps(scan(), ensure_ascii=False, separators=(",", ":"))
    data = data.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(HTML.replace("__DATA__", data).replace("__SHARED_STYLE__", STYLESHEET).replace("__PAGE_HEADER__", page_header('ideas', '아이디어를 연구로', 'IDEAS & EXPERIMENTS', '가설과 반증 조건을 정리하고, 문헌 조사와 심사에서 작은 실험까지 기록을 이어가세요.', '아이디어 살펴보기', '#q')), encoding="utf-8")
    print(f"Generated {OUTPUT.relative_to(ROOT)} with {len(scan())} ideas")


if __name__ == "__main__":
    main()
