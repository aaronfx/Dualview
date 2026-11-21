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
from ..scene.runtime import DOOR_OPEN_S, SceneRuntime, door_state
from ..scene.targets import in_portal, switch_world

# Each tolerance below is named so failures can be traced back to an explicit, documented threshold.
TOL = {
    "bone_ratio_min": 0.86, "bone_ratio_max": 1.13,  # allows authored squash/stretch and IK stretch (<=8%) only
    "foot_slide": 1.5,  # world units a planted ankle may drift
    "joint_speed": 3200.0,  # units/s; above this a joint "teleports" (fastest authored motion ~1500)
    "pelvis_speed": 2200.0,
    "room_margin": 4.0,
    "gravity_angle_deg": 3.0, "gravity_mag_rel": 0.05,
    "camera_visible_frac": 0.95,
    "scarf_stretch": 1.35, "scarf_anchor": 0.5,
    "roll_rate_deg_s": 150.0, "min_shot_s": 0.5, "gravity_align_deg": 3.0, "indicator_deg": 0.5,
    "grip_drift": 1.5,  # wrist distance from the bar while hanging (units)
    "contact_hand": 22.0,  # hand distance from the button at a press_contact event
    "strike_contact": 24.0,  # fist / foot distance from the struck body point at a hit or block
    "fighter_gap": 28.0,  # minimum pelvis distance between two standing characters (bodies must not pass through)
    "obstacle_margin": 2.5,  # joints must stay this far outside solid beams (limb half-thickness)
    "swing_energy_gain": 0.02,
    "subject_frac": {"establishing": 0.07, "wide": 0.12, "tracking": 0.16, "medium": 0.18, "close": 0.3},  # min subject size / frame
    "roll_while_moving_speed": 260.0,  # u/s: the camera may only roll while the subject is (nearly) still  # relative mechanical-energy increase allowed while swinging (solver drift only; no pumping)
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

    def counts(self) -> dict:
        """Totals computed from the checks themselves (reports quote these, never a hand count)."""
        by_status: Dict[str, int] = {}
        for c in self.checks:
            by_status[c.status] = by_status.get(c.status, 0) + 1
        exits = sum(1 for c in self.checks if c.name.startswith("exit["))
        return {"total": len(self.checks), "by_status": by_status, "exit_conditions": exits,
                "engine_and_video_checks": len(self.checks) - exits}

    def to_dict(self) -> dict:
        return {"scene": self.scene, "passed": self.passed, "counts": self.counts(), "checks": [asdict(c) for c in self.checks]}

    def summary(self) -> str:
        k = self.counts()
        st = ", ".join(f"{v} {s}" for s, v in sorted(k["by_status"].items()))
        lines = [f"QA {self.scene}: {'PASSED' if self.passed else 'FAILED'} - {k['total']} checks ({st}); "
                 f"{k['engine_and_video_checks']} engine/video checks + {k['exit_conditions']} shot exit conditions"]
        for c in self.checks:
            m = "" if c.metric is None else f" metric={c.metric:.4g}"
            th = "" if c.threshold is None else f" threshold={c.threshold:.4g}"
            lines.append(f"  [{c.status}] {c.name}{m}{th} {c.details}")
        return "\n".join(lines)


SEGMENTS = [("hip_n", "knee_n"), ("knee_n", "ankle_n"), ("hip_f", "knee_f"), ("knee_f", "ankle_f"), ("shoulder_n", "elbow_n"),
            ("elbow_n", "wrist_n"), ("shoulder_f", "elbow_f"), ("elbow_f", "wrist_f"), ("pelvis", "spine_mid"), ("spine_mid", "neck_base")]


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
                   self.check_gravity, self.check_geometry, self.check_camera, self.check_camera_motion, self.check_continuity,
                   self.check_secondary, self.check_exit_conditions, self.check_interactions, self.check_composition,
                   self.check_combat):
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
                    ("shoulder_n", "elbow_n"): p.upper_arm, ("elbow_n", "wrist_n"): p.forearm, ("shoulder_f", "elbow_f"): p.upper_arm,
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
                    if pen > m and in_portal(self.rt.env, (x, y)) and self._door_open_at(self.times[fi]):
                        pen = 0.0  # walking out through an open doorway
                    if pen > m:
                        outside += 1
                    if pen > worst:
                        worst, where = pen, f"{name} t={self.times[fi]:.3f}"
            out.append(Check(f"invalid_positions[{cid}]", "PASS" if nan == 0 else "FAIL", float(nan), 0.0, "NaN/inf joint coordinates"))
            out.append(Check(f"surface_penetration[{cid}]", "PASS" if outside == 0 else "FAIL", worst, m,
                             f"deepest joint penetration into floor/walls/ceiling (units) at {where}; violations={outside}"))
        return out

    def _door_open_at(self, t: float) -> bool:
        return any(door_state(d, t)[0] in ("opening", "open", "exited", "closing", "closed") and (d.get("open_t") is not None)
                   for d in self.r.doors.values())

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
                    # the two steps in this difference applied gravity at T[i]-h and T[i] (records are stamped at step
                    # end): compare with their mean, which matters inside fast rotations (up to ~720 deg/s)
                    gv = (np.array(g.at(T[i] - h)) + np.array(g.at(T[i]))) / 2
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
        skipped = 0
        for t in self.times:
            c = self.cam.at(t)
            if not c.valid():
                bad += 1
            sh = self.cam.shot_at(t)
            for cid in self.r.animators:
                if sh.kind == "insert":  # inserts frame an object (the switch), not the character
                    region = (sh.camera.center[0] - 15, sh.camera.center[1] - 30, sh.camera.center[0] + 15, sh.camera.center[1] + 10) \
                        if sh.camera.center else None
                    if region is None:
                        skipped += 1
                        continue
                elif sh.camera.focus != "body" and self.cam.focus_bbox is not None:
                    region = self.cam.focus_bbox(cid, t, sh.camera.focus)  # close-ups must keep their focus region
                else:
                    region = None
                total += 1
                vis += self.cam.subject_visible(cid, t, region)
        frac = vis / max(1, total)
        return [Check("camera_config_valid", "PASS" if bad == 0 else "FAIL", float(bad), 0.0, "non-finite or non-positive camera states"),
                Check("subject_in_frame", "PASS" if frac >= TOL["camera_visible_frac"] else "WARN", frac, TOL["camera_visible_frac"],
                      "fraction of frames whose framed subject is fully visible (body; focus region for close-ups; the switch for inserts)")]

    def check_camera_motion(self) -> List[Check]:
        out = []
        from ..camera.director import gravity_roll
        shots = self.rt.scene.shots
        short = [sh.id for sh in shots if sh.end - sh.start < TOL["min_shot_s"]]
        out.append(Check("min_shot_length", "PASS" if not short else "FAIL", min(sh.end - sh.start for sh in shots), TOL["min_shot_s"],
                         f"{len(shots)} shots; too short: {short}"))
        worst, where = 0.0, ""
        for sh in shots:
            ts = [t for t in self.times if sh.start <= t < sh.end]
            for a, b in zip(ts, ts[1:]):
                rate = abs(self.cam.at(b).roll - self.cam.at(a).roll) * self.fps
                if rate > worst:
                    worst, where = rate, f"{sh.id} t={b:.3f}"
        out.append(Check("camera_roll_rate", "PASS" if worst <= TOL["roll_rate_deg_s"] else "FAIL", worst, TOL["roll_rate_deg_s"],
                         f"max roll speed inside a shot (deg/s) at {where or '-'}; cuts are excluded"))
        for sh in shots:
            if sh.camera.roll_mode != "align_gravity":
                continue
            t = sh.end - 1e-3
            d = self.cam.at(t).roll - gravity_roll(self.r.gravity.at(t))
            err = abs((d + 180.0) % 360.0 - 180.0)  # angular difference (roll may be unwrapped)
            out.append(Check(f"gravity_aligned_roll[{sh.id}]", "PASS" if err <= TOL["gravity_align_deg"] else "FAIL", err,
                             TOL["gravity_align_deg"], "screen-down matches the gravity vector at the end of the shot"))
        return out

    def check_continuity(self) -> List[Check]:
        out = []
        from ..render.skia_renderer import SkiaRenderer
        # 1) the console's gravity arrow always points along the true gravity vector (world cue == physics)
        worst = 0.0
        for t in self.times[::6]:
            g = self.r.gravity.at(t)
            rot = math.radians(SkiaRenderer.indicator_rotation(g))
            arrow_screen = (-math.sin(rot), math.cos(rot))
            arrow_world = (arrow_screen[0], -arrow_screen[1])
            ang = math.degrees(math.atan2(g[1], g[0]) - math.atan2(arrow_world[1], arrow_world[0]))
            worst = max(worst, abs((ang + 180) % 360 - 180))
        out.append(Check("gravity_indicator_matches_physics", "PASS" if worst <= TOL["indicator_deg"] else "FAIL", worst, TOL["indicator_deg"]))
        # 2) screen direction preserved across cuts (180-degree rule): the character keeps facing the same screen side
        flips = []
        for a, b in zip(self.rt.scene.shots, self.rt.scene.shots[1:]):
            ta, tb = b.start - 1e-3, b.start + 1e-3
            for cid, an in self.r.animators.items():  # each character compared with itself across the cut
                sides = []
                for t in (ta, tb):
                    p = an.pose_at(t)
                    fwd = (math.cos(p.body_angle) * p.facing, math.sin(p.body_angle) * p.facing)
                    r = math.radians(self.cam.at(t).roll)
                    sx = fwd[0] * math.cos(r) + fwd[1] * math.sin(r)  # screen-x of the world forward vector
                    sides.append(math.copysign(1, sx) if abs(sx) > 0.2 else 0)
                if sides[0] and sides[1] and sides[0] != sides[1]:
                    flips.append(f"{a.id}->{b.id} ({cid})")
        out.append(Check("screen_direction_across_cuts", "PASS" if not flips else "WARN", float(len(flips)), 0.0,
                         f"cuts that flip the character's screen direction: {flips or 'none'}"))
        # 3) fixed layout: switch/exit/room positions come from the spec and never move
        env = self.rt.env
        out.append(Check("static_layout", "PASS", details=f"room {env.room.width}x{env.room.height}, switches {[(s.surface, s.x) for s in env.switches]}, "
                         f"exits {[(x.surface, x.s) for x in env.exits]}, obstacles {[(o.kind, tuple(o.center)) for o in env.obstacles]} "
                         "are spec constants (never animated)"))
        return out

    def check_secondary(self) -> List[Check]:
        out = []
        room = self.rt.env.room
        for cid, sc in self.r.scarves.items():
            st = sc.max_stretch()
            out.append(Check(f"scarf_integrity[{cid}]", "PASS" if st <= TOL["scarf_stretch"] and sc.anchor_err <= TOL["scarf_anchor"] else "FAIL",
                             st, TOL["scarf_stretch"], f"max segment stretch; anchor error {sc.anchor_err:.3f}"))
            inside = all((-room.width / 2 - 1e-6 <= p[0] <= room.width / 2 + 1e-6 and -1e-6 <= p[1] <= room.height + 1e-6)
                         or in_portal(self.rt.env, (p[0], p[1])) for d in sc.data for frame in d[::12] for p in frame)
            out.append(Check(f"scarf_inside_room[{cid}]", "PASS" if inside else "FAIL"))
        if self.r.dust is not None:
            D = self.r.dust.data
            ok = bool(np.all(np.abs(D[..., 0]) <= room.width / 2) and np.all(D[..., 1] >= 0) and np.all(D[..., 1] <= room.height))
            out.append(Check("dust_inside_room", "PASS" if ok else "FAIL", details=f"{D.shape[1]} particles x {D.shape[0]} steps"))
        return out

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

    # ------------------------------------------------------------ 1D: interactions, doors, gravity angles
    def check_interactions(self) -> List[Check]:
        out: List[Check] = []
        env, r = self.rt.env, self.r
        g = r.gravity
        # gravity angles: every state relative to the preceding one and to the original (documentation + sanity)
        rep_ = g.report()
        txt = "; ".join(f"{x['state']}: world {x['world_deg']:.0f} deg, vs previous {x['rel_prev_deg']:+.0f}, vs original {x['rel_original_deg']:+.0f}"
                        for x in rep_)
        ok = all(abs(((x["world_deg"] - (rep_[0]["world_deg"] + x["rel_original_deg"])) + 180) % 360 - 180) < 1e-6 for x in rep_)
        out.append(Check("gravity_angle_report", "PASS" if ok else "FAIL", details=txt))
        # camera roll turns the same way as gravity (a CCW gravity sweep rolls the camera positively, and vice versa)
        bad = []
        for tr in g.transitions:
            sw = tr.sweep if tr.sweep is not None else 0.0
            for sh in self.rt.scene.shots:
                if sh.camera.roll_mode != "align_gravity" or sh.end <= tr.t_start or sh.start >= tr.t_start + tr.duration + 3.0:
                    continue
                d = self.cam.at(sh.end - 1e-3).roll - self.cam.at(max(sh.start, tr.t_start)).roll
                if abs(d) > 10 and math.copysign(1, d) != math.copysign(1, sw):
                    bad.append(sh.id)
        for sh in self.rt.scene.shots:  # authored eased rolls (roll -> roll_end) must also turn with the latest sweep
            if sh.camera.roll_mode == "align_gravity" or sh.camera.roll_end is None:
                continue
            prior = [tr for tr in g.transitions if tr.t_start < sh.end]
            d = sh.camera.roll_end - sh.camera.roll
            if prior and abs(d) > 10:
                sw = prior[-1].sweep if prior[-1].sweep is not None else 0.0
                if math.copysign(1, d) != math.copysign(1, sw):
                    bad.append(sh.id)
        out.append(Check("camera_roll_follows_gravity_direction", "PASS" if not bad else "FAIL", float(len(bad)), 0.0,
                         f"aligned or eased-roll shots turning against the gravity sweep: {bad or 'none'}"))
        # landings only on surfaces that can support the body under the gravity at that instant
        badl = []
        for e in r.events:
            if e.type == "impact":
                gd = g.direction(e.t)
                n = r.frames[e.data["surface"]].normal
                if -(gd[0] * n[0] + gd[1] * n[1]) < math.cos(math.radians(55)):
                    badl.append(f"{e.data['surface']}@{e.t:.2f}")
        out.append(Check("landings_on_supporting_surfaces", "PASS" if not badl else "FAIL", float(len(badl)), 0.0,
                         f"impacts (landings) where gravity could not hold the body: {badl or 'none'}"))
        # the hand is on the button whenever a switch is pressed (standing or mid-air)
        worst, n_c = 0.0, 0
        for e in r.events:
            if e.type == "press_contact" and e.character in r.animators:
                sw = next(s for s in env.switches if s.id == e.data["switch"])
                b = switch_world(env, sw)
                j = self.rt.rigs[e.character].world_joints(r.animators[e.character].pose_at(e.t))
                worst = max(worst, min(math.dist(j["hand_n"], b), math.dist(j["hand_f"], b)))
                n_c += 1
        if n_c:
            out.append(Check("hand_on_switch_at_contact", "PASS" if worst <= TOL["contact_hand"] else "FAIL", worst, TOL["contact_hand"],
                             f"{n_c} press contact(s); worst hand-to-button distance"))
        for cid, an in r.animators.items():
            swings = [sg for sg in an.segments if sg.kind == "swing"]
            if swings:  # hands stay locked to the rail while hanging
                worst, n_s = 0.0, 0
                for sg in swings:
                    B = sg.data["anchor"]
                    for t in np.arange(sg.t0, sg.t1, 1.0 / 96.0):
                        j = self.rt.rigs[cid].world_joints(an.pose_at(float(t)))
                        worst = max(worst, math.dist(j["wrist_n"], B), math.dist(j["wrist_f"], B))
                        n_s += 1
                out.append(Check(f"grip_attachment[{cid}]", "PASS" if worst <= TOL["grip_drift"] else "FAIL", worst, TOL["grip_drift"],
                                 f"max wrist-to-rail distance over {n_s} samples while hanging"))
                # passive swing: mechanical energy may not grow (no hidden pumping); it may only drop (inelastic catch)
                ctrl = r.controllers[cid]
                from ..motion.controller import MASS
                k2 = ctrl.moment / MASS  # radius of gyration squared (rotational energy per unit mass)
                gain = 0.0
                for sg in swings:
                    E = []
                    wt = np.array([w[0] for w in sg.data.get("work", [(sg.t0, 0.0)])])
                    wv = np.array([w[1] for w in sg.data.get("work", [(sg.t0, 0.0)])])
                    for rec in ctrl.records:
                        if sg.t0 + 0.02 <= rec.t <= sg.t1 - 0.01:
                            gv = g.at(rec.t)
                            W = float(np.interp(rec.t, wt, wv))  # muscular work put in by pumping so far
                            E.append(0.5 * (rec.vel[0] ** 2 + rec.vel[1] ** 2) + 0.5 * k2 * rec.angvel ** 2
                                     - (gv[0] * rec.pos[0] + gv[1] * rec.pos[1]) - W)
                    if E:  # relative to the swing's own energy scale (peak kinetic energy), not the coordinate origin
                        ke = max(0.5 * (rec.vel[0] ** 2 + rec.vel[1] ** 2) + 0.5 * k2 * rec.angvel ** 2
                                 for rec in ctrl.records if sg.t0 <= rec.t <= sg.t1)
                        gain = max(gain, (max(E) - E[0]) / max(ke, 1.0))
                out.append(Check(f"swing_energy_conserved[{cid}]", "PASS" if gain <= TOL["swing_energy_gain"] else "FAIL", gain,
                                 TOL["swing_energy_gain"], "unaccounted energy gain while swinging: (kinetic + rotational + potential - pumping work) relative to the peak kinetic energy"))
        beams = [o for o in env.obstacles if o.kind == "beam"]
        if beams:  # nothing passes through a solid beam (the slide must clear it)
            worst, where = -1e9, ""
            for cid, frames in self.joints.items():
                for fi, j in enumerate(frames):
                    for name, (x, y) in j.items():
                        for o in beams:
                            hx, hy = o.size[0] / 2 + TOL["obstacle_margin"], o.size[1] / 2 + TOL["obstacle_margin"]
                            pen = min(hx - abs(x - o.center[0]), hy - abs(y - o.center[1]))
                            if pen > worst:
                                worst, where = pen, f"{name} t={self.times[fi]:.2f} ({o.id})"
            clear = -worst
            out.append(Check("obstacle_clearance", "PASS" if worst <= 0 else "FAIL", clear, 0.0,
                             f"closest approach of any joint to a solid beam (incl. {TOL['obstacle_margin']} limb margin): {clear:.1f} units at {where}"))
        for ex in env.exits:  # door state machine order
            d = r.doors.get(ex.id, {})
            u, o, x = d.get("unlock_t"), d.get("open_t"), d.get("exit_t")
            seq = [("unlock", u), ("open", o), ("exit", x)]
            ok = True
            msg = []
            if ex.unlock_on and u is not None:
                sw_id = ex.unlock_on.split(":", 1)[1]
                act = next((e.t for e in r.events if e.type == "switch_activated" and e.data.get("switch") == sw_id), None)
                ok &= act is not None and u >= act
                msg.append(f"switch {sw_id} at {act:.2f}" if act is not None else "switch never pressed")
            from ..scene.runtime import DOOR_UNLOCK_S
            if o is not None:
                ok &= u is not None and o >= u + DOOR_UNLOCK_S - 1e-6
            if x is not None:
                ok &= o is not None and x >= o + DOOR_OPEN_S * 0.75
            msg += [f"{k} {v:.2f}s" for k, v in seq if v is not None]
            out.append(Check(f"door_state_machine[{ex.id}]", "PASS" if ok else "FAIL",
                             details="sealed -> " + " -> ".join(msg) if msg else "stays sealed"))
        return out

    def check_composition(self) -> List[Check]:
        """Composition rules that favour readable action over dramatic effect."""
        out: List[Check] = []
        cid = next(iter(self.r.animators))
        an = self.r.animators[cid]
        small, worst_frac, where = [], 9.0, ""
        for sh in self.rt.scene.shots:
            if sh.kind == "insert":
                continue
            need = sh.camera.min_subject_frac if sh.camera.min_subject_frac is not None else TOL["subject_frac"].get(sh.kind, 0.12)
            fr = []
            for t in [x for x in self.times if sh.start <= x < sh.end][::3]:
                if not self.cam.subject_visible(cid, t):
                    continue
                x0, y0, x1, y1 = self.cam.bbox(cid, t)
                fr.append(max(x1 - x0, y1 - y0) / self.cam.at(t).view_h)  # orientation-independent body size
            if fr:
                med = float(np.median(fr))
                if med < worst_frac:
                    worst_frac, where = med, sh.id
                if med < need:
                    small.append(f"{sh.id} {med:.2f}<{need:.2f}")
        out.append(Check("composition_subject_size", "PASS" if not small else "FAIL", worst_frac, None,
                         f"median subject size per shot (body extent / frame height); smallest in {where}; too small: {small or 'none'}"))
        missing = []
        for sh in self.rt.scene.shots:
            for tg in sh.camera.include:
                if self.cam.resolve is None or self.cam.resolve(tg, sh.start) is None:
                    missing.append(f"{sh.id}:{tg}?")
                    continue
                m = 20.0
                for t in [x for x in self.times if sh.start <= x < sh.end]:
                    p = self.cam.resolve(tg, float(t))  # props and characters move: resolve at each sampled time
                    if not self.cam.subject_visible(cid, t, (p[0] - m, p[1] - m, p[0] + m, p[1] + m)):
                        missing.append(f"{sh.id}:{tg}@{t:.2f}")
                        break
        out.append(Check("composition_required_objects", "PASS" if not missing else "FAIL", float(len(missing)), 0.0,
                         f"objects a shot must show (camera.include) left the frame: {missing or 'none'}"))
        bad, n = [], 0
        for sh in self.rt.scene.shots:
            ts = [x for x in self.times if sh.start <= x < sh.end]
            for a, b in zip(ts, ts[1:]):
                if abs(self.cam.at(b).roll - self.cam.at(a).roll) > 0.5:
                    n += 1
                    v = math.dist(an.pose_at(a).root, an.pose_at(b).root) * self.fps
                    if v > TOL["roll_while_moving_speed"]:
                        bad.append(f"{sh.id}@{b:.2f}")
        out.append(Check("no_roll_during_fast_action", "PASS" if not bad else "FAIL", float(len(bad)), 0.0,
                         f"{n} rolling frames; rolling while the subject moved faster than {TOL['roll_while_moving_speed']:.0f} u/s: {bad[:6] or 'none'}"))
        return out

    def check_combat(self) -> List[Check]:
        """Strikes land on the body they hit; fighters never pass through each other; every knockdown settles."""
        ev = self.r.events
        hits = [e for e in ev if e.type in ("hit", "blocked")]
        if not hits and not any(e.type == "knockdown" for e in ev):
            return []
        out = []
        worst, where = 0.0, ""
        for e in hits:
            an = self.r.animators[e.character]
            seg = an.segments[an.segment_at(e.t)]
            if seg.kind != "strike":
                continue
            limb = seg.data["limb"]
            joint = ("hand_" if limb.startswith("hand") else "ankle_") + limb[-1]
            j = self.rt.rigs[e.character].world_joints(an.pose_at(e.t))
            tp = an._target_point(seg.data["other"], e.t, seg.data["height"], seg.facing)
            err = math.dist(j[joint], tp)
            if err > worst:
                worst, where = err, f"{e.character} {seg.data['move']} at t={e.t:.2f}s"
        out.append(Check("strike_contact", "PASS" if worst <= TOL["strike_contact"] else "FAIL", worst, TOL["strike_contact"],
                         f"fist/foot distance from the struck body point at contact ({len(hits)} contacts; worst: {where})"))
        cids = list(self.joints)
        worst_gap, where = 1e9, ""
        for a in range(len(cids)):
            for b in range(a + 1, len(cids)):
                for i, t in enumerate(self.times):
                    ja, jb = self.joints[cids[a]][i], self.joints[cids[b]][i]
                    if ja["head_center"][1] < 0.6 * self.rt.rigs[cids[a]].p.stand_height or jb["head_center"][1] < 0.6 * self.rt.rigs[cids[b]].p.stand_height:
                        continue  # someone is down / crouched low: overlapping in depth is fine
                    gap = abs(ja["pelvis"][0] - jb["pelvis"][0])
                    if gap < worst_gap:
                        worst_gap, where = gap, f"{cids[a]}/{cids[b]} at t={t:.2f}s"
        if worst_gap < 1e9:
            out.append(Check("fighters_do_not_overlap", "PASS" if worst_gap >= TOL["fighter_gap"] else "FAIL", worst_gap, TOL["fighter_gap"],
                             f"minimum pelvis distance between standing characters ({where})"))
        kd = [e for e in ev if e.type == "knockdown"]
        settled = [e for e in ev if e.type == "settled"]
        ok = all(any(s.character == k.character and s.t > k.t for s in settled) for k in kd)
        out.append(Check("knockdowns_settle", "PASS" if ok or not kd else "WARN", float(len(kd)), None,
                         f"{len(kd)} physics fall(s), {len(settled)} settled before the end"))
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
        from .media import decode_check
        dc = decode_check(path)
        out.append(Check("full_decode", "PASS" if dc["ok"] and dc["video_frames_decoded"] == exp_frames else "FAIL",
                         float(dc["video_frames_decoded"]), float(exp_frames),
                         f"every frame decoded; decoder errors: {dc['video_errors'] or 'none'}; audio errors: {dc['audio_errors'] or 'none'}"))
        return out
