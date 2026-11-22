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
