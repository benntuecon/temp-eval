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
    from skill_eval.reporting import init_phoenix, scores_table, verdict_line
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

    # Sidebar
    with st.sidebar:
        st.markdown("### Phase A / B")
        use_real = st.checkbox("Use real Haiku agents (Phase B — ~$0.10-0.20/run)", value=False)
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
            st.caption("Phoenix not available — tracing skipped.")

    # ------------------------------------------------------------------
    # Run eval button
    # ------------------------------------------------------------------
    if st.button("Run eval", type="primary"):
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

        # Capture widget value before entering the background thread — Streamlit
        # widgets cannot be accessed from a non-Streamlit thread.
        _use_real = use_real

        def _background() -> None:
            tmp = tempfile.mkdtemp()
            try:
                cfg = build_sample_repo(tmp)

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

        st.divider()
        st.subheader("Results: Baseline vs Challenger")

        # Grouped bar chart via scores_table -> DataFrame
        rows = scores_table(report)
        df = pd.DataFrame(rows).set_index("criterion")
        st.bar_chart(df, use_container_width=True)

        # Objective metrics table
        st.subheader("Objective metrics")
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


# ---------------------------------------------------------------------------
# Entry point: run when Streamlit executes the script (or __main__)
# ---------------------------------------------------------------------------

if __name__ == "__main__" or _is_streamlit():
    main()
