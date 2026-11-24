"""Renderer adapter: the contract every rendering backend implements.

The animation stack (simulation, animator, motion library, camera director, QA) produces only data: a `FrameState`
(poses, props, gravity, doors, secondary motion) and a `CameraState` per frame. A backend turns those into pixels.
The Skia CPU renderer (`render/skia_renderer.py`) is the reference implementation; a GPU or 3D backend (OpenGL via
moderngl, Blender/EEVEE through a headless bridge, WebGPU) implements the same protocol and reuses every animation
system unchanged. See docs/RENDERER_EVALUATION.md for the current backend's limits and the migration path.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Protocol, Tuple, runtime_checkable

import numpy as np

from ..camera.director import CameraState
from ..rig.stickman import Pose
from ..scene.runtime import FrameState


@runtime_checkable
class Renderer(Protocol):
    W: int
    H: int

    def render(self, fs: FrameState, cam: CameraState, red_flash: float = 0.0, fx: Optional[List[dict]] = None, fade: float = 0.0,
               trails: Optional[Dict[str, List[Tuple[Pose, float]]]] = None) -> np.ndarray:
        """Return an (H, W, 4) uint8 RGBA frame for the given state and camera."""
        ...


BACKENDS = {"skia": "apex.render.skia_renderer:SkiaRenderer"}


def make_renderer(backend: str, *args, **kwargs) -> Renderer:
    """Instantiate a registered backend by name (`skia` today)."""
    import importlib
    mod, cls = BACKENDS[backend].split(":")
    return getattr(importlib.import_module(mod), cls)(*args, **kwargs)
