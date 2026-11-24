"""Cross-platform `apex film` support, including Windows (no Unix resource module)."""
import builtins
import sys

from apex.render.film import _rss_mb


def test_film_memory_probe_is_nonnegative_or_explicitly_unknown():
    v = _rss_mb()
    assert v > 0 or v == -1.0


def test_film_memory_probe_survives_windows_without_resource(monkeypatch):
    real_import = builtins.__import__

    def no_resource(name, *args, **kwargs):
        if name in ("resource", "psutil"):
            raise ImportError("simulated Windows / optional psutil unavailable")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", no_resource)
    assert _rss_mb() == -1.0
