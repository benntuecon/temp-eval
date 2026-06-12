"""In-process run execution: one asyncio task per eval run.

Events are buffered in memory AND appended to ``runs/<id>/events.jsonl``,
so SSE subscribers replay history then tail live — reconnects and
post-restart replays work without a job queue.
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from skill_eval.api.schemas import CreateRunRequest, RunSummary
from skill_eval.contracts import ComparisonReport, RunConfig
from skill_eval.events import (
    JudgeStatus,
    QuestionAnswered,
    QuestionAsked,
    RunCompleted,
    RunEvent,
    RunFailed,
    RunStarted,
    StageChanged,
    TakerStatus,
    ThinkingDelta,
    ToolCallEvent,
    dump_event,
    parse_event,
)

# ---------------------------------------------------------------------------
# Fixtures (task before/after repos the agents work on)
# ---------------------------------------------------------------------------

_FIXTURE_BUILDERS = {
    "flagship": "skill_eval.flagship_case:build_flagship_case",
    "sample": "skill_eval.sample_repo:build_sample_repo",
}


def _fixture_builder(fixture_id: str):
    """Resolve a fixture id to its RunConfig builder callable."""
    import importlib

    if fixture_id.startswith("testcase:"):
        from functools import partial

        from skill_eval.testcase_fixture import build_testcase

        return partial(build_testcase, fixture_id.removeprefix("testcase:"))

    target = _FIXTURE_BUILDERS.get(fixture_id)
    if target is None:
        raise KeyError(f"unknown fixture {fixture_id!r}")
    module_name, func_name = target.split(":")
    return getattr(importlib.import_module(module_name), func_name)


def _slug(name: str, fallback: str) -> str:
    s = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    return s or fallback


# ---------------------------------------------------------------------------
# Event translation: agent-layer dicts -> typed RunEvents
# ---------------------------------------------------------------------------


def translate_event(ev: dict) -> RunEvent | None:
    """Map an orchestrator/taker ``on_event`` dict to a typed RunEvent.

    Returns None for events with no UI meaning (kept out of the stream).
    """
    stage = ev.get("stage", "")
    arm = str(ev.get("arm", ""))

    if stage == "sandbox":
        return StageChanged(node="sandbox", stage="sandbox", status="done")

    if stage == "taker":
        status = str(ev.get("status", ""))
        from skill_eval.contracts import RunMetrics

        metrics = None
        if status == "done" and "total_tokens" in ev:
            metrics = RunMetrics(
                total_tokens=int(ev.get("total_tokens", 0)),
                input_tokens=0,
                output_tokens=0,
                wall_seconds=float(ev.get("wall_seconds", 0.0)),
                num_turns=int(ev.get("num_turns", 0)),
                num_questions=int(ev.get("num_questions", 0)),
            )
        return TakerStatus(
            node=f"taker:{arm}",
            arm=arm,
            status=status,
            stop_reason=ev.get("stop_reason"),
            metrics=metrics,
        )

    if stage == "taker_stream":
        kind = ev.get("kind", "")
        node = f"taker:{arm}"
        if kind == "thinking" or kind == "text":
            return ThinkingDelta(node=node, text=str(ev.get("text", "")))
        if kind == "tool":
            return ToolCallEvent(
                node=node, tool=str(ev.get("tool", "")), summary=str(ev.get("summary", ""))
            )
        if kind == "question":
            return QuestionAsked(node="simulator", question=str(ev.get("question", "")))
        if kind == "answer":
            return QuestionAnswered(
                node="simulator",
                question=str(ev.get("question", "")),
                answer=str(ev.get("answer", "")),
            )
        return None

    if stage == "judge":
        criterion = str(ev.get("criterion", ""))
        return JudgeStatus(
            node=f"judge:{arm}:{criterion}",
            arm=arm,
            criterion=criterion,
            status=str(ev.get("status", "")),
            score=ev.get("score"),
            rationale=ev.get("rationale"),
        )

    if stage == "takers_done":
        return StageChanged(node="assemble", stage="takers", status="done")

    if stage == "report":
        return StageChanged(node="report", stage="report", status="done")

    return None


# ---------------------------------------------------------------------------
# RunManager
# ---------------------------------------------------------------------------

_DONE = object()  # queue sentinel


@dataclass
class RunState:
    run_id: str
    label: str
    created_at: float
    status: str = "running"  # running | completed | failed
    verdict: str | None = None
    report: ComparisonReport | None = None
    events: list[RunEvent] = field(default_factory=list)
    subscribers: list[asyncio.Queue] = field(default_factory=list)
    task: asyncio.Task | None = None


class RunManager:
    """Owns live runs; archives finished ones under ``runs_dir``."""

    def __init__(self, runs_dir: str) -> None:
        self.runs_dir = Path(runs_dir)
        self._runs: dict[str, RunState] = {}

    # -- run lifecycle ----------------------------------------------------

    def start(self, req: CreateRunRequest) -> str:
        run_id = uuid.uuid4().hex[:12]
        label = f"{req.baseline.name}-vs-{req.challenger.name}"
        state = RunState(run_id=run_id, label=label, created_at=time.time())
        self._runs[run_id] = state
        state.task = asyncio.get_running_loop().create_task(self._execute(state, req))
        return run_id

    async def _execute(self, state: RunState, req: CreateRunRequest) -> None:
        loop = asyncio.get_running_loop()
        self._publish(state, RunStarted(run_id=state.run_id, label=state.label))
        self._publish(
            state, StageChanged(node="test_generator", stage="generator", status="running")
        )
        tmp = tempfile.mkdtemp(prefix="skill-eval-run-")
        try:
            cfg = await asyncio.to_thread(self._build_config, req, tmp)
            self._publish(
                state, StageChanged(node="test_generator", stage="generator", status="done")
            )

            def on_event(ev: dict) -> None:
                # Called from worker threads — hop onto the loop safely.
                typed = translate_event(ev)
                if typed is not None:
                    loop.call_soon_threadsafe(self._publish, state, typed)

            if req.real_agents:
                from skill_eval.judge import run_judge
                from skill_eval.orchestrator import arun_eval
                from skill_eval.simulator import make_simulator
                from skill_eval.taker import run_taker

                report = await arun_eval(
                    cfg,
                    taker_fn=run_taker,
                    simulator_factory=make_simulator,
                    judge_fn=run_judge,
                    on_event=on_event,
                )
            else:
                from skill_eval.orchestrator import arun_eval
                from skill_eval.simulated import (
                    sim_make_simulator,
                    sim_run_judge,
                    sim_run_taker,
                )

                report = await arun_eval(
                    cfg,
                    taker_fn=sim_run_taker,
                    simulator_factory=sim_make_simulator,
                    judge_fn=sim_run_judge,
                    on_event=on_event,
                )

            state.report = report
            state.verdict = report.pairwise_verdict
            state.status = "completed"
            self._archive_report(state)
            self._publish(
                state,
                RunCompleted(node="report", run_id=state.run_id, verdict=report.pairwise_verdict),
            )
        except Exception as exc:  # noqa: BLE001 — surfaced to the client as RunFailed
            state.status = "failed"
            self._publish(state, RunFailed(run_id=state.run_id, error=str(exc)))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
            self._close_subscribers(state)

    def _build_config(self, req: CreateRunRequest, base_dir: str) -> RunConfig:
        """Materialise the fixture repo + the two pasted skills (sync, threaded)."""
        builder = _fixture_builder(req.fixture)
        cfg: RunConfig = builder(base_dir)
        skills_root = Path(base_dir) / "custom_skills"
        b_slug = _slug(req.baseline.name, "baseline-skill")
        c_slug = _slug(req.challenger.name, "challenger-skill")
        if b_slug == c_slug:
            c_slug = f"{c_slug}-challenger"
        for slug, skill in ((b_slug, req.baseline), (c_slug, req.challenger)):
            d = skills_root / slug
            d.mkdir(parents=True, exist_ok=True)
            (d / "SKILL.md").write_text(skill.markdown)
        return cfg.model_copy(
            update=dict(
                task_brief=req.task_brief,
                baseline_skill_path=str(skills_root / b_slug),
                challenger_skill_path=str(skills_root / c_slug),
                max_turns=req.max_turns,
                thinking_budget=req.thinking_budget or None,
                wall_clock_seconds=req.wall_clock_seconds,
                judge_model=req.judge_model,
                judges_per_criterion=req.judges_per_criterion,
            )
        )

    # -- event fan-out + persistence ---------------------------------------

    def _publish(self, state: RunState, event: RunEvent) -> None:
        if event.ts == 0.0:
            event = event.model_copy(update={"ts": time.time()})
        state.events.append(event)
        self._append_event_log(state, event)
        for q in list(state.subscribers):
            q.put_nowait(event)

    def _close_subscribers(self, state: RunState) -> None:
        for q in list(state.subscribers):
            q.put_nowait(_DONE)

    async def events(self, run_id: str):
        """Async-iterate a run's events: replay history, then tail live."""
        state = self._runs.get(run_id)
        if state is None:
            # Archived run: replay the persisted event log, then stop.
            for ev in self._load_event_log(run_id):
                yield ev
            return

        q: asyncio.Queue = asyncio.Queue()
        # Snapshot-then-subscribe under the event loop (no awaits between),
        # so no event can fall between replay and tail.
        snapshot = list(state.events)
        live = state.status == "running"
        if live:
            state.subscribers.append(q)
        try:
            for ev in snapshot:
                yield ev
            if not live:
                return
            while True:
                item = await q.get()
                if item is _DONE:
                    return
                yield item
        finally:
            if q in state.subscribers:
                state.subscribers.remove(q)

    # -- listing / detail ---------------------------------------------------

    def summary(self, run_id: str) -> RunSummary | None:
        state = self._runs.get(run_id)
        if state is not None:
            return RunSummary(
                run_id=state.run_id,
                status=state.status,
                created_at=state.created_at,
                label=state.label,
                verdict=state.verdict,
            )
        return self._archived_summary(run_id)

    def report(self, run_id: str) -> ComparisonReport | None:
        state = self._runs.get(run_id)
        if state is not None and state.report is not None:
            return state.report
        return self._load_archived_report(run_id)

    def list_runs(self) -> list[RunSummary]:
        live = {rid: self._runs[rid] for rid in self._runs}
        out = [
            RunSummary(
                run_id=s.run_id,
                status=s.status,
                created_at=s.created_at,
                label=s.label,
                verdict=s.verdict,
            )
            for s in live.values()
        ]
        for d in self._archived_dirs():
            if d.name in live:
                continue
            summary = self._archived_summary(d.name)
            if summary is not None:
                out.append(summary)
        out.sort(key=lambda s: s.created_at, reverse=True)
        return out

    # -- disk archive ---------------------------------------------------------

    def _run_dir(self, run_id: str) -> Path:
        return self.runs_dir / run_id

    def _archived_dirs(self) -> list[Path]:
        if not self.runs_dir.is_dir():
            return []
        return [d for d in self.runs_dir.iterdir() if d.is_dir()]

    def _append_event_log(self, state: RunState, event: RunEvent) -> None:
        try:
            d = self._run_dir(state.run_id)
            d.mkdir(parents=True, exist_ok=True)
            with (d / "events.jsonl").open("a") as f:
                f.write(dump_event(event) + "\n")
            meta = {
                "run_id": state.run_id,
                "label": state.label,
                "created_at": state.created_at,
                "status": state.status,
                "verdict": state.verdict,
            }
            (d / "meta.json").write_text(json.dumps(meta))
        except OSError:
            pass  # archival is best-effort, never break a run

    def _archive_report(self, state: RunState) -> None:
        try:
            d = self._run_dir(state.run_id)
            d.mkdir(parents=True, exist_ok=True)
            if state.report is not None:
                (d / "report.json").write_text(state.report.model_dump_json(indent=2))
        except OSError:
            pass

    def _archived_summary(self, run_id: str) -> RunSummary | None:
        meta_path = self._run_dir(run_id) / "meta.json"
        if not meta_path.is_file():
            return None
        try:
            meta = json.loads(meta_path.read_text())
            return RunSummary(
                run_id=str(meta.get("run_id", run_id)),
                status=str(meta.get("status", "completed")),
                created_at=float(meta.get("created_at", 0.0)),
                label=str(meta.get("label", "")),
                verdict=meta.get("verdict"),
            )
        except (OSError, ValueError):
            return None

    def _load_archived_report(self, run_id: str) -> ComparisonReport | None:
        path = self._run_dir(run_id) / "report.json"
        if not path.is_file():
            return None
        try:
            return ComparisonReport.model_validate_json(path.read_text())
        except (OSError, ValueError):
            return None

    def _load_event_log(self, run_id: str) -> list[RunEvent]:
        path = self._run_dir(run_id) / "events.jsonl"
        if not path.is_file():
            return []
        out: list[RunEvent] = []
        try:
            for line in path.read_text().splitlines():
                if line.strip():
                    try:
                        out.append(parse_event(line))
                    except ValueError:
                        continue
        except OSError:
            return out
        return out
