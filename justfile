default:
    @just --list

install:
    uv sync

test:
    uv run pytest

test-live:
    uv run pytest -m live --override-ini "addopts=" -s

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
