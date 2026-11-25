from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime
import runpy
import sys

def test_fallen_crossing_native(tmp_path, monkeypatch):
    p = tmp_path / "fallen.json"
    monkeypatch.setattr(sys, "argv", ["build_fallen_crossing.py", str(p)])
    runpy.run_path("examples/build_fallen_crossing.py", run_name="__main__")
    sim = SceneRuntime(ProjectSpec.model_validate_json(p.read_text()), "s").simulate()
    def event(kind, who):
        return next((e for e in sim.events if e.type == kind and e.character == who), None)
    seq = [event("nudge","iko"),event("settled","pell"),event("adaptive_jump","iko"),event("takeoff","iko")]
    assert all(seq), [(e.type,e.character,e.data) for e in sim.events if e.type in ("nudge_blocked","settled","adaptive_jump","takeoff")]
    assert all(a.t <= b.t for a,b in zip(seq,seq[1:]))
    rec = sim.controllers["iko"].records
    assert any(r.mode == "airborne" for r in rec)
    assert rec[-1].mode == "grounded"
    assert rec[-1].pos[0] > sim.controllers["pell"].records[-1].pos[0] + 180
