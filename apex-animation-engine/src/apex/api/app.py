"""FastAPI backend (independent service; no Creator Studio dependency).

Endpoints
  GET  /health
  GET  /schema                       JSON schema of ProjectSpec
  POST /projects                     create/replace a project (validated)
  GET  /projects                     list
  GET  /projects/{pid}               fetch spec
  POST /projects/{pid}/scenes/{sid}/render   render ONE scene as a background job (scene-level regeneration)
  GET  /jobs/{jid}                   status, stage, progress, QA report, error
  GET  /jobs/{jid}/video             finished MP4
  POST /plan                         story -> validated project (AI provider from backend env, or offline template)
"""
from __future__ import annotations

import json
import os
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ValidationError

from ..scene.schema import ProjectSpec, json_schema
from .storage import Repository

DATA_DIR = os.environ.get("APEX_DATA_DIR", os.path.abspath("apex_data"))
os.makedirs(DATA_DIR, exist_ok=True)

app = FastAPI(title="APEX Animation Engine", version="0.1.0")
repo = Repository(os.path.join(DATA_DIR, "apex.db"))
_pool = ThreadPoolExecutor(max_workers=int(os.environ.get("APEX_RENDER_WORKERS", "1")))


class RenderRequest(BaseModel):
    samples: int = 1
    scale: float = 1.0
    qa: bool = True


class PlanRequest(BaseModel):
    story: str
    offline: bool = False
    save: bool = True


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/schema")
def schema() -> dict:
    return json_schema()


@app.post("/projects")
def create_project(spec: dict) -> dict:
    try:
        proj = ProjectSpec.model_validate(spec)
    except ValidationError as e:
        raise HTTPException(422, detail=json.loads(e.json(include_url=False)))
    repo.save_project(proj.id, proj.title, proj.model_dump(mode="json"))
    return {"id": proj.id, "scenes": [s.id for s in proj.scenes]}


@app.get("/projects")
def list_projects() -> list:
    return repo.list_projects()


@app.get("/projects/{pid}")
def get_project(pid: str) -> dict:
    p = repo.get_project(pid)
    if p is None:
        raise HTTPException(404, "project not found")
    return p


def _run_job(jid: str, pid: str, sid: str, req: RenderRequest) -> None:
    from ..render.pipeline import render_scene
    try:
        proj = ProjectSpec.model_validate(repo.get_project(pid))
        out = os.path.join(DATA_DIR, "renders", f"{pid}__{sid}__{jid}.mp4")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        repo.update_job(jid, status="running")

        def prog(stage: str, frac: float, msg: str) -> None:
            repo.update_job(jid, stage=stage, progress=frac, message=msg)

        res = render_scene(proj, sid, out, samples=req.samples, qa=req.qa, preview_scale=req.scale, progress=prog)
        repo.update_job(jid, status="done", progress=1.0, video=out, qa=json.dumps(res.qa.to_dict(), default=str) if res.qa else None)
    except Exception as e:  # noqa: BLE001 - failures are recorded on the job, never swallowed
        repo.update_job(jid, status="failed", error=f"{type(e).__name__}: {e}\n{traceback.format_exc()[-2000:]}")


@app.post("/projects/{pid}/scenes/{sid}/render")
def render(pid: str, sid: str, req: Optional[RenderRequest] = None) -> dict:
    spec = repo.get_project(pid)
    if spec is None:
        raise HTTPException(404, "project not found")
    if sid not in [s["id"] for s in spec["scenes"]]:
        raise HTTPException(404, "scene not found")
    jid = repo.create_job(pid, sid)
    _pool.submit(_run_job, jid, pid, sid, req or RenderRequest())
    return {"job": jid}


@app.get("/jobs/{jid}")
def job(jid: str) -> dict:
    j = repo.get_job(jid)
    if j is None:
        raise HTTPException(404, "job not found")
    return j


@app.get("/jobs/{jid}/video")
def job_video(jid: str):
    j = repo.get_job(jid)
    if j is None or j["status"] != "done" or not j["video"]:
        raise HTTPException(404, "video not available")
    return FileResponse(j["video"], media_type="video/mp4")


@app.post("/plan")
def plan(req: PlanRequest) -> dict:
    from ..ai.director import PlanningError, StoryDirector
    d = StoryDirector.from_env(offline=req.offline)
    try:
        proj = d.plan(req.story)
    except PlanningError as e:
        raise HTTPException(422, str(e))
    if req.save:
        repo.save_project(proj.id, proj.title, proj.model_dump(mode="json"))
    return {"planner": d.name, "project": proj.model_dump(mode="json")}
