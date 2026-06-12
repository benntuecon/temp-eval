"""Batch eval execution: retrieve K cases for a query, run each as a child run.

A batch owns no agent plumbing of its own — every retrieved case becomes a
normal RunManager child run (fixture ``testcase:<id>``), so each case gets the
full event stream / History treatment for free. The batch layer adds:

- retrieval (vector DB with keyword fallback) at start time,
- a concurrency gate so K real-agent evals don't fork-bomb the host,
- aggregate stats over the completed child reports.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from skill_eval.api.run_manager import RunManager
from skill_eval.api.schemas import (
    BatchCaseState,
    BatchDetail,
    BatchStats,
    BatchSummary,
    CreateBatchRequest,
    CreateRunRequest,
    SkillInput,
)
from skill_eval.contracts import Arm, ComparisonReport
from skill_eval.retriever import retrieve_cases
from skill_eval.testcase_fixture import BASELINE_SKILL, CHALLENGER_SKILL


def _load_explicit_cases(case_ids: list[str]) -> list[dict]:
    """Resolve user-selected case ids to retrieval-shaped hits (dedup, ordered)."""
    from skill_eval.testcase_fixture import list_testcase_ids, load_case

    known = set(list_testcase_ids())
    unknown = [c for c in case_ids if c not in known]
    if unknown:
        raise ValueError(f"unknown test case id(s): {', '.join(sorted(set(unknown)))}")
    seen: set[str] = set()
    hits: list[dict] = []
    for cid in case_ids:
        if cid in seen:
            continue
        seen.add(cid)
        hits.append(
            {
                "case_id": cid,
                "description": str(load_case(cid).get("description", "")),
                "distance": None,
            }
        )
    return hits


def _default_skill(path: Path) -> SkillInput:
    name = path.name
    try:
        return SkillInput(name=name, markdown=(path / "SKILL.md").read_text())
    except (OSError, ValueError):  # missing/undecodable file, blank markdown
        return SkillInput(name=name, markdown=f"# {name}\n")


@dataclass
class _Case:
    case_id: str
    fixture: str
    description: str
    distance: float | None = None
    run_id: str | None = None
    status: str = "queued"  # queued | running | completed | failed


@dataclass
class BatchState:
    batch_id: str
    query: str
    created_at: float
    real_agents: bool
    cases: list[_Case] = field(default_factory=list)
    status: str = "running"  # running | completed | failed
    task: asyncio.Task | None = None


class BatchManager:
    """Owns live batches; child runs live in the wrapped RunManager."""

    def __init__(self, manager: RunManager, runs_dir: str) -> None:
        self.manager = manager
        self.batches_dir = Path(runs_dir) / "batches"
        self._batches: dict[str, BatchState] = {}

    # -- lifecycle ----------------------------------------------------------

    async def start(self, req: CreateBatchRequest) -> str:
        if req.case_ids:
            # The user pruned the retrieval preview: run exactly these cases.
            hits = await asyncio.to_thread(_load_explicit_cases, req.case_ids)
        else:
            # Retrieval embeds the query (chromadb + ONNX model) — keep that
            # work off the event loop or every SSE stream stalls while it runs.
            hits = await asyncio.to_thread(retrieve_cases, req.query, req.top_k)
        if not hits:
            raise ValueError("retriever found no test cases (is testcases/ present?)")

        batch_id = uuid.uuid4().hex[:12]
        state = BatchState(
            batch_id=batch_id,
            query=req.query,
            created_at=time.time(),
            real_agents=req.real_agents,
            cases=[
                _Case(
                    case_id=h["case_id"],
                    fixture=f"testcase:{h['case_id']}",
                    description=h["description"],
                    distance=h["distance"],
                )
                for h in hits
            ],
        )
        self._batches[batch_id] = state
        self._persist(state)  # visible (as interrupted) even if we die mid-batch
        state.task = asyncio.get_running_loop().create_task(self._execute(state, req))
        return batch_id

    async def _execute(self, state: BatchState, req: CreateBatchRequest) -> None:
        try:
            baseline = req.baseline or _default_skill(BASELINE_SKILL)
            challenger = req.challenger or _default_skill(CHALLENGER_SKILL)
            # None = no throttle: every retrieved case runs at once.
            gate = asyncio.Semaphore(req.max_concurrent or len(state.cases))

            async def run_one(case: _Case) -> None:
                async with gate:
                    try:
                        child = CreateRunRequest(
                            fixture=case.fixture,
                            task_brief=case.description,
                            baseline=baseline,
                            challenger=challenger,
                            max_turns=req.max_turns,
                            thinking_budget=req.thinking_budget,
                            wall_clock_seconds=req.wall_clock_seconds,
                            judge_model=req.judge_model,
                            judges_per_criterion=req.judges_per_criterion,
                            real_agents=req.real_agents,
                        )
                        case.run_id = self.manager.start(child)
                        case.status = "running"
                        run_state = self.manager._runs.get(case.run_id)
                        if run_state is not None and run_state.task is not None:
                            # RunManager._execute never raises (failures become
                            # RunFailed events), so awaiting is exception-safe.
                            await run_state.task
                        summary = self.manager.summary(case.run_id)
                        case.status = summary.status if summary else "failed"
                    except Exception:  # noqa: BLE001 — one bad case must not kill the batch
                        case.status = "failed"
                    self._persist(state)  # checkpoint after every case

            await asyncio.gather(*(run_one(c) for c in state.cases))
            state.status = "completed"
        except Exception:  # noqa: BLE001 — batch must reach a terminal state
            state.status = "failed"
            for c in state.cases:
                if c.status in ("queued", "running"):
                    c.status = "failed"
        finally:
            self._persist(state)

    # -- queries --------------------------------------------------------------

    def summary(self, batch_id: str) -> BatchSummary | None:
        state = self._batches.get(batch_id)
        if state is None:
            return self._load_archived(batch_id, summary_only=True)  # type: ignore[return-value]
        return self._summary_of(state)

    def list_batches(self) -> list[BatchSummary]:
        out = [self._summary_of(s) for s in self._batches.values()]
        live = set(self._batches)
        if self.batches_dir.is_dir():
            for f in self.batches_dir.glob("*.json"):
                if f.stem not in live:
                    archived = self._load_archived(f.stem, summary_only=True)
                    if archived is not None:
                        out.append(archived)  # type: ignore[arg-type]
        out.sort(key=lambda s: s.created_at, reverse=True)
        return out

    def detail(self, batch_id: str) -> BatchDetail | None:
        state = self._batches.get(batch_id)
        if state is None:
            return self._load_archived(batch_id, summary_only=False)  # type: ignore[return-value]

        cases: list[BatchCaseState] = []
        reports: list[tuple[str, ComparisonReport]] = []
        for c in state.cases:
            cs = BatchCaseState(
                case_id=c.case_id,
                fixture=c.fixture,
                description=c.description,
                distance=c.distance,
                run_id=c.run_id,
                status=c.status,
            )
            report = self.manager.report(c.run_id) if c.run_id else None
            if report is not None:
                self._fill_case_results(cs, report)
                reports.append((c.case_id, report))
            cases.append(cs)

        stats = _compute_stats(reports) if reports else None
        return BatchDetail(summary=self._summary_of(state), cases=cases, stats=stats)

    # -- internals -------------------------------------------------------------

    def _summary_of(self, state: BatchState) -> BatchSummary:
        done = sum(1 for c in state.cases if c.status == "completed")
        failed = sum(1 for c in state.cases if c.status == "failed")
        return BatchSummary(
            batch_id=state.batch_id,
            query=state.query,
            status=state.status,
            created_at=state.created_at,
            real_agents=state.real_agents,
            total=len(state.cases),
            completed=done,
            failed=failed,
        )

    @staticmethod
    def _fill_case_results(cs: BatchCaseState, report: ComparisonReport) -> None:
        cs.verdict = report.pairwise_verdict
        for ar in report.arms:
            if ar.arm is Arm.BASELINE:
                cs.baseline_total = ar.total_score
                cs.baseline_tokens = ar.metrics.total_tokens
            elif ar.arm is Arm.CHALLENGER:
                cs.challenger_total = ar.total_score
                cs.challenger_tokens = ar.metrics.total_tokens

    def _persist(self, state: BatchState) -> None:
        try:
            self.batches_dir.mkdir(parents=True, exist_ok=True)
            detail = self.detail(state.batch_id)
            if detail is not None:
                path = self.batches_dir / f"{state.batch_id}.json"
                tmp = path.with_suffix(".json.tmp")
                tmp.write_text(detail.model_dump_json(indent=2))
                tmp.replace(path)  # atomic: a crash mid-write can't corrupt the archive
        except Exception:  # noqa: BLE001 — archival is best-effort, never breaks a batch
            pass

    def _load_archived(self, batch_id: str, *, summary_only: bool):
        path = self.batches_dir / f"{batch_id}.json"
        if not path.is_file():
            return None
        try:
            detail = BatchDetail.model_validate_json(path.read_text())
        except (OSError, ValueError):
            return None
        if detail.summary.status == "running":
            # Archived as running but not in memory: the process died mid-batch.
            detail = detail.model_copy(
                update={"summary": detail.summary.model_copy(update={"status": "interrupted"})}
            )
        return detail.summary if summary_only else detail


def _compute_stats(reports: list[tuple[str, ComparisonReport]]) -> BatchStats:
    from skill_eval.reporting import (
        batch_criterion_gap_rows,
        batch_per_criterion_avg,
        batch_score_distribution,
        batch_win_summary,
    )

    just_reports = [r for _cid, r in reports]
    per_case_totals: list[dict] = []
    tokens_per_case: list[dict] = []
    for case_id, report in reports:
        totals = {ar.arm: ar.total_score for ar in report.arms}
        tokens = {ar.arm: ar.metrics.total_tokens for ar in report.arms}
        per_case_totals.append(
            {
                "case": case_id,
                "baseline": totals.get(Arm.BASELINE, 0),
                "challenger": totals.get(Arm.CHALLENGER, 0),
            }
        )
        tokens_per_case.append(
            {
                "case": case_id,
                "baseline": tokens.get(Arm.BASELINE, 0),
                "challenger": tokens.get(Arm.CHALLENGER, 0),
            }
        )

    return BatchStats(
        win_summary=batch_win_summary(just_reports),
        per_criterion_avg=batch_per_criterion_avg(just_reports),
        criterion_gap=batch_criterion_gap_rows(just_reports),
        per_case_totals=per_case_totals,
        score_distribution=batch_score_distribution(just_reports),
        tokens_per_case=tokens_per_case,
    )
