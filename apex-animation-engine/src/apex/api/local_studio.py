"""Loopback-only local APEX Studio with durable job status and no secret UI.

Start: python -m apex.api.local_studio
One worker avoids CPU contention and concurrent budget-ledger writes.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4
import os,json,secrets,re,threading
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import HTMLResponse,FileResponse
from pydantic import BaseModel,Field
from ..ai.local_production import atomic,read,create_from_brief,run_production,approve_preview,stage_project
from ..scene.schema import ProjectSpec

ROOT=Path(os.environ.get("APEX_STUDIO_DIR","apex_data/local_studio")).resolve()
ROOT.mkdir(parents=True,exist_ok=True)
TOKEN=secrets.token_urlsafe(32)
POOL=ThreadPoolExecutor(max_workers=1)
LOCK=threading.Lock()
app=FastAPI(title="APEX Local Studio",docs_url=None,redoc_url=None,openapi_url=None)

@app.middleware("http")
async def local_only(request:Request,call_next):
    from fastapi.responses import JSONResponse
    host=request.headers.get("host","").split(":")[0]
    if host not in ("127.0.0.1","localhost") or request.client is None or request.client.host not in ("127.0.0.1","::1"):
        return JSONResponse({"detail":"Loopback only"},403)
    if request.method!="GET" and request.headers.get("x-apex-local")!=TOKEN:
        return JSONResponse({"detail":"Local session token required"},403)
    return await call_next(request)

def folder(jid):
    if not re.fullmatch(r"[0-9a-f]{32}",jid):raise HTTPException(404)
    p=ROOT/jid
    if not p.is_dir():raise HTTPException(404)
    return p
def status(p,**changes):
    with LOCK:
        f=p/"status.json";s=read(f) if f.exists() else {};s.update(changes);atomic(f,s)
def worker(p,mode,brief=None,offline=True,project=None):
    try:
        status(p,state="running",stage=mode,error=None)
        if mode=="preview" and not (p/"project.json").exists():
            if project is not None:stage_project(project,p)
            else:create_from_brief(brief,p,offline=offline,reason="Local Studio owner requested production")
        def progress(stage,fraction,message):status(p,stage=stage,progress=fraction,message=message)
        run_production(p,final=mode=="final",progress=progress)
        status(p,state="done",stage=mode,progress=1)
    except Exception as exc:status(p,state="failed",error=f"{type(exc).__name__}: {exc}")
def submit(p,mode,**kw):
    status(p,state="queued",stage=mode,progress=0,error=None)
    POOL.submit(worker,p,mode,**kw)

class Brief(BaseModel):
    story:str=Field(min_length=5,max_length=12000)
    offline:bool=True
class Review(BaseModel):
    review:str=Field(min_length=3,max_length=2000)

@app.get("/",response_class=HTMLResponse)
def index():return HTML.replace("__TOKEN__",TOKEN)
@app.post("/jobs")
def create(b:Brief):
    if not b.offline and os.environ.get("APEX_AI_PAID_ENABLED")!="1":raise HTTPException(403,"Enable approved provider and spend limits first")
    jid=uuid4().hex;p=ROOT/jid;p.mkdir()
    atomic(p/"brief.json",b.model_dump());submit(p,"preview",brief=b.story,offline=b.offline);return {"id":jid}
@app.post("/projects")
def create_project(raw:dict):
    try:p=ProjectSpec.model_validate(raw)
    except ValueError as e:raise HTTPException(422,str(e))
    jid=uuid4().hex;d=ROOT/jid;d.mkdir();stage_project(p,d);submit(d,"preview");return {"id":jid}
@app.get("/jobs")
def jobs():
    return [{"id":p.name,**read(p/"status.json")} for p in sorted(ROOT.iterdir(),reverse=True)
            if p.is_dir() and (p/"status.json").exists()]
@app.get("/jobs/{jid}")
def job(jid):return read(folder(jid)/"status.json")
@app.post("/jobs/{jid}/resume")
def resume(jid):
    p=folder(jid)
    with LOCK:
        state=read(p/"status.json")
        if state["state"] not in ("failed","interrupted"):raise HTTPException(409,"Not resumable")
        atomic(p/"status.json",{**state,"state":"queued"})
    b=read(p/"brief.json") if (p/"brief.json").exists() else {}
    POOL.submit(worker,p,state.get("stage") if state.get("stage") in ("preview","final") else "preview",brief=b.get("story"),offline=b.get("offline",True))
    return {"id":jid}
@app.post("/jobs/{jid}/approve")
def approve(jid,r:Review):
    p=folder(jid)
    if read(p/"status.json")["state"]!="done":raise HTTPException(409)
    try:approve_preview(p,r.review)
    except (ValueError,OSError) as e:raise HTTPException(422,str(e))
    submit(p,"final");return {"id":jid}
@app.get("/jobs/{jid}/video/{mode}")
def video(jid,mode):
    p=folder(jid)
    if mode not in ("preview","final"):raise HTTPException(404)
    r=p/(mode+"_report.json")
    if not r.exists() or not read(r).get("technical_pass"):raise HTTPException(404,"No passing video")
    return FileResponse(p/(mode+".mp4"),media_type="video/mp4")
@app.get("/jobs/{jid}/report/{mode}")
def report(jid,mode):
    if mode not in ("preview","final"):raise HTTPException(404)
    p=folder(jid)/(mode+"_report.json")
    if not p.exists():raise HTTPException(404)
    return read(p)

HTML="""<!doctype html><html><head><meta charset="utf-8"><title>APEX Local Studio</title>
<style>body{font:16px system-ui;background:#111923;color:#e3ecf5;max-width:850px;margin:35px auto;padding:0 16px}textarea,input,button,select{font:inherit;padding:10px;border-radius:6px}textarea{box-sizing:border-box;width:100%;min-height:120px}button{background:#efb94b;color:#161a20;cursor:pointer;border:0;margin:7px 5px 7px 0}video{width:100%;background:#000}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#1c2937;padding:12px}section{margin:22px 0}</style></head>
<body><h1>APEX Local Studio</h1><p>Native rehearsal, preview and owner-approved final render. Offline uses existing templates, not unrestricted AI.</p>
<textarea id="story" placeholder="Describe your story"></textarea><label><input type="checkbox" id="paid"> Use configured paid AI (budget controls apply)</label><br><button id="create">Create preview</button>
<section><select id="jobs"></select><button id="load">Refresh jobs</button><button id="resume">Resume failed job</button></section>
<pre id="status"></pre><video id="video" controls></video>
<input id="review" placeholder="Review notes after watching preview"><button id="approve">Approve preview & render final</button><button id="report">Read QA report</button>
<pre id="qa"></pre><script>
const token="__TOKEN__", q=id=>document.getElementById(id);let active="",shown="";
async function api(path,body){const r=await fetch(path,body===undefined?{}:{method:"POST",headers:{"Content-Type":"application/json","X-APEX-Local":token},body:JSON.stringify(body)});const j=await r.json();if(!r.ok)throw Error(JSON.stringify(j.detail));return j}
async function refresh(){const rows=await api("/jobs");q("jobs").replaceChildren();for(const r of rows){let o=document.createElement("option");o.value=r.id;o.textContent=r.id.slice(0,8)+" "+r.state;q("jobs").append(o)}if(active)q("jobs").value=active;else if(rows.length)active=rows[0].id}
async function poll(){if(!active)return;let s=await api("/jobs/"+active);q("status").textContent=JSON.stringify(s,null,2);if(s.state==="done"){let mode=s.stage==="final"?"final":"preview",url="/jobs/"+active+"/video/"+mode;if(shown!==url){q("video").src=url;shown=url}}}
function run(fn){return async()=>{try{await fn()}catch(e){q("status").textContent=e.message}}}
q("create").onclick=run(async()=>{active=(await api("/jobs",{story:q("story").value,offline:!q("paid").checked})).id;await refresh();await poll()});
q("load").onclick=run(refresh);q("jobs").onchange=()=>{active=q("jobs").value;shown="";q("video").removeAttribute("src");q("video").load();poll().catch(()=>{})};
q("resume").onclick=run(async()=>{await api("/jobs/"+active+"/resume",{});await poll()});
q("approve").onclick=run(async()=>{await api("/jobs/"+active+"/approve",{review:q("review").value});await poll()});
q("report").onclick=run(async()=>{let s=await api("/jobs/"+active);q("qa").textContent=JSON.stringify(await api("/jobs/"+active+"/report/"+(s.stage==="final"?"final":"preview")),null,2)});
refresh().then(poll).catch(()=>{});setInterval(()=>poll().catch(()=>{}),2500);</script></body></html>"""

def main():
    # A process restart cannot silently label orphaned work as running.
    for d in ROOT.iterdir():
        f=d/"status.json"
        if d.is_dir() and f.exists() and read(f).get("state") in ("queued","running"):status(d,state="interrupted")
    import uvicorn
    uvicorn.run(app,host="127.0.0.1",port=8078,workers=1)
if __name__=="__main__":main()
