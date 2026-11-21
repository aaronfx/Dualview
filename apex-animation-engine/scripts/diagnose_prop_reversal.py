"""Print data-backed prop reversals and character proximity for Rescue debugging.

Run as: python scripts/diagnose_prop_reversal.py
APEX_EXPERIMENTAL_ACTIVE_FALL=1 APEX_EXPERIMENTAL_JOINTED_FALL=1 to reproduce video.
"""
import json
from pathlib import Path
import numpy as np
from apex.scene.schema import ProjectSpec
from apex.scene.runtime import SceneRuntime

root = Path(__file__).resolve().parents[1]
data = json.loads((root / "examples" / "the_rescue.json").read_text(encoding="utf-8"))
rt = SceneRuntime(ProjectSpec.model_validate(data), "rescue")
result = rt.simulate()
ix = [p.id for p in rt.env.props].index("container")
x = result.prop_tracks["container"][:, 0]
t = result.prop_times
velocity = np.gradient(x, t)
juno = result.controllers["juno"].records
print("container timeline: sec, center_x, dx/dt, juno_x, milo_x")
for sec in np.arange(1.0, 8.01, .25):
    i = int(np.abs(t - sec).argmin())
    jr = min(juno, key=lambda r: abs(r.t - sec))
    mr = min(result.controllers["milo"].records, key=lambda r: abs(r.t - sec))
    print(f"{sec:5.2f}, {x[i]:9.2f}, {velocity[i]:8.2f}, {jr.pos[0]:9.2f}, {mr.pos[0]:9.2f}")
for i in range(1, len(velocity)):
    if 1.0 <= t[i] < 8.0 and velocity[i-1] > 50.0 and velocity[i] < -20.0:
        print(f"REVERSE at {t[i]:.3f}: x={x[i]:.1f} v={velocity[i-1]:.1f} -> {velocity[i]:.1f}")
