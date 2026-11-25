from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime
import runpy
import sys

def test_combined_crossing_native(tmp_path, monkeypatch):
    p = tmp_path / "fallen.json"
    monkeypatch.setattr(sys, "argv", ["build_combined_crossing.py", str(p)])
    runpy.run_path("examples/build_combined_crossing.py", run_name="__main__")
    sim = SceneRuntime(ProjectSpec.model_validate_json(p.read_text()), "s").simulate()
    def event(kind, who):
        return next((e for e in sim.events if e.type == kind and e.character == who), None)
    second_push = next((e for e in sim.events if e.type == "nudge" and e.character == "iko" and e.data.get("with") == "ren"), None)
    seq = [event("nudge","iko"),event("nudge_clear","iko"),second_push,event("settled","ren"),event("adaptive_jump","iko"),event("takeoff","iko")]
    assert all(seq), [(e.type,e.character,e.data) for e in sim.events if e.type in ("nudge_blocked","settled","adaptive_jump","takeoff")]
    assert all(a.t <= b.t for a,b in zip(seq,seq[1:]))
    rec = sim.controllers["iko"].records
    assert any(r.mode == "airborne" for r in rec)
    landing = next((e for e in sim.events if e.type == "impact" and e.character == "iko" and e.t > seq[-1].t), None)
    assert landing is not None, "no physical landing after jump"
    assert sim.controllers["iko"].mode == "grounded"
    assert rec[-1].frame == "floor"
    assert rec[-1].pos[0] > 1000
    assert event("nudge_clear","iko") is not None
    assert any(e.type == "nudge" and e.data.get("with") == "ren" for e in sim.events)
    assert min(b.pos[0]-a.pos[0] for a,b in zip(rec,rec[1:])) >= -1.0, "unexpected backward travel"
    assert rec[-1].pos[0] > sim.controllers["ren"].records[-1].pos[0] + 180
