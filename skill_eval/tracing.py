"""Shared OpenTelemetry / OpenInference helpers for skill-eval.

All helpers are *no-op-safe*: if no TracerProvider is registered they simply
fall through without raising, so unit-tests that never set up a provider are
unaffected.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.trace import Span

# ---------------------------------------------------------------------------
# OpenInference semantic-convention attribute keys
# (Import from openinference.semconv.trace when available; fall back to
# hard-coded strings so the module stays importable even if the package is
# absent.)
# ---------------------------------------------------------------------------

try:
    from openinference.semconv.trace import SpanAttributes as _SA  # type: ignore[import]

    _KIND = _SA.OPENINFERENCE_SPAN_KIND  # "openinference.span.kind"
    _INPUT_VALUE = _SA.INPUT_VALUE  # "input.value"
    _INPUT_MIME = _SA.INPUT_MIME_TYPE  # "input.mime_type"
    _OUTPUT_VALUE = _SA.OUTPUT_VALUE  # "output.value"
    _TOKEN_PROMPT = _SA.LLM_TOKEN_COUNT_PROMPT  # "llm.token_count.prompt"
    _TOKEN_COMPLETION = _SA.LLM_TOKEN_COUNT_COMPLETION  # "llm.token_count.completion"
    _TOKEN_TOTAL = _SA.LLM_TOKEN_COUNT_TOTAL  # "llm.token_count.total"
    _TOOL_NAME = _SA.TOOL_NAME  # "tool.name"
    _TOOL_PARAMETERS = _SA.TOOL_PARAMETERS  # "tool.parameters"
except Exception:  # noqa: BLE001
    _KIND = "openinference.span.kind"
    _INPUT_VALUE = "input.value"
    _INPUT_MIME = "input.mime_type"
    _OUTPUT_VALUE = "output.value"
    _TOKEN_PROMPT = "llm.token_count.prompt"
    _TOKEN_COMPLETION = "llm.token_count.completion"
    _TOKEN_TOTAL = "llm.token_count.total"
    _TOOL_NAME = "tool.name"
    _TOOL_PARAMETERS = "tool.parameters"

# Additional OpenInference attribute keys (string forms — these conventions are
# stable, so we hard-code them rather than importing to keep the block readable).
_LLM_MODEL_NAME = "llm.model_name"
_LLM_INVOCATION_PARAMETERS = "llm.invocation_parameters"
_LLM_INPUT_MESSAGES = "llm.input_messages"
_LLM_OUTPUT_MESSAGES = "llm.output_messages"
_MESSAGE_ROLE = "message.role"
_MESSAGE_CONTENT = "message.content"
_CACHE_READ = "llm.token_count.prompt_details.cache_read"
_CACHE_WRITE = "llm.token_count.prompt_details.cache_write"
_METADATA = "metadata"
_SESSION_ID = "session.id"


# ---------------------------------------------------------------------------
# Tracer accessor
# ---------------------------------------------------------------------------


def get_tracer() -> trace.Tracer:
    """Return a Tracer bound to the *current* TracerProvider (lazy)."""
    return trace.get_tracer("skill_eval")


# ---------------------------------------------------------------------------
# Span-enrichment helpers
# ---------------------------------------------------------------------------


def set_kind(span: Span, kind: str) -> None:
    """Set ``openinference.span.kind`` (e.g. 'AGENT', 'LLM', 'TOOL', 'CHAIN')."""
    try:
        span.set_attribute(_KIND, kind)
    except Exception:  # noqa: BLE001
        pass


def set_input(span: Span, text: str) -> None:
    """Set ``input.value`` + ``input.mime_type=text/plain``."""
    try:
        span.set_attribute(_INPUT_VALUE, text)
        span.set_attribute(_INPUT_MIME, "text/plain")
    except Exception:  # noqa: BLE001
        pass


def set_output(span: Span, text: str) -> None:
    """Set ``output.value``."""
    try:
        span.set_attribute(_OUTPUT_VALUE, text)
    except Exception:  # noqa: BLE001
        pass


def set_tokens(span: Span, prompt: int, completion: int) -> None:
    """Set LLM token-count attributes."""
    try:
        span.set_attribute(_TOKEN_PROMPT, prompt)
        span.set_attribute(_TOKEN_COMPLETION, completion)
        span.set_attribute(_TOKEN_TOTAL, prompt + completion)
    except Exception:  # noqa: BLE001
        pass


def set_cache_tokens(span: Span, cache_read: int, cache_write: int) -> None:
    """Set Anthropic prompt-cache token details (read / creation)."""
    try:
        if cache_read:
            span.set_attribute(_CACHE_READ, int(cache_read))
        if cache_write:
            span.set_attribute(_CACHE_WRITE, int(cache_write))
    except Exception:  # noqa: BLE001
        pass


def set_model_name(span: Span, model_name: str) -> None:
    """Set ``llm.model_name`` so Phoenix labels the LLM span with the model."""
    try:
        span.set_attribute(_LLM_MODEL_NAME, model_name)
    except Exception:  # noqa: BLE001
        pass


def set_invocation_parameters(span: Span, params: dict[str, Any]) -> None:
    """Set ``llm.invocation_parameters`` (JSON of temperature, max_tokens, …)."""
    try:
        span.set_attribute(_LLM_INVOCATION_PARAMETERS, json.dumps(params, default=str))
    except Exception:  # noqa: BLE001
        pass


def set_messages(
    span: Span,
    *,
    input_messages: list[dict[str, str]] | None = None,
    output_messages: list[dict[str, str]] | None = None,
) -> None:
    """Set OpenInference structured ``llm.input_messages`` / ``llm.output_messages``.

    Each message is ``{"role": ..., "content": ...}``.  Phoenix renders these as
    a proper chat panel (role + content) instead of a flat ``input.value`` blob.
    """
    try:
        for i, m in enumerate(input_messages or []):
            span.set_attribute(f"{_LLM_INPUT_MESSAGES}.{i}.{_MESSAGE_ROLE}", str(m.get("role", "")))
            span.set_attribute(
                f"{_LLM_INPUT_MESSAGES}.{i}.{_MESSAGE_CONTENT}", str(m.get("content", ""))
            )
        for i, m in enumerate(output_messages or []):
            span.set_attribute(
                f"{_LLM_OUTPUT_MESSAGES}.{i}.{_MESSAGE_ROLE}", str(m.get("role", ""))
            )
            span.set_attribute(
                f"{_LLM_OUTPUT_MESSAGES}.{i}.{_MESSAGE_CONTENT}", str(m.get("content", ""))
            )
    except Exception:  # noqa: BLE001
        pass


def set_metadata(span: Span, metadata: dict[str, Any]) -> None:
    """Set ``metadata`` (JSON) — arbitrary structured context Phoenix surfaces."""
    try:
        span.set_attribute(_METADATA, json.dumps(metadata, default=str))
    except Exception:  # noqa: BLE001
        pass


def set_session(span: Span, session_id: str) -> None:
    """Set ``session.id`` so Phoenix groups every span of one eval run together."""
    try:
        span.set_attribute(_SESSION_ID, str(session_id))
    except Exception:  # noqa: BLE001
        pass


# ---------------------------------------------------------------------------
# Tool-span context manager (manual lifecycle for accurate durations)
# ---------------------------------------------------------------------------


@contextmanager
def tool_span(
    tracer: trace.Tracer,
    tool_name: str,
    tool_input: dict[str, Any] | None = None,
) -> Generator[Span, None, None]:
    """Context manager that starts a child span named ``tool.<tool_name>``.

    Attributes set on entry:
    - ``openinference.span.kind`` = "TOOL"
    - ``tool.name`` = tool_name
    - ``tool.parameters`` = JSON-serialised *tool_input* (if provided)

    The caller should call ``set_output(span, ...)`` before exiting if the
    result is available.

    Usage::

        with tool_span(tracer, "Read", {"file_path": "/foo.py"}) as span:
            result = do_work()
            set_output(span, result)
    """
    span_name = f"tool.{tool_name}"
    span = tracer.start_span(span_name)
    try:
        set_kind(span, "TOOL")
        try:
            span.set_attribute(_TOOL_NAME, tool_name)
        except Exception:  # noqa: BLE001
            pass
        if tool_input is not None:
            try:
                span.set_attribute(_TOOL_PARAMETERS, json.dumps(tool_input, default=str))
            except Exception:  # noqa: BLE001
                pass
        yield span
    finally:
        span.end()
