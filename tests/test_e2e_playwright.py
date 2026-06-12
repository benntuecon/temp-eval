"""Browser-level E2E: Playwright + real Chromium against the real stack
(FastAPI on :8601 + Vite dev server on :5174 proxying /api).

Verifies what no other layer can — the rendered React DOM:
the live architecture graph lighting up, the hover-thinking node panels,
the results funnel, and the History tab.

Opt-in: excluded from the default fast suite, run with ``just e2e``.
"""

import os
import socket
import subprocess
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

API_PORT = 8601
WEB_PORT = 5174
ROOT = Path(__file__).resolve().parents[1]


def _wait_port(port: int, timeout: float = 40.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("localhost", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.3)
    return False


@pytest.fixture(scope="session")
def app_server(tmp_path_factory):
    """Launch uvicorn + vite dev for the session; tear both down after."""
    env = os.environ.copy()
    env["SKILL_EVAL_RUNS_DIR"] = str(tmp_path_factory.mktemp("runs"))

    api = subprocess.Popen(
        ["uv", "run", "uvicorn", "skill_eval.api.app:app", "--port", str(API_PORT)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    web_env = os.environ.copy()
    web_env["VITE_API_TARGET"] = f"http://localhost:{API_PORT}"
    web = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", str(WEB_PORT), "--strictPort"],
        cwd=ROOT / "frontend",
        env=web_env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert _wait_port(API_PORT), "API did not come up"
        assert _wait_port(WEB_PORT), "Vite did not come up"
        yield f"http://localhost:{WEB_PORT}"
    finally:
        web.terminate()
        api.terminate()
        web.wait(timeout=10)
        api.wait(timeout=10)


def _open(page, url: str) -> None:
    page.goto(url)
    page.get_by_test_id("tab-run").wait_for(timeout=20_000)
    page.get_by_test_id("batch-query").wait_for(timeout=20_000)


def _hover_node(page, text: str) -> None:
    """Hover a React Flow node via raw mouse coords (the canvas is transformed,
    which confuses locator actionability; real pointer events work fine)."""
    node = page.locator(".react-flow__node", has_text=text).first
    node.scroll_into_view_if_needed()
    box = node.bounding_box()
    assert box, f"no bounding box for node {text!r}"
    cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    page.mouse.move(cx - 30, cy - 30)
    page.mouse.move(cx, cy, steps=4)


def test_app_loads_with_batch_form(app_server, page):
    _open(page, app_server)
    assert page.get_by_test_id("tab-history").is_visible()
    assert page.get_by_test_id("batch-query").is_visible()
    assert page.get_by_test_id("run-button").is_visible()
    # run is gated on a retrieval query
    assert page.get_by_test_id("run-button").is_disabled()


def test_simulated_run_lights_graph_and_streams_thinking(app_server, page):
    _open(page, app_server)
    # One retrieved case keeps the run fast; the board auto-opens its pipeline.
    page.get_by_test_id("batch-query").fill("payment api logging banking")
    page.get_by_test_id("batch-topk").fill("1")
    page.get_by_test_id("run-button").click()
    page.get_by_test_id("batch-board").wait_for(timeout=30_000)

    # The graph lights up live (amber pulse) and finishes with results.
    saw_running = False
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if not saw_running and page.locator(".node-running").count() > 0:
            saw_running = True
        if page.get_by_test_id("results-funnel").count() > 0:
            break
        time.sleep(0.1)
    assert saw_running, "no node ever entered the running (pulsing) state"
    assert page.get_by_test_id("results-funnel").is_visible()

    # Hover the taker -> its thinking buffer streams in the panel.
    _hover_node(page, "baseline taker")
    panel = page.get_by_test_id("node-panel")
    panel.wait_for(timeout=5_000)
    text = panel.inner_text()
    assert "taker:baseline" in text
    assert "[simulated]" in text  # the streamed ThinkingDelta content

    # Hover a judge -> score + rationale.
    _hover_node(page, "correctness")
    jtext = page.get_by_test_id("node-panel").inner_text()
    assert "/20" in jtext

    # Hover the simulator -> the Q&A buffer.
    _hover_node(page, "HITL simulator")
    stext = page.get_by_test_id("node-panel").inner_text().lower()
    assert "question" in stext or "answer" in stext

    # Results funnel carries the funnel pieces.
    body = page.get_by_test_id("results-funnel").inner_text()
    assert "Verdict:" in body
    assert "Judge scores & rationales" in body


def test_history_lists_and_renders_archived_run(app_server, page):
    _open(page, app_server)
    page.get_by_test_id("tab-history").click()
    page.get_by_test_id("history-select").wait_for(timeout=15_000)
    # The run archived by the previous test renders its full funnel.
    page.get_by_test_id("results-funnel").wait_for(timeout=15_000)
