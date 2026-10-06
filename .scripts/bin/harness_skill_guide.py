"""Build the dashboard's local, interactive skill and workflow guide."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / ".scripts/docs/research-workflow-map.json"


def load_paths() -> list[dict]:
    return json.loads(MAP.read_text(encoding="utf-8"))["paths"]


def skill_data() -> list[dict]:
    paths = load_paths()
    result = []
    for source in sorted((ROOT / ".agents/skills").glob("*/SKILL.md")):
        text = source.read_text(encoding="utf-8")
        frontmatter = text.split("---", 2)[1] if text.startswith("---") else ""
        match = re.search(r"^description:\s*(.+)$", frontmatter, re.M)
        description = match[1].strip().strip('\"\'') if match else "설명 미기록"
        title = re.search(r"^#\s+(.+)$", text, re.M)
        uses = [dict(step, path_id=path["id"], path_title=path["title"], order=i + 1)
                for path in paths for i, step in enumerate(path["steps"])
                if step.get("skill") == source.parent.name]
        result.append({"name": source.parent.name, "title": title[1] if title else source.parent.name,
                       "description": description, "source": source.relative_to(ROOT).as_posix(),
                       "instructions": text, "uses": uses})
    return result


def guide_html() -> str:
    payload = json.dumps({"paths": load_paths(), "skills": skill_data()}, ensure_ascii=False)
    payload = payload.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return GUIDE.replace("__GUIDE_DATA__", payload)


GUIDE = r'''
<section id="skill-guide" class="guide-section">
<h2>어떤 스킬을 언제 쓰나요?</h2>
<p>작업 흐름을 선택한 뒤 단계를 누르면 역할·입력·산출물·다음 조건이 표시됩니다. 이 그림은 실행 절차 안내이며 현재 작업의 진행 상태가 아닙니다.</p>
<div id="workflow-tabs" class="workflow-tabs" role="group" aria-label="작업 흐름 선택"></div>
<div class="workflow-heading"><h3 id="workflow-title"></h3><p id="workflow-description"></p></div>
<div id="workflow-steps" class="workflow-steps" role="group" aria-label="단계 상세 선택"></div>
<div id="step-detail" class="guide-detail" aria-live="polite"></div>
<p class="guide-source">흐름 정본: <a href="../.scripts/docs/research-workflow-map.json">research-workflow-map.json</a> · 스킬 설명 정본: 각 SKILL.md · <a href="../docs/Harness-Graph.md">실행 원칙</a></p>
</section>
<section id="skill-catalog" class="guide-section">
<h2>스킬 설명과 사용 위치</h2>
<label for="skill-search">스킬 이름·역할 검색</label><input id="skill-search" type="search" placeholder="예: 논문 정독, 반증, keep, graphify">
<p id="skill-count" class="guide-source"></p>
<div id="skill-cards" class="skill-cards"></div>
<div id="skill-detail" class="guide-detail" hidden aria-live="polite"></div>
</section>
<script id="skill-guide-data" type="application/json">__GUIDE_DATA__</script>
<script>
"use strict";
const guideData=JSON.parse(document.getElementById("skill-guide-data").textContent);
const guideSkills=new Map(guideData.skills.map(s=>[s.name,s]));
const guideKinds={skill:"스킬",procedure:"절차",gate:"확인 조건",parallel:"병렬 역할",tool:"실행 도구",playbook:"검토 안내"};
const guideElement=(tag,text,className)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(className)n.className=className;return n;};
const guideLink=(label,path)=>{const n=guideElement("a",label);n.href="../"+path;return n;};
let activePath=guideData.paths[0].id;
let activeStep=0;
function appendField(root,label,value){root.append(guideElement("dt",label),guideElement("dd",value||"미기록"));}
function showStep(path,index){
  activeStep=index;
  for(const [i,button] of [...document.querySelectorAll(".workflow-node")].entries())button.setAttribute("aria-pressed",String(i===index));
  const step=path.steps[index],skill=guideSkills.get(step.skill),root=document.getElementById("step-detail");root.replaceChildren();
  root.append(guideElement("span",`${path.layout==="choices"?"독립 요청 도구":`${index+1}단계`} · ${guideKinds[step.skill?"skill":step.kind]||"절차"}${step.optional?" · 선택 실행":""}`,"guide-badge"));
  root.append(guideElement("h3",step.label));
  if(skill)root.append(guideElement("p",skill.description));
  const fields=guideElement("dl");appendField(fields,"입력",step.input);appendField(fields,"결과",step.output);appendField(fields,"실행 조건",step.condition);
  if(path.layout!=="choices")appendField(fields,"다음 단계",path.steps[index+1]?.label||"이 흐름의 마지막 단계");
  root.append(fields);
  if(step.members)root.append(guideElement("p",`독립 역할: ${step.members.join(" · ")}`));
  if(skill){const button=guideElement("button",`${skill.name} 설명·전체 지침 보기`,"guide-button");button.type="button";button.addEventListener("click",()=>showSkill(skill.name,true));root.append(button);}
  if(step.source||skill?.source)root.append(guideLink("근거 파일 열기",step.source||skill.source));
}
function showPath(id){
  const path=guideData.paths.find(p=>p.id===id);if(!path)return;activePath=id;
  document.getElementById("workflow-title").textContent=path.title;
  document.getElementById("workflow-description").textContent=path.description;
  for(const b of document.getElementById("workflow-tabs").children)b.setAttribute("aria-pressed",String(b.dataset.path===id));
  const root=document.getElementById("workflow-steps");root.replaceChildren();root.classList.toggle("independent",path.layout==="choices");
  path.steps.forEach((step,index)=>{
    if(index&&path.layout!=="choices")root.append(guideElement("span","→","workflow-arrow"));
    const button=guideElement("button",undefined,`workflow-node ${step.kind||"skill"}${step.optional?" optional":""}`);button.type="button";
    button.append(guideElement("span",`${path.layout==="choices"?"독립 요청":index+1} · ${step.optional?"선택":guideKinds[step.skill?"skill":step.kind]||"절차"}`,"node-caption"));
    button.append(guideElement("strong",step.label),guideElement("code",step.skill||guideKinds[step.kind]));
    if(step.members){const members=guideElement("div",undefined,"parallel-members");for(const member of step.members)members.append(guideElement("span",member));button.append(members);}
    button.addEventListener("click",()=>showStep(path,index));root.append(button);
  });
  showStep(path,0);
}
function showSkill(name,scroll){
  const skill=guideSkills.get(name);if(!skill)return;const root=document.getElementById("skill-detail");root.hidden=false;root.replaceChildren();
  root.append(guideElement("h3",`${skill.title} · ${name}`),guideElement("p",skill.description));
  for(const use of skill.uses){const block=guideElement("div",undefined,"skill-use");const button=guideElement("button",`${use.path_title}에서 보기`,"guide-button");button.type="button";
    button.addEventListener("click",()=>{showPath(use.path_id);showStep(guideData.paths.find(p=>p.id===use.path_id),use.order-1);document.getElementById("skill-guide").scrollIntoView({behavior:"smooth",block:"start"});});
    const fields=guideElement("dl");appendField(fields,"입력",use.input);appendField(fields,"결과",use.output);appendField(fields,"조건",use.condition);block.append(button,fields);root.append(block);}
  if(!skill.uses.length)root.append(guideElement("p","개별 요청으로 사용합니다. 실행 범위는 아래 원문 지침을 확인하세요."));
  root.append(guideLink("SKILL.md 원본 열기",skill.source));
  const details=guideElement("details");details.append(guideElement("summary","전체 스킬 지침 펼치기"),guideElement("pre",skill.instructions));root.append(details);
  if(scroll)root.scrollIntoView({behavior:"smooth",block:"start"});
}
function renderSkillCards(){
  const q=document.getElementById("skill-search").value.trim().toLowerCase(),root=document.getElementById("skill-cards");root.replaceChildren();
  const matches=guideData.skills.filter(s=>`${s.name} ${s.title} ${s.description} ${s.uses.map(u=>`${u.label} ${u.input} ${u.output} ${u.condition}`).join(" ")}`.toLowerCase().includes(q));
  document.getElementById("skill-count").textContent=`${matches.length} / ${guideData.skills.length}개 스킬 · 카드를 누르면 사용 조건과 전체 지침을 확인할 수 있습니다.`;
  for(const s of matches){const use=s.uses[0],button=guideElement("button",undefined,"skill-card");button.type="button";button.append(guideElement("code",s.name),guideElement("strong",use?.label||s.title),guideElement("span",use?`${use.input} → ${use.output}`:s.description));if(use)button.append(guideElement("span",use.condition));button.addEventListener("click",()=>showSkill(s.name,true));root.append(button);}
  if(!matches.length)root.append(guideElement("p","검색 조건에 맞는 스킬이 없습니다."));
}

for(const path of guideData.paths){const button=guideElement("button",path.title,"guide-button");button.type="button";button.dataset.path=path.id;button.addEventListener("click",()=>showPath(path.id));document.getElementById("workflow-tabs").append(button);}
document.getElementById("skill-search").addEventListener("input",renderSkillCards);
showPath(activePath);renderSkillCards();
</script>
'''

GUIDE_CSS = '''
.guide-section{scroll-margin-top:20px}.workflow-tabs{display:flex;flex-wrap:wrap;gap:8px}.guide-button{border:1px solid #c8d7cd;background:#f5f8f5;color:#214331;border-radius:8px;padding:9px 12px;cursor:pointer;font:inherit;font-size:13px}.guide-button[aria-pressed=true]{background:#173c32;color:#fff;border-color:#173c32}.workflow-heading h3{margin-bottom:6px}.workflow-heading p{color:#53665b;line-height:1.7}.workflow-steps{display:flex;align-items:center;gap:10px;padding:22px 14px;background:#111e2a;border-radius:10px;overflow:auto}.workflow-node{flex:0 0 175px;align-self:stretch;padding:14px 12px;color:#eaf3ff;background:#1b3550;border:1px solid #669dd2;border-radius:9px;text-align:left;cursor:pointer;font:inherit}.workflow-node[aria-pressed=true]{outline:3px solid #84c7ff;outline-offset:2px}.workflow-node strong,.workflow-node code,.node-caption{display:block}.node-caption{font-size:11px;color:#bfcede;margin-bottom:8px}.workflow-node strong{font-size:15px;line-height:1.5}.workflow-node code{font-size:11px;background:transparent;color:#c9dbef;margin-top:8px;padding:0}.workflow-node.gate{background:#453917;border-color:#d5b554}.workflow-node.parallel{background:#322951;border-color:#a393d4}.workflow-node.optional{border-style:dashed}.workflow-arrow{color:#91bde1;font-size:25px;flex:0 0 20px}.parallel-members{display:grid;gap:4px;margin-top:10px}.parallel-members span{padding:5px;background:#ffffff12;border-radius:4px;font-size:12px}.guide-detail{margin-top:18px;background:#f4f8f5;border:1px solid #cfddd3;border-radius:10px;padding:18px}.guide-detail h3{margin:10px 0}.guide-detail p{line-height:1.7}.guide-detail dl{display:grid;grid-template-columns:85px 1fr;gap:9px 15px;line-height:1.6}.guide-detail dt{font-weight:600;color:#435d4c}.guide-detail dd{margin:0}.guide-detail a{display:inline-block;margin:8px 12px}.guide-detail pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:460px;overflow:auto;background:#fff;padding:16px;font:13px/1.7 ui-monospace,monospace}.guide-badge{font-size:12px;color:#385942}.guide-source{font-size:12px;color:#596c5f}.skill-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:10px}.skill-card{background:#fff;border:1px solid #cbd9ce;border-radius:9px;padding:16px;text-align:left;cursor:pointer;color:#24382d;font:inherit}.skill-card:hover{border-color:#37876a}.skill-card code,.skill-card strong,.skill-card span{display:block}.skill-card strong{margin:10px 0 6px}.skill-card span{font-size:13px;line-height:1.65;color:#586c5f}#skill-search{display:block;width:min(100%,600px);margin-top:8px;border:1px solid #c6d6cb;border-radius:8px;padding:11px;font:inherit}.skill-use{border-bottom:1px solid #d6e2d9;padding:12px 0}.independent{flex-wrap:wrap}.independent .workflow-node{flex:1 1 200px}button:focus-visible{outline:3px solid #3d9ce0;outline-offset:3px}@media(max-width:600px){.guide-detail dl{grid-template-columns:1fr;gap:3px}.guide-detail dd{margin-bottom:12px}.workflow-node{flex-basis:160px}}
'''
