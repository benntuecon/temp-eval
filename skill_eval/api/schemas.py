"""Request/response models for the skill-eval HTTP API."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from skill_eval.contracts import ComparisonReport


class SkillInput(BaseModel):
    """One skill under test: a display name and its SKILL.md body."""

    name: str = Field(min_length=1, max_length=80)
    markdown: str = Field(min_length=1)

    @field_validator("markdown")
    @classmethod
    def _markdown_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("skill markdown must not be blank")
        return v


class CreateRunRequest(BaseModel):
    """Everything needed to race two skills on a task fixture."""

    fixture: str = "flagship"  # fixture id from GET /api/fixtures
    task_brief: str = Field(min_length=1)
    baseline: SkillInput
    challenger: SkillInput
    max_turns: int = Field(default=30, ge=1, le=100)
    thinking_budget: int | None = Field(default=2048, ge=0, le=32000)
    wall_clock_seconds: int | None = Field(default=None, ge=10, le=3600)
    judge_model: str | None = None
    judges_per_criterion: int = Field(default=1, ge=1, le=5)
    real_agents: bool = False  # False = free simulated components

    @field_validator("task_brief")
    @classmethod
    def _brief_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("task brief must not be blank")
        return v


class RunSummary(BaseModel):
    """Lightweight run listing entry (live or archived)."""

    run_id: str
    status: str  # running | completed | failed
    created_at: float  # epoch seconds
    label: str = ""
    verdict: str | None = None


class RunDetail(BaseModel):
    """Full run state: summary plus the report once available."""

    summary: RunSummary
    report: ComparisonReport | None = None


class FixtureInfo(BaseModel):
    """A selectable task fixture with its default brief and skills."""

    id: str
    label: str
    brief: str
    default_baseline: SkillInput
    default_challenger: SkillInput


class HealthInfo(BaseModel):
    """Service health."""

    status: str = "ok"


# ---------------------------------------------------------------------------
# Batch eval: retrieve K test cases for a query, run them all, aggregate
# ---------------------------------------------------------------------------


class RetrievedCase(BaseModel):
    """One retriever hit, normalised to a runnable testcase fixture."""

    case_id: str
    fixture: str  # "testcase:<case_id>" — feed straight into a run
    description: str
    distance: float | None = None  # vector distance; None = keyword fallback


class CreateBatchRequest(BaseModel):
    """Retrieve top-k cases for *query* and eval the skill pair on each."""

    query: str = Field(min_length=1)
    top_k: int = Field(default=10, ge=1, le=50)
    # Explicit case selection: when set (e.g. after the user pruned the
    # retrieval preview), the batch runs exactly these cases in this order
    # instead of re-retrieving for the query.
    case_ids: list[str] | None = Field(default=None, max_length=50)
    # Optional overrides; when omitted the server uses the logging skill pair.
    baseline: SkillInput | None = None
    challenger: SkillInput | None = None
    max_turns: int = Field(default=16, ge=1, le=100)
    thinking_budget: int | None = Field(default=2048, ge=0, le=32000)
    # Hard per-run elapsed-time cap; takers stop with stop_reason=wall_clock.
    wall_clock_seconds: int | None = Field(default=180, ge=10, le=3600)
    judge_model: str | None = None
    judges_per_criterion: int = Field(default=1, ge=1, le=5)
    real_agents: bool = False
    # Cap on concurrently-running child evals; None = run all K at once.
    max_concurrent: int | None = Field(default=None, ge=1, le=50)

    @field_validator("query")
    @classmethod
    def _query_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("query must not be blank")
        return v


class BatchCaseState(BaseModel):
    """Live status of one retrieved case inside a batch."""

    case_id: str
    fixture: str
    description: str
    distance: float | None = None
    run_id: str | None = None
    status: str = "queued"  # queued | running | completed | failed
    verdict: str | None = None
    baseline_total: int | None = None
    challenger_total: int | None = None
    baseline_tokens: int | None = None
    challenger_tokens: int | None = None


class BatchSummary(BaseModel):
    """Lightweight batch listing entry."""

    batch_id: str
    query: str
    status: str  # running | completed | failed | interrupted (stale archive)
    created_at: float
    real_agents: bool = False
    total: int = 0
    completed: int = 0
    failed: int = 0


class BatchStats(BaseModel):
    """Aggregates over the batch's completed child reports."""

    win_summary: dict[str, int]  # {"challenger": n, "baseline": n, "tie": n}
    per_criterion_avg: list[dict]  # rows: {criterion, baseline, challenger}
    criterion_gap: list[dict]  # rows: {criterion, baseline, challenger, gap}
    per_case_totals: list[dict]  # rows: {case, baseline, challenger}
    score_distribution: list[dict]  # rows: {criterion, arm, score}
    tokens_per_case: list[dict]  # rows: {case, baseline, challenger}


class BatchCreated(BaseModel):
    batch_id: str


class BatchDetail(BaseModel):
    """Full batch state: summary, per-case statuses, and aggregate stats."""

    summary: BatchSummary
    cases: list[BatchCaseState]
    stats: BatchStats | None = None
