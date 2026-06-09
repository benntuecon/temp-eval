"""Tests for skill_eval/taker.py — zero network calls.

Pure-helper unit tests use fake ResultMessage-like objects.
The integration test patches ``skill_eval.taker.query`` with an async
generator that yields a fake ResultMessage so ``run_taker`` can complete
without any real API call.
"""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from skill_eval.contracts import Arm, RunConfig, RunMetrics, StopReason, TakerResult, Workspace
from skill_eval.taker import _compute_diff, _metrics_from_result, _stop_reason

# ---------------------------------------------------------------------------
# Fake ResultMessage (no SDK import required)
# ---------------------------------------------------------------------------


class _FakeResult:
    """Minimal stand-in for claude_agent_sdk.ResultMessage."""

    _SENTINEL: dict[str, Any] = {}

    def __init__(
        self,
        num_turns: int = 3,
        stop_reason: str | None = "end_turn",
        usage: dict[str, Any] | None | type = _SENTINEL,
        is_error: bool = False,
        duration_ms: int = 1000,
    ) -> None:
        self.num_turns = num_turns
        self.stop_reason = stop_reason
        self.usage = (
            {"input_tokens": 100, "output_tokens": 50} if usage is _FakeResult._SENTINEL else usage
        )
        self.is_error = is_error
        self.duration_ms = duration_ms


# ---------------------------------------------------------------------------
# _metrics_from_result
# ---------------------------------------------------------------------------


def test_metrics_basic() -> None:
    msg = _FakeResult(num_turns=5, usage={"input_tokens": 200, "output_tokens": 80})
    m = _metrics_from_result(msg, num_questions=2, wall_seconds=3.5)  # type: ignore[arg-type]
    assert m.input_tokens == 200
    assert m.output_tokens == 80
    assert m.total_tokens == 280
    assert m.num_turns == 5
    assert m.num_questions == 2
    assert m.wall_seconds == pytest.approx(3.5)


def test_metrics_missing_usage() -> None:
    msg = _FakeResult(usage=None)
    m = _metrics_from_result(msg, num_questions=0, wall_seconds=1.0)  # type: ignore[arg-type]
    assert m.input_tokens == 0
    assert m.output_tokens == 0
    assert m.total_tokens == 0


def test_metrics_partial_usage() -> None:
    msg = _FakeResult(usage={"input_tokens": 50})  # output_tokens missing
    m = _metrics_from_result(msg, num_questions=0, wall_seconds=0.5)  # type: ignore[arg-type]
    assert m.input_tokens == 50
    assert m.output_tokens == 0
    assert m.total_tokens == 50


# ---------------------------------------------------------------------------
# _stop_reason
# ---------------------------------------------------------------------------


def test_stop_reason_timeout() -> None:
    assert _stop_reason(_FakeResult(2, "end_turn"), True, 30) is StopReason.WALL_CLOCK  # type: ignore[arg-type]


def test_stop_reason_max_turns() -> None:
    assert _stop_reason(_FakeResult(30, None), False, 30) is StopReason.MAX_TURNS  # type: ignore[arg-type]


def test_stop_reason_completed() -> None:
    assert _stop_reason(_FakeResult(3, "end_turn"), False, 30) is StopReason.COMPLETED  # type: ignore[arg-type]


def test_stop_reason_timeout_overrides_end_turn() -> None:
    """WALL_CLOCK takes priority even if stop_reason happens to be 'end_turn'."""
    assert _stop_reason(_FakeResult(3, "end_turn"), True, 30) is StopReason.WALL_CLOCK  # type: ignore[arg-type]


def test_stop_reason_max_turns_exact() -> None:
    """Exactly at max_turns threshold → MAX_TURNS."""
    assert _stop_reason(_FakeResult(10, "end_turn"), False, 10) is StopReason.MAX_TURNS  # type: ignore[arg-type]


def test_stop_reason_completed_below_max() -> None:
    """Below max_turns with end_turn → COMPLETED."""
    assert _stop_reason(_FakeResult(9, "end_turn"), False, 10) is StopReason.COMPLETED  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# _compute_diff
# ---------------------------------------------------------------------------


def _init_git_repo(path: str) -> None:
    """Create a minimal git repo with an initial commit."""
    subprocess.run(["git", "init", "-b", "main"], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=path, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=path, capture_output=True, check=True
    )
    # Initial commit so HEAD exists
    (pytest.importorskip("pathlib").Path(path) / "README.md").write_text("init\n")
    subprocess.run(["git", "add", "-A"], cwd=path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=path, capture_output=True, check=True)


def test_compute_diff_captures_new_file(tmp_path) -> None:
    _init_git_repo(str(tmp_path))
    (tmp_path / "solution.py").write_text("def solve():\n    pass\n")
    diff = _compute_diff(str(tmp_path), "HEAD")
    assert "solution.py" in diff
    assert "+def solve" in diff


def test_compute_diff_captures_modification(tmp_path) -> None:
    _init_git_repo(str(tmp_path))
    readme = tmp_path / "README.md"
    readme.write_text("updated content\n")
    diff = _compute_diff(str(tmp_path), "HEAD")
    assert "README.md" in diff


def test_compute_diff_empty_for_no_changes(tmp_path) -> None:
    _init_git_repo(str(tmp_path))
    # No changes after init → diff should be empty
    diff = _compute_diff(str(tmp_path), "HEAD")
    assert diff == ""


def test_compute_diff_non_git_dir(tmp_path) -> None:
    """Non-git directory should return empty string without raising."""
    diff = _compute_diff(str(tmp_path), "HEAD")
    assert diff == ""


def test_compute_diff_captures_committed_changes(tmp_path) -> None:
    """A skill that runs `git commit` must still have its work captured.

    Diffing vs HEAD would be empty after a commit; diffing vs the original
    `before_ref` captures it.
    """
    _init_git_repo(str(tmp_path))
    before = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(tmp_path), capture_output=True, text=True, check=True
    ).stdout.strip()
    (tmp_path / "solution.py").write_text("def solve():\n    return 42\n")
    subprocess.run(["git", "add", "-A"], cwd=str(tmp_path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "ship it"], cwd=str(tmp_path), capture_output=True, check=True
    )
    # HEAD moved to the new commit; diff vs HEAD is empty, but vs `before` captures it.
    assert _compute_diff(str(tmp_path), "HEAD") == ""
    diff = _compute_diff(str(tmp_path), before)
    assert "solution.py" in diff
    assert "+def solve" in diff


# ---------------------------------------------------------------------------
# Integration test: run_taker with patched query
# ---------------------------------------------------------------------------


def _make_workspace(tmp_path) -> Workspace:
    """Create a temp git repo and return a Workspace pointing at it."""
    _init_git_repo(str(tmp_path))
    return Workspace(
        arm=Arm.CHALLENGER,
        taker_dir=str(tmp_path),
        after_dir=str(tmp_path),
        gold_diff="+def add(a, b):\n+    return a + b\n",
    )


def _make_cfg() -> RunConfig:
    return RunConfig(
        # "HEAD" is a valid ref in the temp repo created by _make_workspace; the
        # taker leaves its work uncommitted, so diffing vs HEAD captures it.
        before_hash="HEAD",
        after_hash="def456",
        repo_path="/fake/repo",
        task_brief="Fix the add function to return a + b.",
        baseline_skill_path="/fake/baseline",
        challenger_skill_path="/fake/challenger",
        models=("claude-haiku-4-5",),
        max_turns=30,
        wall_clock_seconds=None,
    )


def _make_thinking_block(text: str) -> MagicMock:
    """Return a MagicMock that looks like a ThinkingBlock to type(block).__name__."""
    block = MagicMock()
    block.__class__.__name__ = "ThinkingBlock"
    block.thinking = text
    return block


async def _fake_query_gen(*, prompt: str, options: Any):
    """Async generator that yields a fake AssistantMessage with a ThinkingBlock,
    then a fake ResultMessage."""
    from claude_agent_sdk import ResultMessage

    # Yield a fake message whose content includes a ThinkingBlock
    fake_thinking_block = _make_thinking_block("I am thinking about this problem...")
    fake_assistant_msg = MagicMock()
    fake_assistant_msg.__class__.__name__ = "AssistantMessage"
    fake_assistant_msg.content = [fake_thinking_block]
    yield fake_assistant_msg

    # Yield a real ResultMessage so run_taker gets correct type-checking.
    fake = MagicMock(spec=ResultMessage)
    fake.num_turns = 3
    fake.stop_reason = "end_turn"
    fake.is_error = False
    fake.usage = {"input_tokens": 120, "output_tokens": 60}
    fake.duration_ms = 2000
    # Make isinstance checks work
    fake.__class__ = ResultMessage
    yield fake


def test_run_taker_mocked(tmp_path) -> None:
    """run_taker returns a populated TakerResult with patched query."""
    ws = _make_workspace(tmp_path)
    cfg = _make_cfg()

    # Write a tiny file so the diff is non-empty
    (tmp_path / "solution.py").write_text("def add(a, b):\n    return a + b\n")

    ask_calls: list[str] = []

    def _ask(question: str) -> str:
        ask_calls.append(question)
        return "Use PostgreSQL."

    with patch("skill_eval.taker.query", side_effect=_fake_query_gen):
        from skill_eval.taker import run_taker

        result = run_taker(ws, "claude-haiku-4-5", "/fake/skill", cfg, _ask)

    assert isinstance(result, TakerResult)
    assert result.arm is Arm.CHALLENGER
    assert result.model == "claude-haiku-4-5"
    # Diff should contain the new file
    assert "solution.py" in result.diff
    # stop_reason populated
    assert result.stop_reason in StopReason.__members__.values()
    # metrics populated from the fake ResultMessage
    assert isinstance(result.metrics, RunMetrics)
    assert result.metrics.input_tokens == 120
    assert result.metrics.output_tokens == 60
    assert result.metrics.total_tokens == 180
    assert result.metrics.num_turns == 3
    # transcript is a tuple (possibly empty if ResultMessage consumed exclusively)
    assert isinstance(result.transcript, tuple)
    assert isinstance(result.questions, tuple)
    # ThinkingBlock yielded by the fake stream should appear in transcript
    thinking_entries = [e for e in result.transcript if e.get("role") == "thinking"]
    assert len(thinking_entries) >= 1
    assert "thinking about this problem" in thinking_entries[0]["content"]


def test_run_taker_with_skill_md(tmp_path) -> None:
    """SKILL.md is injected into the system_prompt (Approach B)."""
    ws = _make_workspace(tmp_path)
    cfg = _make_cfg()

    # Create a skill directory with a SKILL.md
    skill_dir = tmp_path / "myskill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text("## My Skill\nAlways write clean code.\n")

    captured_options: list[Any] = []

    async def _recording_gen(*, prompt: str, options: Any):
        captured_options.append(options)
        from claude_agent_sdk import ResultMessage

        fake = MagicMock(spec=ResultMessage)
        fake.num_turns = 1
        fake.stop_reason = "end_turn"
        fake.is_error = False
        fake.usage = {"input_tokens": 10, "output_tokens": 5}
        fake.duration_ms = 500
        fake.__class__ = ResultMessage
        yield fake

    with patch("skill_eval.taker.query", side_effect=_recording_gen):
        from skill_eval.taker import run_taker

        run_taker(ws, "claude-haiku-4-5", str(skill_dir), cfg, lambda q: "yes")

    assert captured_options, "options should have been captured"
    opts = captured_options[0]
    assert "My Skill" in (opts.system_prompt or "")
    assert "Always write clean code" in (opts.system_prompt or "")


def test_run_taker_missing_skill_md(tmp_path) -> None:
    """Missing SKILL.md should not raise — system_prompt uses empty skill."""
    ws = _make_workspace(tmp_path)
    cfg = _make_cfg()

    async def _gen(*, prompt: str, options: Any):
        from claude_agent_sdk import ResultMessage

        fake = MagicMock(spec=ResultMessage)
        fake.num_turns = 1
        fake.stop_reason = "end_turn"
        fake.is_error = False
        fake.usage = {"input_tokens": 5, "output_tokens": 2}
        fake.duration_ms = 200
        fake.__class__ = ResultMessage
        yield fake

    with patch("skill_eval.taker.query", side_effect=_gen):
        from skill_eval.taker import run_taker

        result = run_taker(
            ws, "claude-haiku-4-5", str(tmp_path / "nonexistent"), cfg, lambda q: "x"
        )

    assert isinstance(result, TakerResult)


def test_run_taker_thinking_budget_sets_option(tmp_path) -> None:
    """When thinking_budget is set in cfg, the options include a thinking dict."""
    ws = _make_workspace(tmp_path)
    cfg = RunConfig(
        before_hash="HEAD",
        after_hash="def456",
        repo_path="/fake/repo",
        task_brief="Fix the add function.",
        baseline_skill_path="/fake/baseline",
        challenger_skill_path="/fake/challenger",
        models=("claude-haiku-4-5",),
        max_turns=30,
        thinking_budget=2048,
    )

    captured_options: list[Any] = []

    async def _recording_gen(*, prompt: str, options: Any):
        captured_options.append(options)
        from claude_agent_sdk import ResultMessage

        fake = MagicMock(spec=ResultMessage)
        fake.num_turns = 1
        fake.stop_reason = "end_turn"
        fake.is_error = False
        fake.usage = {"input_tokens": 10, "output_tokens": 5}
        fake.duration_ms = 500
        fake.__class__ = ResultMessage
        yield fake

    with patch("skill_eval.taker.query", side_effect=_recording_gen):
        from skill_eval.taker import run_taker

        run_taker(ws, "claude-haiku-4-5", "/fake/skill", cfg, lambda q: "yes")

    assert captured_options, "options should have been captured"
    opts = captured_options[0]
    assert hasattr(opts, "thinking"), "thinking attribute should be present"
    assert opts.thinking == {"type": "enabled", "budget_tokens": 2048}


def test_run_taker_no_thinking_without_budget(tmp_path) -> None:
    """When thinking_budget is None, options should NOT include thinking."""
    ws = _make_workspace(tmp_path)
    cfg = _make_cfg()  # thinking_budget defaults to None

    captured_options: list[Any] = []

    async def _recording_gen(*, prompt: str, options: Any):
        captured_options.append(options)
        from claude_agent_sdk import ResultMessage

        fake = MagicMock(spec=ResultMessage)
        fake.num_turns = 1
        fake.stop_reason = "end_turn"
        fake.is_error = False
        fake.usage = {"input_tokens": 10, "output_tokens": 5}
        fake.duration_ms = 500
        fake.__class__ = ResultMessage
        yield fake

    with patch("skill_eval.taker.query", side_effect=_recording_gen):
        from skill_eval.taker import run_taker

        run_taker(ws, "claude-haiku-4-5", "/fake/skill", cfg, lambda q: "yes")

    assert captured_options, "options should have been captured"
    opts = captured_options[0]
    # thinking should not be set (None or absent) when budget is not configured
    thinking_val = getattr(opts, "thinking", None)
    assert thinking_val is None or thinking_val == {}, (
        f"expected no thinking when budget is None, got: {thinking_val}"
    )
