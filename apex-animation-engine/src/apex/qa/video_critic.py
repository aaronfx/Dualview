"""Inspect decoded preview pixels, not just simulation claims.

Detect long near-black and nearly static runs. These are advisory because a
deliberate fade or held pose can be good filmmaking. No vision-LLM claims.
"""
import subprocess
import numpy as np

def inspect_video(path):
    w,h,hz=96,54,2
    cmd=["ffmpeg","-v","error","-xerror","-i",str(path),"-an","-vf",
         f"fps={hz},scale={w}:{h},format=gray","-f","rawvideo","-"]
    raw=subprocess.run(cmd,check=True,capture_output=True,timeout=180).stdout
    n=w*h
    if not raw or len(raw)%n:raise ValueError("No complete decoded preview frames")
    frames=np.frombuffer(raw,dtype=np.uint8).reshape(-1,h,w).astype(np.float32)
    black=(frames.mean(axis=(1,2))<4)
    still=np.r_[False,(np.abs(np.diff(frames,axis=0)).mean(axis=(1,2))<.35)]
    findings=[]
    for kind,flags,minlen in (("near_black",black,3),("nearly_static",still,5)):
        start=None
        for i,v in enumerate([*flags,False]):
            if v and start is None:start=i
            if not v and start is not None:
                if i-start>=minlen:findings.append({"kind":kind,"start":start/hz,"end":i/hz,"severity":"advisory"})
                start=None
    return {"method":"decoded grayscale frame sampling at 2 Hz","samples":len(frames),"findings":findings}
