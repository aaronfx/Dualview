"""Animation Quality Inspector: numerical / structural checks over a simulated + rendered scene.

Subjective qualities (acting, appeal, comedy) are NOT scored here; previews are produced for human review instead.
"""
from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..camera.director import CameraDirector
from ..render.video import probe
from ..scene.runtime import DOOR_OPEN_S, SceneRuntime, door_state
from ..scene.targets import in_portal, switch_world

# Each tolerance below is named so failures can be traced back to an explicit, documented threshold.
TOL = {
    "body_clearance": 3.0, "held_prop_depth": 3.0, "silhouette_gap": 10.0, "prop_body": 5.0,
    "screen_overlap": 0.15, "screen_overlap_frames": 0.04,
    "structure_depth": 6.0, "top_overhang": 10.0, "flip_land": 0.45, "throw_momentum": 0.25,
    "bone_ratio_min": 0.86, "bone_ratio_max": 1.13,  # allows authored squash/stretch and IK stretch (<=8%) only
    "foot_slide": 1.5,  # world units a planted ankle may drift
    "hand_contact": 10.0,  # units: two hands that hold each other
    "diagram_err": 0.08,  # relative: a number on screen agrees with its independent re-derivation
    "portal_err": 1.0,  # units (or u/s): a portal transfer agrees with its mapping
    "orb_err": 0.03,  # relative: an orb's velocity change agrees with its spec
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
    "carry_reach": 60.0,  # units: a carried prop stays within this of the carrier's nearest hand/pelvis/neck (arms may
                          # extend to swing a held glyph; a prop left behind on a jump/fall is >100u away)
    "float_gap": 26.0,  # units: a posed (kinematic) prop that nobody holds must sit within this of a support below it
    "char_overlap": 0.6,  # fraction: two important characters' screen boxes may overlap at most this much of the smaller
    "char_overlap_frames": 0.12,  # fraction of frames allowed over that overlap before it reads as one shape
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
    # structured diagnostics: when a check fails or warns, exactly why — the worst sample(s) as machine-readable
    # records {t, who, where, state, cause}, so a failure says time, entities, positions, relevant state and a likely
    # root cause rather than only a number. Empty on a clean PASS.
    diag: List[dict] = field(default_factory=list)


# Two acceptance gates. Technical: physics consistency, valid geometry, no unintended clipping, stable replay, correct
# event outcomes, a valid file. Cinematic: readable silhouettes and framing, camera direction, pacing. A film should
# pass both; cinematic checks warn rather than fail, because a person decides what reads well.
CINEMATIC = ("causes_on_screen", "diagrams_in_frame", "subject_in_frame", "silhouettes_readable", "screen_separation", "composition_", "screen_direction_across_cuts",
             "min_shot_length", "no_roll_during_fast_action", "camera_roll_rate", "camera_roll_follows_gravity_direction",
             "characters_not_overlapping", "narrative_", "decisive_events_visible")


def gate_of(name: str) -> str:
    return "cinematic" if name.startswith(CINEMATIC) else "technical"


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
        return {"scene": self.scene, "passed": self.passed, "gates": self.gates(), "counts": self.counts(),
                "checks": [dict(asdict(c), gate=gate_of(c.name)) for c in self.checks]}

    def gates(self) -> Dict[str, str]:
        """technical: PASS unless a technical check failed. cinematic: PASS, WARN (a person should look) or FAIL."""
        tech = [c for c in self.checks if gate_of(c.name) == "technical"]
        cine = [c for c in self.checks if gate_of(c.name) == "cinematic"]
        t = "FAIL" if any(c.status == "FAIL" for c in tech) else "PASS"
        c_ = "FAIL" if any(c.status == "FAIL" for c in cine) else ("WARN" if any(c.status == "WARN" for c in cine) else "PASS")
        return {"technical": t, "cinematic": c_}

    def summary(self) -> str:
        k = self.counts()
        st = ", ".join(f"{v} {s}" for s, v in sorted(k["by_status"].items()))
        g = self.gates()
        lines = [f"QA {self.scene}: {'PASSED' if self.passed else 'FAILED'} - {k['total']} checks ({st}); "
                 f"{k['engine_and_video_checks']} engine/video checks + {k['exit_conditions']} shot exit conditions; "
                 f"gates: technical {g['technical']}, cinematic {g['cinematic']}"]
        for c in self.checks:
            m = "" if c.metric is None else f" metric={c.metric:.4g}"
            th = "" if c.threshold is None else f" threshold={c.threshold:.4g}"
            lines.append(f"  [{c.status}] {c.name}{m}{th} {c.details}")
        return "\n".join(lines)


SEGMENTS = [("hip_n", "knee_n"), ("knee_n", "ankle_n"), ("hip_f", "knee_f"), ("knee_f", "ankle_f"), ("shoulder_n", "elbow_n"),
            ("elbow_n", "wrist_n"), ("shoulder_f", "elbow_f"), ("elbow_f", "wrist_f"), ("pelvis", "spine_mid"), ("spine_mid", "neck_base")]


class Inspector:
    def __init__(self, runtime: SceneRuntime, camera: CameraDirector, fps: int, size: Optional[tuple] = None, warp=None):
        self.rt, self.cam, self.fps = runtime, camera, fps
        self.size = size or (runtime.project.width, runtime.project.height)
        self.r = runtime.result or runtime.simulate()
        self.warp = warp  # film clock vs story clock (Milestone 3); None = the film plays the story 1:1

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
                   self.check_combat, self.check_acrobatics, self._props_through_bodies, self.check_arcade, self.check_particles,
                   self.check_breakables, self.check_morphs, self.check_diagrams, self.check_creatures,
                   self.check_causes_on_screen, self.check_hands_meet,
                   self.check_carried_continuity, self.check_floating_props, self.check_screen_overlap, self.check_narrative):
            rep.checks.extend(fn())
        rep.checks.extend(self.check_time_fx())
        rep.checks.extend(self.check_beats(video))
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
        gone = {}
        for e in self.r.events:  # through an exit door (and faded out beyond it) a character has left the level
            if e.type == "exit_reached":
                gone.setdefault(e.character, e.t)
        for cid, frames in self.joints.items():
            nan, outside, worst, where = 0, 0, 0.0, ""
            for fi, j in enumerate(frames):
                gone_now = self.times[fi] >= gone.get(cid, math.inf)
                for name, (x, y) in j.items():
                    if not (math.isfinite(x) and math.isfinite(y)):
                        nan += 1
                        continue
                    pen = max(-hw - x, x - hw, -y, y - rh)
                    if pen > m and (gone_now or (in_portal(self.rt.env, (x, y)) and self._door_open_at(self.times[fi]))):
                        pen = 0.0  # walking out through an open doorway (or gone through it)
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
        """No joint moves faster than any authored motion. The one exception is a portal, and it is checked, not
        excused: across a portal jump the earlier frame is carried through that portal's own mapping first, so the
        joints must still agree to within one frame of ordinary motion."""
        from ..motion.arcade import portal_maps
        out = []
        dt = 1.0 / self.fps
        pm = portal_maps(self.rt.env)
        jumps = {cid: [(e.t, e.data["from"]) for e in self.r.events if e.type == "portal_exit" and e.character == cid]
                 for cid in self.joints}
        for cid, frames in self.joints.items():
            worst_joint, worst_pel, where = 0.0, 0.0, 0.0
            for i in range(1, len(frames)):
                a, b = frames[i - 1], frames[i]
                j = next((g for tj, g in jumps[cid] if self.times[i - 1] < tj <= self.times[i]), None)
                if j is not None:
                    a = {k: pm[j].point(v) for k, v in a.items()}
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
        gone = {}
        for e in self.r.events:  # once through an exit door the character has left the level (it is not drawn)
            if e.type == "exit_reached":
                gone.setdefault(e.character, e.t)
        for cid, an in self.r.animators.items():
            worst, cnt, where = 0.0, 0, ""
            for iv in an.planted_intervals():
                ts = np.arange(iv.t0, min(iv.t1, gone.get(cid, math.inf)), 1.0 / 96.0)
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
            # an orb or a portal acts on the body at one physics step; that impulse is verified by its own check
            # (orb_impulses, portal_transfers), so only the steps that straddle it are left out here
            # a hand catching a ledge stops the fall through the arms (a constraint, checked by the ledge checks): left out too
            kicks = [e.t for e in self.r.events if e.character == cid and (e.type.startswith(("orb_", "portal_"))
                                                                            or e.type in ("ledge_catch", "ledge_grab", "graze"))]
            worst_t = None
            for seg in ctrl.segments:
                if seg.kind != "airborne":
                    continue
                for i in range(2, len(T) - 2):
                    if not (seg.t0 + 0.03 < T[i] < seg.t1 - 0.03) or M[i - 2] != "airborne" or M[i + 2] != "airborne":
                        continue
                    if any(abs(T[i] - tk) < 2.5 / 240.0 for tk in kicks):
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
                    if mag > worst_mag:
                        worst_t = T[i]
                    worst_ang, worst_mag, n = max(worst_ang, ang), max(worst_mag, mag), n + 1
            if n == 0:
                out.append(Check(f"gravity_direction[{cid}]", "SKIP", details="no airborne phase"))
            else:
                st = "PASS" if worst_ang <= TOL["gravity_angle_deg"] and worst_mag <= TOL["gravity_mag_rel"] else "FAIL"
                out.append(Check(f"gravity_direction[{cid}]", st, worst_ang, TOL["gravity_angle_deg"],
                                 f"airborne root acceleration vs gravity vector over {n} samples; worst magnitude error {worst_mag:.3%}"
                                 + (f" at t={worst_t:.2f}s" if worst_t is not None else "")))
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
            framed = list(self.r.animators)
            if sh.camera.target and sh.kind != "insert":  # a following shot frames its target and the characters it includes
                framed = [sh.camera.target] + [r.split(":", 1)[1] for r in (sh.camera.include or []) if r.startswith("char:")]
            elif sh.camera.include and sh.kind != "insert":
                # a shot with no character subject frames what it lists (a creature, a prop): those must be in view
                framed = [r.split(":", 1)[1] for r in sh.camera.include if r.startswith("char:")]
                for r in sh.camera.include:
                    if not r.startswith("char:"):
                        p = self.cam.resolve(r, t) if self.cam.resolve else None
                        if p is not None:
                            total += 1
                            vis += self.cam.subject_visible(framed[0] if framed else next(iter(self.r.animators)), t,
                                                            (p[0] - 20, p[1] - 20, p[0] + 20, p[1] + 20))
            for cid in framed:
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
            t_gone = next((e.t for e in self.r.events if e.type == "exit_reached" and e.character == cid), math.inf)
            n_ok = int(max(0.0, t_gone - sc.t0) / sc.dt) if math.isfinite(t_gone) else None  # (not after it has left the level)
            inside = all((-room.width / 2 - 1e-6 <= p[0] <= room.width / 2 + 1e-6 and -1e-6 <= p[1] <= room.height + 1e-6)
                         or in_portal(self.rt.env, (p[0], p[1])) for d in sc.data for frame in d[:n_ok:12] for p in frame)
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
            if ex.unlock_on and ex.unlock_on.startswith("together:") and u is not None:
                # re-derived: at the unlock, every one of them is standing near the door (from the rendered bodies)
                from ..scene.targets import exit_world
                who = ex.unlock_on.split(":", 1)[1].split(",")
                ew = exit_world(env, ex.id)
                far = max(math.dist(r.animators[w].root_at(u), ew) for w in who if w in r.animators)
                ok &= far <= ex.open_radius + 2.0 and all(w in r.animators for w in who)
                msg.append(f"together ({', '.join(who)}; farthest {far:.0f} of {ex.open_radius:.0f} units)")
            elif ex.unlock_on and u is not None:
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
            if e.data.get("move") == "throw":  # a thrown glyph: the prop itself must touch the body
                err = self._prop_body_gap(e.data["prop"], e.data["target"], e.t)
            elif seg.kind != "strike":
                continue
            elif seg.data.get("weapon"):  # a wielded glyph: the prop must reach the struck point
                tp = an._target_point(seg.data["other"], e.t, seg.data["height"], seg.facing)
                err = self._prop_point_gap(seg.data["weapon"], tp, e.t)
            else:
                limb = seg.data["limb"]
                joint = ("hand_" if limb.startswith("hand") else "ankle_") + limb[-1]
                j = self.rt.rigs[e.character].world_joints(an.pose_at(e.t))
                tp = an._target_point(seg.data["other"], e.t, seg.data["height"], seg.facing)
                err = math.dist(j[joint], tp)
            if err > worst:
                worst, where = err, f"{e.character} {e.data.get('move') or seg.data.get('move')} at t={e.t:.2f}s"
        out.append(Check("strike_contact", "PASS" if worst <= TOL["strike_contact"] else "FAIL", worst, TOL["strike_contact"],
                         f"fist/foot distance from the struck body point at contact ({len(hits)} contacts; worst: {where})"))
        cids = list(self.joints)
        worst_gap, where = 1e9, ""
        from ..motion.acrobatics import BODY_PASS_Z
        rolls = 0
        gone = self._gone_times()
        for a in range(len(cids)):
            for b in range(a + 1, len(cids)):
                for i, t in enumerate(self.times):
                    if t >= min(gone.get(cids[a], math.inf), gone.get(cids[b], math.inf)):
                        continue  # one of them has gone through an exit door
                    if abs(self.r.animators[cids[a]].depth_at(t) - self.r.animators[cids[b]].depth_at(t)) >= BODY_PASS_Z:
                        rolls += 1
                        continue  # in different depth lanes: one passes in front of the other (body_clearance proves it)
                    ja, jb = self.joints[cids[a]][i], self.joints[cids[b]][i]
                    if ja["head_center"][1] < 0.6 * self.rt.rigs[cids[a]].p.stand_height or jb["head_center"][1] < 0.6 * self.rt.rigs[cids[b]].p.stand_height:
                        continue  # someone is down / crouched low: overlapping in depth is fine
                    gap = abs(ja["pelvis"][0] - jb["pelvis"][0])
                    if gap < worst_gap:
                        worst_gap, where = gap, f"{cids[a]}/{cids[b]} at t={t:.2f}s"
        if worst_gap < 1e9:
            out.append(Check("fighters_do_not_overlap", "PASS" if worst_gap >= TOL["fighter_gap"] else "FAIL", worst_gap, TOL["fighter_gap"],
                             f"minimum pelvis distance between standing characters in the same depth lane ({where}; {rolls} frames with the bodies "
                             f"in separate lanes)"))
        out.append(self._body_clearance())
        out.append(self._silhouettes())
        out.append(self._screen_separation())
        kd = [e for e in ev if e.type == "knockdown"]
        settled = [e for e in ev if e.type == "settled"]
        ok = all(any(s.character == k.character and s.t > k.t for s in settled) for k in kd)
        out.append(Check("knockdowns_settle", "PASS" if ok or not kd else "WARN", float(len(kd)), None,
                         f"{len(kd)} physics fall(s), {len(settled)} settled before the end"))
        return out

    # ------------------------------------------------------------ acrobatics and symbols
    def _prop_segments(self, pid: str, t: float):
        from ..scene import glyphs
        sp = next(p for p in self.rt.env.props if p.id == pid)
        an = next(iter(self.r.animators.values()))
        if sp.kind == "glyph":
            r = (sp.weight or glyphs.default_weight(sp.size)) / 2
            g = self.r.glyph_at(pid, t, sp.glyph)[0]
            return [(an._prop_world(pid, t, a), an._prop_world(pid, t, b)) for a, b in glyphs.segments(g, sp.size)], r
        return [(an._prop_world(pid, t, (-sp.size[0] / 2, 0)), an._prop_world(pid, t, (sp.size[0] / 2, 0)))], sp.size[1] / 2

    def _prop_point_gap(self, pid: str, p, t: float) -> float:
        from ..motion.acrobatics import _seg_dist
        segs, r = self._prop_segments(pid, t)
        return max(0.0, min(_seg_dist(p, p, a, b)[0] for a, b in segs) - r)

    def _prop_body_gap(self, pid: str, cid: str, t: float) -> float:
        """Distance between a prop's surface and a character's body (pelvis-neck-head chain) at time t."""
        from ..motion.acrobatics import _seg_dist
        segs, r = self._prop_segments(pid, t)
        j = self.rt.rigs[cid].world_joints(self.r.animators[cid].pose_at(t))
        chain = [j["pelvis"], j["neck_base"], j["head_center"]]
        d = min(_seg_dist(p, q, a, b)[0] for a, b in segs for p, q in zip(chain, chain[1:]))
        return max(0.0, d - r - 9.0)

    def check_acrobatics(self) -> List[Check]:
        """Bodies never pass inside structures; feet stay within the tops they stand on; flips land upright."""
        from ..scene import structures
        blocks = structures.blocks(self.rt.env)
        ev = self.r.events
        acro = any(e.type in ("flip", "roll_start", "vault", "climbed", "wall_kick", "step_off", "throw") for e in ev)
        if not blocks and not acro:
            return []
        out = []
        worst, where = 0.0, ""
        for cid, js in self.joints.items():
            for i, t in enumerate(self.times):
                for name in ("pelvis", "neck_base", "head_center"):
                    x, y = js[i][name]
                    for b in blocks:
                        if b.owner in self.r.broken and t >= self.r.broken[b.owner]:
                            continue  # it had collapsed by then
                        if b.x0 < x < b.x1 and b.y0 < y < b.y1:
                            depth = min(x - b.x0, b.x1 - x, y - b.y0, b.y1 - y)
                            if depth > worst:
                                worst, where = depth, f"{cid} {name} in '{b.owner}' at t={t:.2f}s"
        if blocks:
            out.append(Check("body_outside_structures", "PASS" if worst <= TOL["structure_depth"] else "FAIL", worst, TOL["structure_depth"],
                             f"deepest a body point goes inside a structure ({where or 'never'})"))
        worst, where = 0.0, ""
        gone = {}
        for e in ev:  # through an exit door (in the wall) a character has left the level
            if e.type == "exit_reached":
                gone.setdefault(e.character, e.t)
        for cid, an in self.r.animators.items():
            for iv in an.planted_intervals():
                if iv.t0 >= gone.get(cid, math.inf):
                    continue
                seg = an.segments[an.segment_at((iv.t0 + iv.t1) / 2)]
                F = self.r.frames[seg.frame]
                if not F.bounded:
                    continue
                s, _ = F.to_frame(iv.point)
                lo, hi = an._span(F)  # tops that continue each other at the same height are walked as one
                off = max(0.0, lo - s, s - hi)
                if off > worst:
                    worst, where = off, f"{cid} on '{F.tag}' at t={iv.t0:.2f}s"
        if any(f.bounded for f in self.r.frames.values()):
            out.append(Check("feet_on_tops", "PASS" if worst <= TOL["top_overhang"] else "FAIL", worst, TOL["top_overhang"],
                             f"how far a planted foot is past the end of the top it stands on ({where or 'none'})"))
        spans = [(c, pid, t0, t1) for c in self.r.controllers.values() for pid, t0, t1 in getattr(c, "carry_log", [])]
        if spans:
            from ..motion.acrobatics import _seg_dist
            worst, where = 0.0, ""
            for c, pid, t0, t1 in spans:
                for t in self.times:
                    if not (t0 <= t < min(t1, self.r.duration)):
                        continue
                    x, y, a = self.r.animators[c.cid].prop_at(pid, t)
                    segs, r = c._prop_segs_at(pid, (x, y), a)
                    for (p, q) in segs:
                        for kind, s0, s1, rs, owner in c._solids():
                            if kind == "seg":
                                pen = r + rs - _seg_dist(p, q, s0, s1)[0]
                            else:
                                pen = max(min(px - s0[0] + r, s1[0] - px + r, py - s0[1] + r, s1[1] - py + r)
                                          for px, py in ((p[0] + (q[0] - p[0]) * k / 8, p[1] + (q[1] - p[1]) * k / 8) for k in range(9)))
                            if pen > worst:
                                worst, where = pen, f"{pid} in '{owner}' at t={t:.2f}s"
            out.append(Check("held_props_outside_structures", "PASS" if worst <= TOL["held_prop_depth"] else "FAIL", worst,
                             TOL["held_prop_depth"], f"deepest a carried prop goes into a structure ({len(spans)} carries; {where or 'never'})"))
        throws = [e for e in ev if e.type in ("hit", "blocked") and e.data.get("move") == "throw" and "impulse" in e.data]
        if throws:
            import numpy as np
            worst, where = 0.0, ""
            ts = self.r.prop_times
            for e in throws:
                tr = self.r.prop_tracks[e.data["prop"]]
                i = int(np.searchsorted(ts, e.t))
                if i < 3 or i + 3 >= len(ts):
                    continue
                g = self.r.gravity.at(e.t)
                v0 = (tr[i - 1] - tr[i - 3]) / (ts[i - 1] - ts[i - 3])
                v1 = (tr[i + 3] - tr[i + 1]) / (ts[i + 3] - ts[i + 1])
                span = (ts[i + 2] - ts[i - 2])
                n = e.data["normal"]
                dv = (v1[0] - v0[0] - g[0] * span) * n[0] + (v1[1] - v0[1] - g[1] * span) * n[1]
                expect = e.data["impulse"] / e.data["prop_mass"]
                err = abs(dv - expect) / max(1.0, expect)
                if err > worst:
                    worst, where = err, f"{e.data['prop']} at t={e.t:.2f}s (measured {dv:.0f}, impulse/mass {expect:.0f} u/s)"
            out.append(Check("throw_momentum", "PASS" if worst <= TOL["throw_momentum"] else "FAIL", worst, TOL["throw_momentum"],
                             f"prop velocity change along the contact normal vs impulse / mass, from the tracked motion ({len(throws)} impacts; "
                             f"worst {where})"))
        flips = [e for e in ev if e.type == "flip"]
        if flips:
            worst, where = 0.0, ""
            for e in flips:
                # it ends at the touchdown, or where the hands catch a ledge (the body must be upright to hang)
                land = next((x for x in ev if x.type in ("impact", "ledge_catch") and x.character == e.character and x.t > e.t), None)
                if land is None:
                    worst, where = math.pi, f"{e.character} flip at t={e.t:.2f}s never lands"
                    continue
                c = self.r.controllers[e.character]
                rec = max((r_ for r_ in c.records if r_.t < land.t - 1e-9), key=lambda r_: r_.t)  # just before touchdown
                F = self.r.frames[land.data["surface"] if land.type == "impact" else "floor"]
                err = abs(math.atan2(math.sin(rec.angle - F.body_angle), math.cos(rec.angle - F.body_angle)))
                if err > worst:
                    worst, where = err, f"{e.character} at t={land.t:.2f}s"
            out.append(Check("flips_land_upright", "PASS" if worst <= TOL["flip_land"] else "FAIL", worst, TOL["flip_land"],
                             f"body angle from upright at the landing of each flip (rad; {len(flips)} flips; worst {where})"))
        return out

    def _silhouettes(self) -> Check:
        """Readability (2D, on screen): while two fighters are upright, their torsos and heads keep a visible gap,
        whatever their depth lanes. Arms and legs may cross (strikes, blocks); bodies should not merge into one shape."""
        from ..motion.acrobatics import BODY_PASS_Z, _seg_dist
        CORE = (("pelvis", "neck_base", 9.0), ("head_center", "head_center", 11.0))
        cids = list(self.joints)
        worst, where, low, apart = 1e9, "", 0, 0
        for a in range(len(cids)):
            for b in range(a + 1, len(cids)):
                ha, hb = self.rt.rigs[cids[a]].p.stand_height, self.rt.rigs[cids[b]].p.stand_height
                for i, t in enumerate(self.times):
                    ja, jb = self.joints[cids[a]][i], self.joints[cids[b]][i]
                    if ja["head_center"][1] < 0.6 * ha or jb["head_center"][1] < 0.6 * hb:
                        continue  # down, rolling or crouched low
                    if abs(self.r.animators[cids[a]].depth_at(t) - self.r.animators[cids[b]].depth_at(t)) >= BODY_PASS_Z:
                        apart += 1  # one passes in front of the other (body_clearance proves they never intersect)
                        continue
                    g = min(_seg_dist(ja[p0], ja[p1], jb[q0], jb[q1])[0] - ra - rb for p0, p1, ra in CORE for q0, q1, rb in CORE)
                    if g < TOL["silhouette_gap"]:
                        low += 1
                    if g < worst:
                        worst, where = g, f"{cids[a]}/{cids[b]} at t={t:.2f}s"
        if worst >= 1e9:
            return Check("silhouettes_readable", "SKIP", details="fewer than two upright characters")
        return Check("silhouettes_readable", "PASS" if worst >= TOL["silhouette_gap"] else "WARN", worst, TOL["silhouette_gap"],
                     f"on-screen gap between two upright fighters' torsos and heads in the same depth plane (closest {where}; "
                     f"{low} frames under the limit; {apart} frames passing in separate depth lanes)")

    def _screen_separation(self) -> Check:
        """Cinematic, from the camera's point of view (scene-independent, no exemptions, crouched bodies included):
        project both characters' torsos, heads and legs through the actual camera (perspective, depth lanes) and measure
        how much the two silhouettes overlap on screen. Overlap in depth reads as one shape in front of another, but a
        lot of it, for long, makes the action hard to read."""
        import numpy as np
        from ..render.skia_renderer import FOV_K
        cids = list(self.joints)
        if len(cids) < 2:
            return Check("screen_separation", "SKIP", details="fewer than two characters")
        W, H = self.size
        gw, gh = 192, 108
        gx, gy = np.meshgrid((np.arange(gw) + 0.5) / gw * W - W / 2, (np.arange(gh) + 0.5) / gh * H - H / 2)
        P = np.stack([gx.ravel(), gy.ravel()], axis=1)
        CORE = (("pelvis", "neck_base", 9.0), ("head_center", "head_center", 11.0), ("hip_n", "knee_n", 4.0), ("knee_n", "ankle_n", 4.0),
                ("hip_f", "knee_f", 4.0), ("knee_f", "ankle_f", 4.0))

        def mask(j, cam, z):
            k = (H * FOV_K) / max(z + cam.view_h * FOV_K, 20.0)
            S = lambda p: np.array([(p[0] - cam.cx) * k, -(p[1] - cam.cy) * k])
            m = np.zeros(len(P), dtype=bool)
            for a, b, r in CORE:
                A, B = S(j[a]), S(j[b])
                AB = B - A
                L = float(AB @ AB)
                u = np.clip(((P - A) @ AB) / L, 0.0, 1.0) if L > 1e-9 else np.zeros(len(P))
                d = np.linalg.norm(P - (A + np.outer(u, AB)), axis=1)
                m |= d <= r * k
            return m
        bad, worst, where, n = 0, 0.0, "", 0
        for i, t in enumerate(self.times[::2]):
            i *= 2
            cam = self.cam.at(t)
            for a in range(len(cids)):
                for b in range(a + 1, len(cids)):
                    ma = mask(self.joints[cids[a]][i], cam, self.r.animators[cids[a]].depth_at(t))
                    mb = mask(self.joints[cids[b]][i], cam, self.r.animators[cids[b]].depth_at(t))
                    small = min(ma.sum(), mb.sum())
                    if small < 4:
                        continue
                    n += 1
                    ov = float((ma & mb).sum()) / small
                    if ov > TOL["screen_overlap"]:
                        bad += 1
                    if ov > worst:
                        worst, where = ov, f"{cids[a]}/{cids[b]} at t={t:.2f}s"
        frac = bad / max(1, n)
        return Check("screen_separation", "PASS" if frac <= TOL["screen_overlap_frames"] else "WARN", frac, TOL["screen_overlap_frames"],
                     f"share of frames where two characters' silhouettes overlap on screen by more than "
                     f"{TOL['screen_overlap']:.0%} of the smaller one (camera view, depth lanes, crouched poses included; "
                     f"worst {worst:.0%} {where or ''})")

    def _props_through_bodies(self) -> List[Check]:
        """Technical: no dynamic prop passes through a standing body that shares its depth (the bounded-force body
        rule), except the props that character is handling at that moment (logged by the engine)."""
        import numpy as np
        from ..motion.acrobatics import _seg_dist
        from ..motion.controller import BODY_R, KNEE_UP
        from ..scene import glyphs
        props = {p.id: p for p in self.rt.env.props}
        if not props:
            return []
        worst, where = 0.0, ""
        ts = self.r.prop_times
        logs = [getattr(cc, "handled_log", []) for cc in self.r.controllers.values()]
        carried = [(pid, t0, t1) for cc in self.r.controllers.values() for pid, t0, t1 in getattr(cc, "carry_log", [])]
        for cid, c in self.r.controllers.items():
            log = getattr(c, "handled_log", [])
            for rec in c.records[::6]:
                if rec.mode not in ("idle", "loco", "turn", "press", "point", "guard", "strike", "dodge", "hurt", "landing", "throw",
                                    "pick_up", "crouch", "gesture", "offer", "push", "lift", "lever"):
                    continue
                handled = set(next((h for (tt, h) in reversed(log) if tt <= rec.t), frozenset()))
                # carried and thrown props (anyone's) meet bodies through the combat rules, not as solids
                handled |= {pid for pid, t0, t1 in carried if t0 <= rec.t <= t1}
                for lg in logs:
                    h2 = next((h for (tt, h) in reversed(lg) if tt <= rec.t), frozenset())
                    handled |= {p for p in h2 if any(p == pid for pid, _, _ in carried)}
                ca, sa = math.cos(rec.angle), math.sin(rec.angle)
                lo, hi = min(-rec.h + KNEE_UP * c.stand_h, c.cap_b[1] - 20.0), c.cap_b[1]
                A = (rec.pos[0] - sa * lo, rec.pos[1] + ca * lo)
                B = (rec.pos[0] - sa * hi, rec.pos[1] + ca * hi)
                i = int(np.searchsorted(ts, rec.t))
                if i >= len(ts):
                    continue
                for pid, sp in props.items():
                    if pid in handled or not sp.collide_characters or not self.r.alive(pid, rec.t):
                        continue
                    if abs(rec.z - sp.z) >= sp.depth / 2 + 14.0:
                        continue
                    x, y, ang = self.r.prop_tracks[pid][i]
                    pc, ps = math.cos(ang), math.sin(ang)
                    if sp.kind == "glyph":
                        wgt = sp.weight or glyphs.default_weight(sp.size)
                        pen = max(BODY_R + wgt / 2 - _seg_dist(A, B, (x + p[0] * pc - p[1] * ps, y + p[0] * ps + p[1] * pc),
                                                               (x + q[0] * pc - q[1] * ps, y + q[0] * ps + q[1] * pc))[0]
                                  for p, q in glyphs.segments(self.r.glyph_at(pid, rec.t, sp.glyph)[0], sp.size))
                    else:
                        hx, hy = sp.size[0] / 2, sp.size[1] / 2
                        pen = -1e9
                        for k in range(9):
                            u = k / 8
                            px, py = A[0] + (B[0] - A[0]) * u - x, A[1] + (B[1] - A[1]) * u - y
                            lx, ly = px * pc + py * ps, -px * ps + py * pc
                            dx, dy = abs(lx) - hx, abs(ly) - hy
                            sd = math.hypot(max(dx, 0.0), max(dy, 0.0)) if (dx > 0 or dy > 0) else max(dx, dy)
                            pen = max(pen, BODY_R - sd)
                    if pen > worst:
                        worst, where = pen, f"{pid} into {cid} at t={rec.t:.2f}s"
        return [Check("props_not_through_bodies", "PASS" if worst <= TOL["prop_body"] else "FAIL", worst, TOL["prop_body"],
                      f"deepest a dynamic prop goes into a standing body in its depth lane ({where or 'never'})")]

    # ------------------------------------------------------------ carried-object continuity (CORE RUN regressions)
    def _carry_spans(self):
        """Every logged carry: (carrier cid, prop id, t_from, t_to) clamped to the scene."""
        out = []
        for cid, c in self.r.controllers.items():
            for pid, t0, t1 in getattr(c, "carry_log", []):
                out.append((cid, pid, t0, min(t1, self.r.duration)))
        return out

    def check_carried_continuity(self) -> List[Check]:
        """A carried prop stays in its carrier's hands for the whole carry — on the ground, through jumps, flips and
        falls — never left floating in the air behind him (the CORE RUN 'core left behind on the jump' bug). Measured as
        the distance from the prop to the carrier's nearest hand or pelvis at every frame of the carry."""
        spans = self._carry_spans()
        if not spans:
            return []
        worst, where, diag = 0.0, "", []
        for cid, pid, t0, t1 in spans:
            an = self.r.animators.get(cid)
            if an is None:
                continue
            span_worst, span_t = 0.0, t0
            for i, t in enumerate(self.times):
                if not (t0 <= t < t1):
                    continue
                px, py, _ = self.r.animators[cid].prop_at(pid, t) if hasattr(self.r.animators[cid], "prop_at") and self.r.animators[cid].prop_at else (self.r.prop_tracks[pid][min(i, len(self.r.prop_tracks[pid]) - 1)][0], self.r.prop_tracks[pid][min(i, len(self.r.prop_tracks[pid]) - 1)][1], 0.0)
                j = self.joints[cid][i]
                d = min(math.dist((px, py), j[p]) for p in ("hand_n", "hand_f", "pelvis", "neck_base"))
                if d > span_worst:
                    span_worst, span_t = d, t
                if d > worst:
                    worst, where = d, f"{pid} vs {cid} at t={t:.2f}s"
            if span_worst > TOL["carry_reach"]:
                diag.append({"t": round(span_t, 3), "who": [cid, pid], "where": {"prop": [round(c, 1) for c in self.r.animators[cid].prop_at(pid, span_t)[:2]]},
                             "state": {"gap": round(span_worst, 1), "carry_span": [round(t0, 2), round(t1, 2)]},
                             "cause": "carried prop drifted beyond hand reach of its carrier — likely the carry is not updated in this motion state (airborne/flip/fall) or the hold pose is wrong"})
        st = "PASS" if worst <= TOL["carry_reach"] else "FAIL"
        return [Check("carried_object_continuity", st, worst, TOL["carry_reach"],
                      f"{len(spans)} carry span(s): farthest a carried prop got from its carrier's hands ({where or 'never'})", diag)]

    def _supports(self):
        """Solid surfaces a resting prop can sit on: static segments, structure tops, and the room floor (y=0)."""
        segs = [(a, b) for _, a, b, _ in self.r.static_segments]
        for ob in self.rt.env.obstacles:
            if ob.kind in ("platform", "beam"):
                cx, cy = ob.center
                hw, hh = ob.size[0] / 2, ob.size[1] / 2
                segs.append(((cx - hw, cy + hh), (cx + hw, cy + hh)))  # the top edge
        hw = self.rt.env.room.width / 2
        segs.append(((-hw, 0.0), (hw, 0.0)))
        return segs

    def check_floating_props(self) -> List[Check]:
        """No posed (kinematic) prop hangs in the air with nothing holding it and nothing under it — the CORE RUN 'core
        left floating at the exit gate' bug. A prop posed by the engine is legitimate only while someone carries it, or
        while it rests on a surface (placed on a holder, set on the ground). Props a carrier takes out through an exit are
        removed from the scene and never reach this check."""
        from ..scene import glyphs
        kin = getattr(self.r, "prop_kinematic", {})
        if not kin or not any(k.any() for k in kin.values()):
            return []
        # raw carry spans (t1 may be inf: carried to the end of the scene — never clamp it here, or a trailing sample
        # just past the clamp reads as a stranded frame)
        raw = [(pid, t0, t1) for c in self.r.controllers.values() for pid, t0, t1 in getattr(c, "carry_log", [])]
        # only props that something carries are subject to this rule; an authored kinematic flyer (e.g. a drone on a
        # scripted path) is meant to hang in the air and is not a stranded carry
        handled = {pid for pid, _, _ in raw}
        if not handled:
            return []
        supports = self._supports()
        ts = self.r.prop_times
        props = {p.id: p for p in self.rt.env.props}
        worst, where, diag = 0.0, "", []
        for pid, flags in kin.items():
            sp = props.get(pid)
            if sp is None or pid not in handled:
                continue
            rad = (sp.weight or glyphs.default_weight(sp.size)) / 2 if sp.kind == "glyph" else sp.size[1] / 2
            for i in range(0, len(flags), 3):
                t = ts[i]
                if not flags[i] or not self.r.alive(pid, t):
                    continue
                if any(t0 <= t <= t1 for p2, t0, t1 in raw if p2 == pid):
                    continue  # someone is carrying it (t1 == inf: to the end of the scene)
                x, y = self.r.prop_tracks[pid][i][0], self.r.prop_tracks[pid][i][1]
                bottom = y - rad
                # the nearest support directly beneath this x
                gap = math.inf
                for a, b in supports:
                    lo, hi = min(a[0], b[0]), max(a[0], b[0])
                    if lo - rad <= x <= hi + rad:
                        sy = a[1] + (b[1] - a[1]) * ((x - a[0]) / (b[0] - a[0]) if abs(b[0] - a[0]) > 1e-6 else 0.0)
                        if sy <= bottom + 2.0:
                            gap = min(gap, bottom - sy)
                if gap > worst:
                    worst, where = gap, f"{pid} at t={t:.2f}s"
                if gap > TOL["float_gap"] and gap < math.inf:
                    diag.append({"t": round(float(t), 3), "who": [pid], "where": {"prop": [round(x, 1), round(y, 1)]},
                                 "state": {"gap_below": round(gap, 1), "kinematic": True, "carried": False},
                                 "cause": "a posed prop nobody is carrying sits well above any surface — likely a carry ended without a release/placement or the prop was not set to dynamics/removed"})
        st = "PASS" if worst <= TOL["float_gap"] or worst == math.inf else "FAIL"
        m = None if worst == math.inf else worst
        return [Check("props_not_floating", st, m, TOL["float_gap"],
                      f"largest gap below an unheld posed prop and the nearest surface ({where or 'none'})", diag)]

    # ------------------------------------------------------------ screen-space occlusion of important entities
    def _important_props(self):
        """Props that carry the story: anything ever carried, thrown, placed, or named in a key event."""
        ids = {pid for _, pid, _, _ in self._carry_spans()}
        for e in self.r.events:
            if e.type in ("throw", "place", "disarm", "pick_up", "carried_out") and isinstance(e.data.get("prop"), str):
                ids.add(e.data["prop"])
        return [p for p in self.rt.env.props if p.id in ids]

    def check_screen_overlap(self) -> List[Check]:
        """Screen-space (camera view): important characters and story props should not visually bury one another. Where
        one entity's silhouette covers most of another's for a sustained stretch, the action reads as a single shape and
        the audience loses track of who holds what. Reports the worst occlusions with diagnostics (which pair, when, how
        much, who is in front)."""
        import numpy as np
        from ..render.skia_renderer import FOV_K
        cids = list(self.joints)
        iprops = self._important_props()
        if len(cids) + len(iprops) < 2:
            return []
        W, H = self.size
        gw, gh = 160, 90
        gx, gy = np.meshgrid((np.arange(gw) + 0.5) / gw * W - W / 2, (np.arange(gh) + 0.5) / gh * H - H / 2)
        P = np.stack([gx.ravel(), gy.ravel()], axis=1)
        CORE = (("pelvis", "neck_base", 9.0), ("head_center", "head_center", 11.0), ("hip_n", "knee_n", 4.0), ("knee_n", "ankle_n", 4.0),
                ("hip_f", "knee_f", 4.0), ("knee_f", "ankle_f", 4.0))

        def cmask(j, cam, z):
            k = (H * FOV_K) / max(z + cam.view_h * FOV_K, 20.0)
            S = lambda p: np.array([(p[0] - cam.cx) * k, -(p[1] - cam.cy) * k])
            m = np.zeros(len(P), dtype=bool)
            for a, b, r in CORE:
                A, B = S(j[a]), S(j[b])
                AB = B - A
                L = float(AB @ AB)
                u = np.clip(((P - A) @ AB) / L, 0.0, 1.0) if L > 1e-9 else np.zeros(len(P))
                m |= np.linalg.norm(P - (A + np.outer(u, AB)), axis=1) <= r * k
            return m

        def pmask(segs, rad, cam, z):
            k = (H * FOV_K) / max(z + cam.view_h * FOV_K, 20.0)
            S = lambda p: np.array([(p[0] - cam.cx) * k, -(p[1] - cam.cy) * k])
            m = np.zeros(len(P), dtype=bool)
            for a, b in segs:
                A, B = S(a), S(b)
                AB = B - A
                L = float(AB @ AB)
                u = np.clip(((P - A) @ AB) / L, 0.0, 1.0) if L > 1e-9 else np.zeros(len(P))
                m |= np.linalg.norm(P - (A + np.outer(u, AB)), axis=1) <= rad * k
            return m
        ent = [("char", c) for c in cids] + [("prop", p.id) for p in iprops]
        raw = [(c.cid, pid, t0, t1) for c in self.r.controllers.values() for pid, t0, t1 in getattr(c, "carry_log", [])]
        bad, worst, where, n, diag = 0, 0.0, "", 0, []
        pflt = {p.id: p for p in iprops}
        for i, t in enumerate(self.times[::2]):
            i *= 2
            cam = self.cam.at(t)
            # a prop and the character carrying it right now overlap by design (he is holding it) — not an occlusion
            held_by = {pid: cid for cid, pid, t0, t1 in raw if t0 <= t <= t1}
            masks = {}
            for kind, eid in ent:
                if kind == "char":
                    masks[eid] = (cmask(self.joints[eid][i], cam, self.r.animators[eid].depth_at(t)), self.r.animators[eid].depth_at(t))
                else:
                    if not self.r.alive(eid, t):
                        continue
                    segs, rad = self._prop_segments(eid, t)
                    masks[eid] = (pmask(segs, rad, cam, pflt[eid].z), pflt[eid].z)
            ids = list(masks)
            for a in range(len(ids)):
                for b in range(a + 1, len(ids)):
                    # skip the carrier/carried pair: a held prop lying over its own carrier is not one burying the other
                    if held_by.get(ids[a]) == ids[b] or held_by.get(ids[b]) == ids[a]:
                        continue
                    ma, za = masks[ids[a]]
                    mb, zb = masks[ids[b]]
                    sa, sb = ma.sum(), mb.sum()
                    small = min(sa, sb)
                    if small < 6:
                        continue
                    n += 1
                    ov = float((ma & mb).sum()) / small
                    if ov > TOL["char_overlap"]:
                        bad += 1
                    if ov > worst:
                        front = ids[a] if za < zb else ids[b]
                        where = f"{ids[a]}/{ids[b]} at t={t:.2f}s ({front} in front)"
                        worst = ov
                    if ov > 0.85:
                        front = ids[a] if za < zb else ids[b]
                        diag.append({"t": round(t, 3), "who": [ids[a], ids[b]], "where": {"front": front},
                                     "state": {"overlap_frac": round(ov, 3), "depths": [round(za, 1), round(zb, 1)]},
                                     "cause": f"{front} almost entirely covers the other on screen — stage them apart, change the depth lane, or move the camera"})
        frac = bad / max(1, n)
        st = "PASS" if frac <= TOL["char_overlap_frames"] else "WARN"
        return [Check("characters_not_overlapping", st, frac, TOL["char_overlap_frames"],
                      f"share of frames where an important character/prop pair overlaps on screen by more than "
                      f"{TOL['char_overlap']:.0%} of the smaller silhouette (worst {worst:.0%}; {where or 'none'})", diag[:12])]

    # ------------------------------------------------------------ narrative beats (order, cause, visibility)
    def check_narrative(self) -> List[Check]:
        """Validate the story's spine from the engine events: the scripted beats happen in order; each decisive effect
        has its cause on record before it; and the decisive beats play where the camera is looking."""
        from ..scene.goals import matches, parse_goal
        sc = self.rt.scene
        goals = list(sc.goals)
        out: List[Check] = []
        ev = self.r.events
        # 1) order: the explicit goals happen, in the listed order
        if goals:
            from ..scene.goals import progress
            met, times, missing = progress(goals, ev, ordered=True)
            diag = []
            if met < len(goals):
                diag.append({"t": None, "who": [missing], "where": {}, "state": {"met": met, "of": len(goals), "times": [None if x is None else round(x, 2) for x in times]},
                             "cause": f"beat {missing!r} did not happen in order after the earlier beats"})
            out.append(Check("narrative_order", "PASS" if met == len(goals) else "WARN", float(met), float(len(goals)),
                             f"{met}/{len(goals)} scripted story beats happened in order" + ("" if met == len(goals) else f"; first missing: {missing}"), diag))
        # 2) causality: an effect must follow its cause (same subject where it applies) within a window
        RULES = [  # (effect type, [cause types], same_subject, window s)
            ("knockdown", ["hit", "strike_start", "throw", "prop_hit"], False, 2.5),
            ("hit", ["strike_start"], True, 1.5),
            ("blocked", ["strike_start"], False, 1.5),
            ("freed", ["pinned"], True, 60.0),
            ("pulled_up", ["ledge_catch", "collapse", "hang_slip", "hand_grab"], False, 60.0),
            ("throw", ["pick_up", "grab"], False, 60.0),
            ("carried_out", ["pick_up", "grab"], False, 1e9),
            ("disarm", ["throw", "hit", "prop_hit"], False, 2.5),
        ]
        by_type: Dict[str, list] = {}
        for e in ev:
            by_type.setdefault(e.type, []).append(e)
        spans = self._carry_spans()
        viol, nrules, diag = 0, 0, []
        for eff, causes, same, win in RULES:
            for e in by_type.get(eff, []):
                nrules += 1
                ok = any(c.t <= e.t + 1e-6 and e.t - c.t <= win and (not same or c.character == e.character)
                         for ct in causes for c in by_type.get(ct, []))
                # handling a prop (throw, carried_out, disarm) is also caused by already carrying it — a prop can be
                # carried in from the previous scene (a placement, logged with no pick_up event of its own)
                if not ok and eff in ("throw", "carried_out", "disarm"):
                    prop = e.data.get("prop") or e.data.get("with")
                    ok = any(t0 <= e.t + 1e-6 for cid, pid, t0, t1 in spans if pid == prop)
                if not ok:
                    viol += 1
                    diag.append({"t": round(e.t, 3), "who": [e.character], "where": {"event": eff},
                                 "state": {"needs_one_of": causes, "within_s": win, "same_subject": same},
                                 "cause": f"{eff}@{e.character} has no preceding {' / '.join(causes)} — the effect appears without its cause"})
        if nrules:
            out.append(Check("narrative_causality", "PASS" if viol == 0 else "WARN", float(viol), 0.0,
                             f"{nrules} cause→effect links checked; {viol} effect(s) without a cause before them", diag[:12]))
        # 3) visibility: the decisive beats (the scripted goal events that have a world point) are on screen
        if goals:
            aspect = self.size[0] / self.size[1]
            off, n, diag = [], 0, []
            for g in goals:
                e = next((x for x in ev if matches(g, x)), None)
                if e is None:
                    continue
                p = e.data.get("point")
                if not isinstance(p, (tuple, list)) or len(p) != 2:
                    continue
                n += 1
                c = self.cam.at(e.t)
                r = math.radians(c.roll)
                dx, dy = p[0] - c.cx, -(p[1] - c.cy)
                sx, sy = dx * math.cos(r) - dy * math.sin(r), dx * math.sin(r) + dy * math.cos(r)
                if abs(sx) > c.view_h * aspect / 2 * 0.96 or abs(sy) > c.view_h / 2 * 0.96:
                    off.append(f"{e.type}@{e.character} t={e.t:.2f}s")
                    diag.append({"t": round(e.t, 3), "who": [e.character], "where": {"point": [round(p[0], 1), round(p[1], 1)], "screen": [round(sx, 1), round(sy, 1)]},
                                 "state": {"view_h": round(c.view_h, 1), "cam": [round(c.cx, 1), round(c.cy, 1)]},
                                 "cause": "a decisive story beat happened off screen — the shot framing this beat does not contain its location"})
            if n:
                out.append(Check("decisive_events_visible", "PASS" if not off else "WARN", float(len(off)), 0.0,
                                 f"{n} decisive beat(s) with a location; off screen: {', '.join(off[:6]) or 'none'}", diag))
        return out

    def _core_at(self, cid: str, t: float, core):
        """The body parts that must keep clear: during a kick, the kicking leg is the weapon (like the arms), not the body."""
        an = self.r.animators[cid]
        seg = an.segments[an.segment_at(t)]
        limb = seg.data.get("limb", "") if seg.kind == "strike" else ""
        if limb.startswith("foot"):
            side = limb[-1]
            return [c for c in core if not c[0].endswith("_" + side)]
        return core

    def _gone_times(self) -> Dict[str, float]:
        """When each character went through an exit door (it has left the level)."""
        out: Dict[str, float] = {}
        for e in self.r.events:
            if e.type == "exit_reached":
                out.setdefault(e.character, e.t)
        return out

    def _body_clearance(self) -> Check:
        """Geometry-aware, no exemptions: the bodies (torso, head, thighs, shins as capsules with a depth extent) of two
        characters never intersect. Two bodies intersect only if they overlap in the picture plane AND their depth lanes
        are closer than two half-depths. Arms are not counted (they block, strike and bump fists by design)."""
        from ..motion.acrobatics import BODY_PASS_Z, _seg_dist
        CORE = (("pelvis", "neck_base", 9.0), ("head_center", "head_center", 11.0), ("hip_n", "knee_n", 5.0), ("knee_n", "ankle_n", 4.5),
                ("hip_f", "knee_f", 5.0), ("knee_f", "ankle_f", 4.5))
        cids = list(self.joints)
        worst, where, n = 0.0, "", 0
        gone = self._gone_times()
        for a in range(len(cids)):
            for b in range(a + 1, len(cids)):
                for i, t in enumerate(self.times):
                    if t >= min(gone.get(cids[a], math.inf), gone.get(cids[b], math.inf)):
                        continue  # one of them has gone through an exit door
                    dz = abs(self.r.animators[cids[a]].depth_at(t) - self.r.animators[cids[b]].depth_at(t))
                    zpen = BODY_PASS_Z - dz
                    if zpen <= 0.0:
                        continue
                    ja, jb = self.joints[cids[a]][i], self.joints[cids[b]][i]
                    ca, cb = self._core_at(cids[a], t, CORE), self._core_at(cids[b], t, CORE)
                    # legs are as thick as they are drawn (half the character's limb width)
                    ca = [(p, q, (self.rt.project.character(cids[a]).style.limb_width / 2 if p.startswith(("hip", "knee")) else r)) for p, q, r in ca]
                    cb = [(p, q, (self.rt.project.character(cids[b]).style.limb_width / 2 if p.startswith(("hip", "knee")) else r)) for p, q, r in cb]
                    for p0, p1, ra in ca:
                        for q0, q1, rb in cb:
                            d = _seg_dist(ja[p0], ja[p1], jb[q0], jb[q1])[0]
                            pen = min(ra + rb - d, zpen)
                            if pen > 0.0:
                                n += 1
                            if pen > worst:
                                worst, where = pen, f"{cids[a]} {p0}-{p1} / {cids[b]} {q0}-{q1} at t={t:.2f}s (depth gap {dz:.0f})"
        return Check("body_clearance", "PASS" if worst <= TOL["body_clearance"] else "FAIL", worst, TOL["body_clearance"],
                     f"deepest intersection of two characters' bodies in 3D (torso, head, legs; no exemptions; {where or 'never'})")

    def check_sync(self, cues) -> List[Check]:
        if cues is None:
            return [Check("audio_event_sync", "SKIP", details="no audio rendered")]
        w = self.warp
        evs = self.r.events if w is None or w.is_identity() else [(w.film_at(e.t), e.type) for e in self.r.events]
        times = {(round(e.t, 6), e.type) for e in self.r.events} if w is None or w.is_identity() else {(round(t, 6), k) for t, k in evs}
        if w is not None and not w.is_identity():
            times |= {(round(w.film_at(sl.t0), 6), "slowmo") for sl in w.slows}
        stray = [c for c in cues if (round(c.t, 6), c.event_type) not in times]
        return [Check("audio_event_sync", "PASS" if not stray else "FAIL", float(len(stray)), 0.0,
                      f"{len(cues)} cues, each placed at its engine event time (0 unbound cues allowed)")]

    def check_beats(self, video: Optional[str] = None) -> List[Check]:
        """Beat sync (Milestone 4), in film time:
        - beat_cuts: every snapped shot boundary is on its beat (to half a film frame);
        - beat_waits: every beat wait ended on its beat (to one physics step);
        - music_on_beat: measured back from the rendered soundtrack, the kick onsets sit on the beat grid."""
        sc = self.rt.scene
        mu = sc.music
        if mu is None:
            return []
        from ..scene.beats import nearest_beat, period
        film = (lambda t: t) if self.warp is None else self.warp.film_at
        out = []
        log = getattr(self.rt, "beat_log", [])
        snapped = [b for b in log if b["snapped"]]
        err = max((abs(film(b["after"]) - nearest_beat(mu, film(b["after"]))[1]) for b in snapped), default=0.0)
        out.append(Check("beat_cuts", "PASS" if err <= 0.5 / self.fps + 1e-6 else "FAIL", err, 0.5 / self.fps,
                         f"{len(snapped)} of {len(log)} cuts snapped onto beats (bpm {mu.bpm:g}; {sum(1 for b in log if b.get('locked'))} "
                         f"kept on a portal crossing); worst offset in seconds of film"))
        ends = [e for e in self.r.events if e.type == "beat_wait_end"]
        P = period(mu)
        werr = max((abs(film(e.t) - (mu.offset + e.data["beat"] * P)) for e in ends), default=0.0)
        out.append(Check("beat_waits", "PASS" if werr <= 1.5 / 240.0 else "FAIL", werr, 1.5 / 240.0,
                         f"{len(ends)} beat waits; worst offset from their beat (s of film)"))
        wav = os.path.splitext(video)[0] + ".wav" if video else None
        if wav and os.path.exists(wav):
            import wave
            import numpy as np
            with wave.open(wav) as w:
                sr = w.getframerate()
                x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").reshape(-1, w.getnchannels()).mean(1) / 32768.0
            from ..audio.sound_director import SR, kick_wave
            k = kick_wave()[: int(0.08 * SR)]  # matched filter on the kick's first 80 ms: other sounds barely correlate
            k = k / (np.linalg.norm(k) + 1e-12)
            errs, found = [], 0
            beats = [b for b in (mu.offset + j * P for j in range(int(len(x) / sr / P) + 1)) if 0.05 < b < len(x) / sr - 0.3]
            for b in beats:
                i0 = int((b - 0.03) * sr)
                seg = x[max(0, i0): int((b + 0.03) * sr) + len(k)]
                if len(seg) < len(k) + 2:
                    continue
                corr = np.correlate(seg, k, mode="valid")
                j = int(np.argmax(corr))
                local = np.linalg.norm(seg[j:j + len(k)]) + 1e-12
                if corr[j] / local > 0.6:  # the kick is really there (normalised correlation)
                    found += 1
                    errs.append(abs((max(0, i0) + j) / sr - b))
            frac = found / max(1, len(beats))
            worst = max(errs, default=1.0)
            ok = frac >= 0.9 and worst <= 0.005
            out.append(Check("music_on_beat", "PASS" if ok else "FAIL", worst, 0.005,
                             f"kick found at {found}/{len(beats)} beats ({frac:.0%}) by matched filter on the rendered WAV; worst offset (s)"))
        else:
            out.append(Check("music_on_beat", "SKIP", details="no soundtrack rendered"))
        return out

    def check_breakables(self) -> List[Check]:
        """Breakables (Milestone 5), against the simulation:
        - breaks_at_threshold: every break was caused by a contact impulse at least the prop's threshold;
        - breaks_conserve_momentum: the pieces leave with the prop's momentum (their scatter adds none);
        - breaks_continuous: at the break each piece is exactly where it was inside the prop (no pop), from the tracks."""
        import numpy as np
        brk = [e for e in self.r.events if e.type == "break"]
        if not any(p.breakable for p in self.rt.env.props):
            return []
        under = [e.character for e in brk if e.data["impulse"] < e.data["threshold"] - 1e-9]
        worst_p, worst_x = 0.0, 0.0
        specs = {p.id: p for p in self.rt.env.props}
        for e in brk:
            P = e.data["momentum"]
            S = [sum(m * v[i] for v, m in e.data["piece_motion"].values()) for i in (0, 1)]
            M = e.data["mass"]
            worst_p = max(worst_p, math.dist(P, S) / (math.hypot(*P) + M))
            k = int(np.searchsorted(self.r.prop_times, e.t - 1e-9))
            par = self.r.prop_tracks[e.character][k]  # the break's own sample: the prop where it broke, the pieces leaving it
            for f in e.data["pieces"]:
                fr = self.r.prop_tracks[f][k]
                loc = specs[f].local
                ca, sa = math.cos(par[2]), math.sin(par[2])
                want = (par[0] + loc[0] * ca - loc[1] * sa, par[1] + loc[0] * sa + loc[1] * ca)
                worst_x = max(worst_x, math.dist(want, fr[:2]), abs(math.remainder(fr[2] - par[2], 2 * math.pi)) * 50.0)
        return [Check("breaks_at_threshold", "PASS" if not under else "FAIL", float(len(under)), 0.0,
                      f"{len(brk)} break(s), each from a contact impulse at or above the prop's threshold"),
                Check("breaks_conserve_momentum", "PASS" if worst_p <= 1e-6 else "FAIL", worst_p, 1e-6,
                      "relative difference between the prop's momentum and its pieces' total"),
                Check("breaks_continuous", "PASS" if worst_x <= 0.5 else "FAIL", worst_x, 0.5,
                      "how far a piece is from its place in the prop at the moment of the break (units)")]

    def check_morphs(self) -> List[Check]:
        """Morphs (Milestone 5): the shape change conserves motion (centre-of-mass velocity and angular momentum), the
        centre of mass only moves by the recorded nudge, no character is inside the new shape when it appears, and the
        drawn blend ends exactly on the new shape (no pop at the swap)."""
        from ..scene import glyphs
        logs = {pid: ms for pid, ms in self.r.morphs.items() if ms}
        if not logs:
            return []
        specs = {p.id: p for p in self.rt.env.props}
        worst_m, worst_c, worst_pop, n = 0.0, 0.0, 0.0, 0
        for pid, ms in logs.items():
            sp = specs[pid]
            for m in ms:
                if m["t_swap"] is None:
                    continue
                n += 1
                worst_m = max(worst_m, math.dist(m["v0"], m["v1"]) / (math.hypot(*m["v0"]) + 1.0),
                              abs(m["I0"] * m["w0"] - m["I1"] * m["w1"]) / (abs(m["I0"] * m["w0"]) + m["I0"]))
                worst_c = max(worst_c, abs(math.dist(m["c0"], m["c1"]) - math.hypot(*m.get("nudge", (0.0, 0.0)))))
                # the drawing just before the swap vs just after
                t0, t1 = m["t_swap"] - 1e-4, m["t_swap"] + 1.0 / 240.0
                a, b = self.rt.evaluate(t0), self.rt.evaluate(t1)
                pa, pb = next(p for p in a.props if p.id == pid), next(p for p in b.props if p.id == pid)
                sa = glyphs.blend(pa.morph[0], pa.morph[1], pa.morph[2], sp.size, shift=pa.morph[3]) if pa.morph else glyphs.strokes(pa.glyph, sp.size)
                sb = glyphs.strokes(pb.glyph, sp.size)
                W = lambda pr, p: (pr.pos[0] + p[0] * math.cos(pr.angle) - p[1] * math.sin(pr.angle),
                                   pr.pos[1] + p[0] * math.sin(pr.angle) + p[1] * math.cos(pr.angle))
                ea = [W(pa, st[0]) for st in sa] + [W(pa, st[-1]) for st in sa]
                eb = [W(pb, st[0]) for st in sb] + [W(pb, st[-1]) for st in sb]
                # every end of the new shape is drawn where the blend left one (small motion over 1/240 s allowed)
                worst_pop = max(worst_pop, max(min(math.dist(p, q) for q in ea) for p in eb))
        return [Check("morphs_conserve_motion", "PASS" if worst_m <= 1e-6 else "FAIL", worst_m, 1e-6,
                      f"{n} shape change(s): relative change of centre-of-mass velocity or angular momentum"),
                Check("morphs_hold_centre", "PASS" if worst_c <= 1e-6 else "FAIL", worst_c, 1e-6,
                      "centre-of-mass shift beyond the recorded nudge (units)"),
                Check("morphs_no_pop", "PASS" if worst_pop <= 6.0 else "FAIL", worst_pop, 6.0,
                      "distance between the drawn blend's end and the new shape at the swap (units)")]

    def check_diagrams(self) -> List[Check]:
        """Diagram layer (Milestone 5): every number shown is re-derived independently and must agree.
        - diagrams_truthful: velocity arrows and speed labels vs the velocity of the *rendered* body (central difference
          of the drawn pelvis or prop centre); distances vs the rendered positions; impulse arrows vs the engine's own
          orb records. Samples straddling an impulse (orb, portal, landing, break) are skipped: there the velocity jumps.
        - diagrams_in_frame (cinematic): the annotated point is on screen while the diagram shows."""
        if not self.rt.scene.diagrams:
            return []
        from ..render.diagrams import Diagrams
        dg = Diagrams(self.rt)
        kicks = {}
        for e in self.r.events:
            if e.type.startswith(("orb_", "portal_")) or e.type in ("impact", "break", "takeoff", "morph", "hit", "throw", "prop_impact",
                                                                       "creature_break"):
                kicks.setdefault(e.character, []).append(e.t)
                if e.data.get("prop"):  # a throw releases (or a pick-up takes) a prop: its velocity jumps there too
                    kicks.setdefault(e.data["prop"], []).append(e.t)
        worst, n, where, vis, tot = 0.0, 0, "none", 0, 0
        h = 1.0 / 48.0
        for t in self.times[::2]:
            for p in dg.at(t):
                d = next(x for x in self.rt.scene.diagrams if x.id == p.src)
                rid = d.target.partition(":")[2]
                if p.kind in ("arrow", "text") and p.data.get("event") is None and p.value is not None and d.kind in ("velocity", "label"):
                    if any(abs(t - k) < 2 * h + 0.02 for k in kicks.get(rid, ())):
                        continue
                    a, b = dg.point(d.target, t - h), dg.point(d.target, t + h)
                    v_ind = math.dist(a, b) / (2 * h)
                    # 15 u/s of authored acting (a settle, a weight shift) moves the drawn root over a still body
                    err = max(0.0, abs(p.value - v_ind) - 15.0) / (abs(v_ind) + 40.0)
                elif p.kind == "dim":
                    err = abs(p.value - math.dist(dg.point(d.target, t), dg.point(d.to, t))) / (p.value + 1.0)
                elif p.data.get("event", "").startswith("orb_"):
                    o = next(e for e in self.r.events if e.type == p.data["event"] and e.character == rid and abs(e.t - p.data["t"]) < 1e-9)
                    rec_after = next(r for r in self.r.controllers[rid].records if r.t >= o.t + 1.0 / 240.0 - 1e-9)
                    g = self.r.gravity.at(o.t)
                    dv = (rec_after.vel[0] - g[0] / 240.0 - o.data["v_before"][0], rec_after.vel[1] - g[1] / 240.0 - o.data["v_before"][1])
                    err = abs(p.value - math.hypot(*dv)) / (math.hypot(*dv) + 1.0)
                else:
                    continue
                n += 1
                if err > worst:
                    worst, where = err, f"{p.src} at t={t:.2f}s"
                tot += 1
                c = self.cam.at(t)
                x, y = p.pts[-1]
                vis += abs(x - c.cx) <= c.view_h * self.size[0] / self.size[1] / 2 and abs(y - c.cy) <= c.view_h / 2
        return [Check("diagrams_truthful", "PASS" if worst <= TOL["diagram_err"] else "FAIL", worst, TOL["diagram_err"],
                      f"{n} shown values re-derived independently; worst relative disagreement ({where})"),
                Check("diagrams_in_frame", "PASS" if tot == 0 or vis / tot >= 0.9 else "WARN", vis / max(1, tot), 0.9,
                      "share of shown annotations whose anchor is on screen")]

    def check_creatures(self) -> List[Check]:
        """Composite creatures (Milestone 5), from the tracks:
        - creature_joints_hold: until it is torn apart, every limb stays on its joint (the two ends of each joint agree);
        - creature_breaks_at_threshold: it only came apart under a blow at or above its threshold;
        - creature_follows_path: while intact and unhindered, the body keeps to its path (a lag means the drive or the
          gait is fighting the physics)."""
        drivers = getattr(self.r, "creatures", []) or []
        if not drivers:
            return []
        worst_j, worst_p, n = 0.0, 0.0, 0
        T = self.r.prop_times
        for dv in drivers:
            end = dv.broken_t if dv.broken_t is not None else T[-1]
            for i in range(0, len(T), 12):
                if T[i] >= end:
                    break
                worst_j = max(worst_j, dv.joint_error(self.r.prop_tracks, i))
                if dv.pt[0] + 0.6 <= T[i] <= dv.pt[-1]:
                    x = self.r.prop_tracks[dv.body_tag][i][0]
                    worst_p = max(worst_p, abs(x - dv.target(T[i])[0]))
                n += 1
        brk = [e for e in self.r.events if e.type == "creature_break"]
        under = [e for e in brk if e.data["impulse"] < e.data["threshold"]]
        return [Check("creature_joints_hold", "PASS" if worst_j <= 3.0 else "FAIL", worst_j, 3.0,
                      f"{len(drivers)} creature(s), {n} samples: largest gap between the two ends of a joint (units)"),
                Check("creature_breaks_at_threshold", "PASS" if not under else "FAIL", float(len(under)), 0.0,
                      f"{len(brk)} creature(s) torn apart, each by a blow at or above its threshold"),
                Check("creature_follows_path", "PASS" if worst_p <= 40.0 else "WARN", worst_p, 40.0,
                      "largest lag behind the path while intact (units)")]

    KEY_EVENTS = ("break", "creature_break", "morph", "morph_start", "throw", "portal_exit", "portal_enter", "orb_jump", "orb_boost",
                  "orb_pad", "collect", "hit", "knockdown", "rope_snap", "pinned", "prop_hit")

    def check_causes_on_screen(self) -> List[Check]:
        """Spatial continuity (cinematic): every key cause and effect (a break, a creature torn apart, a shape change, a throw,
        a portal crossing at both ends, an orb, a blow) happens where the camera is looking at that moment, so a cut never
        hides the link between two connected places."""
        off = []
        n = 0
        aspect = self.size[0] / self.size[1]
        for e in self.r.events:
            if e.type not in self.KEY_EVENTS:
                continue
            p = e.data.get("point")
            if not isinstance(p, (tuple, list)) or len(p) != 2:
                continue
            n += 1
            # a portal crossing is instantaneous: its entry is seen in the frame before, its exit in the frame after
            te = e.t - 1.0 / self.fps if e.type == "portal_enter" else e.t + 1.0 / self.fps if e.type == "portal_exit" else e.t
            c = self.cam.at(te)
            r = math.radians(c.roll)
            dx, dy = p[0] - c.cx, -(p[1] - c.cy)
            sx, sy = dx * math.cos(r) - dy * math.sin(r), dx * math.sin(r) + dy * math.cos(r)
            if abs(sx) > c.view_h * aspect / 2 * 0.96 or abs(sy) > c.view_h / 2 * 0.96:
                off.append(f"{e.type}@{e.character} t={e.t:.2f}s")
        return [] if n == 0 else [Check("causes_on_screen", "PASS" if not off else "WARN", float(len(off)), 0.0,
                                        f"{n} key events; off screen: {', '.join(off[:6]) or 'none'}")]

    def check_hands_meet(self) -> List[Check]:
        """Character interaction (Milestone 6): at every hand grab the two hands really touch, and stay together while one
        character pulls the other (measured on the rendered poses)."""
        grabs = [e for e in self.r.events if e.type == "hand_grab" and e.data.get("with") in self.r.animators and e.character in self.r.animators]
        if not grabs:
            return []
        worst, where = 0.0, ""
        for e in grabs:
            a, b = self.r.animators[e.character], self.r.animators[e.data["with"]]
            hold = e.data.get("hold", 0.5)
            for dt in (0.0, hold / 3, 2 * hold / 3, hold):
                t = e.t + dt
                if t > self.r.duration:
                    break
                ha = self.rt.rigs[e.character].world_joints(a.pose_at(t))["hand_n"]
                hb = self.rt.rigs[e.data["with"]].world_joints(b.pose_at(t))["hand_n"]
                d = math.dist(ha, hb)
                if d > worst:
                    worst, where = d, f"{e.character}-{e.data['with']} at t={t:.2f}s"
        return [Check("hands_meet", "PASS" if worst <= TOL["hand_contact"] else "FAIL", worst, TOL["hand_contact"],
                      f"{len(grabs)} hand grab(s): largest gap between the two hands while holding ({where})")]

    def check_particles(self) -> List[Check]:
        """Event particles (Milestone 4): deterministic (two independent builds give identical particles at every
        sampled frame, in any evaluation order), within the drawing budget, and every burst comes from an engine event."""
        from ..render.particles import MAX_ALIVE, Particles
        a = Particles(self.r.events, self.rt.env, self.rt.project.seed)
        if not a.bursts:
            return []
        b = Particles(self.r.events, self.rt.env, self.rt.project.seed)
        ts = self.times[::3]
        same = all(a.at(t) == b.at(t) for t in reversed(ts))  # b evaluated backwards: no hidden state
        peak = max(len(a.at(t)) for t in ts)
        return [Check("particles_deterministic", "PASS" if same else "FAIL", details=f"{len(a.bursts)} bursts, each from an event"),
                Check("particle_budget", "PASS" if peak <= MAX_ALIVE else "FAIL", float(peak), float(MAX_ALIVE), "most particles alive at once")]

    def check_arcade(self) -> List[Check]:
        """Orbs and portals (Milestone 4), checked against physics, not trusted:
        - portal_transfers: every crossing keeps the speed, rotates the velocity by the portal pair's angle, and the body
          (a character's pelvis, a prop's centre) really is at the mapped exit point just after;
        - orb_impulses: each orb changed the body's velocity by what the orb does (jump/pad: the 'up' speed of a jump of
          its apex height; boost: its speed added), measured from the simulation records around the event;
        - collectibles_once: a collected orb is collected once."""
        import numpy as np
        from ..motion.arcade import ORB_DEFAULT, portal_maps
        env = self.rt.env
        if not (env.portals or env.orbs):
            return []
        out = []
        if env.portals:
            pm = portal_maps(env)
            worst, n, where = 0.0, 0, "none"
            for e in self.r.events:
                if e.type != "portal_exit":
                    continue
                n += 1
                m = pm[e.data["from"]]
                ent = next(x for x in self.r.events if x.type == "portal_enter" and x.character == e.character and abs(x.t - e.t) < 1e-9)
                v_in, v_out = ent.data["velocity"], e.data["velocity"]
                err_v = math.dist(m.vec(v_in), v_out) + abs(math.hypot(*v_in) - math.hypot(*v_out))
                err_p = math.dist(m.point(ent.data["point"]), e.data["point"])
                if e.character in self.r.controllers:
                    rec = next(r for r in self.r.controllers[e.character].records if r.t >= e.t - 1e-9)
                    actual = rec.pos
                else:
                    tr = self.r.prop_tracks[e.character]
                    k = int(np.searchsorted(self.r.prop_times, e.t - 1e-9))
                    actual = (tr[k, 0], tr[k, 1])
                err = max(err_v, err_p, math.dist(actual, e.data["point"]))
                if err > worst:
                    worst, where = err, f"{e.character} via {e.data['from']} at t={e.t:.2f}s"
            out.append(Check("portal_transfers", "PASS" if worst <= TOL["portal_err"] else "FAIL", worst, TOL["portal_err"],
                             f"{n} crossings; worst mismatch in speed, velocity direction or exit position ({where})"))
        if env.orbs:
            orbs = {o.id: o for o in env.orbs}
            worst, n, where = 0.0, 0, "none"
            for e in self.r.events:
                if not e.type.startswith("orb_"):
                    continue
                n += 1
                o = orbs[e.data["orb"]]
                c = self.r.controllers[e.character]
                g = self.r.gravity.at(e.t)
                gm = math.hypot(*g)
                after = next(r for r in c.records if r.t >= e.t + 1.0 / 240.0 - 1e-9)  # one physics step later
                v1 = (after.vel[0] - g[0] / 240.0, after.vel[1] - g[1] / 240.0)  # remove that step's gravity
                power = o.power if o.power is not None else ORB_DEFAULT[o.kind]
                if o.kind == "boost":
                    err = abs(abs(v1[0] - e.data["v_before"][0]) - power) / power
                else:
                    up = (-g[0] / gm, -g[1] / gm)
                    want = math.sqrt(2 * gm * power)
                    err = abs(v1[0] * up[0] + v1[1] * up[1] - want) / want
                if err > worst:
                    worst, where = err, f"{e.data['orb']} ({o.kind}) on {e.character} at t={e.t:.2f}s"
            out.append(Check("orb_impulses", "PASS" if worst <= TOL["orb_err"] else "FAIL", worst, TOL["orb_err"],
                             f"{n} orb hits; worst relative error of the velocity change against the orb's spec ({where})"))
            got = [e.data["orb"] for e in self.r.events if e.type == "collect"]
            out.append(Check("collectibles_once", "PASS" if len(got) == len(set(got)) else "FAIL", float(len(got) - len(set(got))), 0.0,
                             f"{len(set(got))} of {sum(1 for o in env.orbs if o.kind == 'collect')} collectibles taken"))
        return out

    def check_time_fx(self) -> List[Check]:
        """Hit-stop and slow motion: the warp is monotonic and covers the whole story; every blow holds for its frames;
        impact flashes stay within photosensitivity limits."""
        w = self.warp
        if w is None or w.is_identity():
            return []
        import numpy as np
        out = []
        mono = bool(np.all(np.diff(w.S) >= -1e-9) and np.all(np.diff(w.F) > 0))
        cover = abs(w.S[-1] - self.r.duration) < 1e-6
        out.append(Check("time_warp_valid", "PASS" if mono and cover else "FAIL", float(w.film_duration), None,
                         f"story {self.r.duration:.2f}s -> film {w.film_duration:.2f}s; monotonic {mono}; covers the story {cover}; "
                         f"{len(w.holds)} hit-stops, {len(w.slows)} slow-motion sections"))
        bad = []
        for h in w.holds:
            f0 = w.film_at(h.t)
            frames = [k for k in range(int(f0 * self.fps) - 1, int((f0 + h.film) * self.fps) + 2)
                      if abs(w.sim_at(k / self.fps) - h.t) < 1e-6]
            if len(frames) < max(1, int(round(h.film * self.fps)) - 1):
                bad.append(f"{h.kind}@{h.t:.2f}s")
        out.append(Check("hit_stop_frames", "PASS" if not bad else "FAIL", float(len(bad)), 0.0,
                         f"every blow holds its impact frame ({len(w.holds)} holds, "
                         f"{sum(round(h.film * self.fps) for h in w.holds)} frames; short: {', '.join(bad) or 'none'})"))
        from ..render.pipeline import screen_effects
        tfx = self.rt.scene.time_fx
        n = int(round(w.film_duration * self.fps))
        flashes = [k / self.fps for k in range(n) if screen_effects(w, k / self.fps, tfx).get("flash", 0.0) > 0.2]
        worst = max((sum(1 for f in flashes if t0 <= f < t0 + 1.0) for t0 in flashes), default=0)
        out.append(Check("flash_safety", "PASS" if worst <= 3 else "FAIL", float(worst), 3.0,
                         "bright full-screen flashes in any one second (photosensitivity guideline: at most 3)"))
        rates = [sl.rate for sl in w.slows]
        out.append(Check("slowmo_bounds", "PASS" if all(0.1 <= r <= 1.0 for r in rates) else "FAIL", min(rates, default=1.0), 0.1,
                         f"{len(rates)} slow-motion sections; slowest rate {min(rates, default=1.0):.2f}x"))
        return out

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
        exp_frames = int(round((self.warp.film_duration if self.warp is not None else self.r.duration) * self.fps))
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
