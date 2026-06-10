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

    # Every run-scoped span carries the SAME session.id so Phoenix groups them.
    root = next(s for s in spans if s.name == "skill_eval.run")
    session_id = root.attributes.get("session.id")
    assert session_id  # non-empty
    for s in spans:
        if s.name in ("skill_eval.run", "sandbox", "taker", "judge"):
            assert s.attributes.get("session.id") == session_id


def test_span_enrichment_helpers():
    """The new LLM-detail helpers set the expected OpenInference attributes."""
    _EXPORTER.clear()

    from skill_eval.tracing import (
        get_tracer,
        set_cache_tokens,
        set_invocation_parameters,
        set_messages,
        set_metadata,
        set_model_name,
        set_session,
    )

    with get_tracer().start_as_current_span("probe") as span:
        set_model_name(span, "claude-haiku-4-5")
        set_invocation_parameters(span, {"max_tokens": 500})
        set_messages(
            span,
            input_messages=[{"role": "user", "content": "hi"}],
            output_messages=[{"role": "assistant", "content": "yo"}],
        )
        set_cache_tokens(span, 123, 0)
        set_metadata(span, {"k": "v"})
        set_session(span, "sess123")

    probe = next(s for s in _EXPORTER.get_finished_spans() if s.name == "probe")
    a = probe.attributes
    assert a["llm.model_name"] == "claude-haiku-4-5"
    assert "llm.invocation_parameters" in a
    assert a["llm.input_messages.0.message.role"] == "user"
    assert a["llm.input_messages.0.message.content"] == "hi"
    assert a["llm.output_messages.0.message.content"] == "yo"
    assert a["llm.token_count.prompt_details.cache_read"] == 123
    # zero cache-write is omitted (no noise on spans)
    assert "llm.token_count.prompt_details.cache_write" not in a
    assert a["metadata"] == '{"k": "v"}'
    assert a["session.id"] == "sess123"
