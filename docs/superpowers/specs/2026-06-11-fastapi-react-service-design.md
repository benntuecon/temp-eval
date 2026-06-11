# skill-eval as a Service: FastAPI + React — Design

**Date:** 2026-06-11 · **Status:** approved (big-bang migration; user delegated detail decisions)

## Goal

Separate the agent layer behind a formal, typed API. Pydantic v2 owns the contract,
FastAPI serves it, a React SPA consumes it, and Streamlit is deleted. Live run
progress — including each agent's *thinking* — streams to the UI so hovering a
graph node shows what that agent is doing right now.

## Decisions (user-confirmed)

1. **Migration:** big bang — backend + frontend in one push; Streamlit removed at the end.
2. **Contracts:** Pydantic v2 **replaces** the dataclasses in `contracts.py` (one source of truth).
3. **Live events:** **SSE** + a typed, node-addressed event union (transport-agnostic schema; WebSocket only if human-in-the-loop steering is added later).
4. **Frontend:** Vite + React 18 + TypeScript, React Flow (xyflow), Tailwind + shadcn/ui, react-vega (port the Altair specs), TanStack Query, openapi-ts generated client.
5. **Run execution:** in-process `RunManager` (asyncio task per run; events buffered in memory **and** appended to `runs/<id>/events.jsonl` so SSE can replay then tail).

## Architecture

```
frontend/ (Vite+React+TS, port 5173) ──generated client──► skill_eval/api/ (FastAPI, port 8600)
   React Flow pipeline graph                POST /api/runs                → {run_id}
   hover node → live thinking panel   SSE   GET  /api/runs/{id}/events   (replay + tail)
   results funnel (react-vega)        ◄──   GET  /api/runs               (live + archived)
   History + two-run compare                GET  /api/runs/{id}          (status/report)
                                            GET  /api/fixtures           (briefs + default skills)
                                            GET  /api/health             (incl. Phoenix url)
                                                   │
                                            RunManager ── asyncio task per run
                                                   │
                                      skill_eval agent layer (orchestrator/taker/judge/simulator)
                                                   │
                                      runs/ archive (report.json + events.jsonl) + Phoenix traces
```

## Contracts (`skill_eval/contracts.py` → Pydantic v2)

- Existing types become frozen `BaseModel`s with identical field names:
  `RunConfig, Workspace, RunMetrics, TakerResult, JudgeInput, JudgeScore, ArmReport, ComparisonReport`.
  Enums stay `StrEnum`. `report_to_json/report_from_json` become thin wrappers over
  `model_dump_json/model_validate_json` (kept for call-site compatibility).
- **Event union** (`skill_eval/events.py`), discriminated on `type`, every event carries
  `node` (graph node id) + `ts`:
  `RunStarted, StageChanged(stage,status), SandboxReady, ThinkingDelta(text), ToolCallEvent(tool,summary),
  QuestionAsked(question), QuestionAnswered(question,answer), TakerStatus(arm,status,stop_reason?,metrics?),
  JudgeStatus(arm,criterion,status,score?,rationale?), RunCompleted(verdict,report_available),
  RunFailed(error)`.
  Node ids match the graph: `test_generator, sandbox, simulator, taker:baseline, judge:baseline:correctness, assemble, report`.
- **API models** (`skill_eval/api/schemas.py`):
  `SkillInput(name, markdown)`, `CreateRunRequest(fixture, task_brief, baseline, challenger,
  max_turns, thinking_budget?, judge_model?, judges_per_criterion, real_agents)` (validators:
  non-empty brief/skills), `RunSummary(run_id, status, created_at, label, verdict?)`,
  `RunDetail(summary, report?)`, `FixtureInfo(id, label, brief, default_skills)`.

## Backend (`skill_eval/api/`)

- `app.py` — FastAPI factory; CORS for the Vite dev origin; serves `/openapi.json` (client generation source).
- `run_manager.py` — `RunManager`: `start(req) -> run_id` spawns an asyncio task that
  (1) builds the fixture + skill dirs in a temp dir (the current `build_custom_case` logic moves here),
  (2) awaits `arun_eval` with an `on_event` that timestamps, buffers, persists (events.jsonl), and fans out to SSE subscribers,
  (3) archives `report.json`, cleans temp.
  `events(run_id)` async-iterates: replay persisted/buffered events, then tail the live queue.
- **Agent-layer changes (small, surgical):**
  - `orchestrator.arun_eval(...)` — async variant (graph is already async); `run_eval` stays as the sync wrapper.
  - Taker forwards streamed Agent SDK content into `on_event`: thinking deltas, tool-call summaries, Q&A — node-tagged. (Today only Phoenix sees these.)
  - Judge emits rationale in its done event (already done).
- SSE: `text/event-stream`, one JSON event per message, 15s heartbeat comments.

## Frontend (`frontend/`)

- **Run page:** config form (fixture select, brief, two skill editors, budgets, judge model, k,
  real/simulated) → pipeline graph (React Flow custom nodes; grey/gold-pulse/green by status;
  hover/click opens a right-side panel streaming that node's event buffer — thinking, tool calls,
  Q&A, judge rationale) → results funnel: delta metric cards, dumbbell, score matrix + per-criterion
  rationales, quality-vs-cost scatter, taker diffs + gold diff, Q&A, report JSON download.
- **History page:** archived runs (from `GET /api/runs`), open one → same results funnel;
  pick two → per-criterion green/red delta table.
- State: TanStack Query for REST; an `EventStore` (per-run reducer keyed by node id) fed by
  `EventSource`; chart rows derived in TS from the typed report.
- Charts via react-vega using the existing Altair-generated vega-lite specs as the source of truth.

## Testing

- **Backend:** httpx `AsyncClient` contract tests per route; an SSE test running a simulated eval
  and asserting the typed event sequence (incl. ThinkingDelta presence in real-taker mode is
  covered by unit tests on the taker's event forwarding with a mocked SDK stream); schemathesis
  fuzz against `/openapi.json`; existing agent-layer tests unchanged.
- **Frontend:** vitest + RTL (EventStore reducer, node panel, results components with fixture
  report JSON); generated-client typecheck (`tsc`) in `just check-web`.
- **E2E (Playwright):** against `just dev` (API + Vite): page loads, simulated run lights the
  graph, hover panel shows thinking/rationale text, results funnel renders, History lists the run.
- **Drift guard:** `just gen-client` regenerates the TS client from `/openapi.json`; CI/`just check`
  fails on uncommitted diff.

## Error handling

- 404 unknown run; 422 invalid `CreateRunRequest`; run crash → `RunFailed` event + `status="failed"`;
  SSE heartbeats; graceful shutdown cancels run tasks; `runs/` writes are best-effort (never crash a run).

## Removed

`app.py` (Streamlit), `tests/test_app.py` (AppTest), `scripts/screenshot_dashboard.py` retargeted,
`streamlit` dependency. `reporting.py` shrinks to: Phoenix init, judge-evaluation logging,
save/list/load of runs (used by the API), palette + pure chart-row helpers that remain unit-tested
(the FE recomputes its own rows in TS).

## Dev workflow

`just api` (uvicorn :8600) · `just web` (vite :5173) · `just dev` (both) · `just gen-client` ·
`just check` (py fast suite) · `just check-web` (tsc + vitest) · `just e2e` (Playwright vs dev stack).
