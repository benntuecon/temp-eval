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
# Phoenix initialisation (best-effort)
# ---------------------------------------------------------------------------


def init_phoenix() -> str | None:
    """Launch / register Phoenix tracing and instrument LangChain.

    Returns the Phoenix UI URL string, or ``None`` if Phoenix is unavailable.
    This function is fully wrapped in try/except and will *never* raise.
    """
    try:
        import phoenix as px  # type: ignore[import-untyped]

        session = px.launch_app()
        # session.url may be None when Phoenix starts without a port; fall back
        # to str() which returns a usable representation regardless.
        raw_url = getattr(session, "url", None)
        url: str = raw_url if isinstance(raw_url, str) else str(session)
    except Exception:
        return None

    try:
        from openinference.instrumentation.langchain import (  # type: ignore[import-untyped]
            LangChainInstrumentor,
        )

        LangChainInstrumentor().instrument()
    except Exception:
        pass  # Phoenix is available but LangChain instrumentation failed — non-fatal

    return url
