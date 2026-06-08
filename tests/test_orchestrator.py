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
    assert report.pairwise_verdict
    # events captured the workflow stages
    stages = {e.get("stage") for e in events}
    assert {"sandbox", "taker", "judge", "report"} <= stages
