"""Native-backed APEX capability registry (APEX Studio & EDU Foundation V2).

The extension kit ships isolated modules marked `native_verified: false`. A capability becomes *verified* only once it
is proven against the native APEX engine (a native test, a committed render, or both) — `product_sdk.Capability`
enforces that a verified entry carries evidence. The AI Director must consume only verified capabilities.

This module is the single place that maps APEX's proven behaviour to the product-neutral `Backend` contract, so Studio
and EDU (and later Interactive/Simulation/Ads) advertise the same reconciled truth. Nothing here re-implements engine
behaviour: it points at the native implementation and its evidence.
"""
from __future__ import annotations

import json
import os
import tempfile

from .product_sdk import Backend, Capability, Product
from . import rendering

# Proven against the native engine on this branch (feature/apex-three-reference-grade + PR #11 math-balance work).
# Evidence names the native code path and the test/render that exercised it.
VERIFIED: tuple[Capability, ...] = (
    Capability("autonomous_choreography", True,
               "apex.scene.autochoreo.search picks a physics-verified tactic (rejects infeasible ones); "
               "examples/build_impossible_crossing.py renders; tests/test_autochoreo.py"),
    Capability("physical_math_symbols", True,
               "apex.scene.math_stage.compile_math_stage builds a true equation as glyph geometry; tests/test_math_stage.py"),
    Capability("math_equation_transform", True,
               "apex.scene.math_stage.plan_balance + compile_proven_math_pair (SymPy-gated); "
               "tests/test_math_balance.py; examples/build_balance_equation.py render (PR #11)"),
    Capability("fixed_glyph_morph", True,
               "apex.physics.world.reshape morphs a fixed (kinematic) set-dressing glyph upright without NaN; "
               "tests/test_apex_extension_native.py::test_math_world_matches_native"),
    Capability("world_perception", True,
               "apex_extension.world.from_project agrees with apex.scene.structures.obstacle_bounds; "
               "tests/test_apex_extension_native.py::test_world_from_project_matches_native"),
    Capability("character_memory", True,
               "apex_extension.character.native_brain wraps apex.ai.character_brain.CharacterBrain (outcome memory, "
               "appearance-independent); tests/test_apex_extension_native.py::test_character_brain_native"),
)

# Kit interfaces present but not yet proven on the native engine; kept unverified until native evidence exists.
UNVERIFIED: tuple[Capability, ...] = (
    Capability("illustrated_rig_retarget"),   # rig.Rig.retarget present; not yet proven on an illustrated backend
    Capability("dialogue_srt"),
    Capability("ensemble_scheduling"),
    Capability("chart_visualization"),
    Capability("lesson_release_gate"),
    Capability("story_beat_validation"),
    Capability("shot_audio_cues"),
)


class ApexBackend:
    """The native APEX engine presented through the product-neutral Backend protocol."""

    def __init__(self, product: Product = Product.STUDIO):
        self.product = product

    def capabilities(self) -> tuple[Capability, ...]:
        return VERIFIED + UNVERIFIED

    def render(self, project: dict, output: str) -> str:
        """Render a project dict through the native APEX CLI (validate + render), never an alternate backend."""
        from pathlib import Path
        fd, path = tempfile.mkstemp(suffix=".json")
        try:
            with os.fdopen(fd, "w") as fh:
                json.dump(project, fh)
            return str(rendering.render_native(Path(path), Path(output)))
        finally:
            os.unlink(path)


def registry(product: Product = Product.STUDIO) -> Backend:
    """The reconciled APEX capability registry for a product. Advertises only verified capabilities as verified."""
    return ApexBackend(product)
