"""Read-only native simulation interchange for alternate presentation backends."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .runtime import SceneRuntime
from .schema import ProjectSpec


def export_scene(project: ProjectSpec, scene_id: str) -> dict:
    runtime = SceneRuntime(project, scene_id)
    result = runtime.simulate()
    frames = []
    for index in range(int(result.duration * project.fps) + 1):
        t = index / project.fps
        state = runtime.evaluate(t)
        frames.append({
            "t": t,
            "actors": {cid: {"joints": {k: [float(v[0]), float(v[1])]
                                       for k, v in runtime.rigs[cid].world_joints(pose).items()},
                             "depth": float(state.depth.get(cid, 0))}
                       for cid, pose in state.poses.items()},
            "props": [{"id": p.id, "kind": p.kind, "pos": list(p.pos),
                       "size": list(p.size), "angle": p.angle, "glyph": p.glyph,
                       "depth": p.depth, "z": p.z} for p in state.props],
        })
    return {"version": 1, "scene": scene_id, "fps": project.fps,
            "width": project.width, "height": project.height,
            "duration": result.duration, "frames": frames,
            "events": [{"t": e.t, "type": e.type, "actor": e.character} for e in result.events]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("--scene", required=True)
    parser.add_argument("-o", required=True)
    args = parser.parse_args()
    project = ProjectSpec.model_validate_json(Path(args.project).read_text(encoding="utf-8"))
    Path(args.o).write_text(json.dumps(export_scene(project, args.scene), allow_nan=False), encoding="utf-8")


if __name__ == "__main__":
    main()
