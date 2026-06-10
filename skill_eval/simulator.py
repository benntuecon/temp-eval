"""C3: Real reactive HITL simulator backed by claude-haiku-4-5.

The simulator is a closure that captures the gold context (after_dir files +
task_brief) and answers each taker question with a single synchronous Anthropic
call.  It is deliberately *reactive-only*: it answers at the requirement level
and never volunteers implementation details or writes code for the taker.
"""

from pathlib import Path

import anthropic

from skill_eval.contracts import AskFn
from skill_eval.tracing import (
    get_tracer,
    set_cache_tokens,
    set_input,
    set_invocation_parameters,
    set_kind,
    set_messages,
    set_metadata,
    set_model_name,
    set_output,
    set_tokens,
)

# Maximum total characters of file content included in the gold context.
_MAX_GOLD_CHARS = 6000

_PERSONA = (
    "You are the human stakeholder who requested this task. "
    "You know the intended outcome. "
    "Answer the engineer's question helpfully and concisely. "
    "Do NOT write their code or dictate the implementation line-by-line — "
    "answer at the requirement level. "
    "Only answer what is asked."
)


def _build_gold_context(after_dir: str, task_brief: str) -> str:
    """Return a bounded string describing the gold tree + task brief."""
    lines: list[str] = [
        "## Task brief",
        task_brief,
        "",
        "## Gold implementation (reference files)",
    ]
    total_chars = 0
    root = Path(after_dir)
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        try:
            content = path.read_text(errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root)
        header = f"\n### {rel}\n"
        snippet = content[: max(0, _MAX_GOLD_CHARS - total_chars)]
        lines.append(header + snippet)
        total_chars += len(header) + len(snippet)
        if total_chars >= _MAX_GOLD_CHARS:
            lines.append("\n[...gold context truncated for length...]")
            break
    return "\n".join(lines)


def make_simulator(after_dir: str, task_brief: str, model: str) -> AskFn:
    """Return an AskFn that answers taker questions using the gold context.

    Parameters
    ----------
    after_dir:
        Path to the read-only gold worktree (@after_hash).
    task_brief:
        The original requirement / PRD text.
    model:
        Claude model to use (must be passed explicitly; never defaulted).
    """
    gold_context = _build_gold_context(after_dir, task_brief)
    system = f"{_PERSONA}\n\n{gold_context}"
    client = anthropic.Anthropic()

    def ask(question: str) -> str:
        # Trace the simulator's own LLM call as a nested LLM span. Without this,
        # the HITL stakeholder agent is invisible in Phoenix — only the taker's
        # ask_question TOOL latency is captured, not the model call behind it.
        with get_tracer().start_as_current_span("llm.simulator") as span:
            set_kind(span, "LLM")
            set_model_name(span, model)
            set_input(span, question)
            set_invocation_parameters(span, {"model": model, "max_tokens": 400, "temperature": 0})
            set_metadata(span, {"role": "hitl_simulator", "gold_context_chars": len(system)})

            # temperature=0: the stakeholder must answer the same question the
            # same way across arms/repeats, or it becomes a confound.
            response = client.messages.create(
                model=model,
                max_tokens=400,
                temperature=0,
                system=system,
                messages=[{"role": "user", "content": question}],
            )
            answer = "".join(block.text for block in response.content if hasattr(block, "text"))

            set_output(span, answer)
            set_messages(
                span,
                input_messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": question},
                ],
                output_messages=[{"role": "assistant", "content": answer}],
            )
            usage = getattr(response, "usage", None)
            if usage is not None:
                set_tokens(
                    span,
                    int(getattr(usage, "input_tokens", 0) or 0),
                    int(getattr(usage, "output_tokens", 0) or 0),
                )
                set_cache_tokens(
                    span,
                    int(getattr(usage, "cache_read_input_tokens", 0) or 0),
                    int(getattr(usage, "cache_creation_input_tokens", 0) or 0),
                )
            return answer

    return ask
