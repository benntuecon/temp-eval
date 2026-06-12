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
