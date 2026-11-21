"""APEX scene schema v0.1 — the machine-readable contract between the AI Story Director, the editor,
the runtime and the renderer. Every field is validated; see docs/SCENE_SCHEMA.md.
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

SCHEMA_VERSION = "0.1"
Vec2 = Tuple[float, float]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------- characters
class CharacterStyle(Strict):
    body_color: str = "#ffcf3a"
    far_color: str = "#c08f1e"
    visor_color: str = "#5ff6ff"
    scarf_color: str = "#19dcc6"
    glow_color: str = "#ffbe3c"
    limb_width: float = Field(7.0, gt=0, le=20)  # bolder strokes read better at film scale (art direction, 1D quality pass)
    has_scarf: bool = True
    # movement style (character-specific motion signature)
    cadence_scale: float = Field(1.0, gt=0.5, lt=2.0)
    stride_scale: float = Field(1.0, gt=0.5, lt=2.0)
    lean_scale: float = Field(1.0, ge=0.0, lt=3.0)
    arm_swing_scale: float = Field(1.0, ge=0.0, lt=3.0)


class CharacterSpec(Strict):
    id: str
    name: str
    rig: Literal["stickman"] = "stickman"
    proportions: Dict[str, float] = Field(default_factory=dict)
    style: CharacterStyle = Field(default_factory=CharacterStyle)
    strength: float = Field(45000.0, gt=0)  # max sustained hand force (push / lift / lever), in physics force units

    @field_validator("proportions")
    @classmethod
    def _props(cls, v: Dict[str, float]) -> Dict[str, float]:
        import dataclasses
        from ..rig.stickman import Proportions
        known = {f.name for f in dataclasses.fields(Proportions)}
        bad = sorted(set(v) - known)
        if bad:
            raise ValueError(f"unknown proportions {bad}; allowed: {sorted(known)} (segment lengths, a character is ~175 tall)")
        for k, x in v.items():
            if not 1.0 <= float(x) <= 120.0:
                raise ValueError(f"proportions.{k}={x} is outside 1-120 (a segment length)")
        return v


# ---------------------------------------------------------------- environment
class RoomSpec(Strict):
    width: float = Field(1200.0, gt=200)
    height: float = Field(1400.0, gt=200)
    depth_back: float = 700.0
    depth_front: float = -120.0
    entry_door: bool = True
    grid_spacing: float = 100.0


class GravityEffect(Strict):
    """What a switch does to gravity. Give EITHER an absolute direction `to` (with `turn` choosing which way the
    vector rotates to get there) OR a signed rotation `rotate_deg` relative to the gravity at activation
    (+ = counter-clockwise in world coordinates, y up). Both are recorded as a signed sweep, so the state can be
    reported relative to the preceding gravity and to the original one."""
    to: Optional[Vec2] = None  # absolute direction (normalised by the runtime)
    rotate_deg: Optional[float] = None  # relative rotation from the gravity at activation
    turn: Literal["shortest", "ccw", "cw"] = "shortest"  # rotation direction for `to`
    magnitude: Optional[float] = None  # defaults to the current magnitude
    delay: float = Field(0.35, ge=0)
    duration: float = Field(0.2, gt=0)

    @model_validator(mode="after")
    def _one(self) -> "GravityEffect":
        if (self.to is None) == (self.rotate_deg is None):
            raise ValueError("gravity effect needs exactly one of 'to' or 'rotate_deg'")
        if self.rotate_deg is not None and not (0 < abs(self.rotate_deg) <= 360):
            raise ValueError("rotate_deg must be non-zero and within +-360")
        return self


class SwitchSpec(Strict):
    """A wall/floor/ceiling-mounted switch console. `x` is the position ALONG its surface (world x for floor and
    ceiling, world y for the walls); `height` is the button's distance from that surface."""
    id: str
    x: float
    height: float = 66.0  # button top above its surface
    surface: Literal["floor", "wall_right", "wall_left", "ceiling"] = "floor"
    effect: GravityEffect


class PropSpec(Strict):
    """A dynamic rigid body. `container` (heavy box with handles), `post` (tall steel support), `bar` (pry bar /
    lever), `toolbox` (small block, a typical fulcrum), `glyph` (a symbol built from its strokes, see scene/glyphs.py:
    `glyph` names it, `size` is its box, `weight` its stroke thickness). `z` is the depth of the prop's centre
    (negative = nearer the camera than the character plane); props with collide_characters=false pass in front of /
    behind characters."""
    id: str
    kind: Literal["crate", "canister", "container", "post", "bar", "toolbox", "glyph"] = "crate"
    glyph: Optional[str] = None  # kind glyph: "+", "-", "x", "÷", "=", "<", ">", "!", "?", "π", "√", "0".."9"
    weight: Optional[float] = Field(None, gt=0)  # glyph stroke thickness (default 15% of the smaller side)
    color: Optional[str] = None  # glyph colour (default: the theme accent)
    position: Vec2
    size: Vec2 = (40.0, 40.0)
    mass: float = Field(8.0, gt=0)
    angle: float = 0.0  # initial rotation (rad, CCW)
    friction: float = Field(0.6, ge=0, le=2)  # sliding (kinetic) friction
    static_friction: Optional[float] = Field(None, ge=0, le=2)  # while at rest (stick-slip: heavy things "break loose")
    collide_characters: bool = True
    solid: bool = True  # false: fixed set dressing (a tool on a wall rack, a fulcrum block) until a character picks it up
    com: Vec2 = (0.0, 0.0)  # centre of mass in the prop's local frame (e.g. a post with a heavy steel cap is top-heavy)
    z: float = 0.0
    depth: float = Field(60.0, gt=0)  # visual extent along the room depth

    @model_validator(mode="after")
    def _glyph(self) -> "PropSpec":
        if self.kind == "glyph":
            from .glyphs import canonical
            if not self.glyph:
                raise ValueError(f"prop {self.id}: kind 'glyph' needs 'glyph' (the symbol)")
            self.glyph = canonical(self.glyph)
        return self


class RopeSpec(Strict):
    """A strap / rope between two props (or a prop and a fixed world point "world:x,y"): slack below `length`."""
    id: str
    a: str  # "prop:<id>"
    a_local: Vec2 = Field((0.0, 0.0), validation_alias=AliasChoices(  # attachment in a's local frame (common spellings accepted)
        "a_local", "local_a", "a_anchor", "anchor_a", "a_point", "point_a", "a_offset", "offset_a"))
    b: str  # "prop:<id>" or "world:x,y"
    b_local: Vec2 = Field((0.0, 0.0), validation_alias=AliasChoices(
        "b_local", "local_b", "b_anchor", "anchor_b", "b_point", "point_b", "b_offset", "offset_b"))
    length: Optional[float] = Field(None, gt=0)  # total length; or give `slack` and the engine computes it
    slack: Optional[float] = Field(None, ge=0)  # extra length beyond the initial distance between the two ends
    break_force: Optional[float] = Field(None, gt=0)  # the strap snaps when its tension exceeds this (force units)
    color: str = "#ffc21a"

    @model_validator(mode="after")
    def _len(self) -> "RopeSpec":
        if self.length is None and self.slack is None:
            raise ValueError(f"rope {self.id}: give 'length' or 'slack'")
        return self


class ExitSpec(Strict):
    """An exit door set into a room surface; `s` is its centre along that surface (world x for floor/ceiling, world y
    for the walls). State machine: sealed -> unlocking (seal bars retract after the `unlock_on` event) -> unlocked
    -> opening (when a character comes within `open_radius`) -> open -> exited (a character crossed its plane)."""
    id: str
    surface: Literal["floor", "wall_right", "wall_left", "ceiling"] = "wall_right"
    s: float
    width: float = Field(170.0, gt=20)
    sealed: bool = True
    unlock_on: Optional[str] = None  # "switch:<id>" (unlocks when that switch's gravity change settles)
    open_radius: float = Field(260.0, gt=0)


class ObstacleSpec(Strict):
    """Fixed structure spanning the room's depth. `beam`: a solid static collider (box cross-section `size`).
    `bar`: a thin grab rail (radius size[0]/2); it is a grip anchor for grab_swing, not a collider.
    `platform`: a solid box whose top can be stood on (walk off its end and you fall). `glyph`: a fixed symbol
    (scene/glyphs.py) built from its strokes; its near-horizontal strokes can be stood on. Characters cannot walk
    through a structure: they `vault` over it, `climb` onto it or `jump_to` onto it."""
    id: str
    kind: Literal["beam", "bar", "platform", "glyph"] = "beam"
    center: Vec2
    size: Vec2 = (30.0, 120.0)
    glyph: Optional[str] = None
    weight: Optional[float] = Field(None, gt=0)  # glyph stroke thickness
    color: Optional[str] = None

    @model_validator(mode="after")
    def _glyph(self) -> "ObstacleSpec":
        if self.kind == "glyph":
            from .glyphs import canonical
            if not self.glyph:
                raise ValueError(f"obstacle {self.id}: kind 'glyph' needs 'glyph' (the symbol)")
            self.glyph = canonical(self.glyph)
        return self


class ThemeSpec(Strict):
    """Art direction of an environment (renderer colours). Defaults reproduce the original lab look."""
    accent: str = "#46ecff"  # grid lines, console trims, rail brackets
    alert: str = "#ff323e"  # warnings, sealed lamps, gravity-shift flash
    back: str = "#15181e"
    floor: str = "#0a0c0f"
    side: str = "#111419"
    ceiling: str = "#08090b"
    background: str = "#050608"
    dust: str = "#bef5ff"


class EnvironmentSpec(Strict):
    id: str
    room: RoomSpec = Field(default_factory=RoomSpec)
    theme: ThemeSpec = Field(default_factory=ThemeSpec)
    gravity: Vec2 = (0.0, -1568.0)
    switches: List[SwitchSpec] = Field(default_factory=list)
    props: List[PropSpec] = Field(default_factory=list)
    exits: List[ExitSpec] = Field(default_factory=list)
    obstacles: List[ObstacleSpec] = Field(default_factory=list)
    ropes: List[RopeSpec] = Field(default_factory=list)
    dust: int = Field(160, ge=0, le=2000)  # ambient particles that visualise the gravity field

    @model_validator(mode="after")
    def _rope_lengths(self) -> "EnvironmentSpec":
        """Resolve `slack` into a length from the initial geometry (the planner states intent, not distances)."""
        import math
        props = {p.id: p for p in self.props}
        for rp in self.ropes:
            if rp.slack is None:
                continue
            ends = []
            for ref, loc in ((rp.a, rp.a_local), (rp.b, rp.b_local)):
                k, _, v = ref.partition(":")
                if k == "prop" and v in props:
                    pp = props[v]
                    ca, sa = math.cos(pp.angle), math.sin(pp.angle)
                    ends.append((pp.position[0] + loc[0] * ca - loc[1] * sa, pp.position[1] + loc[0] * sa + loc[1] * ca))
                elif k == "world":
                    try:
                        ends.append(tuple(float(c) for c in v.split(",")))
                    except ValueError:
                        pass
            if len(ends) == 2:
                rp.length = math.dist(*ends) + rp.slack
            elif rp.length is None:
                raise ValueError(f"rope {rp.id}: cannot compute its length from slack (unknown end)")
        return self


# ---------------------------------------------------------------- actions (character directives)
ActionType = Literal["idle", "walk_to", "run_to", "turn", "press", "jump", "look_around", "wait_grounded", "look_at", "notice", "point",
                     "duck_slide", "jump_to", "grab_swing", "reach_exit",
                     # physical interaction (Rescue milestone)
                     "push", "lift", "use_lever", "struggle", "crawl_out", "get_up", "offer_hand", "gesture", "wait_for",
                     # combat (Milestone 1)
                     "strike", "guard", "dodge",
                     # acrobatics and symbols (Milestone 2)
                     "roll", "vault", "climb", "wall_kick", "pick_up", "throw"]
StrikeMove = Literal["jab", "cross", "hook", "uppercut", "front_kick", "side_kick", "roundhouse", "sweep", "flying_kick",
                     "swing_weapon"]


class ActionSpec(Strict):
    type: ActionType
    character: str
    target_x: Optional[float] = None  # walk_to / run_to (floor coordinate along the current support surface)
    speed: Optional[float] = None
    duration: Optional[float] = None
    switch: Optional[str] = None
    face: Optional[int] = None  # turn: +1 / -1
    height: Optional[float] = None  # jump apex height
    target: Optional[str] = None  # look_at / notice / point / gaze while walking: "switch:<id>", "exit:<id>", "point:x,y"
    style: Literal["normal", "cautious"] = "normal"  # walk_to / run_to movement style
    hesitate: bool = False  # press: reach, hesitate, pull back, then commit
    release_deg: float = Field(35.0, ge=0, le=89)  # grab_swing: release when the swing passes this angle (from hanging)
    swings: int = Field(1, ge=1, le=4)  # grab_swing: release on this forward swing
    effort: float = Field(1.0, gt=0, le=1.6)  # push / lift / use_lever: fraction of the character's strength used
    tool: Optional[str] = None  # use_lever: "prop:<bar id>"
    fulcrum: Optional[str] = None  # use_lever: "prop:<fulcrum id>"
    until: Optional[str] = None  # use_lever / struggle / wait_for: "event:<type>" or "event:<type>@<character>"
    gesture: Optional[Literal["fist_bump", "shoulder_pat", "wave"]] = None
    distance: Optional[float] = None  # crawl_out: how far to crawl; gesture: the gap between the two characters; roll: how far;
    # strike: the distance (pelvis to pelvis) to engage from (default 0.9 x the move's reach)
    emotion: Optional[str] = None  # acting colour for clips (see motion/library.py EMOTIONS)
    move: Optional[StrikeMove] = None  # strike: which technique
    power: float = Field(1.0, gt=0, le=2.0)  # strike: how hard (with the move's own weight it picks the reaction)
    reaction: Optional[Literal["auto", "flinch", "stagger", "knockdown"]] = None  # strike: force the target's reaction
    dodge: Literal["back", "duck"] = "back"  # dodge: step back out of reach, or duck under a high strike
    onto: Optional[str] = None  # jump_to: land on this structure's top ("obstacle:<id>"); default: the floor (from a top)
    flip: Optional[Literal["front", "back"]] = None  # jump_to / wall_kick: a somersault in the air
    lane: Optional[float] = Field(None, ge=-80, le=80)  # move to this depth lane during the action (negative = nearer the camera)
    note: str = ""

    @model_validator(mode="after")
    def _check(self) -> "ActionSpec":
        need = { "press": ["switch"], "turn": ["face"], "jump": ["height"],
                "look_at": ["target"], "notice": ["target"], "point": ["target"], "duck_slide": ["target_x"],
                "jump_to": ["target_x", "height"], "grab_swing": ["target"], "reach_exit": ["target"],
                "push": ["target"], "lift": ["target"], "use_lever": ["target", "tool", "fulcrum"], "offer_hand": ["target"],
                "gesture": ["target", "gesture"], "wait_for": ["until"], "strike": ["target", "move"],
                "vault": ["target"], "climb": ["target"], "wall_kick": ["target_x"], "pick_up": ["target"], "throw": ["target"]}
        if self.type in ("walk_to", "run_to") and self.target_x is None and not (self.target or "").split(":", 1)[0] in ("char", "prop"):
            raise ValueError(f"action '{self.type}' requires 'target_x' (or a 'char:'/'prop:' target)")
        for f in need.get(self.type, []):
            if getattr(self, f) is None:
                raise ValueError(f"action '{self.type}' requires '{f}'")
        if self.type == "turn" and self.face not in (-1, 1):
            raise ValueError("turn.face must be +1 or -1")
        if self.target is not None:
            kind, _, ref = self.target.partition(":")
            if kind not in ("switch", "exit", "point", "bar", "prop", "char", "obstacle") or not ref:
                raise ValueError(f"target must be 'switch:<id>', 'exit:<id>', 'bar:<id>', 'prop:<id>', 'char:<id>', 'obstacle:<id>' "
                                 f"or 'point:x,y' (got {self.target!r})")
        for f in ("tool", "fulcrum"):
            v = getattr(self, f)
            if v is not None and not v.startswith("prop:"):
                raise ValueError(f"{f} must be 'prop:<id>'")
        if self.type == "vault" and not (self.target or "").startswith(("obstacle:", "prop:")):
            raise ValueError("vault.target must be 'obstacle:<id>' or 'prop:<id>'")
        if self.type == "climb" and not (self.target or "").startswith("obstacle:"):
            raise ValueError("climb.target must be 'obstacle:<id>' (a platform or glyph top)")
        if self.onto is not None and not self.onto.startswith("obstacle:"):
            raise ValueError("onto must be 'obstacle:<id>'")
        if self.type == "pick_up" and not (self.target or "").startswith("prop:"):
            raise ValueError("pick_up.target must be 'prop:<id>'")
        if self.type == "throw" and not (self.target or "").startswith(("char:", "point:")):
            raise ValueError("throw.target must be 'char:<id>' or 'point:x,y'")
        if self.type in ("push", "lift", "use_lever") and not (self.target or "").startswith("prop:"):
            raise ValueError(f"{self.type}.target must be 'prop:<id>'")
        if self.type in ("offer_hand", "gesture", "strike") and not (self.target or "").startswith("char:"):
            raise ValueError(f"{self.type}.target must be 'char:<id>'")
        if self.until is not None and not self.until.startswith(("event:", "next:")):
            raise ValueError("until must be 'event:<type>[@<who>]' (any time, also before the action) or "
                             "'next:<type>[@<who>]' (only after the action starts, e.g. the next strike)")
        if self.type == "grab_swing" and not (self.target or "").startswith("bar:"):
            raise ValueError("grab_swing.target must be 'bar:<id>'")
        if self.type == "reach_exit" and not (self.target or "").startswith("exit:"):
            raise ValueError("reach_exit.target must be 'exit:<id>'")
        return self


class CharacterPlacement(Strict):
    character: str
    x: float
    facing: Literal[-1, 1] = 1
    z: float = Field(0.0, ge=-60, le=60)  # drawing depth lane (negative = nearer the camera); does not affect physics


# ---------------------------------------------------------------- cinematography / sound / shots
class CameraSpec(Strict):
    mode: Literal["static", "follow", "track_x", "dolly"] = "follow"
    target: Optional[str] = None  # character id for follow/track
    center: Optional[Vec2] = None  # static / dolly start / track y
    center_end: Optional[Vec2] = None  # dolly end
    view_height: float = Field(600.0, gt=50)
    view_height_end: Optional[float] = None
    offset: Vec2 = (0.0, 40.0)
    lead: float = Field(0.25, ge=0, le=2)  # seconds of velocity look-ahead
    stiffness: float = Field(6.0, gt=0)
    roll: float = 0.0  # degrees (fixed mode / start of an eased roll)
    roll_end: Optional[float] = None  # eased roll transition over the shot
    roll_ease: Literal["in_out", "sine", "linear"] = "in_out"  # easing of roll -> roll_end
    roll_mode: Literal["fixed", "align_gravity"] = "fixed"  # align_gravity: screen-down follows the gravity vector
    focus: Literal["body", "upper", "head"] = "body"  # framing focus for follow cameras (close-ups use head/upper)
    shake: float = Field(0.0, ge=0, le=3)  # event-driven camera shake amount (impacts, pulses)
    roll_rate: float = Field(110.0, gt=0, le=360)  # max camera roll speed (deg/s) for align_gravity shots
    keep_in_frame: bool = True
    include: List[str] = Field(default_factory=list)  # world objects kept in frame with the subject ("bar:rail", "exit:door1", ...)
    include_margin: float = Field(45.0, ge=0)  # world units around each included object
    min_subject_frac: Optional[float] = None  # composition: subject height / frame height (default by shot kind)


class SoundCue(Strict):
    on_event: str  # engine event type this cue is bound to (sync is by event, never by guessed time)
    sound: str
    gain: float = Field(1.0, ge=0, le=4)


class ShotSpec(Strict):
    id: str
    start: float = Field(ge=0)
    end: float
    kind: Literal["establishing", "wide", "medium", "close", "insert", "tracking"] = "medium"
    description: str = ""
    camera: CameraSpec = Field(default_factory=CameraSpec)
    character_states: Dict[str, str] = Field(default_factory=dict)  # expected state at shot start (documentation + QA hint)
    action_objectives: List[str] = Field(default_factory=list)
    object_interactions: List[str] = Field(default_factory=list)
    environment_state: Dict[str, str] = Field(default_factory=dict)
    physics_requirements: List[str] = Field(default_factory=list)
    sound_cues: List[SoundCue] = Field(default_factory=list)
    exit_conditions: List[str] = Field(default_factory=list)  # e.g. "event:press_contact", "grounded_on:wall_right"
    fade_out: float = Field(0.0, ge=0.0, le=5.0)  # seconds of fade to black at the end of the shot
    # event-timed cut: the shot starts when this event happens in the simulation (+ cut_offset seconds); the engine
    # rewrites start/end from the simulated times, so planners do not have to guess when physics events occur
    cut_on: Optional[str] = None  # "event:<type>" or "event:<type>@<who>"
    cut_offset: float = Field(0.0, ge=-3.0, le=3.0)

    @model_validator(mode="after")
    def _order(self) -> "ShotSpec":
        if self.end <= self.start:
            raise ValueError(f"shot {self.id}: end must be after start")
        if self.cut_on is not None and not self.cut_on.startswith("event:"):
            raise ValueError(f"shot {self.id}: cut_on must be 'event:<type>' or 'event:<type>@<who>'")
        return self


class SlowMoSpec(Strict):
    """Slow motion around a beat: story time runs at `rate` of film time from `before` s before the event to `after` s
    after it, eased in and out over `ramp` s."""
    at: str  # an event, goal syntax: "flip@kai", "knockdown@rho", "event:hit@kai[move=throw]"
    before: float = Field(0.15, ge=0, le=3)
    after: float = Field(0.45, ge=0, le=5)
    rate: float = Field(0.35, ge=0.1, le=1)
    ramp: float = Field(0.12, ge=0, le=1)


class TimeFxSpec(Strict):
    """Film-time effects (Milestone 3). The simulation is untouched; the film samples it through a time warp."""
    hit_stop: bool = True  # at each blow, the impact frame holds for a few film frames
    hit_stop_frames: int = Field(3, ge=1, le=8)  # frames for a blow of power 1 (scaled by power; blocks get half)
    hit_stop_max: int = Field(6, ge=1, le=12)
    hit_stop_events: List[str] = Field(default_factory=lambda: ["hit", "block_hit", "prop_hit"])
    slowmo: List[SlowMoSpec] = Field(default_factory=list)
    screen_fx: bool = True  # impact flash, chromatic split in the hold, speed lines in slow motion, vignette pulse
    smears: bool = True  # motion smears on fast limbs and props
    punch_in: bool = True  # camera punch-in on heavy blows and a slow push-in during slow motion


class SceneSpec(Strict):
    id: str
    title: str = ""
    environment: str
    duration: float = Field(gt=0, le=600)
    placements: List[CharacterPlacement]
    actions: List[ActionSpec] = Field(default_factory=list)
    shots: List[ShotSpec]
    # the story beats that must happen, in order, e.g. ["push_lost@milo", "pinned@milo[by=post]", "freed@milo"];
    # the dry run checks them and the setup solver tunes the physical setup until they happen
    goals: List[str] = Field(default_factory=list)
    time_fx: Optional[TimeFxSpec] = None  # hit-stop, slow motion, smears and screen effects (Milestone 3)

    @model_validator(mode="after")
    def _shots(self) -> "SceneSpec":
        shots = sorted(self.shots, key=lambda s: s.start)
        if not shots:
            raise ValueError("scene needs at least one shot")
        if abs(shots[0].start) > 1e-6:
            raise ValueError("first shot must start at 0")
        for a, b in zip(shots, shots[1:]):
            if abs(a.end - b.start) > 1e-6:
                raise ValueError(f"shots {a.id} and {b.id} are not contiguous")
        if abs(shots[-1].end - self.duration) > 1e-6:
            raise ValueError("last shot must end at scene duration")
        return self


class ProjectSpec(Strict):
    schema_version: str = SCHEMA_VERSION
    id: str
    title: str
    fps: Literal[24, 30] = 24
    width: int = Field(1920, ge=320, le=3840)
    height: int = Field(1080, ge=180, le=2160)
    seed: int = 7
    characters: List[CharacterSpec]
    environments: List[EnvironmentSpec]
    scenes: List[SceneSpec]

    @field_validator("schema_version")
    @classmethod
    def _ver(cls, v: str) -> str:
        if v != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version {v} (engine supports {SCHEMA_VERSION})")
        return v

    @model_validator(mode="after")
    def _refs(self) -> "ProjectSpec":
        chars = {c.id for c in self.characters}
        envs = {e.id: e for e in self.environments}
        if len(chars) != len(self.characters):
            raise ValueError("duplicate character ids")
        for sc in self.scenes:
            if sc.environment not in envs:
                raise ValueError(f"scene {sc.id}: unknown environment {sc.environment}")
            switches = {s.id for s in envs[sc.environment].switches}
            for pl in sc.placements:
                if pl.character not in chars:
                    raise ValueError(f"scene {sc.id}: unknown character {pl.character}")
            placed = {pl.character for pl in sc.placements}
            exits = {x.id for x in envs[sc.environment].exits}
            bars = {o.id for o in envs[sc.environment].obstacles if o.kind == "bar"}
            props = {p.id for p in envs[sc.environment].props}
            for r in envs[sc.environment].ropes:
                for end in (r.a, r.b):
                    k, _, ref = end.partition(":")
                    if not ((k == "prop" and ref in props) or (k == "world" and end == r.b)):
                        raise ValueError(f"rope {r.id}: end {end!r} must be 'prop:<id>' (or 'world:x,y' for b)")
            for ex in envs[sc.environment].exits:
                if ex.unlock_on and (not ex.unlock_on.startswith("switch:") or ex.unlock_on.split(":", 1)[1] not in switches):
                    raise ValueError(f"exit {ex.id}: unlock_on must be 'switch:<id>' of a known switch")
            for a in sc.actions:
                if a.character not in placed:
                    raise ValueError(f"scene {sc.id}: action for unplaced character {a.character}")
                if a.type in ("press", "jump_to") and a.switch is not None and a.switch not in switches:
                    raise ValueError(f"scene {sc.id}: unknown switch {a.switch}")
                for ref_s in (a.target, a.tool, a.fulcrum):
                    if not ref_s:
                        continue
                    kind, _, ref = ref_s.partition(":")
                    if ((kind == "switch" and ref not in switches) or (kind == "exit" and ref not in exits) or (kind == "bar" and ref not in bars)
                            or (kind == "prop" and ref not in props) or (kind == "char" and ref not in placed)):
                        raise ValueError(f"scene {sc.id}: unknown target {ref_s}")
            whos = placed | props | {r.id for r in envs[sc.environment].ropes}
            for g in sc.goals:
                from .goals import parse_goal
                from .goals import check_event
                try:
                    etype, who, _ = parse_goal(g)
                    check_event(etype, f"goal {g!r}")
                except ValueError as e:
                    raise ValueError(f"scene {sc.id}: {e}")
                if who and who not in whos:
                    raise ValueError(f"scene {sc.id}: goal {g!r} names unknown {who!r} (a character, prop or rope id)")
            for sh in sc.shots:
                if sh.cut_on:
                    from .goals import check_event, parse_goal as _pg
                    check_event(_pg(sh.cut_on)[0], f"shot {sh.id} cut_on")
                if sh.camera.target and sh.camera.target not in placed:
                    raise ValueError(f"shot {sh.id}: camera target {sh.camera.target} not in scene")
        return self

    def scene(self, scene_id: str) -> SceneSpec:
        for s in self.scenes:
            if s.id == scene_id:
                return s
        raise KeyError(scene_id)

    def environment(self, env_id: str) -> EnvironmentSpec:
        for e in self.environments:
            if e.id == env_id:
                return e
        raise KeyError(env_id)

    def character(self, cid: str) -> CharacterSpec:
        for c in self.characters:
            if c.id == cid:
                return c
        raise KeyError(cid)


def json_schema() -> dict:
    return ProjectSpec.model_json_schema()
