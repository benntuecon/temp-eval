"""Capture a full-page screenshot of the running dashboard with Playwright.

Usage:
    uv run python scripts/screenshot_dashboard.py [url] [out_path]

Defaults: http://localhost:8501 -> /tmp/skill_eval_dashboard.png.
Playwright auto-waits for the page; we additionally wait for the
architecture graph's SVG so the websocket-rendered content is in frame.
"""

import sys

from playwright.sync_api import sync_playwright


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8501"
    out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/skill_eval_dashboard.png"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 1200})
        page.goto(url)
        page.wait_for_selector("svg", timeout=45_000)
        page.wait_for_timeout(1_000)  # let the last Altair/graph paint settle
        page.screenshot(path=out, full_page=True)
        browser.close()
    print(f"saved {out}")


if __name__ == "__main__":
    main()
