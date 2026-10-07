#!/usr/bin/env python3
"""Generate a self-contained HTML catalog from 01-Papers/library/*.json."""

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit


from research_ui import STYLESHEET, page_header

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = ROOT / "01-Papers" / "library"
OUTPUT = ROOT / "100-views" / "paper-library.html"
PDFINFO = shutil.which("pdfinfo")

# A few local PDFs have no /Title metadata. These titles were checked against
# the first page of the corresponding PDF; they are display fallbacks only.
PDF_TITLE_FALLBACKS = {
    "2026-magne-nitrogen-generalist-gaming-agents": "NITROGEN: An Open Foundation Model for Generalist Gaming Agents",
    "2026-holt-fact-augmented-lookahead-planning": "Fact-Augmented Lookahead Planning for LLM Agents",
    "ding-videozoomer-reinforcement-learned-temporal-focusing-long-video-reasoning": "VideoZoomer: Reinforcement-Learned Temporal Focusing for Long Video Reasoning",
    "huang-can-llms-discover-scientific-laws-real-parallel-worlds": "Can LLMs Discover Scientific Laws in Real and Parallel Worlds?",
    "wang-video-agent-long-form-video-understanding": "VideoAgent: Long-form Video Understanding with Large Language Model as Agent",
    "2026-chng-sensesearch": "SenseSearch: Empowering Vision-Language Models with High-Resolution Agentic Search-Reasoning via Reinforcement Learning",
    "2019-khalilsarai-wifi-multiband-phase-retrieval": "WiFi-Based Indoor Localization via Multi-Band Splicing and Phase Retrieval",
}


def pdf_title(record: dict) -> str:
    """Read PDF title metadata when the structured record has no title."""
    source_path = record.get("source", {}).get("pdf_path")
    if PDFINFO and source_path:
        pdf_path = (ROOT / source_path).resolve()
        if pdf_path.is_relative_to(ROOT) and pdf_path.is_file():
            result = subprocess.run([PDFINFO, str(pdf_path)], capture_output=True, text=True, check=False)
            for line in result.stdout.splitlines():
                if line.startswith("Title:"):
                    title = line.split(":", 1)[1].strip()
                    if title:
                        return title
    return ""


def original_target(record: dict) -> str:
    """Prefer the repository PDF; allow only safe HTTP(S) source fallbacks."""
    source = record.get("source", {})
    pdf_path = source.get("pdf_path")
    if pdf_path:
        local_path = (ROOT / pdf_path).resolve()
        if local_path.is_relative_to(ROOT) and local_path.is_file():
            return local_path.relative_to(ROOT).as_posix()
    for url in source.get("urls", []):
        if not isinstance(url, str):
            continue
        parsed = urlsplit(url.strip())
        if parsed.scheme in {"https", "http"} and parsed.hostname and not any(ch.isspace() for ch in parsed.netloc):
            return url.strip()
    return ""


def load_records() -> list[dict]:
    records = []
    for path in sorted(LIBRARY.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SystemExit(f"{path.relative_to(ROOT)}: {exc}") from exc
        if not isinstance(record, dict) or not isinstance(record.get("title"), str):
            raise SystemExit(f"{path.relative_to(ROOT)}: expected a JSON paper record with a title")
        title = record.get("title", "").strip()
        if not title:
            title = pdf_title(record) or PDF_TITLE_FALLBACKS.get(record.get("slug", ""), "")
        record["catalog_display_title"] = title or record.get("slug", "제목 확인 필요").replace("-", " ").title()
        record["catalog_original_url"] = original_target(record)
        record["catalog_original_status"] = "available" if record["catalog_original_url"] else "missing"
        review_path = record.get("source", {}).get("review_path")
        if not review_path:
            review_path = f"01-Papers/reviews/{record.get('category', 'other')}/{record.get('slug', path.stem)}.md"
        record["catalog_review_path_exists"] = False
        record["catalog_review_needed"] = record.get("structured_review_status") != "complete"
        if review_path:
            local_review = (ROOT / review_path).resolve()
            if local_review.is_relative_to(ROOT) and local_review.is_file():
                record["catalog_review_markdown"] = local_review.read_text(encoding="utf-8")
                record["catalog_review_path_exists"] = True
        if not record["catalog_review_path_exists"]:
            record["catalog_review_needed"] = True
        records.append(record)
    return records


HTML = r'''<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>Paper Library · paper_AgentCLI</title>
  <style>
    :root{font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#17211d;background:#f4f6f2;font-synthesis:none}
    *{box-sizing:border-box}body{margin:0}header{background:#173c32;color:#f5f8f4;padding:34px max(24px,calc((100vw - 1180px)/2)) 30px}
    header p{margin:0 0 8px;color:#b9d6c7;font-size:13px;letter-spacing:.08em;text-transform:uppercase}h1{margin:0;font-size:clamp(27px,4vw,40px);letter-spacing:-.04em}header .sub{margin:9px 0 0;color:#d2e2d8}
    main{max-width:1180px;margin:25px auto;padding:0 20px 60px}.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:18px}
    .stat,.panel,.toolbar,.paper{background:white;border:1px solid #e1e8e1;border-radius:12px;box-shadow:0 2px 8px #183c3210}.stat{padding:16px 18px}.stat span{display:block;color:#6d7972;font-size:13px}.stat strong{display:block;margin-top:5px;font-size:27px;letter-spacing:-.04em}
    .charts{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-bottom:18px}.panel{padding:17px 19px}.panel h2{margin:0 0 14px;font-size:15px}.bars{display:grid;gap:8px}.bar-row{display:grid;grid-template-columns:minmax(82px,130px) 1fr 32px;align-items:center;gap:9px;font-size:12px;color:#59665f}.bar{height:9px;background:#e9efea;border-radius:9px;overflow:hidden}.bar i{display:block;height:100%;background:#37856a;border-radius:9px}.bar-row b{text-align:right;color:#273a31;font-weight:600}
    .toolbar{display:grid;grid-template-columns:minmax(220px,1fr) repeat(3,minmax(145px,190px));gap:10px;padding:12px;margin-bottom:12px}input,select{width:100%;padding:10px 11px;border:1px solid #d9e1da;border-radius:8px;background:#fff;color:#203229;font:inherit;font-size:14px}input:focus,select:focus{outline:2px solid #82b99d;outline-offset:1px}.result-line{display:flex;justify-content:space-between;gap:12px;margin:13px 2px;color:#68766e;font-size:13px}
    #papers{display:grid;gap:9px}.paper{padding:15px 17px;display:grid;grid-template-columns:1fr auto;gap:12px}.paper.clickable{cursor:pointer;transition:border-color .15s,box-shadow .15s}.paper.clickable:hover,.paper.clickable:focus-visible{border-color:#7eae92;box-shadow:0 4px 14px #183c321b;outline:none}.paper h3{margin:0;font-size:16px;line-height:1.4;letter-spacing:-.02em}.meta{margin-top:7px;color:#637169;font-size:12px;display:flex;flex-wrap:wrap;gap:6px 12px}.badges{display:flex;align-content:start;justify-content:end;flex-wrap:wrap;gap:6px}.badge,.topic{border-radius:20px;background:#eef4ef;padding:4px 8px;color:#42624f;font-size:11px;white-space:nowrap}.badge.status{background:#edf2f5;color:#465d6b}.topics{display:flex;flex-wrap:wrap;gap:5px;margin-top:10px}.topic{background:#f5f3e9;color:#736436}.summary{margin-top:9px;color:#536159;font-size:13px;line-height:1.55}.paper a{color:#267052;text-decoration:none}.paper a:hover{text-decoration:underline}.paper-action,.review-action{display:inline-block;margin-top:10px;padding:6px 10px;border:0;border-radius:7px;background:#e8f2eb;color:#286849!important;font:inherit;font-size:12px;font-weight:600;text-decoration:none;cursor:pointer}.empty{text-align:center;padding:42px;color:#78857d;background:white;border:1px dashed #cad5cc;border-radius:12px}
    #review-dialog{width:min(960px,calc(100vw - 24px));max-height:88vh;padding:0;border:1px solid #dce5dd;border-radius:14px;color:#17211d;box-shadow:0 20px 70px #10271e55}#review-dialog::backdrop{background:#10271e99}.review-head{position:sticky;top:0;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:15px 20px;background:#173c32;color:white}.review-head h2{margin:0;font-size:17px}.review-close{border:0;border-radius:7px;padding:6px 10px;background:#ffffff20;color:white;font:inherit;cursor:pointer}.review-body{padding:24px;overflow:auto;line-height:1.72}.review-body h1,.review-body h2,.review-body h3,.review-body h4{line-height:1.35;margin:1.35em 0 .5em}.review-body h1{font-size:1.65em}.review-body h2{font-size:1.35em;border-bottom:1px solid #e1e8e1;padding-bottom:.35em}.review-body h3{font-size:1.15em}.review-body p{margin:.65em 0}.review-body ul,.review-body ol{padding-left:1.6em}.review-body li{margin:.3em 0}.review-body blockquote{margin:1em 0;padding:.2em 1em;border-left:3px solid #7eae92;background:#f4f8f4;color:#40584a}.review-body table{border-collapse:collapse;display:block;overflow:auto;max-width:100%;margin:1em 0;font-size:.9em}.review-body th,.review-body td{border:1px solid #dce5dd;padding:7px 9px;text-align:left;vertical-align:top}.review-body th{background:#eff5f0}.review-body code{padding:.12em .35em;border-radius:4px;background:#edf2ed;font-size:.9em}.review-body pre{padding:12px;overflow:auto;background:#f2f4f2;border-radius:8px}.review-body a{color:#267052}
    .flowchart{display:flex;align-items:center;gap:16px;overflow:auto;padding:18px;margin:16px 0;background:#101923;border:1px solid #314357;border-radius:10px;color:#e9f1ff}.flow-horizontal{flex-direction:row}.flow-vertical{flex-direction:column}.flow-node{position:relative;flex:0 0 150px;min-height:66px;display:grid;place-items:center;padding:10px;border:1px solid #74a3df;border-radius:8px;background:#1b2e4b;text-align:center;font-size:13px;line-height:1.4;white-space:pre-wrap}.flow-horizontal .flow-node:not(:last-child)::after{content:"→";position:absolute;right:-16px;color:#86b8ff}.flow-vertical .flow-node:not(:last-child)::after{content:"↓";position:absolute;bottom:-18px;color:#86b8ff}.flow-branch{max-width:180px;color:#b8d2fa;font-size:12px;line-height:1.4}
    footer{color:#849188;text-align:center;font-size:12px;padding:22px}
    @media(max-width:760px){.stats{grid-template-columns:repeat(2,1fr)}.charts{grid-template-columns:1fr}.toolbar{grid-template-columns:1fr 1fr}.toolbar input{grid-column:1/-1}.paper{grid-template-columns:1fr}.badges{justify-content:start}}
    @media(max-width:430px){main{padding-inline:13px}.toolbar{grid-template-columns:1fr}.toolbar input{grid-column:auto}.stats{gap:8px}.stat{padding:13px}}
  </style>
__SHARED_STYLE__
</head>
<body class="papers-page">
__PAGE_HEADER__
<main>
  <section class="stats" aria-label="요약">
    <div class="stat"><span>전체 논문</span><strong id="total">0</strong></div>
    <div class="stat"><span>리뷰 완료</span><strong id="reviewed">0</strong></div>
    <div class="stat"><span>읽기 대기</span><strong id="queued">0</strong></div>
    <div class="stat"><span>연구 분야</span><strong id="categories">0</strong></div>
  </section>
  <section class="charts">
    <div class="panel"><h2>연도별 논문 수</h2><div id="year-chart" class="bars"></div></div>
    <div class="panel"><h2>분야별 논문 수</h2><div id="category-chart" class="bars"></div></div>
  </section>
  <section class="toolbar" aria-label="검색 및 필터">
    <input id="search" type="search" placeholder="제목, 저자, 주제, 초록 검색…" aria-label="논문 검색">
    <select id="category-filter" aria-label="분야"><option value="">모든 분야</option></select>
    <select id="status-filter" aria-label="읽기 상태"><option value="">모든 상태</option></select>
    <select id="year-filter" aria-label="연도"><option value="">모든 연도</option></select>
  </section>
  <div class="result-line"><span id="result-count"></span><span>출처: <code>01-Papers/library/*.json</code></span></div>
  <p id="bridge-info" class="result-line" role="status"></p>
  <section id="papers" aria-live="polite"></section>
</main>
<dialog id="review-dialog"><div class="review-head"><h2 id="review-title">논문 리뷰</h2><button id="review-close" class="review-close" type="button">닫기</button></div><article id="review-body" class="review-body"></article></dialog>
<footer class="page-footer"><p>저장소 논문 JSON에서 생성 · 갱신: <code>python3 .scripts/bin/paper_catalog_html.py</code></p><div class="footer-wordmark" aria-hidden="true">PAPER AGENT</div></footer>
<script id="paper-data" type="application/json">__PAPER_DATA__</script>
<script>
"use strict";
const papers = JSON.parse(document.getElementById("paper-data").textContent);
const labels = {"wifi-csi":"WiFi CSI","game-ai":"Game AI","agent-ai":"Agent AI","computer-vision":"Computer Vision",other:"기타",candidate:"후보",keep:"Keep",triage:"트리아지",reading:"읽는 중",reviewed:"리뷰 완료",rejected:"제외"};
const $ = (id) => document.getElementById(id);
const value = (v, fallback="미상") => v === null || v === undefined || v === "" ? fallback : String(v);
function addOptions(id, values, formatter=(v)=>v){
  const select=$(id); for(const item of values){const option=document.createElement("option");option.value=String(item);option.textContent=formatter(item);select.append(option);}
}
const years=[...new Set(papers.map(p=>p.year).filter(Number.isInteger))].sort((a,b)=>b-a);
const categories=[...new Set(papers.map(p=>p.category).filter(Boolean))].sort();
const statuses=[...new Set(papers.map(p=>p.reading_status).filter(Boolean))].sort();
addOptions("category-filter",categories,v=>labels[v]||v);addOptions("status-filter",statuses,v=>labels[v]||v);addOptions("year-filter",years);
function drawBars(id, counts, formatter=(v)=>v){
  const root=$(id), entries=Object.entries(counts).sort((a,b)=>b[1]-a[1]||String(a[0]).localeCompare(String(b[0]))), max=Math.max(1,...entries.map(([,n])=>n));
  for(const [key,count] of entries){const row=document.createElement("div");row.className="bar-row";const name=document.createElement("span");name.textContent=formatter(key);const track=document.createElement("div");track.className="bar";const fill=document.createElement("i");fill.style.width=`${count/max*100}%`;track.append(fill);const number=document.createElement("b");number.textContent=count;row.append(name,track,number);root.append(row);}
  if(!entries.length)root.textContent="데이터 없음";
}
const byYear={};for(const p of papers){const k=value(p.year,"연도 미상");byYear[k]=(byYear[k]||0)+1;}
const byCategory={};for(const p of papers){const k=value(p.category,"분야 미상");byCategory[k]=(byCategory[k]||0)+1;}
drawBars("year-chart",byYear);drawBars("category-chart",byCategory,v=>labels[v]||v);
$("total").textContent=papers.length;
$("reviewed").textContent=papers.filter(p=>p.structured_review_status==="complete").length;
$("queued").textContent=papers.filter(p=>["candidate","keep","triage","reading"].includes(p.reading_status)).length;
$("categories").textContent=categories.length;
function make(tag,cls,text){const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node;}
function renderMarkdown(source){
  const escape=(s)=>s.replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;").replaceAll('"',"&quot;");
  const inline=(s)=>escape(s)
    .replace(/`([^`]+)`/g,"<code>$1</code>")
    .replace(/\*\*(.+?)\*\*/g,"<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g,"<em>$1</em>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g,'<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  const lines=source.replaceAll("\r\n","\n").split("\n"),out=[];let para=[],list="",code=false,codeLines=[],codeLanguage="";
  const flushPara=()=>{if(para.length){out.push(`<p>${inline(para.join(" "))}</p>`);para=[];}};
  const closeList=()=>{if(list){out.push(`</${list}>`);list="";}};
  for(let i=0;i<lines.length;i++){
    const line=lines[i];
    if(line.trim().startsWith("```")){flushPara();closeList();if(code){if(codeLanguage==="mermaid")out.push(renderFlowchart(codeLines));else out.push(`<pre><code>${escape(codeLines.join("\n"))}</code></pre>`);codeLines=[];code=false;codeLanguage="";}else{code=true;codeLanguage=line.trim().slice(3).trim();}continue;}
    if(code){codeLines.push(line);continue;}
    if(!line.trim()){flushPara();closeList();continue;}
    if(/^\s*\|/.test(line)){
      flushPara();closeList();const rows=[];
      while(i<lines.length&&/^\s*\|/.test(lines[i]))rows.push(lines[i++]);i--;
      const cells=(row)=>row.trim().replace(/^\|/,'').replace(/\|$/,'').split('|').map(x=>x.trim());
      const data=rows.map(cells).filter(row=>!row.every(cell=>/^:?-{3,}:?$/.test(cell)));
      if(data.length){const head=data.shift();out.push(`<table><thead><tr>${head.map(c=>`<th>${inline(c)}</th>`).join("")}</tr></thead><tbody>${data.map(row=>`<tr>${row.map(c=>`<td>${inline(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`);}
      continue;
    }
    const heading=line.match(/^\s{0,3}(#{1,6})\s+(.+?)\s*#*$/);
    if(heading){flushPara();closeList();const level=heading[1].length;out.push(`<h${level}>${inline(heading[2])}</h${level}>`);continue;}
    if(/^\s*(---+|\*\*\*+)\s*$/.test(line)){flushPara();closeList();out.push("<hr>");continue;}
    const quote=line.match(/^\s*>\s?(.*)$/);if(quote){flushPara();closeList();out.push(`<blockquote>${inline(quote[1])}</blockquote>`);continue;}
    const item=line.match(/^\s*(?:[-*+]\s+|(\d+)\.\s+)(.*)$/);
    if(item){flushPara();const type=item[1]?"ol":"ul";if(list!==type){closeList();list=type;out.push(`<${list}>`);}out.push(`<li>${inline(item[2])}</li>`);continue;}
    closeList();para.push(line.trim());
  }
  flushPara();closeList();if(code)out.push(`<pre><code>${escape(codeLines.join("\n"))}</code></pre>`);return out.join("\n");
}
function renderFlowchart(lines){
  const nodes=new Map(),edges=[];let direction="LR";
  const nodePattern=/^\s*([\w-]+)\s*(?:\[([^\]]*)\]|\(([^)]*)\)|\{([^}]*)\})?/;
  for(const raw of lines){const line=raw.trim();if(!line||line.startsWith("%%"))continue;const head=line.match(/^flowchart\s+(LR|RL|TB|TD|BT)/i);if(head){direction=head[1].toUpperCase();continue;}
    const parts=line.split(/\s*-->|\s*---|\s*==>/);if(parts.length<2){const match=line.match(nodePattern);if(match&&match[2])nodes.set(match[1],match[2]);continue;}
    const getNode=(part)=>{const m=part.match(nodePattern);if(!m)return null;const label=m[2]||m[3]||m[4]||m[1];nodes.set(m[1],label);return m[1];};
    let from=getNode(parts[0]);for(let i=1;i<parts.length;i++){const to=getNode(parts[i]);if(from&&to)edges.push([from,to]);from=to;}
  }
  if(!nodes.size){const pre=document.createElement("pre"),code=document.createElement("code");code.textContent=lines.join("\n");pre.append(code);return pre.outerHTML;}
  const horizontal=direction==="LR"||direction==="RL",ordered=[...nodes.keys()];if(direction==="RL"||direction==="BT")ordered.reverse();
  const row=document.createElement("div");row.className=`flowchart ${horizontal?"flow-horizontal":"flow-vertical"}`;
  for(const id of ordered){const box=document.createElement("div");box.className="flow-node";box.textContent=nodes.get(id);row.append(box);const outgoing=edges.filter(e=>e[0]===id).map(e=>nodes.get(e[1]));if(outgoing.length>1){const branch=document.createElement("div");branch.className="flow-branch";branch.textContent=`→ ${outgoing.join("  ·  ")}`;row.append(branch);}}
  return row.outerHTML;
}
const reviewStates=new Map();
const bridgeAddress="http://127.0.0.1:8765/100-views/paper-library.html";
const bridgeInfo=$("bridge-info");
function connectionHelp(message){
  bridgeInfo.replaceChildren(document.createTextNode(message+" "));
  const link=make("a","","로컬 실행기로 열기 ↗");link.href=bridgeAddress;bridgeInfo.append(link);
  bridgeInfo.append(document.createTextNode(" · 실행 명령: python3 .scripts/bin/onboard_research.py"));
}
if(location.protocol==="file:")connectionHelp("검색·필터·리뷰 보기는 바로 사용할 수 있습니다. 새 리뷰는 로컬 실행기에서 시작하세요.");
async function reviewRequest(url,options={}){
  const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
  try{
    const response=await fetch(url,{...options,signal:controller.signal,cache:"no-store"});
    let data;try{data=await response.json();}catch{throw new Error("리뷰 실행기가 아닌 주소입니다.");}
    if(!response.ok)throw new Error(data.error||`HTTP ${response.status}`);
    return data;
  }finally{clearTimeout(timer);}
}
async function startReview(p,statusNode,button){
  if(reviewStates.get(p.slug)?.busy)return;
  const update=(message,busy)=>{
    reviewStates.set(p.slug,{message,busy});statusNode.textContent=message;button.disabled=busy;
    for(const node of document.querySelectorAll("[data-review-slug]"))if(node.dataset.reviewSlug===p.slug){
      if(node.tagName==="BUTTON")node.disabled=busy;else node.textContent=message;
    }
  };
  if(location.protocol!=="http:"||location.hostname!=="127.0.0.1"){
    update("로컬 실행기로 연 뒤 리뷰를 시작하세요.",false);connectionHelp("리뷰를 시작하려면 로컬 실행기를 실행하세요.");return;
  }
  update("로컬 리뷰 실행기 연결 중…",true);
  try{
    const status=await reviewRequest("/api/status");
    if(!["codex-cli","claude-cli"].includes(status.runner))throw new Error("리뷰 실행기가 아닌 주소입니다.");
    if(!status.ready)throw new Error(status.reason||"에이전트 연결이 필요합니다. 온보딩 명령을 실행하세요.");
    const accepted=await reviewRequest("/api/reviews",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({slug:p.slug})});
    const job=accepted.job;
    if(!job?.job_id)throw new Error("작업 ID를 받지 못했습니다.");
    update("리뷰 작업을 대기열에 넣었습니다.",true);
    const poll=async()=>{
      try{
        const current=await reviewRequest(`/api/reviews/${encodeURIComponent(p.slug)}`);
        const latest=current.jobs?.find(item=>item.job_id===job.job_id);
        if(!latest)throw new Error("리뷰 작업을 찾을 수 없습니다. 실행기 상태를 확인하세요.");
        if(latest.status==="completed"){
          update("리뷰 완료. 새 리뷰를 불러오는 중…",false);location.reload();return;
        }
        if(latest.status==="failed"){update(`리뷰 실패: ${latest.message||"실행 기록을 확인하세요."}`,false);return;}
        update(`리뷰 진행 중 (${latest.status})`,true);setTimeout(poll,3000);
      }catch(error){update(`상태 조회 실패: ${error.message}`,false);}
    };setTimeout(poll,1500);
  }catch(error){update(`실행기 연결 실패: ${error.message}`,false);connectionHelp("리뷰 실행기 연결을 확인하세요.");}
}
async function restoreActiveReviews(){
  if(location.protocol!=="http:"||location.hostname!=="127.0.0.1")return;
  try{
    const status=await reviewRequest("/api/status");
    bridgeInfo.textContent=status.ready?`연결된 에이전트: ${status.agent||status.runner} · 본인 계정으로 리뷰 실행`:`에이전트 연결 필요: ${status.reason||"python3 .scripts/bin/onboard_research.py"}`;
    const latest=new Map((status.queue?.jobs||[]).map(job=>[job.slug,job]));
    let active=false,completed=false;
    for(const job of latest.values()){
      const busy=job.status==="queued"||job.status==="running";
      if(busy){reviewStates.set(job.slug,{busy:true,message:`리뷰 진행 중 (${job.status})`});active=true;}
      else if(reviewStates.get(job.slug)?.busy){
        reviewStates.set(job.slug,{busy:false,message:job.status==="failed"?`리뷰 실패: ${job.message||"실행 기록을 확인하세요."}`:"리뷰 완료"});
        if(job.status==="completed")completed=true;
      }
    }
    if(completed){location.reload();return;}
    render();
    if(active)setTimeout(restoreActiveReviews,3000);
  }catch(error){connectionHelp(`실행기 상태를 확인할 수 없습니다: ${error.message}`);}
}
function openReview(p){
  $("review-title").textContent=`${p.catalog_display_title||p.title||p.slug} · 리뷰`;
  $("review-body").innerHTML=renderMarkdown(p.catalog_review_markdown||"");
  $("review-dialog").showModal();
}
$("review-close").addEventListener("click",()=>$("review-dialog").close());
$("review-dialog").addEventListener("click",event=>{if(event.target===$("review-dialog"))$("review-dialog").close();});
function render(){
  const q=$("search").value.trim().toLocaleLowerCase(), category=$("category-filter").value,status=$("status-filter").value,year=$("year-filter").value;
  const matches=papers.filter(p=>{
    const hay=[p.catalog_display_title,p.title,p.slug,...(p.authors||[]),...(p.topics||[]),p.abstract,p.one_line_summary,p.publication?.venue].filter(Boolean).join(" ").toLocaleLowerCase();
    return (!q||hay.includes(q))&&(!category||p.category===category)&&(!status||p.reading_status===status)&&(!year||String(p.year)===year);
  }).sort((a,b)=>(b.year||0)-(a.year||0)||String(a.title).localeCompare(String(b.title)));
  $("result-count").textContent=`${matches.length} / ${papers.length}편 표시`;
  const root=$("papers");root.replaceChildren();if(!matches.length){root.append(make("div","empty","조건에 맞는 논문이 없습니다."));return;}
  for(const p of matches){
    const card=make("article","paper"),main=make("div"),heading=make("h3");
    const title=make("span","",p.catalog_display_title||p.title||p.slug||"제목 확인 필요");heading.append(title);
    if(p.catalog_review_markdown){const button=make("button","review-action","리뷰 보기");button.type="button";button.addEventListener("click",event=>{event.stopPropagation();openReview(p);});heading.append(button);}
    const state=reviewStates.get(p.slug);
    const reviewStatus=make("span","link-status",state?.message||"");reviewStatus.dataset.reviewSlug=p.slug;reviewStatus.setAttribute("role","status");
    if(p.catalog_review_needed){const start=make("button","review-action","리뷰 시작");start.type="button";start.dataset.reviewSlug=p.slug;start.disabled=!!state?.busy;start.addEventListener("click",event=>{event.stopPropagation();startReview(p,reviewStatus,start);});heading.append(start);heading.append(reviewStatus);}
    main.append(heading);
    main.append(make("div","meta",`${value(p.year)} · ${value((p.authors||[]).slice(0,2).join(", "))}${(p.authors||[]).length>2?" 외":""} · ${value(p.publication?.venue)}`));
    if(p.one_line_summary)main.append(make("div","summary",p.one_line_summary));
    if((p.topics||[]).length){const topics=make("div","topics");for(const t of p.topics)topics.append(make("span","topic",t));main.append(topics);}
    const linkStatus=make("span","link-status","");
    let target="";
    try{
      if(typeof p.catalog_original_url==="string"&&p.catalog_original_url.trim()){
        const path=/^https?:\/\//i.test(p.catalog_original_url)?p.catalog_original_url:"../"+p.catalog_original_url;
        const resolved=new URL(path,document.baseURI);
        if(["file:","http:","https:"].includes(resolved.protocol))target=resolved.href;
      }
    }catch{}
    const open=make("a","paper-action",target?"원문 열기 ↗":"원문을 열 수 없음");
    open.href=target||"#";open.target="_blank";open.rel="noopener noreferrer";
    if(!target){
      open.setAttribute("aria-disabled","true");
      open.addEventListener("click",event=>{event.preventDefault();linkStatus.textContent="유효한 저장소 PDF 또는 HTTP(S) 원문 URL이 없습니다.";linkStatus.style.color="#ffc7f0";});
    }else{
      open.addEventListener("click",()=>{linkStatus.textContent="새 탭에서 원문을 여는 중입니다. 열리지 않으면 브라우저의 팝업 또는 로컬 파일 권한을 확인하세요.";});
    }
    open.addEventListener("click",event=>event.stopPropagation());main.append(open,linkStatus);
    const badges=make("div","badges");badges.append(make("span","badge",labels[p.category]||value(p.category)),make("span","badge status",labels[p.reading_status]||value(p.reading_status)),make("span","badge",p.structured_review_status==="complete"?"구조화 리뷰 완료":"구조화 리뷰 대기"));
    card.append(main,badges);root.append(card);
  }
}
for(const id of ["search","category-filter","status-filter","year-filter"])$(id).addEventListener("input",render);
for(const id of ["category-filter","status-filter","year-filter"])$(id).addEventListener("change",render);
render();
restoreActiveReviews();
</script>
</body>
</html>
'''


def main() -> None:
    records = load_records()
    embedded = json.dumps(records, ensure_ascii=False, separators=(",", ":"))
    embedded = embedded.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(HTML.replace("__PAPER_DATA__", embedded).replace("__SHARED_STYLE__", STYLESHEET).replace("__PAGE_HEADER__", page_header('papers', '다음 발견이 시작되는 곳', 'PAPER LIBRARY', '관심 있는 논문을 찾고, 원문과 리뷰를 이어서 읽으세요. 읽기 상태와 연구 분야도 함께 정리할 수 있습니다.', '논문 찾아보기', '#search')), encoding="utf-8")
    print(f"Generated {OUTPUT.relative_to(ROOT)} with {len(records)} records ({date.today().isoformat()}).")


if __name__ == "__main__":
    main()
