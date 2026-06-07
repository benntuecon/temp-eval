# Spike #3 — Isolated skill loading

SDK version: 0.2.93
ClaudeAgentOptions signature (abbreviated to relevant fields):

```
ClaudeAgentOptions(
    tools: list[str] | ToolsPreset | None = None,
    allowed_tools: list[str] = <factory>,
    system_prompt: str | SystemPromptPreset | SystemPromptFile | None = None,
    cwd: str | Path | None = None,
    setting_sources: list[Literal['user', 'project', 'local']] | None = None,
    skills: list[str] | Literal['all'] | None = None,
    ...
)
```

Full signature confirmed via `inspect.signature(ClaudeAgentOptions.__init__)`. Both `setting_sources`
and `skills` exist in 0.2.93. The `query` function takes keyword-only args: `prompt=` and `options=`.

## Skill directory layout for Approach A

The SDK passes `--skills` and `--setting-sources` flags to the `claude` CLI. When
`setting_sources=["project"]` and `cwd=<workdir>`, the CLI looks for skills under:

```
<workdir>/.claude/skills/<skill-name>/SKILL.md
```

The spike copies `tests/fixtures/skills/haiku-only/` to
`<workdir>/.claude/skills/haiku-only/` before constructing `ClaudeAgentOptions`.

## Blocking issue: zero API credit balance

Both approaches were blocked at the API call stage by a billing error:

```
{"type":"error","error":{"type":"invalid_request_error",
 "message":"Your credit balance is too low to access the Anthropic API.
  Please go to Plans & Billing to upgrade or purchase credits."}}
```

The Claude CLI reports this as `result: "Credit balance is too low"` with
`subtype: "success"` and `is_error: true`. The Python SDK then raises:

```
Exception: Claude Code returned an error result: success
```

(The SDK uses `subtype` as fallback text when the error array is empty, hence
the confusing "success" suffix — but the root cause is the billing error.)

The CLI infrastructure loaded correctly: the init event confirms the skills
list, tools, model, and API key source. The blocking happens at the first
inference call, not at skill loading.

## What we can infer about Approach A

The `claude` CLI fully initialised with:
- `skills: ["haiku-only"]` appearing in the session init event's skill list
  (for user-level skills — not yet confirmed for project-level isolated skills)
- No errors loading the options

The SDK correctly passes `--setting-sources project --skills haiku-only` flags
to the CLI subprocess. The skill directory layout
(`<cwd>/.claude/skills/<name>/SKILL.md`) follows the standard Claude Code
convention. Approach A is structurally sound and expected to work once credits
are restored.

## Result summary

- Approach A (setting_sources + skills filter): **BLOCKED — billing error before
  inference; infrastructure wired correctly, ACTIVATED=unknown**
- Approach B (system_prompt injection): **BLOCKED — same billing error,
  ACTIVATED=unknown**

## Recommendation for C2 (run_taker)

**Prefer Approach A** once the API account has credits. Use this exact options dict:

```python
import shutil, tempfile
from pathlib import Path
from claude_agent_sdk import ClaudeAgentOptions, query

FIXTURE = Path("tests/fixtures/skills/haiku-only")

async def run_with_skill(prompt: str) -> str:
    workdir = Path(tempfile.mkdtemp(prefix="skill_eval_"))
    skill_dst = workdir / ".claude/skills/haiku-only"
    skill_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXTURE, skill_dst)
    try:
        options = ClaudeAgentOptions(
            cwd=str(workdir),
            setting_sources=["project"],   # ignore user/local settings
            skills=["haiku-only"],          # allowlist — only this skill
            allowed_tools=["Skill"],        # permit skill invocation
        )
        messages = [m async for m in query(prompt=prompt, options=options)]
        return _collect_text(messages)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
```

If Approach A turns out not to isolate user-level skills sufficiently in
practice (i.e., the user's global skills still load alongside the fixture),
fall back to Approach B (system_prompt injection), which requires no file
system setup and is guaranteed to override Claude's default behaviour:

```python
options = ClaudeAgentOptions(
    system_prompt=f"Follow this skill exactly:\n\n{skill_md}",
    allowed_tools=[],
)
```

Approach B has the advantage of being simpler and unaffected by the
`setting_sources` resolution order. The downside is that it bypasses the
real skill-loading machinery and thus doesn't test that the `Skill` tool
works correctly in a harness.

## Unresolved questions (need credits to answer)

1. Does `setting_sources=["project"]` fully suppress user-level skills, or do
   they bleed through?
2. Does `skills=["haiku-only"]` act as a strict allowlist (other skills
   suppressed) or just as a hint?
3. Does the response actually start with "Skill" when the haiku-only fixture
   is loaded via Approach A?

These will be answered by re-running `spikes/spike_skill_loading.py` once the
API account has been topped up.
