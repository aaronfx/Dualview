"""APEX scene schema v0.1 — the machine-readable contract between the AI Story Director, the editor,
the runtime and the renderer. Every field is validated; see docs/SCENE_SCHEMA.md.
"""
from __future__ import annotations

from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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
    limb_width: float = Field(5.2, gt=0, le=20)
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
    id: str
    kind: Literal["crate", "canister"] = "crate"
    position: Vec2
    size: Vec2 = (40.0, 40.0)
    mass: float = Field(8.0, gt=0)


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
    `bar`: a thin grab rail (radius size[0]/2); it is a grip anchor for grab_swing, not a collider."""
    id: str
    kind: Literal["beam", "bar"] = "beam"
    center: Vec2
    size: Vec2 = (30.0, 120.0)


class EnvironmentSpec(Strict):
    id: str
    room: RoomSpec = Field(default_factory=RoomSpec)
    gravity: Vec2 = (0.0, -1568.0)
    switches: List[SwitchSpec] = Field(default_factory=list)
    props: List[PropSpec] = Field(default_factory=list)
    exits: List[ExitSpec] = Field(default_factory=list)
    obstacles: List[ObstacleSpec] = Field(default_factory=list)
    dust: int = Field(160, ge=0, le=2000)  # ambient particles that visualise the gravity field


# ---------------------------------------------------------------- actions (character directives)
ActionType = Literal["idle", "walk_to", "run_to", "turn", "press", "jump", "look_around", "wait_grounded", "look_at", "notice", "point",
                     "duck_slide", "jump_to", "grab_swing", "reach_exit"]


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
    note: str = ""

    @model_validator(mode="after")
    def _check(self) -> "ActionSpec":
        need = {"walk_to": ["target_x"], "run_to": ["target_x"], "press": ["switch"], "turn": ["face"], "jump": ["height"],
                "look_at": ["target"], "notice": ["target"], "point": ["target"], "duck_slide": ["target_x"],
                "jump_to": ["target_x", "height"], "grab_swing": ["target"], "reach_exit": ["target"]}
        for f in need.get(self.type, []):
            if getattr(self, f) is None:
                raise ValueError(f"action '{self.type}' requires '{f}'")
        if self.type == "turn" and self.face not in (-1, 1):
            raise ValueError("turn.face must be +1 or -1")
        if self.target is not None:
            kind, _, ref = self.target.partition(":")
            if kind not in ("switch", "exit", "point", "bar") or not ref:
                raise ValueError(f"target must be 'switch:<id>', 'exit:<id>', 'bar:<id>' or 'point:x,y' (got {self.target!r})")
        if self.type == "grab_swing" and not (self.target or "").startswith("bar:"):
            raise ValueError("grab_swing.target must be 'bar:<id>'")
        if self.type == "reach_exit" and not (self.target or "").startswith("exit:"):
            raise ValueError("reach_exit.target must be 'exit:<id>'")
        return self


class CharacterPlacement(Strict):
    character: str
    x: float
    facing: Literal[-1, 1] = 1


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
    roll_mode: Literal["fixed", "align_gravity"] = "fixed"  # align_gravity: screen-down follows the gravity vector
    focus: Literal["body", "upper", "head"] = "body"  # framing focus for follow cameras (close-ups use head/upper)
    shake: float = Field(0.0, ge=0, le=3)  # event-driven camera shake amount (impacts, pulses)
    roll_rate: float = Field(110.0, gt=0, le=360)  # max camera roll speed (deg/s) for align_gravity shots
    keep_in_frame: bool = True


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

    @model_validator(mode="after")
    def _order(self) -> "ShotSpec":
        if self.end <= self.start:
            raise ValueError(f"shot {self.id}: end must be after start")
        return self


class SceneSpec(Strict):
    id: str
    title: str = ""
    environment: str
    duration: float = Field(gt=0, le=600)
    placements: List[CharacterPlacement]
    actions: List[ActionSpec] = Field(default_factory=list)
    shots: List[ShotSpec]

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
            for ex in envs[sc.environment].exits:
                if ex.unlock_on and (not ex.unlock_on.startswith("switch:") or ex.unlock_on.split(":", 1)[1] not in switches):
                    raise ValueError(f"exit {ex.id}: unlock_on must be 'switch:<id>' of a known switch")
            for a in sc.actions:
                if a.character not in placed:
                    raise ValueError(f"scene {sc.id}: action for unplaced character {a.character}")
                if a.type in ("press", "jump_to") and a.switch is not None and a.switch not in switches:
                    raise ValueError(f"scene {sc.id}: unknown switch {a.switch}")
                if a.target:
                    kind, _, ref = a.target.partition(":")
                    if (kind == "switch" and ref not in switches) or (kind == "exit" and ref not in exits) or (kind == "bar" and ref not in bars):
                        raise ValueError(f"scene {sc.id}: unknown target {a.target}")
            for sh in sc.shots:
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
