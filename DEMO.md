# Demo script (~2 min)

**One-liner:** "How do you know if a coding-agent *skill* is actually any good? We run two skills head-to-head on the same task and let a judge panel score the results."

## Setup (before you present)
```bash
just app          # dashboard at localhost:8501, auto-starts Phoenix at localhost:6006
```
Open both tabs. (Optionally pre-run the Flagship once so Phoenix already has a rich trace to show.)

## The flow

**1. The problem (15s).** "A skill is just instructions you give an agent. Two skills *sound* equally reasonable — which one actually makes the agent better? You can't tell by reading them. So we measure."

**2. The setup (20s).** Show the two skills in `flagship/skills/`:
- **disciplined** — "find every ambiguity, ask the stakeholder, test first."
- **ship-it-fast** — "don't ask questions, just assume and ship."
The task: implement `prorate_refund` — but the brief **deliberately omits 4 critical details** (month length, same-day refund, rounding, clamping). A good agent has to *ask*.

**3. Run it live (40s).** Dashboard → **Mode: Flagship** → **Run flagship**. Narrate the **live agent graph**: sandbox → two takers → twelve judges, lighting up green. "Two real agents are solving it right now, each under its skill; a simulated stakeholder answers their questions; then 12 judges score them."

**4. The result (25s).** When it lands:
```
disciplined  118/120   asked 5 questions   ✅ every edge case
ship-it-fast  30/120   asked 0 questions   ❌ guessed, happy-path only
```
"The disciplined skill made the agent ask the 4 missing details — **question_quality 20 vs 0** — and it got the rounding and clamping right. Ship-it-fast guessed and shipped a half-right answer."

**5. The receipts (20s).** Open **Phoenix** (`localhost:6006`) → the disciplined taker span → expand its tool timeline: you can *watch* it Read the file, **ask the 5 questions**, write a test, edit. Click a judge → read its prompt and rationale. "Every score is backed by a trace — no black box."

## The close
"So: a skill eval that's **agent-driven, isolated, and evidence-backed** — it tells you not just *which* skill wins, but *why*, criterion by criterion." 

## Backup talking points
- **Free mode:** Single case / Batch run on simulated data instantly — no API cost — for iterating on the harness itself.
- **Batch:** 10 tasks → win rates + score-distribution boxplots (spread, not just averages).
- **Validity:** takers run with global skills disabled, and diffs are captured vs the start commit (so an agent that `git commit`s isn't scored as having done nothing).
