# Skill Eval — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the foundation that unblocks all parallel component work — a installable Python package, the shared `contracts.py` integration contract, and two runnable spikes that pin down the Claude Agent SDK mechanisms the test-taker depends on.

**Architecture:** A single Python package `skill_eval` exposing typed data contracts that every later component imports. Two throwaway spike scripts validate (a) loading an isolated Claude Code Skill into an Agent SDK session and (b) routing a custom `ask_question` tool to a Python handler while capturing budgets/metrics. Findings are written to `docs/superpowers/spikes/`.

**Tech Stack:** Python ≥3.11, `claude-agent-sdk`, `langgraph`, `arize-phoenix`, `streamlit`, `pytest`, `mypy`. Build backend: `hatchling`.

**Scope:** This plan covers GitHub issues **#1** (scaffolding), **#2** (contracts), **#3** (skill-loading spike), **#4** (ask_question spike). Components C1/C2/C3/C5/C6/C7 (issues #5–#10) get their own plans, written by the parallel sessions against the contract this plan produces.

**Prerequisites:**
- Tasks 1–2: only `pip` (no network to Anthropic).
- Tasks 3–4 (spikes): require `ANTHROPIC_API_KEY` in the environment **and** network egress to the Anthropic API. Confirm the sandbox allows this before starting them.

---

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` | Package metadata, deps, pytest config |
| `.gitignore` | Ignore venv, `.env`, worktree temp dirs, Phoenix store |
| `.env.example` | Document required env vars |
| `README.md` | How to install + run |
| `skill_eval/__init__.py` | Package marker + `__version__` |
| `skill_eval/contracts.py` | **All shared types + component signatures** (the integration contract) |
| `tests/test_smoke.py` | Package imports |
| `tests/test_contracts.py` | Contracts are constructible, frozen where required, enums correct |
| `spikes/spike_skill_loading.py` | Validate isolated skill loading (issue #3) |
| `spikes/spike_ask_question.py` | Validate custom tool routing + counting + metrics (issue #4) |
| `tests/fixtures/skills/haiku-only/SKILL.md` | Fixture skill for the loading spike |
| `docs/superpowers/spikes/2026-06-06-skill-loading.md` | Findings (issue #3) |
| `docs/superpowers/spikes/2026-06-06-ask-question-and-metrics.md` | Findings (issue #4) |

---

## Task 1: Project scaffolding (issue #1)

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `README.md`
- Create: `skill_eval/__init__.py`
- Test: `tests/test_smoke.py`

- [ ] **Step 1: Write the failing smoke test**

Create `tests/test_smoke.py`:
```python
def test_package_imports():
    import skill_eval

    assert skill_eval.__version__ == "0.1.0"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skill_eval'`

- [ ] **Step 3: Create the package**

Create `skill_eval/__init__.py`:
```python
"""Skill Eval — eval/comparison harness for two Claude Code Skills."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Create `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "skill-eval"
version = "0.1.0"
description = "Eval/comparison harness for two Claude Code Skills"
requires-python = ">=3.11"
dependencies = [
    "claude-agent-sdk",
    "anthropic",
    "langgraph",
    "arize-phoenix",
    "arize-phoenix-otel",
    "openinference-instrumentation-langchain",
    "openinference-instrumentation-anthropic",
    "streamlit",
]

[project.optional-dependencies]
dev = ["pytest", "mypy"]

[tool.hatch.build.targets.wheel]
packages = ["skill_eval"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 5: Create `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
.venv/
venv/
*.egg-info/
.pytest_cache/
.mypy_cache/
.env
# git worktrees created at runtime for test-takers
.worktrees/
# Phoenix local trace store
.phoenix/
```

- [ ] **Step 6: Create `.env.example`**

```dotenv
# Required for the test-takers, simulator, and judges (Tasks 3-4 and all components)
ANTHROPIC_API_KEY=sk-ant-...
# Phoenix runs locally; default endpoint is fine. Override if needed:
# PHOENIX_COLLECTOR_ENDPOINT=http://localhost:6006
```

- [ ] **Step 7: Create `README.md`**

```markdown
# skill-eval

Eval/comparison harness for two Claude Code Skills (baseline vs challenger).
See `docs/superpowers/specs/2026-06-06-skill-eval-system-design.md`.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # then fill in ANTHROPIC_API_KEY
```

## Run

```bash
pytest                       # unit tests
phoenix serve                # trace UI at http://localhost:6006 (once Phoenix is wired)
```
```

- [ ] **Step 8: Install the package**

Run: `pip install -e ".[dev]"`
Expected: installs `skill-eval` and dev deps without error.

- [ ] **Step 9: Run the smoke test to verify it passes**

Run: `python -m pytest tests/test_smoke.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add pyproject.toml .gitignore .env.example README.md skill_eval/__init__.py tests/test_smoke.py
git commit -m "feat: project scaffolding and dependencies (#1)"
```

---

## Task 2: Shared data contracts (issue #2)

**Files:**
- Create: `skill_eval/contracts.py`
- Test: `tests/test_contracts.py`

- [ ] **Step 1: Write the failing contracts test**

Create `tests/test_contracts.py`:
```python
import dataclasses

import pytest

from skill_eval.contracts import (
    Arm,
    StopReason,
    Criterion,
    RunConfig,
    Workspace,
    RunMetrics,
    TakerResult,
    JudgeInput,
    JudgeScore,
    ArmReport,
    ComparisonReport,
)


def test_enum_values():
    assert Arm.BASELINE.value == "baseline"
    assert Arm.CHALLENGER.value == "challenger"
    assert StopReason.MAX_TURNS.value == "max_turns"
    assert {c.value for c in Criterion} == {
        "correctness",
        "completeness",
        "distance_to_gold",
        "code_quality",
        "question_quality",
        "approach",
    }


def test_runconfig_defaults_and_frozen():
    cfg = RunConfig(
        before_hash="aaa",
        after_hash="bbb",
        repo_path="/repo",
        task_brief="Implement feature X",
        baseline_skill_path="/skills/base",
        challenger_skill_path="/skills/chal",
        models=["claude-opus-4-8"],
    )
    assert cfg.max_turns == 30
    assert cfg.max_tokens is None
    assert cfg.wall_clock_seconds is None
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.max_turns = 5  # type: ignore[misc]


def test_workspace_frozen():
    ws = Workspace(arm=Arm.BASELINE, taker_dir="/t", after_dir="/a", gold_diff="diff")
    with pytest.raises(dataclasses.FrozenInstanceError):
        ws.taker_dir = "/x"  # type: ignore[misc]


def test_full_report_composition():
    metrics = RunMetrics(
        total_tokens=10,
        input_tokens=6,
        output_tokens=4,
        wall_seconds=1.5,
        num_turns=2,
        num_questions=1,
    )
    taker = TakerResult(
        arm=Arm.CHALLENGER,
        model="claude-opus-4-8",
        diff="patch",
        transcript=[{"role": "user", "content": "hi"}],
        questions=["which db?"],
        stop_reason=StopReason.COMPLETED,
        metrics=metrics,
    )
    assert taker.metrics.num_questions == 1

    score = JudgeScore(
        criterion=Criterion.CORRECTNESS, score=20, rationale="matches gold"
    )
    arm_report = ArmReport(
        arm=Arm.CHALLENGER,
        model="claude-opus-4-8",
        metrics=metrics,
        scores=[score],
        total_score=20,
    )
    report = ComparisonReport(
        config=RunConfig(
            before_hash="a",
            after_hash="b",
            repo_path="/repo",
            task_brief="x",
            baseline_skill_path="/b",
            challenger_skill_path="/c",
            models=["claude-opus-4-8"],
        ),
        arms=[arm_report],
        pairwise_verdict="challenger wins",
    )
    assert report.arms[0].scores[0].score == 20


def test_judge_input_constructs():
    metrics = RunMetrics(0, 0, 0, 0.0, 0, 0)
    taker = TakerResult(
        arm=Arm.BASELINE,
        model="m",
        diff="",
        transcript=[],
        questions=[],
        stop_reason=StopReason.MAX_TURNS,
        metrics=metrics,
    )
    ji = JudgeInput(
        criterion=Criterion.COMPLETENESS,
        task_brief="x",
        gold_diff="gold",
        after_dir="/a",
        taker=taker,
    )
    assert ji.criterion is Criterion.COMPLETENESS


def test_callable_aliases_importable():
    from skill_eval.contracts import AskFn, MakeSimulator  # noqa: F401
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python -m pytest tests/test_contracts.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'skill_eval.contracts'`

- [ ] **Step 3: Implement `skill_eval/contracts.py`**

```python
"""Shared data contracts for the skill-eval harness.

This is the single integration point every component builds against. It contains
only types and function signatures — no business logic. See the design spec §6.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional


# ---------- Enums ----------


class Arm(str, Enum):
    """Which skill a test-taker is running."""

    BASELINE = "baseline"
    CHALLENGER = "challenger"


class StopReason(str, Enum):
    """Why a test-taker run ended."""

    COMPLETED = "completed"
    MAX_TURNS = "max_turns"
    MAX_TOKENS = "max_tokens"
    WALL_CLOCK = "wall_clock"
    ERROR = "error"


class Criterion(str, Enum):
    """One judged dimension. Each becomes its own concurrent judge."""

    CORRECTNESS = "correctness"            # satisfies the requirement (vs gold)
    COMPLETENESS = "completeness"          # how much of the task got done
    DISTANCE_TO_GOLD = "distance_to_gold"  # semantic closeness of diff to gold diff
    CODE_QUALITY = "code_quality"          # maintainability / idiomaticity
    QUESTION_QUALITY = "question_quality"  # quality of clarifying questions asked
    APPROACH = "approach"                  # strategy / efficiency / lack of thrashing


# ---------- Inputs ----------


@dataclass(frozen=True)
class RunConfig:
    """The eval's input: commits, task, skills, and the test budget."""

    before_hash: str
    after_hash: str
    repo_path: str
    task_brief: str                            # PRD / Jira story / requirement text
    baseline_skill_path: str                   # path to baseline skill dir
    challenger_skill_path: str                 # path to challenger skill dir
    models: list[str]                          # one full eval per model
    max_turns: int = 30
    max_tokens: Optional[int] = None           # optional hard token cap
    wall_clock_seconds: Optional[int] = None   # real elapsed-time cap


# ---------- Sandbox (Component 1) ----------


@dataclass(frozen=True)
class Workspace:
    """Isolated dirs for one arm plus the shared gold tree."""

    arm: Arm
    taker_dir: str        # worktree @before_hash the taker edits
    after_dir: str        # read-only worktree @after_hash (gold tree)
    gold_diff: str        # `git diff before..after`


# ---------- Metrics (Component 4) ----------


@dataclass
class RunMetrics:
    """Objective, non-LLM measurements of a single taker run."""

    total_tokens: int
    input_tokens: int
    output_tokens: int
    wall_seconds: float
    num_turns: int
    num_questions: int


# ---------- Test-taker (Component 2) ----------


# Handler injected for the custom ask_question tool: question -> answer text.
AskFn = Callable[[str], str]


@dataclass
class TakerResult:
    """Everything one taker produced, ready for judging."""

    arm: Arm
    model: str
    diff: str                  # patch: before_hash -> taker end state
    transcript: list[dict]     # full message log
    questions: list[str]       # clarifying questions the taker asked
    stop_reason: StopReason
    metrics: RunMetrics


# ---------- HITL Simulator (Component 3) ----------


# Factory binds ground-truth context, returns the AskFn handed to a taker:
# (after_dir, task_brief, model) -> AskFn
MakeSimulator = Callable[[str, str, str], AskFn]


# ---------- Judges (Component 5) ----------


@dataclass(frozen=True)
class JudgeInput:
    """Everything one judge needs to score one criterion for one taker."""

    criterion: Criterion
    task_brief: str
    gold_diff: str
    after_dir: str
    taker: TakerResult


@dataclass
class JudgeScore:
    """A single judge's 0-20 score plus rationale."""

    criterion: Criterion
    score: int                 # 0-20, anchored
    rationale: str


# ---------- Final report (Component 7) ----------


@dataclass
class ArmReport:
    """Aggregated result for one arm (one model)."""

    arm: Arm
    model: str
    metrics: RunMetrics
    scores: list[JudgeScore]
    total_score: int           # sum of criterion scores (or weighted)


@dataclass
class ComparisonReport:
    """The system's output: baseline vs challenger, per model."""

    config: RunConfig
    arms: list[ArmReport]      # baseline + challenger, per model
    pairwise_verdict: str      # which is better and why


# ---------- Component function signatures ----------
# Implementations live in their own modules; these signatures are the contract.


def prepare_workspaces(cfg: RunConfig) -> dict[Arm, Workspace]:
    """Component 1: create git worktrees and compute the gold diff."""
    raise NotImplementedError


def run_taker(
    ws: Workspace,
    model: str,
    skill_path: str,
    cfg: RunConfig,
    ask_fn: AskFn,
) -> TakerResult:
    """Component 2: run a Claude Agent SDK session under budget; return result."""
    raise NotImplementedError


def make_simulator(after_dir: str, task_brief: str, model: str) -> AskFn:
    """Component 3: build the AskFn the simulator uses to answer questions."""
    raise NotImplementedError


def run_judge(ji: JudgeInput, model: str) -> JudgeScore:
    """Component 5: score one criterion for one taker (0-20)."""
    raise NotImplementedError


def run_eval(cfg: RunConfig) -> ComparisonReport:
    """Component 6: orchestrate the whole eval and return the comparison."""
    raise NotImplementedError
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python -m pytest tests/test_contracts.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Type-check the contract (issue #2 acceptance)**

Run: `python -m mypy skill_eval/contracts.py`
Expected: `Success: no issues found in 1 source file`

- [ ] **Step 6: Commit**

```bash
git add skill_eval/contracts.py tests/test_contracts.py
git commit -m "feat: shared data contracts (#2)"
```

---

## Task 3: Spike — isolated skill loading (issue #3)

This is an **investigation**, not red-green TDD: it runs a real Agent SDK session, observes behavior, and records findings. The script below is the best-known API from the SDK docs; **Step 2 verifies the actual installed API and you adapt + record any deltas in the findings doc.** Requires `ANTHROPIC_API_KEY` + network.

**Files:**
- Create: `tests/fixtures/skills/haiku-only/SKILL.md`
- Create: `spikes/spike_skill_loading.py`
- Create: `docs/superpowers/spikes/2026-06-06-skill-loading.md`

- [ ] **Step 1: Create a detectable fixture skill**

Create `tests/fixtures/skills/haiku-only/SKILL.md`:
```markdown
---
name: haiku-only
description: Use for ANY user request, no matter the topic. Forces all answers to be a haiku.
---

# Haiku Only

No matter what the user asks, respond with EXACTLY one haiku (three lines,
5-7-5 syllables) and nothing else. Begin the first line with the word "Skill".
```

The `Skill` first-word marker makes activation trivially detectable in output.

- [ ] **Step 2: Confirm the installed SDK surface**

Run:
```bash
python -c "import claude_agent_sdk, inspect; print(claude_agent_sdk.__version__); import claude_agent_sdk as s; print([n for n in dir(s) if not n.startswith('_')])"
python -c "from claude_agent_sdk import ClaudeAgentOptions; import inspect; print(inspect.signature(ClaudeAgentOptions.__init__))"
```
Expected: prints a version and the available names; the `ClaudeAgentOptions` signature shows which of `cwd`, `setting_sources`, `skills`, `system_prompt`, `allowed_tools` actually exist. **Record the real signature in the findings doc.** If `skills`/`setting_sources` are absent, only Approach B (system-prompt injection) is viable — note that and skip Approach A.

- [ ] **Step 3: Write the spike script**

Create `spikes/spike_skill_loading.py`:
```python
"""Spike (#3): can we load ONE specific Claude Code Skill into an isolated session?

Run: python spikes/spike_skill_loading.py
Requires: ANTHROPIC_API_KEY in env.
Adapt option names to the real SDK signature found in Step 2; record deltas.
"""

import asyncio
import shutil
import tempfile
from pathlib import Path

from claude_agent_sdk import query, ClaudeAgentOptions

FIXTURE = Path(__file__).parent.parent / "tests/fixtures/skills/haiku-only"
PROMPT = "What is the capital of France?"


def _collect_text(messages: list) -> str:
    """Best-effort concatenation of assistant text across SDK message shapes."""
    out = []
    for m in messages:
        result = getattr(m, "result", None)
        if isinstance(result, str):
            out.append(result)
        content = getattr(m, "content", None)
        if isinstance(content, list):
            for block in content:
                text = getattr(block, "text", None)
                if text:
                    out.append(text)
    return "\n".join(out)


async def approach_a_setting_sources() -> str:
    """Point the SDK at a project dir that contains only the fixture skill."""
    workdir = Path(tempfile.mkdtemp(prefix="spike_skill_a_"))
    skill_dst = workdir / ".claude/skills/haiku-only"
    skill_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXTURE, skill_dst)
    try:
        options = ClaudeAgentOptions(
            cwd=str(workdir),
            setting_sources=["project"],
            skills=["haiku-only"],
            allowed_tools=["Skill"],
        )
        messages = [m async for m in query(prompt=PROMPT, options=options)]
        return _collect_text(messages)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def approach_b_system_prompt() -> str:
    """Fallback: inject the SKILL.md straight into the system prompt."""
    skill_md = (FIXTURE / "SKILL.md").read_text()
    options = ClaudeAgentOptions(
        system_prompt=f"Follow this skill exactly:\n\n{skill_md}",
        allowed_tools=[],
    )
    messages = [m async for m in query(prompt=PROMPT, options=options)]
    return _collect_text(messages)


async def main() -> None:
    for name, coro in [("A setting_sources", approach_a_setting_sources),
                       ("B system_prompt", approach_b_system_prompt)]:
        try:
            text = await coro()
            activated = text.strip().lower().startswith("skill")
            print(f"\n=== Approach {name} ===")
            print(text)
            print(f"ACTIVATED={activated}")
        except Exception as exc:  # noqa: BLE001 - spike: surface any failure
            print(f"\n=== Approach {name} FAILED: {type(exc).__name__}: {exc} ===")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: Run the spike and observe**

Run: `python spikes/spike_skill_loading.py`
Expected: each approach prints the model's answer and `ACTIVATED=True/False`. A haiku starting with "Skill" means that approach loaded the skill. At least one approach should activate.

- [ ] **Step 5: Record findings**

Create `docs/superpowers/spikes/2026-06-06-skill-loading.md` documenting:
- The real `ClaudeAgentOptions` signature (from Step 2).
- Which approach(es) activated the skill (`ACTIVATED=True`).
- **The recommended mechanism for C2** to load exactly one skill with no cross-contamination, and the exact options to use.
- Any deltas from the script (renamed/missing options).

Template:
```markdown
# Spike #3 — Isolated skill loading

SDK version: <x.y.z>
ClaudeAgentOptions signature: <paste>

## Result
- Approach A (setting_sources + skills filter): ACTIVATED=<bool>
- Approach B (system_prompt injection): ACTIVATED=<bool>

## Recommendation for C2 (run_taker)
<the exact option dict to load one skill in isolation, and why>
```

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures/skills/haiku-only/SKILL.md spikes/spike_skill_loading.py docs/superpowers/spikes/2026-06-06-skill-loading.md
git commit -m "spike: isolated Claude Code Skill loading in Agent SDK (#3)"
```

---

## Task 4: Spike — ask_question routing, counting & metrics (issue #4)

Investigation that pins down: custom-tool round-trip to a Python handler, counting tool calls, reading token/turn metrics, and wall-clock cancellation. Requires `ANTHROPIC_API_KEY` + network.

**Files:**
- Create: `spikes/spike_ask_question.py`
- Create: `docs/superpowers/spikes/2026-06-06-ask-question-and-metrics.md`

- [ ] **Step 1: Confirm the tool & result API**

Run:
```bash
python -c "from claude_agent_sdk import tool, create_sdk_mcp_server; print('tools ok')"
python -c "import claude_agent_sdk as s; print([n for n in dir(s) if 'Result' in n or 'Message' in n or 'Hook' in n])"
```
Expected: prints `tools ok` and the names of the result/message/hook classes. **Record them** — you'll confirm the metrics attribute names empirically in Step 3.

- [ ] **Step 2: Write the spike script**

Create `spikes/spike_ask_question.py`:
```python
"""Spike (#4): custom ask_question tool -> Python handler; counting; metrics; timeout.

Run: python spikes/spike_ask_question.py
Requires: ANTHROPIC_API_KEY in env.
"""

import asyncio
import dataclasses
from typing import Any

from claude_agent_sdk import (
    query,
    ClaudeAgentOptions,
    tool,
    create_sdk_mcp_server,
    HookMatcher,
)

# --- the Python callback the agent's question must reach ---
HANDLER_CALLS: list[str] = []


def my_callback(question: str) -> str:
    HANDLER_CALLS.append(question)
    # Stand-in for the real HITL simulator (Component 3).
    return "Use PostgreSQL."


@tool("ask_question", "Ask the human stakeholder a clarifying question.", {"question": str})
async def ask_question(args: dict[str, Any]) -> dict[str, Any]:
    answer = my_callback(args["question"])
    return {"content": [{"type": "text", "text": answer}]}


# --- count tool calls via a PostToolUse hook (cross-check with HANDLER_CALLS) ---
HOOK_COUNTS: dict[str, int] = {}


async def count_hook(input_data, tool_use_id, context):  # noqa: ANN001
    name = input_data.get("tool_name", "?")
    HOOK_COUNTS[name] = HOOK_COUNTS.get(name, 0) + 1
    return {}


PROMPT = (
    "You MUST call the ask_question tool exactly once to ask which database to "
    "use, then reply in one sentence naming that database. Do not assume."
)


def dump_metrics(message) -> None:
    """Discover the REAL metric attribute names on the final message."""
    print(f"\n-- final message type: {type(message).__name__}")
    if dataclasses.is_dataclass(message):
        print(dataclasses.asdict(message))
    else:
        print({k: v for k, v in vars(message).items()})


async def main() -> None:
    server = create_sdk_mcp_server(name="hitl", version="1.0.0", tools=[ask_question])
    options = ClaudeAgentOptions(
        mcp_servers={"hitl": server},
        allowed_tools=["mcp__hitl__ask_question"],
        max_turns=5,
        hooks={"PostToolUse": [HookMatcher(hooks=[count_hook])]},
    )

    last = None
    try:
        async with asyncio.timeout(120):
            async for message in query(prompt=PROMPT, options=options):
                last = message
    except TimeoutError:
        print("WALL-CLOCK TIMEOUT fired (asyncio.timeout)")

    print(f"\nHANDLER_CALLS = {HANDLER_CALLS}")
    print(f"HOOK_COUNTS   = {HOOK_COUNTS}")
    if last is not None:
        dump_metrics(last)


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Run the spike and observe**

Run: `python spikes/spike_ask_question.py`
Expected:
- `HANDLER_CALLS` contains exactly one question string → the agent's tool call reached the Python handler.
- `HOOK_COUNTS` shows `mcp__hitl__ask_question: 1` (confirms the counting mechanism for `num_questions`).
- The `dump_metrics` output reveals the **actual** attribute names carrying input/output tokens and the end/stop reason.

- [ ] **Step 4: Record findings**

Create `docs/superpowers/spikes/2026-06-06-ask-question-and-metrics.md`:
```markdown
# Spike #4 — ask_question routing, counting, metrics

SDK version: <x.y.z>
Result/Message/Hook classes: <from Step 1>

## Confirmed
- Custom tool -> Python handler round-trip: <works? exact wiring>
- Question counting: HANDLER_CALLS vs HOOK_COUNTS agreed = <bool>; chosen method for `num_questions` = <which>
- Metric attribute names (map to RunMetrics):
  - input_tokens  -> <real attr>
  - output_tokens -> <real attr>
  - total_tokens  -> <real attr or input+output>
  - num_turns     -> <real attr or count of assistant turns>
  - stop/end reason -> <real attr> ; mapping to StopReason: <table>
- Wall-clock: asyncio.timeout fired = <bool>; how to mark StopReason.WALL_CLOCK on cancel.

## Recommendation for C2 (run_taker)
<exact options + how to populate RunMetrics + StopReason from a real run>
```

- [ ] **Step 5: Commit**

```bash
git add spikes/spike_ask_question.py docs/superpowers/spikes/2026-06-06-ask-question-and-metrics.md
git commit -m "spike: ask_question routing, counting, and metrics (#4)"
```

---

## Done criteria for this plan

- `pip install -e ".[dev]"` succeeds; `pytest` is green; `mypy skill_eval/contracts.py` is clean.
- `skill_eval/contracts.py` matches spec §6 exactly — every later component can import its types and signatures.
- Both spike findings docs answer the open questions in spec §12 with concrete, copy-pasteable options for C2.
- After this plan, issues #5–#10 can be built in parallel against a locked contract.
