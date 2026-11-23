"""Audio sample assets are optional: missing WAVs must not break a film."""
import json

from apex.audio.samples import SampleBank


def test_missing_manifest_entries_do_not_crash_and_use_synthesis(tmp_path):
    (tmp_path / "manifest.json").write_text(json.dumps({
        "sounds": {"footstep": {"layers": [{"files": ["unshipped/step.wav"]}], "synth_mix": 0.2}},
        "room_tone": {"file": "unshipped/room.ogg"}
    }), encoding="utf-8")
    bank = SampleBank(48000, seed=11, root=str(tmp_path))
    assert not bank.has("footstep")
    assert bank.render("footstep", 0) is None
    assert bank.room_tone(200) is None


def test_corrupt_audio_decodes_are_rejected_without_render_crash(tmp_path):
    bad = tmp_path / "bad.wav"
    bad.write_bytes(b"this-is-not-a-wav")
    (tmp_path / "manifest.json").write_text(json.dumps({
        "sounds": {"impact": {"layers": [{"files": ["bad.wav"]}]}}
    }), encoding="utf-8")
    bank = SampleBank(48000, seed=11, root=str(tmp_path))
    # FFmpeg may be missing on development machines; in either case the
    # optional asset must be gracefully rejected and the synth retained.
    assert bank.render("impact", 0) is None
