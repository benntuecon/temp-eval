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
  - `input_tokens` → `result_msg.usage["input_tokens"]`
  - `output_tokens` → `result_msg.usage["output_tokens"]`
  - `cache_tokens` → `result_msg.usage["cache_creation_input_tokens"]` / `"cache_read_input_tokens"`
  - `total_cost` → `result_msg.total_cost_usd` (direct float field)
  - `num_turns` → `result_msg.num_turns` (direct int field)
  - `model_usage_breakdown` → `result_msg.model_usage` (dict from CLI `modelUsage` JSON key)
  - `stop_reason` → `result_msg.stop_reason` (str | None)

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

## Real run results (credits restored, 2026-06-06)

### ask_question round-trip

CONFIRMED. Exactly ONE call reached the Python handler:

```
HANDLER_CALLS = ['Which database should we use for this project (e.g., PostgreSQL, MySQL, SQLite, MongoDB, or another)?']
```

The agent then answered using the returned value:

```
result = "Based on your selection, we'll use PostgreSQL as the database for this project."
```

### Hook counting

The PostToolUse hook fired, but `input_data.get("tool_name")` was used (incorrectly — it should be
`input_data.tool_name`), so the dict key fell back to `"?"`:

```
HOOK_COUNTS = {'?': 2}
```

**Conclusion:** count questions via `len(HANDLER_CALLS)` (handler invocation count) — reliable.
Do NOT rely on the PostToolUse hook key unless using `input_data.tool_name` (attribute access).

### Real ResultMessage field values observed

```
subtype         = 'success'
is_error        = False
num_turns       = 3
stop_reason     = 'end_turn'
duration_ms     = 12931
duration_api_ms = 11318
total_cost_usd  = 0.2338   # NB: run used the expensive default model (Opus)
usage = {
    'input_tokens': 8461,
    'output_tokens': 555,
    'cache_creation_input_tokens': 25199,
    'cache_read_input_tokens': 40287,
    ...
}
model_usage = {'claude-opus-4-8[1m]': {...}}   # default model — always pin Haiku explicitly
result = "Based on your selection, we'll use PostgreSQL as the database for this project."
```

**Critical:** the default model resolved to `claude-opus-4-8[1m]` (expensive). Always set
`model="claude-haiku-4-5"` explicitly in `ClaudeAgentOptions`.

## RunMetrics mapping

| RunMetrics field | Source |
|---|---|
| `input_tokens` | `usage["input_tokens"]` |
| `output_tokens` | `usage["output_tokens"]` |
| `total_tokens` | `input_tokens + output_tokens` (computed) |
| `wall_seconds` | `duration_ms / 1000` |
| `num_turns` | `msg.num_turns` |
| `num_questions` | `len(HANDLER_CALLS)` (handler invocation count) |

## StopReason mapping

| `stop_reason` value | StopReason enum | Notes |
|---|---|---|
| `"end_turn"` | `COMPLETED` | Normal completion |
| `"max_turns"` (expected) | `MAX_TURNS` | Confirm exact value when C2 forces it |
| n/a — `asyncio.timeout` cancel | `WALL_CLOCK` | Exception path, not a ResultMessage field |
| exception or `is_error=True` | `ERROR` | SDK raises instead of yielding on some errors |

**Important:** when the SDK raises (e.g., billing error, unhandled `is_error=True` cases), `last`
remains `None` and metrics are unavailable. C2 must wrap `query()` in `try/except` and treat any
exception as `StopReason.ERROR`.

## Recommendation for C2 (run_taker)

**Wiring the ask_question tool:**

```python
@tool("ask_question", "Ask the human stakeholder a clarifying question.", {"question": str})
async def ask_question(args: dict[str, Any]) -> dict[str, Any]:
    answer = hitl_callback(args["question"])   # your HITL handler
    return {"content": [{"type": "text", "text": answer}]}

server = create_sdk_mcp_server(name="hitl", version="1.0.0", tools=[ask_question])
options = ClaudeAgentOptions(
    model="claude-haiku-4-5",               # cheapest model — hackathon cost control
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

num_turns     = last.num_turns                              # int, always present
total_cost    = last.total_cost_usd                         # float | None
stop_reason   = last.stop_reason                            # str | None  (e.g. "end_turn")
is_error      = last.is_error                               # bool
duration_ms   = last.duration_ms                            # int
input_tokens  = (last.usage or {}).get("input_tokens")
output_tokens = (last.usage or {}).get("output_tokens")
total_tokens  = (input_tokens or 0) + (output_tokens or 0)
wall_seconds  = last.duration_ms / 1000
num_questions = len(HANDLER_CALLS)                          # handler invocation count
```
