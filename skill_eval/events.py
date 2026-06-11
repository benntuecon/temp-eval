"""Typed, node-addressed run events — the live contract between backend and UI.

Every event names the architecture-graph ``node`` it belongs to, so the
frontend can accumulate per-node buffers and render "what is this agent
thinking right now" on hover. The union is discriminated on ``type``; the
schema is transport-agnostic (today SSE, WebSocket-compatible by design).

Node id convention (matches the pipeline graph):
``test_generator, sandbox, simulator, taker:<arm>, judge:<arm>:<criterion>,
assemble, report``.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter

from skill_eval.contracts import RunMetrics


class _Base(BaseModel):
    node: str = ""  # architecture-graph node id this event belongs to
    ts: float = 0.0  # epoch seconds, stamped by the emitter/manager


class RunStarted(_Base):
    type: Literal["run_started"] = "run_started"
    run_id: str
    label: str = ""


class StageChanged(_Base):
    type: Literal["stage_changed"] = "stage_changed"
    stage: str  # generator | sandbox | takers | judges | report
    status: str  # pending | running | done


class ThinkingDelta(_Base):
    type: Literal["thinking_delta"] = "thinking_delta"
    text: str


class ToolCallEvent(_Base):
    type: Literal["tool_call"] = "tool_call"
    tool: str
    summary: str = ""


class QuestionAsked(_Base):
    type: Literal["question_asked"] = "question_asked"
    question: str


class QuestionAnswered(_Base):
    type: Literal["question_answered"] = "question_answered"
    question: str
    answer: str


class TakerStatus(_Base):
    type: Literal["taker_status"] = "taker_status"
    arm: str
    status: str  # running | done
    stop_reason: str | None = None
    metrics: RunMetrics | None = None


class JudgeStatus(_Base):
    type: Literal["judge_status"] = "judge_status"
    arm: str
    criterion: str
    status: str  # running | done
    score: int | None = None
    rationale: str | None = None


class RunCompleted(_Base):
    type: Literal["run_completed"] = "run_completed"
    run_id: str
    verdict: str


class RunFailed(_Base):
    type: Literal["run_failed"] = "run_failed"
    run_id: str
    error: str


RunEvent = Annotated[
    RunStarted
    | StageChanged
    | ThinkingDelta
    | ToolCallEvent
    | QuestionAsked
    | QuestionAnswered
    | TakerStatus
    | JudgeStatus
    | RunCompleted
    | RunFailed,
    Field(discriminator="type"),
]

# Adapter for parsing arbitrary event JSON back into the right concrete type.
run_event_adapter: TypeAdapter[RunEvent] = TypeAdapter(RunEvent)


def parse_event(text: str) -> RunEvent:
    """Parse one JSON event into its concrete model (discriminated on type)."""
    return run_event_adapter.validate_json(text)


def dump_event(event: RunEvent) -> str:
    """Serialise one event to JSON."""
    return run_event_adapter.dump_json(event).decode()
