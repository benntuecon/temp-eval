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
uv sync && cp .env.example .env   # backend deps + ANTHROPIC_API_KEY
cd frontend && npm install && cd ..
just dev                          # FastAPI :8600 + React :5173 (Phoenix auto-starts at :6006)
```

Open http://localhost:5173. Two tabs:
- **Run eval** — paste two `SKILL.md` bodies (prefilled with the flagship ship-it-fast vs
  disciplined matchup), pick a fixture, set budgets/judge model/k, and race them (real Haiku
  agents, or free simulated components). The **whole architecture renders as a live React Flow
  graph** — skills → test generator (mock) → test cases → sandbox → takers ↔ HITL simulator →
  judges → assemble → report — nodes pulse amber while running and turn green when done, and
  **hovering any node opens a panel streaming that agent's live thinking** (taker reasoning and
  tool calls as they happen, simulator Q&A, judge rationales the moment they land).
- **History** — every run is archived (`runs/<id>/report.json` + `events.jsonl`); browse past
  runs and **diff two runs** per criterion with green/red deltas.

## Architecture (service)

```
frontend/ (Vite+React+TS) ──openapi-ts client──► skill_eval/api/ (FastAPI :8600)
   React Flow live graph        SSE /api/runs/{id}/events (typed event union)
   hover-thinking panels        POST/GET /api/runs · /api/fixtures · /api/health
   react-vega results funnel              │
                                   RunManager (asyncio task per run)
                                          │
                            agent layer: orchestrator → takers ↔ simulator → judges
                                          │
                            runs/ archive + Phoenix traces (one session per run)
```

The contract is **Pydantic v2** end to end: `skill_eval/contracts.py` (report types) and
`skill_eval/events.py` (node-addressed event union) generate the OpenAPI schema, and the
TypeScript client is generated from it (`just gen-client`) — frontend and backend cannot drift.

## Measurement validity

- **temperature=0** on every judge and simulator call — graded verdicts are not sampled.
- **Judge ≠ taker model** (`judge_model` config) to avoid same-family self-preference; **k replicate judges per criterion** with median aggregation and recorded spread.
- **Criterion-blind judging** — `code_quality` and `approach` judges never see the gold solution; gold stays visible only for the criteria defined against it.
- **Real contrasting skills everywhere** — the 10 sample batch cases (CLI/`run_batch`) load the actual ship-it-fast vs disciplined skills (previously placeholders).
- Every clarifying **question is stored with the stakeholder's answer** (Q&A pairs in the report).

## Visualizations

The results funnel follows the **aggregate → matrix → drill-down** pattern of the two most
credible OSS eval UIs (promptfoo 22k★, Langfuse 28k★): delta metric cards → per-criterion
score matrix with green/red Δ and "why?" rationale drill-downs → evidence (each arm's actual
diff, the gold reference diff, clarifying Q&A) → JSON download. Charts are vega-lite via
react-vega (dumbbell gap chart, quality-vs-cost scatter) — one colour per arm everywhere,
grouped never stacked. The **live architecture graph** is the centerpiece: per-node status
lighting plus hover panels streaming each agent's thinking in real time.


**Phoenix** (`localhost:6006`) — deep per-agent traces, all grouped into **one Session** per run:
taker tool timelines + thinking trajectory + real token counts, every simulator answer as its own
LLM span, every judge prompt + rationale as structured messages, judge scores as span annotations.

## Dev

```bash
just check        # python: ruff format + lint + mypy + pytest (123 tests incl. API contract + SSE, no network)
just check-web    # frontend: tsc + vitest (event-store reducer & co.)
just e2e          # Playwright + real Chromium against the real stack: live graph, hover-thinking panels, full run
just gen-client   # regenerate the typed TS client from the OpenAPI schema
just screenshot   # full-page Playwright screenshot of the running app
just test-live    # the one real end-to-end smoke test (needs API + credits)
just phoenix      # standalone Phoenix (the API auto-starts it otherwise)
just graph        # refresh the graphify code knowledge graph
```

## Layout
- `skill_eval/` — `contracts.py` + `events.py` (the Pydantic contract), `api/` (FastAPI + RunManager), `orchestrator.py` (LangGraph), `sandbox.py`/`git_ops.py` (worktrees), `taker.py`/`simulator.py`/`judge.py` (real components), `simulated.py` (free stand-ins), `reporting.py`, `tracing.py`.
- `frontend/` — Vite + React + TS app (React Flow graph, hover-thinking panels, react-vega funnel, generated client in `src/api/schema.d.ts`).
- `flagship/skills/` — the two demo skills (`disciplined`, `ship-it-fast`). `docs/superpowers/` — specs, plans, decisions, spikes.

See `DEMO.md` for the 2-minute presentation script.
