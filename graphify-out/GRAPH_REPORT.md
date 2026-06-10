# Graph Report - skill-eval  (2026-06-08)

## Corpus Check
- 50 files · ~38,660 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 574 nodes · 1372 edges · 29 communities (25 shown, 4 thin omitted)
- Extraction: 82% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 243 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `6877c1e0`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]

## God Nodes (most connected - your core abstractions)
1. `RunConfig` - 67 edges
2. `Workspace` - 43 edges
3. `TakerResult` - 43 edges
4. `Arm` - 41 edges
5. `RunMetrics` - 36 edges
6. `JudgeScore` - 32 edges
7. `ComparisonReport` - 32 edges
8. `JudgeInput` - 31 edges
9. `run_taker()` - 31 edges
10. `StopReason` - 26 edges

## Surprising Connections (you probably didn't know these)
- `_FakeResult` --uses--> `Arm`  [INFERRED]
  tests/test_taker.py → skill_eval/contracts.py
- `_FakeResult` --uses--> `StopReason`  [INFERRED]
  tests/test_taker.py → skill_eval/contracts.py
- `_FakeResult` --uses--> `RunConfig`  [INFERRED]
  tests/test_taker.py → skill_eval/contracts.py
- `_FakeResult` --uses--> `Workspace`  [INFERRED]
  tests/test_taker.py → skill_eval/contracts.py
- `_FakeResult` --uses--> `RunMetrics`  [INFERRED]
  tests/test_taker.py → skill_eval/contracts.py

## Import Cycles
- None detected.

## Communities (29 total, 4 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.19
Nodes (16): Arm, build_sample_repo(), RunConfig, cleanup_workspaces(), prepare_workspaces(), Workspace, Live end-to-end smoke test.  Marked ``@pytest.mark.live`` and skipped unless ``A, test_real_end_to_end() (+8 more)

### Community 1 - "Community 1"
Cohesion: 0.12
Nodes (40): Send, ArmReport, Criterion, JudgeInput, Everything one judge needs to score one criterion for one taker., Aggregated result for one arm (one model)., One judged dimension. Each becomes its own concurrent judge., _build_graph() (+32 more)

### Community 2 - "Community 2"
Cohesion: 0.08
Nodes (68): ResultMessage, RunMetrics, Arm, JudgeScore, make_simulator(), prepare_workspaces(), AskFn, Shared data contracts for the skill-eval harness.  This is the single integratio (+60 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (21): 10. Build order & parallelization plan, 11. Out of scope (YAGNI for the hackathon), 12. Risks & open questions, 1. Goal, 2. Inputs & Outputs, 3. Architecture — two layers, 4. Tech stack & rationale, 5. Components (+13 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (58): _is_streamlit(), main(), Streamlit dashboard for the skill-eval Phase A walking skeleton.  Run with:, Single-case control-room view.      Parameters     ----------     build_cfg:, Return True when this file is being executed by Streamlit., Flagship mode: disciplined vs ship-it-fast on prorate_refund with real Haiku age, Batch (10 cases) view: run all sample cases and show aggregate viz., _run_batch_mode() (+50 more)

### Community 5 - "Community 5"
Cohesion: 0.17
Nodes (11): Design: the injectable seam, File Structure, Phase A done criteria, Phase B preview (separate plan), Task 0: Extend contracts with injection/event aliases, Task 1: Sample task-repo builder, Task 2: C1 Sandbox — worktrees + gold diff, Task 3: Simulated components (+3 more)

### Community 6 - "Community 6"
Cohesion: 0.29
Nodes (9): HookContext, ask_question(), count_hook(), dump_metrics(), main(), my_callback(), Any, Spike (#4): custom ask_question tool -> Python handler; counting; metrics; timeo (+1 more)

### Community 7 - "Community 7"
Cohesion: 0.20
Nodes (9): ask_question round-trip, Confirmed WITHOUT inference (static), Hook counting, Real ResultMessage field values observed, Real run results (credits restored, 2026-06-06), Recommendation for C2 (run_taker), RunMetrics mapping, Spike #4 — ask_question routing, counting, metrics (+1 more)

### Community 8 - "Community 8"
Cohesion: 0.20
Nodes (9): Approach A — `cwd` + `setting_sources` + `skills` + `allowed_tools=["Skill"]`, Approach A (use when testing real skill-trigger machinery), Approach B — inject SKILL.md into `system_prompt`, Approach B (recommended default), Real run results (credits restored, 2026-06-06), Recommendation for C2 (run_taker), Result summary, Skill directory layout for Approach A (+1 more)

### Community 9 - "Community 9"
Cohesion: 0.28
Nodes (7): approach_a_setting_sources(), approach_b_system_prompt(), _collect_text(), Spike (#3): can we load ONE specific Claude Code Skill into an isolated session?, Best-effort concatenation of assistant text across SDK message shapes., Point the SDK at a project dir that contains only the fixture skill., Fallback: inject the SKILL.md straight into the system prompt.

### Community 10 - "Community 10"
Cohesion: 0.25
Nodes (7): Done criteria for this plan, File Structure, Skill Eval — Foundation Implementation Plan, Task 1: Project scaffolding with uv (issue #1), Task 2: Shared data contracts (issue #2), Task 3: Spike — isolated skill loading (issue #3), Task 4: Spike — ask_question routing, counting & metrics (issue #4)

### Community 11 - "Community 11"
Cohesion: 0.09
Nodes (49): InMemorySpanExporter, _parse_response(), JudgeScore, C5: Real judge backed by claude-haiku-4-5.  Scores one criterion for one taker r, Extract (score, rationale) from the model response.      Tries json.loads on the, Score one criterion for one taker result on a 0-20 anchored rubric.      Paramet, run_judge(), _build_gold_context() (+41 more)

### Community 12 - "Community 12"
Cohesion: 0.25
Nodes (7): Dev, How it works, Layout, Quickstart, skill-eval, The headline result, Visualizations

### Community 16 - "Community 16"
Cohesion: 0.06
Nodes (42): CalledProcessError, build_flagship_case(), RunConfig, add_all(), commit(), config(), diff(), diff_cached() (+34 more)

### Community 19 - "Community 19"
Cohesion: 0.08
Nodes (43): _compute_diff(), _metrics_from_result(), Extract ``RunMetrics`` from the final ``ResultMessage``., Map SDK fields to a ``StopReason`` enum value., Stage all changes and return the diff against the starting commit.      Diffs ag, _stop_reason(), _fake_query_gen(), _FakeResult (+35 more)

### Community 20 - "Community 20"
Cohesion: 0.09
Nodes (37): ComparisonReport, EventFn, JudgeFn, MakeSimulator, RunConfig, TakerFn, Concurrent batch runner for skill-eval.  Runs multiple RunConfigs through run_ev, Run *cfgs* through run_eval concurrently; return reports in input order.      Ar (+29 more)

### Community 21 - "Community 21"
Cohesion: 0.16
Nodes (22): _build_prompt(), JudgeInput, Build the judge prompt for a single criterion evaluation.      This is a pure fu, _ji(), correctness prompt must include concrete anchor descriptors from the spec., question_quality prompt must instruct the judge to derive ambiguities from brief, Prompt must embed the task brief, gold diff, and taker diff., Every criterion prompt must include all five anchor values 0/5/10/15/20. (+14 more)

### Community 22 - "Community 22"
Cohesion: 0.17
Nodes (11): Confirmed SDK wiring (from spikes #3/#4 — do not re-derive), File Structure, Phase B done criteria, Phase B — Real Haiku-backed Components, Task 0: pytest live marker (keep CI free), Task 1: C3 — real simulator (`skill_eval/simulator.py`), Task 2: C5 — real judge (`skill_eval/judge.py`), Task 3: C2 — real taker (`skill_eval/taker.py`) (+3 more)

### Community 23 - "Community 23"
Cohesion: 0.18
Nodes (10): Disciplined Implementation, Process (follow every step; do not skip), Red flags — stop and correct course, Step 1 — Read context, Step 2 — Enumerate ambiguities, Step 3 — Ask every ambiguity to the stakeholder, Step 4 — Write a failing test, Step 5 — Implement minimally (+2 more)

### Community 24 - "Community 24"
Cohesion: 0.20
Nodes (9): Assume Python defaults, Don't read the existing code carefully, Guess confidently and keep going, Never ask clarifying questions, Prefer clever one-liners, Principles, Ship It Fast, Skip tests — add them later (+1 more)

### Community 25 - "Community 25"
Cohesion: 0.22
Nodes (8): 1. Two shell categories → two tools, 2. Worktree concurrency hardening (in `git_ops.py`), 3. Worktrunk — not in the runtime path, Decision: Shell isolation + worktree concurrency, Decisions, Deferred / future, Implementation, Problem

### Community 26 - "Community 26"
Cohesion: 0.25
Nodes (7): Batch Cases + Concurrent Runner Implementation Plan, File Map, Self-Review, Task 1: Create `skill_eval/sample_cases.py` with all 10 task repos, Task 2: Generalize `skill_eval/simulated.py`, Task 3: Create `skill_eval/batch.py`, Task 4: Run `just check` and fix any lint/type/test issues

### Community 27 - "Community 27"
Cohesion: 0.25
Nodes (7): Baseline = BAD: `flagship/skills/ship-it-fast/SKILL.md`, Build plan, Challenger = GOOD: `flagship/skills/disciplined/SKILL.md`, Flagship Comparison — design, Judge refinement — per-criterion anchored rubric, The task: `prorate_refund`, The two skills

### Community 28 - "Community 28"
Cohesion: 0.33
Nodes (5): Backup talking points, Demo script (~2 min), Setup (before you present), The close, The flow

## Knowledge Gaps
- **104 isolated node(s):** `PreToolUse`, `CalledProcessError`, `HookContext`, `InMemorySpanExporter`, `graphify` (+99 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **4 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RunConfig` connect `Community 2` to `Community 0`, `Community 1`, `Community 4`, `Community 11`, `Community 16`, `Community 19`, `Community 20`?**
  _High betweenness centrality (0.082) - this node is a cross-community bridge._
- **Why does `run_taker()` connect `Community 11` to `Community 1`, `Community 2`, `Community 19`, `Community 4`?**
  _High betweenness centrality (0.036) - this node is a cross-community bridge._
- **Why does `Arm` connect `Community 2` to `Community 0`, `Community 1`, `Community 4`, `Community 19`, `Community 20`, `Community 21`?**
  _High betweenness centrality (0.031) - this node is a cross-community bridge._
- **Are the 40 inferred relationships involving `RunConfig` (e.g. with `Arm` and `ResultMessage`) actually correct?**
  _`RunConfig` has 40 INFERRED edges - model-reasoned connections that need verification._
- **Are the 30 inferred relationships involving `Workspace` (e.g. with `Arm` and `ResultMessage`) actually correct?**
  _`Workspace` has 30 INFERRED edges - model-reasoned connections that need verification._
- **Are the 27 inferred relationships involving `TakerResult` (e.g. with `ResultMessage` and `RunMetrics`) actually correct?**
  _`TakerResult` has 27 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `Arm` (e.g. with `Arm` and `Send`) actually correct?**
  _`Arm` has 24 INFERRED edges - model-reasoned connections that need verification._