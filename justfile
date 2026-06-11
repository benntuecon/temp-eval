default:
    @just --list

install:
    uv sync

test:
    uv run pytest

test-live:
    uv run pytest -m live --override-ini "addopts=" -s

# Browser-level E2E: Playwright + real Chromium against a live Streamlit server
e2e:
    uv run pytest -m e2e --override-ini "addopts=" -v

# Full-page screenshot of the running dashboard (Playwright)
screenshot url="http://localhost:8501" out="/tmp/skill_eval_dashboard.png":
    uv run python scripts/screenshot_dashboard.py {{url}} {{out}}

lint:
    uv run ruff check .

fmt:
    uv run ruff format .

types:
    uv run mypy

check: fmt lint types test

app:
    uv run streamlit run app.py

phoenix:
    uv run phoenix serve

graph:
    graphify update .

clean-worktrees:
    -git worktree prune
