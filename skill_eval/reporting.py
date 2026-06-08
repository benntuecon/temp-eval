"""Reporting helpers and Phoenix initialisation for the skill-eval dashboard.

Pure helpers (``scores_table``, ``verdict_line``) are testable without any
Streamlit or Phoenix runtime.  ``init_phoenix`` is best-effort: it is wrapped
in a broad try/except so a missing or unavailable Phoenix server never crashes
the app.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skill_eval.contracts import ComparisonReport

# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def scores_table(report: ComparisonReport) -> list[dict]:
    """Return one row per Criterion with a score column per arm.

    Each row is ``{"criterion": str, "baseline": int, "challenger": int}``.
    The order of rows matches ``Criterion`` enum iteration order.
    """
    from skill_eval.contracts import Arm, Criterion

    # Build a quick lookup: (arm, criterion) -> score
    score_map: dict[tuple[str, str], int] = {}
    for arm_report in report.arms:
        for js in arm_report.scores:
            score_map[(arm_report.arm.value, js.criterion.value)] = js.score

    rows = []
    for criterion in Criterion:
        row: dict = {"criterion": criterion.value}
        for arm in Arm:
            row[arm.value] = score_map.get((arm.value, criterion.value), 0)
        rows.append(row)
    return rows


def verdict_line(report: ComparisonReport) -> str:
    """Re-derive the winner from total scores and return a human-readable verdict."""
    from skill_eval.contracts import Arm

    totals = {ar.arm: ar.total_score for ar in report.arms}
    baseline = totals.get(Arm.BASELINE, 0)
    challenger = totals.get(Arm.CHALLENGER, 0)
    margin = abs(challenger - baseline)

    if challenger > baseline:
        return f"Challenger wins by {margin} points ({challenger} vs {baseline})"
    elif baseline > challenger:
        return f"Baseline wins by {margin} points ({baseline} vs {challenger})"
    else:
        return f"Tie — both arms scored {baseline}"


# ---------------------------------------------------------------------------
# Batch aggregation helpers
# ---------------------------------------------------------------------------


def batch_win_summary(reports: list[ComparisonReport]) -> dict[str, int]:
    """Count wins for challenger, baseline, and ties across a batch of reports.

    Compares each report's per-arm ``total_score``.  Returns a dict with keys
    ``"challenger"``, ``"baseline"``, and ``"tie"``.
    """
    from skill_eval.contracts import Arm

    counts: dict[str, int] = {"challenger": 0, "baseline": 0, "tie": 0}
    for report in reports:
        totals = {ar.arm: ar.total_score for ar in report.arms}
        c = totals.get(Arm.CHALLENGER, 0)
        b = totals.get(Arm.BASELINE, 0)
        if c > b:
            counts["challenger"] += 1
        elif b > c:
            counts["baseline"] += 1
        else:
            counts["tie"] += 1
    return counts


def batch_per_case_totals(reports: list[ComparisonReport]) -> list[dict]:
    """Return one row per report with ``case``, ``baseline``, and ``challenger`` totals.

    The ``case`` label is derived from the first ~4 words of the config's
    ``task_brief``; falls back to ``"case {i+1}"`` if the brief is empty.
    """
    from skill_eval.contracts import Arm

    rows = []
    for i, report in enumerate(reports):
        brief = report.config.task_brief.strip()
        if brief:
            words = brief.split()
            case_label = " ".join(words[:4])
        else:
            case_label = f"case {i + 1}"

        totals = {ar.arm: ar.total_score for ar in report.arms}
        rows.append(
            {
                "case": case_label,
                "baseline": totals.get(Arm.BASELINE, 0),
                "challenger": totals.get(Arm.CHALLENGER, 0),
            }
        )
    return rows


def batch_per_criterion_avg(reports: list[ComparisonReport]) -> list[dict]:
    """Return one row per Criterion with average baseline and challenger scores.

    Averages each criterion's score across all reports per arm.  Scores are
    rounded to 1 decimal place.  Row order matches ``Criterion`` enum order.
    """
    from skill_eval.contracts import Arm, Criterion

    # Accumulate sums per (arm, criterion)
    sums: dict[tuple[str, str], float] = {}
    for arm in Arm:
        for criterion in Criterion:
            sums[(arm.value, criterion.value)] = 0.0

    n = len(reports)
    for report in reports:
        for arm_report in report.arms:
            for js in arm_report.scores:
                key = (arm_report.arm.value, js.criterion.value)
                sums[key] = sums.get(key, 0.0) + js.score

    rows = []
    for criterion in Criterion:
        row: dict = {"criterion": criterion.value}
        for arm in Arm:
            total = sums.get((arm.value, criterion.value), 0.0)
            row[arm.value] = round(total / n, 1) if n > 0 else 0.0
        rows.append(row)
    return rows


# ---------------------------------------------------------------------------
# Phoenix initialisation (best-effort)
# ---------------------------------------------------------------------------


def init_phoenix() -> str | None:
    """Launch / register Phoenix tracing and auto-instrument all supported SDKs.

    Returns the Phoenix UI URL string, or ``None`` if Phoenix is unavailable.
    This function is fully wrapped in try/except and will *never* raise.
    """
    try:
        import phoenix as px  # type: ignore[import-untyped]
        from phoenix.otel import register  # type: ignore[import-untyped]

        session = px.launch_app()
        register(project_name="skill-eval", auto_instrument=True)
        return getattr(session, "url", None) or str(session)
    except Exception:
        return None
