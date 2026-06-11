"""FastAPI service exposing the skill-eval agent layer.

Run with:
    just api          # uvicorn on :8600

The OpenAPI schema at /openapi.json is the source for the frontend's
generated TypeScript client (just gen-client).
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from skill_eval.api.run_manager import RunManager
from skill_eval.api.schemas import (
    CreateRunRequest,
    FixtureInfo,
    HealthInfo,
    RunDetail,
    RunSummary,
    SkillInput,
)
from skill_eval.events import dump_event

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

    baseline = _flagship_skill("ship-it-fast", "ship working code fast")
    challenger = _flagship_skill("disciplined", "clarify every ambiguity, test-first")
    return [
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


def create_app(runs_dir: str | None = None, init_tracing: bool = True) -> FastAPI:
    """Build the FastAPI app. ``init_tracing=False`` keeps tests offline."""
    app = FastAPI(title="skill-eval", version="1.0.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    manager = RunManager(runs_dir or _default_runs_dir())
    app.state.manager = manager
    app.state.phoenix_url = None

    @app.on_event("startup")
    async def _startup() -> None:  # pragma: no cover - exercised in dev, not tests
        if init_tracing:
            import asyncio

            from skill_eval.reporting import init_phoenix

            app.state.phoenix_url = await asyncio.to_thread(init_phoenix)

    @app.get("/api/health", response_model=HealthInfo)
    def health() -> HealthInfo:
        return HealthInfo(status="ok", phoenix_url=app.state.phoenix_url)

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
