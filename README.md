# skill-eval

**An eval harness that measures how much a Claude Code *skill* improves an agent — by running two skills head-to-head on the same task and scoring the results.**

Give it a task (a repo at a `before` commit, a `after`/gold commit, and a brief) plus two skills — a **baseline** and a **challenger** — and it spins up two real Claude-Agent-SDK coding agents, lets each attempt the task under its skill, simulates a human answering their clarifying questions, then has a panel of LLM judges score both on 6 criteria (0–20 each). You get a holistic, evidence-backed comparison.

## The headline result

On a deliberately **under-specified** `prorate_refund` task (4 critical details the brief omits), a **disciplined** skill (read → ask about every ambiguity → test-first → implement) vs a **ship-it-fast** skill (don't ask, just guess and ship):

```
VERDICT: challenger (disciplined) wins by 88 — 118 vs 30 / 120

ship-it-fast   30/120   questions asked: 0   → guessed the edge cases wrong
disciplined   118/120   questions asked: 5   → asked, nailed every edge case
               (question_quality 20 vs 0)
```

The system correctly detects that the skill which makes the agent **ask the right questions** produces dramatically better work — and shows *why* in the traces.

## How it works

```
INPUT: before_hash, after_hash, task_brief, baseline_skill, challenger_skill
   │
   ▼  (LangGraph orchestration, Send fan-out, async)
 sandbox ──► 2 test-takers (concurrent)        ──► 12 judges (concurrent) ──► report
   git        Claude Agent SDK, isolated            one per (arm × criterion)
   worktrees  skill injected, ask_question →        0–20 anchored rubric
              HITL simulator (has the gold)
```

- **Test-takers** — real Claude Agent SDK agents, each loaded with one skill *in isolation* (`setting_sources=[]`, so no global skills leak in). A custom `ask_question` tool routes their clarifying questions to the simulator.
- **HITL simulator** — an LLM that answers questions using the gold tree as ground truth (reactive only — it never volunteers the solution).
- **Judges** — one LLM per criterion (`correctness`, `completeness`, `distance_to_gold`, `code_quality`, `question_quality`, `approach`), each with an anchored 0/5/10/15/20 rubric. `question_quality` is derived by comparing the under-specified brief to the gold's decisions.
- **Orchestrator** — a LangGraph graph; each taker and judge is a real node (`Send` fan-out) so they run concurrently and show up individually in traces.

Everything is **injectable**: simulated stand-ins (free, instant) for the plumbing, real Haiku agents for the truth.

## Quickstart

```bash
uv sync                       # install
cp .env.example .env          # add ANTHROPIC_API_KEY
just app                      # dashboard at localhost:8501 (auto-starts Phoenix at :6006)
```

In the dashboard pick a **Mode**:
- **Single case** — watch one eval run live (simulated = free, or toggle real Haiku).
- **Batch (10 cases)** — 10 tasks at once: win summary, per-case + per-criterion bars, score-distribution boxplots.
- **Flagship** — the disciplined-vs-ship-it-fast comparison above, with real agents.

## Visualizations
- **Live agent graph** — the eval fan-out as a Graphviz DAG, nodes lighting grey→gold→green.
- **Control room** — per-arm panels, a 12-tile judges grid, headline delta metrics.
- **Comparison dataviz** (best-practice, one colour per arm everywhere):
  - **Grouped 0–20 bars** per criterion.
  - **Dumbbell / gap chart** — connects each arm's score per criterion, sorted by the gap, so the *difference* is the primary visual (the canonical way to compare two series across many dimensions).
  - **Quality-vs-cost scatter** — total score against total tokens, answering "is the better skill worth what it costs?".
  - Batch adds per-criterion gap dumbbells and score-distribution boxplots.
- **Phoenix** (`localhost:6006`) — deep per-agent traces, all grouped into **one Session** per run:
  - **Taker** (AGENT): tool timeline (Read/Edit/Bash/ask_question), thinking trajectory, an LLM `model` child span carrying real prompt/completion/cache token counts, and metadata (skill, stop_reason, thinking budget).
  - **HITL simulator** (LLM): every stakeholder answer captured as its own span — model, tokens, and the structured system/user/assistant messages it saw.
  - **Judges** (LLM): each prompt + rationale as structured input/output messages, model name, invocation parameters, and token counts.
  - Judge scores logged as span annotations; auto-instrumentation adds raw Anthropic `messages.create` and LangGraph node spans on top.

## Dev

```bash
just check        # ruff format + lint + mypy + pytest  (92 tests, no network)
just test-live    # the one real end-to-end smoke test (needs API + credits)
just phoenix      # standalone Phoenix (just app auto-starts it otherwise)
just graph        # refresh the graphify code knowledge graph
```

## Layout
- `skill_eval/` — `contracts.py` (the typed contract), `orchestrator.py` (LangGraph), `sandbox.py`/`git_ops.py` (worktrees), `taker.py`/`simulator.py`/`judge.py` (real components), `simulated.py` (free stand-ins), `reporting.py`, `tracing.py`.
- `flagship/skills/` — the two demo skills (`disciplined`, `ship-it-fast`).
- `app.py` — the Streamlit dashboard. `docs/superpowers/` — specs, plans, decisions, spikes.

See `DEMO.md` for the 2-minute presentation script.
