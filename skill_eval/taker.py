"""C2: Real taker backed by the Claude Agent SDK (claude-haiku-4-5).

The taker is a *synchronous* function that wraps an async Agent SDK session.
It runs in the orchestrator's worker thread, so internal ``asyncio.run`` is
safe (there is no outer event loop in that thread).

Skill loading uses Approach B: inject the SKILL.md text into ``system_prompt``.
The ``ask_question`` MCP tool is an in-process SDK tool whose handler calls the
injected ``ask_fn`` closure and increments a shared question counter.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, ResultMessage, create_sdk_mcp_server, query, tool
from opentelemetry import trace

from skill_eval import git_ops
from skill_eval.contracts import AskFn, RunConfig, RunMetrics, StopReason, TakerResult, Workspace
from skill_eval.tracing import get_tracer, set_input, set_kind, set_output, set_tokens, tool_span

# ---------------------------------------------------------------------------
# Pure helpers (unit-testable without network)
# ---------------------------------------------------------------------------


def _metrics_from_result(
    result_msg: ResultMessage,
    num_questions: int,
    wall_seconds: float,
) -> RunMetrics:
    """Extract ``RunMetrics`` from the final ``ResultMessage``."""
    usage = result_msg.usage or {}
    input_tokens: int = int(usage.get("input_tokens", 0))
    output_tokens: int = int(usage.get("output_tokens", 0))
    total_tokens = input_tokens + output_tokens
    return RunMetrics(
        total_tokens=total_tokens,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        wall_seconds=wall_seconds,
        num_turns=result_msg.num_turns,
        num_questions=num_questions,
    )


def _stop_reason(
    result_msg: ResultMessage,
    timed_out: bool,
    max_turns: int,
) -> StopReason:
    """Map SDK fields to a ``StopReason`` enum value."""
    if timed_out:
        return StopReason.WALL_CLOCK
    if result_msg.num_turns >= max_turns:
        return StopReason.MAX_TURNS
    return StopReason.COMPLETED


def _compute_diff(taker_dir: str) -> str:
    """Stage all changes and return the cached diff (new + modified files).

    Returns an empty string if git is unavailable or the directory is not a
    git repository.
    """
    try:
        git_ops.add_all(taker_dir)
        return git_ops.diff_cached(taker_dir)
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------
# Main entrypoint
# ---------------------------------------------------------------------------


def run_taker(
    ws: Workspace,
    model: str,
    skill_path: str,
    cfg: RunConfig,
    ask_fn: AskFn,
) -> TakerResult:
    """Run a Claude Agent SDK session under budget and return the result.

    Parameters
    ----------
    ws:
        Isolated workspace for this arm (taker_dir is the editable worktree).
    model:
        Claude model identifier (passed explicitly; we always use haiku).
    skill_path:
        Path to the skill directory; ``SKILL.md`` is read and injected into
        the system prompt (Approach B).
    cfg:
        Run configuration containing budgets (max_turns, wall_clock_seconds).
    ask_fn:
        Callable the taker uses to ask the human-simulator a question.
    """
    # -- Read SKILL.md (empty string if missing) -------------------------
    skill_md_path = Path(skill_path) / "SKILL.md"
    skill_md = skill_md_path.read_text() if skill_md_path.exists() else ""

    # -- Mutable state shared between run_taker and the async tool handler --
    # Using a list-as-counter avoids nonlocal friction in nested async funcs.
    question_counter: list[int] = [0]
    asked_questions: list[str] = []

    # -- Define the in-process MCP tool ------------------------------------
    @tool("ask_question", "Ask the human stakeholder a clarifying question.", {"question": str})
    async def _ask_question(args: dict[str, Any]) -> dict[str, Any]:
        question_counter[0] += 1
        question = args["question"]
        asked_questions.append(question)
        tracer = get_tracer()
        with tool_span(tracer, "ask_question", {"question": question}) as span:
            set_input(span, question)
            answer = ask_fn(question)
            set_output(span, answer)
        return {"content": [{"type": "text", "text": answer}]}

    server = create_sdk_mcp_server(name="hitl", version="1.0.0", tools=[_ask_question])

    options = ClaudeAgentOptions(
        model="claude-haiku-4-5",
        cwd=ws.taker_dir,
        system_prompt=(
            f"{skill_md}\n\n"
            "You are an engineer. Complete the task described in the prompt. "
            "Use the ask_question tool if you need clarification from the stakeholder."
        ),
        allowed_tools=[
            "Read",
            "Write",
            "Edit",
            "Bash",
            "Grep",
            "Glob",
            "mcp__hitl__ask_question",
        ],
        # Isolation: load NO user/project/local settings so the taker cannot
        # access the user's global ~/.claude skills, plugins, or CLAUDE.md.
        # The skill-under-test is already injected via system_prompt (Approach B).
        setting_sources=[],
        # Belt-and-suspenders: explicitly suppress every discovered skill and
        # block the Skill tool so a global plugin cannot sneak skills back in.
        skills=[],
        disallowed_tools=["Skill"],
        mcp_servers={"hitl": server},
        max_turns=cfg.max_turns,
        permission_mode="bypassPermissions",
    )

    # -- Async inner session (collected via asyncio.run) -------------------
    transcript: list[dict[str, Any]] = []
    last_result: list[ResultMessage | None] = [None]
    timed_out: list[bool] = [False]
    error_msg: list[str | None] = [None]
    wall_start = time.monotonic()

    async def _session() -> None:
        nonlocal wall_start
        wall_start = time.monotonic()
        try:
            coro = _run_query()
            if cfg.wall_clock_seconds is not None:
                async with asyncio.timeout(cfg.wall_clock_seconds):
                    await coro
            else:
                await coro
        except TimeoutError:
            timed_out[0] = True
        except Exception as exc:  # noqa: BLE001
            error_msg[0] = str(exc)

    async def _run_query() -> None:
        # Maps tool_use_id -> (Span, tracer context token) for open tool spans.
        # We use the tracer's manual start_span / span.end so durations are real.
        open_tool_spans: dict[str, trace.Span] = {}
        tracer = get_tracer()

        async for message in query(prompt=cfg.task_brief, options=options):
            if isinstance(message, ResultMessage):
                last_result[0] = message
            else:
                # ---- Instrument tool-use / tool-result blocks ----
                # AssistantMessage carries content blocks (ToolUseBlock items).
                # UserMessage carries ToolResultBlock items.
                # We detect these defensively by block type name, not exact class,
                # since SDK versions may rename or reorganise classes.
                content = getattr(message, "content", None)
                if isinstance(content, list):
                    for block in content:
                        btype = type(block).__name__
                        # Open a span for each tool-use block
                        if btype == "ToolUseBlock":
                            tool_id = getattr(block, "id", None)
                            tool_name = getattr(block, "name", None) or "unknown"
                            tool_input = getattr(block, "input", None) or {}
                            if tool_id and tool_id not in open_tool_spans:
                                child = tracer.start_span(f"tool.{tool_name}")
                                try:
                                    child.set_attribute("openinference.span.kind", "TOOL")
                                    child.set_attribute("tool.name", tool_name)
                                    try:
                                        child.set_attribute(
                                            "tool.parameters",
                                            json.dumps(tool_input, default=str),
                                        )
                                    except Exception:  # noqa: BLE001
                                        pass
                                    set_input(child, json.dumps(tool_input, default=str))
                                except Exception:  # noqa: BLE001
                                    pass
                                open_tool_spans[tool_id] = child

                        # Close the matching span when the tool result arrives
                        elif btype == "ToolResultBlock":
                            tool_use_id = getattr(block, "tool_use_id", None)
                            span = open_tool_spans.pop(tool_use_id, None) if tool_use_id else None
                            if span is not None:
                                try:
                                    raw_content = getattr(block, "content", None)
                                    if isinstance(raw_content, str):
                                        result_text = raw_content
                                    elif isinstance(raw_content, list):
                                        parts = []
                                        for item in raw_content:
                                            if isinstance(item, dict):
                                                parts.append(item.get("text", str(item)))
                                            else:
                                                parts.append(str(item))
                                        result_text = "\n".join(parts)
                                    else:
                                        result_text = str(raw_content) if raw_content else ""
                                    set_output(span, result_text[:2000])
                                except Exception:  # noqa: BLE001
                                    pass
                                span.end()

                # Close any spans that never received a result (edge cases)
                # — we do this lazily at session end (see below)

                # Collect all non-ResultMessage messages as transcript entries.
                # SDK messages are dataclass instances; convert to dict for storage.
                try:
                    import dataclasses

                    if dataclasses.is_dataclass(message):
                        transcript.append(dataclasses.asdict(message))  # type: ignore[arg-type]
                    else:
                        transcript.append(
                            {"type": str(type(message).__name__), "raw": str(message)}
                        )
                except Exception:  # noqa: BLE001
                    transcript.append({"type": str(type(message).__name__), "raw": str(message)})

        # Close any spans that never received a result (tool call with no result)
        for orphan in list(open_tool_spans.values()):
            try:
                orphan.end()
            except Exception:  # noqa: BLE001
                pass
        open_tool_spans.clear()

    asyncio.run(_session())

    wall_seconds = time.monotonic() - wall_start
    diff = _compute_diff(ws.taker_dir)
    num_q = question_counter[0]

    # -- Determine stop_reason and metrics ---------------------------------
    if error_msg[0] is not None and last_result[0] is None:
        # Hard error: SDK raised without yielding a ResultMessage.
        metrics = RunMetrics(
            total_tokens=0,
            input_tokens=0,
            output_tokens=0,
            wall_seconds=wall_seconds,
            num_turns=0,
            num_questions=num_q,
        )
        stop = StopReason.ERROR
    elif timed_out[0] and last_result[0] is None:
        metrics = RunMetrics(
            total_tokens=0,
            input_tokens=0,
            output_tokens=0,
            wall_seconds=wall_seconds,
            num_turns=0,
            num_questions=num_q,
        )
        stop = StopReason.WALL_CLOCK
    else:
        result_msg = last_result[0]
        if result_msg is None:
            # Completed with no ResultMessage at all (edge case).
            metrics = RunMetrics(
                total_tokens=0,
                input_tokens=0,
                output_tokens=0,
                wall_seconds=wall_seconds,
                num_turns=0,
                num_questions=num_q,
            )
            stop = StopReason.COMPLETED
        else:
            metrics = _metrics_from_result(result_msg, num_q, wall_seconds)
            if timed_out[0]:
                stop = StopReason.WALL_CLOCK
            else:
                stop = _stop_reason(result_msg, timed_out[0], cfg.max_turns)

    # -- Enrich the current taker span (set by orchestrator) ---------------
    taker_span = trace.get_current_span()
    try:
        skill_name = Path(skill_path).name
        input_text = f"task: {cfg.task_brief}\nskill: {skill_name}"
        set_input(taker_span, input_text)
        # set_kind is already done by the orchestrator, but re-set to be safe
        set_kind(taker_span, "AGENT")
        # output: first ~1500 chars of the resulting diff
        set_output(taker_span, diff[:1500] if diff else "(empty diff)")
        # token counts from metrics
        set_tokens(taker_span, metrics.input_tokens, metrics.output_tokens)
    except Exception:  # noqa: BLE001
        pass

    return TakerResult(
        arm=ws.arm,
        model=model,
        diff=diff,
        transcript=tuple(transcript),
        questions=tuple(asked_questions),
        stop_reason=stop,
        metrics=metrics,
    )
