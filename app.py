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
        st.markdown("### Phase A")
        st.info("Phase A = simulated data (no API)")
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

        col_base, col_chal = st.columns(2)
        with col_base:
            st.markdown("**Baseline**")
            base_log = st.empty()
        with col_chal:
            st.markdown("**Challenger**")
            chal_log = st.empty()

        event_log_placeholder = st.empty()

        # Accumulate per-arm messages and global event log
        arm_msgs: dict[str, list[str]] = {"baseline": [], "challenger": []}
        all_events: list[str] = []

        def _refresh_ui() -> None:
            base_log.markdown("\n\n".join(arm_msgs["baseline"]) or "_waiting…_")
            chal_log.markdown("\n\n".join(arm_msgs["challenger"]) or "_waiting…_")
            event_log_placeholder.markdown(
                "**Event log**\n\n" + "\n\n".join(all_events[-20:])
                if all_events
                else "_no events yet_"
            )

        # ------------------------------------------------------------------
        # Background thread: run_eval pushes events into a queue
        # ------------------------------------------------------------------
        q: queue.Queue = queue.Queue()

        def _background() -> None:
            tmp = tempfile.mkdtemp()
            try:
                cfg = build_sample_repo(tmp)

                def on_event(ev: dict) -> None:
                    q.put(("event", ev))

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
                _refresh_ui()
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
            msg = ev.get("msg", "")
            criterion = ev.get("criterion", "")

            # Build a short human-readable line
            if stage == "sandbox":
                line = f"[sandbox] {msg}"
                all_events.append(line)
            elif stage == "taker":
                line = f"[taker:{arm}] {msg}"
                if arm in arm_msgs:
                    arm_msgs[arm].append(f"**{msg.upper()}**")
                all_events.append(line)
            elif stage == "judge":
                line = f"[judge:{arm}] criterion={criterion}"
                if arm in arm_msgs:
                    arm_msgs[arm].append(f"judge: {criterion}")
                all_events.append(line)
            elif stage == "report":
                verdict = ev.get("verdict", "")
                line = f"[report] {verdict}"
                all_events.append(line)
            else:
                all_events.append(f"[{stage}] {ev}")

            _refresh_ui()

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
        _refresh_ui()
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
