# Graph Report - skill-eval  (2026-06-08)

## Corpus Check
- 26 files · ~15,138 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 214 nodes · 517 edges · 19 communities (13 shown, 6 thin omitted)
- Extraction: 73% EXTRACTED · 27% INFERRED · 0% AMBIGUOUS · INFERRED: 139 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `0200ff2c`
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

## God Nodes (most connected - your core abstractions)
1. `RunConfig` - 33 edges
2. `Arm` - 31 edges
3. `Workspace` - 27 edges
4. `TakerResult` - 25 edges
5. `JudgeInput` - 24 edges
6. `JudgeScore` - 24 edges
7. `ComparisonReport` - 20 edges
8. `Criterion` - 18 edges
9. `RunMetrics` - 17 edges
10. `ArmReport` - 16 edges

## Surprising Connections (you probably didn't know these)
- `test_runconfig_defaults_and_frozen()` --calls--> `RunConfig`  [EXTRACTED]
  tests/test_contracts.py → skill_eval/contracts.py
- `test_workspace_frozen()` --calls--> `Workspace`  [EXTRACTED]
  tests/test_contracts.py → skill_eval/contracts.py
- `main()` --calls--> `run_eval()`  [EXTRACTED]
  app.py → skill_eval/orchestrator.py
- `main()` --calls--> `build_sample_repo()`  [EXTRACTED]
  app.py → skill_eval/sample_repo.py
- `test_full_report_composition()` --calls--> `RunConfig`  [EXTRACTED]
  tests/test_contracts.py → skill_eval/contracts.py

## Import Cycles
- None detected.

## Communities (19 total, 6 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.14
Nodes (26): Arm, make_simulator(), prepare_workspaces(), Shared data contracts for the skill-eval harness.  This is the single integratio, Component 1: create git worktrees and compute the gold diff., Component 2: run a Claude Agent SDK session under budget; return result., Component 3: build the AskFn the simulator uses to answer questions., Component 6: orchestrate the whole eval and return the comparison. (+18 more)

### Community 1 - "Community 1"
Cohesion: 0.18
Nodes (29): EventFn, JudgeFn, MakeSimulator, ArmReport, ComparisonReport, Criterion, JudgeScore, A single judge's 0-20 score plus rationale. (+21 more)

### Community 2 - "Community 2"
Cohesion: 0.19
Nodes (28): JudgeInput, JudgeScore, Arm, JudgeInput, AskFn, Everything one judge needs to score one criterion for one taker., Which skill a test-taker is running., Why a test-taker run ended. (+20 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (21): 10. Build order & parallelization plan, 11. Out of scope (YAGNI for the hackathon), 12. Risks & open questions, 1. Goal, 2. Inputs & Outputs, 3. Architecture — two layers, 4. Tech stack & rationale, 5. Components (+13 more)

### Community 4 - "Community 4"
Cohesion: 0.19
Nodes (15): _is_streamlit(), main(), Streamlit dashboard for the skill-eval Phase A walking skeleton.  Run with:, Return True when this file is being executed by Streamlit., init_phoenix(), ComparisonReport, Reporting helpers and Phoenix initialisation for the skill-eval dashboard.  Pure, Return one row per Criterion with a score column per arm.      Each row is ``{"c (+7 more)

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

### Community 12 - "Community 12"
Cohesion: 0.50
Nodes (3): Develop, Setup, skill-eval

## Knowledge Gaps
- **53 isolated node(s):** `PreToolUse`, `HookContext`, `graphify`, `Setup`, `Develop` (+48 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RunConfig` connect `Community 0` to `Community 1`, `Community 2`, `Community 11`, `Community 4`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Why does `Arm` connect `Community 2` to `Community 0`, `Community 1`, `Community 11`, `Community 4`?**
  _High betweenness centrality (0.028) - this node is a cross-community bridge._
- **Why does `build_sample_repo()` connect `Community 0` to `Community 1`, `Community 2`, `Community 4`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Are the 18 inferred relationships involving `RunConfig` (e.g. with `Arm` and `EventFn`) actually correct?**
  _`RunConfig` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `Arm` (e.g. with `Arm` and `EventFn`) actually correct?**
  _`Arm` has 18 INFERRED edges - model-reasoned connections that need verification._
- **Are the 17 inferred relationships involving `Workspace` (e.g. with `Arm` and `EventFn`) actually correct?**
  _`Workspace` has 17 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `TakerResult` (e.g. with `EventFn` and `JudgeFn`) actually correct?**
  _`TakerResult` has 14 INFERRED edges - model-reasoned connections that need verification._