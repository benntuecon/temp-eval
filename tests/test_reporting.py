from skill_eval.contracts import (
    Arm,
    ArmReport,
    ComparisonReport,
    Criterion,
    JudgeScore,
    RunConfig,
    RunMetrics,
)
from skill_eval.reporting import (
    agent_graph_dot,
    batch_per_case_totals,
    batch_per_criterion_avg,
    batch_win_summary,
    scores_table,
    verdict_line,
)


def _make_report(
    baseline_base: int, challenger_base: int, task_brief: str = "Fix the add function in calculator"
):
    """Build a fake ComparisonReport with deterministic scores."""
    m = RunMetrics(100, 60, 40, 1.2, 3, 1)

    def arm(a, base):
        scores = [JudgeScore(c, base + i, "ok") for i, c in enumerate(Criterion)]
        return ArmReport(a, "claude-haiku-4-5", m, scores, sum(s.score for s in scores))

    cfg = RunConfig("a", "b", "/r", task_brief, "/b", "/c", ("claude-haiku-4-5",))
    return ComparisonReport(
        cfg, [arm(Arm.BASELINE, baseline_base), arm(Arm.CHALLENGER, challenger_base)], "verdict"
    )


def _report():
    return _make_report(8, 12)


def test_scores_table_shape():
    rows = scores_table(_report())
    # one row per criterion, columns per arm
    assert len(rows) == len(Criterion)
    assert "baseline" in rows[0] and "challenger" in rows[0]


def test_verdict_line():
    assert "challenger" in verdict_line(_report()).lower()


# ---------------------------------------------------------------------------
# Batch aggregation helpers
# ---------------------------------------------------------------------------

# Three reports: challenger wins, baseline wins, tie
_BATCH_REPORTS = [
    _make_report(8, 12, "Fix the add function in calculator"),  # challenger wins (higher base)
    _make_report(15, 8, "Fix the reverse string function here"),  # baseline wins (higher base)
    _make_report(10, 10, "Fix the is even parity check logic"),  # tie (equal bases)
]


def test_batch_win_summary_counts():
    summary = batch_win_summary(_BATCH_REPORTS)
    assert set(summary.keys()) == {"challenger", "baseline", "tie"}
    assert sum(summary.values()) == len(_BATCH_REPORTS)
    assert summary["challenger"] == 1
    assert summary["baseline"] == 1
    assert summary["tie"] == 1


def test_batch_per_case_totals_shape():
    rows = batch_per_case_totals(_BATCH_REPORTS)
    assert len(rows) == len(_BATCH_REPORTS)
    for row in rows:
        assert "case" in row
        assert "baseline" in row
        assert "challenger" in row


def test_batch_per_case_totals_label_derived_from_brief():
    rows = batch_per_case_totals(_BATCH_REPORTS)
    # First ~4 words of the first brief
    assert rows[0]["case"] == "Fix the add function"


def test_batch_per_criterion_avg_shape():
    rows = batch_per_criterion_avg(_BATCH_REPORTS)
    assert len(rows) == len(Criterion)
    for row in rows:
        assert "criterion" in row
        assert "baseline" in row
        assert "challenger" in row


def test_batch_per_criterion_avg_values_are_rounded():
    rows = batch_per_criterion_avg(_BATCH_REPORTS)
    for row in rows:
        # Values should be floats rounded to 1 decimal (no more than 1 decimal place)
        for arm_key in ("baseline", "challenger"):
            val = row[arm_key]
            assert isinstance(val, float)
            assert round(val, 1) == val


# ---------------------------------------------------------------------------
# agent_graph_dot
# ---------------------------------------------------------------------------


def test_agent_graph_dot():
    """Build a sample state and verify the returned DOT string."""
    pipeline = {
        "sandbox": "done",
        "takers": "running",
        "judges": "pending",
        "report": "pending",
    }
    taker_state = {
        "baseline": {"status": "done"},
        "challenger": {"status": "running"},
    }
    judge_status: dict[tuple[str, str], dict] = {
        ("baseline", "correctness"): {"status": "done", "score": 17},
        ("baseline", "completeness"): {"status": "pending", "score": None},
        ("baseline", "distance_to_gold"): {"status": "pending", "score": None},
        ("baseline", "code_quality"): {"status": "pending", "score": None},
        ("baseline", "question_quality"): {"status": "pending", "score": None},
        ("baseline", "approach"): {"status": "pending", "score": None},
        ("challenger", "correctness"): {"status": "pending", "score": None},
        ("challenger", "completeness"): {"status": "pending", "score": None},
        ("challenger", "distance_to_gold"): {"status": "pending", "score": None},
        ("challenger", "code_quality"): {"status": "pending", "score": None},
        ("challenger", "question_quality"): {"status": "pending", "score": None},
        ("challenger", "approach"): {"status": "pending", "score": None},
    }

    dot = agent_graph_dot(pipeline, taker_state, judge_status)

    # Must be a digraph
    assert "digraph" in dot
    assert "{" in dot and "}" in dot

    # Must contain taker node ids for both arms
    assert "taker_baseline" in dot
    assert "taker_challenger" in dot

    # Must contain a judge node showing 17/20 for the done judge
    assert "17/20" in dot

    # Must contain the green fill color for at least one done node
    assert "#a5d6a7" in dot
