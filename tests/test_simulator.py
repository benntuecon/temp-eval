from unittest.mock import MagicMock, patch

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from skill_eval.simulator import make_simulator


@patch("skill_eval.simulator.anthropic.Anthropic")
def test_make_simulator_answers(mock_cls, tmp_path):
    (tmp_path / "calculator.py").write_text("def add(a, b):\n    return a + b\n")
    msg = MagicMock()
    msg.content = [MagicMock(text="Yes — it should return the sum.")]
    mock_cls.return_value.messages.create.return_value = msg

    ask = make_simulator(str(tmp_path), "Fix add so it sums.", "claude-haiku-4-5")
    answer = ask("Should add return a+b?")
    assert "sum" in answer.lower()
    # used the cheapest model + included the question
    _, kwargs = mock_cls.return_value.messages.create.call_args
    assert kwargs["model"] == "claude-haiku-4-5"


def _install_exporter() -> InMemorySpanExporter:
    """Attach an in-memory exporter to the active provider (proxy-safe)."""
    exporter = InMemorySpanExporter()
    provider = trace.get_tracer_provider()
    if type(provider).__name__ == "ProxyTracerProvider":
        provider = TracerProvider()
        provider.add_span_processor(SimpleSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
    else:
        provider.add_span_processor(SimpleSpanProcessor(exporter))  # type: ignore[attr-defined]
    return exporter


@patch("skill_eval.simulator.anthropic.Anthropic")
def test_make_simulator_emits_traced_llm_span(mock_cls, tmp_path):
    """The HITL simulator's model call is captured as an LLM span with tokens."""
    exporter = _install_exporter()
    exporter.clear()

    (tmp_path / "calculator.py").write_text("def add(a, b):\n    return a + b\n")
    msg = MagicMock()
    msg.content = [MagicMock(text="Use Decimal with ROUND_HALF_UP.")]
    msg.usage = MagicMock(
        input_tokens=120,
        output_tokens=30,
        cache_read_input_tokens=64,
        cache_creation_input_tokens=0,
    )
    mock_cls.return_value.messages.create.return_value = msg

    ask = make_simulator(str(tmp_path), "Prorate the refund.", "claude-haiku-4-5")
    ask("How should rounding work?")

    sim = next(s for s in exporter.get_finished_spans() if s.name == "llm.simulator")
    a = sim.attributes
    assert a["openinference.span.kind"] == "LLM"
    assert a["llm.model_name"] == "claude-haiku-4-5"
    assert a["llm.token_count.prompt"] == 120
    assert a["llm.token_count.completion"] == 30
    assert a["llm.token_count.total"] == 150
    assert a["llm.token_count.prompt_details.cache_read"] == 64
    # structured messages: system + user in, assistant out
    assert a["llm.input_messages.0.message.role"] == "system"
    assert a["llm.input_messages.1.message.role"] == "user"
    assert a["llm.output_messages.0.message.role"] == "assistant"
    assert "Decimal" in a["llm.output_messages.0.message.content"]
