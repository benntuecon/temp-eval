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
# Shared visual palette — ONE colour per arm, used by EVERY chart so the eye
# can compare across views without re-learning the legend each time.
# ---------------------------------------------------------------------------

ARM_COLORS: dict[str, str] = {
    "baseline": "#E45756",  # warm red  → the weaker/control arm
    "challenger": "#4C78A8",  # cool blue → the arm under test
}

# Column order for grouped bars / dumbbells (baseline first, challenger second).
ARM_ORDER: list[str] = ["baseline", "challenger"]


def arm_color_list(columns: list[str]) -> list[str]:
    """Return a colour per column in ``columns`` order (for ``st.bar_chart``)."""
    return [ARM_COLORS.get(c, "#999999") for c in columns]


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
# Comparison-dataviz helpers (single report) — gap, winners, quality-vs-cost
# ---------------------------------------------------------------------------


def criterion_gap_rows(report: ComparisonReport) -> list[dict]:
    """Return one row per Criterion with baseline, challenger, and the gap.

    ``gap = challenger - baseline`` (positive ⇒ challenger ahead).  This feeds a
    dumbbell / diverging chart — the canonical way to compare two series across
    several dimensions, because it makes the *difference* the primary visual.
    Rows are sorted by descending gap so the biggest wins float to the top.
    """
    from skill_eval.contracts import Arm, Criterion

    score_map: dict[tuple[str, str], int] = {}
    for arm_report in report.arms:
        for js in arm_report.scores:
            score_map[(arm_report.arm.value, js.criterion.value)] = js.score

    rows = []
    for criterion in Criterion:
        b = score_map.get((Arm.BASELINE.value, criterion.value), 0)
        c = score_map.get((Arm.CHALLENGER.value, criterion.value), 0)
        rows.append({"criterion": criterion.value, "baseline": b, "challenger": c, "gap": c - b})
    rows.sort(key=lambda r: r["gap"], reverse=True)
    return rows


def criterion_winners(report: ComparisonReport) -> list[dict]:
    """Return one row per Criterion with the per-criterion winner and margin.

    Each row is ``{"criterion": str, "winner": "baseline"|"challenger"|"tie",
    "margin": int}``.  Order matches :func:`criterion_gap_rows` (largest gap
    first).
    """
    rows = []
    for r in criterion_gap_rows(report):
        gap = r["gap"]
        if gap > 0:
            winner = "challenger"
        elif gap < 0:
            winner = "baseline"
        else:
            winner = "tie"
        rows.append({"criterion": r["criterion"], "winner": winner, "margin": abs(gap)})
    return rows


def quality_cost_rows(report: ComparisonReport) -> list[dict]:
    """Return one row per arm pairing quality (total score) against cost.

    Each row is ``{"arm", "total_score", "total_tokens", "wall_seconds",
    "num_turns", "num_questions"}`` — the data behind a quality-vs-cost scatter
    that answers "is the better skill worth what it costs?".
    """
    rows = []
    for arm_report in report.arms:
        m = arm_report.metrics
        rows.append(
            {
                "arm": arm_report.arm.value,
                "total_score": arm_report.total_score,
                "total_tokens": m.total_tokens,
                "wall_seconds": round(m.wall_seconds, 2),
                "num_turns": m.num_turns,
                "num_questions": m.num_questions,
            }
        )
    return rows


# ---------------------------------------------------------------------------
# Report serialisation (for st.download_button / archival)
# ---------------------------------------------------------------------------


def report_to_json(report: ComparisonReport) -> str:
    """Serialise a ComparisonReport to pretty-printed JSON.

    StrEnum members serialise as their string values; anything else
    non-JSON-native falls back to ``str``.
    """
    import json
    from dataclasses import asdict

    return json.dumps(asdict(report), indent=2, default=str)


def reports_to_json(reports: list[ComparisonReport]) -> str:
    """Serialise a batch of ComparisonReports to one JSON array."""
    import json
    from dataclasses import asdict

    return json.dumps([asdict(r) for r in reports], indent=2, default=str)


def report_from_json(text: str) -> ComparisonReport:
    """Reconstruct a ComparisonReport (with real dataclasses/enums) from JSON.

    Tolerant of schema drift: unknown keys in the payload are dropped, missing
    optional fields fall back to their dataclass defaults.
    """
    import json
    from dataclasses import fields

    from skill_eval.contracts import (
        Arm,
        ArmReport,
        ComparisonReport,
        Criterion,
        JudgeScore,
        RunConfig,
        RunMetrics,
    )

    def _known(cls: type, d: dict) -> dict:
        names = {f.name for f in fields(cls)}
        return {k: v for k, v in d.items() if k in names}

    data = json.loads(text)

    cfg_d = _known(RunConfig, dict(data.get("config", {})))
    cfg_d["models"] = tuple(cfg_d.get("models", ()))
    cfg = RunConfig(**cfg_d)

    arms: list[ArmReport] = []
    for a in data.get("arms", []):
        metrics = RunMetrics(**_known(RunMetrics, dict(a.get("metrics", {}))))
        scores = [
            JudgeScore(
                criterion=Criterion(s["criterion"]),
                score=int(s["score"]),
                rationale=str(s.get("rationale", "")),
            )
            for s in a.get("scores", [])
        ]
        arms.append(
            ArmReport(
                arm=Arm(a["arm"]),
                model=str(a.get("model", "")),
                metrics=metrics,
                scores=scores,
                total_score=int(a.get("total_score", 0)),
                questions=tuple(a.get("questions", ())),
                diff=str(a.get("diff", "")),
                stop_reason=str(a.get("stop_reason", "")),
                qa=tuple((str(q), str(ans)) for q, ans in a.get("qa", ())),
            )
        )

    return ComparisonReport(
        config=cfg,
        arms=arms,
        pairwise_verdict=str(data.get("pairwise_verdict", "")),
        gold_diff=str(data.get("gold_diff", "")),
        session_id=str(data.get("session_id", "")),
    )


# ---------------------------------------------------------------------------
# Run history on disk (promptfoo `list` / Langfuse experiments-table analog)
# ---------------------------------------------------------------------------


def save_report(report: ComparisonReport, runs_dir: str, label: str = "run") -> str:
    """Persist a report as ``<runs_dir>/<ts>_<label>_<suffix>.json``; return the path.

    Best-effort archival: any failure returns "" rather than raising, so a
    full disk or read-only checkout never breaks the dashboard.
    """
    try:
        import uuid
        from datetime import datetime
        from pathlib import Path

        d = Path(runs_dir)
        d.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = d / f"{ts}_{label}_{uuid.uuid4().hex[:6]}.json"
        path.write_text(report_to_json(report))
        return str(path)
    except Exception:
        return ""


def list_saved_runs(runs_dir: str) -> list[dict]:
    """Return saved run files, newest first: ``{"name", "path"}`` per run."""
    from pathlib import Path

    d = Path(runs_dir)
    if not d.is_dir():
        return []
    files = sorted(d.glob("*.json"), key=lambda p: p.name, reverse=True)
    return [{"name": p.stem, "path": str(p)} for p in files]


def load_report(path: str) -> ComparisonReport:
    """Load one saved run back into a ComparisonReport."""
    from pathlib import Path

    return report_from_json(Path(path).read_text())


def run_delta_rows(report_a: ComparisonReport, report_b: ComparisonReport) -> list[dict]:
    """Per-(criterion, arm) score deltas between two runs (B − A).

    The Langfuse compare-view pattern: run A is the baseline run, run B the
    candidate; positive delta means B improved on A. Long-form rows
    ``{"criterion", "arm", "run_a", "run_b", "delta"}``, Criterion order, arms
    baseline-then-challenger within each criterion.
    """
    from skill_eval.contracts import Arm, Criterion

    def _score_map(report: ComparisonReport) -> dict[tuple[str, str], int]:
        out: dict[tuple[str, str], int] = {}
        for ar in report.arms:
            for s in ar.scores:
                out[(ar.arm.value, s.criterion.value)] = s.score
        return out

    a_map, b_map = _score_map(report_a), _score_map(report_b)
    rows = []
    for criterion in Criterion:
        for arm in Arm:
            key = (arm.value, criterion.value)
            a, b = a_map.get(key, 0), b_map.get(key, 0)
            rows.append(
                {
                    "criterion": criterion.value,
                    "arm": arm.value,
                    "run_a": a,
                    "run_b": b,
                    "delta": b - a,
                }
            )
    return rows


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


def batch_criterion_gap_rows(reports: list[ComparisonReport]) -> list[dict]:
    """Return per-Criterion average baseline, challenger, and gap across a batch.

    Built on :func:`batch_per_criterion_avg`; adds ``gap = challenger - baseline``
    and sorts by descending gap.  Feeds the batch dumbbell chart.
    """
    from skill_eval.contracts import Arm

    rows = []
    for r in batch_per_criterion_avg(reports):
        b = r.get(Arm.BASELINE.value, 0.0)
        c = r.get(Arm.CHALLENGER.value, 0.0)
        rows.append(
            {"criterion": r["criterion"], "baseline": b, "challenger": c, "gap": round(c - b, 1)}
        )
    rows.sort(key=lambda r: r["gap"], reverse=True)
    return rows


# ---------------------------------------------------------------------------
# Agent-graph DOT builder (pure, no Streamlit/Phoenix dependency)
# ---------------------------------------------------------------------------

_STATUS_COLOR = {
    "pending": "#E0E0E0",
    "running": "#FFD54F",
    "done": "#81C784",
    "error": "#E57373",
}

_CRITERIA_ORDER = [
    "correctness",
    "completeness",
    "distance_to_gold",
    "code_quality",
    "question_quality",
    "approach",
]


def agent_graph_dot(
    pipeline: dict[str, str],
    taker_state: dict[str, dict],
    judge_status: dict[tuple[str, str], dict],
) -> str:
    """Return a Graphviz DOT digraph string representing the eval fan-out.

    Parameters
    ----------
    pipeline:
        stage -> ``"pending" | "running" | "done"`` for ``sandbox``, ``takers``,
        ``judges``, ``report``.
    taker_state:
        arm (``"baseline"`` / ``"challenger"``) -> dict with at least a
        ``"status"`` key (``"pending" | "running" | "done"``).
    judge_status:
        ``(arm, criterion)`` -> ``{"status": str, "score": int | None}``.

    Returns
    -------
    str
        A valid ``digraph { ... }`` DOT string suitable for
        ``st.graphviz_chart()``.

    Layout notes (deliberate, after a readability review):
    - ``rankdir=LR`` — 16 nodes read wide, not tall, so the graph fits a
      dashboard row without scrolling.
    - One invisible *junction* point per arm collapses the 6 judge→assemble
      edges into a single edge, so ``assemble`` receives 2 arrowheads, not 12.
    - Edges are de-emphasised (translucent, thin); node *status colour* is the
      primary signal. d3-graphviz layout is deterministic, so nodes do not
      jump between 1 Hz repaints.
    """

    def _color(status: str) -> str:
        return _STATUS_COLOR.get(status, _STATUS_COLOR["pending"])

    def _node(node_id: str, label: str, status: str, indent: str = "    ") -> str:
        color = _color(status)
        safe_label = label.replace('"', '\\"')
        outline = ' penwidth=2 color="#B8860B"' if status == "running" else ""
        return f'{indent}{node_id} [label="{safe_label}" fillcolor="{color}"{outline}]'

    lines: list[str] = [
        "digraph {",
        "    rankdir=LR",
        "    ranksep=0.45",
        "    nodesep=0.18",
        "    splines=spline",
        "    bgcolor=transparent",
        '    fontname="Helvetica"',
        '    node [shape=box style="rounded,filled" fontname="Helvetica"'
        ' fontsize=12 margin="0.15,0.08" color="#bbbbbb"]',
        '    edge [color="#00000033" penwidth=0.8 arrowsize=0.6]',
        "",
    ]

    # --- sandbox node ---
    sandbox_status = pipeline.get("sandbox", "pending")
    lines.append(_node("sandbox", "sandbox", sandbox_status))
    lines.append("")

    # --- one cluster per arm: taker + 6 judges + invisible fan-in junction ---
    arms = ["baseline", "challenger"]
    for arm in arms:
        ts = taker_state.get(arm, {})
        taker_status = ts.get("status", "pending")

        lines.append(f"    subgraph cluster_{arm} {{")
        lines.append(f'        label="{arm}"')
        lines.append('        style="rounded,filled" fillcolor="#FAFAFA" color="#DDDDDD"')
        lines.append("")
        lines.append(_node(f"taker_{arm}", f"taker\\n({taker_status})", taker_status, "        "))
        lines.append("")

        for criterion in _CRITERIA_ORDER:
            js = judge_status.get((arm, criterion), {"status": "pending", "score": None})
            j_status = js.get("status", "pending")
            score = js.get("score")
            if j_status == "done" and score is not None:
                j_label = f"{criterion}\\n{score}/20"
            else:
                j_label = criterion
            lines.append(_node(f"judge_{arm}_{criterion}", j_label, j_status, "        "))

        # Invisible junction: 6 judge edges merge here, ONE edge continues on.
        lines.append(f'        j_{arm} [shape=point width=0.06 label="" color="#999999"]')
        lines.append("    }")
        lines.append("")

    # --- assemble node ---
    assemble_status = pipeline.get("report", "pending")
    lines.append(_node("assemble", "assemble", assemble_status))
    lines.append("")

    # --- edges ---
    for arm in arms:
        lines.append(f"    sandbox -> taker_{arm}")

    lines.append("")

    for arm in arms:
        for criterion in _CRITERIA_ORDER:
            lines.append(f"    taker_{arm} -> judge_{arm}_{criterion}")

    lines.append("")

    # judges -> junction (no arrowheads) -> assemble (one visible edge per arm)
    for arm in arms:
        for criterion in _CRITERIA_ORDER:
            lines.append(f"    judge_{arm}_{criterion} -> j_{arm} [arrowhead=none]")
        lines.append(f'    j_{arm} -> assemble [penwidth=1.2 color="#666666" arrowsize=0.8]')

    lines.append("}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Phoenix span-evaluation logging (best-effort)
# ---------------------------------------------------------------------------


def log_judge_evaluations(records: list[tuple]) -> bool:
    """Log per-judge scores to Phoenix as span evaluations.

    Parameters
    ----------
    records:
        List of ``(span_id, arm, criterion, score, rationale)`` tuples.

    Returns
    -------
    bool
        ``True`` if all evaluations were logged successfully, ``False`` on any
        failure.  This function *never* raises.
    """
    try:
        from phoenix.client import Client
        from phoenix.client.__generated__.v1 import AnnotationResult, SpanAnnotationData

        if not records:
            return False

        client = Client()
        annotations: list[SpanAnnotationData] = [
            SpanAnnotationData(
                name=criterion,
                annotator_kind="CODE",
                span_id=span_id,
                result=AnnotationResult(
                    label=arm,
                    score=float(score),
                    explanation=rationale,
                ),
            )
            for span_id, arm, criterion, score, rationale in records
        ]
        client.spans.log_span_annotations(span_annotations=annotations, sync=True)
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Batch score distribution (pure, testable)
# ---------------------------------------------------------------------------


def batch_score_distribution(reports: list) -> list[dict]:
    """Return long-form rows for per-criterion, per-arm score distributions.

    Each row has ``{"criterion": str, "arm": str, "score": int}``.
    There is one row per judge score across ALL reports, so the total row
    count is ``len(reports) * 12`` (2 arms × 6 criteria per report).
    """
    rows: list[dict] = []
    for report in reports:
        for arm_report in report.arms:
            for js in arm_report.scores:
                rows.append(
                    {
                        "criterion": js.criterion.value,
                        "arm": arm_report.arm.value,
                        "score": js.score,
                    }
                )
    return rows


# ---------------------------------------------------------------------------
# Phoenix initialisation (best-effort)
# ---------------------------------------------------------------------------


def init_phoenix() -> str | None:
    """Register tracing against a Phoenix server, auto-starting one if needed.

    If nothing is listening on ``localhost:6006``, spawn ``phoenix serve`` as a
    detached background process and wait briefly for it to come up; then register
    the tracer and return the Phoenix UI URL (or ``None`` if it couldn't be
    reached/started). Never raises. (``px.launch_app()`` is intentionally avoided —
    it doesn't work from Streamlit's worker thread.)
    """
    import socket
    import time

    host, ui_port = "localhost", 6006

    def _reachable() -> bool:
        try:
            with socket.create_connection((host, ui_port), timeout=0.5):
                return True
        except OSError:
            return False

    if not _reachable():
        # Auto-start a detached Phoenix server (survives Streamlit reruns/exit).
        try:
            import subprocess
            import sys
            from pathlib import Path

            phoenix_bin = Path(sys.executable).with_name("phoenix")
            cmd = [str(phoenix_bin), "serve"] if phoenix_bin.exists() else ["phoenix", "serve"]
            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except Exception:
            return None
        # Phoenix needs a few seconds (DB migrations, server bind).
        deadline = time.monotonic() + 20.0
        while time.monotonic() < deadline:
            if _reachable():
                break
            time.sleep(0.5)
        else:
            return None  # didn't come up in time

    try:
        from phoenix.otel import register  # type: ignore[import-untyped]

        register(project_name="skill-eval", auto_instrument=True)
        return f"http://{host}:{ui_port}"
    except Exception:
        return None
