"""Optional local multimodal review using a user-installed Ollama vision model.

No paid provider, no uploads or cloud URLs, no automatic model downloads.
Output is advisory and must never override native QA or owner approval.
"""
from pathlib import Path
from typing import Literal
import subprocess,base64,json,re
import httpx
from pydantic import BaseModel,Field,ConfigDict

class Finding(BaseModel):
    model_config=ConfigDict(extra="forbid")
    time_seconds:float=Field(ge=0)
    category:Literal["acting","composition","continuity","collision","readability","story","other"]
    observation:str=Field(min_length=3,max_length=600)
    suggestion:str=Field(min_length=3,max_length=600)

class VisionReport(BaseModel):
    model_config=ConfigDict(extra="forbid")
    findings:list[Finding]=Field(max_length=20)
    limitations:str=Field(max_length=1000)

def frame(path,t):
    data=subprocess.run(["ffmpeg","-v","error","-ss",str(t),"-i",str(path),"-frames:v","1",
                         "-vf","scale=640:-2","-f","image2pipe","-vcodec","mjpeg","-"],
                        capture_output=True,check=True,timeout=30).stdout
    if not data:raise ValueError("Frame unavailable")
    return base64.b64encode(data).decode("ascii")

def review_video(path,model,*,client=None):
    path=Path(path)
    if not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,100}",model):raise ValueError("Invalid local model name")
    probe=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=nw=1:nk=1",str(path)],
                         capture_output=True,check=True,timeout=30,text=True)
    duration=float(probe.stdout)
    if not 0<duration<=360:raise ValueError("Review supports clips up to 360 seconds")
    times=[round(duration*(i+.5)/6,3) for i in range(6)]
    images=[frame(path,t) for t in times]
    prompt=("Review these actual APEX frames in order, timestamps seconds "+str(times)+
            ". Identify only visible concerns; do not infer physics, motion between frames or artistic approval. "
            "Return structured observations and actionable suggestions. Distinguish uncertainty.")
    payload={"model":model,"stream":False,"format":VisionReport.model_json_schema(),
             "messages":[{"role":"user","content":prompt,"images":images}],
             "options":{"temperature":0,"num_predict":1400}}
    # Fixed loopback destination, no redirects and no proxy forwarding.
    own=client is None
    c=client or httpx.Client(timeout=180,trust_env=False,follow_redirects=False)
    try:
        response=c.post("http://127.0.0.1:11434/api/chat",json=payload);response.raise_for_status()
        report=VisionReport.model_validate_json(response.json()["message"]["content"])
    finally:
        if own:c.close()
    if any(f.time_seconds>duration for f in report.findings):raise ValueError("Critic timestamp exceeds video")
    return {"method":"local model sampled images; no continuous-video analysis","model":model,"frame_times":times,
            "advisory":True,**report.model_dump(mode="json")}
