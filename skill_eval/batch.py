"""Concurrent batch runner for skill-eval.

Runs multiple RunConfigs through run_eval concurrently using a thread pool
(run_eval is synchronous — threads, not asyncio). Output order matches input order.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from skill_eval.contracts import (
    ComparisonReport,
    EventFn,
    JudgeFn,
    MakeSimulator,
    RunConfig,
    TakerFn,
)
from skill_eval.orchestrator import run_eval


def run_batch(
    cfgs: list[RunConfig],
    *,
    taker_fn: TakerFn | None = None,
    simulator_factory: MakeSimulator | None = None,
    judge_fn: JudgeFn | None = None,
    max_cases: int = 4,
    on_event: EventFn | None = None,
) -> list[ComparisonReport]:
    """Run *cfgs* through run_eval concurrently; return reports in input order.

    Args:
        cfgs: List of RunConfig objects to evaluate.
        taker_fn: Injected taker (None → real taker, Phase B).
        simulator_factory: Injected simulator factory (None → real, Phase B).
        judge_fn: Injected judge (None → real judge, Phase B).
        max_cases: Maximum concurrent evals (ThreadPoolExecutor max_workers).
        on_event: Optional callback; receives every run_eval event enriched with
            a ``"case"`` key (the 0-based index of the config in *cfgs*).

    Returns:
        List of ComparisonReport in the same order as *cfgs*.
    """
    results: dict[int, ComparisonReport] = {}

    def _run_one(i: int, cfg: RunConfig) -> tuple[int, ComparisonReport]:
        def _wrapped_event(ev: dict[str, Any]) -> None:
            if on_event is not None:
                on_event({**ev, "case": i})

        report = run_eval(
            cfg,
            taker_fn=taker_fn,
            simulator_factory=simulator_factory,
            judge_fn=judge_fn,
            on_event=_wrapped_event if on_event is not None else None,
        )
        return i, report

    with ThreadPoolExecutor(max_workers=max_cases) as executor:
        futures = {executor.submit(_run_one, i, cfg): i for i, cfg in enumerate(cfgs)}
        for future in as_completed(futures):
            i, report = future.result()  # re-raises any exception from the thread
            results[i] = report

    return [results[i] for i in range(len(cfgs))]
