from unittest.mock import MagicMock, patch

import pytest

from skill_eval.contracts import Arm, Criterion, JudgeInput, RunMetrics, StopReason, TakerResult
from skill_eval.judge import _build_prompt, run_judge


def _ji(criterion=Criterion.CORRECTNESS, questions=()):
    m = RunMetrics(0, 0, 0, 0.0, 0, 0)
    t = TakerResult(
        Arm.CHALLENGER, "m", "+    return a + b", (), questions, StopReason.COMPLETED, m
    )
    return JudgeInput(criterion, "fix add", "+    return a + b", "/x", t)


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


# ---------------------------------------------------------------------------
# Pure unit tests for _build_prompt — NO API calls
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "criterion",
    [
        Criterion.CORRECTNESS,
        Criterion.COMPLETENESS,
        Criterion.DISTANCE_TO_GOLD,
        Criterion.CODE_QUALITY,
        Criterion.QUESTION_QUALITY,
        Criterion.APPROACH,
    ],
)
def test_build_prompt_contains_anchors(criterion):
    """Every criterion prompt must include all five anchor values 0/5/10/15/20."""
    ji = _ji(criterion=criterion)
    prompt = _build_prompt(ji)
    for anchor in ("0", "5", "10", "15", "20"):
        assert anchor in prompt, f"Anchor '{anchor}' missing from {criterion} prompt"


@pytest.mark.parametrize(
    "criterion",
    [
        Criterion.CORRECTNESS,
        Criterion.COMPLETENESS,
        Criterion.DISTANCE_TO_GOLD,
        Criterion.CODE_QUALITY,
        Criterion.QUESTION_QUALITY,
        Criterion.APPROACH,
    ],
)
def test_build_prompt_contains_criterion_name(criterion):
    """Each prompt must name the criterion being scored."""
    ji = _ji(criterion=criterion)
    prompt = _build_prompt(ji)
    assert criterion.value in prompt


def test_build_prompt_includes_taker_questions():
    """Taker questions must appear verbatim in the prompt."""
    questions = ("What is the month length?", "How to handle day 0?")
    ji = _ji(criterion=Criterion.QUESTION_QUALITY, questions=questions)
    prompt = _build_prompt(ji)
    for q in questions:
        assert q in prompt, f"Question '{q}' not found in prompt"


def test_build_prompt_no_questions_note():
    """When the taker asked nothing, the prompt should say so explicitly."""
    ji = _ji(criterion=Criterion.QUESTION_QUALITY, questions=())
    prompt = _build_prompt(ji)
    assert "NO clarifying questions" in prompt


def test_build_prompt_question_quality_anchor_phrase():
    """question_quality prompt must include a concrete anchor descriptor."""
    ji = _ji(criterion=Criterion.QUESTION_QUALITY)
    prompt = _build_prompt(ji)
    assert "asked nothing or irrelevant" in prompt
    assert "surfaced ALL critical ambiguities" in prompt


def test_build_prompt_correctness_anchor_phrase():
    """correctness prompt must include concrete anchor descriptors from the spec."""
    ji = _ji(criterion=Criterion.CORRECTNESS)
    prompt = _build_prompt(ji)
    assert "happy path only" in prompt
    assert "matches ALL gold behavior" in prompt


def test_build_prompt_blind_criteria_never_see_gold():
    """code_quality and approach are judged blind — the gold diff must not leak."""
    m = RunMetrics(0, 0, 0, 0.0, 0, 0)
    t = TakerResult(Arm.CHALLENGER, "m", "+ taker change", (), (), StopReason.COMPLETED, m)
    for criterion in (Criterion.CODE_QUALITY, Criterion.APPROACH):
        ji = JudgeInput(criterion, "fix add", "+ GOLD_SECRET_MARKER", "/x", t)
        prompt = _build_prompt(ji)
        assert "GOLD_SECRET_MARKER" not in prompt, f"gold leaked into {criterion} prompt"
        assert "withheld" in prompt


def test_build_prompt_gold_based_criteria_see_gold():
    """Criteria defined against the gold must still receive the gold diff."""
    m = RunMetrics(0, 0, 0, 0.0, 0, 0)
    t = TakerResult(Arm.CHALLENGER, "m", "+ taker change", (), (), StopReason.COMPLETED, m)
    for criterion in (
        Criterion.CORRECTNESS,
        Criterion.COMPLETENESS,
        Criterion.DISTANCE_TO_GOLD,
        Criterion.QUESTION_QUALITY,
    ):
        ji = JudgeInput(criterion, "fix add", "+ GOLD_SECRET_MARKER", "/x", t)
        assert "GOLD_SECRET_MARKER" in _build_prompt(ji)


@patch("skill_eval.judge.anthropic.Anthropic")
def test_run_judge_is_deterministic_temperature_zero(mock_cls):
    """Judging must request temperature=0 — graded verdicts may not be sampled."""
    msg = MagicMock()
    msg.content = [MagicMock(text='{"score": 10, "rationale": "x"}')]
    create = mock_cls.return_value.messages.create
    create.return_value = msg
    run_judge(_ji(), "claude-haiku-4-5")
    assert create.call_args.kwargs["temperature"] == 0


def test_build_prompt_question_quality_brief_vs_gold_instruction():
    """question_quality prompt must instruct the judge to derive ambiguities from brief vs gold."""
    ji = _ji(criterion=Criterion.QUESTION_QUALITY)
    prompt = _build_prompt(ji)
    assert "CRITICAL AMBIGUITIES" in prompt or "critical ambiguit" in prompt.lower()
    assert "gold" in prompt.lower()
    assert "task_brief" in prompt or "brief" in prompt.lower()


def test_build_prompt_contains_task_brief_and_diffs():
    """Prompt must embed the task brief, gold diff, and taker diff."""
    ji = _ji(criterion=Criterion.CORRECTNESS)
    prompt = _build_prompt(ji)
    assert ji.task_brief in prompt
    assert ji.gold_diff in prompt
    assert ji.taker.diff in prompt
