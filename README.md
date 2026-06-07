# skill-eval

Eval/comparison harness for two Claude Code Skills (baseline vs challenger).
See docs/superpowers/specs/2026-06-06-skill-eval-system-design.md

## Setup

    uv sync                 # creates .venv, installs deps + dev tools, writes uv.lock
    cp .env.example .env     # then fill in ANTHROPIC_API_KEY

## Develop

    uv run pytest            # tests
    uv run ruff check .      # lint
    uv run ruff format .     # format
    uv run mypy              # type-check
    uv run python spikes/spike_skill_loading.py   # a spike (needs ANTHROPIC_API_KEY)
