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
screenshot url="http://localhost:5173" out="/tmp/skill_eval_dashboard.png":
    uv run python scripts/screenshot_dashboard.py {{url}} {{out}}

lint:
    uv run ruff check .

fmt:
    uv run ruff format .

types:
    uv run mypy

check: fmt lint types test

# FastAPI backend on :8600 (OpenAPI at /openapi.json)
api:
    uv run uvicorn skill_eval.api.app:app --port 8600 --reload

# React frontend dev server on :5173 (proxies /api -> :8600)
web:
    cd frontend && npm run dev

# Both servers together (Ctrl-C stops both)
dev:
    #!/usr/bin/env bash
    trap 'kill 0' EXIT
    uv run uvicorn skill_eval.api.app:app --port 8600 &
    cd frontend && npm run dev

# Regenerate the typed TS client from the backend's OpenAPI schema
gen-client:
    uv run python -c "import json; from skill_eval.api.app import create_app; print(json.dumps(create_app(init_tracing=False).openapi()))" > /tmp/skill_eval_openapi.json
    cd frontend && npx openapi-typescript /tmp/skill_eval_openapi.json -o src/api/schema.d.ts

# Frontend typecheck + unit tests
check-web:
    cd frontend && npm run typecheck && npm run test -- --run

phoenix:
    uv run phoenix serve

graph:
    graphify update .

clean-worktrees:
    -git worktree prune
