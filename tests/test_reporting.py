from skill_eval.contracts import (
    Arm,
    ArmReport,
    ComparisonReport,
    Criterion,
    JudgeScore,
    RunConfig,
    RunMetrics,
)
from skill_eval.reporting import scores_table, verdict_line


def _report():
    m = RunMetrics(100, 60, 40, 1.2, 3, 1)

    def arm(a, base):
        scores = [JudgeScore(c, base + i, "ok") for i, c in enumerate(Criterion)]
        return ArmReport(a, "claude-haiku-4-5", m, scores, sum(s.score for s in scores))

    cfg = RunConfig("a", "b", "/r", "x", "/b", "/c", ("claude-haiku-4-5",))
    return ComparisonReport(cfg, [arm(Arm.BASELINE, 8), arm(Arm.CHALLENGER, 12)], "challenger wins")


def test_scores_table_shape():
    rows = scores_table(_report())
    # one row per criterion, columns per arm
    assert len(rows) == len(Criterion)
    assert "baseline" in rows[0] and "challenger" in rows[0]


def test_verdict_line():
    assert "challenger" in verdict_line(_report()).lower()
