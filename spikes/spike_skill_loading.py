"""Spike (#3): can we load ONE specific Claude Code Skill into an isolated session?

Run: uv run python spikes/spike_skill_loading.py
Requires: ANTHROPIC_API_KEY in env.
Adapt option names to the real SDK signature found in Step 2; record deltas.

Real SDK findings (0.2.93):
- Both `setting_sources` and `skills` exist on ClaudeAgentOptions.
- `query` takes keyword-only args: prompt=, options=.
- `skills` type: list[str] | Literal['all'] | None
- `setting_sources` type: list[Literal['user', 'project', 'local']] | None
"""

import asyncio
import shutil
import tempfile
from pathlib import Path

from claude_agent_sdk import ClaudeAgentOptions, query

FIXTURE = Path(__file__).parent.parent / "tests/fixtures/skills/haiku-only"
PROMPT = "What is the capital of France?"


def _collect_text(messages: list) -> str:
    """Best-effort concatenation of assistant text across SDK message shapes."""
    out = []
    for m in messages:
        result = getattr(m, "result", None)
        if isinstance(result, str):
            out.append(result)
        content = getattr(m, "content", None)
        if isinstance(content, list):
            for block in content:
                text = getattr(block, "text", None)
                if text:
                    out.append(text)
    return "\n".join(out)


async def approach_a_setting_sources() -> str:
    """Point the SDK at a project dir that contains only the fixture skill."""
    workdir = Path(tempfile.mkdtemp(prefix="spike_skill_a_"))
    skill_dst = workdir / ".claude/skills/haiku-only"
    skill_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(FIXTURE, skill_dst)
    try:
        options = ClaudeAgentOptions(
            model="claude-haiku-4-5",  # cheapest model — hackathon cost control
            cwd=str(workdir),
            setting_sources=["project"],
            skills=["haiku-only"],
            allowed_tools=["Skill"],
        )
        messages = [m async for m in query(prompt=PROMPT, options=options)]
        return _collect_text(messages)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def approach_b_system_prompt() -> str:
    """Fallback: inject the SKILL.md straight into the system prompt."""
    skill_md = (FIXTURE / "SKILL.md").read_text()
    options = ClaudeAgentOptions(
        model="claude-haiku-4-5",  # cheapest model — hackathon cost control
        system_prompt=f"Follow this skill exactly:\n\n{skill_md}",
        allowed_tools=[],
    )
    messages = [m async for m in query(prompt=PROMPT, options=options)]
    return _collect_text(messages)


async def main() -> None:
    for name, coro in [
        ("A setting_sources", approach_a_setting_sources),
        ("B system_prompt", approach_b_system_prompt),
    ]:
        try:
            text = await coro()
            activated = text.strip().lower().startswith("skill")
            print(f"\n=== Approach {name} ===")
            print(text)
            print(f"ACTIVATED={activated}")
        except Exception as exc:  # noqa: BLE001 - spike: surface any failure
            print(f"\n=== Approach {name} FAILED: {type(exc).__name__}: {exc} ===")


if __name__ == "__main__":
    asyncio.run(main())
