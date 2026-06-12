# SkillForge Frontend-Backend Contract

This document records what the current SkillForge frontend assumes from the backend, and how that compares with Ben's original `experiments` branch contract.

## Executive Summary

The current `Luciana-frontend` branch does **not** change the real frontend-backend API contract from Ben's `experiments` branch.

The contract-critical files are unchanged from `origin/experiments`:

- `frontend/src/api/client.ts`
- `frontend/src/api/schema.d.ts`
- `skill_eval/api/schemas.py`
- `skill_eval/events.py`
- `skill_eval/contracts.py`

What changed is the demo/frontend layer:

- Hand-drawn SkillForge UI and screen sequence.
- Mock fallback run stream in `frontend/src/mockRun.ts`.
- Frontend defaults and display choices, such as `max_turns = 5`, OpenAI model labels, and a mock cost estimate.
- Mock-only milestone/hidden-requirement cards and decision-report enrichments.

Backend owners should treat the OpenAPI schema and SSE event union as still authoritative.

## Runtime Topology

The frontend is a Vite/React app.

During local development:

- Frontend runs on `http://127.0.0.1:5173`.
- Backend runs on `http://127.0.0.1:8600`.
- Vite proxies same-origin `/api/*` calls to the backend.

The frontend API wrapper intentionally uses:

```ts
const BASE = "";
```

That means the frontend expects backend routes to be available on the same origin in production, or proxied during development.

## HTTP Endpoints Assumed by the Frontend

### `GET /api/health`

Used by the typed client but not central to the demo screens.

Expected response:

```ts
{
  status: string;
  phoenix_url?: string | null;
}
```

### `GET /api/fixtures`

Used to populate the task fixture dropdown and prefill skill cards.

Expected response:

```ts
FixtureInfo[] = Array<{
  id: string;
  label: string;
  brief: string;
  default_baseline: SkillInput;
  default_challenger: SkillInput;
}>
```

Where:

```ts
SkillInput = {
  name: string;
  markdown: string;
}
```

Frontend fallback:

If this endpoint is unavailable or empty, the frontend uses `DEMO_FIXTURES` from `frontend/src/mockRun.ts`.

### `POST /api/runs`

Used when the user clicks `Run eval`.

Expected request:

```ts
CreateRunRequest = {
  fixture: string;
  task_brief: string;
  baseline: SkillInput;
  challenger: SkillInput;
  max_turns: number;
  thinking_budget: number | null;
  judge_model?: string | null;
  judges_per_criterion: number;
  real_agents: boolean;
}
```

Current frontend submission behavior:

```ts
{
  fixture,
  task_brief,
  baseline,
  challenger,
  max_turns,
  thinking_budget,
  judge_model,
  judges_per_criterion: 1,
  real_agents: false
}
```

Important UI choices:

- `max_turns` defaults to `5` in the frontend UI, even though the backend schema default is still `30`.
- `thinking_budget` defaults to `2048`.
- `judge_model` options displayed in the UI are OpenAI model labels:
  - `gpt-4.1-mini`
  - `gpt-4.1`
  - `gpt-4.1-nano`
  - `gpt-4o-mini`
- `real_agents` is no longer shown in the UI and is always sent as `false`.
- Extra skill cards can be added visually, but the real backend contract is still pairwise: only `baseline` and `challenger` are submitted.

Expected response:

```ts
RunSummary = {
  run_id: string;
  status: string;      // running | completed | failed
  created_at: number;  // epoch seconds
  label: string;
  verdict?: string | null;
}
```

Frontend fallback:

If `POST /api/runs` fails, the frontend enters demo mode and plays `subscribeMockRun()` from `frontend/src/mockRun.ts`.

### `GET /api/runs`

Used by the Run History screen.

Expected response:

```ts
RunSummary[]
```

The history page filters completed runs and fetches details when a run is selected.

### `GET /api/runs/{run_id}`

Used after a run completes and by Run History.

Expected response:

```ts
RunDetail = {
  summary: RunSummary;
  report?: ComparisonReport | null;
}
```

The frontend renders the decision report only when `report` is present.

### `GET /api/runs/{run_id}/events`

Used for live evaluation progress.

Transport:

- Server-Sent Events.
- Each `message` frame contains one JSON-serialized `RunEvent`.
- The stream is finite. The frontend closes it when it receives `run_completed` or `run_failed`.

## SSE Event Contract

Every event should include:

```ts
{
  type: string;
  node?: string;
  ts?: number;
}
```

The frontend relies on `type` as the discriminant and uses `node` to attach live evidence to graph nodes.

Current event union:

```ts
RunStarted = {
  type: "run_started";
  run_id: string;
  label: string;
  node?: string;
  ts?: number;
}

StageChanged = {
  type: "stage_changed";
  stage: string;   // generator | sandbox | takers | judges | report
  status: string;  // pending | running | done
  node?: string;
  ts?: number;
}

ThinkingDelta = {
  type: "thinking_delta";
  text: string;
  node: string;
  ts?: number;
}

ToolCallEvent = {
  type: "tool_call";
  tool: string;
  summary: string;
  node: string;
  ts?: number;
}

QuestionAsked = {
  type: "question_asked";
  question: string;
  node?: string;
  ts?: number;
}

QuestionAnswered = {
  type: "question_answered";
  question: string;
  answer: string;
  node?: string;
  ts?: number;
}

TakerStatus = {
  type: "taker_status";
  arm: string;       // baseline | challenger
  status: string;    // running | done
  stop_reason?: string | null;
  metrics?: RunMetrics | null;
  node?: string;
  ts?: number;
}

JudgeStatus = {
  type: "judge_status";
  arm: string;       // baseline | challenger
  criterion: string;
  status: string;    // running | done
  score?: number | null;
  rationale?: string | null;
  node?: string;
  ts?: number;
}

RunCompleted = {
  type: "run_completed";
  run_id: string;
  verdict: string;
  node?: string;
  ts?: number;
}

RunFailed = {
  type: "run_failed";
  run_id: string;
  error: string;
  node?: string;
  ts?: number;
}
```

## Node IDs Assumed by the Frontend

The live graph and behavior replay expect these node IDs:

```txt
skill:baseline
skill:challenger
test_generator
test_cases
sandbox
simulator
taker:baseline
taker:challenger
judge:baseline:correctness
judge:baseline:completeness
judge:baseline:distance_to_gold
judge:baseline:code_quality
judge:baseline:question_quality
judge:baseline:approach
judge:challenger:correctness
judge:challenger:completeness
judge:challenger:distance_to_gold
judge:challenger:code_quality
judge:challenger:question_quality
judge:challenger:approach
assemble
report
```

If the backend emits a known event type with an unknown `node`, the event can still be processed, but graph highlighting and node-level thinking display may not line up with the intended UI node.

## Criteria Assumed by the Frontend

The frontend graph and score tables expect these six criteria:

```txt
correctness
completeness
distance_to_gold
code_quality
question_quality
approach
```

These match the current backend `Criterion` enum.

## Report Contract Assumed by the Frontend

The decision report renders from:

```ts
ComparisonReport = {
  config: RunConfig;
  arms: ArmReport[];
  pairwise_verdict: string;
  gold_diff: string;
  session_id: string;
}
```

Each arm should include:

```ts
ArmReport = {
  arm: "baseline" | "challenger" | string;
  model: string;
  metrics: RunMetrics;
  scores: JudgeScore[];
  total_score: number;
  questions: string[];
  diff: string;
  stop_reason: string;
  qa: Array<[string, string]>;
}
```

Each score should include:

```ts
JudgeScore = {
  criterion: string;
  score: number;
  rationale: string;
}
```

`RunMetrics` is used for token, latency, turn, and question display:

```ts
RunMetrics = {
  total_tokens: number;
  input_tokens: number;
  output_tokens: number;
  wall_seconds: number;
  num_turns: number;
  num_questions: number;
}
```

## Mock/Demo-Only Frontend Assumptions

These items are currently frontend-only and should not be mistaken for backend requirements:

### Mock fixtures

`frontend/src/mockRun.ts` defines fallback fixtures for:

- `flagship`
- `calculator`

These are used only when the backend fixtures are unavailable.

### Mock live run

If `POST /api/runs` fails, `subscribeMockRun()` emits a 20-ish second synthetic event stream and creates a synthetic `ComparisonReport`.

This lets the demo continue without a live backend.

### Milestones Reached cards

The `Milestones Reached` cards are computed in the frontend from the selected fixture/task brief and live progress.

They are not currently backend fields.

Current mocked milestone titles include:

- Public contract
- Acceptance behavior
- Boundaries
- Change scope

For the refund fixture, the cards use:

- Month length
- Same-day cancel
- Rounding rule
- Clamp behavior

### Decision-report enrichments

`ResultsFunnel.tsx` includes mocked/derived sections such as:

- hidden requirement unlocks
- assumptions
- missed critical ambiguities
- keep/restrict/retest/prune interpretation

These are currently presentation-layer inferences from the `ComparisonReport`, not backend-provided fields.

## Comparison With Ben's Original `experiments` Branch

### Unchanged from Ben's contract

The following are unchanged:

- HTTP endpoints:
  - `GET /api/health`
  - `GET /api/fixtures`
  - `POST /api/runs`
  - `GET /api/runs`
  - `GET /api/runs/{run_id}`
  - `GET /api/runs/{run_id}/events`
  - `GET /api/schema/event-types`
- `CreateRunRequest` shape.
- `SkillInput` shape.
- `RunSummary` and `RunDetail` shape.
- `FixtureInfo` shape.
- `ComparisonReport`, `ArmReport`, `JudgeScore`, and `RunMetrics` shape.
- SSE `RunEvent` union.
- Node ID convention.
- Six-criterion judge model.

### Changed in the frontend only

Compared with Ben's `experiments` branch, `Luciana-frontend` changes:

- Visual design and screen flow.
- Default visible `max_turns` from backend default `30` to frontend UI default `5`.
- Judge model dropdown labels from earlier Claude-oriented/demo labels to OpenAI model labels.
- Replaces visible `judges_per_criterion` control with a dynamic mock cost estimate.
- Removes the visible `Run real agents` checkbox and sends `real_agents: false`.
- Adds extra skill cards in the UI for demo exploration, but does not submit them to the backend.
- Adds frontend mock data and mock SSE fallback.
- Adds product narrative screens:
  - Problem
  - Team
  - Product animation
  - Eval Lab
  - Milestones + Behavior Replay
  - Decision Report
  - Onboarding
  - Future Roadmaps + Q&A

### Backend attention points

Backend does not need to change for the current frontend to run.

If the backend wants to make the demo-only parts real later, likely future contract additions would be:

- A backend-provided `milestones` or `hidden_requirements` array.
- Backend-provided per-skill milestone verdicts.
- A first-class `cost_estimate` endpoint or field.
- True multi-skill comparison support beyond pairwise baseline/challenger.
- Structured decision recommendation: `keep | restrict | retest | prune`.

Until those are added, the frontend treats those sections as mock or derived presentation data.

## Safe Editing Notes

When changing backend behavior, keep these stable unless coordinating a frontend update:

- Do not rename event `type` values.
- Do not rename `baseline` or `challenger` arm identifiers.
- Do not remove `node` from live events that should appear in the graph.
- Do not remove any of the six judge criteria without updating `CRITERIA` in `frontend/src/state/eventStore.ts`.
- Do not change the `ComparisonReport.arms[].scores[]` structure without updating `ResultsFunnel.tsx` and `charts.ts`.

When changing frontend behavior:

- Treat `frontend/src/api/schema.d.ts` as generated from backend OpenAPI.
- Regenerate the client types instead of hand-editing schema definitions.
- Keep mock/demo data clearly isolated in `frontend/src/mockRun.ts`.
