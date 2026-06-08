"""C3: Real reactive HITL simulator backed by claude-haiku-4-5.

The simulator is a closure that captures the gold context (after_dir files +
task_brief) and answers each taker question with a single synchronous Anthropic
call.  It is deliberately *reactive-only*: it answers at the requirement level
and never volunteers implementation details or writes code for the taker.
"""

from pathlib import Path

import anthropic

from skill_eval.contracts import AskFn

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
        response = client.messages.create(
            model=model,
            max_tokens=400,
            system=system,
            messages=[{"role": "user", "content": question}],
        )
        return "".join(block.text for block in response.content if hasattr(block, "text"))

    return ask
