"""C6 LangGraph orchestrator for skill-eval.

Wires sandbox → takers (concurrent) → judges (concurrent) → report
as a LangGraph StateGraph. Concrete components are injected so Phase A
uses the simulated stand-ins and Phase B swaps in real LLM-backed ones
without changing this file.
"""

from __future__ import annotations

import asyncio
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

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

# ---------------------------------------------------------------------------
# LangGraph state
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
    taker_results: dict[Arm, TakerResult]
    scores: dict[Arm, list[JudgeScore]]
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
    cfg = state["cfg"]
    on_event = state.get("on_event")
    _emit(on_event, {"stage": "sandbox", "msg": "preparing workspaces"})
    spaces = prepare_workspaces(cfg)
    _emit(on_event, {"stage": "sandbox", "msg": "workspaces ready", "arms": list(spaces)})
    return {"spaces": spaces}


# ---------------------------------------------------------------------------
# Node: run takers concurrently
# ---------------------------------------------------------------------------


def _node_takers(state: _EvalState) -> dict[str, Any]:
    cfg = state["cfg"]
    spaces: dict[Arm, Workspace] = state["spaces"]
    taker_fn: TakerFn = state["taker_fn"]
    simulator_factory: MakeSimulator = state["simulator_factory"]
    on_event = state.get("on_event")
    model = cfg.models[0]

    async def _run_all() -> dict[Arm, TakerResult]:
        async def _run_one(arm: Arm, ws: Workspace) -> tuple[Arm, TakerResult]:
            skill_path = (
                cfg.challenger_skill_path if arm is Arm.CHALLENGER else cfg.baseline_skill_path
            )
            ask_fn = simulator_factory(ws.after_dir, cfg.task_brief, model)
            _emit(on_event, {"stage": "taker", "arm": arm.value, "msg": "starting"})
            result: TakerResult = await asyncio.to_thread(
                taker_fn, ws, model, skill_path, cfg, ask_fn
            )
            _emit(
                on_event,
                {
                    "stage": "taker",
                    "arm": arm.value,
                    "msg": "done",
                    "stop_reason": result.stop_reason.value,
                },
            )
            return arm, result

        pairs = await asyncio.gather(*[_run_one(arm, ws) for arm, ws in spaces.items()])
        return dict(pairs)

    taker_results = asyncio.run(_run_all())
    return {"taker_results": taker_results}


# ---------------------------------------------------------------------------
# Node: run judges concurrently (arm × Criterion)
# ---------------------------------------------------------------------------


def _node_judges(state: _EvalState) -> dict[str, Any]:
    cfg = state["cfg"]
    spaces: dict[Arm, Workspace] = state["spaces"]
    taker_results: dict[Arm, TakerResult] = state["taker_results"]
    judge_fn: JudgeFn = state["judge_fn"]
    on_event = state.get("on_event")
    model = cfg.models[0]

    async def _run_all() -> dict[Arm, list[JudgeScore]]:
        async def _run_one(arm: Arm, criterion: Criterion) -> tuple[Arm, JudgeScore]:
            ws = spaces[arm]
            taker = taker_results[arm]
            ji = JudgeInput(
                criterion=criterion,
                task_brief=cfg.task_brief,
                gold_diff=ws.gold_diff,
                after_dir=ws.after_dir,
                taker=taker,
            )
            _emit(
                on_event,
                {"stage": "judge", "arm": arm.value, "criterion": criterion.value},
            )
            score: JudgeScore = await asyncio.to_thread(judge_fn, ji, model)
            return arm, score

        # fan-out over all (arm × criterion) pairs
        tasks = [_run_one(arm, criterion) for arm in spaces for criterion in Criterion]
        results = await asyncio.gather(*tasks)

        # group by arm
        grouped: dict[Arm, list[JudgeScore]] = {arm: [] for arm in spaces}
        for arm, score in results:
            grouped[arm].append(score)
        return grouped

    scores = asyncio.run(_run_all())
    return {"scores": scores}


# ---------------------------------------------------------------------------
# Node: assemble report
# ---------------------------------------------------------------------------


def _node_assemble(state: _EvalState) -> dict[str, Any]:
    cfg = state["cfg"]
    taker_results: dict[Arm, TakerResult] = state["taker_results"]
    scores: dict[Arm, list[JudgeScore]] = state["scores"]
    on_event = state.get("on_event")

    arm_reports: list[ArmReport] = []
    for arm, arm_scores in scores.items():
        taker = taker_results[arm]
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
    g.add_node("takers", _node_takers)
    g.add_node("judges", _node_judges)
    g.add_node("assemble", _node_assemble)
    g.add_edge(START, "prepare")
    g.add_edge("prepare", "takers")
    g.add_edge("takers", "judges")
    g.add_edge("judges", "assemble")
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

    # Run the graph; always clean up workspaces.
    initial_state: _EvalState = {
        "cfg": cfg,
        "taker_fn": taker_fn,
        "simulator_factory": simulator_factory,
        "judge_fn": judge_fn,
        "on_event": on_event,
    }

    spaces: dict[Arm, Workspace] | None = None
    try:
        final_state: _EvalState = _GRAPH.invoke(initial_state)
        spaces = final_state.get("spaces")
        report: ComparisonReport = final_state["report"]
    finally:
        if spaces is not None:
            cleanup_workspaces(spaces)

    return report
