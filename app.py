"""Streamlit dashboard for the skill-eval Phase A walking skeleton.

Run with:
    uv run streamlit run app.py

The module can be imported without side-effects (no Streamlit calls,
no Phoenix launch, no eval run happen at import time).  All live logic
lives inside ``main()``, which Streamlit calls automatically when it
executes the script.
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
        batch_per_case_totals,
        batch_per_criterion_avg,
        batch_score_distribution,
        batch_win_summary,
        init_phoenix,
        scores_table,
        verdict_line,
    )
    from skill_eval.sample_repo import build_sample_repo
    from skill_eval.simulated import sim_make_simulator, sim_run_judge, sim_run_taker

    # ------------------------------------------------------------------
    # Page config
    # ------------------------------------------------------------------
    st.set_page_config(
        page_title="Skill Eval — Phase A",
        page_icon="⚖️",
        layout="wide",
    )

    st.title("Skill Eval — Phase A Live Race")

    # ------------------------------------------------------------------
    # Mode selector
    # ------------------------------------------------------------------
    mode = st.radio("Mode", ["Single case", "Batch (10 cases)", "Flagship"], horizontal=True)

    # Sidebar
    with st.sidebar:
        st.markdown("### Phase A / B")
        if mode == "Flagship":
            st.info("Flagship always uses real Haiku agents.")
            use_real = False  # sidebar toggle unused in Flagship mode
        elif mode == "Batch (10 cases)":
            use_real = st.checkbox(
                "Use real Haiku agents (Phase B — Batch of 10 ≈ $1.5–2 with real agents)",
                value=False,
            )
        else:
            use_real = st.checkbox("Use real Haiku agents (Phase B — ~$0.10-0.20/run)", value=False)
        if mode != "Flagship":
            if use_real:
                st.warning("Real API calls — costs money!")
            else:
                st.info("Simulated data (no API)")
                st.markdown("All components are deterministic Python — zero LLM cost.")

        # Phoenix link (cached in session so we don't relaunch on every rerun)
        if "phoenix_url" not in st.session_state:
            st.session_state["phoenix_url"] = init_phoenix()
        phoenix_url = st.session_state["phoenix_url"]
        if phoenix_url:
            st.markdown(f"[Open Phoenix traces]({phoenix_url})")
        else:
            st.caption("Phoenix not running — start it with `just phoenix`, then rerun.")

    # ------------------------------------------------------------------
    # Single case mode
    # ------------------------------------------------------------------
    if mode == "Single case":
        _run_single_case(
            st=st,
            pd=pd,
            queue=queue,
            shutil=shutil,
            tempfile=tempfile,
            threading=threading,
            use_real=use_real,
            run_eval=run_eval,
            scores_table=scores_table,
            verdict_line=verdict_line,
            build_cfg=build_sample_repo,
            force_real=False,
            sim_make_simulator=sim_make_simulator,
            sim_run_judge=sim_run_judge,
            sim_run_taker=sim_run_taker,
            agent_graph_dot=agent_graph_dot,
        )

    # ------------------------------------------------------------------
    # Flagship mode
    # ------------------------------------------------------------------
    elif mode == "Flagship":
        _run_flagship_mode(
            st=st,
            pd=pd,
            queue=queue,
            shutil=shutil,
            tempfile=tempfile,
            threading=threading,
            run_eval=run_eval,
            scores_table=scores_table,
            verdict_line=verdict_line,
            agent_graph_dot=agent_graph_dot,
            sim_make_simulator=sim_make_simulator,
            sim_run_judge=sim_run_judge,
            sim_run_taker=sim_run_taker,
        )

    # ------------------------------------------------------------------
    # Batch (10 cases) mode
    # ------------------------------------------------------------------
    else:
        _run_batch_mode(
            st=st,
            pd=pd,
            queue=queue,
            tempfile=tempfile,
            threading=threading,
            use_real=use_real,
            batch_win_summary=batch_win_summary,
            batch_per_case_totals=batch_per_case_totals,
            batch_per_criterion_avg=batch_per_criterion_avg,
            batch_score_distribution=batch_score_distribution,
            sim_make_simulator=sim_make_simulator,
            sim_run_judge=sim_run_judge,
            sim_run_taker=sim_run_taker,
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
    scores_table,  # type: ignore[type-arg]
    verdict_line,  # type: ignore[type-arg]
    build_cfg=None,  # type: ignore[type-arg]  callable(base_dir) -> RunConfig
    force_real: bool = False,
    sim_make_simulator,  # type: ignore[type-arg]
    sim_run_judge,  # type: ignore[type-arg]
    sim_run_taker,  # type: ignore[type-arg]
    agent_graph_dot,  # type: ignore[type-arg]
    button_label: str = "Run eval",
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
    button_label:
        Label for the primary action button.
    """
    if st.button(button_label, type="primary"):
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
            "sandbox": "pending",
            "takers": "pending",
            "judges": "pending",
            "report": "pending",
        }

        # arm -> {"status": str, "stop_reason": str, "num_questions": int}
        taker_state: dict[str, dict] = {
            "baseline": {},
            "challenger": {},
        }

        # (arm, criterion) -> cell string
        judge_cells: dict[tuple[str, str], str] = {}

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
                    panel.markdown(f"✅ done  \nstop: `{stop}`  \nquestions: **{nq}**")

            # --- Judges grid ---
            rows = []
            for crit in CRITERIA_ORDER:
                base_cell = judge_cells.get(("baseline", crit), "⬜")
                chal_cell = judge_cells.get(("challenger", crit), "⬜")
                rows.append({"criterion": crit, "baseline": base_cell, "challenger": chal_cell})
            judges_df = pd.DataFrame(rows).set_index("criterion")
            judges_placeholder.dataframe(judges_df, use_container_width=True)

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
            graph_placeholder.graphviz_chart(
                agent_graph_dot(pipeline, taker_state, js_map),
                use_container_width=True,
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
        spinner_text = st.empty()
        spinner_text.info("Running…")

        while t.is_alive() or not q.empty():
            try:
                kind, payload = q.get(timeout=0.05)
            except queue.Empty:
                _refresh()
                continue

            if kind == "done":
                report = payload
                break

            if kind == "error":
                st.error(f"Eval failed: {payload}")
                break

            # kind == "event"
            ev: dict = payload
            stage = ev.get("stage", "?")
            arm = ev.get("arm", "")
            criterion = ev.get("criterion", "")

            if stage == "sandbox":
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
                        }
                        all_events.append(
                            f"[taker:{arm}] done — stop={ev.get('stop_reason')} "
                            f"questions={ev.get('num_questions')}"
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
                    all_events.append(f"[judge:{arm}] {criterion} done — score={score}")

            elif stage == "report":
                pipeline["judges"] = "done"
                pipeline["report"] = "done"
                verdict = ev.get("verdict", "")
                all_events.append(f"[report] {verdict}")

            else:
                all_events.append(f"[{stage}] {ev}")

            _refresh()

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

        spinner_text.success("Eval complete!")
        _refresh()
        t.join(timeout=5)

        # ------------------------------------------------------------------
        # Results
        # ------------------------------------------------------------------
        if report is None:
            st.error("Eval did not return a report — check logs.")
            return

        import altair as alt

        from skill_eval.reporting import (
            ARM_COLORS,
            arm_color_list,
            criterion_gap_rows,
            quality_cost_rows,
        )

        st.divider()
        st.subheader("Results: Baseline vs Challenger")

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

        # --- Grouped 0–20 bars per criterion (consistent arm colours) ---
        rows = scores_table(report)
        df = pd.DataFrame(rows).set_index("criterion")
        ordered_cols = [c for c in ("baseline", "challenger") if c in df.columns]
        st.bar_chart(
            df[ordered_cols],
            use_container_width=True,
            stack=False,
            color=arm_color_list(ordered_cols),
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
            st.altair_chart((connector + dots).properties(height=280), use_container_width=True)

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
                labels = scatter.mark_text(align="left", dx=10, fontWeight="bold").encode(
                    text="arm:N"
                )
                st.altair_chart(scatter + labels, use_container_width=True)
        with col_table:
            metrics_rows = []
            for ar in report.arms:
                m = ar.metrics
                metrics_rows.append(
                    {
                        "arm": ar.arm.value,
                        "total_tokens": m.total_tokens,
                        "wall_seconds": round(m.wall_seconds, 2),
                        "num_turns": m.num_turns,
                        "num_questions": m.num_questions,
                    }
                )
            st.dataframe(pd.DataFrame(metrics_rows).set_index("arm"), use_container_width=True)

        # Verdict
        st.success(f"Verdict: {verdict_line(report)}")

        # ------------------------------------------------------------------
        # Clarifying questions side-by-side
        # ------------------------------------------------------------------
        st.subheader("Clarifying questions asked")
        st.caption(
            "What each skill made the agent ask — the concrete signal of capability."
            " Full reasoning trajectory in Phoenix."
        )

        # Pull the two ArmReports by arm value (order not assumed)
        baseline_ar = next((ar for ar in report.arms if ar.arm.value == "baseline"), None)
        challenger_ar = next((ar for ar in report.arms if ar.arm.value == "challenger"), None)

        col_q_base, col_q_chal = st.columns(2)

        with col_q_base:
            st.markdown("**Baseline**")
            if baseline_ar is None or not baseline_ar.questions:
                st.markdown("*(no clarifying questions asked)*")
            else:
                q_lines = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(baseline_ar.questions))
                st.markdown(q_lines)

        with col_q_chal:
            st.markdown("**Challenger**")
            if challenger_ar is None or not challenger_ar.questions:
                st.markdown("*(no clarifying questions asked)*")
            else:
                q_lines = "\n".join(f"{i + 1}. {q}" for i, q in enumerate(challenger_ar.questions))
                st.markdown(q_lines)


def _run_flagship_mode(
    *,
    st,  # type: ignore[type-arg]
    pd,  # type: ignore[type-arg]
    queue,  # type: ignore[type-arg]
    shutil,  # type: ignore[type-arg]
    tempfile,  # type: ignore[type-arg]
    threading,  # type: ignore[type-arg]
    run_eval,  # type: ignore[type-arg]
    scores_table,  # type: ignore[type-arg]
    verdict_line,  # type: ignore[type-arg]
    agent_graph_dot,  # type: ignore[type-arg]
    sim_make_simulator,  # type: ignore[type-arg]
    sim_run_judge,  # type: ignore[type-arg]
    sim_run_taker,  # type: ignore[type-arg]
) -> None:
    """Flagship mode: disciplined vs ship-it-fast on prorate_refund with real Haiku agents."""
    st.caption(
        "Disciplined skill vs ship-it-fast skill on an under-specified `prorate_refund` task"
        " — runs **real Haiku agents** (~$0.40)."
    )

    from skill_eval.flagship_case import build_flagship_case

    _run_single_case(
        st=st,
        pd=pd,
        queue=queue,
        shutil=shutil,
        tempfile=tempfile,
        threading=threading,
        use_real=False,  # overridden by force_real
        run_eval=run_eval,
        scores_table=scores_table,
        verdict_line=verdict_line,
        build_cfg=build_flagship_case,
        force_real=True,
        sim_make_simulator=sim_make_simulator,
        sim_run_judge=sim_run_judge,
        sim_run_taker=sim_run_taker,
        agent_graph_dot=agent_graph_dot,
        button_label="Run flagship",
    )


def _run_batch_mode(
    *,
    st,  # type: ignore[type-arg]
    pd,  # type: ignore[type-arg]
    queue,  # type: ignore[type-arg]
    tempfile,  # type: ignore[type-arg]
    threading,  # type: ignore[type-arg]
    use_real: bool,
    batch_win_summary,  # type: ignore[type-arg]
    batch_per_case_totals,  # type: ignore[type-arg]
    batch_per_criterion_avg,  # type: ignore[type-arg]
    batch_score_distribution,  # type: ignore[type-arg]
    sim_make_simulator,  # type: ignore[type-arg]
    sim_run_judge,  # type: ignore[type-arg]
    sim_run_taker,  # type: ignore[type-arg]
) -> None:
    """Batch (10 cases) view: run all sample cases and show aggregate viz."""
    from skill_eval.batch import run_batch
    from skill_eval.sample_cases import build_sample_cases

    if not st.button("Run batch", type="primary"):
        st.info("Click **Run batch** to evaluate all 10 sample cases.")
        return

    st.divider()
    st.subheader("Batch progress")

    # ------------------------------------------------------------------
    # Placeholders for live progress
    # ------------------------------------------------------------------
    progress_bar = st.progress(0.0)
    status_placeholder = st.empty()
    status_placeholder.info("Starting batch…")
    case_log_placeholder = st.empty()

    # ------------------------------------------------------------------
    # Background thread: run_batch pushes events into a queue
    # ------------------------------------------------------------------
    q: queue.Queue = queue.Queue()
    _use_real = use_real

    def _background() -> None:
        tmp = tempfile.mkdtemp()
        try:
            cfgs = build_sample_cases(tmp)
            total = len(cfgs)

            def on_event(ev: dict) -> None:
                q.put(("event", ev, total))

            if _use_real:
                from skill_eval.judge import run_judge
                from skill_eval.simulator import make_simulator
                from skill_eval.taker import run_taker

                reports = run_batch(
                    cfgs,
                    taker_fn=run_taker,
                    simulator_factory=make_simulator,
                    judge_fn=run_judge,
                    max_cases=4,
                    on_event=on_event,
                )
            else:
                reports = run_batch(
                    cfgs,
                    taker_fn=sim_run_taker,
                    simulator_factory=sim_make_simulator,
                    judge_fn=sim_run_judge,
                    max_cases=4,
                    on_event=on_event,
                )
            q.put(("done", reports, total))
        except Exception as exc:
            q.put(("error", exc, 0))

    t = threading.Thread(target=_background, daemon=True)
    t.start()

    # ------------------------------------------------------------------
    # Drain queue: track per-case completion via "report" stage events
    # ------------------------------------------------------------------
    reports = None
    cases_done: set[int] = set()
    case_lines: list[str] = []
    total_cases = 10  # we know it's 10

    while t.is_alive() or not q.empty():
        try:
            item = q.get(timeout=0.05)
        except queue.Empty:
            continue

        kind = item[0]
        if kind == "done":
            reports = item[1]
            break
        if kind == "error":
            st.error(f"Batch failed: {item[1]}")
            return

        # kind == "event"
        ev: dict = item[1]
        case_idx: int = ev.get("case", -1)
        stage = ev.get("stage", "")

        if stage == "report" and case_idx not in cases_done:
            cases_done.add(case_idx)
            case_lines.append(f"case {case_idx + 1} done")
            frac = len(cases_done) / total_cases
            progress_bar.progress(frac)
            status_placeholder.info(f"{len(cases_done)} / {total_cases} cases done…")
            case_log_placeholder.markdown("\n\n".join(case_lines[-total_cases:]))

    t.join(timeout=10)

    if reports is None:
        st.error("Batch did not return reports — check logs.")
        return

    progress_bar.progress(1.0)
    status_placeholder.success(f"All {total_cases} cases complete!")

    # ------------------------------------------------------------------
    # Aggregate visualisations
    # ------------------------------------------------------------------
    st.divider()
    st.subheader("Aggregate: Baseline vs Challenger")

    # 1. Win summary metrics
    win_summary = batch_win_summary(reports)
    col_c, col_b, col_t = st.columns(3)
    col_c.metric("Challenger wins", win_summary["challenger"])
    col_b.metric("Baseline wins", win_summary["baseline"])
    col_t.metric("Ties", win_summary["tie"])

    import altair as alt

    from skill_eval.reporting import ARM_COLORS, arm_color_list, batch_criterion_gap_rows

    _arm_scale = alt.Scale(
        domain=["baseline", "challenger"],
        range=[ARM_COLORS["baseline"], ARM_COLORS["challenger"]],
    )

    # 2. Per-case totals bar chart
    st.subheader("Per-case total scores")
    per_case = batch_per_case_totals(reports)
    df_cases = pd.DataFrame(per_case).set_index("case")
    st.bar_chart(
        df_cases[["baseline", "challenger"]],
        use_container_width=True,
        stack=False,
        color=arm_color_list(["baseline", "challenger"]),
    )

    # 3. Per-criterion averages bar chart
    st.subheader("Per-criterion averages")
    per_crit = batch_per_criterion_avg(reports)
    df_crit = pd.DataFrame(per_crit).set_index("criterion")
    st.bar_chart(
        df_crit[["baseline", "challenger"]],
        use_container_width=True,
        stack=False,
        color=arm_color_list(["baseline", "challenger"]),
    )

    # 3b. Per-criterion gap (dumbbell) — biggest average difference first
    st.subheader("Where the skills differ (avg per-criterion gap)")
    gap_rows = batch_criterion_gap_rows(reports)
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
        connector = (
            alt.Chart(df_gap)
            .mark_rule(color="#bbbbbb", strokeWidth=2)
            .encode(
                y=y_enc,
                x=alt.X("baseline:Q", title="Avg score (0–20)", scale=alt.Scale(domain=[0, 20])),
                x2="challenger:Q",
            )
        )
        dots = (
            alt.Chart(long)
            .mark_circle(size=170, opacity=1.0)
            .encode(
                y=y_enc,
                x=alt.X("score:Q", scale=alt.Scale(domain=[0, 20])),
                color=alt.Color("arm:N", scale=_arm_scale, title="Arm"),
                tooltip=["criterion:N", "arm:N", "score:Q", "gap:Q"],
            )
        )
        st.altair_chart((connector + dots).properties(height=280), use_container_width=True)

    # 4. Score distributions (grouped boxplot per criterion, baseline vs challenger)
    st.subheader("Score distributions")
    dist_rows = batch_score_distribution(reports)
    if dist_rows:
        df_dist = pd.DataFrame(dist_rows)
        chart = (
            alt.Chart(df_dist)
            .mark_boxplot()
            .encode(
                x=alt.X("criterion:N", title="Criterion"),
                y=alt.Y("score:Q", title="Score", scale=alt.Scale(domain=[0, 20])),
                color=alt.Color("arm:N", title="Arm", scale=_arm_scale),
                xOffset=alt.XOffset("arm:N"),
            )
            .properties(height=350)
        )
        st.altair_chart(chart, use_container_width=True)

    # 5. Detailed per-case table (was 4)
    st.subheader("Per-case detail")
    table_rows = []
    for row in per_case:
        b_total = row["baseline"]
        c_total = row["challenger"]
        if c_total > b_total:
            winner = "challenger"
        elif b_total > c_total:
            winner = "baseline"
        else:
            winner = "tie"
        table_rows.append(
            {
                "case": row["case"],
                "baseline total": b_total,
                "challenger total": c_total,
                "winner": winner,
            }
        )
    st.dataframe(pd.DataFrame(table_rows).set_index("case"), use_container_width=True)


# ---------------------------------------------------------------------------
# Entry point: run when Streamlit executes the script (or __main__)
# ---------------------------------------------------------------------------

if __name__ == "__main__" or _is_streamlit():
    main()
