"""Unit tests for the typed event union and API schemas."""

import pytest
from pydantic import ValidationError

from skill_eval.api.schemas import CreateRunRequest, SkillInput
from skill_eval.events import (
    JudgeStatus,
    RunCompleted,
    ThinkingDelta,
    dump_event,
    parse_event,
)


def test_event_round_trip_discriminated():
    ev = ThinkingDelta(node="taker:baseline", ts=123.0, text="reading refund.py…")
    back = parse_event(dump_event(ev))
    assert isinstance(back, ThinkingDelta)
    assert back == ev


def test_parse_event_picks_concrete_type_from_json():
    raw = (
        '{"type": "judge_status", "node": "judge:challenger:correctness",'
        ' "ts": 1.0, "arm": "challenger", "criterion": "correctness",'
        ' "status": "done", "score": 18, "rationale": "matches gold"}'
    )
    ev = parse_event(raw)
    assert isinstance(ev, JudgeStatus)
    assert ev.score == 18 and ev.rationale == "matches gold"


def test_parse_event_unknown_type_rejected():
    with pytest.raises(ValidationError):
        parse_event('{"type": "not_a_real_event", "node": "x", "ts": 0}')


def test_run_completed_event():
    ev = parse_event('{"type": "run_completed", "run_id": "r1", "verdict": "tie"}')
    assert isinstance(ev, RunCompleted)
    assert ev.node == "" and ev.ts == 0.0  # defaults


def test_create_run_request_validates_blank_fields():
    ok = CreateRunRequest(
        task_brief="fix it",
        baseline=SkillInput(name="a", markdown="# a"),
        challenger=SkillInput(name="b", markdown="# b"),
    )
    assert ok.judges_per_criterion == 1

    with pytest.raises(ValidationError):
        CreateRunRequest(
            task_brief="   ",
            baseline=SkillInput(name="a", markdown="# a"),
            challenger=SkillInput(name="b", markdown="# b"),
        )
    with pytest.raises(ValidationError):
        SkillInput(name="a", markdown="   ")
    with pytest.raises(ValidationError):
        CreateRunRequest(
            task_brief="x",
            baseline=SkillInput(name="a", markdown="# a"),
            challenger=SkillInput(name="b", markdown="# b"),
            judges_per_criterion=99,
        )
