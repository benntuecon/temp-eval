# Phase B — Real Haiku-backed Components

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Steps use `- [ ]`.

**Goal:** Replace the simulated taker/simulator/judges with real `claude-haiku-4-5`-backed implementations, so `run_eval(cfg)` (no injected fns) runs a genuine eval: two Claude-Agent-SDK coding agents (each loaded with a skill) attempt the task, a reactive LLM simulator answers their questions, and an LLM judge panel scores the results 0–20. The orchestrator, sandbox, contracts, and dashboard do **not** change shape.

**Architecture:** Three new modules implement the contract signatures the orchestrator already lazy-imports: `skill_eval/taker.py` (`run_taker`), `skill_eval/simulator.py` (`make_simulator`), `skill_eval/judge.py` (`run_judge`). The taker uses the async Claude Agent SDK; the simulator and judges are single **synchronous** Anthropic calls (so they slot into the existing sync-via-`to_thread` orchestrator with no nested event loops).

**Tech Stack:** `claude-agent-sdk` (taker), `anthropic` sync client (simulator + judges), `claude-haiku-4-5`. Phoenix gets real spans via `phoenix.otel.register(auto_instrument=True)`.

**Cost discipline:** Model is always Haiku. `uv run pytest` makes **zero** API calls — every unit test mocks the SDK/client. One `@pytest.mark.live` smoke test (skipped by default) does a single real end-to-end run (~$0.10–0.20).

## Confirmed SDK wiring (from spikes #3/#4 — do not re-derive)

- **Skill loading = system-prompt injection (Approach B).** Read `<skill_path>/SKILL.md` and inject it into `system_prompt`. Reliable + identical treatment for both arms. (Default model resolves to Opus if unset — always pass `model="claude-haiku-4-5"`.)
- **`ask_question` = custom in-process MCP tool.** `@tool("ask_question", ...)` + `create_sdk_mcp_server(name="hitl", ...)`, register via `mcp_servers={"hitl": server}`, allow with `allowed_tools=[..., "mcp__hitl__ask_question"]`. The handler calls `ask_fn(question)`, increments a counter (→ `num_questions`).
- **Metrics from the final `ResultMessage`:** `num_turns`, `usage["input_tokens"]`, `usage["output_tokens"]`, `duration_ms`, `stop_reason`. The SDK **raises** on `is_error` instead of yielding → wrap the run in `try/except`.
- **Budgets:** `max_turns=cfg.max_turns` on the options; wall-clock via `asyncio.timeout(cfg.wall_clock_seconds)`; `max_tokens` is a best-effort post-check (not a hard mid-run abort).
- **StopReason mapping:** `stop_reason == "end_turn"` → `COMPLETED`; turns exhausted → `MAX_TURNS`; `asyncio.TimeoutError` → `WALL_CLOCK`; any exception/`is_error` → `ERROR`.

## File Structure

| File | Responsibility |
|---|---|
| `pyproject.toml` (modify) | register `live` pytest marker + default `-m "not live"` |
| `skill_eval/simulator.py` | C3: real reactive simulator (sync Anthropic call) |
| `skill_eval/judge.py` | C5: real judge (sync Anthropic call, 0–20 anchored, robust parse) |
| `skill_eval/taker.py` | C2: real taker (async Agent SDK, skill + ask_question + budget + metrics) |
| `skill_eval/reporting.py` (modify) | wire `phoenix.otel.register(auto_instrument=True)` |
| `app.py` (modify) | sidebar toggle: simulated (default) vs real Haiku |
| `tests/test_simulator.py`, `tests/test_judge.py`, `tests/test_taker.py` | mocked unit tests |
| `tests/test_live_smoke.py` | `@pytest.mark.live` real end-to-end |

Gates each task: `uv run ruff check .` · `ruff format --check .` · `mypy` · `pytest` (which skips live).

---

## Task 0: pytest live marker (keep CI free)

- [ ] In `pyproject.toml` `[tool.pytest.ini_options]` add:
```toml
markers = ["live: hits the real Anthropic API (skipped by default)"]
addopts = "-m 'not live'"
```
- [ ] Verify `uv run pytest -q` still green, then commit `test: add live marker, default-skip live tests`.

---

## Task 1: C3 — real simulator (`skill_eval/simulator.py`)

Reactive oracle: answers a taker's question using the gold tree + task brief, **never volunteering the implementation** (per the reactive-only design decision in the spec).

- [ ] **Test first** `tests/test_simulator.py` — mock `anthropic.Anthropic`:
```python
from unittest.mock import MagicMock, patch
from skill_eval.simulator import make_simulator


@patch("skill_eval.simulator.anthropic.Anthropic")
def test_make_simulator_answers(mock_cls, tmp_path):
    (tmp_path / "calculator.py").write_text("def add(a, b):\n    return a + b\n")
    msg = MagicMock()
    msg.content = [MagicMock(text="Yes — it should return the sum.")]
    mock_cls.return_value.messages.create.return_value = msg

    ask = make_simulator(str(tmp_path), "Fix add so it sums.", "claude-haiku-4-5")
    answer = ask("Should add return a+b?")
    assert "sum" in answer.lower()
    # used the cheapest model + included the question
    _, kwargs = mock_cls.return_value.messages.create.call_args
    assert kwargs["model"] == "claude-haiku-4-5"
```
- [ ] **Implement** `make_simulator(after_dir, task_brief, model) -> AskFn`:
  - Build a gold-context string once (the closure captures it): `task_brief` + a bounded listing/snippet of files under `after_dir` (cap total chars, e.g. 6000).
  - System prompt persona: *"You are the human stakeholder who requested this task. You know the intended outcome. Answer the engineer's question helpfully and concisely. Do NOT write their code or dictate the implementation line-by-line — answer at the requirement level. Only answer what is asked."*
  - The returned `ask(question)` does a sync call: `anthropic.Anthropic().messages.create(model=model, max_tokens=400, system=<persona+gold>, messages=[{"role":"user","content":question}])`, returns the concatenated text. (Import `anthropic` at module top so the patch target is `skill_eval.simulator.anthropic.Anthropic`.)
- [ ] Gates + commit `feat: C3 real reactive simulator (Haiku)`.

---

## Task 2: C5 — real judge (`skill_eval/judge.py`)

- [ ] **Test first** `tests/test_judge.py` — mock the client; cover parse + clamp:
```python
from unittest.mock import MagicMock, patch
from skill_eval.contracts import Arm, Criterion, JudgeInput, RunMetrics, StopReason, TakerResult
from skill_eval.judge import run_judge


def _ji():
    m = RunMetrics(0, 0, 0, 0.0, 0, 0)
    t = TakerResult(Arm.CHALLENGER, "m", "+    return a + b", (), (), StopReason.COMPLETED, m)
    return JudgeInput(Criterion.CORRECTNESS, "fix add", "+    return a + b", "/x", t)


@patch("skill_eval.judge.anthropic.Anthropic")
def test_run_judge_parses_score(mock_cls):
    msg = MagicMock()
    msg.content = [MagicMock(text='{"score": 18, "rationale": "correct fix"}')]
    mock_cls.return_value.messages.create.return_value = msg
    s = run_judge(_ji(), "claude-haiku-4-5")
    assert s.criterion is Criterion.CORRECTNESS
    assert s.score == 18 and s.rationale


@patch("skill_eval.judge.anthropic.Anthropic")
def test_run_judge_clamps(mock_cls):
    msg = MagicMock()
    msg.content = [MagicMock(text='{"score": 99, "rationale": "x"}')]
    mock_cls.return_value.messages.create.return_value = msg
    assert run_judge(_ji(), "claude-haiku-4-5").score == 20
```
- [ ] **Implement** `run_judge(ji, model) -> JudgeScore`:
  - Per-criterion anchored rubric in the prompt with the 0–20 scale (0 = no/zero implementation … 10 = partial … 20 = matches gold/excellent) and 1–2 few-shot anchors. Include `ji.task_brief`, `ji.gold_diff`, `ji.taker.diff`, and a short transcript note.
  - Ask the model to reply with **strict JSON** `{"score": <int 0-20>, "rationale": "<one sentence>"}`. `max_tokens=300`.
  - Parse robustly: try `json.loads` on the first `{...}` block; fall back to a regex for `score`/an integer; **clamp to [0,20]**; default rationale if missing. Return `JudgeScore(ji.criterion, score, rationale)`.
- [ ] Gates + commit `feat: C5 real judge with 0-20 anchored rubric (Haiku)`.

---

## Task 3: C2 — real taker (`skill_eval/taker.py`)

The hard one. Sync entrypoint wrapping the async Agent SDK; runs in the orchestrator's worker thread so internal `asyncio.run` is safe.

- [ ] **First, pure helpers + their tests** (`tests/test_taker.py`, no SDK/network):
  - `_metrics_from_result(result_msg, num_questions, wall_seconds) -> RunMetrics` — reads `usage["input_tokens"]`/`["output_tokens"]`, `num_turns`; total = in+out.
  - `_stop_reason(result_msg, timed_out: bool, max_turns: int) -> StopReason` — timed_out→WALL_CLOCK; `num_turns >= max_turns`→MAX_TURNS; `stop_reason=="end_turn"`→COMPLETED; else COMPLETED.
  - `_compute_diff(taker_dir) -> str` — `git -C dir add -A` then `git -C dir diff --cached HEAD` (captures new + modified files).
  Test these with fake objects / a temp git repo. Example:
```python
from skill_eval.taker import _stop_reason
from skill_eval.contracts import StopReason
class _R:  # fake ResultMessage
    def __init__(self, n, sr): self.num_turns=n; self.stop_reason=sr
def test_stop_reason_timeout():
    assert _stop_reason(_R(2, "end_turn"), True, 30) is StopReason.WALL_CLOCK
def test_stop_reason_max_turns():
    assert _stop_reason(_R(30, None), False, 30) is StopReason.MAX_TURNS
def test_stop_reason_completed():
    assert _stop_reason(_R(3, "end_turn"), False, 30) is StopReason.COMPLETED
```
- [ ] **Mocked integration test** — patch `claude_agent_sdk.query` with a fake async generator yielding one fake `ResultMessage`; patch `create_sdk_mcp_server`/`tool` as needed; build a temp git worktree; assert `run_taker(...)` returns a `TakerResult` whose `diff` reflects an edit and `metrics`/`stop_reason` are populated. (Keep this focused; the real agentic loop is covered by the live smoke.)
- [ ] **Implement** `run_taker(ws, model, skill_path, cfg, ask_fn) -> TakerResult`:
  - Read `Path(skill_path)/"SKILL.md"` → `skill_md` (empty string if missing).
  - `num_questions = 0`. Define the tool:
```python
from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions, query

@tool("ask_question", "Ask the human stakeholder a clarifying question.", {"question": str})
async def _ask(args):
    nonlocal num_questions  # use a mutable holder (list) if nonlocal is awkward
    num_questions += 1
    return {"content": [{"type": "text", "text": ask_fn(args["question"])}]}

server = create_sdk_mcp_server(name="hitl", version="1.0.0", tools=[_ask])
options = ClaudeAgentOptions(
    model="claude-haiku-4-5",
    cwd=ws.taker_dir,
    system_prompt=f"{skill_md}\n\nYou are an engineer. Complete the task. "
                  f"Use the ask_question tool if you need clarification.",
    allowed_tools=["Read","Write","Edit","Bash","Grep","Glob","mcp__hitl__ask_question"],
    mcp_servers={"hitl": server},
    max_turns=cfg.max_turns,
    permission_mode="bypassPermissions",  # autonomous edits in the isolated worktree
)
```
  - `_session()` async: collect messages/transcript, keep the last `ResultMessage`, measure wall time. Wrap the `async for` in `asyncio.timeout(cfg.wall_clock_seconds)` when set; catch `asyncio.TimeoutError` (→ timed_out=True) and broad `Exception` (→ ERROR path).
  - Run via `asyncio.run(_session())`. Build `diff = _compute_diff(ws.taker_dir)`, metrics, stop_reason; assemble `TakerResult(arm=ws.arm, model=model, diff=diff, transcript=tuple(transcript), questions=tuple(...), stop_reason=..., metrics=...)`. Track the actual questions asked (append in the tool handler).
- [ ] Gates + commit `feat: C2 real taker via Claude Agent SDK (Haiku, skill + ask_question + budget)`.

---

## Task 4: Phoenix real tracing (`reporting.py`)

- [ ] Update `init_phoenix()` to actually export spans:
```python
def init_phoenix() -> str | None:
    try:
        import phoenix as px
        from phoenix.otel import register
        session = px.launch_app()
        register(project_name="skill-eval", auto_instrument=True)  # exports LangChain/LangGraph + Anthropic spans
        return getattr(session, "url", None) or str(session)
    except Exception:
        return None
```
- [ ] Keep it best-effort (never raises). Existing `reporting` tests still pass. Commit `feat: wire Phoenix OTel register + auto-instrument for real spans`.

---

## Task 5: app.py — simulated vs real toggle

- [ ] Add a sidebar `st.checkbox("Use real Haiku agents (Phase B — ~$0.10–0.20/run)", value=False)`.
- [ ] When checked, the background `_background` injects the real components:
```python
if use_real:
    from skill_eval.taker import run_taker
    from skill_eval.simulator import make_simulator
    from skill_eval.judge import run_judge
    report = run_eval(cfg, taker_fn=run_taker, simulator_factory=make_simulator,
                      judge_fn=run_judge, on_event=on_event)
else:
    report = run_eval(cfg, taker_fn=sim_run_taker, simulator_factory=sim_make_simulator,
                      judge_fn=sim_run_judge, on_event=on_event)
```
- [ ] `import app` stays side-effect-free; commit `feat: dashboard toggle for real vs simulated agents`.

---

## Task 6: Live smoke test + one real run

- [ ] `tests/test_live_smoke.py`:
```python
import os, tempfile
import pytest
from skill_eval.sample_repo import build_sample_repo
from skill_eval.orchestrator import run_eval
from skill_eval.contracts import Arm, Criterion


@pytest.mark.live
@pytest.mark.skipif(not os.environ.get("ANTHROPIC_API_KEY"), reason="no API key")
def test_real_end_to_end():
    cfg = build_sample_repo(tempfile.mkdtemp())
    report = run_eval(cfg)  # real components (lazy defaults), Haiku
    assert {a.arm for a in report.arms} == {Arm.BASELINE, Arm.CHALLENGER}
    for ar in report.arms:
        assert {s.criterion for s in ar.scores} == set(Criterion)
        assert all(0 <= s.score <= 20 for s in ar.scores)
    assert report.pairwise_verdict
```
- [ ] Run it for real ONCE: `uv run pytest tests/test_live_smoke.py -m live -q -s`. Confirm a real `ComparisonReport` (both arms, 0–20 scores). Record cost/observations.
- [ ] Commit `test: live end-to-end smoke (real Haiku)`.

---

## Phase B done criteria
- `uv run pytest` green and **makes no API calls** (live skipped).
- `uv run pytest -m live` produces a real `ComparisonReport` on the calculator task with Haiku.
- Streamlit toggle runs the real pipeline; Phoenix shows per-agent spans (taker/simulator/judge) with tokens.
- Orchestrator/contracts/sandbox unchanged.
