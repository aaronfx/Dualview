# Action film plan: *CORE RUN* (working title)

The owner asked for a full animated action movie of 2 to 3 minutes. It should be full of action and emotion every second, with no characters standing around doing nothing. It should move through different environments and include running, fighting, climbing, jumping, breaking things and rolling. It starts as soon as *The Last Retry* is delivered.

Everything uses engine systems that already exist and are covered by QA:
- combat, ragdoll knockdowns and get-ups;
- acrobatics: jump, flip, roll, vault, climb, wall kick, slide;
- thrown and wielded glyphs;
- breakables, collapses, orbs and portals, composite creatures;
- acting clips;
- the open-world biomes;
- the film score;
- `apex film`.

The film is original. Its characters, story and look are APEX's own.

## Cast

| Character | Look | Role |
|---|---|---|
| IKO | Yellow, pink scarf | The hero: fast and reckless |
| PELL | Blue | His partner: clumsy but brave, and he saves IKO twice |
| VEX | Red, new | A rival who steals the glowing core and fights dirty |
| Drones | Glyph creatures (composite) | VEX's minions, which get smashed |

## Story and scenes (each scene a simulated scene; joined by `apex film`)

| # | World | Time | Action beats (no idle beats) |
|---|---|---|---|
| 1 | City rooftops, night, rain | 0–25 s | VEX smashes a glass case (breakable) and grabs the core. IKO and PELL burst in and the chase starts: rooftop leaps with flips and landing rolls. VEX throws crates back, PELL ducks under one, IKO vaults a vent |
| 2 | Storm tower scaffolding | 25–55 s | Vertical chase: ledge climbs, wall kicks, vaults over girders, a crate smashed through. IKO catches VEX on a girder and they trade strikes, blocks and dodges. VEX sweeps IKO down (ragdoll) and escapes. PELL hauls IKO up (helped get-up) |
| 3 | Canyon at sunset | 55–90 s | VEX crosses a rope bridge and it collapses behind him. IKO flips across on a jump orb, PELL slides under a swinging hazard. A glyph drone attacks: PELL throws a glyph and tears it apart, and IKO rolls through the debris |
| 4 | Void arena | 90–130 s | The final fight. VEX wields a glyph weapon. Combos, a roundhouse, a sweep, a flying kick, dodges and guards. IKO is knocked down, and PELL throws a glyph that knocks the weapon away. IKO gets up for a flying kick and VEX goes down (ragdoll). The core is recovered |
| 5 | Summit at dawn | 130–150 s | They run up to the summit with the core. IKO cheers, PELL laughs, fist bump. A fade on the sunrise |

## Rules for this film

- **No idle time:** no idle action longer than about 0.8 s. Waits are covered by another character's action in the same shot.
- **Cuts:** every 1.5 to 4 s, placed from events. Slow motion on the key hits, smashes and leaps.
- **Score:** mostly action. Tension on the fight build-ups, sad when IKO is down, triumph at the end.
- **QA:** every scene must pass the technical and cinematic gates. The film checks must pass, and there is no manual frame repair.
- **Delivery:** a 720p draft for review, then 1080p final. Compressed MP4s in two parts (crf 28, faststart).

## Builder

- **Builder:** `examples/build_core_run.py` → `examples/core_run.json`.
- **Render:** `apex film examples/core_run.json -o out/core_run/core_run.mp4`.

## Director's Cut (after the first-draft review)

The review found the first draft closer to a set of action sequences than a story. The Director's Cut rebuilds it around the stolen core: what each character wants, what stops them, what they do about it, and what changes. The five worlds, the cast and the engine systems are kept.

### The story as built (`examples/build_core_run.py`)

| # | Scene | What happens (simulated; cuts, slow motion and score are placed from the events) |
|---|---|---|
| 1 | The theft (city, night, rain) | A close-up of the core in its glass case. VEX punches through the glass and lifts the core out; the city's lights die in a wave from the plinth and the beacons pulse red. IKO and PELL turn; VEX shows them the core and laughs. They vault the empty plinth; VEX kicks a crate back at them (IKO ducks, PELL rolls). Over the gap and the vent; IKO's flying kick is launched from too far, VEX steps out of it and kicks him to the roof edge; IKO waves PELL's hand away and runs on |
| 2 | The storm tower | VEX leaps the girders with the core; IKO climbs after him. On the girder IKO's jab, cross and side kick are taken on VEX's guard as he gives ground; IKO cheers too soon; VEX slips the roundhouse and sweeps him. IKO tries to get up alone and cannot; VEX looks down at him, laughs and leaves. PELL offers his hand; IKO, sitting up, takes it and is pulled up; PELL points the way |
| 3 | The canyon (sunset) | VEX crosses the rope bridge and kicks out its stake: the bridge falls. IKO leaps for a jump orb, which flips him across (it bursts); PELL jumps short, catches the far edge and climbs up. A beam swings across the path; both go under it low. The drone shrugs off IKO's kick; PELL steps past IKO and his thrown X tears it apart; IKO rolls through the wreckage and they follow VEX into the portal |
| 4 | The arena (the void) | VEX sets the core in a socket (the arena floods with energy) and takes up a staff. IKO's jab is blocked, the swing is slipped, the side kick lands, the cross is blocked; PELL rushes in too late as the staff knocks IKO down. IKO cannot rise. PELL's thrown X knocks the staff out of VEX's hands. IKO gets up, looks at PELL, ducks VEX's hook and the flying kick lands. VEX cannot rise. IKO takes the core out of the socket and they go |
| 5 | The return of the light (summit, dawn) | IKO and PELL run up with the core; IKO sets it in the beacon; a ring of light goes out and the dark city below lights up again in a wave. IKO looks at PELL; a fist bump; the camera pulls back over the restored world: CORE RUN. VEX is not in this scene |

### What the engine gained for it

- `place`: set a carried prop down on a holder (a `pedestal` structure seats it) or at a point.
- `placements[].carrying`: a scene starts with a prop in a character's hands (the core carried between scenes).
- `strike` at a prop (`prop:<id>`): a punch or standing kick delivers a real blow (it breaks glass, sends a crate flying, can be shrugged off by a sturdy drone).
- A thrown symbol that hits a held symbol knocks it out of the hands (`disarm`); a knockdown drops what is held.
- `get_up` with `hesitate`: an attempt to rise that fails; a helped get-up now also works from the back.
- Orbs with `once` (spent after one use).
- World power: `backdrop.power` cues dim, flicker and relight the city's windows and signs (as a wave from an origin, with a ring of light), red warning beacons pulse while the power is out, `city_lights` puts a distant city below the summit, and `energy` props glow.

## Status (first draft rendered)

The first draft is a 720p, 2:15 film with five scenes, built by `examples/build_core_run.py` (`out/core_run/` is not committed).
- **QA gates:**
  - tower, canyon and summit pass the technical gate;
  - the cinematic gate passes or warns in every scene.
- **Still failing the technical gate**, all to fix before the final 1080p render:
  - **City:**
    - `obstacle_clearance`: a toe clips the vent during a vault (t≈16.4 s);
    - `body_clearance`: IKO and VEX at the point-blank throw (t≈19.9 s);
    - `throw_momentum`: the bar hitting IKO at 3.0 s (31 % against 25 %).
  - **Arena:**
    - `bone_lengths[vex]`: two frames at t≈7.2 s, upper arms compressed while VEX is hurt holding the staff;
    - `strike_contact`: the flying kick, 49 units against 24;
    - `props_not_through_bodies`: IKO stands on the spent X at the end.
- **Fragile choreography:** small changes cascade through the physics (lanes, throw origins, timing). Change one thing at a time and re-run `ends.py`-style checks (every scene must still reach its closing event) before running QA.
