# Batch Cases + Concurrent Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 10 sample task repos, generalize the simulated scoring for per-case variance, and wire a concurrent batch runner so the eval dashboard has rich, differentiated data.

**Architecture:** Three new/modified files — `skill_eval/sample_cases.py` (10 task repos via `build_sample_cases`), `skill_eval/simulated.py` (hash-based deterministic scoring + task-seeded metrics), `skill_eval/batch.py` (ThreadPoolExecutor wrapper around `run_eval`). Two new test files validate them with no API calls.

**Tech Stack:** Python 3.11+, hashlib.sha256 (deterministic hashing), concurrent.futures.ThreadPoolExecutor, pytest, existing skill_eval contracts (RunConfig, ComparisonReport), git_ops module for all git operations.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `skill_eval/sample_cases.py` | Create | 10 task repos, `build_sample_cases()` |
| `skill_eval/simulated.py` | Modify | Hash-based scoring, task-seeded metrics, generic marker write |
| `skill_eval/batch.py` | Create | Concurrent batch runner, `run_batch()` |
| `tests/test_sample_cases.py` | Create | Validates 10 RunConfigs structure |
| `tests/test_batch.py` | Create | Validates 3-case batch run with variance |

---

### Task 1: Create `skill_eval/sample_cases.py` with all 10 task repos

**Files:**
- Create: `skill_eval/sample_cases.py`

- [ ] **Step 1: Write the failing test first**

Create `tests/test_sample_cases.py`:

```python
import subprocess

import pytest

from skill_eval.sample_cases import build_sample_cases


def _commit_exists(repo: str, sha: str) -> bool:
    return subprocess.run(["git", "-C", repo, "cat-file", "-e", sha]).returncode == 0


def test_build_sample_cases_returns_10(tmp_path):
    cfgs = build_sample_cases(str(tmp_path))
    assert len(cfgs) == 10


def test_sample_cases_distinct_repos(tmp_path):
    cfgs = build_sample_cases(str(tmp_path))
    repo_paths = [c.repo_path for c in cfgs]
    assert len(set(repo_paths)) == 10


def test_sample_cases_before_after_differ(tmp_path):
    cfgs = build_sample_cases(str(tmp_path))
    for cfg in cfgs:
        assert cfg.before_hash != cfg.after_hash


def test_sample_cases_commits_exist(tmp_path):
    cfgs = build_sample_cases(str(tmp_path))
    for cfg in cfgs:
        assert _commit_exists(cfg.repo_path, cfg.before_hash)
        assert _commit_exists(cfg.repo_path, cfg.after_hash)


def test_sample_cases_task_brief_nonempty(tmp_path):
    cfgs = build_sample_cases(str(tmp_path))
    for cfg in cfgs:
        assert cfg.task_brief.strip()


def test_sample_cases_skill_dirs_exist(tmp_path):
    from pathlib import Path

    cfgs = build_sample_cases(str(tmp_path))
    for cfg in cfgs:
        assert Path(cfg.baseline_skill_path).is_dir()
        assert Path(cfg.challenger_skill_path).is_dir()
```

- [ ] **Step 2: Run the test to verify it fails (import error)**

```bash
cd /Users/Ben/code/learning/skill-eval && uv run pytest tests/test_sample_cases.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'skill_eval.sample_cases'`

- [ ] **Step 3: Implement `skill_eval/sample_cases.py`**

```python
"""Ten sample task repos for the skill-eval batch runner.

Each repo has two commits (before/buggy and after/fixed) plus a failing→passing
test file, matching the pattern of skill_eval.sample_repo.build_sample_repo.
"""

from pathlib import Path

from skill_eval import git_ops
from skill_eval.contracts import RunConfig


def _init_repo(path: Path) -> None:
    """Initialise a git repo with standard eval config."""
    path.mkdir(parents=True, exist_ok=True)
    git_ops.init(str(path))
    git_ops.config(str(path), "user.email", "eval@example.com")
    git_ops.config(str(path), "user.name", "Eval Fixture")


def _add_skills(repo: Path) -> tuple[str, str]:
    """Create placeholder skill dirs; return (baseline_path, challenger_path)."""
    for arm in ("baseline", "challenger"):
        sk = repo / ".claude/skills" / arm
        sk.mkdir(parents=True, exist_ok=True)
        (sk / "SKILL.md").write_text(
            f"---\nname: {arm}\ndescription: {arm} coding skill (placeholder)\n---\n"
        )
    return (
        str(repo / ".claude/skills/baseline"),
        str(repo / ".claude/skills/challenger"),
    )


def _make_case(
    base_dir: str,
    case_id: str,
    src_file: str,
    buggy_src: str,
    fixed_src: str,
    test_src: str,
    task_brief: str,
) -> RunConfig:
    """Build one case repo and return its RunConfig."""
    repo = Path(base_dir) / case_id
    _init_repo(repo)
    baseline_path, challenger_path = _add_skills(repo)

    # Before commit (buggy)
    (repo / src_file).write_text(buggy_src)
    (repo / f"test_{src_file}").write_text(test_src)
    git_ops.add_all(str(repo))
    git_ops.commit(str(repo), f"before: {case_id} with bug")
    before_hash = git_ops.rev_parse(str(repo))

    # After commit (fixed)
    (repo / src_file).write_text(fixed_src)
    git_ops.add_all(str(repo))
    git_ops.commit(str(repo), f"after: {case_id} fix")
    after_hash = git_ops.rev_parse(str(repo))

    return RunConfig(
        before_hash=before_hash,
        after_hash=after_hash,
        repo_path=str(repo),
        task_brief=task_brief,
        baseline_skill_path=baseline_path,
        challenger_skill_path=challenger_path,
        models=("claude-haiku-4-5",),
    )


def build_sample_cases(base_dir: str) -> list[RunConfig]:
    """Build 10 sample task repos under *base_dir*; return one RunConfig each."""
    cases: list[RunConfig] = []

    # Case 01: calculator add
    cases.append(
        _make_case(
            base_dir,
            "case_01",
            "calculator.py",
            buggy_src="def add(a, b):\n    return a - b  # BUG\n",
            fixed_src="def add(a, b):\n    return a + b\n",
            test_src=(
                "from calculator import add\n\n\n"
                "def test_add():\n    assert add(2, 3) == 5\n"
            ),
            task_brief=(
                "The `add(a, b)` function in calculator.py subtracts instead of adding. "
                "Fix it so it returns the sum and make the tests pass."
            ),
        )
    )

    # Case 02: string reversal
    cases.append(
        _make_case(
            base_dir,
            "case_02",
            "strings.py",
            buggy_src="def reverse_string(s):\n    return s  # BUG: should reverse\n",
            fixed_src="def reverse_string(s):\n    return s[::-1]\n",
            test_src=(
                "from strings import reverse_string\n\n\n"
                "def test_reverse_string():\n"
                '    assert reverse_string("abc") == "cba"\n'
            ),
            task_brief=(
                "The `reverse_string(s)` function in strings.py returns the string unchanged "
                "instead of reversed. Fix it so reverse_string('abc') returns 'cba'."
            ),
        )
    )

    # Case 03: is_even parity check
    cases.append(
        _make_case(
            base_dir,
            "case_03",
            "numbers.py",
            buggy_src="def is_even(n):\n    return n % 2 == 1  # BUG: inverted\n",
            fixed_src="def is_even(n):\n    return n % 2 == 0\n",
            test_src=(
                "from numbers import is_even\n\n\n"
                "def test_is_even():\n"
                "    assert is_even(4)\n"
                "    assert not is_even(3)\n"
            ),
            task_brief=(
                "The `is_even(n)` function in numbers.py has inverted logic (returns True for "
                "odd numbers). Fix it so is_even(4) is True and is_even(3) is False."
            ),
        )
    )

    # Case 04: factorial missing base case
    cases.append(
        _make_case(
            base_dir,
            "case_04",
            "recursion.py",
            buggy_src=(
                "def factorial(n):\n"
                "    return n * factorial(n - 1)  # BUG: missing base case\n"
            ),
            fixed_src=(
                "def factorial(n):\n"
                "    if n <= 1:\n"
                "        return 1\n"
                "    return n * factorial(n - 1)\n"
            ),
            test_src=(
                "from recursion import factorial\n\n\n"
                "def test_factorial():\n"
                "    assert factorial(5) == 120\n"
            ),
            task_brief=(
                "The `factorial(n)` function in recursion.py is missing a base case and causes "
                "infinite recursion. Add `if n <= 1: return 1` so factorial(5) returns 120."
            ),
        )
    )

    # Case 05: max_in_list uses min
    cases.append(
        _make_case(
            base_dir,
            "case_05",
            "lists.py",
            buggy_src="def max_in_list(xs):\n    return min(xs)  # BUG: should be max\n",
            fixed_src="def max_in_list(xs):\n    return max(xs)\n",
            test_src=(
                "from lists import max_in_list\n\n\n"
                "def test_max_in_list():\n"
                "    assert max_in_list([3, 7, 2]) == 7\n"
            ),
            task_brief=(
                "The `max_in_list(xs)` function in lists.py returns the minimum instead of "
                "the maximum. Fix it so max_in_list([3, 7, 2]) returns 7."
            ),
        )
    )

    # Case 06: count_vowels missing 'u'
    cases.append(
        _make_case(
            base_dir,
            "case_06",
            "text.py",
            buggy_src=(
                "def count_vowels(s):\n"
                '    vowels = "aeio"  # BUG: missing u\n'
                "    return sum(1 for c in s.lower() if c in vowels)\n"
            ),
            fixed_src=(
                "def count_vowels(s):\n"
                '    vowels = "aeiou"\n'
                "    return sum(1 for c in s.lower() if c in vowels)\n"
            ),
            test_src=(
                "from text import count_vowels\n\n\n"
                "def test_count_vowels():\n"
                '    assert count_vowels("queue") == 4\n'
            ),
            task_brief=(
                "The `count_vowels(s)` function in text.py uses vowels='aeio' (missing 'u'). "
                "Fix it so count_vowels('queue') returns 4."
            ),
        )
    )

    # Case 07: fizzbuzz wrong check order
    cases.append(
        _make_case(
            base_dir,
            "case_07",
            "fizzbuzz.py",
            buggy_src=(
                "def fizzbuzz(n):\n"
                "    if n % 3 == 0:\n"
                '        return "Fizz"  # BUG: checked before n%15\n'
                "    elif n % 5 == 0:\n"
                '        return "Buzz"\n'
                "    elif n % 15 == 0:\n"
                '        return "FizzBuzz"\n'
                "    return str(n)\n"
            ),
            fixed_src=(
                "def fizzbuzz(n):\n"
                "    if n % 15 == 0:\n"
                '        return "FizzBuzz"\n'
                "    elif n % 3 == 0:\n"
                '        return "Fizz"\n'
                "    elif n % 5 == 0:\n"
                '        return "Buzz"\n'
                "    return str(n)\n"
            ),
            test_src=(
                "from fizzbuzz import fizzbuzz\n\n\n"
                "def test_fizzbuzz_15():\n"
                '    assert fizzbuzz(15) == "FizzBuzz"\n'
            ),
            task_brief=(
                "The `fizzbuzz(n)` function in fizzbuzz.py checks n%3 and n%5 before n%15, "
                "so fizzbuzz(15) returns 'Fizz' instead of 'FizzBuzz'. Fix the check order."
            ),
        )
    )

    # Case 08: celsius to fahrenheit missing +32
    cases.append(
        _make_case(
            base_dir,
            "case_08",
            "temperature.py",
            buggy_src=(
                "def c_to_f(c):\n"
                "    return c * 9 / 5  # BUG: missing + 32\n"
            ),
            fixed_src=(
                "def c_to_f(c):\n"
                "    return c * 9 / 5 + 32\n"
            ),
            test_src=(
                "from temperature import c_to_f\n\n\n"
                "def test_c_to_f():\n"
                "    assert c_to_f(100) == 212\n"
            ),
            task_brief=(
                "The `c_to_f(c)` function in temperature.py is missing the +32 offset. "
                "Fix it so c_to_f(100) returns 212."
            ),
        )
    )

    # Case 09: dedupe doesn't preserve order
    cases.append(
        _make_case(
            base_dir,
            "case_09",
            "dedupe.py",
            buggy_src=(
                "def dedupe(xs):\n"
                "    return list(set(xs))  # BUG: doesn't preserve order\n"
            ),
            fixed_src=(
                "def dedupe(xs):\n"
                "    seen: set = set()\n"
                "    result = []\n"
                "    for x in xs:\n"
                "        if x not in seen:\n"
                "            seen.add(x)\n"
                "            result.append(x)\n"
                "    return result\n"
            ),
            test_src=(
                "from dedupe import dedupe\n\n\n"
                "def test_dedupe_preserves_order():\n"
                "    assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]\n"
            ),
            task_brief=(
                "The `dedupe(xs)` function in dedupe.py uses set() which destroys ordering. "
                "Rewrite it to deduplicate while preserving first-occurrence order so "
                "dedupe([3, 1, 3, 2, 1]) returns [3, 1, 2]."
            ),
        )
    )

    # Case 10: gcd stub returns a
    cases.append(
        _make_case(
            base_dir,
            "case_10",
            "mathutils.py",
            buggy_src=(
                "def gcd(a, b):\n"
                "    return a  # BUG: stub, should be Euclidean algorithm\n"
            ),
            fixed_src=(
                "def gcd(a, b):\n"
                "    while b:\n"
                "        a, b = b, a % b\n"
                "    return a\n"
            ),
            test_src=(
                "from mathutils import gcd\n\n\n"
                "def test_gcd():\n"
                "    assert gcd(12, 18) == 6\n"
            ),
            task_brief=(
                "The `gcd(a, b)` function in mathutils.py is a stub that returns `a`. "
                "Implement the Euclidean algorithm so gcd(12, 18) returns 6."
            ),
        )
    )

    return cases
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
cd /Users/Ben/code/learning/skill-eval && uv run pytest tests/test_sample_cases.py -v
```

Expected: 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skill_eval/sample_cases.py tests/test_sample_cases.py
git commit -m "feat: add 10 sample task repos in sample_cases.py"
```

---

### Task 2: Generalize `skill_eval/simulated.py`

**Files:**
- Modify: `skill_eval/simulated.py`

The key change: replace the hardcoded `"a + b"` heuristic with a `hashlib.sha256`-based deterministic score per `(task_brief, arm, criterion)`. Challenger gets a slight bias (+1 to +3 from hash) but with enough variance that baseline can win individual criteria.

- [ ] **Step 1: Verify existing tests pass before changes**

```bash
cd /Users/Ben/code/learning/skill-eval && uv run pytest tests/test_simulated.py tests/test_orchestrator.py -v
```

Expected: all pass.

- [ ] **Step 2: Replace the simulated.py implementation**

Replace the full contents of `skill_eval/simulated.py`:

```python
"""Deterministic simulated components for Phase A walking skeleton.

These make no API calls. They exercise the real workflow shape so the orchestrator,
sandbox, and live UI all behave as they will in Phase B — just without LLM cost.

Scoring is deterministic via sha256 of (task_brief, arm, criterion) so different
tasks and criteria yield different scores, with a small challenger bias on average.
"""

import hashlib
from pathlib import Path

from skill_eval import git_ops
from skill_eval.contracts import (
    Arm,
    AskFn,
    JudgeInput,
    JudgeScore,
    RunConfig,
    RunMetrics,
    StopReason,
    TakerResult,
    Workspace,
)

# ---------------------------------------------------------------------------
# Deterministic hash helper
# ---------------------------------------------------------------------------


def _stable_hash_int(text: str) -> int:
    """Return a stable integer hash of *text* using sha256 (not Python's hash())."""
    return int(hashlib.sha256(text.encode()).hexdigest(), 16)


# ---------------------------------------------------------------------------
# Simulator (Component 3 stand-in)
# ---------------------------------------------------------------------------

_CANNED_ANSWERS = [
    "Yes, the function should return the correct result as described in the task.",
    "Correct — the implementation has the bug described; fix it as specified.",
    "The fix is straightforward: apply the change described in the task brief.",
    "You are on the right track. The expected behaviour matches the task brief.",
    "The test asserts the correct value; implement the function accordingly.",
]


def sim_make_simulator(after_dir: str, task_brief: str, model: str) -> AskFn:
    """Return a canned AskFn that gives helpful, deterministic answers."""
    call_count = [0]

    def ask(question: str) -> str:
        idx = call_count[0] % len(_CANNED_ANSWERS)
        call_count[0] += 1
        # Vary by question length to look slightly dynamic
        variant = _CANNED_ANSWERS[(idx + len(question)) % len(_CANNED_ANSWERS)]
        return variant

    return ask


# ---------------------------------------------------------------------------
# Taker (Component 2 stand-in)
# ---------------------------------------------------------------------------

_CLARIFYING_QUESTIONS = [
    "Can you confirm the expected return value for the function under test?",
    "Is there a specific edge case I should handle beyond the failing test?",
    "Should I preserve the existing function signature exactly?",
    "Are there any performance constraints I should be aware of?",
]


def sim_run_taker(
    ws: Workspace,
    model: str,
    skill_path: str,
    cfg: RunConfig,
    ask_fn: AskFn,
) -> TakerResult:
    """Simulate a taker: ask clarifying questions, write a marker, return result."""
    is_challenger = ws.arm is Arm.CHALLENGER

    # Derive a task-specific seed from the brief so per-case metrics differ
    task_seed = _stable_hash_int(cfg.task_brief)

    # Number of questions: challenger asks 2-4, baseline asks 1-2 (task-dependent)
    if is_challenger:
        num_q = 2 + (task_seed % 3)  # 2, 3, or 4
    else:
        num_q = 1 + (task_seed % 2)  # 1 or 2

    questions_asked: list[str] = []
    for i in range(num_q):
        q = _CLARIFYING_QUESTIONS[i % len(_CLARIFYING_QUESTIONS)]
        ask_fn(q)
        questions_asked.append(q)

    # Write a small marker change into the worktree so diff is non-empty.
    # Find the first .py file (excluding test files) and append a comment,
    # or fall back to writing a SOLUTION_NOTES.md.
    taker_path = Path(ws.taker_dir)
    py_files = sorted(
        f for f in taker_path.glob("*.py") if not f.name.startswith("test_")
    )
    if py_files:
        target = py_files[0]
        arm_label = ws.arm.value
        brief_snippet = cfg.task_brief[:40].replace("\n", " ")
        target.write_text(
            target.read_text() + f"\n# [simulated {arm_label}] {brief_snippet}\n"
        )
    else:
        (taker_path / "SOLUTION_NOTES.md").write_text(
            f"# Solution Notes\n\nArm: {ws.arm.value}\nTask: {cfg.task_brief[:80]}\n"
        )

    # Compute actual git diff of what the taker changed
    try:
        diff = git_ops.diff_workdir(ws.taker_dir)
    except Exception:  # noqa: BLE001
        diff = f"+ # [simulated {ws.arm.value}]"

    # Seed metrics deterministically from task + arm so per-case values differ.
    # Use the lower bits of the hash for token/turn ranges.
    arm_offset = 100 if is_challenger else 0
    base_tokens = 200 + (task_seed % 200) + arm_offset  # 200-499
    input_frac = 55 + (task_seed % 20)  # 55-74% of total are input tokens
    input_tokens = base_tokens * input_frac // 100
    output_tokens = base_tokens - input_tokens
    num_turns = 3 + (task_seed % 4) + (1 if is_challenger else 0)  # 3-7 turns
    wall_secs = 0.1 + (task_seed % 50) / 100.0 + (0.05 if is_challenger else 0.0)

    metrics = RunMetrics(
        total_tokens=base_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        wall_seconds=round(wall_secs, 3),
        num_turns=num_turns,
        num_questions=len(questions_asked),
    )

    transcript: tuple[dict, ...] = (
        {"role": "user", "content": cfg.task_brief},
        {
            "role": "assistant",
            "content": f"I'll implement the fix. Questions asked: {len(questions_asked)}",
        },
    )

    return TakerResult(
        arm=ws.arm,
        model=model,
        diff=diff,
        transcript=transcript,
        questions=tuple(questions_asked),
        stop_reason=StopReason.COMPLETED,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Judge (Component 5 stand-in)
# ---------------------------------------------------------------------------

# The score for each (task_brief, arm, criterion) is:
#   base = 8 + hash(...) % 12          → band [8, 19]
#   challenger_boost = 1 + hash2 % 3   → +1, +2, or +3 on average
#   but we only apply boost ~70% of the time (hash3 % 10 >= 3)
#   final = clamp(base + boost_if_applied, 0, 20)
#
# This gives challenger a ~+1.4 average advantage while ensuring baseline
# wins a meaningful number of per-(case, criterion) comparisons.

_BOOST_APPLY_THRESHOLD = 3  # hash % 10 >= this → apply boost (7 out of 10 times)


def sim_run_judge(ji: JudgeInput, model: str) -> JudgeScore:
    """Return a deterministic 0-20 score for one criterion using sha256-based hash."""
    criterion_key = ji.criterion.value
    arm_value = ji.taker.arm.value
    brief = ji.task_brief

    # Primary hash: base score in [8, 19]
    h1 = _stable_hash_int(f"{brief}|{arm_value}|{criterion_key}|base")
    base = 8 + (h1 % 12)

    # Challenger boost
    if ji.taker.arm is Arm.CHALLENGER:
        h2 = _stable_hash_int(f"{brief}|{criterion_key}|boost_magnitude")
        boost_magnitude = 1 + (h2 % 3)  # 1, 2, or 3
        h3 = _stable_hash_int(f"{brief}|{criterion_key}|boost_apply")
        apply_boost = (h3 % 10) >= _BOOST_APPLY_THRESHOLD
        score = min(20, base + (boost_magnitude if apply_boost else 0))
    else:
        score = base

    rationale = (
        f"[simulated] {criterion_key}: arm={arm_value}, score={score}/20"
    )

    return JudgeScore(criterion=ji.criterion, score=score, rationale=rationale)
```

- [ ] **Step 3: Run existing simulated and orchestrator tests to verify they still pass**

```bash
cd /Users/Ben/code/learning/skill-eval && uv run pytest tests/test_simulated.py tests/test_orchestrator.py -v
```

Expected: all pass (score still in [0,20], num_questions >= 1, 12 scores, both arms).

Note: The `test_sim_judge_scores_in_range` test passes a diff of `"+ return a + b"` but the new judge no longer checks for that string — it uses a hash of `task_brief`. The score will still be in [0, 20] so the test passes unchanged.

- [ ] **Step 4: Commit**

```bash
git add skill_eval/simulated.py
git commit -m "refactor: generalize simulated scoring with sha256 hash-based per-case variance"
```

---

### Task 3: Create `skill_eval/batch.py`

**Files:**
- Create: `skill_eval/batch.py`

- [ ] **Step 1: Write the failing test first**

Create `tests/test_batch.py`:

```python
from skill_eval.batch import run_batch
from skill_eval.contracts import Arm, ComparisonReport, Criterion
from skill_eval.sample_cases import build_sample_cases
from skill_eval.simulated import sim_make_simulator, sim_run_judge, sim_run_taker


def test_run_batch_returns_3_reports(tmp_path):
    cfgs = build_sample_cases(str(tmp_path))[:3]
    reports = run_batch(
        cfgs,
        taker_fn=sim_run_taker,
        simulator_factory=sim_make_simulator,
        judge_fn=sim_run_judge,
        max_cases=2,
    )
    assert len(reports) == 3
    for r in reports:
        assert isinstance(r, ComparisonReport)


def test_run_batch_arms_and_scores(tmp_path):
    cfgs = build_sample_cases(str(tmp_path))[:3]
    reports = run_batch(
        cfgs,
        taker_fn=sim_run_taker,
        simulator_factory=sim_make_simulator,
        judge_fn=sim_run_judge,
        max_cases=2,
    )
    for report in reports:
        arms = {a.arm for a in report.arms}
        assert arms == {Arm.BASELINE, Arm.CHALLENGER}
        for arm_report in report.arms:
            assert len(arm_report.scores) == len(list(Criterion))


def test_run_batch_per_case_variance(tmp_path):
    """Challenger total scores must not all be identical across 3 cases."""
    cfgs = build_sample_cases(str(tmp_path))[:3]
    reports = run_batch(
        cfgs,
        taker_fn=sim_run_taker,
        simulator_factory=sim_make_simulator,
        judge_fn=sim_run_judge,
        max_cases=2,
    )
    challenger_totals = [
        a.total_score for r in reports for a in r.arms if a.arm is Arm.CHALLENGER
    ]
    assert len(set(challenger_totals)) > 1, (
        f"All challenger totals identical: {challenger_totals}"
    )


def test_run_batch_on_event(tmp_path):
    """on_event callback receives events tagged with case index."""
    cfgs = build_sample_cases(str(tmp_path))[:2]
    events = []
    run_batch(
        cfgs,
        taker_fn=sim_run_taker,
        simulator_factory=sim_make_simulator,
        judge_fn=sim_run_judge,
        max_cases=2,
        on_event=events.append,
    )
    assert events, "no events emitted"
    case_indices = {e.get("case") for e in events}
    assert case_indices == {0, 1}, f"expected case indices 0 and 1, got {case_indices}"


def test_run_batch_preserves_order(tmp_path):
    """Output order must match input order regardless of execution order."""
    cfgs = build_sample_cases(str(tmp_path))[:3]
    reports = run_batch(
        cfgs,
        taker_fn=sim_run_taker,
        simulator_factory=sim_make_simulator,
        judge_fn=sim_run_judge,
        max_cases=3,
    )
    for i, (cfg, report) in enumerate(zip(cfgs, reports)):
        assert report.config.repo_path == cfg.repo_path, (
            f"Position {i}: expected {cfg.repo_path}, got {report.config.repo_path}"
        )
```

- [ ] **Step 2: Run the test to verify it fails (import error)**

```bash
cd /Users/Ben/code/learning/skill-eval && uv run pytest tests/test_batch.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'skill_eval.batch'`

- [ ] **Step 3: Implement `skill_eval/batch.py`**

```python
"""Concurrent batch runner for skill-eval.

Runs multiple RunConfigs through run_eval concurrently using a thread pool
(run_eval is synchronous — threads, not asyncio). Output order matches input order.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from skill_eval.contracts import (
    ComparisonReport,
    EventFn,
    JudgeFn,
    MakeSimulator,
    RunConfig,
    TakerFn,
)
from skill_eval.orchestrator import run_eval


def run_batch(
    cfgs: list[RunConfig],
    *,
    taker_fn: TakerFn | None = None,
    simulator_factory: MakeSimulator | None = None,
    judge_fn: JudgeFn | None = None,
    max_cases: int = 4,
    on_event: EventFn | None = None,
) -> list[ComparisonReport]:
    """Run *cfgs* through run_eval concurrently; return reports in input order.

    Args:
        cfgs: List of RunConfig objects to evaluate.
        taker_fn: Injected taker (None → real taker, Phase B).
        simulator_factory: Injected simulator factory (None → real, Phase B).
        judge_fn: Injected judge (None → real judge, Phase B).
        max_cases: Maximum concurrent evals (ThreadPoolExecutor max_workers).
        on_event: Optional callback; receives every run_eval event enriched with
            a ``"case"`` key (the 0-based index of the config in *cfgs*).

    Returns:
        List of ComparisonReport in the same order as *cfgs*.
    """
    results: dict[int, ComparisonReport] = {}

    def _run_one(i: int, cfg: RunConfig) -> tuple[int, ComparisonReport]:
        def _wrapped_event(ev: dict[str, Any]) -> None:
            if on_event is not None:
                on_event({**ev, "case": i})

        report = run_eval(
            cfg,
            taker_fn=taker_fn,
            simulator_factory=simulator_factory,
            judge_fn=judge_fn,
            on_event=_wrapped_event if on_event is not None else None,
        )
        return i, report

    with ThreadPoolExecutor(max_workers=max_cases) as executor:
        futures = {executor.submit(_run_one, i, cfg): i for i, cfg in enumerate(cfgs)}
        for future in as_completed(futures):
            i, report = future.result()  # re-raises any exception from the thread
            results[i] = report

    return [results[i] for i in range(len(cfgs))]
```

- [ ] **Step 4: Run batch tests**

```bash
cd /Users/Ben/code/learning/skill-eval && uv run pytest tests/test_batch.py -v
```

Expected: 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add skill_eval/batch.py tests/test_batch.py
git commit -m "feat: concurrent batch runner in batch.py"
```

---

### Task 4: Run `just check` and fix any lint/type/test issues

**Files:**
- Modify as needed: `skill_eval/batch.py`, `skill_eval/sample_cases.py`, `skill_eval/simulated.py`

- [ ] **Step 1: Run full check suite**

```bash
cd /Users/Ben/code/learning/skill-eval && uv run just check 2>&1
```

- [ ] **Step 2: Fix ruff format issues (if any)**

```bash
cd /Users/Ben/code/learning/skill-eval && uv run ruff format skill_eval/batch.py skill_eval/sample_cases.py skill_eval/simulated.py tests/test_sample_cases.py tests/test_batch.py
```

- [ ] **Step 3: Fix ruff lint issues (if any)**

```bash
cd /Users/Ben/code/learning/skill-eval && uv run ruff check skill_eval/batch.py skill_eval/sample_cases.py skill_eval/simulated.py tests/test_sample_cases.py tests/test_batch.py --fix
```

- [ ] **Step 4: Fix mypy issues (if any)**

Run mypy focused on skill_eval only (mypy config targets `skill_eval/` dir):

```bash
cd /Users/Ben/code/learning/skill-eval && uv run mypy 2>&1
```

- [ ] **Step 5: Run all tests to confirm green**

```bash
cd /Users/Ben/code/learning/skill-eval && uv run pytest -v 2>&1 | tail -30
```

- [ ] **Step 6: Final squash commit if needed**

```bash
git add skill_eval/batch.py skill_eval/sample_cases.py skill_eval/simulated.py tests/test_sample_cases.py tests/test_batch.py
git commit -m "feat: 10 sample test cases + concurrent batch runner; generalize simulated scoring"
```

---

## Self-Review

**Spec coverage check:**

| Requirement | Task |
|-------------|------|
| `build_sample_cases` returns 10 RunConfigs | Task 1 |
| Each case: before/after commits, test file | Task 1 |
| Skill dirs at `.claude/skills/baseline/SKILL.md` | Task 1 |
| `sim_run_judge`: sha256-based, 8-19 band, challenger +1..+3 bias, clamp [0,20] | Task 2 |
| `sim_run_taker`: ≥1 question, deterministic metrics, non-empty diff | Task 2 |
| Existing tests still pass | Task 2 |
| `run_batch` with ThreadPoolExecutor, preserves order | Task 3 |
| `on_event` tagged with `"case"` index | Task 3 |
| `test_sample_cases.py`: 10 configs, distinct paths, commits exist, skills exist | Task 1 |
| `test_batch.py`: 3 reports, 2 arms, 6 scores each, variance, order | Task 3 |
| `just check` green | Task 4 |
| Commit with correct message | Task 4 |

**Placeholder scan:** No TODOs or TBDs in plan. All code blocks are complete.

**Type consistency:**
- `build_sample_cases(base_dir: str) -> list[RunConfig]` — matches spec
- `run_batch(cfgs, *, taker_fn, simulator_factory, judge_fn, max_cases, on_event) -> list[ComparisonReport]` — matches spec
- `sim_run_judge(ji: JudgeInput, model: str) -> JudgeScore` — unchanged signature
- `sim_run_taker(ws, model, skill_path, cfg, ask_fn) -> TakerResult` — unchanged signature
