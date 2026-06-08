# Walking Skeleton — Phase A (simulated end-to-end + live visual)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Run the entire defined workflow end-to-end — sandbox → 2 test-takers (concurrent) → HITL simulator answering questions → 6 judges (concurrent) → comparison report — driven by LangGraph, traced in Phoenix, and shown live in Streamlit. Phase A uses **simulated** LLM components (deterministic, zero API cost). Phase B swaps in real Haiku-backed components with no change to the orchestrator or dashboard.

**Architecture:** Components are injected into the orchestrator as functions matching the `contracts.py` signatures (`run_taker`, `make_simulator`, `run_judge`). Phase A passes the `simulated.py` implementations; Phase B passes the real ones. The orchestrator is a LangGraph graph that fans out to takers then judges, emits stage events through an `on_event` callback for the live UI, and returns a `ComparisonReport`. Visualization = Phoenix (OpenInference traces of the LangGraph run) + Streamlit (live per-arm status + final 0–20 comparison).

**Tech Stack:** Python ≥3.11 (uv), `langgraph`, `arize-phoenix` + `openinference-instrumentation-langchain`, `streamlit`. Cheapest model (`claude-haiku-4-5`) is Phase B only — Phase A makes **no API calls**.

**Scope:** Phase A only (issues #5 sandbox, #10 orchestrator, #9 dashboards, plus simulated stand-ins for #6/#7/#8). Real Haiku components (#6/#7/#8) are Phase B, a separate plan.

**Cost guardrail:** Phase A must not call the Anthropic API. The only "agents" are deterministic Python functions.

---

## Design: the injectable seam

The orchestrator never imports a concrete component. Its signature:

```python
def run_eval(
    cfg: RunConfig,
    *,
    taker_fn: TakerFn = ...,            # (ws, model, skill_path, cfg, ask_fn) -> TakerResult
    simulator_factory: MakeSimulator = ...,  # (after_dir, task_brief, model) -> AskFn
    judge_fn: JudgeFn = ...,            # (ji, model) -> JudgeScore
    on_event: EventFn | None = None,    # (dict) -> None   live-progress sink
) -> ComparisonReport: ...
```

Phase A wiring: `taker_fn=sim_run_taker, simulator_factory=sim_make_simulator, judge_fn=sim_run_judge`.
Phase B wiring: the real implementations. Nothing else changes.

`TakerFn`, `JudgeFn`, `EventFn` are `Callable` aliases added to `contracts.py` in Task 0.

---

## File Structure

| File | Responsibility |
|---|---|
| `skill_eval/contracts.py` (modify) | Add `TakerFn`, `JudgeFn`, `EventFn`, `Event` aliases/type |
| `skill_eval/sample_repo.py` | Build a throwaway git repo with before/after commits + task brief (for tests + demo) |
| `skill_eval/sandbox.py` | C1: `prepare_workspaces` — git worktrees + gold diff |
| `skill_eval/simulated.py` | Deterministic `sim_run_taker` / `sim_make_simulator` / `sim_run_judge` |
| `skill_eval/orchestrator.py` | C6: LangGraph `run_eval` with injection + events |
| `skill_eval/reporting.py` | Phoenix init + helpers to summarize a `ComparisonReport` |
| `app.py` | Streamlit: run the eval, live per-arm status, final comparison |
| `tests/test_sandbox.py`, `tests/test_simulated.py`, `tests/test_orchestrator.py`, `tests/test_reporting.py` | Tests |

Every task ends green on `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy`, `uv run pytest`.

---

## Task 0: Extend contracts with injection/event aliases

**Files:** Modify `skill_eval/contracts.py`; Test `tests/test_contracts.py` (extend).

- [ ] **Step 1: Add a test** for the new aliases in `tests/test_contracts.py`:
```python
def test_phase_a_aliases_importable():
    from skill_eval.contracts import EventFn, JudgeFn, TakerFn  # noqa: F401
```
- [ ] **Step 2:** Run `uv run pytest tests/test_contracts.py -q` → FAIL (ImportError).
- [ ] **Step 3: Add to `contracts.py`** (after the existing aliases, keeping style):
```python
# Orchestrator injection points (Phase A walking skeleton):
TakerFn = Callable[["Workspace", str, str, "RunConfig", AskFn], "TakerResult"]
JudgeFn = Callable[["JudgeInput", str], "JudgeScore"]
# Live-progress event sink. Event is a free-form dict: {"stage", "arm"?, "msg", ...}.
Event = dict
EventFn = Callable[[Event], None]
```
(Place these near the other `Callable` aliases; forward-reference names already defined above are fine as plain names — drop the quotes if the symbols precede this block.)
- [ ] **Step 4:** Run `uv run pytest -q` → PASS. Run gates (`ruff check`, `ruff format --check`, `mypy`).
- [ ] **Step 5: Commit** `git commit -m "feat: add orchestrator injection + event aliases (#10)"`

---

## Task 1: Sample task-repo builder

A helper that creates a temporary git repo with two commits (before = stub with a bug, after = fixed) and returns a `RunConfig`. Used by every later test and by the demo so the pipeline has something real to run on.

**Files:** Create `skill_eval/sample_repo.py`; Test `tests/test_sample_repo.py`.

- [ ] **Step 1: Write the test** `tests/test_sample_repo.py`:
```python
import subprocess

from skill_eval.sample_repo import build_sample_repo


def _commit_exists(repo: str, sha: str) -> bool:
    return subprocess.run(["git", "-C", repo, "cat-file", "-e", sha]).returncode == 0


def test_build_sample_repo(tmp_path):
    cfg = build_sample_repo(str(tmp_path))
    assert cfg.repo_path == str(tmp_path)
    assert cfg.before_hash and cfg.after_hash
    assert cfg.before_hash != cfg.after_hash
    assert _commit_exists(cfg.repo_path, cfg.before_hash)
    assert _commit_exists(cfg.repo_path, cfg.after_hash)
    assert cfg.task_brief
    # before has the bug, after fixes it
    before = subprocess.run(
        ["git", "-C", cfg.repo_path, "show", f"{cfg.before_hash}:calculator.py"],
        capture_output=True, text=True,
    ).stdout
    after = subprocess.run(
        ["git", "-C", cfg.repo_path, "show", f"{cfg.after_hash}:calculator.py"],
        capture_output=True, text=True,
    ).stdout
    assert "return a - b" in before   # the bug
    assert "return a + b" in after    # the fix
```

- [ ] **Step 2:** Run → FAIL (no module).
- [ ] **Step 3: Implement `skill_eval/sample_repo.py`.** Build a repo with `calculator.py` (an `add` that wrongly subtracts) + a failing test, commit = before; fix `add` to return `a + b`, commit = after. Return a `RunConfig` with both skill paths pointing at a tiny placeholder skill dir under the repo (e.g. `.claude/skills/baseline` and `.../challenger`, each a one-line `SKILL.md`), `models=("claude-haiku-4-5",)`, and a `task_brief` describing the fix. Use `subprocess.run(["git", ...], cwd=path, check=True)` with a local user.name/email config so commits work in CI. Capture the SHAs via `git rev-parse HEAD`.
```python
import subprocess
from pathlib import Path

from skill_eval.contracts import RunConfig

TASK_BRIEF = (
    "The `add(a, b)` function in calculator.py returns the wrong result "
    "(it subtracts). Fix it so it returns the sum, and make the tests pass."
)


def _git(repo: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", repo, *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def build_sample_repo(path: str) -> RunConfig:
    repo = Path(path)
    repo.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "eval@example.com")
    _git(path, "config", "user.name", "Eval Fixture")
    # placeholder skills so skill_path is a real dir (real loading is Phase B)
    for arm in ("baseline", "challenger"):
        sk = repo / ".claude/skills" / arm
        sk.mkdir(parents=True, exist_ok=True)
        (sk / "SKILL.md").write_text(
            f"---\nname: {arm}\ndescription: {arm} coding skill (placeholder)\n---\n"
        )
    (repo / "calculator.py").write_text("def add(a, b):\n    return a - b  # BUG\n")
    (repo / "test_calculator.py").write_text(
        "from calculator import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    )
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "before: calculator with add bug")
    before = _git(path, "rev-parse", "HEAD")
    (repo / "calculator.py").write_text("def add(a, b):\n    return a + b\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "after: fix add")
    after = _git(path, "rev-parse", "HEAD")
    return RunConfig(
        before_hash=before,
        after_hash=after,
        repo_path=path,
        task_brief=TASK_BRIEF,
        baseline_skill_path=str(repo / ".claude/skills/baseline"),
        challenger_skill_path=str(repo / ".claude/skills/challenger"),
        models=("claude-haiku-4-5",),
    )
```
- [ ] **Step 4:** Run → PASS. Gates green.
- [ ] **Step 5: Commit** `git commit -m "feat: sample task-repo builder for the skeleton (#5)"`

---

## Task 2: C1 Sandbox — worktrees + gold diff

**Files:** Create `skill_eval/sandbox.py`; Test `tests/test_sandbox.py`.

- [ ] **Step 1: Write the test** `tests/test_sandbox.py`:
```python
import os

from skill_eval.contracts import Arm
from skill_eval.sample_repo import build_sample_repo
from skill_eval.sandbox import cleanup_workspaces, prepare_workspaces


def test_prepare_workspaces(tmp_path):
    cfg = build_sample_repo(str(tmp_path / "repo"))
    spaces = prepare_workspaces(cfg)
    try:
        assert set(spaces) == {Arm.BASELINE, Arm.CHALLENGER}
        for arm, ws in spaces.items():
            assert ws.arm is arm
            assert os.path.isdir(ws.taker_dir)
            # taker dir is checked out at the BEFORE commit (still has the bug)
            calc = open(os.path.join(ws.taker_dir, "calculator.py")).read()
            assert "return a - b" in calc
            # after dir has the fix
            after_calc = open(os.path.join(ws.after_dir, "calculator.py")).read()
            assert "return a + b" in after_calc
            # gold diff goes bug -> fix
            assert "-    return a - b" in ws.gold_diff
            assert "+    return a + b" in ws.gold_diff
    finally:
        cleanup_workspaces(spaces)
```

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement `skill_eval/sandbox.py`.** Implement `prepare_workspaces(cfg) -> dict[Arm, Workspace]` using `git worktree add --detach <dir> <hash>` into a temp area under `<repo>/.worktrees/...` (gitignored): one taker worktree per arm at `before_hash`, one shared `after` worktree at `after_hash`. `gold_diff = git -C <repo> diff <before>..<after>`. Also implement `cleanup_workspaces(spaces)` that runs `git worktree remove --force` for each unique dir. Use `tempfile.mkdtemp` dirs and `subprocess.run([...], check=True)`.
```python
import subprocess
import tempfile
from pathlib import Path

from skill_eval.contracts import Arm, RunConfig, Workspace


def _git(repo: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", repo, *args], check=True, capture_output=True, text=True
    ).stdout


def prepare_workspaces(cfg: RunConfig) -> dict[Arm, Workspace]:
    base = Path(cfg.repo_path) / ".worktrees"
    base.mkdir(exist_ok=True)
    after_dir = tempfile.mkdtemp(prefix="after_", dir=base)
    _git(cfg.repo_path, "worktree", "add", "--detach", "-f", after_dir, cfg.after_hash)
    gold_diff = _git(cfg.repo_path, "diff", f"{cfg.before_hash}..{cfg.after_hash}")
    spaces: dict[Arm, Workspace] = {}
    for arm in (Arm.BASELINE, Arm.CHALLENGER):
        taker_dir = tempfile.mkdtemp(prefix=f"{arm.value}_", dir=base)
        _git(cfg.repo_path, "worktree", "add", "--detach", "-f", taker_dir, cfg.before_hash)
        spaces[arm] = Workspace(
            arm=arm, taker_dir=taker_dir, after_dir=after_dir, gold_diff=gold_diff
        )
    return spaces


def cleanup_workspaces(spaces: dict[Arm, Workspace]) -> None:
    if not spaces:
        return
    repo = None
    dirs = set()
    for ws in spaces.values():
        dirs.add(ws.taker_dir)
        dirs.add(ws.after_dir)
    for ws in spaces.values():
        repo = str(Path(ws.taker_dir).parent.parent)  # <repo>/.worktrees/<dir>
        break
    for d in dirs:
        if repo:
            subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", d])
```
- [ ] **Step 4:** Run → PASS. Gates green.
- [ ] **Step 5: Commit** `git commit -m "feat: C1 sandbox — git worktrees + gold diff (#5)"`

---

## Task 3: Simulated components

Deterministic stand-ins for the taker, simulator, and judges. They exercise the real workflow shape (the taker actually asks a question via `ask_fn` and writes a partial change so the diff is real), but do **no** API calls. Small `time.sleep`s + `on_event`-friendly returns make the live view lively.

**Files:** Create `skill_eval/simulated.py`; Test `tests/test_simulated.py`.

- [ ] **Step 1: Write the test** `tests/test_simulated.py`:
```python
from skill_eval.contracts import (
    Arm,
    Criterion,
    JudgeInput,
    RunMetrics,
    StopReason,
    TakerResult,
)
from skill_eval.sample_repo import build_sample_repo
from skill_eval.sandbox import cleanup_workspaces, prepare_workspaces
from skill_eval.simulated import sim_make_simulator, sim_run_judge, sim_run_taker


def test_sim_simulator_answers():
    ask = sim_make_simulator(after_dir="/x", task_brief="fix add", model="m")
    answer = ask("Should add return the sum?")
    assert isinstance(answer, str) and answer


def test_sim_taker_asks_and_returns(tmp_path):
    cfg = build_sample_repo(str(tmp_path / "repo"))
    spaces = prepare_workspaces(cfg)
    try:
        asked = []
        ask = lambda q: asked.append(q) or "Yes, return a + b."  # noqa: E731
        res = sim_run_taker(
            spaces[Arm.CHALLENGER], "m", cfg.challenger_skill_path, cfg, ask
        )
        assert isinstance(res, TakerResult)
        assert res.arm is Arm.CHALLENGER
        assert len(asked) == res.metrics.num_questions >= 1
        assert res.stop_reason in set(StopReason)
        assert isinstance(res.metrics, RunMetrics)
    finally:
        cleanup_workspaces(spaces)


def test_sim_judge_scores_in_range():
    metrics = RunMetrics(0, 0, 0, 0.0, 0, 0)
    taker = TakerResult(
        arm=Arm.BASELINE, model="m", diff="+ return a + b",
        transcript=(), questions=(), stop_reason=StopReason.COMPLETED, metrics=metrics,
    )
    ji = JudgeInput(
        criterion=Criterion.CORRECTNESS, task_brief="fix add",
        gold_diff="+ return a + b", after_dir="/x", taker=taker,
    )
    score = sim_run_judge(ji, "m")
    assert score.criterion is Criterion.CORRECTNESS
    assert 0 <= score.score <= 20
    assert score.rationale
```

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement `skill_eval/simulated.py`.** `sim_make_simulator` returns an `ask` closure giving a canned helpful answer (vary slightly by question). `sim_run_taker` calls `ask_fn` once with a plausible clarifying question, optionally writes a partial fix into `ws.taker_dir/calculator.py` and computes a real `git diff`, sleeps ~0.3s, and returns a `TakerResult` with fabricated-but-sensible `RunMetrics` (challenger gets a slightly higher-quality result than baseline so the comparison is interesting). `sim_run_judge` returns a deterministic 0–20 score keyed off the criterion + whether the taker diff contains `a + b` (so the "correct" arm scores high), with a short rationale. Keep challenger > baseline on average. Use only stdlib + contracts; no network.
- [ ] **Step 4:** Run → PASS. Gates green.
- [ ] **Step 5: Commit** `git commit -m "feat: simulated taker/simulator/judges for the skeleton"`

---

## Task 4: C6 Orchestrator (LangGraph)

**Files:** Create `skill_eval/orchestrator.py`; Test `tests/test_orchestrator.py`.

- [ ] **Step 1: Write the test** `tests/test_orchestrator.py`:
```python
from skill_eval.contracts import Arm, ComparisonReport, Criterion
from skill_eval.orchestrator import run_eval
from skill_eval.sample_repo import build_sample_repo
from skill_eval.simulated import sim_make_simulator, sim_run_judge, sim_run_taker


def test_run_eval_simulated_end_to_end(tmp_path):
    cfg = build_sample_repo(str(tmp_path / "repo"))
    events = []
    report = run_eval(
        cfg,
        taker_fn=sim_run_taker,
        simulator_factory=sim_make_simulator,
        judge_fn=sim_run_judge,
        on_event=events.append,
    )
    assert isinstance(report, ComparisonReport)
    arms = {a.arm for a in report.arms}
    assert arms == {Arm.BASELINE, Arm.CHALLENGER}
    for arm_report in report.arms:
        # one score per criterion
        assert {s.criterion for s in arm_report.scores} == set(Criterion)
        assert arm_report.total_score == sum(s.score for s in arm_report.scores)
    assert report.pairwise_verdict
    # events captured the workflow stages
    stages = {e.get("stage") for e in events}
    assert {"sandbox", "taker", "judge", "report"} <= stages
```

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement `skill_eval/orchestrator.py`.** Build a LangGraph `StateGraph` over a `TypedDict` state (`cfg`, `spaces`, `taker_results`, `scores`, `report`, plus the injected fns + `on_event`). Nodes:
  - `prepare`: call `prepare_workspaces(cfg)`; emit `{"stage":"sandbox", "msg": "..."}`.
  - `takers`: run both arms **concurrently** with `asyncio.gather` wrapping `taker_fn` in `asyncio.to_thread` (the sim/real fns are sync); each builds an `ask_fn` via `simulator_factory(ws.after_dir, cfg.task_brief, model)`; emit `{"stage":"taker","arm":...,"msg":...}` before/after each.
  - `judges`: for every (arm × `Criterion`) run `judge_fn` **concurrently** via `asyncio.to_thread`; emit `{"stage":"judge","arm":...,"criterion":...}`.
  - `assemble`: build `ArmReport`s (total_score = sum of scores), a `pairwise_verdict` string (compare total_scores across arms, name the winner with the margin), and the `ComparisonReport`; emit `{"stage":"report"}`.
  Compile the graph and run it (`graph.invoke` inside `asyncio.run`, or make nodes sync and use `asyncio.run` only inside the takers/judges nodes). Expose `run_eval(cfg, *, taker_fn=..., simulator_factory=..., judge_fn=..., on_event=None) -> ComparisonReport` with the real implementations as defaults (import them lazily to avoid forcing the API deps at import time). Always `cleanup_workspaces` in a `finally`.
  - [ ] Keep model = `cfg.models[0]` for now (single-model skeleton).
- [ ] **Step 4:** Run → PASS. Gates green.
- [ ] **Step 5: Commit** `git commit -m "feat: C6 LangGraph orchestrator with injection + events (#10)"`

---

## Task 5: C7 Visualization — Phoenix + Streamlit

**Files:** Create `skill_eval/reporting.py`, `app.py`; Test `tests/test_reporting.py`.

- [ ] **Step 1: Write the test** `tests/test_reporting.py` for the pure helpers (no Streamlit/Phoenix runtime):
```python
from skill_eval.contracts import (
    Arm, ArmReport, ComparisonReport, Criterion, JudgeScore, RunConfig, RunMetrics,
)
from skill_eval.reporting import scores_table, verdict_line


def _report():
    m = RunMetrics(100, 60, 40, 1.2, 3, 1)
    def arm(a, base):
        scores = [JudgeScore(c, base + i, "ok") for i, c in enumerate(Criterion)]
        return ArmReport(a, "claude-haiku-4-5", m, scores, sum(s.score for s in scores))
    cfg = RunConfig("a", "b", "/r", "x", "/b", "/c", ("claude-haiku-4-5",))
    return ComparisonReport(cfg, [arm(Arm.BASELINE, 8), arm(Arm.CHALLENGER, 12)], "challenger wins")


def test_scores_table_shape():
    rows = scores_table(_report())
    # one row per criterion, columns per arm
    assert len(rows) == len(Criterion)
    assert "baseline" in rows[0] and "challenger" in rows[0]


def test_verdict_line():
    assert "challenger" in verdict_line(_report()).lower()
```

- [ ] **Step 2:** Run → FAIL.
- [ ] **Step 3: Implement `skill_eval/reporting.py`** with: `init_phoenix()` (launch/register Phoenix tracer + `LangChainInstrumentor().instrument()` guarded by try/except so missing/None is non-fatal; return the session/url or None); `scores_table(report) -> list[dict]` (one row per criterion with a column per arm + the criterion name); `verdict_line(report) -> str` (re-derive winner from total scores). Keep `init_phoenix` import-safe (don't crash if phoenix isn't running).
- [ ] **Step 4: Implement `app.py`** (Streamlit). On load: `init_phoenix()` and show the Phoenix URL. A **"Run eval"** button builds the sample repo (`build_sample_repo` in a temp dir), then runs `run_eval(cfg, taker_fn=sim_run_taker, simulator_factory=sim_make_simulator, judge_fn=sim_run_judge, on_event=...)` in a background thread that pushes events into a `queue.Queue`; the main script drains the queue into two side-by-side per-arm status panels (baseline vs challenger) updating live via `st.empty()` placeholders, plus a running event log. On completion render: a **0–20 grouped bar chart per criterion** (baseline vs challenger) via `st.bar_chart` on `scores_table(report)`, an objective-metrics table, and the `verdict_line`. Add a sidebar note: "Phase A = simulated data (no API)."
- [ ] **Step 5: Smoke-check** (no API):
  - `uv run pytest -q` (reporting helpers pass)
  - `uv run python -c "import app"` parses/imports clean (guard Streamlit calls under a `main()` or `if __name__` where needed so import is side-effect-free)
  - Manually: `uv run streamlit run app.py` → click Run → watch the live per-arm panels fill, then the comparison chart + verdict. (Document this manual step in the commit message; CI can't click.)
- [ ] **Step 6: Gates + Commit**
  ```bash
  uv run ruff format . && uv run ruff check . && uv run mypy && uv run pytest -q
  git add skill_eval/reporting.py app.py tests/test_reporting.py
  git commit -m "feat: C7 Phoenix + Streamlit live race & comparison (#9)"
  ```

---

## Phase A done criteria

- `uv run pytest` green; all four gates clean; **no test hits the network**.
- `uv run streamlit run app.py` → **Run eval** shows the full workflow executing live (sandbox → 2 takers asking questions → 6 judges) and ends with a baseline-vs-challenger 0–20 comparison + verdict. Phoenix shows the LangGraph run trace.
- The orchestrator + dashboard are component-agnostic, so Phase B only swaps the three injected functions.

## Phase B preview (separate plan)
Real `run_taker` (Agent SDK, Haiku, skill via system-prompt injection per spike #3, `ask_question` tool → simulator per spike #4, budget + `ResultMessage` metrics, try/except → `StopReason.ERROR`), real `make_simulator` (one Haiku call), real `run_judge` (Haiku, 0–20 anchored few-shot). Add `openinference-instrumentation-anthropic` so LLM calls show in Phoenix. Inject them into the same `run_eval`.
