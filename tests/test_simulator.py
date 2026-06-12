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


@patch("skill_eval.simulator.anthropic.Anthropic")
def test_make_simulator_deterministic_settings(mock_cls, tmp_path):
    """The stakeholder call pins temperature=0 and includes the gold context."""
    (tmp_path / "calculator.py").write_text("def add(a, b):\n    return a + b\n")
    msg = MagicMock()
    msg.content = [MagicMock(text="Use Decimal with ROUND_HALF_UP.")]
    mock_cls.return_value.messages.create.return_value = msg

    ask = make_simulator(str(tmp_path), "Prorate the refund.", "claude-haiku-4-5")
    answer = ask("How should rounding work?")

    assert "Decimal" in answer
    _, kwargs = mock_cls.return_value.messages.create.call_args
    assert kwargs["temperature"] == 0
    assert "Prorate the refund." in kwargs["system"]
    assert "calculator.py" in kwargs["system"]
    assert kwargs["messages"] == [{"role": "user", "content": "How should rounding work?"}]
