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
    ARM_COLORS,
    agent_graph_dot,
    arm_color_list,
    batch_criterion_gap_rows,
    batch_per_case_totals,
    batch_per_criterion_avg,
    batch_score_distribution,
    batch_win_summary,
    criterion_gap_rows,
    criterion_winners,
    list_saved_runs,
    load_report,
    quality_cost_rows,
    report_from_json,
    report_to_json,
    reports_to_json,
    run_delta_rows,
    save_report,
    scores_table,
    verdict_line,
)


def _make_report(
    baseline_base: int, challenger_base: int, task_brief: str = "Fix the add function in calculator"
):
    """Build a fake ComparisonReport with deterministic scores."""
    m = RunMetrics(
        total_tokens=100,
        input_tokens=60,
        output_tokens=40,
        wall_seconds=1.2,
        num_turns=3,
        num_questions=1,
    )

    def arm(a, base):
        scores = [
            JudgeScore(criterion=c, score=base + i, rationale="ok") for i, c in enumerate(Criterion)
        ]
        return ArmReport(
            arm=a,
            model="claude-haiku-4-5",
            metrics=m,
            scores=scores,
            total_score=sum(s.score for s in scores),
        )

    cfg = RunConfig(
        before_hash="a",
        after_hash="b",
        repo_path="/r",
        task_brief=task_brief,
        baseline_skill_path="/b",
        challenger_skill_path="/c",
        models=("claude-haiku-4-5",),
    )
    return ComparisonReport(
        config=cfg,
        arms=[arm(Arm.BASELINE, baseline_base), arm(Arm.CHALLENGER, challenger_base)],
        pairwise_verdict="verdict",
    )


def _report():
    return _make_report(8, 12)


def test_report_to_json_round_trips():
    import json

    payload = json.loads(report_to_json(_report()))
    assert payload["pairwise_verdict"] == "verdict"
    assert {a["arm"] for a in payload["arms"]} == {"baseline", "challenger"}
    # nested dataclasses serialise: scores carry criterion/score/rationale
    first_score = payload["arms"][0]["scores"][0]
    assert set(first_score) == {"criterion", "score", "rationale"}
    # new ArmReport fields present with defaults
    assert "diff" in payload["arms"][0] and "stop_reason" in payload["arms"][0]


def test_reports_to_json_is_array():
    import json

    payload = json.loads(reports_to_json([_report(), _make_report(15, 8)]))
    assert isinstance(payload, list) and len(payload) == 2


def test_report_json_round_trip_reconstructs_dataclasses():
    rep = _report()
    back = report_from_json(report_to_json(rep))
    assert back == rep  # full dataclass equality incl. enums and tuples


def test_save_list_load_runs(tmp_path):
    runs_dir = str(tmp_path / "runs")
    rep_a, rep_b = _make_report(8, 12), _make_report(15, 8)
    p1 = save_report(rep_a, runs_dir, label="single")
    p2 = save_report(rep_b, runs_dir, label="flagship")
    assert p1 and p2 and p1 != p2

    runs = list_saved_runs(runs_dir)
    assert len(runs) == 2
    assert {r["path"] for r in runs} == {p1, p2}

    assert load_report(p1) == rep_a
    assert load_report(p2) == rep_b


def test_list_saved_runs_missing_dir_is_empty(tmp_path):
    assert list_saved_runs(str(tmp_path / "nope")) == []


def test_run_delta_rows():
    rep_a, rep_b = _make_report(8, 12), _make_report(10, 11)
    rows = run_delta_rows(rep_a, rep_b)
    assert len(rows) == len(Criterion) * 2
    by_key = {(r["arm"], r["criterion"]): r for r in rows}
    first = Criterion.CORRECTNESS.value
    # baseline base 8 -> 10 (delta +2); challenger base 12 -> 11 (delta -1)
    assert by_key[("baseline", first)]["delta"] == 2
    assert by_key[("challenger", first)]["delta"] == -1


def test_scores_table_shape():
    rows = scores_table(_report())
    # one row per criterion, columns per arm
    assert len(rows) == len(Criterion)
    assert "baseline" in rows[0] and "challenger" in rows[0]


def test_verdict_line():
    assert "challenger" in verdict_line(_report()).lower()


# ---------------------------------------------------------------------------
# Comparison-dataviz helpers (gap / winners / quality-cost / palette)
# ---------------------------------------------------------------------------


def test_criterion_gap_rows_shape_and_gap():
    rows = criterion_gap_rows(_report())  # baseline base 8, challenger base 12
    assert len(rows) == len(Criterion)
    for row in rows:
        assert set(row) == {"criterion", "baseline", "challenger", "gap"}
        # challenger = base+i, baseline = base+i ⇒ constant gap of 4 here
        assert row["gap"] == row["challenger"] - row["baseline"] == 4


def test_criterion_gap_rows_sorted_by_gap_desc():
    # Build a report where gaps differ per criterion so ordering is observable.
    m = RunMetrics(
        total_tokens=100,
        input_tokens=60,
        output_tokens=40,
        wall_seconds=1.2,
        num_turns=3,
        num_questions=1,
    )
    base_scores = [JudgeScore(criterion=c, score=5, rationale="x") for c in Criterion]
    chal_scores = [
        JudgeScore(criterion=c, score=5 + i, rationale="x") for i, c in enumerate(Criterion)
    ]  # gap grows
    cfg = RunConfig(
        before_hash="a",
        after_hash="b",
        repo_path="/r",
        task_brief="brief",
        baseline_skill_path="/b",
        challenger_skill_path="/c",
        models=("claude-haiku-4-5",),
    )
    report = ComparisonReport(
        config=cfg,
        arms=[
            ArmReport(
                arm=Arm.BASELINE,
                model="m",
                metrics=m,
                scores=base_scores,
                total_score=sum(s.score for s in base_scores),
            ),
            ArmReport(
                arm=Arm.CHALLENGER,
                model="m",
                metrics=m,
                scores=chal_scores,
                total_score=sum(s.score for s in chal_scores),
            ),
        ],
        pairwise_verdict="v",
    )
    rows = criterion_gap_rows(report)
    gaps = [r["gap"] for r in rows]
    assert gaps == sorted(gaps, reverse=True)


def test_criterion_winners():
    rows = criterion_winners(_report())  # challenger ahead everywhere
    assert len(rows) == len(Criterion)
    for row in rows:
        assert row["winner"] == "challenger"
        assert row["margin"] == 4


def test_quality_cost_rows():
    rows = quality_cost_rows(_report())
    assert len(rows) == 2
    arms = {r["arm"] for r in rows}
    assert arms == {"baseline", "challenger"}
    for row in rows:
        assert set(row) >= {"arm", "total_score", "total_tokens", "wall_seconds", "num_questions"}
        assert row["total_tokens"] == 100  # from RunMetrics(100, ...)


def test_arm_color_palette():
    assert set(ARM_COLORS) == {"baseline", "challenger"}
    assert arm_color_list(["baseline", "challenger"]) == [
        ARM_COLORS["baseline"],
        ARM_COLORS["challenger"],
    ]
    # Unknown column falls back to a neutral grey, never raises.
    assert arm_color_list(["mystery"]) == ["#999999"]


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


def test_batch_criterion_gap_rows():
    rows = batch_criterion_gap_rows(_BATCH_REPORTS)
    assert len(rows) == len(Criterion)
    gaps = [r["gap"] for r in rows]
    assert gaps == sorted(gaps, reverse=True)  # sorted by descending gap
    for row in rows:
        assert set(row) == {"criterion", "baseline", "challenger", "gap"}
        assert round(row["gap"], 1) == round(row["challenger"] - row["baseline"], 1)


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
    assert "#81C784" in dot

    # Left-to-right layout: wide, not tall
    assert "rankdir=LR" in dot

    # Fan-in junctions: judges merge into one point per arm, then -> assemble,
    # so assemble receives 2 edges instead of 12.
    assert "j_baseline -> assemble" in dot
    assert "j_challenger -> assemble" in dot
    assert dot.count("-> assemble") == 2

    # Whole-architecture nodes: skills -> (mock) test generator -> test cases
    # -> sandbox; HITL simulator; assemble -> report.
    for node in ("skill_baseline", "skill_challenger", "test_generator", "test_cases"):
        assert node in dot
    assert "simulator" in dot
    assert "assemble -> report" in dot

    # Every architecture node carries a hover tooltip ("thinking process").
    assert dot.count("tooltip=") >= 18  # 5 pipeline + 1 sim + 2 takers + 12 judges...


def test_agent_graph_dot_meta_tooltips():
    """meta enriches hover tooltips: skill names, rationales, verdict."""
    pipeline = {"sandbox": "done", "takers": "done", "judges": "done", "report": "done"}
    taker_state = {"baseline": {"status": "done"}, "challenger": {"status": "done"}}
    judge_status = {("baseline", "correctness"): {"status": "done", "score": 17}}
    meta = {
        "baseline_skill": "ship-it-fast",
        "challenger_skill": "disciplined",
        "verdict": "challenger wins by 80",
        "rationales": {("baseline", "correctness"): 'judge said "close but no edge cases"'},
    }
    dot = agent_graph_dot(pipeline, taker_state, judge_status, meta)
    assert "ship-it-fast" in dot
    assert "disciplined" in dot
    assert "challenger wins by 80" in dot
    # rationale lands in the judge tooltip, with quotes DOT-escaped
    assert "close but no edge cases" in dot
    assert '\\"close but no edge cases\\"' in dot


# ---------------------------------------------------------------------------
# batch_score_distribution
# ---------------------------------------------------------------------------


def test_batch_score_distribution_row_count():
    """len(reports) * 12 rows (2 arms × 6 criteria per report)."""
    n_reports = 3
    rows = batch_score_distribution(_BATCH_REPORTS[:n_reports])
    assert len(rows) == n_reports * 12


def test_batch_score_distribution_schema():
    """Every row has criterion, arm, and score keys."""
    rows = batch_score_distribution(_BATCH_REPORTS)
    for row in rows:
        assert "criterion" in row
        assert "arm" in row
        assert "score" in row
        assert isinstance(row["score"], int)
        assert row["arm"] in ("baseline", "challenger")


def test_batch_score_distribution_empty():
    assert batch_score_distribution([]) == []
