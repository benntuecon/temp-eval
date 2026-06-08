"""Live end-to-end smoke test.

Marked ``@pytest.mark.live`` and skipped unless ``ANTHROPIC_API_KEY`` is set.
The default ``addopts = "-m 'not live'"`` in pyproject.toml ensures this is
*never* executed by a plain ``uv run pytest -q`` run.

To run intentionally (costs real money):
    uv run pytest tests/test_live_smoke.py -m live -q -s
"""

import os
import tempfile

import pytest

from skill_eval.contracts import Arm, Criterion
from skill_eval.orchestrator import run_eval
from skill_eval.sample_repo import build_sample_repo


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no API key")
def test_real_end_to_end() -> None:
    cfg = build_sample_repo(tempfile.mkdtemp())
    report = run_eval(cfg)  # real components (lazy defaults), Haiku
    assert {a.arm for a in report.arms} == {Arm.BASELINE, Arm.CHALLENGER}
    for ar in report.arms:
        assert {s.criterion for s in ar.scores} == set(Criterion)
        assert all(0 <= s.score <= 20 for s in ar.scores)
    assert report.pairwise_verdict
