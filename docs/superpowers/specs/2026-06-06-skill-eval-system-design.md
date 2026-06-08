# Skill Eval System — Design Spec

- **Date:** 2026-06-06
- **Status:** Draft for review
- **Author:** Ben Chen (with Claude)
- **Context:** Hackathon project

## 1. Goal

Given a software-engineering task and **two Claude Code Skills** (a *baseline* and a
*challenger*), produce a **holistic, quantitative + qualitative comparison** of how well
each skill helps an agent accomplish the task — even when the agent doesn't finish.

The system is an **eval/comparison harness**, not a collaborating "crew" of agents.

## 2. Inputs & Outputs

### Inputs
- `before_hash` — git commit representing the repo state *before* the task is done.
- `after_hash` — git commit representing the *completed* task (the ground truth / "gold").
- `baseline_skill` — path to a Claude Code Skill directory.
- `challenger_skill` — path to a Claude Code Skill directory.
- `task_brief` — the engineering requirement (Jira story / PRD / free text) describing what
  `after_hash` resolves.
- `RunConfig` — the test budget/config (models, max turns, max tokens, wall-clock cap).

### Output
- A `ComparisonReport`: per-arm objective metrics + per-criterion 0–20 judge scores +
  rationales + a final pairwise verdict ("challenger vs. baseline — which is better and why").
- Live + post-run **visualization** (Streamlit) and per-call **trace drill-down** (Phoenix).

## 3. Architecture — two layers

```
                          OUTER LAYER  (LangGraph orchestration + Phoenix + Streamlit)
  ┌──────────────────────────────────────────────────────────────────────────────┐
  │                                                                                │
  │  1. Sandbox/Repo Manager                                                       │
  │        └─ git worktree @before per arm, worktree @after (RO), gold diff        │
  │                                                                                │
  │  2A. Test-taker (BASELINE)        2B. Test-taker (CHALLENGER)   [concurrent]   │
  │        └─ Claude Agent SDK            └─ Claude Agent SDK                       │
  │           + skill loaded                 + skill loaded                         │
  │           + common tools                 + common tools                        │
  │           + custom ask_question ────┐                                          │
  │                                     ▼                                          │
  │  3. HITL Simulator (LLM, has @after) ── answers clarifying questions           │
  │                                                                                │
  │  4. Metrics Collector (no LLM): tokens · time · turns · #questions             │
  │                                                                                │
  │  5. Judge Panel (LLM, has @after + gold diff)  [all concurrent]                │
  │        └─ one judge per criterion, score 0–20                                  │
  │                                                                                │
  │  6. Orchestrator (this whole graph)                                            │
  │  7. Reporting: ComparisonReport → Streamlit dashboard + Phoenix traces         │
  └──────────────────────────────────────────────────────────────────────────────┘
```

**Key layering rule:** the test-takers are **Claude Agent SDK** instances (the only thing
that natively loads a Claude Code Skill + ships the common tools). A LangGraph "test-taker
node" is just a Python function that *calls out to* a Claude Agent SDK session — we do **not**
rebuild the coding agent inside the framework.

## 4. Tech stack & rationale

| Layer | Choice | Why |
|---|---|---|
| Test-takers (inner) | **Claude Agent SDK (Python)** | Only runtime that loads Claude Code Skills + common tools |
| Orchestration | **LangGraph** | Flow is a deterministic DAG; nodes are plain Python; MIT; runs fully offline |
| Trace drill-down | **Phoenix** (`arize-phoenix`) | Single pip install, local server, no Docker; OTel/OpenInference auto-tracing |
| Live race view + final comparison charts | **Streamlit** | Fully offline; custom side-by-side + 0–20 distribution charts |
| LLM provider | **Anthropic Claude** | Test-takers, simulator, judges |

**Sandbox constraint:** the hackathon runs in a sandbox. Everything above runs **offline /
local** (Docker available but not required by this stack — Phoenix was chosen over Langfuse
specifically to avoid the Postgres/ClickHouse/Redis footprint).

## 5. Components

Each component is an **independently buildable unit** with a contract (see §6). This is the
seam map for parallelizing build work across multiple Claude Code sessions.

| # | Component | LLM? | Responsibility |
|---|---|---|---|
| 1 | **Sandbox/Repo Manager** | No | Create a `git worktree` @`before_hash` per arm; a read-only worktree @`after_hash`; compute the gold diff (`git diff before..after`). |
| 2 | **Test-taker Runner** | Yes (Claude SDK) | Run a Claude Agent SDK session in the arm's worktree with the skill loaded + common tools; wire `ask_question` to the simulator; enforce budget; return diff + transcript + metrics. |
| 3 | **HITL Simulator** | Yes | Answer a clarifying question using `@after` tree + `task_brief` as ground truth. Exposed as an `AskFn`. |
| 4 | **Metrics Collector** | No | Objective only: tokens, wall-time, turns, #questions. Captured during the taker run. |
| 5 | **Judge** | Yes | One judge per criterion; score 0–20 with anchored few-shot rubric + rationale. All judges concurrent. |
| 6 | **Orchestrator** | No | The LangGraph graph wiring 1 → (2A‖2B) → 4 → 5 → compare; the shared state schema. |
| 7 | **Reporting/Dashboards** | No | Assemble `ComparisonReport`; feed Streamlit (live + comparison) and Phoenix (traces). |

**Customization lives almost entirely in 1–5.** LangGraph provides 6's runtime; Phoenix +
Streamlit provide 7's UI.

## 6. Data contracts (`contracts.py`)

The single source of truth shared by all parallel build sessions. Write this **first, alone**;
then each session builds one component against it using mocks.

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


# ---------- Enums ----------

class Arm(str, Enum):
    BASELINE = "baseline"
    CHALLENGER = "challenger"


class StopReason(str, Enum):
    COMPLETED = "completed"
    MAX_TURNS = "max_turns"
    MAX_TOKENS = "max_tokens"
    WALL_CLOCK = "wall_clock"
    ERROR = "error"


class Criterion(str, Enum):
    CORRECTNESS = "correctness"            # satisfies the requirement (vs gold)
    COMPLETENESS = "completeness"          # how much of the task got done
    DISTANCE_TO_GOLD = "distance_to_gold"  # semantic closeness of diff to gold diff
    CODE_QUALITY = "code_quality"          # maintainability / idiomaticity
    QUESTION_QUALITY = "question_quality"  # quality of clarifying questions asked
    APPROACH = "approach"                  # strategy / efficiency / lack of thrashing


# ---------- Inputs ----------

@dataclass(frozen=True)
class RunConfig:
    before_hash: str
    after_hash: str
    repo_path: str
    task_brief: str                      # PRD / Jira story / requirement text
    baseline_skill_path: str             # path to baseline skill dir
    challenger_skill_path: str           # path to challenger skill dir
    models: list[str]                    # one full eval per model
    max_turns: int = 30
    max_tokens: Optional[int] = None     # optional hard cap
    wall_clock_seconds: Optional[int] = None  # real elapsed-time cap


# ---------- Sandbox (Component 1) ----------

@dataclass(frozen=True)
class Workspace:
    arm: Arm
    taker_dir: str        # worktree @before_hash the taker edits
    after_dir: str        # read-only worktree @after_hash (gold tree)
    gold_diff: str        # `git diff before..after`


# ---------- Metrics (Component 4) ----------

@dataclass
class RunMetrics:
    total_tokens: int
    input_tokens: int
    output_tokens: int
    wall_seconds: float
    num_turns: int
    num_questions: int


# ---------- Test-taker (Component 2) ----------

# Handler injected into the taker for the custom ask_question tool.
# question -> answer text.
AskFn = Callable[[str], str]

@dataclass
class TakerResult:
    arm: Arm
    model: str
    diff: str                 # patch: before_hash -> taker end state
    transcript: list[dict]    # full message log (role/content/tool calls)
    questions: list[str]      # clarifying questions the taker asked
    stop_reason: StopReason
    metrics: RunMetrics


# ---------- HITL Simulator (Component 3) ----------

# Factory binds ground-truth context, returns the AskFn handed to a taker.
MakeSimulator = Callable[[str, str, str], AskFn]   # (after_dir, task_brief, model) -> AskFn


# ---------- Judges (Component 5) ----------

@dataclass(frozen=True)
class JudgeInput:
    criterion: Criterion
    task_brief: str
    gold_diff: str
    after_dir: str
    taker: TakerResult

@dataclass
class JudgeScore:
    criterion: Criterion
    score: int                # 0-20, anchored
    rationale: str


# ---------- Final report (Component 7) ----------

@dataclass
class ArmReport:
    arm: Arm
    model: str
    metrics: RunMetrics
    scores: list[JudgeScore]
    total_score: int          # sum of criterion scores (or weighted)

@dataclass
class ComparisonReport:
    config: RunConfig
    arms: list[ArmReport]     # baseline + challenger, per model
    pairwise_verdict: str     # which is better and why


# ---------- Component function signatures ----------

# Component 1
def prepare_workspaces(cfg: RunConfig) -> dict[Arm, Workspace]: ...

# Component 2
def run_taker(ws: Workspace, model: str, skill_path: str,
              cfg: RunConfig, ask_fn: AskFn) -> TakerResult: ...

# Component 3
def make_simulator(after_dir: str, task_brief: str, model: str) -> AskFn: ...

# Component 5 (one call per (arm, criterion); all run concurrently)
def run_judge(ji: JudgeInput, model: str) -> JudgeScore: ...

# Component 6 (entrypoint)
def run_eval(cfg: RunConfig) -> ComparisonReport: ...
```

## 7. Control flow (LangGraph)

```
START
  → prepare_workspaces           (Component 1)
  → fan-out per model in cfg.models:
       fan-out per arm {baseline, challenger}   [concurrent]:
            run_taker (with ask_fn = make_simulator(...))   (2 + 3 + 4)
       → fan-out per (arm × criterion)          [all concurrent]:
            run_judge                           (Component 5)
  → assemble ComparisonReport + pairwise_verdict (Component 7)
END
```

- **Concurrency:** both takers run concurrently; all judges run concurrently.
- **Budget enforcement:** a taker run ends when **any** of `max_turns`, `max_tokens`, or
  `wall_clock_seconds` trips first. Partial work is still judged.
- **State:** LangGraph state holds `workspaces`, `taker_results`, `judge_scores`, accumulating
  toward `ComparisonReport`.

## 8. Component details

### 8.1 Sandbox/Repo Manager (1)
- `git worktree add <tmp> <before_hash>` once per arm (fast; no full clone).
- `git worktree add <tmp_after> <after_hash>` once, treated read-only, shared by simulator + judges.
- `gold_diff = git diff <before_hash>..<after_hash>`.
- Cleanup: `git worktree remove` on teardown.
- No Docker required for the hackathon; takers run `bash` directly in their worktree.
  *(Risk noted in §12.)*

### 8.2 Test-taker Runner (2)
- Uses the **Claude Agent SDK (Python)**.
- **Skill loading:** point the SDK at a skills directory containing only this arm's skill so it
  triggers naturally; fallback = inject skill content into the system prompt. *(Confirm exact
  mechanism at build time — §12.)*
- **Tools:** the SDK's built-in common tools (read/write/edit file, bash, grep/glob) **plus** a
  **custom `ask_question` tool** whose handler is the injected `ask_fn` (→ the simulator). The
  exact tool name doesn't matter (Copilot uses `vscode_askQuestion`); only the behavior does.
- **Budget watchdog:** count turns; track cumulative tokens; a wall-clock timer aborts the
  session. Record which budget tripped as `StopReason`.
- **Output:** `git diff` of the worktree (before → end) = `TakerResult.diff`; full transcript;
  list of questions asked; `RunMetrics`.

### 8.3 HITL Simulator (3)
- A single Claude call (per question) with system context = `task_brief` + ability to read the
  `@after` tree (gold). Prompted to answer **as a knowledgeable human stakeholder would** —
  helpful but not spoon-feeding the implementation.
- `make_simulator(after_dir, task_brief, model)` returns an `AskFn` closure bound to that context.
- **Design decision (2026-06-08): reactive-only.** The simulator is a pure oracle — it answers
  when the taker calls `ask_question`, and never proactively interjects, reviews plans, or
  course-corrects. Rationale: the simulator holds the gold (`@after`), so proactive intervention
  would leak the solution and confound the skill measurement (we'd be scoring "skill + how hard
  the human rescued it"). Keeping it reactive puts the full burden of "ask the right thing at the
  right time" on the skill, which is exactly what the `question_quality` and `approach` judges
  measure. Proactive / plan-review modes were considered and deliberately deferred (could return
  later as a config-gated `hitl_mode` knob with a requirement-level-only guardrail).

### 8.4 Metrics Collector (4)
- **Purely objective, no LLM:** `total/input/output tokens`, `wall_seconds`, `num_turns`,
  `num_questions`. Captured inside `run_taker`.
- Subjective measures (question quality, completion) are **judges**, not metrics.

### 8.5 Judge Panel (5)
- **One judge per criterion** (6 criteria in `Criterion`), all concurrent, per arm.
- **Score scale: 0–20**, with **anchored few-shot examples** in every judge prompt so the
  distribution is sensible:
  - **0** = no / zero implementation (or completely wrong)
  - ~5 = minimal
  - ~10 = partial
  - ~15 = mostly there
  - **20** = matches gold / excellent
- Each judge has `@after` tree + `gold_diff` as ground truth and returns `score` + `rationale`.
- Judge scores are also pushed to **Phoenix** as evaluations attached to the run's traces.

### 8.6 Reporting / Dashboards (7)
- **Streamlit** — two views:
  1. **Live race:** baseline vs. challenger side-by-side as they run (current turn, latest
     action, questions asked, tokens/time ticking).
  2. **Final comparison:** 0–20 score bars per criterion (baseline vs. challenger),
     score-distribution charts, objective-metric table, and the pairwise verdict.
- **Phoenix** — per-call **trace drill-down**: exactly what each taker/simulator/judge LLM call
  sent and received (OTel/OpenInference auto-instrumentation of LangGraph + Anthropic).

## 9. Visualization summary (covers "both equally")
- **During a run (live):** Streamlit race view (+ Phoenix live traces).
- **After a run (post-hoc):** Streamlit comparison dashboard (scores/metrics/verdict) +
  Phoenix deep trace inspection.

## 10. Build order & parallelization plan

To fan out across multiple Claude Code sessions without collisions:

1. **Solo, first (~1h):** write `contracts.py` exactly as §6. This is the integration contract.
2. **Fan out — one session per component, each against mocks** (never touching each other's files):
   - Session A → **Component 1** (Sandbox/Repo Manager) — most independent.
   - Session B → **Component 3** (HITL Simulator) — independent (just needs `after_dir`+brief).
   - Session C → **Component 5** (Judge) — independent (mock a `TakerResult`).
   - Session D → **Component 7** (Streamlit + Phoenix wiring) — consumes `ComparisonReport`.
   - **Component 2** (Test-taker Runner) — highest-risk (Claude Agent SDK + skill loading +
     ask_question + budget). **Owner builds this** or pairs on it. Metrics (4) folds in here.
3. **Owner integrates** as pieces land via **Component 6** (the LangGraph graph in `run_eval`).

Independence ranking (easiest to delegate → hardest): **1, 3, 5, 7** then **2/4**, then **6**.

## 11. Out of scope (YAGNI for the hackathon)
- Docker/container isolation of taker `bash` (revisit if running untrusted skills).
- Multi-tenant / persistent eval history beyond Phoenix's local store.
- Auth, deployment, CI.
- Auto-generating the `task_brief` from the diff (it's an input).
- Cost/billing dashboards (Phoenix shows token usage already).

## 12. Risks & open questions
- **Skill loading mechanism** in the Claude Agent SDK — confirm whether to use a skills
  directory vs. system-prompt injection. *(Build-time spike, Component 2.)*
- **`ask_question` interception** — confirm the cleanest SDK mechanism (custom in-process tool
  vs. hook). *(Build-time spike, Component 2.)*
- **Budget enforcement granularity** — token/wall-clock aborts may land mid-turn; define what
  "partial diff" means at abort.
- **Taker runs arbitrary `bash`** on the host (no Docker) — acceptable for trusted hackathon
  skills only.
- **Phoenix score-distribution polish** — Phoenix is trace-first; the polished 0–20 distribution
  charts are built in Streamlit, with Phoenix used for deep trace drill-down.
- **Models matrix size** — `models: list[str]` multiplies runs by `len(models) × 2 arms`; keep
  the list short for the demo.
