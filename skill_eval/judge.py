"""C5: Real judge backed by claude-haiku-4-5.

Scores one criterion for one taker result on a 0-20 anchored rubric using a
single synchronous Anthropic call.  The response is expected as strict JSON;
parsing is robust with a regex fallback and the score is always clamped to
[0, 20].
"""

import json
import re

import anthropic
from opentelemetry import trace

from skill_eval.contracts import JudgeInput, JudgeScore
from skill_eval.tracing import set_input, set_kind, set_output, set_tokens

# ---------------------------------------------------------------------------
# Per-criterion anchored rubric (0 / 5 / 10 / 15 / 20)
# Taken verbatim from docs/superpowers/specs/2026-06-08-flagship-comparison.md
# ---------------------------------------------------------------------------

_RUBRIC: dict[str, dict[int, str]] = {
    "correctness": {
        0: "not implemented / completely wrong",
        5: "happy path only; wrong on the gold's key decisions",
        10: "partially correct, misses several decisions",
        15: "matches most gold behavior, one minor miss",
        20: "matches ALL gold behavior incl. edge cases",
    },
    "completeness": {
        0: "nothing",
        5: "stub/trivial",
        10: "core done, edges missing",
        15: "nearly all done",
        20: "fully complete per gold",
    },
    "distance_to_gold": {
        0: "unrelated diff",
        5: "superficially related",
        10: "same shape, different logic",
        15: "close, small deviations",
        20: "semantically equivalent to gold diff",
    },
    "code_quality": {
        0: "broken/unreadable",
        5: "works but messy, no tests",
        10: "acceptable",
        15: "clean, readable",
        20: "idiomatic, tested, clear",
    },
    "question_quality": {
        0: "asked nothing or irrelevant",
        5: "1 vague question",
        10: "asked some, missed critical ambiguities",
        15: "asked most critical missing-info questions",
        20: "surfaced ALL critical ambiguities, clear & specific",
    },
    "approach": {
        0: "chaotic / wrong path / thrashing",
        5: "disorganized",
        10: "reasonable",
        15: "solid: read context + clarified",
        20: "exemplary: read -> clarified every ambiguity -> test-first -> minimal",
    },
}

_CRITERION_DEFINITION: dict[str, str] = {
    "correctness": (
        "Whether the taker's implementation satisfies the stated requirement "
        "and matches the gold diff's intent, including edge cases and key decisions."
    ),
    "completeness": (
        "How much of the required change was implemented. "
        "Penalise missing parts, stub-only implementations, or unhandled cases."
    ),
    "distance_to_gold": (
        "Semantic similarity between the taker's diff and the gold diff. "
        "Focus on whether the logic is equivalent, not just surface textual similarity."
    ),
    "code_quality": (
        "Readability, idiomaticity, and maintainability of the taker's changes. "
        "Consider naming, structure, test coverage, and use of language features."
    ),
    "question_quality": (
        "Quality of the clarifying questions the taker asked before implementing. "
        "Derive the CRITICAL AMBIGUITIES by comparing what is under-specified in the "
        "task_brief against the concrete decisions encoded in the gold diff. "
        "Then score whether the taker's questions surfaced those critical missing-info "
        "gaps. Questions that are vague, irrelevant, or that guess instead of asking "
        "score lower. A taker that asked nothing scores 0 on this criterion."
    ),
    "approach": (
        "Overall strategy and efficiency: did the taker follow a sensible path — "
        "reading existing code, clarifying ambiguities, writing tests before code, "
        "implementing minimally — with minimal thrashing?"
    ),
}


def _build_prompt(ji: JudgeInput) -> str:
    """Build the judge prompt for a single criterion evaluation.

    This is a pure function (no I/O) so it can be unit-tested without any
    API call.
    """
    criterion = ji.criterion.value
    rubric = _RUBRIC.get(criterion, {})
    definition = _CRITERION_DEFINITION.get(criterion, "")

    # Build the anchored scale text
    scale_lines = "\n".join(
        f"  {score:2d}  = {descriptor}" for score, descriptor in sorted(rubric.items())
    )

    # Format the taker's clarifying questions
    if ji.taker.questions:
        questions_block = "\n".join(f"  Q{i + 1}: {q}" for i, q in enumerate(ji.taker.questions))
        questions_text = (
            f"The taker asked {len(ji.taker.questions)} clarifying question(s):\n{questions_block}"
        )
    else:
        questions_text = "The taker asked NO clarifying questions."

    # For question_quality: add explicit instruction about deriving ambiguities
    if criterion == "question_quality":
        criterion_extra = (
            "\n\nIMPORTANT for question_quality scoring:\n"
            "1. First, compare the task_brief (under-specified) to the gold_diff "
            "(which encodes concrete decisions such as rounding rules, boundary handling, "
            "month-length definition, etc.) to identify all CRITICAL AMBIGUITIES — "
            "decisions the brief leaves open that the gold resolves.\n"
            "2. Then examine the taker's questions above and assess how many of those "
            "critical ambiguities were explicitly surfaced with clear, specific questions.\n"
            "3. Score based on the rubric anchors: 0 if nothing/irrelevant, up to 20 "
            "if ALL critical ambiguities were surfaced with clarity."
        )
    else:
        criterion_extra = ""

    return f"""\
You are an expert code-review judge. Score the taker's work on the criterion \
**{criterion}** for the following task.

## Criterion definition
{definition}{criterion_extra}

## Anchored 0 / 5 / 10 / 15 / 20 scale
{scale_lines}

Note: the taker may not have finished due to budget limits (token cap, turn cap, \
or wall-clock). Judge only what is present in their diff and questions.

---
## Task brief (may be deliberately under-specified)
{ji.task_brief}

## Gold diff (reference solution — encodes the authoritative decisions)
```diff
{ji.gold_diff}
```

## Taker diff (what the taker submitted)
```diff
{ji.taker.diff}
```

## Taker's clarifying questions
{questions_text}

Stop reason: {ji.taker.stop_reason.value}

---
Reply with ONLY a valid JSON object — no markdown fences, no extra text:
{{"score": <integer 0-20 matching one of the anchors>, "rationale": "<one concise sentence>"}}
"""


def _parse_response(text: str) -> tuple[int, str]:
    """Extract (score, rationale) from the model response.

    Tries json.loads on the first {...} block; falls back to regex for score.
    Score is always clamped to [0, 20].
    """
    # Attempt 1: find the first JSON object in the text
    brace_match = re.search(r"\{[^}]*\}", text, re.DOTALL)
    if brace_match:
        try:
            data = json.loads(brace_match.group())
            score = int(data.get("score", 0))
            rationale = str(data.get("rationale", "")).strip() or "no rationale provided"
            return max(0, min(20, score)), rationale
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

    # Attempt 2: regex fallback — grab the first integer after "score"
    score_match = re.search(r'"?score"?\s*[:=]\s*(\d+)', text, re.IGNORECASE)
    score = int(score_match.group(1)) if score_match else 0
    return max(0, min(20, score)), "rationale could not be parsed"


def run_judge(ji: JudgeInput, model: str) -> JudgeScore:
    """Score one criterion for one taker result on a 0-20 anchored rubric.

    Parameters
    ----------
    ji:
        All context needed for the judge.
    model:
        Claude model to use (must be passed explicitly; never defaulted).
    """
    client = anthropic.Anthropic()
    prompt = _build_prompt(ji)

    # Enrich the current judge span (set by orchestrator via start_as_current_span)
    judge_span = trace.get_current_span()
    set_kind(judge_span, "LLM")
    set_input(judge_span, prompt)

    response = client.messages.create(
        model=model,
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = "".join(block.text for block in response.content if hasattr(block, "text"))
    score, rationale = _parse_response(raw_text)

    # Enrich with output and token counts
    set_output(judge_span, f"score={score} | {rationale}")
    usage = getattr(response, "usage", None)
    if usage is not None:
        prompt_tokens = getattr(usage, "input_tokens", 0) or 0
        completion_tokens = getattr(usage, "output_tokens", 0) or 0
        set_tokens(judge_span, int(prompt_tokens), int(completion_tokens))

    return JudgeScore(criterion=ji.criterion, score=score, rationale=rationale)
