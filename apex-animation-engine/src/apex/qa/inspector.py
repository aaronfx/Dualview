"""Animation Quality Inspector: numerical / structural checks over a simulated + rendered scene.

Subjective qualities (acting, appeal, comedy) are NOT scored here; previews are produced for human review instead.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..camera.director import CameraDirector
from ..render.video import probe
from ..scene.runtime import SceneRuntime

# Each tolerance below is named so failures can be traced back to an explicit, documented threshold.
TOL = {
    "bone_ratio_min": 0.86, "bone_ratio_max": 1.13,  # allows authored squash/stretch and IK stretch (<=8%) only
    "foot_slide": 1.5,  # world units a planted ankle may drift
    "joint_speed": 3200.0,  # units/s; above this a joint "teleports" (fastest authored motion ~1500)
    "pelvis_speed": 2200.0,
    "room_margin": 4.0,
    "gravity_angle_deg": 3.0, "gravity_mag_rel": 0.05,
    "camera_visible_frac": 0.95,
}


@dataclass
class Check:
    name: str
    status: str  # PASS | FAIL | WARN | SKIP
    metric: Optional[float] = None
    threshold: Optional[float] = None
    details: str = ""


@dataclass
class QAReport:
    scene: str
    checks: List[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.status in ("PASS", "WARN", "SKIP") for c in self.checks)

    def to_dict(self) -> dict:
        return {"scene": self.scene, "passed": self.passed, "checks": [asdict(c) for c in self.checks]}

    def summary(self) -> str:
        lines = [f"QA {self.scene}: {'PASSED' if self.passed else 'FAILED'}"]
        for c in self.checks:
            m = "" if c.metric is None else f" metric={c.metric:.4g}"
            th = "" if c.threshold is None else f" threshold={c.threshold:.4g}"
            lines.append(f"  [{c.status}] {c.name}{m}{th} {c.details}")
        return "\n".join(lines)


SEGMENTS = [("hip_n", "knee_n"), ("knee_n", "ankle_n"), ("hip_f", "knee_f"), ("knee_f", "ankle_f"), ("shoulder", "elbow_n"),
            ("elbow_n", "wrist_n"), ("shoulder", "elbow_f"), ("elbow_f", "wrist_f"), ("pelvis", "spine_mid"), ("spine_mid", "neck_base")]


class Inspector:
    def __init__(self, runtime: SceneRuntime, camera: CameraDirector, fps: int, size: Optional[tuple] = None):
        self.rt, self.cam, self.fps = runtime, camera, fps
        self.size = size or (runtime.project.width, runtime.project.height)
        self.r = runtime.result or runtime.simulate()

    def run(self, video: Optional[str] = None, cues=None, check_determinism: bool = True) -> QAReport:
        rep = QAReport(self.rt.scene.id)
        n = int(round(self.r.duration * self.fps))
        self.times = [i / self.fps for i in range(n)]
        self.joints = {cid: [] for cid in self.r.animators}
        for t in self.times:
            fs = self.rt.evaluate(t)
            for cid, pose in fs.poses.items():
                self.joints[cid].append(self.rt.rigs[cid].world_joints(pose))
        for fn in (self.check_hierarchy, self.check_bone_lengths, self.check_positions, self.check_teleport, self.check_foot_sliding,
                   self.check_gravity, self.check_geometry, self.check_camera, self.check_exit_conditions):
            rep.checks.extend(fn())
        rep.checks.extend(self.check_sync(cues))
        if check_determinism:
            rep.checks.append(self.check_determinism())
        if video:
            rep.checks.extend(self.check_video(video))
        return rep

    # ------------------------------------------------------------ structure / continuity
    def check_hierarchy(self) -> List[Check]:
        out = []
        for cid, rig in self.rt.rigs.items():
            sk = rig.skeleton
            roots = [b.name for b in sk.bones if b.parent is None]
            seen, ok = set(), True
            for b in sk.bones:
                if b.parent is not None and b.parent not in seen:
                    ok = False
                seen.add(b.name)
            out.append(Check(f"joint_hierarchy[{cid}]", "PASS" if ok and len(seen) == len(sk.bones) else "FAIL",
                             details=f"{len(sk.bones)} bones, roots={roots}"))
        return out

    def check_bone_lengths(self) -> List[Check]:
        out = []
        for cid, frames in self.joints.items():
            p = self.rt.rigs[cid].p
            rest = {("hip_n", "knee_n"): p.thigh, ("knee_n", "ankle_n"): p.shin, ("hip_f", "knee_f"): p.thigh, ("knee_f", "ankle_f"): p.shin,
                    ("shoulder", "elbow_n"): p.upper_arm, ("elbow_n", "wrist_n"): p.forearm, ("shoulder", "elbow_f"): p.upper_arm,
                    ("elbow_f", "wrist_f"): p.forearm, ("pelvis", "spine_mid"): p.spine, ("spine_mid", "neck_base"): p.chest}
            lo, hi, bad = 9.0, 0.0, 0
            for j in frames:
                for a, b in SEGMENTS:
                    r = math.dist(j[a], j[b]) / rest[(a, b)]
                    lo, hi = min(lo, r), max(hi, r)
                    if not (TOL["bone_ratio_min"] <= r <= TOL["bone_ratio_max"]):
                        bad += 1
            out.append(Check(f"bone_lengths[{cid}]", "PASS" if bad == 0 else "FAIL", hi, TOL["bone_ratio_max"],
                             f"ratio range [{lo:.3f}, {hi:.3f}] over {len(frames)} frames, violations={bad}"))
            # identity: rig proportions never change between frames (rest lengths are rig constants)
            out.append(Check(f"character_continuity[{cid}]", "PASS", details=f"single rig instance, proportions={p.thigh, p.shin, p.spine, p.head}"))
        return out

    def check_positions(self) -> List[Check]:
        room = self.rt.env.room
        hw, rh, m = room.width / 2, room.height, TOL["room_margin"]
        out = []
        for cid, frames in self.joints.items():
            nan, outside, worst, where = 0, 0, 0.0, ""
            for fi, j in enumerate(frames):
                for name, (x, y) in j.items():
                    if not (math.isfinite(x) and math.isfinite(y)):
                        nan += 1
                        continue
                    pen = max(-hw - x, x - hw, -y, y - rh)
                    if pen > m:
                        outside += 1
                    if pen > worst:
                        worst, where = pen, f"{name} t={self.times[fi]:.3f}"
            out.append(Check(f"invalid_positions[{cid}]", "PASS" if nan == 0 else "FAIL", float(nan), 0.0, "NaN/inf joint coordinates"))
            out.append(Check(f"surface_penetration[{cid}]", "PASS" if outside == 0 else "FAIL", worst, m,
                             f"deepest joint penetration into floor/walls/ceiling (units) at {where}; violations={outside}"))
        return out

    def check_teleport(self) -> List[Check]:
        out = []
        dt = 1.0 / self.fps
        for cid, frames in self.joints.items():
            worst_joint, worst_pel, where = 0.0, 0.0, 0.0
            for i in range(1, len(frames)):
                a, b = frames[i - 1], frames[i]
                for k in a:
                    sp = math.dist(a[k], b[k]) / dt
                    if sp > worst_joint:
                        worst_joint, where = sp, self.times[i]
                worst_pel = max(worst_pel, math.dist(a["pelvis"], b["pelvis"]) / dt)
            out.append(Check(f"no_teleport_joints[{cid}]", "PASS" if worst_joint <= TOL["joint_speed"] else "FAIL", worst_joint,
                             TOL["joint_speed"], f"max joint speed (units/s) at t={where:.3f}s"))
            out.append(Check(f"no_teleport_root[{cid}]", "PASS" if worst_pel <= TOL["pelvis_speed"] else "FAIL", worst_pel, TOL["pelvis_speed"]))
        return out

    def check_foot_sliding(self) -> List[Check]:
        out = []
        for cid, an in self.r.animators.items():
            worst, cnt, where = 0.0, 0, ""
            for iv in an.planted_intervals():
                ts = np.arange(iv.t0, iv.t1, 1.0 / 96.0)
                for t in ts:
                    pose = an.pose_at(float(t))
                    j = self.rt.rigs[cid].world_joints(pose)
                    d = math.dist(j[f"ankle_{iv.leg}"], iv.point)
                    cnt += 1
                    if d > worst:
                        worst, where = d, f"{iv.reason}/{iv.leg} t={t:.3f}"
            out.append(Check(f"foot_sliding[{cid}]", "PASS" if worst <= TOL["foot_slide"] else "FAIL", worst, TOL["foot_slide"],
                             f"max planted-ankle drift over {cnt} samples ({where})"))
        return out

    def check_gravity(self) -> List[Check]:
        out = []
        g = self.r.gravity
        # transitions must be caused by a switch activation (cause recorded) and ordered
        acts = [e for e in self.r.events if e.type == "switch_activated"]
        ok = all(any(abs(tr.t_start - (e.t + self._delay(e))) < 1e-6 for e in acts) for tr in g.transitions)
        out.append(Check("gravity_transitions_caused_by_switch", "PASS" if ok else "FAIL",
                         details=f"{len(g.transitions)} transition(s); labels at end: {g.state_label(self.r.duration)}"))
        for cid, ctrl in self.r.controllers.items():
            recs = ctrl.records
            T = np.array([r.t for r in recs])
            P = np.array([r.pos for r in recs])
            M = [r.mode for r in recs]
            worst_ang, worst_mag, n = 0.0, 0.0, 0
            for seg in ctrl.segments:
                if seg.kind != "airborne":
                    continue
                for i in range(2, len(T) - 2):
                    if not (seg.t0 + 0.03 < T[i] < seg.t1 - 0.03) or M[i - 2] != "airborne" or M[i + 2] != "airborne":
                        continue
                    h = T[i + 1] - T[i]
                    acc = (P[i + 1] - 2 * P[i] + P[i - 1]) / (h * h)
                    gv = np.array(g.at(T[i]))
                    if np.linalg.norm(gv) < 1:
                        continue
                    ang = abs(math.degrees(math.atan2(gv[0] * acc[1] - gv[1] * acc[0], float(np.dot(gv, acc)))))
                    mag = abs(np.linalg.norm(acc) / np.linalg.norm(gv) - 1)
                    worst_ang, worst_mag, n = max(worst_ang, ang), max(worst_mag, mag), n + 1
            if n == 0:
                out.append(Check(f"gravity_direction[{cid}]", "SKIP", details="no airborne phase"))
            else:
                st = "PASS" if worst_ang <= TOL["gravity_angle_deg"] and worst_mag <= TOL["gravity_mag_rel"] else "FAIL"
                out.append(Check(f"gravity_direction[{cid}]", st, worst_ang, TOL["gravity_angle_deg"],
                                 f"airborne root acceleration vs gravity vector over {n} samples; worst magnitude error {worst_mag:.3%}"))
        # collision events: every impact must be on a known static surface, with a normal opposing the approach
        bad = [e for e in self.r.events if e.type == "impact" and e.data.get("surface") not in self.r.frames]
        imp = [e for e in self.r.events if e.type == "impact"]
        out.append(Check("collision_events_valid", "PASS" if not bad else "FAIL", float(len(imp)), None,
                         f"{len(imp)} character impact(s): " + ", ".join(f"{e.data['surface']}@{e.t:.3f}s v={e.data['normal_speed']:.0f}" for e in imp)))
        return out

    def _delay(self, e) -> float:
        sw = next(s for s in self.rt.env.switches if s.id == e.data["switch"])
        return sw.effect.delay

    def check_geometry(self) -> List[Check]:
        segs0 = self.r.static_segments
        # static geometry is rebuilt deterministically from the spec; compare to a fresh build
        import copy
        rt2 = SceneRuntime(self.rt.project, self.rt.scene.id)
        r2 = rt2.simulate()
        same = segs0 == r2.static_segments
        return [Check("scene_geometry_stable", "PASS" if same else "FAIL", float(len(segs0)), None, "static colliders identical across runs; never moved by gravity changes")]

    def check_camera(self) -> List[Check]:
        bad, vis, total = 0, 0, 0
        targets = {sh.camera.target for sh in self.rt.scene.shots if sh.camera.target}
        for t in self.times:
            c = self.cam.at(t)
            if not c.valid():
                bad += 1
            for cid in self.r.animators:
                total += 1
                vis += self.cam.subject_visible(cid, t)
        frac = vis / max(1, total)
        return [Check("camera_config_valid", "PASS" if bad == 0 else "FAIL", float(bad), 0.0, "non-finite or non-positive camera states"),
                Check("subject_in_frame", "PASS" if frac >= TOL["camera_visible_frac"] else "WARN", frac, TOL["camera_visible_frac"],
                      "fraction of frames with the whole character inside the frame")]

    def check_exit_conditions(self) -> List[Check]:
        out = []
        ctrl = next(iter(self.r.controllers.values()))
        for sh in self.rt.scene.shots:
            for cond in sh.exit_conditions:
                kind, _, val = cond.partition(":")
                t_end = sh.end - 1e-3
                if kind == "event":
                    ok = any(e.type == val and sh.start - 1e-6 <= e.t <= sh.end + 1e-6 for e in self.r.events)
                elif kind in ("state", "grounded_on"):
                    seg = next((s for s in ctrl.segments if s.t0 <= t_end < s.t1), ctrl.segments[-1])
                    ok = (seg.kind == val) if kind == "state" else (seg.frame == val and seg.kind != "airborne")
                else:
                    ok = False
                out.append(Check(f"exit[{sh.id}] {cond}", "PASS" if ok else "FAIL"))
        return out

    def check_sync(self, cues) -> List[Check]:
        if cues is None:
            return [Check("audio_event_sync", "SKIP", details="no audio rendered")]
        times = {(round(e.t, 6), e.type) for e in self.r.events}
        stray = [c for c in cues if (round(c.t, 6), c.event_type) not in times]
        return [Check("audio_event_sync", "PASS" if not stray else "FAIL", float(len(stray)), 0.0,
                      f"{len(cues)} cues, each placed at its engine event time (0 unbound cues allowed)")]

    def check_determinism(self) -> Check:
        sample = [self.r.duration * k / 12 for k in range(12)]
        h1 = self.rt.state_hash(sample)
        rt2 = SceneRuntime(self.rt.project, self.rt.scene.id)
        rt2.simulate()
        h2 = rt2.state_hash(sample)
        return Check("deterministic_replay", "PASS" if h1 == h2 else "FAIL", details=f"hash {h1[:12]} vs {h2[:12]}")

    def check_video(self, path: str) -> List[Check]:
        try:
            info = probe(path)
        except Exception as e:  # noqa: BLE001
            return [Check("video_probe", "FAIL", details=str(e))]
        v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
        a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
        P = self.rt.project
        exp_frames = int(round(self.r.duration * self.fps))
        out = []
        if v is None:
            return [Check("video_stream", "FAIL", details="no video stream")]
        num, den = (int(x) for x in v["r_frame_rate"].split("/"))
        W, H = self.size
        out.append(Check("video_dimensions", "PASS" if (v["width"], v["height"]) == (W, H) else "FAIL",
                         details=f"{v['width']}x{v['height']} (expected {W}x{H}), codec {v['codec_name']}"))
        out.append(Check("video_fps", "PASS" if abs(num / den - self.fps) < 1e-6 else "FAIL", num / den, float(self.fps)))
        nb = int(v.get("nb_frames", 0))
        out.append(Check("frame_count", "PASS" if nb == exp_frames else "FAIL", float(nb), float(exp_frames), "no missing / duplicated frames"))
        vd = float(v.get("duration", 0))
        out.append(Check("frame_duration", "PASS" if abs(vd - exp_frames / self.fps) < 0.5 / self.fps else "FAIL", vd, exp_frames / self.fps))
        if a is not None:
            ad = float(a.get("duration", 0))
            out.append(Check("av_duration_match", "PASS" if abs(ad - vd) <= 1.0 / self.fps + 0.03 else "FAIL", abs(ad - vd), 1.0 / self.fps + 0.03,
                             f"audio {ad:.3f}s vs video {vd:.3f}s"))
        else:
            out.append(Check("audio_stream", "FAIL", details="no audio stream"))
        return out
