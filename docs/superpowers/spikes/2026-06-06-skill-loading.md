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

## Real run results (credits restored, 2026-06-06)

### Approach A — `cwd` + `setting_sources` + `skills` + `allowed_tools=["Skill"]`

WORKS. The Skill tool loaded the `haiku-only` skill; the init event output included:

```
Base directory for this skill: .../.claude/skills/haiku-only
```

followed by the SKILL.md echo. The model produced a valid haiku starting with "Skill":

> "Skill says Paris reigns, / Seine winds through the City of / Light, France's proud heart."

The script printed `ACTIVATED=False` — this is a **false negative**: `_collect_text`
concatenates the Skill tool's preamble before the haiku, so `.startswith("skill")` matched
"Base directory…" rather than the haiku line. The skill genuinely activated and exercised
the real Skill-tool machinery.

### Approach B — inject SKILL.md into `system_prompt`

WORKS cleanly. Produced a haiku starting with "Skill", `ACTIVATED=True`, no preamble noise.

## Result summary

| Approach | Result | ACTIVATED (script) | Notes |
|---|---|---|---|
| A (`setting_sources` + `skills`) | WORKS | False (false negative — preamble offset) | Real Skill-tool machinery exercised |
| B (`system_prompt` injection) | WORKS | True | Clean transcript, no preamble |

## Recommendation for C2 (run_taker)

**Prefer Approach B (system_prompt injection)** as the default for the eval harness:
simplest, strict isolation, clean transcript (no Skill-tool preamble), `ACTIVATED` check
is reliable. Use Approach A when you specifically want to exercise real skill-trigger
behaviour (e.g., testing that `HookMatcher` fires on `Skill` tool use).

**Critical:** always set `model` explicitly to the cheapest Haiku model. The SDK default
resolved to `claude-opus-4-8[1m]` (expensive) in both approaches.

### Approach B (recommended default)

```python
options = ClaudeAgentOptions(
    model="claude-haiku-4-5",               # cheapest model — hackathon cost control
    system_prompt=f"Follow this skill exactly:\n\n{skill_md}",
    allowed_tools=[],
)
```

### Approach A (use when testing real skill-trigger machinery)

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
            model="claude-haiku-4-5",           # cheapest model — hackathon cost control
            cwd=str(workdir),
            setting_sources=["project"],        # ignore user/local settings
            skills=["haiku-only"],              # allowlist — only this skill
            allowed_tools=["Skill"],            # permit skill invocation
        )
        messages = [m async for m in query(prompt=prompt, options=options)]
        return _collect_text(messages)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
```

Note: when using Approach A, adjust `_collect_text` or the `ACTIVATED` check to skip the
Skill-tool preamble lines (or search for the haiku anywhere in the output rather than
using `.startswith`).
