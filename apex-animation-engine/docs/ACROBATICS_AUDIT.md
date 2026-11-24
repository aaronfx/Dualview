# Milestone 2 audit: acrobatics and symbols as physical objects

Goal: the character can move through a world built from symbols, and use those symbols. Reference: the original benchmark film, a character fighting a symbolic world. Nothing from the reference films is copied: no characters, scenes, glyph art or levels.

## What exists before Milestone 2

| Capability | Status | Where |
|---|---|---|
| Support surfaces | Only the four room surfaces (floor, walls, ceiling). Each is an infinite line, so a character can never walk off an edge | `motion/frames.py` |
| Fixed structures | `beam`: a static box. You can collide with it or slide under it, but you **cannot stand on it**. `bar`: a grab rail | `scene/schema.ObstacleSpec`, `runtime.simulate` |
| Walking into structures | Grounded characters are kinematic, so they **walk straight through** beams and props | `controller._locomote` |
| Jumps | `jump` needs a run-up. `jump_to` is ballistic, aimed at a point **on the same surface**. Mid-air: tuck, brace and a switch slap. No rotation control beyond staying upright | `controller._takeoff`, `_takeoff_to` |
| Bar swing | `grab_swing`: catch, pump, release (physics pin) | `controller._swing` |
| Slide | `duck_slide` under beams | `controller._slide` |
| Props | Boxes only (crate, canister, container, post, bar, toolbox). One rectangle shape each | `physics/world.add_box` |
| Carrying | Only the lever bar during `use_lever`, held kinematically | `interaction._carry_pose` |
| Throwing, wielding | None | — |
| Symbols | None. There is no glyph geometry, physics or rendering | — |
| Combat | Eight grounded strikes, guard, dodge, ragdoll knockdown (Milestone 1) | `motion/combat.py` |

## What Milestone 2 adds

| Need | Design |
|---|---|
| **Glyphs as geometry** | `scene/glyphs.py`: each symbol (digits, `+ − × ÷ = π √ ? ! < >`) is a set of strokes in a unit box. One definition drives three things: physics (each stroke a rounded segment, so a capsule), standable tops (its near-horizontal strokes) and rendering (thick glowing strokes) |
| **Standable structures** | New obstacle kinds. `platform` is a static box with a standable top. `glyph` is a static symbol whose horizontal strokes are standable. Every standable top becomes a support frame with **extents**, so walking past an end means **stepping off and falling** |
| **No walking through structures** | Walking into a structure on the floor is an authoring error. The dry run names the structure and suggests `vault`, `climb` or `jump_to` |
| **Jump onto, off and between** | `jump_to` gains `onto` (land on a platform or glyph top). The ballistic solution accounts for the height difference. From a platform, it lands on the floor by default |
| **Flips** | `jump_to` and `wall_kick` take `flip: front | back`. Physics drives the body rotation along a planned profile that completes before landing, and the animation tucks and then opens out for the landing |
| **Roll** | `roll` is a forward roll along the surface. When it directly follows a jump, it starts at touchdown (a landing roll that absorbs the drop) |
| **Vault** | `vault` over a low structure or prop: plant a hand on top, swing the legs over, land on the far side |
| **Ledge climb** | `climb` onto a platform or glyph top: jump up, hang from the edge, pull up, mantle, stand on top |
| **Wall kick** | `wall_kick`: run at a wall (a room wall or a structure's side), two steps up it, then push off into a back flip and land |
| **Air kick** | Strike move `flying_kick`: a jumping lunge with contact at the top of the arc. It uses the same contact rules as the other strikes |
| **Glyph props** | A prop with `kind: glyph` is a dynamic compound body built from the glyph's strokes. It can be pushed (existing `push`), picked up, carried, swung and thrown |
| **Pick up, throw** | `pick_up` grips a light prop and carries it. `throw` aims a ballistic arc at a character or a point. A thrown prop that reaches a character **hits** (a reaction), is **blocked** by a guard, or misses one who ducks. This is decided geometrically, in the simulation, like a strike |
| **Wield** | Strike move `swing_weapon` while carrying a prop: the reach is the arm plus the prop, and contact happens at the prop's far end |
| **Events** | `step_off`, `flip`, `roll_start`, `roll_end`, `vault`, `ledge_grab`, `climbed`, `wall_contact`, `wall_kick`, `pick_up`, `throw`, `prop_hit` |
| **QA** | Standing on structures (feet on the top within its extents), no walking through structures, flips land upright, thrown props: contact and outcome |

## Known limits (deliberately out of scope)

- Standing on a **moving** glyph is not supported. Only fixed glyphs and platforms can be stood on; dynamic glyph props can be pushed, carried and thrown.
- Wall-runs are a short wall kick (two steps), not a sustained run along a wall.
- Hit-stop, slow motion and smears are Milestone 3. Living symbols (composite creatures) are Milestone 5.
