"""Deterministic simulated components for Phase A walking skeleton.

These make no API calls. They exercise the real workflow shape so the orchestrator,
sandbox, and live UI all behave as they will in Phase B — just without LLM cost.

Scoring is deterministic via sha256 of (task_brief, arm, criterion) so different
tasks and criteria yield different scores, with a small challenger bias on average.
"""

import hashlib
from collections.abc import Callable
from pathlib import Path

from skill_eval import git_ops
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
# Deterministic hash helper
# ---------------------------------------------------------------------------


def _stable_hash_int(text: str) -> int:
    """Return a stable integer hash of *text* using sha256 (not Python's hash())."""
    return int(hashlib.sha256(text.encode()).hexdigest(), 16)


# ---------------------------------------------------------------------------
# Simulator (Component 3 stand-in)
# ---------------------------------------------------------------------------

_CANNED_ANSWERS = [
    "Yes, the function should return the correct result as described in the task.",
    "Correct — the implementation has the bug described; fix it as specified.",
    "The fix is straightforward: apply the change described in the task brief.",
    "You are on the right track. The expected behaviour matches the task brief.",
    "The test asserts the correct value; implement the function accordingly.",
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
    "Can you confirm the expected return value for the function under test?",
    "Is there a specific edge case I should handle beyond the failing test?",
    "Should I preserve the existing function signature exactly?",
    "Are there any performance constraints I should be aware of?",
]


def sim_run_taker(
    ws: Workspace,
    model: str,
    skill_path: str,
    cfg: RunConfig,
    ask_fn: AskFn,
    on_event: Callable[[dict], None] | None = None,
) -> TakerResult:
    """Simulate a taker: ask clarifying questions, write a marker, return result."""
    is_challenger = ws.arm is Arm.CHALLENGER

    def _emit_stream(kind: str, **payload: object) -> None:
        if on_event is None:
            return
        try:
            on_event({"stage": "taker_stream", "kind": kind, "arm": ws.arm.value, **payload})
        except Exception:  # noqa: BLE001
            pass

    # Synthetic thinking so the free/simulated path exercises the live
    # hover-thinking panel exactly like a real run would.
    _emit_stream(
        "thinking",
        text=f"[simulated] Reading the project as the {ws.arm.value} arm; "
        f"brief: {cfg.task_brief[:80]}…",
    )
    _emit_stream("tool", tool="Read", summary='{"file": "the project source"}')

    # Derive a task-specific seed from the brief so per-case metrics differ
    task_seed = _stable_hash_int(cfg.task_brief)

    # Number of questions: challenger asks 2-4, baseline asks 1-2 (task-dependent)
    if is_challenger:
        num_q = 2 + (task_seed % 3)  # 2, 3, or 4
    else:
        num_q = 1 + (task_seed % 2)  # 1 or 2

    questions_asked: list[str] = []
    qa_pairs: list[tuple[str, str]] = []
    for i in range(num_q):
        q = _CLARIFYING_QUESTIONS[i % len(_CLARIFYING_QUESTIONS)]
        answer = ask_fn(q)
        questions_asked.append(q)
        qa_pairs.append((q, answer))

    # Write a small marker change into the worktree so diff is non-empty.
    # Find the first .py file (excluding test files) and append a comment,
    # or fall back to writing a SOLUTION_NOTES.md.
    taker_path = Path(ws.taker_dir)
    py_files = sorted(f for f in taker_path.glob("*.py") if not f.name.startswith("test_"))
    if py_files:
        target = py_files[0]
        arm_label = ws.arm.value
        brief_snippet = cfg.task_brief[:40].replace("\n", " ")
        target.write_text(target.read_text() + f"\n# [simulated {arm_label}] {brief_snippet}\n")
    else:
        (taker_path / "SOLUTION_NOTES.md").write_text(
            f"# Solution Notes\n\nArm: {ws.arm.value}\nTask: {cfg.task_brief[:80]}\n"
        )

    # Compute actual git diff of what the taker changed
    try:
        diff = git_ops.diff_workdir(ws.taker_dir)
    except Exception:  # noqa: BLE001
        diff = f"+ # [simulated {ws.arm.value}]"

    # Seed metrics deterministically from task + arm so per-case values differ.
    # Use the lower bits of the hash for token/turn ranges.
    arm_offset = 100 if is_challenger else 0
    base_tokens = 200 + (task_seed % 200) + arm_offset  # 200-499
    input_frac = 55 + (task_seed % 20)  # 55-74% of total are input tokens
    input_tokens = base_tokens * input_frac // 100
    output_tokens = base_tokens - input_tokens
    num_turns = 3 + (task_seed % 4) + (1 if is_challenger else 0)  # 3-7 turns
    wall_secs = 0.1 + (task_seed % 50) / 100.0 + (0.05 if is_challenger else 0.0)

    metrics = RunMetrics(
        total_tokens=base_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        wall_seconds=round(wall_secs, 3),
        num_turns=num_turns,
        num_questions=len(questions_asked),
    )

    transcript: tuple[dict, ...] = (
        {"role": "user", "content": cfg.task_brief},
        {
            "role": "assistant",
            "content": f"I'll implement the fix. Questions asked: {len(questions_asked)}",
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
        qa=tuple(qa_pairs),
    )


# ---------------------------------------------------------------------------
# Judge (Component 5 stand-in)
# ---------------------------------------------------------------------------

# The score for each (task_brief, arm, criterion) is:
#   base = 8 + hash(...) % 12          → band [8, 19]
#   challenger_boost = 1 + hash2 % 3   → +1, +2, or +3 on average
#   but we only apply boost ~70% of the time (hash3 % 10 >= 3)
#   final = clamp(base + boost_if_applied, 0, 20)
#
# This gives challenger a ~+1.4 average advantage while ensuring baseline
# wins a meaningful number of per-(case, criterion) comparisons.

_BOOST_APPLY_THRESHOLD = 3  # hash % 10 >= this → apply boost (7 out of 10 times)


def sim_run_judge(ji: JudgeInput, model: str) -> JudgeScore:
    """Return a deterministic 0-20 score for one criterion using sha256-based hash."""
    criterion_key = ji.criterion.value
    arm_value = ji.taker.arm.value
    brief = ji.task_brief

    # Primary hash: base score in [8, 19]
    h1 = _stable_hash_int(f"{brief}|{arm_value}|{criterion_key}|base")
    base = 8 + (h1 % 12)

    # Challenger boost
    if ji.taker.arm is Arm.CHALLENGER:
        h2 = _stable_hash_int(f"{brief}|{criterion_key}|boost_magnitude")
        boost_magnitude = 1 + (h2 % 3)  # 1, 2, or 3
        h3 = _stable_hash_int(f"{brief}|{criterion_key}|boost_apply")
        apply_boost = (h3 % 10) >= _BOOST_APPLY_THRESHOLD
        score = min(20, base + (boost_magnitude if apply_boost else 0))
    else:
        score = base

    rationale = f"[simulated] {criterion_key}: arm={arm_value}, score={score}/20"

    return JudgeScore(criterion=ji.criterion, score=score, rationale=rationale)
