# FastAPI + React Service Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Streamlit dashboard with a Pydantic-contract FastAPI backend + React (Vite/TS) frontend per `docs/superpowers/specs/2026-06-11-fastapi-react-service-design.md`.

**Architecture:** agent layer untouched in behavior; contracts promoted to Pydantic v2; in-process RunManager streams node-addressed events over SSE; React Flow graph with hover-live-thinking panels; react-vega results funnel; openapi-ts generated client.

**Tech stack:** FastAPI, uvicorn, sse-starlette (or hand-rolled StreamingResponse), httpx (tests), schemathesis; Vite, React 18, TS, @xyflow/react, Tailwind, react-vega, @tanstack/react-query, openapi-typescript(+fetch wrapper), vitest, Playwright.

**Verification gate per task:** `just check` stays green; new tests added with each task.

---

### Task 1: contracts.py → Pydantic v2
- [ ] Convert all dataclasses to frozen `BaseModel` (same fields/names/defaults); keep StrEnums.
- [ ] `reporting.report_to_json/from_json` → `model_dump_json` / `model_validate_json` wrappers.
- [ ] Fix call sites (`dataclasses.replace` → `model_copy(update=...)`, `asdict` → `model_dump`).
- [ ] Full suite green.

### Task 2: event union + API schemas
- [ ] `skill_eval/events.py`: discriminated union per spec (`type` literal discriminator, `node`, `ts` float epoch set by emitter).
- [ ] `skill_eval/api/schemas.py`: `SkillInput, CreateRunRequest (validators), RunSummary, RunDetail, FixtureInfo`.
- [ ] Unit tests: serialization round-trip, discriminator parsing, request validation errors.

### Task 3: arun_eval + taker thinking/tool/Q&A event forwarding
- [ ] `orchestrator.arun_eval(...)` async (extract body of `run_eval`; sync wrapper calls `asyncio.run`).
- [ ] Taker: in the SDK message loop, forward `ThinkingDelta`, `ToolCallEvent`, Q&A events via `on_event` (plumb `on_event` into `run_taker`'s closure via cfg? No — extend TakerFn signature is invasive; instead pass an optional `event_sink` attribute on `ask_fn`? Decision: extend `run_taker` with optional kwarg `on_event=None`, orchestrator passes a node-tagging adapter; simulated taker emits a couple of synthetic ThinkingDeltas so the free path demos the panel).
- [ ] Unit tests with mocked SDK stream asserting forwarded events.

### Task 4: FastAPI app + RunManager + SSE + tests
- [ ] `skill_eval/api/run_manager.py`: RunState(status, events list, asyncio.Queue subscribers, report), `start()`, `events()` async generator (replay + tail), persistence to `runs/<id>/` (`events.jsonl`, `report.json`), fixture+skills materialisation (port `build_custom_case`).
- [ ] `skill_eval/api/app.py`: routes per spec; CORS for :5173; SSE via StreamingResponse; `create_app()` factory.
- [ ] httpx tests: health, fixtures, create+detail+list, 404, 422, full simulated run via SSE asserting typed sequence ends with RunCompleted; schemathesis smoke.
- [ ] `just api` recipe.

### Task 5: frontend scaffold + generated client
- [ ] `npm create vite@latest frontend -- --template react-ts`; deps: @xyflow/react, @tanstack/react-query, react-vega vega vega-lite, tailwind, shadcn-style primitives (hand-rolled minimal: button/card/badge/tabs), openapi-typescript dev-dep.
- [ ] `just gen-client` → `frontend/src/api/schema.d.ts` + thin typed fetch/SSE helpers.
- [ ] `just web`, `just dev`, `just check-web` (tsc + vitest) recipes.

### Task 6: Run page — form + live graph + thinking panel
- [ ] `EventStore` reducer: events → {pipeline statuses, per-node buffers, judge scores}; vitest coverage.
- [ ] React Flow graph mirroring the architecture DAG (fixed layout, status colors, pulse on running).
- [ ] Node hover/click → side panel rendering the node buffer live (thinking deltas append as they stream).
- [ ] Config form (fixture select prefilled from /api/fixtures, skill editors, budgets, toggles) → POST /runs → subscribe SSE.

### Task 7: results funnel + History
- [ ] Results: metric delta cards, dumbbell + scatter + matrix (react-vega specs ported from reporting helpers), rationale accordions, diff viewers, Q&A, JSON download.
- [ ] History page: list runs, open → funnel; select two → delta table.

### Task 8: retire Streamlit, retarget E2E, docs
- [ ] Delete `app.py`, `tests/test_app.py`; drop streamlit dep; `scripts/screenshot_dashboard.py` → React app.
- [ ] Playwright E2E: dev-stack fixture (uvicorn + vite preview), 3 scenarios (load, simulated run lights graph + panel shows thinking, history lists run).
- [ ] README + justfile rewrite; graphify update.

### Task 9: full verification + commit
- [ ] `just check` (py), `just check-web`, `just e2e` all green; screenshot the React app; commit(s) on `experiments`.
