import pytest
from pydantic import ValidationError

from skill_eval.contracts import (
    Arm,
    ArmReport,
    ComparisonReport,
    Criterion,
    JudgeInput,
    JudgeScore,
    RunConfig,
    RunMetrics,
    StopReason,
    TakerResult,
    Workspace,
)


def test_enum_values():
    assert Arm.BASELINE.value == "baseline"
    assert Arm.CHALLENGER.value == "challenger"
    assert StopReason.MAX_TURNS.value == "max_turns"
    assert {c.value for c in Criterion} == {
        "correctness",
        "completeness",
        "distance_to_gold",
        "code_quality",
        "question_quality",
        "approach",
    }
    assert {s.value for s in StopReason} == {
        "completed",
        "max_turns",
        "max_tokens",
        "wall_clock",
        "error",
    }


def test_runconfig_defaults_and_frozen():
    cfg = RunConfig(
        before_hash="aaa",
        after_hash="bbb",
        repo_path="/repo",
        task_brief="Implement feature X",
        baseline_skill_path="/skills/base",
        challenger_skill_path="/skills/chal",
        models=("claude-opus-4-8",),
    )
    assert cfg.max_turns == 30
    assert cfg.max_tokens is None
    assert cfg.wall_clock_seconds is None
    assert cfg.thinking_budget is None
    with pytest.raises(ValidationError):
        cfg.max_turns = 5  # type: ignore[misc]


def test_runconfig_thinking_budget():
    """thinking_budget can be set to a positive integer; defaults to None."""
    cfg_no_thinking = RunConfig(
        before_hash="a",
        after_hash="b",
        repo_path="/r",
        task_brief="t",
        baseline_skill_path="/b",
        challenger_skill_path="/c",
        models=("claude-haiku-4-5",),
    )
    assert cfg_no_thinking.thinking_budget is None

    cfg_with_thinking = RunConfig(
        before_hash="a",
        after_hash="b",
        repo_path="/r",
        task_brief="t",
        baseline_skill_path="/b",
        challenger_skill_path="/c",
        models=("claude-haiku-4-5",),
        thinking_budget=2048,
    )
    assert cfg_with_thinking.thinking_budget == 2048


def test_workspace_frozen():
    ws = Workspace(arm=Arm.BASELINE, taker_dir="/t", after_dir="/a", gold_diff="diff")
    with pytest.raises(ValidationError):
        ws.taker_dir = "/x"  # type: ignore[misc]


def test_full_report_composition():
    metrics = RunMetrics(
        total_tokens=10,
        input_tokens=6,
        output_tokens=4,
        wall_seconds=1.5,
        num_turns=2,
        num_questions=1,
    )
    taker = TakerResult(
        arm=Arm.CHALLENGER,
        model="claude-opus-4-8",
        diff="patch",
        transcript=({"role": "user", "content": "hi"},),
        questions=("which db?",),
        stop_reason=StopReason.COMPLETED,
        metrics=metrics,
    )
    assert taker.metrics.num_questions == 1

    score = JudgeScore(criterion=Criterion.CORRECTNESS, score=20, rationale="matches gold")
    arm_report = ArmReport(
        arm=Arm.CHALLENGER,
        model="claude-opus-4-8",
        metrics=metrics,
        scores=[score],
        total_score=20,
    )
    # default questions is empty tuple
    assert arm_report.questions == ()

    arm_report_with_questions = ArmReport(
        arm=Arm.CHALLENGER,
        model="claude-opus-4-8",
        metrics=metrics,
        scores=[score],
        total_score=20,
        questions=("Which DB?", "Any performance constraints?"),
    )
    assert arm_report_with_questions.questions == ("Which DB?", "Any performance constraints?")

    report = ComparisonReport(
        config=RunConfig(
            before_hash="a",
            after_hash="b",
            repo_path="/repo",
            task_brief="x",
            baseline_skill_path="/b",
            challenger_skill_path="/c",
            models=("claude-opus-4-8",),
        ),
        arms=[arm_report],
        pairwise_verdict="challenger wins",
    )
    assert report.arms[0].scores[0].score == 20


def test_judge_input_constructs():
    metrics = RunMetrics(
        total_tokens=0,
        input_tokens=0,
        output_tokens=0,
        wall_seconds=0.0,
        num_turns=0,
        num_questions=0,
    )
    taker = TakerResult(
        arm=Arm.BASELINE,
        model="m",
        diff="",
        transcript=(),
        questions=(),
        stop_reason=StopReason.MAX_TURNS,
        metrics=metrics,
    )
    ji = JudgeInput(
        criterion=Criterion.COMPLETENESS,
        task_brief="x",
        gold_diff="gold",
        after_dir="/a",
        taker=taker,
    )
    assert ji.criterion is Criterion.COMPLETENESS


def test_callable_aliases_importable():
    from skill_eval.contracts import AskFn, MakeSimulator  # noqa: F401


def test_phase_a_aliases_importable():
    from skill_eval.contracts import EventFn, JudgeFn, TakerFn  # noqa: F401
