"""FastAPI service exposing the skill-eval agent layer.

Run with:
    just api          # uvicorn on :8600

The OpenAPI schema at /openapi.json is the source for the frontend's
generated TypeScript client (just gen-client).
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from skill_eval.api.batch_manager import BatchManager
from skill_eval.api.run_manager import RunManager
from skill_eval.api.schemas import (
    BatchCreated,
    BatchDetail,
    BatchSummary,
    CreateBatchRequest,
    CreateRunRequest,
    FixtureInfo,
    HealthInfo,
    RetrievedCase,
    RunDetail,
    RunSummary,
    SkillInput,
)
from skill_eval.events import RunEvent, dump_event

_REPO_ROOT = Path(__file__).resolve().parents[2]

SSE_HEARTBEAT_SECONDS = 15.0


def _default_runs_dir() -> str:
    return os.environ.get("SKILL_EVAL_RUNS_DIR") or str(_REPO_ROOT / "runs")


def _flagship_skill(name: str, fallback_title: str) -> SkillInput:
    p = _REPO_ROOT / "flagship" / "skills" / name / "SKILL.md"
    try:
        return SkillInput(name=name, markdown=p.read_text())
    except OSError:
        return SkillInput(
            name=name,
            markdown=f"---\nname: {name}\ndescription: {fallback_title}\n---\n\n# {name}\n",
        )


def _fixtures() -> list[FixtureInfo]:
    from skill_eval.flagship_case import TASK_BRIEF as FLAGSHIP_BRIEF
    from skill_eval.sample_repo import TASK_BRIEF as SAMPLE_BRIEF
    from skill_eval.testcase_fixture import list_testcase_ids, load_case

    # Demo test cases first: each pairs the naive vs best-practices logging
    # skills against a noisy before/after repo from testcases/.
    log_baseline = _flagship_skill("logging-naive", "print everything, ship it")
    log_challenger = _flagship_skill(
        "logging-best-practices", "leveled, structured, redacted logging"
    )
    out: list[FixtureInfo] = [
        FixtureInfo(
            id=f"testcase:{case_id}",
            label=f"Case {case_id} — logging improvement",
            brief=load_case(case_id)["description"],
            default_baseline=log_baseline,
            default_challenger=log_challenger,
        )
        for case_id in list_testcase_ids()
    ]

    baseline = _flagship_skill("ship-it-fast", "ship working code fast")
    challenger = _flagship_skill("disciplined", "clarify every ambiguity, test-first")
    out += [
        FixtureInfo(
            id="flagship",
            label="Flagship: prorate_refund (under-specified — rewards asking)",
            brief=FLAGSHIP_BRIEF,
            default_baseline=baseline,
            default_challenger=challenger,
        ),
        FixtureInfo(
            id="sample",
            label="Sample: calculator add bug (trivial)",
            brief=SAMPLE_BRIEF,
            default_baseline=baseline,
            default_challenger=challenger,
        ),
    ]
    return out


def create_app(runs_dir: str | None = None) -> FastAPI:
    """Build the FastAPI app."""
    app = FastAPI(title="skill-eval", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    effective_runs_dir = runs_dir or _default_runs_dir()
    manager = RunManager(effective_runs_dir)
    app.state.manager = manager
    batches = BatchManager(manager, effective_runs_dir)
    app.state.batches = batches

    @app.get("/api/health", response_model=HealthInfo)
    def health() -> HealthInfo:
        return HealthInfo(status="ok")

    # Documentation-only: pulls the RunEvent discriminated union into the
    # OpenAPI components so the generated TypeScript client gets typed events
    # (the SSE route itself streams text/event-stream and can't carry a model).
    @app.get("/api/schema/event-types", response_model=list[RunEvent])
    def event_types() -> list:
        return []

    @app.get("/api/fixtures", response_model=list[FixtureInfo])
    def fixtures() -> list[FixtureInfo]:
        return _fixtures()

    @app.post("/api/runs", response_model=RunSummary, status_code=201)
    async def create_run(req: CreateRunRequest) -> RunSummary:
        # async on purpose: RunManager.start() spawns the run task on THIS loop
        # (sync routes execute in a threadpool with no running loop).
        if req.fixture not in {f.id for f in _fixtures()}:
            raise HTTPException(status_code=422, detail=f"unknown fixture {req.fixture!r}")
        run_id = manager.start(req)
        summary = manager.summary(run_id)
        assert summary is not None
        return summary

    @app.get("/api/runs", response_model=list[RunSummary])
    def list_runs() -> list[RunSummary]:
        return manager.list_runs()

    @app.get("/api/runs/{run_id}", response_model=RunDetail)
    def run_detail(run_id: str) -> RunDetail:
        summary = manager.summary(run_id)
        if summary is None:
            raise HTTPException(status_code=404, detail="unknown run")
        return RunDetail(summary=summary, report=manager.report(run_id))

    # -- batch eval: retrieve K cases for a query, run them all ------------

    @app.get("/api/retrieve", response_model=list[RetrievedCase])
    async def retrieve(
        query: str,
        # same bounds as CreateBatchRequest.top_k: out-of-range k must fail the
        # same way on both endpoints, not clamp on one and 422 on the other
        k: int = Query(default=10, ge=1, le=50),
    ) -> list[RetrievedCase]:
        if not query.strip():
            raise HTTPException(status_code=422, detail="query must not be blank")
        import asyncio

        from skill_eval.retriever import retrieve_cases

        hits = await asyncio.to_thread(retrieve_cases, query, k)
        return [
            RetrievedCase(
                case_id=h["case_id"],
                fixture=f"testcase:{h['case_id']}",
                description=h["description"],
                distance=h["distance"],
            )
            for h in hits
        ]

    @app.post("/api/batches", response_model=BatchCreated, status_code=201)
    async def create_batch(req: CreateBatchRequest) -> BatchCreated:
        # async on purpose: BatchManager.start() spawns its task on THIS loop
        # (retrieval itself runs in a worker thread inside start()).
        try:
            batch_id = await batches.start(req)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return BatchCreated(batch_id=batch_id)

    @app.get("/api/batches", response_model=list[BatchSummary])
    def list_batches() -> list[BatchSummary]:
        return batches.list_batches()

    @app.get("/api/batches/{batch_id}", response_model=BatchDetail)
    def batch_detail(batch_id: str) -> BatchDetail:
        detail = batches.detail(batch_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="unknown batch")
        return detail

    @app.get("/api/runs/{run_id}/events")
    async def run_events(run_id: str) -> StreamingResponse:
        if manager.summary(run_id) is None:
            raise HTTPException(status_code=404, detail="unknown run")

        async def stream():
            import asyncio

            agen = manager.events(run_id)
            try:
                while True:
                    try:
                        ev = await asyncio.wait_for(agen.__anext__(), SSE_HEARTBEAT_SECONDS)
                    except TimeoutError:
                        yield ": heartbeat\n\n"  # SSE comment keeps proxies alive
                        continue
                    except StopAsyncIteration:
                        break
                    yield f"data: {dump_event(ev)}\n\n"
            finally:
                await agen.aclose()

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    return app


app = create_app()
