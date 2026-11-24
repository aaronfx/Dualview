"""The APEX showreel: every benchmark film, Milestone 1 to 6, re-rendered with the current engine, each introduced
by a title card that says what it demonstrates.

Every film is rendered from its committed scene file by the engine (with QA); nothing is edited by hand. The title
cards are drawn here; the films are joined with `render/film.py`'s concat (fades in from each card).

    PYTHONPATH=src python examples/make_showreel.py out/reel [--height 1080] [--samples 1] [--jobs 3] [--only name,...]
"""
import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "src"))

# (scene file, milestone label, title, what it shows)
REEL = [
    ("gravity_switch_1d.json", "FOUNDATIONS", "Gravity Switch: Escape",
     ["Gravity switches with signed rotations; slides, swings, doors", "Camera roll follows the physics"]),
    ("foundry_flip.json", "FOUNDATIONS", "Foundry Flip",
     ["Generalization test: a new room, the same engine", "Surface switches and flips"]),
    ("the_rescue.json", "FOUNDATIONS", "The Rescue",
     ["Physical interaction: push, rope, pinning, lever, help up", "Bounded-force bodies against dynamic props"]),
    ("runaway_crate.json", "FOUNDATIONS", "The Runaway Crate",
     ["A crate breaks loose; characters react", "Hands that really meet in a help-up"]),
    ("first_exchange.json", "MILESTONE 1", "First Exchange",
     ["Combat: strikes, blocks, dodges, hit reactions", "Ragdoll knockdown and recovery"]),
    ("symbol_run.json", "MILESTONE 2", "Symbol Run",
     ["Acrobatics: platforms, vaults, climbs, flips, rolls", "Glyph props that can be stood on and thrown"]),
    ("glyph_duel.json", "MILESTONE 3", "Glyph Duel",
     ["Acrobatics and combat with wielded and thrown symbols", "Time effects: hit-stop, slow motion, smears, action camera"]),
    ("orb_runner.json", "MILESTONE 4", "Orb Runner",
     ["Level grid, jump and boost orbs, portals (characters and props)", "Beat-synced cuts and event particles"]),
    ("specimen.json", "MILESTONE 5", "The Specimen",
     ["Impulse-driven breakables, glyph morphs, a composite creature", "A diagram layer whose numbers QA re-derives"]),
    ("last_retry.json", "MILESTONE 6", "The Last Retry",
     ["Emotional acting, collapsing structures, ledge catches and rescues", "Retries, a HUD, an exit for two; a multi-scene film"]),
]


def card(path, W, H, fps, label, title, lines, secs=3.6):
    """A title card: rendered with Skia (same fonts as the HUD), encoded with silence."""
    import skia
    from apex.render.video import VideoWriter
    s = H / 1080.0
    tf = skia.Typeface("DejaVu Sans", skia.FontStyle.Bold())
    tr = skia.Typeface("DejaVu Sans", skia.FontStyle.Normal())
    fl, ft, fb = skia.Font(tf, 30 * s), skia.Font(tf, 84 * s), skia.Font(tr, 34 * s)
    wav = path + ".wav"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-t", str(secs), "-i", "anullsrc=r=48000:cl=stereo", wav], check=True)
    w = VideoWriter(path, W, H, fps, audio=wav)
    surf = skia.Surface(W, H)
    n = int(secs * fps)
    for i in range(n):
        t = i / fps
        a = min(1.0, t / 0.5, (secs - t) / 0.5)
        c = surf.getCanvas()
        c.clear(skia.Color(3, 4, 9))
        sh = skia.GradientShader.MakeRadial(skia.Point(W / 2, H * 0.45), W * 0.6, [skia.Color4f(0.05, 0.12, 0.2, 1.0), skia.Color4f(0.01, 0.015, 0.035, 1.0)])
        c.drawRect(skia.Rect(0, 0, W, H), skia.Paint(Shader=sh))
        p = lambda r, g, b, k=1.0: skia.Paint(AntiAlias=True, Color4f=skia.Color4f(r, g, b, a * k))
        x0 = W * 0.12
        c.drawString(label, x0, H * 0.36, fl, p(0.31, 0.85, 1.0))
        c.drawRect(skia.Rect(x0, H * 0.38, x0 + 140 * s * min(1.0, t / 0.8), H * 0.38 + 4 * s), p(0.31, 0.85, 1.0))
        c.drawString(title, x0, H * 0.50, ft, p(0.96, 0.97, 1.0))
        for k, line in enumerate(lines):
            c.drawString(line, x0, H * (0.60 + 0.06 * k), fb, p(0.75, 0.82, 0.92, 0.95))
        w.write(surf.makeImageSnapshot().toarray(colorType=skia.ColorType.kRGBA_8888_ColorType))
    w.close()
    os.remove(wav)


def render_one(args):
    fname, out_dir, height, samples = args
    from apex.scene.schema import ProjectSpec
    proj = ProjectSpec.model_validate(json.load(open(os.path.join(HERE, fname))))
    scale = height / proj.height
    out = os.path.join(out_dir, os.path.splitext(fname)[0] + ".mp4")
    meta = out + ".json"
    if os.path.exists(out) and os.path.exists(meta):
        return json.load(open(meta))
    if len(proj.scenes) > 1:
        from apex.render.film import render_film
        r = render_film(proj, out, samples=samples, preview_scale=scale)
        info = {"film": fname, "seconds": round(r.seconds, 1), "duration": round(r.duration, 2),
                "gates": [m.gates for m in r.scenes], "film_checks": [(c["name"], c["status"]) for c in r.film_checks]}
    else:
        from apex.render.pipeline import render_scene
        from apex.render.video import probe
        r = render_scene(proj, proj.scenes[0].id, out, samples=samples, preview_scale=scale, qa=True)
        info = {"film": fname, "seconds": round(r.seconds, 1), "duration": float(probe(out)["format"]["duration"]),
                "gates": [r.qa.gates()] if r.qa else []}
    json.dump(info, open(meta, "w"), indent=1)
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out_dir")
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--samples", type=int, default=1)
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--only", default=None)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    W, H, fps = a.height * 16 // 9, a.height, 24
    films = [r for r in REEL if not a.only or os.path.splitext(r[0])[0] in a.only.split(",")]
    with ProcessPoolExecutor(a.jobs) as ex:
        infos = list(ex.map(render_one, [(f, a.out_dir, a.height, a.samples) for f, *_ in films]))
    for i in infos:
        print(json.dumps(i))
    if a.only:
        return
    from apex.render.film import _concat
    parts, fades = [], []
    for k, (fname, label, title, lines) in enumerate(REEL):
        cp = os.path.join(a.out_dir, f"card_{k:02d}.mp4")
        if not os.path.exists(cp):
            card(cp, W, H, fps, label, title, lines)
        parts += [cp, os.path.join(a.out_dir, os.path.splitext(fname)[0] + ".mp4")]
        fades += [False, True]
    out = os.path.join(a.out_dir, "APEX_showreel_M1-M6.mp4")
    _concat(parts, out, fps, (W, H), fades, crf=18)
    json.dump(infos, open(os.path.join(a.out_dir, "showreel_report.json"), "w"), indent=1)
    print("wrote", out)


if __name__ == "__main__":
    main()
