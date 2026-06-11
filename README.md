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

The dashboard has two tabs:
- **Run eval** — bring your own skills: paste two `SKILL.md` bodies (prefilled with the flagship ship-it-fast vs disciplined matchup), pick a task fixture, set `max_turns`/thinking budget, judge model, and judges-per-criterion, then race them (real Haiku agents, or free simulated components to demo the flow). A live **architecture graph** shows the whole pipeline — skills → test generator (mock service) → test cases (before/after project) → sandbox → takers ↔ HITL simulator → judges → assemble → report — with nodes lighting up as stages run; **hover any node** to read what it's doing/thinking (judge tooltips include the rationale as soon as each score lands).
- **History** — every completed run is archived to `runs/` as JSON; browse past runs and **diff two runs** per criterion (did your skill edit actually help?).

Results persist across reruns (stored in session state) and every report is downloadable as JSON.

## Measurement validity

- **temperature=0** on every judge and simulator call — graded verdicts are not sampled.
- **Judge ≠ taker model** (`judge_model` config) to avoid same-family self-preference; **k replicate judges per criterion** with median aggregation and recorded spread.
- **Criterion-blind judging** — `code_quality` and `approach` judges never see the gold solution; gold stays visible only for the criteria defined against it.
- **Real contrasting skills everywhere** — the 10 sample batch cases (CLI/`run_batch`) load the actual ship-it-fast vs disciplined skills (previously placeholders).
- Every clarifying **question is stored with the stakeholder's answer** (Q&A pairs in the report).

## Visualizations

The results page follows the **aggregate → matrix → drill-down funnel** used by the two most credible OSS eval UIs (promptfoo 22k★, Langfuse 28k★):

- **Live architecture graph** — the *whole* pipeline as a left-to-right Graphviz DAG (skills → test generator → test cases → sandbox → takers ↔ simulator → judges → assemble → report), nodes lighting grey→gold→green as stages run; per-arm clusters with junction nodes so the 12-judge fan-in reads as 2 clean edges; **hover tooltips** narrate each node's thinking (incl. live judge rationales).
- **Control room** — per-arm panels (stop reason, questions, turns, wall time), a 12-tile judges grid, headline delta metrics.
- **Comparison dataviz** (best-practice, one colour per arm everywhere):
  - **Dumbbell / gap chart** — connects each arm's score per criterion, sorted by the gap, so the *difference* is the primary visual.
  - **Score matrix + judge rationales** — exact scores with green/red Δ, then an expander per criterion showing *why* each judge scored each arm (rationale as a first-class field, the promptfoo `llm-rubric` pattern).
  - **Quality-vs-cost scatter** — total score against total tokens, answering "is the better skill worth what it costs?".
  - **Evidence panels** — the actual diff each taker produced, the gold reference diff, and the clarifying Q&A, side by side.
  - **History compare** — per-criterion green/red deltas between any two archived runs.
- **Phoenix** (`localhost:6006`) — deep per-agent traces, all grouped into **one Session** per run:
  - **Taker** (AGENT): tool timeline (Read/Edit/Bash/ask_question), thinking trajectory, an LLM `model` child span carrying real prompt/completion/cache token counts, and metadata (skill, stop_reason, thinking budget).
  - **HITL simulator** (LLM): every stakeholder answer captured as its own span — model, tokens, and the structured system/user/assistant messages it saw.
  - **Judges** (LLM): each prompt + rationale as structured input/output messages, model name, invocation parameters, and token counts.
  - Judge scores logged as span annotations; auto-instrumentation adds raw Anthropic `messages.create` and LangGraph node spans on top.

## Dev

```bash
just check        # ruff format + lint + mypy + pytest  (112 tests incl. headless AppTest UI tests, no network)
just test-live    # the one real end-to-end smoke test (needs API + credits)
just phoenix      # standalone Phoenix (just app auto-starts it otherwise)
just graph        # refresh the graphify code knowledge graph
```

## Layout
- `skill_eval/` — `contracts.py` (the typed contract), `orchestrator.py` (LangGraph), `sandbox.py`/`git_ops.py` (worktrees), `taker.py`/`simulator.py`/`judge.py` (real components), `simulated.py` (free stand-ins), `reporting.py`, `tracing.py`.
- `flagship/skills/` — the two demo skills (`disciplined`, `ship-it-fast`).
- `app.py` — the Streamlit dashboard. `docs/superpowers/` — specs, plans, decisions, spikes.

See `DEMO.md` for the 2-minute presentation script.
