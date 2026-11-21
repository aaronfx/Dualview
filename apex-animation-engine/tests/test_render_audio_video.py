import hashlib
import os
import wave

import numpy as np

from apex.audio.sound_director import SoundDirector
from apex.render.pipeline import render_scene
from apex.render.skia_renderer import SkiaRenderer
from apex.render.video import probe
from tests.test_qa import _camera


def test_renderer_output_shape_and_repeatable_pixels(gravity_runtime):
    rt = gravity_runtime
    cam = _camera(rt)
    r = SkiaRenderer(480, 270, rt.env, {"axel": rt.project.character("axel").style}, rt.rigs)
    a = r.render(rt.evaluate(4.6), cam.at(4.6), 0.3)
    b = r.render(rt.evaluate(4.6), cam.at(4.6), 0.3)
    assert a.shape == (270, 480, 4) and a.dtype == np.uint8
    assert a[..., :3].mean() > 5  # not a black frame
    assert hashlib.sha256(a.tobytes()).hexdigest() == hashlib.sha256(b.tobytes()).hexdigest()


def test_sound_cues_are_bound_to_event_times(gravity_runtime, tmp_path):
    ev = gravity_runtime.result.events
    sd = SoundDirector(7)
    cues = sd.render(ev, gravity_runtime.scene.duration, str(tmp_path / "a.wav"))
    times = {(round(e.t, 6), e.type) for e in ev}
    assert cues and all((round(c.t, 6), c.event_type) in times for c in cues)
    with wave.open(str(tmp_path / "a.wav")) as w:
        assert abs(w.getnframes() / w.getframerate() - gravity_runtime.scene.duration) < 1e-3


def test_end_to_end_small_render_produces_playable_mp4(gravity_project, tmp_path):
    out = str(tmp_path / "gs.mp4")
    res = render_scene(gravity_project, "switch_and_fall", out, preview_scale=0.2, qa=True)
    assert os.path.getsize(out) > 10_000
    info = probe(out)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (384, 216) and v["r_frame_rate"] == "24/1" and int(v["nb_frames"]) == 252
    assert any(s["codec_type"] == "audio" for s in info["streams"])
    assert res.qa.passed, res.qa.summary()


def test_non_frame_aligned_duration_keeps_every_frame(motion_project, tmp_path):
    """Regression: audio shorter than the frame-quantised video made ffmpeg's -shortest drop the last frame."""
    d = motion_project.model_dump(mode="json")
    sc = d["scenes"][0]
    sc["duration"] = 3.01
    sc["actions"] = sc["actions"][:2]
    sc["shots"][0]["end"] = 3.01
    sc["shots"][0]["exit_conditions"] = []
    from apex.scene.schema import ProjectSpec
    proj = ProjectSpec.model_validate(d)
    out = str(tmp_path / "short.mp4")
    render_scene(proj, sc["id"], out, preview_scale=0.15, qa=False)
    v = next(s for s in probe(out)["streams"] if s["codec_type"] == "video")
    assert int(v["nb_frames"]) == round(3.01 * 24)
