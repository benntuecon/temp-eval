"""Offline tests: verify OTel spans are emitted by a simulated run.

Uses an in-memory span exporter so no Phoenix server or network is needed.
``trace.set_tracer_provider`` is set once at module import time so the lazy
``_get_tracer()`` helper in orchestrator.py picks up this provider when spans
are actually created (inside run_eval / node functions).
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

# ---------------------------------------------------------------------------
# Module-level provider setup — must run before any orchestrator call.
# Guard so repeated test-collection in the same process doesn't trigger the
# "Overriding of current TracerProvider is not allowed" warning.
# ---------------------------------------------------------------------------

_EXPORTER = InMemorySpanExporter()

_current_provider = trace.get_tracer_provider()
_is_proxy = type(_current_provider).__name__ == "ProxyTracerProvider"
if _is_proxy:
    _provider = TracerProvider()
    _provider.add_span_processor(SimpleSpanProcessor(_EXPORTER))
    trace.set_tracer_provider(_provider)
else:
    # A provider was already installed (e.g., running the full suite more than
    # once); attach our exporter to whatever provider is active if possible.
    try:
        _current_provider.add_span_processor(  # type: ignore[attr-defined]
            SimpleSpanProcessor(_EXPORTER)
        )
    except Exception:
        pass


def test_eval_emits_spans(tmp_path):
    # Clear any spans from previous test invocations in this session.
    _EXPORTER.clear()

    import tempfile  # noqa: F401 — kept for symmetry with spec example

    from skill_eval.orchestrator import run_eval
    from skill_eval.sample_repo import build_sample_repo
    from skill_eval.simulated import sim_make_simulator, sim_run_judge, sim_run_taker

    cfg = build_sample_repo(str(tmp_path / "repo"))
    run_eval(
        cfg, taker_fn=sim_run_taker, simulator_factory=sim_make_simulator, judge_fn=sim_run_judge
    )

    spans = _EXPORTER.get_finished_spans()
    names = [s.name for s in spans]
    assert "skill_eval.run" in names
    assert names.count("taker") == 2
    assert names.count("judge") == 12
    judge_spans = [s for s in spans if s.name == "judge"]
    assert all("score" in s.attributes for s in judge_spans)
    assert all(0 <= s.attributes["score"] <= 20 for s in judge_spans)
