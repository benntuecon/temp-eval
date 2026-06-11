"""Capture a full-page screenshot of the running dashboard with Playwright.

Usage:
    uv run python scripts/screenshot_dashboard.py [url] [out_path]

Defaults: http://localhost:5173 -> /tmp/skill_eval_dashboard.png.
Waits for the React app's Run tab + prefilled fixture form before shooting.
"""

import sys

from playwright.sync_api import sync_playwright


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:5173"
    out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/skill_eval_dashboard.png"

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1700, "height": 1100})
        page.goto(url)
        page.get_by_test_id("tab-run").wait_for(timeout=30_000)
        page.wait_for_function(
            "() => document.querySelector('[data-testid=fixture-select]')?.options.length >= 1",
            timeout=30_000,
        )
        page.wait_for_timeout(800)  # let the graph settle
        page.screenshot(path=out, full_page=True)
        browser.close()
    print(f"saved {out}")


if __name__ == "__main__":
    main()
