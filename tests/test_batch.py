from skill_eval.batch import run_batch
from skill_eval.contracts import Arm, ComparisonReport, Criterion
from skill_eval.sample_cases import build_sample_cases
from skill_eval.simulated import sim_make_simulator, sim_run_judge, sim_run_taker


def test_run_batch_returns_3_reports(tmp_path):
    cfgs = build_sample_cases(str(tmp_path))[:3]
    reports = run_batch(
        cfgs,
        taker_fn=sim_run_taker,
        simulator_factory=sim_make_simulator,
        judge_fn=sim_run_judge,
        max_cases=2,
    )
    assert len(reports) == 3
    for r in reports:
        assert isinstance(r, ComparisonReport)


def test_run_batch_arms_and_scores(tmp_path):
    cfgs = build_sample_cases(str(tmp_path))[:3]
    reports = run_batch(
        cfgs,
        taker_fn=sim_run_taker,
        simulator_factory=sim_make_simulator,
        judge_fn=sim_run_judge,
        max_cases=2,
    )
    for report in reports:
        arms = {a.arm for a in report.arms}
        assert arms == {Arm.BASELINE, Arm.CHALLENGER}
        for arm_report in report.arms:
            assert len(arm_report.scores) == len(list(Criterion))


def test_run_batch_per_case_variance(tmp_path):
    """Challenger total scores must not all be identical across 3 cases."""
    cfgs = build_sample_cases(str(tmp_path))[:3]
    reports = run_batch(
        cfgs,
        taker_fn=sim_run_taker,
        simulator_factory=sim_make_simulator,
        judge_fn=sim_run_judge,
        max_cases=2,
    )
    challenger_totals = [a.total_score for r in reports for a in r.arms if a.arm is Arm.CHALLENGER]
    assert len(set(challenger_totals)) > 1, f"All challenger totals identical: {challenger_totals}"


def test_run_batch_on_event(tmp_path):
    """on_event callback receives events tagged with case index."""
    cfgs = build_sample_cases(str(tmp_path))[:2]
    events = []
    run_batch(
        cfgs,
        taker_fn=sim_run_taker,
        simulator_factory=sim_make_simulator,
        judge_fn=sim_run_judge,
        max_cases=2,
        on_event=events.append,
    )
    assert events, "no events emitted"
    case_indices = {e.get("case") for e in events}
    assert case_indices == {0, 1}, f"expected case indices 0 and 1, got {case_indices}"


def test_run_batch_preserves_order(tmp_path):
    """Output order must match input order regardless of execution order."""
    cfgs = build_sample_cases(str(tmp_path))[:3]
    reports = run_batch(
        cfgs,
        taker_fn=sim_run_taker,
        simulator_factory=sim_make_simulator,
        judge_fn=sim_run_judge,
        max_cases=3,
    )
    for i, (cfg, report) in enumerate(zip(cfgs, reports, strict=True)):
        assert report.config.repo_path == cfg.repo_path, (
            f"Position {i}: expected {cfg.repo_path}, got {report.config.repo_path}"
        )
