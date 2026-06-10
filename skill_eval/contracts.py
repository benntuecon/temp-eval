"""Shared data contracts for the skill-eval harness.

This is the single integration point every component builds against. It contains
only types and function signatures — no business logic. See the design spec §6.
"""

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

# ---------- Enums ----------


class Arm(StrEnum):
    """Which skill a test-taker is running."""

    BASELINE = "baseline"
    CHALLENGER = "challenger"


class StopReason(StrEnum):
    """Why a test-taker run ended."""

    COMPLETED = "completed"
    MAX_TURNS = "max_turns"
    MAX_TOKENS = "max_tokens"
    WALL_CLOCK = "wall_clock"
    ERROR = "error"


class Criterion(StrEnum):
    """One judged dimension. Each becomes its own concurrent judge."""

    CORRECTNESS = "correctness"  # satisfies the requirement (vs gold)
    COMPLETENESS = "completeness"  # how much of the task got done
    DISTANCE_TO_GOLD = "distance_to_gold"  # semantic closeness of diff to gold diff
    CODE_QUALITY = "code_quality"  # maintainability / idiomaticity
    QUESTION_QUALITY = "question_quality"  # quality of clarifying questions asked
    APPROACH = "approach"  # strategy / efficiency / lack of thrashing


# ---------- Inputs ----------


@dataclass(frozen=True)
class RunConfig:
    """The eval's input: commits, task, skills, and the test budget."""

    before_hash: str
    after_hash: str
    repo_path: str
    task_brief: str  # PRD / Jira story / requirement text
    baseline_skill_path: str  # path to baseline skill dir
    challenger_skill_path: str  # path to challenger skill dir
    models: tuple[str, ...]  # one full eval per model
    max_turns: int = 30
    max_tokens: int | None = None  # optional hard token cap
    wall_clock_seconds: int | None = None  # real elapsed-time cap
    thinking_budget: int | None = None  # token budget for extended thinking (None = disabled)
    judge_model: str | None = None  # decouple judge from taker model (None = taker model)
    judges_per_criterion: int = 1  # k replicate judges per (arm, criterion); median wins


# ---------- Sandbox (Component 1) ----------


@dataclass(frozen=True)
class Workspace:
    """Isolated dirs for one arm plus the shared gold tree."""

    arm: Arm
    taker_dir: str  # worktree @before_hash the taker edits
    after_dir: str  # read-only worktree @after_hash (gold tree)
    gold_diff: str  # `git diff before..after`


# ---------- Metrics (Component 4) ----------


@dataclass(frozen=True)
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


@dataclass(frozen=True)
class TakerResult:
    """Everything one taker produced, ready for judging."""

    arm: Arm
    model: str
    diff: str  # patch: before_hash -> taker end state
    transcript: tuple[dict, ...]  # full message log
    questions: tuple[str, ...]  # clarifying questions the taker asked
    stop_reason: StopReason
    metrics: RunMetrics
    qa: tuple[tuple[str, str], ...] = ()  # (question, simulator answer) pairs


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
    score: int  # 0-20, anchored
    rationale: str


# ---------- Final report (Component 7) ----------


@dataclass
class ArmReport:
    """Aggregated result for one arm (one model)."""

    arm: Arm
    model: str
    metrics: RunMetrics
    scores: list[JudgeScore]
    total_score: int  # sum of criterion scores (or weighted)
    questions: tuple[str, ...] = ()  # clarifying questions the arm's taker asked
    diff: str = ""  # the patch the taker actually produced
    stop_reason: str = ""  # StopReason value of the taker run
    qa: tuple[tuple[str, str], ...] = ()  # (question, simulator answer) pairs


@dataclass
class ComparisonReport:
    """The system's output: baseline vs challenger, per model."""

    config: RunConfig
    arms: list[ArmReport]  # baseline + challenger, per model
    pairwise_verdict: str  # which is better and why
    gold_diff: str = ""  # the reference before..after diff (same for both arms)
    session_id: str = ""  # Phoenix session id grouping every span of this run


# ---------- Orchestrator injection points (Phase A walking skeleton) ----------

TakerFn = Callable[[Workspace, str, str, RunConfig, AskFn], TakerResult]
JudgeFn = Callable[[JudgeInput, str], JudgeScore]
# Live-progress event sink. Event is a free-form dict: {"stage", "arm"?, "msg", ...}.
Event = dict
EventFn = Callable[[Event], None]


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
