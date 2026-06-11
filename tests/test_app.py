"""Headless UI tests via Streamlit's official AppTest framework.

These boot the real dashboard script, click the real buttons, and assert on
the rendered element tree — no browser, no network.  Phoenix init is skipped
by pre-seeding ``session_state["phoenix_url"]`` (the header only calls
``init_phoenix()`` when that key is absent).  Run archiving is redirected to
a tmp dir via ``SKILL_EVAL_RUNS_DIR`` so tests never pollute ``runs/``.

The app has exactly two tabs — "Run eval" (the bring-your-own-skills form +
live architecture graph) and "History" — and AppTest renders both each run.
"""

import pytest
from streamlit.testing.v1 import AppTest


@pytest.fixture(autouse=True)
def _isolate_runs_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_EVAL_RUNS_DIR", str(tmp_path / "runs"))


def _boot() -> AppTest:
    at = AppTest.from_file("app.py", default_timeout=120)
    at.session_state["phoenix_url"] = None  # skip Phoenix init: no network in tests
    return at


def _click_button(at: AppTest, label: str) -> AppTest:
    matches = [b for b in at.button if b.label == label]
    assert matches, f"no button labelled {label!r}; found {[b.label for b in at.button]}"
    matches[0].click()
    return at.run()


def test_app_boots_without_errors():
    at = _boot().run()
    assert not at.exception
    # Two tabs only: the run form and history. No mode radio, no sidebar widgets.
    assert not at.radio
    assert [b.label for b in at.button] == ["Run custom eval"]


def test_run_tab_runs_user_skills_and_results_persist():
    at = _boot().run()

    # Free simulated components for the test; skill dirs are still written.
    at.toggle(key="custom_real_agents").set_value(False)
    at = _click_button(at, "Run custom eval")
    assert not at.exception

    # The user-pasted skills were materialised and wired into the RunConfig.
    stored = at.session_state["report::custom"]
    cfg = stored["report"].config
    assert "custom_skills" in cfg.baseline_skill_path
    assert "custom_skills" in cfg.challenger_skill_path
    assert cfg.baseline_skill_path != cfg.challenger_skill_path

    # The results funnel rendered, rationales included.
    headers = [h.value for h in at.subheader]
    assert any("Results" in h for h in headers)
    assert any("rationale" in h.lower() for h in headers)

    # A plain rerun (any widget interaction) must NOT lose the results.
    at = at.run()
    assert not at.exception
    headers = [h.value for h in at.subheader]
    assert any("Results" in h for h in headers)


def test_history_tab_lists_archived_runs():
    import os
    from pathlib import Path

    at = _boot().run()
    at.toggle(key="custom_real_agents").set_value(False)
    at = _click_button(at, "Run custom eval")
    assert not at.exception

    # The completed run auto-archived to SKILL_EVAL_RUNS_DIR …
    runs_dir = Path(os.environ["SKILL_EVAL_RUNS_DIR"])
    assert len(list(runs_dir.glob("*.json"))) == 1

    # … and the History tab (rendered in the same pass) lists it.
    assert at.selectbox, "expected a run selectbox in the History tab"
