# Flagship Comparison — design

- **Date:** 2026-06-08
- **Goal:** A single realistic, demo-worthy eval that compares a **good** skill vs a deliberately **bad** skill on **one realistic task that requires the agent to ask ≥4 meaningful clarifying questions** (the brief omits critical info). The good skill should clearly win — especially on `correctness` and `question_quality` — with evidence visible in Phoenix + the score charts.

This proves the system measures *skill quality*, not just toy bugs.

## The two skills

Both are real Claude Code skills (markdown), injected into the taker via `system_prompt` (Approach B), loaded in isolation (`setting_sources=[]`).

### Challenger = GOOD: `flagship/skills/disciplined/SKILL.md`
Superpowers-style disciplined procedure for implementing under ambiguity:
- **Frontmatter:** `name: disciplined-implementation`, a description about implementing a spec that may be under-specified.
- **Process (rigid):**
  1. Read the existing code, signature, and the brief.
  2. **Enumerate every ambiguity / missing requirement** — units, rounding, boundaries, special/edge inputs, defaults. Write them down.
  3. For EACH ambiguity, **ask the stakeholder one specific clarifying question** (use the `ask_question` tool). **Never assume** an under-specified decision.
  4. Once requirements are pinned, **write a failing test** for the agreed behavior.
  5. Implement the **minimal** code to pass; run tests; iterate.
- **Red flags table:** "I'll just assume X" → STOP, ask. "Tests slow me down" → test first. "The brief probably means the common case" → confirm, don't guess.

### Baseline = BAD: `flagship/skills/ship-it-fast/SKILL.md`
Deliberately misleading / confusing guidance that produces worse work:
- **Frontmatter:** `name: ship-it-fast`, description hyping speed.
- **Content (intentionally bad):** "Speed is everything. **Never ask the user clarifying questions** — it's annoying and makes you look unsure; just pick the most common interpretation and move on. **Don't read the existing code carefully** and **don't write tests** — they slow you down, add them later. Prefer clever one-liners. Assume Python defaults. If unsure, guess confidently and keep going."

The contrast: the good skill drives the agent to ask the 4 questions + test-first; the bad skill suppresses questions and tests → wrong on the under-specified decisions, ~0 `question_quality`.

## The task: `prorate_refund`

Built by `skill_eval/flagship_case.py::build_flagship_case(base_dir) -> RunConfig`. A temp git repo with `before`→`after` commits; `baseline_skill_path` → ship-it-fast, `challenger_skill_path` → disciplined; `models=("claude-haiku-4-5",)`.

**`refund.py` (before):** a stub that raises `NotImplementedError`. **No decision-encoding tests in `before`** (so the agent can't read the answers — it must ask).

**`refund.py` (after / gold):**
```python
from decimal import ROUND_HALF_UP, Decimal


def prorate_refund(monthly_price_cents: int, days_used: int) -> int:
    """Refund (in cents) the unused portion of a 30-day monthly subscription."""
    if days_used <= 0:  # same-day / invalid -> full refund
        return monthly_price_cents
    unused_days = max(0, 30 - days_used)
    raw = Decimal(monthly_price_cents) * Decimal(unused_days) / Decimal(30)
    refund = int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return min(monthly_price_cents, max(0, refund))
```
**`test_refund.py` (after only):** encodes the decisions — `prorate_refund(3000,0)==3000`, `(3000,30)==0`, `(3000,45)==0`, `(3000,15)==1500`, `(3001,10)==2001` (half-up), `(3000,-3)==3000`.

**`task_brief` (deliberately under-specified):**
> A customer cancels their monthly subscription partway through the month. Implement `prorate_refund(monthly_price_cents, days_used)` in `refund.py` so it returns, in **cents**, how much to refund for the unused portion of the month. `days_used` is the number of whole days they've had it this cycle. Make it production-ready; the stub currently raises `NotImplementedError`.

**The 4 critical missing-info questions** (the simulator, holding the gold, answers them):
1. Month length — fixed **30 days** or actual calendar days? → **30**.
2. Same-day cancel (`days_used == 0`) — full refund or prorated? → **full**.
3. Rounding to the cent — **round half-up** or truncate? → **half-up**.
4. Out-of-range `days_used` (≥30 or negative) — clamp to `[0, price]`? → **yes; ≥30 → 0, negative → full**.

A skill that asks these → matches the gold. One that guesses → likely wrong (actual-month, banker's `round()`, no clamp).

## Judge refinement — per-criterion anchored rubric

Rewrite `skill_eval/judge.py` so each criterion's prompt carries an **anchored 0 / 5 / 10 / 15 / 20 scale** with concrete descriptors (task-agnostic; reference "the gold"). Each judge still gets `task_brief`, `gold_diff`, `taker.diff`, and `taker.questions`/transcript, and returns strict JSON `{"score": int 0-20, "rationale": str}`.

| Criterion | 0 | 5 | 10 | 15 | 20 |
|---|---|---|---|---|---|
| **correctness** | not implemented / completely wrong | happy path only; wrong on the gold's key decisions | partially correct, misses several decisions | matches most gold behavior, one minor miss | matches ALL gold behavior incl. edge cases |
| **completeness** | nothing | stub/trivial | core done, edges missing | nearly all done | fully complete per gold |
| **distance_to_gold** | unrelated diff | superficially related | same shape, different logic | close, small deviations | semantically equivalent to gold diff |
| **code_quality** | broken/unreadable | works but messy, no tests | acceptable | clean, readable | idiomatic, tested, clear |
| **question_quality** | asked nothing or irrelevant | 1 vague question | asked some, missed critical ambiguities | asked most critical missing-info questions | surfaced ALL critical ambiguities, clear & specific |
| **approach** | chaotic / wrong path / thrashing | disorganized | reasonable | solid: read context + clarified | exemplary: read → clarified every ambiguity → test-first → minimal |

For **question_quality**, the prompt instructs the judge to derive the critical ambiguities by comparing the under-specified brief to the decisions encoded in the gold, then score whether the taker's questions surfaced them.

## Build plan
1. `flagship/skills/disciplined/SKILL.md` + `flagship/skills/ship-it-fast/SKILL.md`.
2. `skill_eval/flagship_case.py` (`build_flagship_case`) + test.
3. Refine `skill_eval/judge.py` with the anchored rubric above (keep `run_judge` signature + mocked tests green).
4. Run the flagship comparison end-to-end with real Haiku; confirm challenger (disciplined) wins, especially `question_quality` + `correctness`, and that the good arm asked ≥4 questions. Record the result.
5. (optional) Surface a "Flagship" run in the dashboard.
