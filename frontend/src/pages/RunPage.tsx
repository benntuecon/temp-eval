// Run page (SkillForge demo sequence): query form -> milestone flip cards +
// live K-band architecture graph -> aggregate batch stats -> per-case
// decision report -> onboarding + roadmap screens.
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import {
  api,
  subscribeEvents,
  type BatchCaseState,
  type BatchDetail,
  type BatchStats,
  type CreateBatchRequest,
} from "../api/client";
import { ARM_COLORS, type BatchQualityCostRow } from "../components/charts";
import { PipelineGraph } from "../components/PipelineGraph";
import { ResultsFunnel } from "../components/ResultsFunnel";
import { RunForm } from "../components/RunForm";
import { initialRunState, reduceEvent, type RunLiveState } from "../state/eventStore";

type MilestoneCard = {
  title: string;
  note: string;
  flipped: boolean;
  chips?: Array<{ label: string; value: string; met: boolean }>;
};

/** Real batch milestones drive the flip cards (no scripted fixtures). */
function batchMilestones(detail: BatchDetail | undefined, query: string): MilestoneCard[] {
  const cases = detail?.cases ?? [];
  const running = cases.filter((c) => c.status === "running").length;
  const terminal = cases.filter((c) => c.status === "completed" || c.status === "failed").length;
  const done = detail?.summary.status !== undefined && detail.summary.status !== "running";
  const ws = (detail?.stats?.win_summary ?? {}) as Record<string, number>;
  return [
    {
      title: "Cases retrieved",
      note: detail
        ? `vecDB matched ${cases.length} test case${cases.length === 1 ? "" : "s"} for "${query}".`
        : "The retriever embeds your query and pulls the top-K matching test cases.",
      flipped: !!detail,
    },
    {
      title: "Agents working",
      note: detail
        ? `${running} case${running === 1 ? "" : "s"} running now — two takers per case, one per skill.`
        : "Every case runs both skills head-to-head in isolated sandboxes.",
      flipped: running > 0 || terminal > 0,
    },
    {
      title: "Judges scoring",
      note: detail
        ? `${terminal}/${cases.length} cases judged across six criteria.`
        : "Twelve judges per case score both arms on an anchored 0–20 rubric.",
      flipped: terminal > 0,
    },
    {
      title: "Verdict",
      note: done ? "All cases aggregated — the decision report is ready below." : "Aggregates into one win summary across the whole batch.",
      flipped: done,
      chips: done
        ? [
            { label: "skill 1", value: `${ws.baseline ?? 0} wins`, met: (ws.baseline ?? 0) > (ws.challenger ?? 0) },
            { label: "skill 2", value: `${ws.challenger ?? 0} wins`, met: (ws.challenger ?? 0) >= (ws.baseline ?? 0) },
          ]
        : undefined,
    },
  ];
}

function MilestoneCards({ detail, query }: { detail: BatchDetail | undefined; query: string }) {
  const cards = batchMilestones(detail, query);
  const revealed = cards.filter((c) => c.flipped).length;
  const stage =
    !detail
      ? "Waiting for a run"
      : revealed === cards.length
        ? "All cards revealed"
        : `Revealing ${revealed} of ${cards.length}`;

  return (
    <section className="sketch-card bg-sketch-paper p-4" aria-label="Live batch milestones">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-hand text-lg font-bold text-sketch-ink">Milestones Reached</h3>
          <p className="text-xs font-semibold text-sketch-muted">
            Cards flip as the live batch eval moves from retrieval to verdict.
          </p>
        </div>
        <span className="sticky-note bg-sketch-yellow px-3 py-1 font-hand text-xs font-bold">
          {stage}
        </span>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        {cards.map((card, index) => (
          <div
            key={card.title}
            className={`flip-card ${card.flipped ? "is-flipped" : ""}`}
            style={{ transitionDelay: `${index * 120}ms` }}
          >
            <div className="flip-card-inner">
              <div className="flip-face flip-front">
                <span className="font-hand text-3xl">?</span>
                <span className="font-hand text-sm font-bold">hidden</span>
              </div>
              <div className="flip-face flip-back">
                <span className="font-hand text-sm font-bold">{card.title}</span>
                <span className="mt-1 text-xs font-semibold leading-4">{card.note}</span>
                {card.chips ? (
                  <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] font-bold">
                    {card.chips.map((chip) => (
                      <div
                        key={chip.label}
                        className={`requirement-verdict ${chip.met ? "is-met" : "is-missed"}`}
                      >
                        <span>{chip.label}</span>
                        <strong>{chip.value}</strong>
                      </div>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

/** Dark code block showing REAL live evidence for the hovered/clicked node. */
function NodeThinkingCodeBlock({
  nodeId,
  live,
  cases,
  selectedCaseId,
}: {
  nodeId: string | null;
  live: RunLiveState;
  cases: BatchCaseState[];
  selectedCaseId: string | null;
}) {
  let body = "// hover or click any node in the graph";
  let innerId = nodeId;
  let nodeCaseId: string | null = null;
  if (nodeId?.startsWith("case:")) nodeCaseId = nodeId.slice("case:".length);
  else if (nodeId?.includes("/")) {
    const slash = nodeId.indexOf("/");
    nodeCaseId = nodeId.slice(0, slash);
    innerId = nodeId.slice(slash + 1);
  }

  if (nodeId) {
    const c = nodeCaseId ? cases.find((x) => x.case_id === nodeCaseId) : undefined;
    if (nodeId.startsWith("case:") || (nodeCaseId && nodeCaseId !== selectedCaseId)) {
      body = c
        ? [
            `case: ${c.case_id} [${c.status}]`,
            c.distance != null ? `distance: ${Number(c.distance).toFixed(3)}` : null,
            c.baseline_total != null ? `scores: baseline ${c.baseline_total} · challenger ${c.challenger_total}` : null,
            c.verdict ?? null,
            "",
            c.description,
            "",
            "// click to attach the live stream to this case",
          ]
            .filter((l): l is string => l != null)
            .join("\n")
        : "// unknown case";
    } else if (innerId) {
      const buffer = live.buffers[innerId] ?? [];
      body =
        buffer.length > 0
          ? buffer
              .slice(-30)
              .map((e) => `[${e.kind}] ${e.text}`)
              .join("\n\n")
          : `// ${innerId}: nothing streamed yet (${live.nodeStatus[innerId] ?? "pending"})`;
    }
  }

  return (
    <aside
      className="thinking-code-card bg-sketch-ink text-sketch-paper"
      data-testid="node-panel"
      data-scroll-free
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="font-hand text-sm font-bold">Node thinking</span>
        <span className="font-hand rounded-[10px_8px_11px_7px] border border-sketch-paper/70 px-2 py-0.5 text-xs font-bold text-sketch-paper/80">
          {nodeId ?? "none"}
        </span>
      </div>
      <pre className="max-h-[460px] overflow-y-auto whitespace-pre-wrap break-words font-mono text-xs leading-5">
        {body}
      </pre>
    </aside>
  );
}

/** One dot per (case, arm): join the batch's score and token rows by case. */
function qualityCostRows(stats: BatchStats): BatchQualityCostRow[] {
  const tokensByCase = new Map(stats.tokens_per_case.map((r) => [String(r.case), r]));
  return stats.per_case_totals.flatMap((r) => {
    const t = tokensByCase.get(String(r.case));
    return (["baseline", "challenger"] as const).map((arm) => ({
      case: String(r.case),
      arm,
      score: Number(r[arm] ?? 0),
      tokens: Number(t?.[arm] ?? 0),
    }));
  });
}

function BarPair({
  label,
  baseline,
  challenger,
  max,
}: {
  label: string;
  baseline: number;
  challenger: number;
  max: number;
}) {
  const pct = (v: number) => `${max > 0 ? Math.min(100, (v / max) * 100) : 0}%`;
  return (
    <div className="mb-2">
      <div className="mb-0.5 flex justify-between text-xs font-semibold text-sketch-ink">
        <span className="truncate pr-2">{label}</span>
        <span className="shrink-0 tabular-nums">
          {baseline.toLocaleString()} vs {challenger.toLocaleString()}
        </span>
      </div>
      <div className="space-y-0.5">
        <div className="h-2 rounded-full border border-sketch-ink/30 bg-sketch-paper">
          <div className="h-full rounded-full" style={{ width: pct(baseline), background: ARM_COLORS.baseline }} />
        </div>
        <div className="h-2 rounded-full border border-sketch-ink/30 bg-sketch-paper">
          <div className="h-full rounded-full" style={{ width: pct(challenger), background: ARM_COLORS.challenger }} />
        </div>
      </div>
    </div>
  );
}

/** Aggregate batch stats in the SkillForge sticky-note language. */
function BatchStatsBoard({ stats, partial }: { stats: BatchStats; partial: boolean }) {
  const ws = stats.win_summary as Record<string, number>;
  const maxTokens = Math.max(
    1,
    ...stats.tokens_per_case.flatMap((r) => [Number(r.baseline ?? 0), Number(r.challenger ?? 0)]),
  );
  return (
    <div className="space-y-4" data-testid="batch-stats">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="font-hand text-2xl font-bold text-sketch-ink">Batch scoreboard</h3>
        {partial && (
          <span className="sticky-note rotate-[0.5deg] bg-sketch-yellow px-2 py-0.5 font-hand text-xs font-bold">
            partial — runs still in flight
          </span>
        )}
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="sticky-note rotate-[-1deg] bg-sketch-pink p-3 text-center">
          <div className="font-hand text-3xl font-bold">{ws.baseline ?? 0}</div>
          <div className="font-hand text-xs font-bold">skill 1 wins</div>
        </div>
        <div className="sticky-note rotate-[1deg] bg-sketch-yellow p-3 text-center">
          <div className="font-hand text-3xl font-bold">{ws.tie ?? 0}</div>
          <div className="font-hand text-xs font-bold">ties</div>
        </div>
        <div className="sticky-note rotate-[-2deg] bg-sketch-blue p-3 text-center">
          <div className="font-hand text-3xl font-bold">{ws.challenger ?? 0}</div>
          <div className="font-hand text-xs font-bold">skill 2 wins</div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div className="sketch-card bg-sketch-paper p-4">
          <h4 className="font-hand mb-3 text-sm font-bold text-sketch-muted">
            AVG SCORE PER CRITERION (0–20)
          </h4>
          {stats.criterion_gap.map((r) => (
            <BarPair
              key={String(r.criterion)}
              label={`${r.criterion} (gap ${Number(r.gap) > 0 ? "+" : ""}${r.gap})`}
              baseline={Number(r.baseline ?? 0)}
              challenger={Number(r.challenger ?? 0)}
              max={20}
            />
          ))}
        </div>
        <div className="sketch-card bg-sketch-paper p-4">
          <h4 className="font-hand mb-3 text-sm font-bold text-sketch-muted">
            TOTAL SCORE PER CASE (0–120)
          </h4>
          {stats.per_case_totals.map((r) => (
            <BarPair
              key={String(r.case)}
              label={String(r.case)}
              baseline={Number(r.baseline ?? 0)}
              challenger={Number(r.challenger ?? 0)}
              max={120}
            />
          ))}
        </div>
        <div className="sketch-card bg-sketch-paper p-4 lg:col-span-2">
          <h4 className="font-hand mb-3 text-sm font-bold text-sketch-muted">
            TOKENS SPENT PER CASE
          </h4>
          {stats.tokens_per_case.map((r) => (
            <BarPair
              key={String(r.case)}
              label={String(r.case)}
              baseline={Number(r.baseline ?? 0)}
              challenger={Number(r.challenger ?? 0)}
              max={maxTokens}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

const SKILLFORGE_ONBOARDING_MARKDOWN = `Name
onboarding-to-skillforge

Description
Send your agent to SkillForge: consolidate skills, pick a challenger pair, and launch a live eval to decide what to keep, restrict, or retest.

User invocable
true

Onboarding to SkillForge
SkillForge is an eval lab that runs controlled head-to-head experiments between two skills (a baseline and a challenger) so you can decide: keep, restrict, or retest — rather than letting every new skill silently degrade agent accuracy.

Usage: /onboarding-to-skillforge [--skill-dir <path>] [--query <text>]

ARGUMENTS: $ARGUMENTS

Why this matters
Every skill added to an agent rides in context on every call. Research shows accuracy drops up to 85% as skill catalogues grow, and agents pick the right skill only 13% of the time without filtering. SkillForge retrieves the top-K matching test cases from its vector DB and races both skills on every one of them, live.

Flow
Step 1 — Inventory your skills
List every skill the agent currently has loaded. For each skill, capture:

Name — the name: field from its SKILL.md frontmatter
Description — the description: field
Path — the file path to the SKILL.md
If --skill-dir was passed, scan that directory. Otherwise scan ~/.claude/skills/ and any project-local .claude/skills/ directories.

Output a numbered list so the user can pick two skills to compare.

Step 2 — Choose baseline and challenger
Ask the user (or infer from $ARGUMENTS) which two skills to compare:

Baseline skill — the existing trusted skill (skill 1)
Challenger skill — the new or suspected-redundant skill (skill 2)
If the user hasn't decided yet, suggest pairs by looking for skills with overlapping descriptions or similar task domains.

Step 3 — Write the retrieval query
Describe the kind of work the skills target (domain, team, symptoms). SkillForge embeds the query and pulls the top-K matching test cases — each case carries its own task description, before-repo, and gold after-repo.

Step 4 — Package the eval payload
Construct the eval payload:

{
  "query": "<retrieval query>",
  "top_k": 10,
  "baseline": {
    "name": "<baseline skill name>",
    "markdown": "<full contents of baseline SKILL.md>"
  },
  "challenger": {
    "name": "<challenger skill name>",
    "markdown": "<full contents of challenger SKILL.md>"
  },
  "wall_clock_seconds": 180
}

Read the actual SKILL.md content for both skills — do not summarize.

Step 5 — Send to SkillForge
Open the SkillForge Eval Lab in the browser. Pre-fill the form fields:

Retrieval query → your query
Baseline skill name + SKILL.md content
Challenger skill name + SKILL.md content
If browser automation is unavailable, output the payload as a formatted block the user can paste directly into the SkillForge UI.

Step 6 — Report the batch results
Once the batch completes, read the scoreboard:

Metric	Baseline	Challenger
case wins	n	n
avg criterion scores	0-20	0-20
tokens per case	count	count

Then give a one-sentence recommendation per skill:

Keep — challenger wins the case majority with cleaner diffs; promote it
Restrict — challenger wins some domains but loses others; scope it
Retest — unclear signal; refine the retrieval query and run again
Prune — baseline and challenger overlap heavily; drop the weaker one

Decision heuristics
If the challenger wins most cases and costs fewer tokens → promote challenger, archive baseline
If wins split by domain → restrict each skill to the domains it wins
If neither separates → the test cases may be under-discriminating, not the skills

What to skip
Do not summarize SKILL.md content when sending to SkillForge — send the full text
Do not auto-prune without user confirmation
Do not run evals on more than two skills at a time; SkillForge is pairwise by design

Related
RAG-MCP 2025 — skill-selection accuracy research
LongFuncEval (Kate et al.) — accuracy decay with catalogue size
PromptDebt (EASE 2025) — prompt & skill config as #1 LLM technical debt source`;

function OnboardingRoadmap() {
  return (
    <section className="demo-screen demo-screen-panel sketch-card onboarding-screen bg-sketch-paper p-5" aria-label="Onboarding to SkillForge">
      <div className="onboarding-code-area">
        <pre className="onboarding-code-block" data-scroll-free>
          <code>{SKILLFORGE_ONBOARDING_MARKDOWN}</code>
        </pre>
      </div>
      <div className="onboarding-cta-area">
        <div className="onboarding-cta font-hand">
          Onboarding to SkillForge Now
        </div>
      </div>
    </section>
  );
}

function FutureRoadmapScreen() {
  return (
    <section className="demo-screen demo-screen-panel sketch-card future-roadmap-screen bg-sketch-paper p-5" aria-label="Future roadmaps">
      <h2 className="future-roadmap-title font-hand">
        Future Roadmaps
      </h2>
      <div className="future-roadmap-grid mt-5">
        <article className="future-roadmap-card">
          <div className="future-roadmap-number font-hand">1</div>
          <div>
            <h3 className="font-hand text-xl font-bold">Configurable Judge Groups</h3>
            <p className="mt-3 text-sm font-semibold leading-6">
              Allow teams to define and prioritize the evaluation criteria that matter most to their skills,
              making SkillForge assessments more flexible, targeted, and use-case specific.
            </p>
          </div>
        </article>
        <article className="future-roadmap-card">
          <div className="future-roadmap-number font-hand">2</div>
          <div>
            <h3 className="font-hand text-xl font-bold">JPMC Skills Marketplace Integration</h3>
            <p className="mt-3 text-sm font-semibold leading-6">
              Connect SkillForge with the JPMC Skills Marketplace to establish a consistent quality evaluation
              and pruning framework for skills across the JPMC Agentic AI ecosystem.
            </p>
          </div>
        </article>
      </div>
      <div className="future-qa font-hand" aria-label="Q and A">
        Q&amp;A
      </div>
    </section>
  );
}

export function RunPage({ navSlot }: { navSlot?: ReactNode }) {
  const [batchId, setBatchId] = useState<string | null>(null);
  const [activeQuery, setActiveQuery] = useState("");
  const [selectedCase, setSelectedCase] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [live, setLive] = useState<RunLiveState>(initialRunState);
  const [error, setError] = useState<string | null>(null);

  const detail = useQuery({
    queryKey: ["batch", batchId],
    queryFn: () => api.batchDetail(batchId!),
    enabled: !!batchId,
    refetchInterval: (q) => (q.state.data?.summary.status === "running" ? 2000 : false),
  });
  const running = detail.data?.summary.status === "running";

  // Auto-open the first launched case so the pipeline lights up immediately.
  useEffect(() => {
    if (selectedCase || !detail.data) return;
    const first = detail.data.cases.find((c) => c.run_id);
    if (first) setSelectedCase(first.case_id);
  }, [detail.data, selectedCase]);

  // Attach the SSE stream to the selected case's child run (replays history).
  const selected = detail.data?.cases.find((c) => c.case_id === selectedCase);
  const selectedRunId = selected?.run_id ?? null;
  useEffect(() => {
    setLive(initialRunState());
    if (!selectedRunId) return;
    return subscribeEvents(selectedRunId, (ev) => setLive((s) => reduceEvent(s, ev)));
  }, [selectedRunId]);

  // The selected case's full decision report, once it has been judged.
  const caseDetail = useQuery({
    queryKey: ["run", selectedRunId, selected?.status],
    queryFn: () => api.runDetail(selectedRunId!),
    enabled: selectedRunId != null && selected?.status === "completed",
  });
  const report = caseDetail.data?.report;

  async function startAndShowReplay(req: CreateBatchRequest) {
    setError(null);
    try {
      const { batch_id } = await api.createBatch(req);
      setActiveQuery(req.query);
      setSelectedCase(null);
      setSelectedNode(null);
      setBatchId(batch_id);
      window.setTimeout(() => {
        document.querySelector<HTMLElement>('[data-screen="replay"]')?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 180);
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <div className="space-y-4">
      {/* SCREEN 2: Eval setup. Show Eval Lab / Run History tabs, explain the
          experiment, then end this screen at the Run eval button. */}
      <section className="demo-screen demo-screen-panel space-y-4">
        {navSlot}
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="sketch-card bg-sketch-paper p-4">
            <div className="font-hand text-sm font-bold text-sketch-muted">Experiment question</div>
            <h2 className="font-hand mt-1 text-2xl font-bold leading-tight">
              Should this skill become a trusted default, or is it just more context debt?
            </h2>
            <p className="mt-2 text-sm font-semibold leading-6">
              Describe the work; the vector DB retrieves the matching test cases. Every case
              races both skills live — questions asked, code changed, judges convinced.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="sticky-note rotate-[-1deg] bg-sketch-pink p-3">
              <div className="font-hand text-sm font-bold">Input</div>
              <div className="font-hand mt-2 text-3xl">✎</div>
              <p className="mt-2 text-xs font-semibold">One query, K test cases.</p>
            </div>
            <div className="sticky-note rotate-[1deg] bg-sketch-blue p-3">
              <div className="font-hand text-sm font-bold">Replay</div>
              <div className="font-hand mt-2 text-3xl">↝</div>
              <p className="mt-2 text-xs font-semibold">K live agent pipelines.</p>
            </div>
            <div className="sticky-note rotate-[-2deg] bg-sketch-green p-3">
              <div className="font-hand text-sm font-bold">Decision</div>
              <div className="font-hand mt-2 text-3xl">✓</div>
              <p className="mt-2 text-xs font-semibold">Keep, restrict, retest.</p>
            </div>
          </div>
        </div>

        <RunForm running={!!running} onSubmit={startAndShowReplay} />

        {error ? (
          <div className="sticky-note rotate-[-0.5deg] bg-sketch-pink p-3 text-sm font-semibold text-sketch-ink">
            Could not start the batch: {error}
          </div>
        ) : null}
        {detail.error != null ? (
          <div className="sticky-note rotate-[0.5deg] bg-sketch-pink p-3 text-sm font-semibold text-sketch-ink">
            Batch status fetch failing: {String(detail.error)}
          </div>
        ) : null}
      </section>

      {/* SCREEN 3: Milestones + behavior replay across all K case bands. */}
      <section className="demo-screen demo-screen-panel space-y-4" data-screen="replay">
        <MilestoneCards detail={detail.data} query={activeQuery} />
        <h2 className="font-hand mb-2 text-lg font-bold text-sketch-ink">
          Behavior replay{" "}
          <span className="text-sm font-semibold text-sketch-muted">
            — every retrieved case gets its own pipeline; click a band to attach its live stream
          </span>
        </h2>
        <div className="behavior-replay-grid">
          <PipelineGraph
            state={live}
            onSelectNode={setSelectedNode}
            batch={{
              query: activeQuery,
              cases: detail.data?.cases ?? [],
              selectedCaseId: selectedCase,
              onSelectCase: setSelectedCase,
            }}
          />
          <NodeThinkingCodeBlock
            nodeId={selectedNode}
            live={live}
            cases={detail.data?.cases ?? []}
            selectedCaseId={selectedCase}
          />
        </div>
      </section>

      {/* SCREEN 4: Aggregate batch scoreboard — the one result. */}
      {detail.data?.stats ? (
        <section className="demo-screen demo-screen-panel">
          <BatchStatsBoard
            stats={detail.data.stats}
            partial={detail.data.summary.status === "running"}
          />
        </section>
      ) : null}

      {/* SCREEN 5: Per-case decision report for the case being watched. */}
      {report ? (
        <section className="demo-screen demo-screen-panel">
          <div className="font-hand mb-2 text-sm font-bold text-sketch-muted">
            Decision report — case {selected?.case_id}
          </div>
          <ResultsFunnel
            report={report}
            batchQualityCost={detail.data?.stats ? qualityCostRows(detail.data.stats) : undefined}
          />
        </section>
      ) : null}

      {/* SCREEN 6 + 7: onboarding and future roadmap close the presentation. */}
      <OnboardingRoadmap />
      <FutureRoadmapScreen />
    </div>
  );
}
