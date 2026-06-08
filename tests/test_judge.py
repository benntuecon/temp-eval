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
