"""Deterministic simulated components for Phase A walking skeleton.

These make no API calls. They exercise the real workflow shape so the orchestrator,
sandbox, and live UI all behave as they will in Phase B — just without LLM cost.
"""

import subprocess
import time
from pathlib import Path

from skill_eval.contracts import (
    Arm,
    AskFn,
    JudgeInput,
    JudgeScore,
    RunConfig,
    RunMetrics,
    StopReason,
    TakerResult,
    Workspace,
)

# ---------------------------------------------------------------------------
# Simulator (Component 3 stand-in)
# ---------------------------------------------------------------------------

_CANNED_ANSWERS = [
    "Yes, the function should return the sum of the two arguments.",
    "Correct — return `a + b` instead of `a - b`.",
    "The fix is straightforward: change the subtraction to addition.",
    "You are on the right track. The expected output for add(2, 3) is 5.",
    "The test expects add(2, 3) == 5, so return a + b.",
]


def sim_make_simulator(after_dir: str, task_brief: str, model: str) -> AskFn:
    """Return a canned AskFn that gives helpful, deterministic answers."""
    call_count = [0]

    def ask(question: str) -> str:
        idx = call_count[0] % len(_CANNED_ANSWERS)
        call_count[0] += 1
        # Vary by question length to look slightly dynamic
        variant = _CANNED_ANSWERS[(idx + len(question)) % len(_CANNED_ANSWERS)]
        return variant

    return ask


# ---------------------------------------------------------------------------
# Taker (Component 2 stand-in)
# ---------------------------------------------------------------------------

_CLARIFYING_QUESTIONS = [
    "Should the function return the sum of the two arguments?",
    "Is the fix as simple as changing `a - b` to `a + b`?",
    "Does the test suite already cover the add function?",
]


def sim_run_taker(
    ws: Workspace,
    model: str,
    skill_path: str,
    cfg: RunConfig,
    ask_fn: AskFn,
) -> TakerResult:
    """Simulate a taker: ask a clarifying question, write a fix, return result."""
    # Determine if this is the challenger arm for slightly better output
    is_challenger = ws.arm is Arm.CHALLENGER

    # Ask at least one clarifying question (the contract requires num_questions >= 1)
    questions_asked: list[str] = []
    num_q = 2 if is_challenger else 1
    for i in range(num_q):
        q = _CLARIFYING_QUESTIONS[i % len(_CLARIFYING_QUESTIONS)]
        ask_fn(q)
        questions_asked.append(q)

    # Simulate thinking time
    time.sleep(0.05)

    # Write a partial/full fix into the taker worktree
    calc_path = Path(ws.taker_dir) / "calculator.py"
    if is_challenger:
        # Challenger produces the correct fix
        calc_path.write_text("def add(a, b):\n    return a + b\n")
    else:
        # Baseline produces a partial fix (comment removed, still correct but minimal)
        calc_path.write_text("def add(a, b):\n    return a + b  # fixed\n")

    # Compute actual git diff of what the taker changed
    try:
        result = subprocess.run(
            ["git", "-C", ws.taker_dir, "diff"],
            capture_output=True,
            text=True,
        )
        diff = result.stdout
    except Exception:
        diff = "+ return a + b"

    # Build fabricated-but-sensible metrics
    # Challenger uses slightly more tokens/turns (more thorough)
    if is_challenger:
        metrics = RunMetrics(
            total_tokens=320,
            input_tokens=180,
            output_tokens=140,
            wall_seconds=0.35,
            num_turns=4,
            num_questions=len(questions_asked),
        )
    else:
        metrics = RunMetrics(
            total_tokens=210,
            input_tokens=130,
            output_tokens=80,
            wall_seconds=0.25,
            num_turns=3,
            num_questions=len(questions_asked),
        )

    transcript: tuple[dict, ...] = (
        {"role": "user", "content": cfg.task_brief},
        {
            "role": "assistant",
            "content": f"I'll fix the add function. Questions: {len(questions_asked)}",
        },
    )

    return TakerResult(
        arm=ws.arm,
        model=model,
        diff=diff,
        transcript=transcript,
        questions=tuple(questions_asked),
        stop_reason=StopReason.COMPLETED,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Judge (Component 5 stand-in)
# ---------------------------------------------------------------------------

# Base scores per criterion for a "correct" diff (contains `a + b`)
_BASE_SCORES: dict[str, int] = {
    "correctness": 17,
    "completeness": 15,
    "distance_to_gold": 16,
    "code_quality": 14,
    "question_quality": 13,
    "approach": 14,
}

# Bonus for challenger arm
_CHALLENGER_BONUS = 2

# Penalty when the diff does NOT contain the fix
_NO_FIX_PENALTY = 8


def sim_run_judge(ji: JudgeInput, model: str) -> JudgeScore:
    """Return a deterministic 0-20 score for one criterion."""
    criterion_key = ji.criterion.value
    has_fix = "a + b" in ji.taker.diff
    is_challenger = ji.taker.arm is Arm.CHALLENGER

    base = _BASE_SCORES.get(criterion_key, 12)
    score = base
    if not has_fix:
        score = max(0, score - _NO_FIX_PENALTY)
    if is_challenger:
        score = min(20, score + _CHALLENGER_BONUS)

    rationale = (
        f"[simulated] {criterion_key}: "
        + ("fix present" if has_fix else "fix absent")
        + f", arm={ji.taker.arm.value}"
        + f", score={score}/20"
    )

    return JudgeScore(criterion=ji.criterion, score=score, rationale=rationale)
