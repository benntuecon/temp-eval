"""Headless UI tests via Streamlit's official AppTest framework.

These boot the real dashboard script, click the real buttons, and assert on
the rendered element tree — no browser, no network.  Phoenix init is skipped
by pre-seeding ``session_state["phoenix_url"]`` (the sidebar only calls
``init_phoenix()`` when that key is absent).
"""

from streamlit.testing.v1 import AppTest


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


def test_single_case_results_persist_across_reruns():
    at = _boot().run()
    at = _click_button(at, "Run eval")
    assert not at.exception

    # The finished report is persisted, and the results funnel rendered.
    assert "report::single" in at.session_state
    headers = [h.value for h in at.subheader]
    assert any("Results" in h for h in headers)
    assert any("rationale" in h.lower() for h in headers)

    # A plain rerun (any widget interaction) must NOT lose the results.
    at = at.run()
    assert not at.exception
    headers = [h.value for h in at.subheader]
    assert any("Results" in h for h in headers)


def test_custom_mode_runs_user_skills_through_the_harness():
    at = _boot().run()
    at.radio[0].set_value("Custom")
    at = at.run()
    assert not at.exception

    # Free simulated components for the test; skill dirs are still written.
    at.toggle(key="custom_real_agents").set_value(False)

    at = _click_button(at, "Run custom eval")
    assert not at.exception

    stored = at.session_state["report::custom"]
    cfg = stored["report"].config
    # The user-pasted skills were materialised and wired into the RunConfig.
    assert "custom_skills" in cfg.baseline_skill_path
    assert "custom_skills" in cfg.challenger_skill_path
    assert cfg.baseline_skill_path != cfg.challenger_skill_path
