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
    to: Vec2  # direction (normalised by the runtime)
    magnitude: Optional[float] = None  # defaults to the current magnitude
    delay: float = Field(0.35, ge=0)
    duration: float = Field(0.2, gt=0)


class SwitchSpec(Strict):
    id: str
    x: float
    height: float = 66.0  # button top above the floor
    effect: GravityEffect


class PropSpec(Strict):
    id: str
    kind: Literal["crate", "canister"] = "crate"
    position: Vec2
    size: Vec2 = (40.0, 40.0)
    mass: float = Field(8.0, gt=0)


class EnvironmentSpec(Strict):
    id: str
    room: RoomSpec = Field(default_factory=RoomSpec)
    gravity: Vec2 = (0.0, -1568.0)
    switches: List[SwitchSpec] = Field(default_factory=list)
    props: List[PropSpec] = Field(default_factory=list)


# ---------------------------------------------------------------- actions (character directives)
ActionType = Literal["idle", "walk_to", "run_to", "turn", "press", "jump", "look_around", "wait_grounded"]


class ActionSpec(Strict):
    type: ActionType
    character: str
    target_x: Optional[float] = None  # walk_to / run_to (floor coordinate along the current support surface)
    speed: Optional[float] = None
    duration: Optional[float] = None
    switch: Optional[str] = None
    face: Optional[int] = None  # turn: +1 / -1
    height: Optional[float] = None  # jump apex height
    note: str = ""

    @model_validator(mode="after")
    def _check(self) -> "ActionSpec":
        need = {"walk_to": ["target_x"], "run_to": ["target_x"], "press": ["switch"], "turn": ["face"], "jump": ["height"]}
        for f in need.get(self.type, []):
            if getattr(self, f) is None:
                raise ValueError(f"action '{self.type}' requires '{f}'")
        if self.type == "turn" and self.face not in (-1, 1):
            raise ValueError("turn.face must be +1 or -1")
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
    roll: float = 0.0  # degrees
    keep_in_frame: bool = True


class SoundCue(Strict):
    on_event: str  # engine event type this cue is bound to (sync is by event, never by guessed time)
    sound: str
    gain: float = Field(1.0, ge=0, le=4)


class ShotSpec(Strict):
    id: str
    start: float = Field(ge=0)
    end: float
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
            for a in sc.actions:
                if a.character not in placed:
                    raise ValueError(f"scene {sc.id}: action for unplaced character {a.character}")
                if a.type == "press" and a.switch not in switches:
                    raise ValueError(f"scene {sc.id}: unknown switch {a.switch}")
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
