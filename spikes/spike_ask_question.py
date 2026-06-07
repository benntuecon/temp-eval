"""Spike (#4): custom ask_question tool -> Python handler; counting; metrics; timeout.

Run: uv run python spikes/spike_ask_question.py
Requires: ANTHROPIC_API_KEY in env (and account credits for the inference part).

Real SDK findings (0.2.93) recorded here:
- Hook callback signature:
    (input_data: HookInputUnion, tool_use_id: str | None, context: HookContext)
    -> Awaitable[dict]
  Access tool name via: input_data.tool_name  (NOT input_data.get("tool_name"))
- ResultMessage fields for metrics:
    num_turns:        int  (direct, always present)
    total_cost_usd:   float | None
    usage:            dict[str, Any] | None  (raw Anthropic API usage dict;
                      likely keys: input_tokens, output_tokens, cache_creation_input_tokens,
                      cache_read_input_tokens -- confirmed at runtime only)
    model_usage:      dict[str, Any] | None  (mapped from CLI JSON "modelUsage" key)
    stop_reason:      str | None
    is_error:         bool
    duration_ms:      int
    duration_api_ms:  int
"""

import asyncio
import dataclasses
from typing import Any

from claude_agent_sdk import (
    ClaudeAgentOptions,
    HookContext,
    HookMatcher,
    create_sdk_mcp_server,
    query,
    tool,
)

# --- the Python callback the agent's question must reach ---
HANDLER_CALLS: list[str] = []


def my_callback(question: str) -> str:
    HANDLER_CALLS.append(question)
    # Stand-in for the real HITL simulator (Component 3).
    return "Use PostgreSQL."


@tool("ask_question", "Ask the human stakeholder a clarifying question.", {"question": str})
async def ask_question(args: dict[str, Any]) -> dict[str, Any]:
    answer = my_callback(args["question"])
    return {"content": [{"type": "text", "text": answer}]}


# --- count tool calls via a PostToolUse hook (cross-check with HANDLER_CALLS) ---
HOOK_COUNTS: dict[str, int] = {}


async def count_hook(
    input_data: Any, tool_use_id: str | None, context: HookContext
) -> dict[str, Any]:
    # input_data is PostToolUseHookInput — access .tool_name directly (not dict.get)
    name = getattr(input_data, "tool_name", "?")
    HOOK_COUNTS[name] = HOOK_COUNTS.get(name, 0) + 1
    return {}


PROMPT = (
    "You MUST call the ask_question tool exactly once to ask which database to "
    "use, then reply in one sentence naming that database. Do not assume."
)


def dump_metrics(message: Any) -> None:
    """Discover the REAL metric attribute names on the final message."""
    print(f"\n-- final message type: {type(message).__name__}")
    if dataclasses.is_dataclass(message):
        print(dataclasses.asdict(message))
    else:
        print({k: v for k, v in vars(message).items()})


async def main() -> None:
    server = create_sdk_mcp_server(name="hitl", version="1.0.0", tools=[ask_question])
    options = ClaudeAgentOptions(
        mcp_servers={"hitl": server},
        allowed_tools=["mcp__hitl__ask_question"],
        max_turns=5,
        hooks={"PostToolUse": [HookMatcher(hooks=[count_hook])]},
    )

    last = None
    try:
        async with asyncio.timeout(120):
            async for message in query(prompt=PROMPT, options=options):
                last = message
    except TimeoutError:
        print("WALL-CLOCK TIMEOUT fired (asyncio.timeout)")

    print(f"\nHANDLER_CALLS = {HANDLER_CALLS}")
    print(f"HOOK_COUNTS   = {HOOK_COUNTS}")
    if last is not None:
        dump_metrics(last)


if __name__ == "__main__":
    asyncio.run(main())
