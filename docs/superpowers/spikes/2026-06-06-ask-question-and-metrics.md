# Spike #4 — ask_question routing, counting, metrics

SDK version: 0.2.93

Result/Message/Hook classes (from `dir(claude_agent_sdk)` filtered to `Result|Message|Hook`):

```
['AssistantMessage', 'BaseHookInput', 'ForkSessionResult', 'HookCallback',
 'HookContext', 'HookEventMessage', 'HookInput', 'HookJSONOutput', 'HookMatcher',
 'Message', 'MirrorErrorMessage', 'NotificationHookInput',
 'NotificationHookSpecificOutput', 'PermissionRequestHookInput',
 'PermissionRequestHookSpecificOutput', 'PermissionResult', 'PermissionResultAllow',
 'PermissionResultDeny', 'PostToolUseFailureHookInput',
 'PostToolUseFailureHookSpecificOutput', 'PostToolUseHookInput', 'PreCompactHookInput',
 'PreToolUseHookInput', 'ResultMessage', 'ServerToolResultBlock', 'SessionMessage',
 'StopHookInput', 'SubagentStartHookInput', 'SubagentStartHookSpecificOutput',
 'SubagentStopHookInput', 'SystemMessage', 'TaskNotificationMessage',
 'TaskProgressMessage', 'TaskStartedMessage', 'ToolResultBlock', 'UserMessage',
 'UserPromptSubmitHookInput']
```

Final-message class + its real attributes (from `dataclasses.fields(ResultMessage)`):

```
ResultMessage  (is a @dataclass)
  subtype:            str
  duration_ms:        int
  duration_api_ms:    int
  is_error:           bool
  num_turns:          int
  session_id:         str
  stop_reason:        str | None
  total_cost_usd:     float | None
  usage:              dict[str, Any] | None    <- raw Anthropic API usage dict (see below)
  result:             str | None               <- final text output
  structured_output:  Any
  model_usage:        dict[str, Any] | None    <- from CLI JSON key "modelUsage"
  permission_denials: list[Any] | None
  deferred_tool_use:  DeferredToolUse | None
  errors:             list[str] | None
  api_error_status:   int | None               <- HTTP status (e.g. 429) when is_error=True
  uuid:               str | None
```

## Confirmed WITHOUT inference (static)

- **Imports tool/create_sdk_mcp_server/HookMatcher:** OK — `from claude_agent_sdk import tool, create_sdk_mcp_server, HookMatcher` succeeds.

- **Tool + MCP server + ClaudeAgentOptions construct without error:** OK — verified by constructing all three objects without starting inference. `create_sdk_mcp_server` returns a `dict` (McpSdkServerConfig TypedDict). `ClaudeAgentOptions` is a `@dataclass`.

- **Real attribute names that map to RunMetrics (from class introspection):**
  - `input_tokens` → `result_msg.usage["input_tokens"]` (key in the `usage: dict` field; keys follow Anthropic API conventions; exact keys PENDING CREDITS runtime confirmation)
  - `output_tokens` → `result_msg.usage["output_tokens"]` (same dict)
  - `cache_tokens` → `result_msg.usage["cache_creation_input_tokens"]` / `"cache_read_input_tokens"` (same dict, PENDING)
  - `total_cost` → `result_msg.total_cost_usd` (direct float field, always present after a successful run)
  - `num_turns` → `result_msg.num_turns` (direct int field, confirmed in dataclass)
  - `model_usage_breakdown` → `result_msg.model_usage` (dict from CLI `modelUsage` JSON key; structure PENDING runtime)
  - `stop_reason` → `result_msg.stop_reason` (str | None; values like `"end_turn"`, `"max_turns"` — exact mapping PENDING CREDITS)

- **HookMatcher / hook callback signature:**

  ```python
  HookMatcher(
      matcher: str | None = None,
      hooks: list[Callable[[HookInputUnion, str | None, HookContext],
                            Awaitable[AsyncHookJSONOutput | SyncHookJSONOutput]]] = [],
      timeout: float | None = None,
  )
  ```

  Hook callback receives: `(input_data, tool_use_id: str | None, context: HookContext)`.
  For PostToolUse, `input_data` is `PostToolUseHookInput` (a TypedDict-like class with attrs:
  `hook_event_name`, `tool_name`, `tool_input`, `tool_response`, `tool_use_id`, plus
  BaseHookInput fields `session_id`, `transcript_path`, `cwd`).
  Access the tool name via `input_data.tool_name` — NOT `input_data.get("tool_name")`.
  Return value is a plain `dict` (empty `{}` is fine for pass-through).

- **Syntax check:** `ast.parse(open('spikes/spike_ask_question.py').read())` → parses ok.
- **ruff check:** All checks passed (0 errors).

## PENDING CREDITS (needs a funded account to verify)

- **ask_question round-trip (HANDLER_CALLS == 1):** PENDING — the `query()` iterator never
  yielded a message; `HANDLER_CALLS` was never printed before the exception was raised.
- **HOOK_COUNTS shows the tool fired:** PENDING — same reason.
- **Actual metric values + stop_reason from a real ResultMessage:** PENDING.
- **Exact keys inside `usage` dict:** PENDING (expected: `input_tokens`, `output_tokens`,
  `cache_creation_input_tokens`, `cache_read_input_tokens` per Anthropic API spec).

- **Exact billing error observed:**

  ```
  Exception: Claude Code returned an error result: success
  ```

  Raised inside `claude_agent_sdk/_internal/query.py:852` via
  `raise Exception(message.get("error", "Unknown error"))`. The underlying CLI JSON has
  `subtype="success"` but `is_error=True`; the SDK raises rather than yielding the
  `ResultMessage`, so `last` remains `None` and `dump_metrics` is never called. This matches
  the Spike #3 finding exactly.

## Recommendation for C2 (run_taker)

**Wiring the ask_question tool:**

```python
@tool("ask_question", "Ask the human stakeholder a clarifying question.", {"question": str})
async def ask_question(args: dict[str, Any]) -> dict[str, Any]:
    answer = hitl_callback(args["question"])   # your HITL handler
    return {"content": [{"type": "text", "text": answer}]}

server = create_sdk_mcp_server(name="hitl", version="1.0.0", tools=[ask_question])
options = ClaudeAgentOptions(
    mcp_servers={"hitl": server},
    allowed_tools=["mcp__hitl__ask_question"],
    ...
)
```

**Reading metrics from the final ResultMessage:**

```python
async for message in query(prompt=..., options=options):
    last = message
# last is a ResultMessage when the run succeeds

# Confirmed-safe direct fields:
num_turns     = last.num_turns           # int, always present
total_cost    = last.total_cost_usd      # float | None
stop_reason   = last.stop_reason         # str | None  (e.g. "end_turn")
is_error      = last.is_error            # bool
duration_ms   = last.duration_ms         # int

# Usage dict (keys are PENDING runtime confirmation, but expected per Anthropic API):
input_tokens  = (last.usage or {}).get("input_tokens")
output_tokens = (last.usage or {}).get("output_tokens")
```

**What must be confirmed once credits exist:**
1. Exact keys present in `result_msg.usage` (the raw Anthropic API dict).
2. Exact keys present in `result_msg.model_usage` (the CLI `modelUsage` JSON).
3. Whether the SDK raises or yields a `ResultMessage` on `is_error=True` non-billing runs
   (e.g. `max_turns` exceeded) — currently it raises for the billing case.
4. HANDLER_CALLS == 1 after one ask_question round-trip.
5. HOOK_COUNTS["mcp__hitl__ask_question"] == 1 via the PostToolUse hook.
6. stop_reason value mapping: e.g. `"end_turn"` vs `"max_turns"` vs `"tool_use"`.
