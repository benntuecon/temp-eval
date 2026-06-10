from skill_eval.contracts import Arm, ComparisonReport, Criterion
from skill_eval.orchestrator import run_eval
from skill_eval.sample_repo import build_sample_repo
from skill_eval.simulated import sim_make_simulator, sim_run_judge, sim_run_taker


def test_run_eval_simulated_end_to_end(tmp_path):
    cfg = build_sample_repo(str(tmp_path / "repo"))
    events = []
    report = run_eval(
        cfg,
        taker_fn=sim_run_taker,
        simulator_factory=sim_make_simulator,
        judge_fn=sim_run_judge,
        on_event=events.append,
    )
    assert isinstance(report, ComparisonReport)
    arms = {a.arm for a in report.arms}
    assert arms == {Arm.BASELINE, Arm.CHALLENGER}
    for arm_report in report.arms:
        # one score per criterion
        assert {s.criterion for s in arm_report.scores} == set(Criterion)
        assert arm_report.total_score == sum(s.score for s in arm_report.scores)
        # questions is always a tuple
        assert isinstance(arm_report.questions, tuple)
    # simulated taker always asks >= 1 question per arm, so at least one arm non-empty
    assert any(len(ar.questions) > 0 for ar in report.arms)
    # the taker's diff and stop_reason survive into the report
    for arm_report in report.arms:
        assert arm_report.diff  # simulated taker writes a marker change
        assert arm_report.stop_reason == "completed"
        # Q&A pairs: one per question, with a non-empty simulator answer
        assert len(arm_report.qa) == len(arm_report.questions)
        assert all(q and a for q, a in arm_report.qa)
    assert report.pairwise_verdict
    # events captured the workflow stages
    stages = {e.get("stage") for e in events}
    assert {"sandbox", "taker", "judge", "report"} <= stages


def test_k_judges_median_aggregation(tmp_path):
    """judges_per_criterion=3 fans out 3 replicates per cell but the report
    still carries ONE aggregated (median) score per criterion, with the
    replicate spread recorded in the rationale."""
    import dataclasses

    cfg = dataclasses.replace(build_sample_repo(str(tmp_path / "repo")), judges_per_criterion=3)
    report = run_eval(
        cfg,
        taker_fn=sim_run_taker,
        simulator_factory=sim_make_simulator,
        judge_fn=sim_run_judge,
    )
    for arm_report in report.arms:
        assert {s.criterion for s in arm_report.scores} == set(Criterion)
        assert len(arm_report.scores) == len(Criterion)  # aggregated, not 18
        for s in arm_report.scores:
            assert s.rationale.startswith("[k=3, scores=")
        assert arm_report.total_score == sum(s.score for s in arm_report.scores)


def test_judge_model_decoupling_reaches_judges(tmp_path):
    """cfg.judge_model (not the taker model) must be handed to judge_fn."""
    import dataclasses

    seen_models: list[str] = []

    def spy_judge(ji, model):
        seen_models.append(model)
        return sim_run_judge(ji, model)

    cfg = dataclasses.replace(
        build_sample_repo(str(tmp_path / "repo")), judge_model="claude-sonnet-4-6"
    )
    run_eval(
        cfg,
        taker_fn=sim_run_taker,
        simulator_factory=sim_make_simulator,
        judge_fn=spy_judge,
    )
    assert seen_models and set(seen_models) == {"claude-sonnet-4-6"}


def test_reducer_counts(tmp_path):
    """Send-based fan-out must produce exactly 2 taker_results and 12 score entries."""
    cfg = build_sample_repo(str(tmp_path / "repo"))
    from skill_eval.orchestrator import _GRAPH
    from skill_eval.sandbox import cleanup_workspaces, prepare_workspaces

    spaces = prepare_workspaces(cfg)
    try:
        import asyncio

        initial_state = {
            "cfg": cfg,
            "taker_fn": sim_run_taker,
            "simulator_factory": sim_make_simulator,
            "judge_fn": sim_run_judge,
            "on_event": None,
            "spaces": spaces,
            "taker_results": [],
            "scores": [],
        }
        final_state = asyncio.run(_GRAPH.ainvoke(initial_state))
    finally:
        cleanup_workspaces(spaces)

    # 2 arms × 1 taker each
    assert len(final_state["taker_results"]) == 2
    taker_arms = {arm for arm, _ in final_state["taker_results"]}
    assert taker_arms == {Arm.BASELINE, Arm.CHALLENGER}

    # 2 arms × 6 criteria = 12 score entries (now 3-tuples: arm, score, span_id)
    assert len(final_state["scores"]) == 12
    score_arm_criterion_pairs = {
        (arm.value, score.criterion.value) for arm, score, _sid in final_state["scores"]
    }
    expected_pairs = {(arm.value, c.value) for arm in Arm for c in Criterion}
    assert score_arm_criterion_pairs == expected_pairs
    # span_ids are 16-char hex strings
    for _arm, _score, sid in final_state["scores"]:
        assert isinstance(sid, str) and len(sid) == 16
