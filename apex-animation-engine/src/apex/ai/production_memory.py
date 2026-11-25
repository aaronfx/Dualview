"""Local, evidence-based production memory. No training or imaginary outcomes."""
from __future__ import annotations
from pathlib import Path
import json, sqlite3, hashlib
from .character_brain import CharacterBrain, Personality, Perception, Intent

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(",",":"),default=str).encode()).hexdigest()

class ProductionMemory:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.executescript("""
            CREATE TABLE IF NOT EXISTS evidence(project TEXT,scene TEXT,hash TEXT,payload TEXT,
            PRIMARY KEY(project,scene,hash));
            CREATE TABLE IF NOT EXISTS approval(project TEXT,hash TEXT,review TEXT,PRIMARY KEY(project,hash));
            """)
    def connect(self):return sqlite3.connect(self.path)
    def record(self,project,scene,sim):
        """Only call after real native simulation. Replays deduplicate by evidence hash."""
        events=[{"t":float(e.t),"type":e.type,"actor":e.character,"data":e.data} for e in sim.events
                if e.type not in ("footstep","prop_impact")]
        states={}
        for cid,ctrl in sim.controllers.items():
            records=ctrl.records
            states[cid]={"position":list(records[-1].pos) if len(records) else None,
                         "velocity":list(records[-1].vel) if len(records) else None,
                         "violation":ctrl.violation,"carrying":getattr(ctrl,"carrying",None)}
        payload={"actors":states,"events":events}
        key=digest(payload)
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO evidence VALUES(?,?,?,?)",(project,scene,key,json.dumps(payload,default=str)))
        return key
    def recall(self,project,limit=12):
        with self.connect() as db:
            rows=db.execute("SELECT scene,hash,payload FROM evidence WHERE project=? ORDER BY rowid DESC LIMIT ?",
                            (project,max(1,min(100,limit)))).fetchall()
        return [{"scene":s,"hash":h,**json.loads(p)} for s,h,p in rows]
    def actor_brain(self,project,actor,personality=None):
        brain=CharacterBrain(personality or Personality())
        # Scope memory to this production. A failed trial does not become
        # canon; callers only record the selected actual scene.
        for scene in reversed(self.recall(project)):
            for e in scene["events"]:
                if e["actor"]!=actor:continue
                typ=e["type"];data=e["data"]
                target=str(data.get("prop") or data.get("target") or data.get("by") or "world")
                if typ in ("push_fail","lift_fail","grab_missed","help_missed","action_impossible"):
                    intent=Intent.HELP if typ=="help_missed" else Intent.APPROACH
                    brain.record_outcome(target,intent,succeeded=False)
                elif typ in ("pick_up","lift_ok","climbed","hand_grab"):
                    brain.record_outcome(target,Intent.HELP if typ=="hand_grab" else Intent.APPROACH,succeeded=True)
        return brain
    def approve(self,project,hash_,review):
        if not review.strip():raise ValueError("human review required")
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO approval VALUES(?,?,?)",(project,hash_,review))
    def approved(self,project,hash_):
        with self.connect() as db:
            return db.execute("SELECT review FROM approval WHERE project=? AND hash=?",(project,hash_)).fetchone() is not None
