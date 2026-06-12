# Graph Report - skill-eval  (2026-06-11)

## Corpus Check
- 111 files · ~59,755 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1126 nodes · 2378 edges · 84 communities (76 shown, 8 thin omitted)
- Extraction: 82% EXTRACTED · 18% INFERRED · 0% AMBIGUOUS · INFERRED: 418 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `4e62f4f4`
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
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 83|Community 83]]

## God Nodes (most connected - your core abstractions)
1. `RunConfig` - 80 edges
2. `RunMetrics` - 66 edges
3. `ComparisonReport` - 50 edges
4. `TakerResult` - 47 edges
5. `Workspace` - 44 edges
6. `Arm` - 42 edges
7. `RunManager` - 40 edges
8. `JudgeScore` - 37 edges
9. `JudgeInput` - 34 edges
10. `run_taker()` - 32 edges

## Surprising Connections (you probably didn't know these)
- `_FakeResult` --uses--> `Arm`  [INFERRED]
  tests/test_taker.py → skill_eval/contracts.py
- `_FakeResult` --uses--> `StopReason`  [INFERRED]
  tests/test_taker.py → skill_eval/contracts.py
- `test_runconfig_defaults_and_frozen()` --calls--> `RunConfig`  [EXTRACTED]
  tests/test_contracts.py → skill_eval/contracts.py
- `_FakeResult` --uses--> `RunConfig`  [INFERRED]
  tests/test_taker.py → skill_eval/contracts.py
- `Any` --uses--> `RunConfig`  [INFERRED]
  tests/test_taker.py → skill_eval/contracts.py

## Import Cycles
- 1-file cycle: `skill_eval/api/app.py -> skill_eval/api/app.py`

## Communities (84 total, 8 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (70): create_app(), _default_runs_dir(), _fixtures(), _flagship_skill(), FastAPI service exposing the skill-eval agent layer.  Run with:     just api, Build the FastAPI app. ``init_tracing=False`` keeps tests offline., _fixture_builder(), In-process run execution: one asyncio task per eval run.  Events are buffered in (+62 more)

### Community 1 - "Community 1"
Cohesion: 0.15
Nodes (27): Send, ArmReport, Criterion, JudgeInput, JudgeScore, Everything one judge needs to score one criterion for one taker., A single judge's 0-20 score plus rationale., Aggregated result for one arm (one model). (+19 more)

### Community 2 - "Community 2"
Cohesion: 0.17
Nodes (33): ResultMessage, RunMetrics, Arm, prepare_workspaces(), AskFn, Everything one taker produced, ready for judging., Which skill a test-taker is running., Component 1: create git worktrees and compute the gold diff. (+25 more)

### Community 3 - "Community 3"
Cohesion: 0.09
Nodes (21): 10. Build order & parallelization plan, 11. Out of scope (YAGNI for the hackathon), 12. Risks & open questions, 1. Goal, 2. Inputs & Outputs, 3. Architecture — two layers, 4. Tech stack & rationale, 5. Components (+13 more)

### Community 4 - "Community 4"
Cohesion: 0.12
Nodes (30): _build_prompt(), JudgeInput, Build the judge prompt for a single criterion evaluation.      This is a pure fu, _ji(), _metrics(), Taker questions must appear verbatim in the prompt., When the taker asked nothing, the prompt should say so explicitly., question_quality prompt must include a concrete anchor descriptor. (+22 more)

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
Cohesion: 0.10
Nodes (48): InMemorySpanExporter, _parse_response(), C5: Real judge backed by claude-haiku-4-5.  Scores one criterion for one taker r, Extract (score, rationale) from the model response.      Tries json.loads on the, Score one criterion for one taker result on a 0-20 anchored rubric.      Paramet, run_judge(), _build_gold_context(), make_simulator() (+40 more)

### Community 12 - "Community 12"
Cohesion: 0.20
Nodes (9): Architecture (service), Dev, How it works, Layout, Measurement validity, Quickstart, skill-eval, The headline result (+1 more)

### Community 16 - "Community 16"
Cohesion: 0.07
Nodes (28): CalledProcessError, add_all(), commit(), config(), diff(), diff_cached(), diff_workdir(), init() (+20 more)

### Community 19 - "Community 19"
Cohesion: 0.06
Nodes (57): _compute_diff(), _metrics_from_result(), Extract ``RunMetrics`` from the final ``ResultMessage``., Map SDK fields to a ``StopReason`` enum value.      ``max_tokens`` is a best-eff, Stage all changes and return the diff against the starting commit.      Diffs ag, _stop_reason(), _fake_query_gen(), _FakeResult (+49 more)

### Community 20 - "Community 20"
Cohesion: 0.10
Nodes (32): Run *cfgs* through run_eval concurrently; return reports in input order.      Ar, run_batch(), _add_skills(), build_sample_cases(), _flagship_skill_text(), _init_repo(), _make_case(), Path (+24 more)

### Community 21 - "Community 21"
Cohesion: 0.06
Nodes (51): api, ArmReport, ComparisonReport, CreateRunRequest, FixtureInfo, JudgeScore, RunDetail, RunEvent (+43 more)

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

### Community 29 - "Community 29"
Cohesion: 0.15
Nodes (17): criterion_gap_rows(), criterion_winners(), ComparisonReport, quality_cost_rows(), Return one row per Criterion with the per-criterion winner and margin.      Each, Return one row per arm pairing quality (total score) against cost.      Each row, Return one row per Criterion with a score column per arm.      Each row is ``{"c, Re-derive the winner from total scores and return a human-readable verdict. (+9 more)

### Community 30 - "Community 30"
Cohesion: 0.20
Nodes (14): arm_color_list(), batch_criterion_gap_rows(), batch_per_case_totals(), batch_per_criterion_avg(), Return one row per report with ``case``, ``baseline``, and ``challenger`` totals, Return a colour per column in ``columns`` order (for ``st.bar_chart``)., Return one row per Criterion with average baseline and challenger scores.      A, Return per-Criterion average baseline, challenger, and gap across a batch. (+6 more)

### Community 31 - "Community 31"
Cohesion: 0.18
Nodes (11): list_saved_runs(), load_report(), Return saved run files, newest first: ``{"name", "path"}`` per run., Load one saved run back into a ComparisonReport., Per-(criterion, arm) score deltas between two runs (B − A).      The Langfuse co, run_delta_rows(), _make_report(), Build a fake ComparisonReport with deterministic scores. (+3 more)

### Community 32 - "Community 32"
Cohesion: 0.09
Nodes (36): Arm, make_simulator(), Shared data contracts for the skill-eval harness.  This is the single integratio, Component 3: build the AskFn the simulator uses to answer questions., git_ops — the sole git shell-out point for skill-eval.  All functions accept a *, build_sample_repo(), RunConfig, cleanup_workspaces() (+28 more)

### Community 33 - "Community 33"
Cohesion: 0.29
Nodes (7): batch_score_distribution(), Return long-form rows for per-criterion, per-arm score distributions.      Each, len(reports) * 12 rows (2 arms × 6 criteria per report)., Every row has criterion, arm, and score keys., test_batch_score_distribution_empty(), test_batch_score_distribution_row_count(), test_batch_score_distribution_schema()

### Community 34 - "Community 34"
Cohesion: 0.29
Nodes (7): log_judge_evaluations(), Log per-judge scores to Phoenix as span evaluations.      Parameters     -------, client(), Should return False (or at minimum not raise) when no Phoenix is running., Empty records: no crash, returns False., test_log_judge_evaluations_best_effort_no_phoenix(), test_log_judge_evaluations_empty()

### Community 35 - "Community 35"
Cohesion: 0.33
Nodes (6): agent_graph_dot(), Return a Graphviz DOT digraph of the WHOLE eval architecture, live.      Flow: t, Build a sample state and verify the returned DOT string., meta enriches hover tooltips: skill names, rationales, verdict., test_agent_graph_dot(), test_agent_graph_dot_meta_tooltips()

### Community 36 - "Community 36"
Cohesion: 0.06
Nodes (31): dependencies, react, react-dom, react-vega, @tanstack/react-query, vega, vega-lite, @xyflow/react (+23 more)

### Community 37 - "Community 37"
Cohesion: 0.17
Nodes (17): ComparisonReport, EventFn, JudgeFn, MakeSimulator, RunConfig, TakerFn, Concurrent batch runner for skill-eval.  Runs multiple RunConfigs through run_ev, ComparisonReport (+9 more)

### Community 38 - "Community 38"
Cohesion: 0.13
Nodes (14): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noEmit, noUnusedLocals (+6 more)

### Community 39 - "Community 39"
Cohesion: 0.10
Nodes (19): Anti-pattern gallery — these are defects, never models to imitate, ❌ Banner / decoration logging, ❌ Entry/exit announcements and variable dumps, ❌ Everything at one level / secrets in messages, ❌ Narrative / verbal logging, ❌ Per-iteration progress lines, Process (follow every step; do not skip), Production Logging Discipline (+11 more)

### Community 40 - "Community 40"
Cohesion: 0.17
Nodes (11): Architecture, Backend (`skill_eval/api/`), Contracts (`skill_eval/contracts.py` → Pydantic v2), Decisions (user-confirmed), Dev workflow, Error handling, Frontend (`frontend/`), Goal (+3 more)

### Community 41 - "Community 41"
Cohesion: 0.15
Nodes (9): OutOfStockError, place_order(), Checkout flow — retail storefront team.  Logging configuration belongs to the ap, _reserve_inventory(), OutOfStockError, place_order(), Checkout flow — retail storefront team., _reserve_inventory() (+1 more)

### Community 42 - "Community 42"
Cohesion: 0.18
Nodes (10): Banners make logs scannable, Dump full state — redaction loses evidence, f-strings everywhere, configure wherever, Just Log It, Log entry, exit, and everything in between, Narrate the story — verbal logging, Never let an error crash the service, One level is enough (+2 more)

### Community 43 - "Community 43"
Cohesion: 0.18
Nodes (10): FastAPI + React Service Implementation Plan, Task 1: contracts.py → Pydantic v2, Task 2: event union + API schemas, Task 3: arun_eval + taker thinking/tool/Q&A event forwarding, Task 4: FastAPI app + RunManager + SSE + tests, Task 5: frontend scaffold + generated client, Task 6: Run page — form + live graph + thinking panel, Task 7: results funnel + History (+2 more)

### Community 44 - "Community 44"
Cohesion: 0.16
Nodes (13): batch_win_summary(), _esc(), init_phoenix(), Reporting helpers and Phoenix initialisation for the skill-eval dashboard.  Pure, Serialise a ComparisonReport to pretty-printed JSON (Pydantic)., Persist a report as ``<runs_dir>/<ts>_<label>_<suffix>.json``; return the path., Count wins for challenger, baseline, and ties across a batch of reports.      Co, Escape a string for use inside a double-quoted DOT attribute. (+5 more)

### Community 45 - "Community 45"
Cohesion: 0.27
Nodes (10): app_server(), _hover_node(), _open(), Browser-level E2E: Playwright + real Chromium against the real stack (FastAPI on, Launch uvicorn + vite dev for the session; tear both down after., Hover a React Flow node via raw mouse coords (the canvas is transformed,     whi, test_app_loads_with_pipeline_graph(), test_history_lists_and_renders_archived_run() (+2 more)

### Community 46 - "Community 46"
Cohesion: 0.23
Nodes (18): _build_graph(), _emit(), _EvalState, _fan_out_judges(), _fan_out_takers(), _get_tracer(), _node_assemble(), _node_judge() (+10 more)

### Community 47 - "Community 47"
Cohesion: 0.29
Nodes (8): _find_user(), _hash(), login(), logout(), Login and session service — identity & access team., First 8 chars are enough to correlate a session without exposing it., _token_prefix(), validate_session()

### Community 48 - "Community 48"
Cohesion: 0.24
Nodes (7): capture_payment(), _mask_pan(), Payment capture service — global banking platform., Last 4 digits only — full PANs must never reach the logs., refund_payment(), _send_refund(), _send_to_gateway()

### Community 49 - "Community 49"
Cohesion: 0.27
Nodes (6): _deliver(), _mask_email(), Email/SMS notification dispatcher — growth & comms team., a***@example.com — enough to investigate, not enough to leak PII., send_campaign(), _send_with_retry()

### Community 50 - "Community 50"
Cohesion: 0.31
Nodes (4): _find_user(), _hash(), login(), Login and session service — identity & access team.

### Community 51 - "Community 51"
Cohesion: 0.33
Nodes (5): components, $defs, operations, paths, webhooks

### Community 52 - "Community 52"
Cohesion: 0.28
Nodes (5): capture_payment(), Payment capture service — global banking platform., refund_payment(), _send_refund(), _send_to_gateway()

### Community 53 - "Community 53"
Cohesion: 0.33
Nodes (6): Serialise a batch of ComparisonReports to one JSON array., Reconstruct a ComparisonReport (real models/enums) from JSON.      Pydantic hand, report_from_json(), reports_to_json(), test_report_json_round_trip_reconstructs_dataclasses(), test_reports_to_json_is_array()

### Community 54 - "Community 54"
Cohesion: 0.40
Nodes (4): after, before, description, repo

### Community 55 - "Community 55"
Cohesion: 0.40
Nodes (4): after, before, description, repo

### Community 56 - "Community 56"
Cohesion: 0.40
Nodes (4): after, before, description, repo

### Community 57 - "Community 57"
Cohesion: 0.40
Nodes (4): after, before, description, repo

### Community 58 - "Community 58"
Cohesion: 0.40
Nodes (4): after, before, description, repo

### Community 59 - "Community 59"
Cohesion: 0.40
Nodes (4): after, before, description, repo

### Community 60 - "Community 60"
Cohesion: 0.40
Nodes (4): after, before, description, repo

### Community 61 - "Community 61"
Cohesion: 0.40
Nodes (4): after, before, description, repo

### Community 62 - "Community 62"
Cohesion: 0.40
Nodes (4): after, before, description, repo

### Community 63 - "Community 63"
Cohesion: 0.40
Nodes (4): after, before, description, repo

### Community 64 - "Community 64"
Cohesion: 0.43
Nodes (7): chunked(), dedupe_orders(), load(), normalize_country(), Nightly customer-orders ETL — data engineering team., run_pipeline(), transform_row()

### Community 65 - "Community 65"
Cohesion: 0.43
Nodes (5): Fraud-score model inference service — ML platform team., _run_model(), score_batch(), score_request(), warmup()

### Community 66 - "Community 66"
Cohesion: 0.32
Nodes (4): _crosses(), _publish_fills(), Order matching engine — fintech trading desk., submit_order()

### Community 67 - "Community 67"
Cohesion: 0.43
Nodes (7): chunked(), dedupe_orders(), load(), normalize_country(), Nightly customer-orders ETL — data engineering team., run_pipeline(), transform_row()

### Community 68 - "Community 68"
Cohesion: 0.43
Nodes (5): Fraud-score model inference service — ML platform team., _run_model(), score_batch(), score_request(), warmup()

### Community 69 - "Community 69"
Cohesion: 0.32
Nodes (4): _crosses(), _publish_fills(), Order matching engine — fintech trading desk., submit_order()

### Community 70 - "Community 70"
Cohesion: 0.32
Nodes (4): _deliver(), Email/SMS notification dispatcher — growth & comms team., send_campaign(), _send_with_retry()

### Community 71 - "Community 71"
Cohesion: 0.33
Nodes (3): needs_reorder(), Warehouse inventory sync — logistics team., reorder_report()

### Community 73 - "Community 73"
Cohesion: 0.33
Nodes (3): needs_reorder(), Warehouse inventory sync — logistics team., reorder_report()

### Community 75 - "Community 75"
Cohesion: 0.40
Nodes (3): firmware_supported(), parse_firmware(), Device telemetry ingestor — IoT platform team.

### Community 76 - "Community 76"
Cohesion: 0.40
Nodes (3): firmware_supported(), parse_firmware(), Device telemetry ingestor — IoT platform team.

### Community 79 - "Community 79"
Cohesion: 0.39
Nodes (6): build_flagship_case(), RunConfig, _commit_exists(), Return file contents at a given commit, or None if the file doesn't exist., _show_file(), test_build_flagship_case()

### Community 83 - "Community 83"
Cohesion: 0.36
Nodes (7): _make_repo(), Path, Tests for skill_eval/git_ops.py — no network calls required., Initialise a repo with git identity configured., 16 threads calling worktree_add concurrently must all succeed., test_concurrent_worktree_add(), test_repo_roundtrip()

## Knowledge Gaps
- **253 isolated node(s):** `PreToolUse`, `allow`, `name`, `private`, `version` (+248 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **8 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RunConfig` connect `Community 37` to `Community 0`, `Community 1`, `Community 32`, `Community 2`, `Community 11`, `Community 44`, `Community 46`, `Community 79`, `Community 19`, `Community 20`, `Community 53`, `Community 29`, `Community 30`, `Community 31`?**
  _High betweenness centrality (0.046) - this node is a cross-community bridge._
- **Why does `RunMetrics` connect `Community 0` to `Community 32`, `Community 1`, `Community 2`, `Community 4`, `Community 37`, `Community 11`, `Community 44`, `Community 19`, `Community 53`, `Community 29`, `Community 30`, `Community 31`?**
  _High betweenness centrality (0.041) - this node is a cross-community bridge._
- **Why does `RunManager` connect `Community 0` to `Community 37`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Are the 49 inferred relationships involving `RunConfig` (e.g. with `RunManager` and `RunState`) actually correct?**
  _`RunConfig` has 49 INFERRED edges - model-reasoned connections that need verification._
- **Are the 38 inferred relationships involving `RunMetrics` (e.g. with `RunManager` and `RunState`) actually correct?**
  _`RunMetrics` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 31 inferred relationships involving `ComparisonReport` (e.g. with `RunManager` and `RunState`) actually correct?**
  _`ComparisonReport` has 31 INFERRED edges - model-reasoned connections that need verification._
- **Are the 27 inferred relationships involving `TakerResult` (e.g. with `ResultMessage` and `RunMetrics`) actually correct?**
  _`TakerResult` has 27 INFERRED edges - model-reasoned connections that need verification._