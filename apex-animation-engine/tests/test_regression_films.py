"""Regression benchmark: the committed films keep working after every engine change (see apex.qa.benchmark)."""
import json
import os

import pytest

from apex.qa import benchmark


@pytest.mark.parametrize("fname", list(benchmark.FILMS))
def test_film_does_not_regress(fname):
    base = json.load(open(benchmark.BASELINE)) if os.path.exists(benchmark.BASELINE) else {}
    for sid, cur in benchmark.run_film(fname, determinism=False).items():
        bad = benchmark.compare(base.get(fname, {}).get(sid), cur)
        assert not bad, f"{fname}/{sid}: {bad}"
