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
# Anchored rubric text (shared across criteria, specialised per criterion)
# ---------------------------------------------------------------------------

_RUBRIC_COMMON = """\
Score on a 0-20 integer scale:
  0  = nothing useful was produced / criterion entirely missing
  5  = very poor / major gaps
 10  = partial — some elements correct but significant issues remain
 15  = good — mostly correct with minor gaps or style issues
 20  = excellent — matches or exceeds the gold reference

Anchor examples:
  0  → empty diff or completely wrong approach
 10  → half the changes present, key logic still incorrect
 20  → diff is functionally identical or better than gold
"""

_CRITERION_GUIDANCE: dict[str, str] = {
    "correctness": (
        "Focus on whether the taker's diff satisfies the stated requirement"
        " and matches the gold diff's intent."
    ),
    "completeness": (
        "Focus on how much of the required change was implemented; penalise missing parts."
    ),
    "distance_to_gold": "Focus on semantic similarity between the taker diff and the gold diff.",
    "code_quality": (
        "Focus on readability, idiomaticity, and maintainability of the taker's changes."
    ),
    "question_quality": (
        "Focus on whether the clarifying questions the taker asked were relevant and well-targeted."
    ),
    "approach": (
        "Focus on the overall strategy and efficiency:"
        " did the taker take a sensible path with minimal thrashing?"
    ),
}


def _build_prompt(ji: JudgeInput) -> str:
    guidance = _CRITERION_GUIDANCE.get(ji.criterion.value, "")
    questions_note = (
        f"The taker asked {len(ji.taker.questions)} clarifying question(s)."
        if ji.taker.questions
        else "The taker asked no clarifying questions."
    )
    return f"""\
You are an expert code-review judge.  Score the taker's work on the criterion \
**{ji.criterion.value}** for the following task.

{_RUBRIC_COMMON}
Criterion guidance: {guidance}

---
## Task brief
{ji.task_brief}

## Gold diff (reference solution)
```diff
{ji.gold_diff}
```

## Taker diff (what was submitted)
```diff
{ji.taker.diff}
```

## Additional context
{questions_note}
Stop reason: {ji.taker.stop_reason.value}

---
Reply with **only** valid JSON — no markdown fences, no extra text:
{{"score": <integer 0-20>, "rationale": "<one concise sentence>"}}
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
        max_tokens=300,
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
