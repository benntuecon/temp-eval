"""Streamlit dashboard for the skill-eval harness.

Run with:
    uv run streamlit run app.py

The module can be imported without side-effects (no Streamlit calls,
no Phoenix launch, no eval run happen at import time).  All live logic
lives inside ``main()``, which Streamlit calls automatically when it
executes the script.

Layout principles (after a promptfoo / Langfuse comparison-UI review):
- **Funnel**: aggregate delta metrics → per-criterion score matrix with
  green/red Δ → drill-down (judge rationales, taker diffs, Phoenix traces).
- **Persistence**: finished reports live in ``st.session_state`` and render
  OUTSIDE the run-button branch, so results survive widget interactions.
- **Encoding**: one colour per arm everywhere; grouped, never stacked.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Helpers (defined before use)
# ---------------------------------------------------------------------------


def _is_streamlit() -> bool:
    """Return True when this file is being executed by Streamlit."""
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


def _slug(name: str, fallback: str) -> str:
    """Slugify a user-supplied skill name into a safe directory name."""
    import re

    s = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    return s or fallback


def _runs_dir() -> str:
    """Directory where completed runs are archived as JSON.

    Defaults to the project-local ``runs/``; override with the
    ``SKILL_EVAL_RUNS_DIR`` env var (tests point it at a tmp dir).
    """
    import os
    from pathlib import Path

    return os.environ.get("SKILL_EVAL_RUNS_DIR") or str(Path(__file__).resolve().parent / "runs")


# ---------------------------------------------------------------------------
# Main dashboard logic
# ---------------------------------------------------------------------------


def main() -> None:
    import queue
    import shutil
    import tempfile
    import threading

    import pandas as pd
    import streamlit as st

    from skill_eval.orchestrator import run_eval
    from skill_eval.reporting import (
        agent_graph_dot,
        init_phoenix,
        verdict_line,
    )
    from skill_eval.simulated import sim_make_simulator, sim_run_judge, sim_run_taker

    # ------------------------------------------------------------------
    # Page config + compact header (no sidebar — everything lives inline)
    # ------------------------------------------------------------------
    st.set_page_config(
        page_title="Skill Eval",
        page_icon="⚖️",
        layout="wide",
    )

    st.title("⚖️ Skill Eval")

    # Phoenix link (cached in session so we don't relaunch on every rerun)
    if "phoenix_url" not in st.session_state:
        with st.spinner("Connecting to Phoenix…"):
            st.session_state["phoenix_url"] = init_phoenix()
    phoenix_url = st.session_state["phoenix_url"]
    if phoenix_url:
        st.caption(
            "Race two Claude Code skills on the same task and let a judge panel decide"
            f" — every agent, question, and judge call traced in [Phoenix]({phoenix_url})."
        )
    else:
        st.caption(
            "Race two Claude Code skills on the same task and let a judge panel decide."
            " ⚠️ Phoenix not running — start it with `just phoenix`, then rerun."
        )

    # ------------------------------------------------------------------
    # Two tabs only: run an eval, or browse/compare archived runs
    # ------------------------------------------------------------------
    tab_run, tab_history = st.tabs(["▶ Run eval", "📜 History"])

    with tab_run:
        _run_custom_mode(
            st=st,
            pd=pd,
            queue=queue,
            shutil=shutil,
            tempfile=tempfile,
            threading=threading,
            run_eval=run_eval,
            verdict_line=verdict_line,
            agent_graph_dot=agent_graph_dot,
            sim_make_simulator=sim_make_simulator,
            sim_run_judge=sim_run_judge,
            sim_run_taker=sim_run_taker,
        )

    with tab_history:
        _run_history_mode(
            st=st,
            pd=pd,
            verdict_line=verdict_line,
            agent_graph_dot=agent_graph_dot,
        )


def _run_single_case(
    *,
    st,  # type: ignore[type-arg]
    pd,  # type: ignore[type-arg]
    queue,  # type: ignore[type-arg]
    shutil,  # type: ignore[type-arg]
    tempfile,  # type: ignore[type-arg]
    threading,  # type: ignore[type-arg]
    use_real: bool,
    run_eval,  # type: ignore[type-arg]
    verdict_line,  # type: ignore[type-arg]
    build_cfg=None,  # type: ignore[type-arg]  callable(base_dir) -> RunConfig
    force_real: bool = False,
    sim_make_simulator,  # type: ignore[type-arg]
    sim_run_judge,  # type: ignore[type-arg]
    sim_run_taker,  # type: ignore[type-arg]
    agent_graph_dot,  # type: ignore[type-arg]
    button_label: str = "Run eval",
    state_key: str = "single",
    trigger: bool | None = None,
    graph_meta: dict | None = None,
) -> None:
    """Single-case control-room view.

    Parameters
    ----------
    build_cfg:
        Callable ``(base_dir: str) -> RunConfig`` used to set up the repo.
        Defaults to ``build_sample_repo`` when *None*.
    force_real:
        When *True*, always use the real taker/simulator/judge regardless of
        the ``use_real`` sidebar toggle (used by Flagship mode).
    state_key:
        ``st.session_state`` key suffix under which the finished report is
        stored — results render from there so they survive reruns.
    trigger:
        When not *None*, used instead of an internal ``st.button`` (used by
        Custom mode, whose run is triggered by a form submit).
    """
    import time

    clicked = st.button(button_label, type="primary") if trigger is None else trigger

    if clicked:
        st.divider()
        st.subheader("Live progress")

        # ------------------------------------------------------------------
        # Placeholders for the live control-room widgets
        # ------------------------------------------------------------------
        pipeline_placeholder = st.empty()

        col_base, col_chal = st.columns(2)
        with col_base:
            st.markdown("**Baseline**")
            base_panel = st.empty()
        with col_chal:
            st.markdown("**Challenger**")
            chal_panel = st.empty()

        st.markdown("**Judges grid**")
        judges_placeholder = st.empty()

        st.markdown("**Agent graph**")
        graph_placeholder = st.empty()

        event_log_placeholder = st.empty()

        # ------------------------------------------------------------------
        # State dicts updated in the drain loop
        # ------------------------------------------------------------------
        # stage -> "pending" | "running" | "done"
        pipeline: dict[str, str] = {
            "generator": "running",  # the (mock) test generator builds the fixture first
            "sandbox": "pending",
            "takers": "pending",
            "judges": "pending",
            "report": "pending",
        }

        # arm -> {"status": str, "stop_reason": str, "num_questions": int, ...}
        taker_state: dict[str, dict] = {
            "baseline": {},
            "challenger": {},
        }

        # (arm, criterion) -> cell string
        judge_cells: dict[tuple[str, str], str] = {}
        # (arm, criterion) -> rationale text, for live hover tooltips on the graph
        judge_rationales: dict[tuple[str, str], str] = {}

        CRITERIA_ORDER = [
            "correctness",
            "completeness",
            "distance_to_gold",
            "code_quality",
            "question_quality",
            "approach",
        ]

        all_events: list[str] = []

        # ------------------------------------------------------------------
        # _refresh: repaint all placeholders from current state
        # ------------------------------------------------------------------
        def _refresh() -> None:
            # --- Pipeline strip ---
            stage_icons = {"pending": "⬜", "running": "⏳", "done": "✅"}
            parts = []
            for stage_name, label in [
                ("sandbox", "Sandbox"),
                ("takers", "Takers"),
                ("judges", "Judges"),
                ("report", "Report"),
            ]:
                icon = stage_icons[pipeline[stage_name]]
                parts.append(f"{icon} **{label}**")
            pipeline_placeholder.markdown("  →  ".join(parts))

            # --- Taker panels ---
            for real_arm, panel in [("baseline", base_panel), ("challenger", chal_panel)]:
                state = taker_state[real_arm]
                if not state:
                    panel.markdown("_waiting…_")
                elif state.get("status") == "running":
                    panel.markdown("⏳ running")
                else:
                    stop = state.get("stop_reason", "—")
                    nq = state.get("num_questions", "—")
                    turns = state.get("num_turns", "—")
                    wall = state.get("wall_seconds", "—")
                    panel.markdown(
                        f"✅ done — stop: `{stop}`  \n"
                        f"questions: **{nq}** · turns: **{turns}** · {wall}s"
                    )

            # --- Judges grid ---
            rows = []
            for crit in CRITERIA_ORDER:
                base_cell = judge_cells.get(("baseline", crit), "⬜")
                chal_cell = judge_cells.get(("challenger", crit), "⬜")
                rows.append({"criterion": crit, "baseline": base_cell, "challenger": chal_cell})
            judges_df = pd.DataFrame(rows).set_index("criterion")
            judges_placeholder.dataframe(judges_df, width="stretch")

            # --- Agent graph ---
            # Build judge_status from judge_cells
            js_map: dict[tuple[str, str], dict] = {}
            for arm_key in ("baseline", "challenger"):
                for crit in CRITERIA_ORDER:
                    cell = judge_cells.get((arm_key, crit), "⬜")
                    if cell == "⬜":
                        js_map[(arm_key, crit)] = {"status": "pending", "score": None}
                    elif cell == "⏳":
                        js_map[(arm_key, crit)] = {"status": "running", "score": None}
                    else:
                        # cell is like "✅ 17"
                        try:
                            score = int(cell.split()[-1])
                        except (ValueError, IndexError):
                            score = None
                        js_map[(arm_key, crit)] = {"status": "done", "score": score}
            live_meta = dict(graph_meta or {})
            live_meta["rationales"] = dict(judge_rationales)
            graph_placeholder.graphviz_chart(
                agent_graph_dot(pipeline, taker_state, js_map, live_meta),
                width="stretch",
            )

            # --- Event log ---
            recent = all_events[-15:]
            if recent:
                log_text = "**Event log**\n\n" + "\n\n".join(recent)
            else:
                log_text = "_no events yet_"
            event_log_placeholder.markdown(log_text)

        # ------------------------------------------------------------------
        # Background thread: run_eval pushes events into a queue
        # ------------------------------------------------------------------
        q: queue.Queue = queue.Queue()

        # Capture values before entering the background thread — Streamlit
        # widgets cannot be accessed from a non-Streamlit thread.
        _use_real = force_real or use_real
        # Resolve build_cfg: default to build_sample_repo when not supplied.
        _build_cfg = build_cfg
        if _build_cfg is None:
            from skill_eval.sample_repo import build_sample_repo as _bsr

            _build_cfg = _bsr

        def _background() -> None:
            tmp = tempfile.mkdtemp()
            try:
                cfg = _build_cfg(tmp)

                def on_event(ev: dict) -> None:
                    q.put(("event", ev))

                if _use_real:
                    from skill_eval.judge import run_judge
                    from skill_eval.simulator import make_simulator
                    from skill_eval.taker import run_taker

                    report = run_eval(
                        cfg,
                        taker_fn=run_taker,
                        simulator_factory=make_simulator,
                        judge_fn=run_judge,
                        on_event=on_event,
                    )
                else:
                    report = run_eval(
                        cfg,
                        taker_fn=sim_run_taker,
                        simulator_factory=sim_make_simulator,
                        judge_fn=sim_run_judge,
                        on_event=on_event,
                    )
                q.put(("done", report))
            except Exception as exc:
                q.put(("error", exc))
            finally:
                shutil.rmtree(tmp, ignore_errors=True)

        t = threading.Thread(target=_background, daemon=True)
        t.start()

        # ------------------------------------------------------------------
        # Main loop: drain queue while thread is alive or queue non-empty
        # ------------------------------------------------------------------
        report = None
        failed = False
        spinner_text = st.empty()
        spinner_text.info("Running…")
        last_paint = 0.0

        while t.is_alive() or not q.empty():
            try:
                kind, payload = q.get(timeout=0.05)
            except queue.Empty:
                # Throttle idle repaints — the graphviz re-render is the
                # expensive part, no need to redraw 20×/sec with no new data.
                now = time.monotonic()
                if now - last_paint > 0.25:
                    _refresh()
                    last_paint = now
                continue

            if kind == "done":
                report = payload
                break

            if kind == "error":
                st.error(f"Eval failed: {payload}")
                failed = True
                break

            # kind == "event"
            ev: dict = payload
            stage = ev.get("stage", "?")
            arm = ev.get("arm", "")
            criterion = ev.get("criterion", "")

            if stage == "sandbox":
                pipeline["generator"] = "done"  # fixture built — mock generator finished
                pipeline["sandbox"] = "running"
                msg = ev.get("msg", "")
                arms_list = ev.get("arms", [])
                if arms_list:
                    all_events.append(f"[sandbox] {msg} — arms: {', '.join(arms_list)}")
                else:
                    all_events.append(f"[sandbox] {msg}")
                # Sandbox is a single-shot event; mark done immediately
                pipeline["sandbox"] = "done"

            elif stage == "taker":
                status = ev.get("status", "")
                if pipeline["takers"] == "pending":
                    pipeline["takers"] = "running"
                if arm in taker_state:
                    if status == "running":
                        taker_state[arm] = {"status": "running"}
                        all_events.append(f"[taker:{arm}] running")
                    elif status == "done":
                        taker_state[arm] = {
                            "status": "done",
                            "stop_reason": ev.get("stop_reason", "—"),
                            "num_questions": ev.get("num_questions", "—"),
                            "num_turns": ev.get("num_turns", "—"),
                            "wall_seconds": ev.get("wall_seconds", "—"),
                        }
                        all_events.append(
                            f"[taker:{arm}] done — stop={ev.get('stop_reason')} "
                            f"questions={ev.get('num_questions')} "
                            f"turns={ev.get('num_turns')}"
                        )

            elif stage == "takers_done":
                pipeline["takers"] = "done"
                count = ev.get("count", "")
                all_events.append(f"[takers_done] {count} takers finished")

            elif stage == "judge":
                if pipeline["judges"] == "pending":
                    pipeline["judges"] = "running"
                status = ev.get("status", "")
                score = ev.get("score")
                key = (arm, criterion)
                if status == "running":
                    judge_cells[key] = "⏳"
                    all_events.append(f"[judge:{arm}] {criterion} running")
                elif status == "done" and score is not None:
                    judge_cells[key] = f"✅ {score}"
                    if ev.get("rationale"):
                        judge_rationales[key] = str(ev["rationale"])
                    all_events.append(f"[judge:{arm}] {criterion} done — score={score}")

            elif stage == "report":
                pipeline["judges"] = "done"
                pipeline["report"] = "done"
                verdict = ev.get("verdict", "")
                all_events.append(f"[report] {verdict}")

            else:
                all_events.append(f"[{stage}] {ev}")

            _refresh()
            last_paint = time.monotonic()

        # Drain remaining events after thread finishes
        while not q.empty():
            try:
                kind, payload = q.get_nowait()
                if kind == "done":
                    report = payload
                elif kind == "event":
                    ev = payload
                    all_events.append(str(ev))
            except queue.Empty:
                break

        t.join(timeout=5)

        if failed:
            spinner_text.error("Eval failed — see error above.")
            return

        if report is None:
            spinner_text.empty()
            st.error("Eval did not return a report — check logs.")
            return

        spinner_text.success("Eval complete!")
        _refresh()

        # Persist so results survive any widget interaction (rerun) …
        st.session_state[f"report::{state_key}"] = {
            "report": report,
            "events": list(all_events),
        }
        # … and archive to disk so the run shows up in History mode.
        from skill_eval.reporting import save_report

        saved_path = save_report(report, _runs_dir(), label=state_key)
        if saved_path:
            st.caption(f"Run archived: `{saved_path}` (browse it in **History** mode)")

    # ------------------------------------------------------------------
    # Results — rendered OUTSIDE the button branch from session_state so
    # they survive any widget interaction that reruns the script.
    # ------------------------------------------------------------------
    stored = st.session_state.get(f"report::{state_key}")
    if not stored:
        return
    _render_single_results(
        st=st,
        pd=pd,
        report=stored["report"],
        events=stored["events"],
        verdict_line=verdict_line,
        agent_graph_dot=agent_graph_dot,
        state_key=state_key,
    )


def _render_single_results(
    *,
    st,  # type: ignore[type-arg]
    pd,  # type: ignore[type-arg]
    report,  # type: ignore[type-arg]
    events,  # type: ignore[type-arg]
    verdict_line,  # type: ignore[type-arg]
    agent_graph_dot,  # type: ignore[type-arg]
    state_key: str,
) -> None:
    """Render the full results funnel for a completed single-case report.

    Funnel (promptfoo / Langfuse pattern): headline delta metrics →
    per-criterion matrix with Δ → drill-down (rationales, diffs, traces).
    """
    from pathlib import Path

    import altair as alt

    from skill_eval.reporting import (
        ARM_COLORS,
        criterion_gap_rows,
        quality_cost_rows,
        report_to_json,
    )

    st.divider()
    st.subheader("Results: Baseline vs Challenger")

    # --- Run-config context: what exactly was compared ---
    cfg = report.config
    base_skill = Path(cfg.baseline_skill_path).name
    chal_skill = Path(cfg.challenger_skill_path).name
    bits = [
        f"skills: `{base_skill}` vs `{chal_skill}`",
        f"model: `{cfg.models[0]}`",
        f"max_turns: {cfg.max_turns}",
    ]
    if cfg.thinking_budget:
        bits.append(f"thinking: {cfg.thinking_budget}")
    if report.session_id:
        bits.append(f"Phoenix session: `{report.session_id[:12]}…`")
    st.caption(" · ".join(bits))
    with st.expander("Task brief & gold reference"):
        st.markdown(f"**Task brief**\n\n> {cfg.task_brief}")
        if report.gold_diff:
            st.markdown("**Gold reference diff** (what the judges compare against)")
            st.code(report.gold_diff, language="diff")

    # Resolve the two arms once (order not assumed).
    baseline_ar = next((ar for ar in report.arms if ar.arm.value == "baseline"), None)
    challenger_ar = next((ar for ar in report.arms if ar.arm.value == "challenger"), None)

    # --- Headline delta metrics (challenger framed against baseline) ---
    if baseline_ar is not None and challenger_ar is not None:
        b_m, c_m = baseline_ar.metrics, challenger_ar.metrics
        k1, k2, k3, k4 = st.columns(4)
        k1.metric(
            "Challenger total",
            f"{challenger_ar.total_score}/120",
            delta=challenger_ar.total_score - baseline_ar.total_score,
        )
        k2.metric("Baseline total", f"{baseline_ar.total_score}/120")
        k3.metric(
            "Questions asked",
            c_m.num_questions,
            delta=c_m.num_questions - b_m.num_questions,
        )
        k4.metric(
            "Tokens",
            f"{c_m.total_tokens:,}",
            delta=c_m.total_tokens - b_m.total_tokens,
            delta_color="inverse",  # more tokens = more cost = "worse"
        )

    # --- Dumbbell / gap chart: the difference per criterion, biggest first ---
    st.subheader("Where the skills differ (per-criterion gap)")
    st.caption(
        "Each line connects the two scores; the longer the line, the bigger the gap."
        " Sorted by challenger − baseline."
    )
    gap_rows = criterion_gap_rows(report)
    if gap_rows:
        order = [r["criterion"] for r in gap_rows]
        df_gap = pd.DataFrame(gap_rows)
        long = df_gap.melt(
            id_vars=["criterion", "gap"],
            value_vars=["baseline", "challenger"],
            var_name="arm",
            value_name="score",
        )
        y_enc = alt.Y("criterion:N", sort=order, title=None)
        color_enc = alt.Color(
            "arm:N",
            scale=alt.Scale(
                domain=["baseline", "challenger"],
                range=[ARM_COLORS["baseline"], ARM_COLORS["challenger"]],
            ),
            title="Arm",
        )
        connector = (
            alt.Chart(df_gap)
            .mark_rule(color="#bbbbbb", strokeWidth=2)
            .encode(
                y=y_enc,
                x=alt.X("baseline:Q", title="Score (0–20)", scale=alt.Scale(domain=[0, 20])),
                x2="challenger:Q",
            )
        )
        dots = (
            alt.Chart(long)
            .mark_circle(size=170, opacity=1.0)
            .encode(
                y=y_enc,
                x=alt.X("score:Q", scale=alt.Scale(domain=[0, 20])),
                color=color_enc,
                tooltip=["criterion:N", "arm:N", "score:Q", "gap:Q"],
            )
        )
        st.altair_chart((connector + dots).properties(height=280), width="stretch")

    # --- Score matrix + judge rationales (the drill-down layer) ---
    st.subheader("Judge scores & rationales")
    st.caption("Exact scores with Δ, then expand any criterion to read *why* the judges scored it.")
    if gap_rows:
        df_matrix = pd.DataFrame(gap_rows).rename(columns={"gap": "Δ"})

        def _delta_style(v) -> str:  # noqa: ANN001
            if v > 0:
                return "color: #2e7d32; font-weight: bold"
            if v < 0:
                return "color: #c62828; font-weight: bold"
            return "color: #777777"

        st.dataframe(
            df_matrix.set_index("criterion").style.map(_delta_style, subset=["Δ"]),
            width="stretch",
        )

        # rationale lookup: (arm, criterion) -> (score, rationale)
        rationale_map: dict[tuple[str, str], tuple[int, str]] = {}
        for ar in report.arms:
            for s in ar.scores:
                rationale_map[(ar.arm.value, s.criterion.value)] = (s.score, s.rationale)

        for r in gap_rows:
            crit = r["criterion"]
            label = (
                f"{crit} — baseline {r['baseline']}/20 vs challenger {r['challenger']}/20"
                f" (Δ {r['gap']:+d})"
            )
            with st.expander(label):
                col_b, col_c = st.columns(2)
                b_score, b_rat = rationale_map.get(("baseline", crit), (0, "—"))
                c_score, c_rat = rationale_map.get(("challenger", crit), (0, "—"))
                with col_b:
                    st.markdown(f"**Baseline — {b_score}/20**")
                    st.markdown(b_rat or "_no rationale_")
                with col_c:
                    st.markdown(f"**Challenger — {c_score}/20**")
                    st.markdown(c_rat or "_no rationale_")

    # --- Objective metrics + quality-vs-cost scatter ---
    st.subheader("Quality vs cost")
    st.caption("Up-and-to-the-left is better: higher score for fewer tokens.")
    qc_rows = quality_cost_rows(report)
    col_scatter, col_table = st.columns([3, 2])
    with col_scatter:
        if qc_rows:
            df_qc = pd.DataFrame(qc_rows)
            scatter = (
                alt.Chart(df_qc)
                .mark_circle(size=400, opacity=0.85)
                .encode(
                    x=alt.X("total_tokens:Q", title="Cost — total tokens"),
                    y=alt.Y(
                        "total_score:Q",
                        title="Quality — total score",
                        scale=alt.Scale(domain=[0, 120]),
                    ),
                    color=alt.Color(
                        "arm:N",
                        scale=alt.Scale(
                            domain=["baseline", "challenger"],
                            range=[ARM_COLORS["baseline"], ARM_COLORS["challenger"]],
                        ),
                        title="Arm",
                    ),
                    tooltip=[
                        "arm:N",
                        "total_score:Q",
                        "total_tokens:Q",
                        "wall_seconds:Q",
                        "num_turns:Q",
                        "num_questions:Q",
                    ],
                )
                .properties(height=300)
            )
            labels = scatter.mark_text(align="left", dx=10, fontWeight="bold").encode(text="arm:N")
            st.altair_chart(scatter + labels, width="stretch")
    with col_table:
        metrics_rows = []
        for ar in report.arms:
            m = ar.metrics
            metrics_rows.append(
                {
                    "arm": ar.arm.value,
                    "stop": ar.stop_reason or "—",
                    "tokens in/out": f"{m.input_tokens:,} / {m.output_tokens:,}",
                    "wall_seconds": round(m.wall_seconds, 2),
                    "num_turns": m.num_turns,
                    "num_questions": m.num_questions,
                }
            )
        st.dataframe(pd.DataFrame(metrics_rows).set_index("arm"), width="stretch")

    # Verdict
    st.success(f"Verdict: {verdict_line(report)}")

    # ------------------------------------------------------------------
    # What each arm actually changed (the evidence behind the scores)
    # ------------------------------------------------------------------
    st.subheader("What each arm changed")
    st.caption("The actual patch each taker produced — judge scores are about *this* code.")
    col_d_base, col_d_chal = st.columns(2)
    for ar, col in ((baseline_ar, col_d_base), (challenger_ar, col_d_chal)):
        with col:
            name = ar.arm.value if ar is not None else "—"
            st.markdown(f"**{name.capitalize()}**")
            if ar is None or not ar.diff:
                st.markdown("*(no diff captured)*")
            else:
                with st.expander(f"diff ({len(ar.diff):,} chars)", expanded=False):
                    st.code(ar.diff, language="diff")

    # ------------------------------------------------------------------
    # Clarifying questions side-by-side
    # ------------------------------------------------------------------
    st.subheader("Clarifying questions & stakeholder answers")
    st.caption(
        "What each skill made the agent ask — and what the (simulated) stakeholder"
        " answered. The concrete signal of capability; full trajectory in Phoenix."
    )

    def _render_qa(ar) -> None:  # noqa: ANN001
        if ar is None or not (ar.qa or ar.questions):
            st.markdown("*(no clarifying questions asked)*")
            return
        if ar.qa:
            for i, (q, a) in enumerate(ar.qa):
                st.markdown(f"{i + 1}. **{q}**")
                st.markdown(f"   > {a}")
        else:  # older reports: questions only
            st.markdown("\n".join(f"{i + 1}. {q}" for i, q in enumerate(ar.questions)))

    col_q_base, col_q_chal = st.columns(2)
    with col_q_base:
        st.markdown("**Baseline**")
        _render_qa(baseline_ar)
    with col_q_chal:
        st.markdown("**Challenger**")
        _render_qa(challenger_ar)

    # ------------------------------------------------------------------
    # Export + post-mortem details
    # ------------------------------------------------------------------
    st.download_button(
        "Download report (JSON)",
        data=report_to_json(report),
        file_name=f"skill_eval_report_{state_key}.json",
        mime="application/json",
        on_click="ignore",
        key=f"dl::{state_key}",
    )

    with st.expander("Architecture graph (final state) — hover nodes for their thinking"):
        criteria = [s.criterion.value for s in report.arms[0].scores] if report.arms else []
        pipeline = {
            "generator": "done",
            "sandbox": "done",
            "takers": "done",
            "judges": "done",
            "report": "done",
        }
        taker_state = {
            ar.arm.value: {
                "status": "done",
                "stop_reason": ar.stop_reason or "—",
                "num_questions": ar.metrics.num_questions,
                "num_turns": ar.metrics.num_turns,
                "wall_seconds": round(ar.metrics.wall_seconds, 1),
            }
            for ar in report.arms
        }
        js_map = {
            (ar.arm.value, s.criterion.value): {"status": "done", "score": s.score}
            for ar in report.arms
            for s in ar.scores
        }
        final_meta = {
            "baseline_skill": base_skill,
            "challenger_skill": chal_skill,
            "task_brief": cfg.task_brief,
            "verdict": report.pairwise_verdict,
            "rationales": {
                (ar.arm.value, s.criterion.value): s.rationale
                for ar in report.arms
                for s in ar.scores
            },
        }
        if criteria:
            st.graphviz_chart(
                agent_graph_dot(pipeline, taker_state, js_map, final_meta), width="stretch"
            )

    with st.expander(f"Event log ({len(events)} events)"):
        st.markdown("\n\n".join(events) if events else "_no events_")


def _run_custom_mode(
    *,
    st,  # type: ignore[type-arg]
    pd,  # type: ignore[type-arg]
    queue,  # type: ignore[type-arg]
    shutil,  # type: ignore[type-arg]
    tempfile,  # type: ignore[type-arg]
    threading,  # type: ignore[type-arg]
    run_eval,  # type: ignore[type-arg]
    verdict_line,  # type: ignore[type-arg]
    agent_graph_dot,  # type: ignore[type-arg]
    sim_make_simulator,  # type: ignore[type-arg]
    sim_run_judge,  # type: ignore[type-arg]
    sim_run_taker,  # type: ignore[type-arg]
) -> None:
    """Custom mode: bring-your-own skills (and budgets) on a chosen task fixture."""
    from pathlib import Path

    from skill_eval.flagship_case import TASK_BRIEF as FLAGSHIP_BRIEF
    from skill_eval.flagship_case import build_flagship_case
    from skill_eval.sample_repo import TASK_BRIEF as SAMPLE_BRIEF
    from skill_eval.sample_repo import build_sample_repo

    st.caption(
        "Two skills in, scored comparison out. Edit anything below — nothing runs"
        " until you submit. The default matchup is the flagship"
        " *ship-it-fast vs disciplined* race."
    )

    root = Path(__file__).resolve().parent

    def _skill_text(name: str) -> str:
        p = root / "flagship" / "skills" / name / "SKILL.md"
        try:
            return p.read_text()
        except Exception:
            return f"---\nname: {name}\ndescription: describe the skill here\n---\n\n# {name}\n"

    FIXTURES = {
        "Flagship: prorate_refund (under-specified — rewards asking)": FLAGSHIP_BRIEF,
        "Sample: calculator add bug (trivial)": SAMPLE_BRIEF,
    }

    with st.form("custom_run"):
        task_choice = st.selectbox(
            "Task fixture",
            list(FIXTURES),
            help=(
                "The before/after repo the agents work on. Gold-based criteria"
                " (correctness, distance_to_gold) stay meaningful only if your"
                " brief still targets the fixture's stub."
            ),
        )
        task_brief = st.text_area("Task brief", value=FLAGSHIP_BRIEF, height=140)

        col_b, col_c = st.columns(2)
        with col_b:
            base_name = st.text_input("Baseline skill name", "ship-it-fast")
            base_md = st.text_area(
                "Baseline SKILL.md", value=_skill_text("ship-it-fast"), height=300
            )
        with col_c:
            chal_name = st.text_input("Challenger skill name", "disciplined")
            chal_md = st.text_area(
                "Challenger SKILL.md", value=_skill_text("disciplined"), height=300
            )

        col1, col2, col3 = st.columns(3)
        max_turns = col1.number_input("max_turns", min_value=1, max_value=100, value=30)
        thinking_budget = col2.number_input(
            "thinking budget (0 = off)", min_value=0, max_value=32000, value=2048, step=512
        )
        col_j1, col_j2 = st.columns(2)
        judge_model = col_j1.selectbox(
            "Judge model",
            ["claude-haiku-4-5", "claude-sonnet-4-6"],
            help=(
                "Decoupling the judge from the taker model reduces same-family"
                " self-preference bias. Sonnet judges cost more but grade better."
            ),
        )
        judges_k = col_j2.number_input(
            "Judges per criterion (k)",
            min_value=1,
            max_value=5,
            value=1,
            help="k replicate judges per criterion; the median wins and the spread is recorded.",
        )
        real_agents = col3.toggle(
            "Real Haiku agents (~$0.40)",
            value=True,
            key="custom_real_agents",
            help=(
                "Off = free simulated components. NOTE: the simulated taker ignores"
                " skill text entirely — only useful to demo the flow."
            ),
        )

        submitted = st.form_submit_button("Run custom eval", type="primary")

    errors: list[str] = []
    if submitted:
        if not task_brief.strip():
            errors.append("Task brief is empty.")
        if not base_md.strip():
            errors.append("Baseline skill markdown is empty.")
        if not chal_md.strip():
            errors.append("Challenger skill markdown is empty.")
        for e in errors:
            st.error(e)

    # Capture plain values for the background thread (no st.* in there).
    _brief = task_brief
    _base_md, _chal_md = base_md, chal_md
    _b_slug = _slug(base_name, "baseline-skill")
    _c_slug = _slug(chal_name, "challenger-skill")
    if _b_slug == _c_slug:
        _c_slug = f"{_c_slug}-challenger"
    _max_turns = int(max_turns)
    _thinking = int(thinking_budget) or None
    _judge_model = str(judge_model)
    _judges_k = int(judges_k)

    _base_builder = build_flagship_case if task_choice.startswith("Flagship") else build_sample_repo

    graph_meta = {
        "baseline_skill": _b_slug,
        "challenger_skill": _c_slug,
        "fixture": task_choice,
        "task_brief": _brief,
    }

    # The whole architecture, upfront: skills → (mock) test generator → test
    # cases → sandbox → takers ↔ simulator → judges → assemble → report.
    # During a run the same graph lights up live; hover any node for its
    # "thinking". Hidden once results exist (the final graph lives there).
    if not submitted and "report::custom" not in st.session_state:
        st.markdown("**Pipeline** — hover any node to see what it does")
        st.graphviz_chart(
            agent_graph_dot({}, {}, {}, graph_meta),
            width="stretch",
        )

    def build_custom_case(base_dir: str):  # -> RunConfig
        import dataclasses

        cfg = _base_builder(base_dir)
        skills_root = Path(base_dir) / "custom_skills"
        b_dir = skills_root / _b_slug
        c_dir = skills_root / _c_slug
        for d, md in ((b_dir, _base_md), (c_dir, _chal_md)):
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text(md)
        return dataclasses.replace(
            cfg,
            task_brief=_brief,
            baseline_skill_path=str(b_dir),
            challenger_skill_path=str(c_dir),
            max_turns=_max_turns,
            thinking_budget=_thinking,
            judge_model=_judge_model,
            judges_per_criterion=_judges_k,
        )

    _run_single_case(
        st=st,
        pd=pd,
        queue=queue,
        shutil=shutil,
        tempfile=tempfile,
        threading=threading,
        use_real=real_agents,
        run_eval=run_eval,
        verdict_line=verdict_line,
        build_cfg=build_custom_case,
        force_real=False,
        sim_make_simulator=sim_make_simulator,
        sim_run_judge=sim_run_judge,
        sim_run_taker=sim_run_taker,
        agent_graph_dot=agent_graph_dot,
        state_key="custom",
        trigger=bool(submitted and not errors),
        graph_meta=graph_meta,
    )


def _run_history_mode(
    *,
    st,  # type: ignore[type-arg]
    pd,  # type: ignore[type-arg]
    verdict_line,  # type: ignore[type-arg]
    agent_graph_dot,  # type: ignore[type-arg]
) -> None:
    """History mode: browse archived runs and diff two of them (run-over-run).

    The promptfoo "Eval Actions → Compare" / Langfuse baseline-compare pattern:
    pick a candidate run, optionally pick an earlier baseline run, and read
    green/red per-criterion deltas — the view that answers "did my skill edit
    actually help?".
    """
    from skill_eval.reporting import list_saved_runs, load_report, run_delta_rows

    st.caption(
        "Every completed Single/Flagship/Custom run is archived to `runs/` as JSON."
        " Pick one to re-read it, or compare two to see what a skill edit changed."
    )

    runs = list_saved_runs(_runs_dir())
    if not runs:
        st.info("No saved runs yet — finish a Single, Flagship, or Custom run first.")
        return

    names = [r["name"] for r in runs]
    paths = {r["name"]: r["path"] for r in runs}

    sel = st.selectbox("Run to view (B — candidate)", names)
    try:
        report_b = load_report(paths[sel])
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load run: {exc}")
        return

    # --- Run-over-run compare (optional) ---
    others = [n for n in names if n != sel]
    if others:
        with st.expander("Compare against an earlier run (A — baseline run)"):
            sel_a = st.selectbox("Baseline run (A)", others)
            try:
                report_a = load_report(paths[sel_a])
            except Exception as exc:  # noqa: BLE001
                st.error(f"Could not load baseline run: {exc}")
                report_a = None
            if report_a is not None:
                # Headline: total score movement per arm (B − A)
                totals_a = {ar.arm.value: ar.total_score for ar in report_a.arms}
                totals_b = {ar.arm.value: ar.total_score for ar in report_b.arms}
                col_b_, col_c_ = st.columns(2)
                for arm_name, col in (("baseline", col_b_), ("challenger", col_c_)):
                    col.metric(
                        f"{arm_name} total (B)",
                        f"{totals_b.get(arm_name, 0)}/120",
                        delta=totals_b.get(arm_name, 0) - totals_a.get(arm_name, 0),
                    )

                rows = run_delta_rows(report_a, report_b)
                df_long = pd.DataFrame(rows)
                wide = df_long.pivot(index="criterion", columns="arm")
                # columns become (run_a|run_b|delta, arm); flatten for display
                wide.columns = [f"{arm} {col}" for col, arm in wide.columns]
                ordered = [
                    c
                    for c in (
                        "baseline run_a",
                        "baseline run_b",
                        "baseline delta",
                        "challenger run_a",
                        "challenger run_b",
                        "challenger delta",
                    )
                    if c in wide.columns
                ]
                wide = wide[ordered].rename(
                    columns=lambda c: (
                        c.replace("run_a", "A").replace("run_b", "B").replace("delta", "Δ")
                    )
                )

                def _delta_style(v) -> str:  # noqa: ANN001
                    if v > 0:
                        return "color: #2e7d32; font-weight: bold"
                    if v < 0:
                        return "color: #c62828; font-weight: bold"
                    return "color: #777777"

                delta_cols = [c for c in wide.columns if c.endswith("Δ")]
                st.dataframe(wide.style.map(_delta_style, subset=delta_cols), width="stretch")

    # --- Full results funnel for the selected run ---
    _render_single_results(
        st=st,
        pd=pd,
        report=report_b,
        events=[],
        verdict_line=verdict_line,
        agent_graph_dot=agent_graph_dot,
        state_key="history",
    )


# ---------------------------------------------------------------------------
# Entry point: run when Streamlit executes the script (or __main__)
# ---------------------------------------------------------------------------

if __name__ == "__main__" or _is_streamlit():
    main()
