from skill_eval.contracts import (
    Arm,
    Criterion,
    JudgeInput,
    RunMetrics,
    StopReason,
    TakerResult,
)
from skill_eval.sample_repo import build_sample_repo
from skill_eval.sandbox import cleanup_workspaces, prepare_workspaces
from skill_eval.simulated import sim_make_simulator, sim_run_judge, sim_run_taker


def test_sim_simulator_answers():
    ask = sim_make_simulator(after_dir="/x", task_brief="fix add", model="m")
    answer = ask("Should add return the sum?")
    assert isinstance(answer, str) and answer


def test_sim_taker_asks_and_returns(tmp_path):
    cfg = build_sample_repo(str(tmp_path / "repo"))
    spaces = prepare_workspaces(cfg)
    try:
        asked = []
        ask = lambda q: asked.append(q) or "Yes, return a + b."  # noqa: E731
        res = sim_run_taker(spaces[Arm.CHALLENGER], "m", cfg.challenger_skill_path, cfg, ask)
        assert isinstance(res, TakerResult)
        assert res.arm is Arm.CHALLENGER
        assert len(asked) == res.metrics.num_questions >= 1
        assert res.stop_reason in set(StopReason)
        assert isinstance(res.metrics, RunMetrics)
    finally:
        cleanup_workspaces(spaces)


def test_sim_judge_scores_in_range():
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
        diff="+ return a + b",
        transcript=(),
        questions=(),
        stop_reason=StopReason.COMPLETED,
        metrics=metrics,
    )
    ji = JudgeInput(
        criterion=Criterion.CORRECTNESS,
        task_brief="fix add",
        gold_diff="+ return a + b",
        after_dir="/x",
        taker=taker,
    )
    score = sim_run_judge(ji, "m")
    assert score.criterion is Criterion.CORRECTNESS
    assert 0 <= score.score <= 20
    assert score.rationale
