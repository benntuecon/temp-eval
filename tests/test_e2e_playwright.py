"""Browser-level E2E tests: Playwright drives real Chromium against a real
Streamlit server.

These verify what AppTest structurally cannot — the rendered DOM: the
architecture graph's SVG, its hover "thinking" tooltips, and a full
simulated run clicked through an actual browser (auto-waiting included).

Opt-in: excluded from the default fast suite, run with ``just e2e``.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

PORT = 8597


@pytest.fixture(scope="session")
def app_server(tmp_path_factory):
    """Launch a real Streamlit server for the session; tear it down after."""
    env = os.environ.copy()
    env["SKILL_EVAL_RUNS_DIR"] = str(tmp_path_factory.mktemp("runs"))
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "app.py",
            "--server.headless",
            "true",
            "--server.port",
            str(PORT),
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("localhost", PORT), timeout=0.5):
                break
        except OSError:
            time.sleep(0.3)
    else:
        proc.terminate()
        pytest.fail(f"Streamlit server did not come up on :{PORT}")
    yield f"http://localhost:{PORT}"
    proc.terminate()
    proc.wait(timeout=10)


def _open(page, url: str) -> None:
    page.goto(url)
    # The architecture graph is the last heavy element on the Run tab — once
    # ITS svg exists the page is fully rendered. (A bare "svg" selector would
    # match Streamlit's menu icons long before the app finishes rendering.)
    page.wait_for_selector('[data-testid="stGraphVizChart"] svg', timeout=60_000)


def test_dashboard_loads_with_two_tabs(app_server, page):
    _open(page, app_server)
    assert page.get_by_role("tab", name="Run eval").is_visible()
    assert page.get_by_role("tab", name="History").is_visible()
    # No sidebar: Phoenix lives in the header caption, not a sidebar widget.
    assert page.locator('[data-testid="stSidebar"]').count() == 0


def test_architecture_graph_renders_with_thinking_tooltips(app_server, page):
    _open(page, app_server)
    content = page.content()
    # Architecture nodes are present in the rendered SVG…
    for label in ("test generator", "test cases", "sandbox", "HITL simulator", "report"):
        assert label in content, f"graph node {label!r} missing from rendered page"
    # …and hover tooltips made it into the live DOM as SVG link titles:
    # the mock test-generator narration and the judge criterion blurbs.
    assert "MOCK service call" in content
    assert "judged BLIND" in content


def test_simulated_run_end_to_end_in_browser(app_server, page):
    _open(page, app_server)
    # Free simulated components: flip the "Real Haiku agents" toggle off.
    page.get_by_text("Real Haiku agents (~$0.40)").click()
    page.get_by_role("button", name="Run custom eval").click()

    # The simulated eval takes a few seconds; Playwright auto-waits. Scope to
    # the Run tab's panel — the History tab renders the archived run's
    # results too, so unscoped text lookups hit both panels.
    run_panel = page.get_by_label("▶ Run eval")
    run_panel.get_by_text("Results: Baseline vs Challenger").wait_for(timeout=90_000)
    assert run_panel.get_by_text("Judge scores & rationales").is_visible()
    assert "Verdict:" in page.content()

    # The final architecture graph carries judge rationales in its tooltips.
    assert "Rationale:" in page.content()
