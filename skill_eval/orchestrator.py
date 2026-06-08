"""C6 LangGraph orchestrator for skill-eval.

Wires sandbox → takers (concurrent) → judges (concurrent) → report
as a LangGraph StateGraph using the Send API for real per-agent fan-out.
Each taker and each judge is an independently-visible LangGraph node.

Concrete components are injected so Phase A uses the simulated stand-ins
and Phase B swaps in real LLM-backed ones without changing this file.
"""

from __future__ import annotations

import asyncio
import operator
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from opentelemetry import trace

from skill_eval.contracts import (
    Arm,
    ArmReport,
    ComparisonReport,
    Criterion,
    EventFn,
    JudgeFn,
    JudgeInput,
    JudgeScore,
    MakeSimulator,
    RunConfig,
    TakerFn,
    TakerResult,
    Workspace,
)
from skill_eval.sandbox import cleanup_workspaces, prepare_workspaces


def _get_tracer() -> trace.Tracer:
    """Return a tracer bound to the *current* TracerProvider.

    Called lazily (inside each function) so that a test can install an
    in-memory provider via ``trace.set_tracer_provider(...)`` before the
    first span is created, even after the module has been imported.
    """
    return trace.get_tracer("skill_eval")


# ---------------------------------------------------------------------------
# LangGraph state  (reducer channels so parallel nodes can append safely)
# ---------------------------------------------------------------------------


class _EvalState(TypedDict, total=False):
    # inputs (set at graph start)
    cfg: RunConfig
    taker_fn: TakerFn
    simulator_factory: MakeSimulator
    judge_fn: JudgeFn
    on_event: EventFn | None
    # inter-node data
    spaces: dict[Arm, Workspace]
    # reducer channels: parallel nodes append their results
    taker_results: Annotated[list[tuple[Arm, TakerResult]], operator.add]
    scores: Annotated[list[tuple[Arm, JudgeScore]], operator.add]
    # final output
    report: ComparisonReport


# ---------------------------------------------------------------------------
# Node helpers
# ---------------------------------------------------------------------------


def _emit(on_event: EventFn | None, event: dict[str, Any]) -> None:
    if on_event is not None:
        on_event(event)


# ---------------------------------------------------------------------------
# Node: prepare workspaces
# ---------------------------------------------------------------------------


def _node_prepare(state: _EvalState) -> dict[str, Any]:
    """Emit sandbox stage events; workspaces are already created by run_eval."""
    on_event = state.get("on_event")
    spaces: dict[Arm, Workspace] = state["spaces"]
    cfg: RunConfig = state["cfg"]
    with _get_tracer().start_as_current_span("sandbox") as span:
        span.set_attribute("openinference.span.kind", "CHAIN")
        span.set_attribute("num_arms", len(spaces))
        # Enrich with hashes and gold diff sizes
        span.set_attribute("before_hash", cfg.before_hash)
        span.set_attribute("after_hash", cfg.after_hash)
        # Accumulate gold_diff_chars across arms
        total_gold_chars = sum(len(ws.gold_diff) for ws in spaces.values())
        span.set_attribute("gold_diff_chars", total_gold_chars)
        _emit(on_event, {"stage": "sandbox", "msg": "workspaces ready", "arms": list(spaces)})
    return {}


# ---------------------------------------------------------------------------
# Fan-out: one Send("taker", ...) per arm
# ---------------------------------------------------------------------------


def _fan_out_takers(state: _EvalState) -> list[Send]:
    cfg = state["cfg"]
    spaces: dict[Arm, Workspace] = state["spaces"]
    model = cfg.models[0]
    sends: list[Send] = []
    for arm, ws in spaces.items():
        sends.append(
            Send(
                "taker",
                {
                    "arm": arm,
                    "ws": ws,
                    "cfg": cfg,
                    "model": model,
                    "taker_fn": state["taker_fn"],
                    "simulator_factory": state["simulator_factory"],
                    "on_event": state.get("on_event"),
                },
            )
        )
    return sends


# ---------------------------------------------------------------------------
# Node: taker  (async — runs concurrently via ainvoke)
# ---------------------------------------------------------------------------


async def _node_taker(payload: dict[str, Any]) -> dict[str, Any]:
    arm: Arm = payload["arm"]
    ws: Workspace = payload["ws"]
    cfg: RunConfig = payload["cfg"]
    model: str = payload["model"]
    taker_fn: TakerFn = payload["taker_fn"]
    simulator_factory: MakeSimulator = payload["simulator_factory"]
    on_event: EventFn | None = payload.get("on_event")

    skill_path = cfg.challenger_skill_path if arm is Arm.CHALLENGER else cfg.baseline_skill_path
    ask_fn = simulator_factory(ws.after_dir, cfg.task_brief, model)

    with _get_tracer().start_as_current_span("taker") as span:
        span.set_attribute("openinference.span.kind", "AGENT")
        span.set_attribute("arm", arm.value)
        span.set_attribute("model", model)

        _emit(on_event, {"stage": "taker", "arm": arm.value, "status": "running"})

        result: TakerResult = await asyncio.to_thread(taker_fn, ws, model, skill_path, cfg, ask_fn)

        span.set_attribute("stop_reason", result.stop_reason.value)
        span.set_attribute("num_questions", result.metrics.num_questions)
        span.set_attribute("total_tokens", result.metrics.total_tokens)

        _emit(
            on_event,
            {
                "stage": "taker",
                "arm": arm.value,
                "status": "done",
                "stop_reason": result.stop_reason.value,
                "num_questions": result.metrics.num_questions,
            },
        )

    return {"taker_results": [(arm, result)]}


# ---------------------------------------------------------------------------
# Node: judges_dispatch  (join after all takers complete)
# ---------------------------------------------------------------------------


def _node_judges_dispatch(state: _EvalState) -> dict[str, Any]:
    on_event = state.get("on_event")
    _emit(on_event, {"stage": "takers_done", "count": len(state["taker_results"])})
    return {}


# ---------------------------------------------------------------------------
# Fan-out: one Send("judge", ...) per arm × Criterion
# ---------------------------------------------------------------------------


def _fan_out_judges(state: _EvalState) -> list[Send]:
    cfg = state["cfg"]
    spaces: dict[Arm, Workspace] = state["spaces"]
    taker_map: dict[Arm, TakerResult] = dict(state["taker_results"])
    model = cfg.models[0]
    sends: list[Send] = []
    for arm, ws in spaces.items():
        taker = taker_map[arm]
        for criterion in Criterion:
            sends.append(
                Send(
                    "judge",
                    {
                        "arm": arm,
                        "criterion": criterion,
                        "cfg": cfg,
                        "model": model,
                        "ws": ws,
                        "taker": taker,
                        "judge_fn": state["judge_fn"],
                        "on_event": state.get("on_event"),
                    },
                )
            )
    return sends


# ---------------------------------------------------------------------------
# Node: judge  (async — runs concurrently via ainvoke)
# ---------------------------------------------------------------------------


async def _node_judge(payload: dict[str, Any]) -> dict[str, Any]:
    arm: Arm = payload["arm"]
    criterion: Criterion = payload["criterion"]
    cfg: RunConfig = payload["cfg"]
    model: str = payload["model"]
    ws: Workspace = payload["ws"]
    taker: TakerResult = payload["taker"]
    judge_fn: JudgeFn = payload["judge_fn"]
    on_event: EventFn | None = payload.get("on_event")

    ji = JudgeInput(
        criterion=criterion,
        task_brief=cfg.task_brief,
        gold_diff=ws.gold_diff,
        after_dir=ws.after_dir,
        taker=taker,
    )

    with _get_tracer().start_as_current_span("judge") as span:
        span.set_attribute("openinference.span.kind", "LLM")
        span.set_attribute("arm", arm.value)
        span.set_attribute("criterion", criterion.value)

        _emit(
            on_event,
            {"stage": "judge", "arm": arm.value, "criterion": criterion.value, "status": "running"},
        )

        score: JudgeScore = await asyncio.to_thread(judge_fn, ji, model)

        span.set_attribute("score", score.score)

        _emit(
            on_event,
            {
                "stage": "judge",
                "arm": arm.value,
                "criterion": criterion.value,
                "status": "done",
                "score": score.score,
            },
        )

    return {"scores": [(arm, score)]}


# ---------------------------------------------------------------------------
# Node: assemble report  (join after all judges complete)
# ---------------------------------------------------------------------------


def _node_assemble(state: _EvalState) -> dict[str, Any]:
    cfg = state["cfg"]
    on_event = state.get("on_event")

    taker_map: dict[Arm, TakerResult] = dict(state["taker_results"])

    # Group scores by arm
    scores_by_arm: dict[Arm, list[JudgeScore]] = {}
    for arm, score in state["scores"]:
        scores_by_arm.setdefault(arm, []).append(score)

    arm_reports: list[ArmReport] = []
    for arm, arm_scores in scores_by_arm.items():
        taker = taker_map[arm]
        total = sum(s.score for s in arm_scores)
        arm_reports.append(
            ArmReport(
                arm=arm,
                model=taker.model,
                metrics=taker.metrics,
                scores=arm_scores,
                total_score=total,
            )
        )

    # Determine pairwise verdict
    totals = {ar.arm: ar.total_score for ar in arm_reports}
    baseline_score = totals.get(Arm.BASELINE, 0)
    challenger_score = totals.get(Arm.CHALLENGER, 0)
    margin = abs(challenger_score - baseline_score)

    if challenger_score > baseline_score:
        verdict = f"challenger wins by {margin} points ({challenger_score} vs {baseline_score})"
    elif baseline_score > challenger_score:
        verdict = f"baseline wins by {margin} points ({baseline_score} vs {challenger_score})"
    else:
        verdict = f"tie — both arms scored {baseline_score}"

    report = ComparisonReport(
        config=cfg,
        arms=arm_reports,
        pairwise_verdict=verdict,
    )

    _emit(on_event, {"stage": "report", "verdict": verdict})
    return {"report": report}


# ---------------------------------------------------------------------------
# Build and compile the graph (once at module load)
# ---------------------------------------------------------------------------


def _build_graph() -> Any:
    g: StateGraph = StateGraph(_EvalState)
    g.add_node("prepare", _node_prepare)
    g.add_node("taker", _node_taker)  # type: ignore[arg-type]
    g.add_node("judges_dispatch", _node_judges_dispatch)
    g.add_node("judge", _node_judge)  # type: ignore[arg-type]
    g.add_node("assemble", _node_assemble)

    g.add_edge(START, "prepare")
    g.add_conditional_edges("prepare", _fan_out_takers, ["taker"])
    g.add_edge("taker", "judges_dispatch")
    g.add_conditional_edges("judges_dispatch", _fan_out_judges, ["judge"])
    g.add_edge("judge", "assemble")
    g.add_edge("assemble", END)

    return g.compile()


_GRAPH = _build_graph()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_eval(
    cfg: RunConfig,
    *,
    taker_fn: TakerFn | None = None,
    simulator_factory: MakeSimulator | None = None,
    judge_fn: JudgeFn | None = None,
    on_event: EventFn | None = None,
) -> ComparisonReport:
    """Orchestrate a full eval: sandbox → takers → judges → report.

    Phase A: pass ``taker_fn=sim_run_taker``, ``simulator_factory=sim_make_simulator``,
    ``judge_fn=sim_run_judge`` from ``skill_eval.simulated``.
    Phase B: swap in the real LLM-backed implementations.

    Args:
        cfg: Eval configuration (commits, task brief, skill paths, model).
        taker_fn: Callable matching ``TakerFn``. Defaults to the real taker
            (Phase B); raises ``NotImplementedError`` if the real module is absent.
        simulator_factory: Callable matching ``MakeSimulator``. Same note.
        judge_fn: Callable matching ``JudgeFn``. Same note.
        on_event: Optional callback receiving ``{"stage": ..., ...}`` dicts.

    Returns:
        A :class:`ComparisonReport` with per-arm scores and a pairwise verdict.
    """
    # Lazy defaults: try to import the real Phase-B implementations.
    if taker_fn is None:
        try:
            from skill_eval.taker import run_taker as _real_taker  # type: ignore[import]

            taker_fn = _real_taker
        except ImportError as exc:
            raise NotImplementedError(
                "real taker is Phase B; pass taker_fn=sim_run_taker for now"
            ) from exc

    if simulator_factory is None:
        try:
            from skill_eval.simulator import make_simulator as _real_sim  # type: ignore[import]

            simulator_factory = _real_sim
        except ImportError as exc:
            raise NotImplementedError(
                "real simulator is Phase B; pass simulator_factory=sim_make_simulator for now"
            ) from exc

    if judge_fn is None:
        try:
            from skill_eval.judge import run_judge as _real_judge  # type: ignore[import]

            judge_fn = _real_judge
        except ImportError as exc:
            raise NotImplementedError(
                "real judge is Phase B; pass judge_fn=sim_run_judge for now"
            ) from exc

    # Create workspaces BEFORE invoking the graph so cleanup is guaranteed
    # even when a node after prepare raises.
    spaces: dict[Arm, Workspace] = prepare_workspaces(cfg)
    try:
        with _get_tracer().start_as_current_span("skill_eval.run") as root:
            root.set_attribute("openinference.span.kind", "CHAIN")
            root.set_attribute("models", ",".join(cfg.models))
            # Enrich input with task brief and skill names
            import os as _os

            baseline_name = _os.path.basename(cfg.baseline_skill_path)
            challenger_name = _os.path.basename(cfg.challenger_skill_path)
            root.set_attribute("input.value", cfg.task_brief)
            root.set_attribute("input.mime_type", "text/plain")
            root.set_attribute("baseline_skill", baseline_name)
            root.set_attribute("challenger_skill", challenger_name)
            initial_state: _EvalState = {
                "cfg": cfg,
                "taker_fn": taker_fn,
                "simulator_factory": simulator_factory,
                "judge_fn": judge_fn,
                "on_event": on_event,
                "spaces": spaces,
                "taker_results": [],
                "scores": [],
            }
            final_state: _EvalState = asyncio.run(_GRAPH.ainvoke(initial_state))
            report: ComparisonReport = final_state["report"]
            root.set_attribute("verdict", report.pairwise_verdict)
            # Build per-arm totals summary for output.value
            arm_summary = "; ".join(f"{ar.arm.value}={ar.total_score}" for ar in report.arms)
            root.set_attribute(
                "output.value",
                f"{report.pairwise_verdict} | arms: {arm_summary}",
            )
    finally:
        cleanup_workspaces(spaces)

    return report
