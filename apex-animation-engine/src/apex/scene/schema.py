"""APEX scene schema v0.1 — the machine-readable contract between the AI Story Director, the editor,
the runtime and the renderer. Every field is validated; see docs/SCENE_SCHEMA.md.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Tuple

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
    grid_alpha: float = Field(1.0, ge=0, le=1)  # strength of the neon grid (set dressing reads better over a quieter grid)
    style: Literal["box", "open"] = "box"  # "open": no cutaway room is drawn; the environment's backdrop is the world
    # (the room's bounds still hold physically: its walls are the edges of the playable area)
    void_below: Optional[float] = None  # Milestone 6: drawn as a bottomless void below this height (the floor is still
    # there physically, far below a level built on platforms; a scene's `fail` zone catches a fall before it is reached)


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


class BreakSpec(Strict):
    """A breakable prop (Milestone 5). It breaks when a single contact impulse on it reaches `impulse` (mass x velocity
    units, e.g. a 4 kg symbol landing at 500 u/s gives about 2000-3500). A glyph breaks into its strokes (long
    strokes into runs of a few segments); a box into a `grid` x `grid` of blocks. The pieces carry on with the
    prop's own motion (velocity and spin at each piece's centre of mass), plus a `scatter` (u/s) that pushes them
    apart without changing the total momentum."""
    impulse: float = Field(gt=0)
    scatter: float = Field(60.0, ge=0, le=600)
    grid: int = Field(2, ge=2, le=4)


class MorphSpec(Strict):
    """A glyph prop turning into another glyph (Milestone 5). It starts at time `at` or on an event `on` (goal syntax,
    e.g. "collect@iko"), draws as a blend of the two shapes over `duration`, and then becomes the new shape physically
    (same mass; its centre of mass, velocity and angular momentum are kept). The change waits while the new shape
    would overlap a character or a structure."""
    to: str
    at: Optional[float] = Field(None, ge=0)
    on: Optional[str] = None
    duration: float = Field(0.5, gt=0, le=5)
    delay: float = Field(0.0, ge=0, le=10)  # with `on`: start this long after the event

    @model_validator(mode="after")
    def _one(self) -> "MorphSpec":
        from .glyphs import canonical
        self.to = canonical(self.to)
        if (self.at is None) == (self.on is None):
            raise ValueError("a morph needs exactly one of 'at' (a time) or 'on' (an event)")
        return self


class TransposeSpec(Strict):
    """A fixed (set-dressing) glyph gliding to a new place along an arc — the reusable "cross the equals sign" move for
    the Math world. It starts at time `at` or on an event `on` (e.g. a character gesture), travels to `to` over
    `duration` seconds rising `arc` units at the apex, and rests there. A sign flip (`+`<->`-`, `x`<->`/`) is authored
    separately as a `morph` on the same trigger with `delay = duration/2`, so the symbol inverts as it crosses."""
    to: Vec2
    at: Optional[float] = Field(None, ge=0)
    on: Optional[str] = None
    duration: float = Field(0.5, gt=0, le=4)
    delay: float = Field(0.0, ge=0, le=10)   # with `on`: start this long after the event
    arc: float = Field(90.0, ge=0, le=600)

    @model_validator(mode="after")
    def _one(self) -> "TransposeSpec":
        if (self.at is None) == (self.on is None):
            raise ValueError("a transpose needs exactly one of 'at' (a time) or 'on' (an event)")
        return self


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
    energy: bool = False  # a glowing energy core: drawn with a pulsing light around it
    material: Optional[Literal["glass"]] = None  # glass: drawn see-through with bright edges (its pieces too)
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
    breakable: Optional[BreakSpec] = None  # Milestone 5: breaks into pieces under a hard enough blow
    fragment_of: Optional[str] = None  # a piece of a breakable prop (made by the engine; exists once it breaks)
    local: Vec2 = (0.0, 0.0)  # a box piece's centre in its parent's frame
    morphs: List[MorphSpec] = Field(default_factory=list)  # Milestone 5: shape changes (glyph props)
    transposes: List["TransposeSpec"] = Field(default_factory=list)  # Math world: glide a fixed glyph across the equation
    creature_of: Optional[str] = None  # a part of a composite creature (made by the engine)

    @model_validator(mode="after")
    def _glyph(self) -> "PropSpec":
        if self.kind == "glyph":
            from .glyphs import canonical
            if not self.glyph:
                raise ValueError(f"prop {self.id}: kind 'glyph' needs 'glyph' (the symbol)")
            self.glyph = canonical(self.glyph)
        if self.morphs and (self.kind != "glyph" or self.breakable is not None):
            raise ValueError(f"prop {self.id}: only an unbreakable glyph prop can morph")
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
    unlock_on: Optional[str] = None  # "switch:<id>" (when that switch's gravity change settles) or "together:<id>,<id>,..."
    # (Milestone 6: only when all those characters stand within `open_radius` of it at once)
    open_radius: float = Field(260.0, gt=0)


class CollapseSpec(Strict):
    """A structure that gives way (Milestone 6): a platform that breaks into `pieces` planks which fall. It goes when
    the character `under` has stood on it for `after` seconds (weight), at time `at`, or on an event `on`, whichever
    comes first. Whoever stands on it then loses their footing; from that moment it is not a solid or a support for
    anyone."""
    under: Optional[str] = None
    after: float = Field(0.5, ge=0, le=30)
    at: Optional[float] = Field(None, ge=0)
    on: Optional[str] = None
    pieces: int = Field(4, ge=1, le=16)
    color: Optional[str] = None

    @model_validator(mode="after")
    def _one(self) -> "CollapseSpec":
        if all(x is None for x in (self.under, self.at, self.on)):
            raise ValueError("a collapse needs at least one of 'under', 'at' or 'on'")
        return self


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
    collapse: Optional[CollapseSpec] = None  # Milestone 6: a platform that gives way
    style: Optional[Literal["slab", "roof", "rock", "girder", "bridge", "pillar", "pedestal"]] = None  # how it is drawn: a roof is the
    # top of a building (its facade is drawn down into the depths), rock a cliff, a bridge planks on ropes

    @model_validator(mode="after")
    def _glyph(self) -> "ObstacleSpec":
        if self.kind == "glyph":
            from .glyphs import canonical
            if not self.glyph:
                raise ValueError(f"obstacle {self.id}: kind 'glyph' needs 'glyph' (the symbol)")
            self.glyph = canonical(self.glyph)
        return self


class OrbSpec(Strict):
    """An arcade orb (Milestone 4). It changes the physical state of a character whose body touches it:
    `jump`: in the air, the body's velocity along "up" is set to that of a jump of apex `power` (a mid-air jump);
    `boost`: in the air, `power` u/s is added along the direction of travel; `pad`: on a surface, stepping on it launches
    the body to apex height `power` (keeping its run speed); `collect`: a pick-up (an event; it disappears).
    Jump, boost and pad orbs re-arm once the body has left them; a collect orb is taken once."""
    id: str
    kind: Literal["jump", "boost", "pad", "collect"] = "jump"
    center: Vec2
    radius: float = Field(20.0, gt=2, le=120)
    power: Optional[float] = Field(None, gt=0)  # jump/pad: apex height (default 130/170); boost: speed added (default 320)
    flip: Optional[Literal["front", "back"]] = None  # jump orb: the mid-air jump is a somersault
    once: bool = False  # spent after one use (it bursts): a jump, boost or pad that does not re-arm
    color: Optional[str] = None


class PortalSpec(Strict):
    """One end of a portal pair (Milestone 4). A body (character or prop) whose centre crosses the portal's plane from
    its open side, within its height, comes out of the linked portal with the same speed: position and velocity are
    rotated from this portal's frame into the other's (momentum preserved). `angle` is the direction the portal opens
    toward, in degrees (0 = facing +x, 180 = facing -x, 90 = facing up)."""
    id: str
    center: Vec2
    link: str  # the other end's id
    angle: float = 0.0
    height: float = Field(150.0, gt=20)
    color: Optional[str] = None


class LevelSpec(Strict):
    """A level drawn as a character grid (Milestone 4), expanded into platforms, orbs, portals and markers.
    Rows run top to bottom; the bottom row sits on the floor; `origin` is the floor point under the left edge of column 0.
    Legend: `#` solid block (runs are merged into platforms), `=` a thin ledge on the top of its cell,
    `o` jump orb, `b` boost orb, `^` jump pad (on the floor or a block), `*` collectible,
    a capital letter and the same lower-case letter: a linked portal pair (opening toward the free side),
    a digit: a marker (`placements[].at`), `.` or space: empty. `legend` overrides an entry's fields by symbol,
    e.g. {"o": {"power": 160}, "A": {"angle": 180}}."""
    rows: List[str]
    cell: float = Field(60.0, gt=10)
    origin: Vec2 = (-600.0, 0.0)
    legend: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    markers: Dict[str, Vec2] = Field(default_factory=dict)  # filled by the expansion: digit -> world point (cell bottom centre)
    expanded: bool = False  # set once the grid has been expanded into the environment (re-validation does not repeat it)


class DecorSpec(Strict):
    """Set dressing (Milestone 5): drawn, never collided with. On the back wall unless `z` is given.
    `window` (a night skyline outside), `panel` (a wall panel with status lights), `screen` (a monitor with a live trace
    and a `text` title), `pipe` (from (x, y) to (x2, y2)), `lamp` (a ceiling lamp at x with its light cone), `bench`
    (a lab bench, front of the wall at depth z), `shelf` (a wall shelf with glassware)."""
    kind: Literal["window", "panel", "screen", "pipe", "lamp", "bench", "shelf"]
    x: float
    y: float = 0.0
    w: float = 120.0
    h: float = 80.0
    x2: Optional[float] = None
    y2: Optional[float] = None
    z: Optional[float] = None
    color: Optional[str] = None
    text: str = ""
    seed: int = 0


class CreaturePart(Strict):
    """A limb or feature of a composite creature: a glyph hung on the body at `at` (body frame) by its `pivot` point
    (its own frame; default: the top of a leg or arm, its centre otherwise)."""
    glyph: str
    size: Vec2 = (30.0, 40.0)
    at: Vec2 = (0.0, 0.0)
    pivot: Optional[Vec2] = None
    role: Literal["leg", "arm", "tail", "head", "eye"] = "leg"
    mass: float = Field(1.0, gt=0)
    weight: Optional[float] = Field(None, gt=0)
    color: Optional[str] = None
    swing: float = Field(0.45, ge=0, le=1.5)  # gait swing of a leg or arm (rad)
    phase: float = 0.0  # gait phase offset (rad); legs on alternate sides use 0 and pi

    @model_validator(mode="after")
    def _g(self) -> "CreaturePart":
        from .glyphs import canonical
        self.glyph = canonical(self.glyph)
        if self.pivot is None:
            self.pivot = (0.0, self.size[1] / 2) if self.role in ("leg", "arm") else (0.0, 0.0)
        return self


class CreatureSpec(Strict):
    """A composite creature (Milestone 5): a body glyph with glyph limbs on pivot joints. Each part is a physical glyph
    prop (it collides, is drawn and is checked like any prop). The body follows `path` (time, x) with at most
    `max_force` and holds itself up at `height` (the centre's height above the floor) with at most `max_lift`; its legs
    swing in a gait paced by the distance travelled. A contact impulse of `breaks` or more on any part tears the joints:
    the creature falls apart into its parts."""
    id: str
    body: str
    size: Vec2 = (70.0, 50.0)
    position: Vec2
    mass: float = Field(6.0, gt=0)
    weight: Optional[float] = Field(None, gt=0)
    color: Optional[str] = None
    parts: List[CreaturePart] = Field(default_factory=list)
    path: List[Tuple[float, float]] = Field(default_factory=list)  # (time, x) waypoints, linear between them
    height: Optional[float] = None
    stride: float = Field(60.0, gt=5)
    max_force: float = Field(9000.0, gt=0)
    max_lift: float = Field(30000.0, gt=0)
    breaks: Optional[float] = Field(None, gt=0)
    z: float = 0.0
    depth: float = Field(30.0, gt=0)
    morphs: List["MorphSpec"] = Field(default_factory=list)  # shape changes of the body glyph (e.g. once torn apart)

    @model_validator(mode="after")
    def _g(self) -> "CreatureSpec":
        from .glyphs import canonical
        self.body = canonical(self.body)
        if self.height is None:
            self.height = self.position[1]
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


class GlitchSpec(Strict):
    """A corruption front (drawn only): a wall of red static that advances along x from `x0` at `speed` u/s from
    time `start`. Structures it reaches are expected to give way (the builder gives them collapse times)."""
    x0: float
    speed: float = Field(60.0, ge=0)
    start: float = 0.0
    direction: Literal[1, -1] = 1
    stop: Optional[float] = None  # it halts at this x
    color: str = "#ff2a48"


class PowerCue(Strict):
    """The world's lights change (the Director's Cut): from `at` (scene time) the distant city's windows and signs fade
    to `level` over `fade` seconds, flickering on the way. With `origin` (x, y) the change spreads outward from there as
    a wave (`speed` world units a second) and a ring of light pulses out from that point."""
    at: float = Field(..., ge=0)
    level: float = Field(..., ge=0, le=1)
    fade: float = Field(1.2, gt=0)
    origin: Optional[Vec2] = None
    speed: float = Field(5000.0, gt=0)


class BackdropSpec(Strict):
    """The world around an open environment (cinematic upgrade): sky, distant layers drawn at depth (so they move
    with real parallax), weather and fog. Drawn only; nothing in it collides."""
    kind: Literal["city", "canyon", "tower", "void", "summit"]
    seed: int = 1
    sky: Optional[List[str]] = None  # top -> horizon colours (2 or 3); defaults per kind
    sun: Optional[Vec2] = None  # a sun or moon at this (x, y) on the far sky (default per kind; [] none)
    weather: Literal["none", "rain", "embers", "snow", "motes", "data"] = "none"
    weather_amount: float = Field(1.0, ge=0, le=3)
    fog: Optional[str] = None  # haze colour toward the bottom of the frame
    horizon: Optional[float] = None  # world height of the far horizon line (default: below the level)
    lightning: bool = False
    glitch: Optional[GlitchSpec] = None
    city_lights: bool = False  # summit: a distant city far below (its lights follow `power`)
    power: List[PowerCue] = Field(default_factory=list)  # the lights' level over time (starts at `power0`)
    power0: float = Field(1.0, ge=0, le=1)


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
    orbs: List[OrbSpec] = Field(default_factory=list)
    portals: List[PortalSpec] = Field(default_factory=list)
    level: Optional[LevelSpec] = None  # a grid level, expanded into obstacles, orbs, portals and markers
    creatures: List[CreatureSpec] = Field(default_factory=list)  # composite creatures (Milestone 5)
    decor: List[DecorSpec] = Field(default_factory=list)  # set dressing (Milestone 5)
    backdrop: Optional[BackdropSpec] = None  # the world around an open room (cinematic upgrade)

    @model_validator(mode="after")
    def _creatures(self) -> "EnvironmentSpec":
        """Each creature's body and parts become glyph props of their own (`creature_of` ties them together)."""
        have = {p.creature_of for p in self.props if p.creature_of}
        for cr in self.creatures:
            if cr.id in have:
                continue
            bx, by = cr.position
            self.props.append(PropSpec(id=f"{cr.id}.body", kind="glyph", glyph=cr.body, position=(bx, by), size=cr.size, mass=cr.mass,
                                       weight=cr.weight, color=cr.color, z=cr.z, depth=cr.depth, creature_of=cr.id,
                                       morphs=list(cr.morphs)))
            for k, pt in enumerate(cr.parts):
                pos = (bx + pt.at[0] - pt.pivot[0], by + pt.at[1] - pt.pivot[1])
                self.props.append(PropSpec(id=f"{cr.id}.{k}", kind="glyph", glyph=pt.glyph, position=pos, size=pt.size, mass=pt.mass,
                                           weight=pt.weight, color=pt.color or cr.color, z=cr.z, depth=cr.depth, creature_of=cr.id,
                                           friction=0.9))
        return self

    @model_validator(mode="after")
    def _fragments(self) -> "EnvironmentSpec":
        """Each breakable prop gets its pieces as props of their own (inactive until it breaks); so does each platform
        that can collapse (its planks)."""
        import math
        have = {p.fragment_of for p in self.props if p.fragment_of}
        add = []
        for ob in self.obstacles:
            if ob.collapse is None or ob.id in have:
                continue
            if ob.kind != "platform":
                raise ValueError(f"obstacle {ob.id}: only a platform can collapse")
            n = ob.collapse.pieces
            w = ob.size[0] / n
            for k in range(n):
                x = ob.center[0] - ob.size[0] / 2 + (k + 0.5) * w
                add.append(PropSpec(id=f"{ob.id}~{k}", kind="crate", position=(x, ob.center[1]), size=(w - 2.0, ob.size[1]),
                                    mass=max(2.0, 0.004 * w * ob.size[1]), friction=0.7, fragment_of=ob.id, collide_characters=False,
                                    z=0.0, depth=120.0, color=ob.collapse.color or ob.color))
        for p in self.props:
            if p.breakable is None or p.id in have or p.fragment_of:
                continue
            base = p.model_dump(exclude={"breakable", "fragment_of", "local", "id", "static_friction"})
            if p.kind == "glyph":
                from .glyphs import pieces
                pcs = pieces(p.glyph)
                sx, sy = p.size  # lengths at the prop's real size (a non-square glyph stretches its strokes unevenly)
                lens = [sum(math.hypot((b[0] - a[0]) * sx, (b[1] - a[1]) * sy) for a, b in zip(pc, pc[1:])) or 1e-3 for pc in pcs]
                for k, L in enumerate(lens):
                    add.append(PropSpec(**dict(base, id=f"{p.id}~{k}", glyph=f"{p.glyph}#{k}", mass=p.mass * L / sum(lens),
                                               fragment_of=p.id)))
            else:
                g = p.breakable.grid
                w, h = p.size[0] / g, p.size[1] / g
                for i in range(g):
                    for j in range(g):
                        loc = (-p.size[0] / 2 + (i + 0.5) * w, -p.size[1] / 2 + (j + 0.5) * h)
                        small = max(w, h) < 45.0  # debris below knee height is kicked aside, not a wall
                        add.append(PropSpec(**dict(base, id=f"{p.id}~{i * g + j}", size=(w, h), mass=p.mass / (g * g), com=(0.0, 0.0),
                                                   fragment_of=p.id, local=loc,
                                                   collide_characters=False if small else p.collide_characters)))
        self.props.extend(add)
        return self

    @model_validator(mode="after")
    def _level(self) -> "EnvironmentSpec":
        if self.level is not None and not self.level.expanded:
            from .level import expand
            expand(self)
        ids = {p.id for p in self.portals}
        for p in self.portals:
            if p.link not in ids or p.link == p.id:
                raise ValueError(f"portal {p.id}: link {p.link!r} must name another portal")
        return self

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
                     "roll", "vault", "climb", "wall_kick", "pick_up", "throw",
                     # beat sync (Milestone 4)
                     "wait_beat",
                     # acting and rescue (Milestone 6)
                     "act", "catch_ledge", "hang", "pull_up",
                     # the Director's Cut: set a carried prop down on a structure's top or at a point
                     "place"]
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
    gesture: Optional[Literal["fist_bump", "shoulder_pat", "wave", "nudge"]] = None
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
    beats: int = Field(1, ge=1, le=64)  # wait_beat: hold until this many beats from now have started (the next action starts on it)
    clip: Optional[str] = None  # act: full-body clip; run_to/walk_to: upper-body acting overlay while feet keep moving
    notice_while_moving: bool = False  # run_to/walk_to: glance at target during travel; emit causal notice event
    intensity: float = Field(1.0, gt=0, le=2.5)  # act: exaggeration (scales the clip's deviation from neutral)
    tempo: float = Field(1.0, gt=0.2, le=3.0)  # act: playback speed
    tremble: float = Field(0.0, ge=0, le=1.5)  # act: shaking hands, arms and head (fear, exhaustion)
    slip_at: Optional[float] = Field(None, ge=0)  # hang: the near hand slips off this long into the hang (`distance`: the drop)
    # hang with `duration`: after that long the character scrambles up over the edge unaided
    note: str = ""

    @model_validator(mode="after")
    def _check(self) -> "ActionSpec":
        need = { "press": ["switch"], "turn": ["face"], "jump": ["height"],
                "look_at": ["target"], "notice": ["target"], "point": ["target"], "duck_slide": ["target_x"],
                "jump_to": ["target_x", "height"], "grab_swing": ["target"], "reach_exit": ["target"],
                "push": ["target"], "lift": ["target"], "use_lever": ["target", "tool", "fulcrum"], "offer_hand": ["target"],
                "gesture": ["target", "gesture"], "wait_for": ["until"], "strike": ["target", "move"],
                "vault": ["target"], "climb": ["target"], "wall_kick": ["target_x"], "pick_up": ["target"], "throw": ["target"],
                "act": ["clip"], "catch_ledge": ["target"], "pull_up": ["target"], "place": ["target"]}
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
        if self.type == "throw" and not (self.target or "").startswith(("char:", "point:", "prop:")):
            raise ValueError("throw.target must be 'char:<id>', 'prop:<id>' (where it is at the release) or 'point:x,y'")
        if self.type in ("push", "lift", "use_lever") and not (self.target or "").startswith("prop:"):
            raise ValueError(f"{self.type}.target must be 'prop:<id>'")
        if self.notice_while_moving and (self.type not in ("walk_to", "run_to") or self.target is None):
            raise ValueError("notice_while_moving needs a walk_to/run_to with an observation target")
        if self.type == "act" or (self.type in ("walk_to", "run_to") and self.clip is not None):
            from ..motion.library import get_clip
            try:
                get_clip(self.clip)
            except KeyError as e:
                from ..motion.library import list_clips
                raise ValueError(f"act: unknown clip {self.clip!r}; clips: {', '.join(list_clips())}") from e
        if self.type == "catch_ledge" and not (self.target or "").startswith("obstacle:"):
            raise ValueError("catch_ledge.target must be 'obstacle:<id>' (the top whose edge to catch)")
        if self.type == "pull_up" and not (self.target or "").startswith("char:"):
            raise ValueError("pull_up.target must be 'char:<id>' (the character hanging from the edge)")
        if self.type in ("offer_hand", "gesture") and not (self.target or "").startswith("char:"):
            raise ValueError(f"{self.type}.target must be 'char:<id>'")
        if self.type == "strike" and not (self.target or "").startswith(("char:", "prop:")):
            raise ValueError("strike.target must be 'char:<id>' or 'prop:<id>' (a blow at a thing: smash it, kick it away)")
        if self.type == "strike" and self.target.startswith("prop:") and self.move in ("swing_weapon", "flying_kick", "sweep"):
            raise ValueError(f"strike at a prop: '{self.move}' is not supported (use a punch or a standing kick)")
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
    x: float = 0.0
    at: Optional[str] = None  # a level marker (digit): x comes from the level grid
    on: Optional[str] = None  # start standing on this structure's top ("obstacle:<id>"), not on the floor
    facing: Literal[-1, 1] = 1
    z: float = Field(0.0, ge=-60, le=60)  # drawing depth lane (negative = nearer the camera); does not affect physics
    carrying: Optional[str] = None  # starts the scene holding this prop ("prop:<id>"), e.g. a core carried in from a previous scene


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
    bound_to_room: bool = False  # the view never shows past the room's walls (it slides along them instead)
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


class DiagramSpec(Strict):
    """An annotation drawn over the picture from simulation data (Milestone 5), never a hand-written number:
    `velocity`: an arrow showing a body's velocity (length = speed x `scale`), with its speed;
    `trajectory`: the path a body takes over the diagram's time, drawn as it is travelled;
    `label`: text that follows a body; `{speed}`, `{height}`, `{mass}`, `{name}` are filled from the simulation;
    `measure`: a dimension line between `target` and `to` with the distance;
    `impulse`: at each orb hit or break of `target`, an arrow of the velocity change (orb) or the blow (break).
    It shows from `t0` to `t1` (story time), or from the event `on` for `duration` seconds."""
    id: str
    kind: Literal["velocity", "trajectory", "label", "measure", "impulse"]
    target: str
    to: Optional[str] = None
    t0: Optional[float] = Field(None, ge=0)
    t1: Optional[float] = Field(None, ge=0)
    on: Optional[str] = None
    duration: float = Field(1.5, gt=0, le=30)
    text: Optional[str] = None
    scale: float = Field(0.15, gt=0, le=2)
    unit: str = "u"
    color: Optional[str] = None

    @model_validator(mode="after")
    def _when(self) -> "DiagramSpec":
        if (self.t0 is None) == (self.on is None):
            raise ValueError(f"diagram {self.id}: give either t0 (and t1) or on")
        if self.kind == "measure" and not self.to:
            raise ValueError(f"diagram {self.id}: a measure needs 'to'")
        for ref in (self.target, self.to):
            if ref is not None and ref.partition(":")[0] not in ("char", "prop", "point", "creature"):
                raise ValueError(f"diagram {self.id}: targets are 'char:<id>', 'prop:<id>', 'creature:<id>' or 'point:x,y'")
        return self


class FailSpec(Strict):
    """A way to fail (Milestone 6): a character whose body drops below `below` (world y) has failed (`fail` event)."""
    below: float
    characters: List[str] = Field(default_factory=list)  # default: everyone


class HudMessage(Strict):
    text: str
    at: Optional[float] = Field(None, ge=0)
    on: Optional[str] = None  # an event (goal syntax)
    delay: float = Field(0.0, ge=0, le=10)
    duration: float = Field(2.5, gt=0, le=30)
    style: Literal["alert", "info", "success", "title"] = "info"


class HudSpec(Strict):
    """A game-style overlay drawn over the picture (Milestone 6): a retry counter (it ticks down with a flash at each
    `fail`) and messages shown at a time or on an event."""
    retries: Optional[int] = Field(None, ge=0, le=9)
    retries_max: int = Field(3, ge=1, le=9)
    label: str = "RETRIES"
    messages: List[HudMessage] = Field(default_factory=list)


class MusicSpec(Strict):
    """A beat grid in film time (what the audience hears), Milestone 4. Beat k is at `offset + k * 60 / bpm` s.
    `snap_cuts`: each shot boundary within `snap_window` beats of a beat moves onto it. `wait_beat` actions end on
    beats. The soundtrack is rendered on the grid; QA checks that cuts, beat waits and the music's onsets agree."""
    bpm: float = Field(120.0, ge=40, le=240)
    offset: float = Field(0.0, ge=0, le=10)
    beats_per_bar: int = Field(4, ge=2, le=8)
    snap_cuts: bool = True
    snap_window: float = Field(0.5, gt=0, le=0.5)
    gain: float = Field(1.0, ge=0, le=2)


class ScoreCue(Strict):
    """From this moment the score plays `mood` (at a time, or on an event in goal syntax), until the next cue."""
    mood: Literal["calm", "tension", "action", "sad", "hope", "triumph", "silence"]
    at: Optional[float] = Field(None, ge=0)
    on: Optional[str] = None
    delay: float = 0.0

    @model_validator(mode="after")
    def _when(self) -> "ScoreCue":
        if (self.at is None) == (self.on is None):
            raise ValueError("a score cue needs exactly one of 'at' or 'on'")
        return self


class ScoreSpec(Strict):
    """The film score of a scene (cinematic upgrade): mood cues, synthesised in the scene's key. `level` is the
    music's peak relative to the sound effects' peak."""
    key: str = "D"
    level: float = Field(0.55, ge=0, le=2)
    cues: List[ScoreCue] = Field(default_factory=list)


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
    music: Optional[MusicSpec] = None  # beat grid: cut snapping, beat waits, beat-locked soundtrack (Milestone 4)
    diagrams: List[DiagramSpec] = Field(default_factory=list)  # annotations from simulation data (Milestone 5)
    fail: Optional[FailSpec] = None  # Milestone 6: falling out of the level
    hud: Optional[HudSpec] = None  # Milestone 6: retry counter and messages
    transition_in: Literal["cut", "fade", "rewind", "warp"] = "cut"  # how a film enters this scene from the previous one
    score: Optional[ScoreSpec] = None  # cinematic upgrade: music that follows the story's moods
    retry_of: Optional[str] = None  # Milestone 6: this scene is a retry of that scene (it restarts from the same state)

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


from .creative import CreativePlan


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
    creative_plan: Optional[CreativePlan] = None  # optional cross-scene story contract; absent in legacy projects

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
                if pl.at is not None:
                    lv = envs[sc.environment].level
                    if lv is None or pl.at not in lv.markers:
                        raise ValueError(f"scene {sc.id}: placement of {pl.character} at unknown level marker {pl.at!r}")
                    pl.x = lv.markers[pl.at][0]
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
                if ex.unlock_on and ex.unlock_on.startswith("together:"):
                    who = set(ex.unlock_on.split(":", 1)[1].split(","))
                    if not who or not who <= chars:
                        raise ValueError(f"exit {ex.id}: unlock_on 'together:' must list known characters")
                elif ex.unlock_on and (not ex.unlock_on.startswith("switch:") or ex.unlock_on.split(":", 1)[1] not in switches):
                    raise ValueError(f"exit {ex.id}: unlock_on must be 'switch:<id>' of a known switch or 'together:<ids>'")
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
            whos = placed | props | {r.id for r in envs[sc.environment].ropes} | {c.id for c in envs[sc.environment].creatures}
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
