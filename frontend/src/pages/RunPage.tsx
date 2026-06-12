// Run page: form -> live architecture graph + click-driven thinking code block -> results.
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, subscribeEvents, type ComparisonReport, type CreateRunRequest } from "../api/client";
import { PipelineGraph } from "../components/PipelineGraph";
import { ResultsFunnel } from "../components/ResultsFunnel";
import { RunForm } from "../components/RunForm";
import { subscribeMockRun } from "../mockRun";
import { initialRunState, reduceEvent, type RunLiveState } from "../state/eventStore";

type RequirementCard = {
  title: string;
  note: string;
  skill1: "met" | "not met";
  skill2: "met" | "not met";
};

function discoveryCards(req: CreateRunRequest | null) {
  const brief = req?.task_brief.toLowerCase() ?? "";
  if (brief.includes("prorate_refund")) {
    return [
      {
        title: "Month length",
        note: "30-day denominator must be confirmed before implementation.",
        skill1: "not met",
        skill2: "met",
      },
      {
        title: "Same-day cancel",
        note: "days_used <= 0 should return the full amount.",
        skill1: "not met",
        skill2: "met",
      },
      {
        title: "Rounding rule",
        note: "Money should use the product's cent rounding policy.",
        skill1: "not met",
        skill2: "met",
      },
      {
        title: "Clamp behavior",
        note: "days_used >= 30 should never produce a negative refund.",
        skill1: "not met",
        skill2: "met",
      },
    ];
  }
  if (brief.includes("add(a, b)")) {
    return [
      {
        title: "Signature",
        note: "Keep add(a, b) unchanged.",
        skill1: "met",
        skill2: "met",
      },
      {
        title: "Semantic fix",
        note: "Change the broken operator only.",
        skill1: "met",
        skill2: "met",
      },
      {
        title: "Test target",
        note: "Make add(2, 3) return 5.",
        skill1: "met",
        skill2: "met",
      },
      {
        title: "Overhead check",
        note: "Do not add extra process to an obvious one-line fix.",
        skill1: "met",
        skill2: "not met",
      },
    ];
  }
  return [
    {
      title: "Public contract",
      note: "Preserve the interface unless told otherwise.",
      skill1: "not met",
      skill2: "met",
    },
    {
      title: "Acceptance behavior",
      note: "Find the observable target behavior.",
      skill1: "not met",
      skill2: "met",
    },
    {
      title: "Boundaries",
      note: "Check edge cases before shipping.",
      skill1: "not met",
      skill2: "met",
    },
    {
      title: "Change scope",
      note: "Avoid unrelated refactors.",
      skill1: "not met",
      skill2: "met",
    },
  ] satisfies RequirementCard[];
}

function discoveryProgress(live: RunLiveState): number {
  if (live.runStatus === "completed") return 4;
  const anyJudgeRunning = Object.values(live.judges).some((j) => j.status === "running" || j.status === "done");
  const takersDone = ["baseline", "challenger"].some((arm) => live.takers[arm]?.status === "done");
  if (anyJudgeRunning || live.nodeStatus.assemble === "running" || live.nodeStatus.report === "done") return 4;
  if (takersDone || live.questionCount > 0 || live.nodeStatus.simulator === "running") return 3;
  if (live.nodeStatus.sandbox === "running" || live.nodeStatus.sandbox === "done") return 2;
  if (live.nodeStatus.test_generator === "running" || live.nodeStatus.test_cases === "done") return 1;
  return 0;
}

function LiveDiscoveryCards({ live, request }: { live: RunLiveState; request: CreateRunRequest | null }) {
  const progress = discoveryProgress(live);
  const cards = discoveryCards(request);
  const stage =
    live.runStatus === "idle"
      ? "Waiting for a run"
      : live.runStatus === "completed"
        ? "All cards revealed"
        : `Revealing ${progress} of ${cards.length}`;

  return (
    <section className="sketch-card bg-sketch-paper p-4" aria-label="Live requirement discovery">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h3 className="font-hand text-lg font-bold text-sketch-ink">Milestones Reached</h3>
          <p className="text-xs font-semibold text-sketch-muted">
            Cards flip as the live eval reveals whether each skill satisfied the hidden requirement.
          </p>
        </div>
        <span className="sticky-note bg-sketch-yellow px-3 py-1 font-hand text-xs font-bold">
          {stage}
        </span>
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
        {cards.map((card, index) => {
          const flipped = index < progress;
          return (
            <div
              key={card.title}
              className={`flip-card ${flipped ? "is-flipped" : ""}`}
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
                  <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] font-bold">
                    <div className={`requirement-verdict ${card.skill1 === "met" ? "is-met" : "is-missed"}`}>
                      <span>skill 1</span>
                      <strong>{card.skill1}</strong>
                    </div>
                    <div className={`requirement-verdict ${card.skill2 === "met" ? "is-met" : "is-missed"}`}>
                      <span>skill 2</span>
                      <strong>{card.skill2}</strong>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function nodeProcessName(nodeId: string | null): string {
  if (!nodeId) return "select_a_node";
  return nodeId.replace(/[^a-zA-Z0-9]+/g, "_").replace(/^_+|_+$/g, "").toLowerCase();
}

function NodeThinkingCodeBlock({ nodeId }: { nodeId: string | null }) {
  const processName = nodeProcessName(nodeId);
  return (
    <aside className="thinking-code-card bg-sketch-ink text-sketch-paper" data-testid="node-thinking-code">
      <div className="mb-3 flex items-center justify-between gap-2">
        <span className="font-hand text-sm font-bold">Node thinking</span>
        <span className="font-hand rounded-[10px_8px_11px_7px] border border-sketch-paper/70 px-2 py-0.5 text-xs font-bold text-sketch-paper/80">
          {nodeId ?? "none"}
        </span>
      </div>
      <pre className="whitespace-pre-wrap break-words font-mono text-sm leading-6">
        {`{thinking process_${processName}}`}
      </pre>
    </aside>
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

Usage: /onboarding-to-skillforge [--skill-dir <path>] [--task <fixture>]

ARGUMENTS: $ARGUMENTS

Why this matters
Every skill added to an agent rides in context on every call. Research shows accuracy drops up to 85% as skill catalogues grow, and agents pick the right skill only 13% of the time without filtering. SkillForge runs a live agent graph against a hidden-requirement task fixture and scores both skills across four milestones: public contract, acceptance behavior, boundaries, and change scope.

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

Step 3 — Select a task fixture
Default to the flagship fixture: prorate_refund (under-specified — rewards asking clarifying questions before acting).

If --task was passed, use that fixture name instead. Accepted fixtures:

prorate_refund — flagship; tests whether the skill prompts the agent to ask before assuming
calculator_add_bug — trivial; use only to sanity-check the pipeline

Step 4 — Package the eval payload
Construct the eval payload:

{
  "task_fixture": "<fixture name>",
  "baseline": {
    "name": "<baseline skill name>",
    "skill_md": "<full contents of baseline SKILL.md>"
  },
  "challenger": {
    "name": "<challenger skill name>",
    "skill_md": "<full contents of challenger SKILL.md>"
  },
  "judge_model": "gpt-4.1-mini",
  "max_turns": 10,
  "thinking_budget": 0
}

Read the actual SKILL.md content for both skills — do not summarize.

Step 5 — Send to SkillForge
Open the SkillForge Eval Lab at [https://skillforge.dev](https://skillforge.dev/) in the browser (via the Chrome MCP or by instructing the user). Pre-fill the form fields:

Task fixture → selected fixture
Baseline skill name + SKILL.md content
Challenger skill name + SKILL.md content
If browser automation is unavailable, output the payload as a formatted block the user can paste directly into the SkillForge UI.

Step 6 — Report the milestone results
Once the eval run completes, read the four milestone cards:

Milestone	Baseline	Challenger
Public contract	met / not met	met / not met
Acceptance behavior	met / not met	met / not met
Boundaries	met / not met	met / not met
Change scope	met / not met	met / not met

Then give a one-sentence recommendation per skill:

Keep — challenger met all milestones baseline didn't; promote it
Restrict — challenger passed some milestones but missed boundaries or change scope; use only in scoped contexts
Retest — unclear signal; adjust the task fixture and run again
Prune — baseline and challenger overlap heavily; drop the weaker one

Decision heuristics
If the challenger clears all four milestones and baseline misses at least one → promote challenger, archive baseline
If both pass → look at change-scope; the skill with tighter scope wins
If neither passes acceptance behavior → the task fixture may be wrong, not the skills
If challenger passes public contract but fails boundaries → restrict (do not default-load)

What to skip
Do not summarize SKILL.md content when sending to SkillForge — send the full text
Do not auto-prune without user confirmation
Do not run evals on more than two skills at a time; SkillForge is pairwise by design

Related
SkillForge Eval Lab: [https://skillforge.dev](https://skillforge.dev/)
RAG-MCP 2025 — skill-selection accuracy research
LongFuncEval (Kate et al.) — accuracy decay with catalogue size
PromptDebt (EASE 2025) — prompt & skill config as #1 LLM technical debt source`;

function OnboardingRoadmap() {
  return (
    <section className="demo-screen demo-screen-panel sketch-card onboarding-screen bg-sketch-paper p-5" aria-label="Onboarding to SkillForge">
      <div className="onboarding-code-area">
        <h2 className="font-hand text-4xl font-bold leading-tight text-sketch-ink md:text-6xl">
          Onboard to SkillForge Now
        </h2>
        <pre className="onboarding-code-block mt-4" data-scroll-free>
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
      <h2 className="problem-title font-hand">
        Future Roadmaps
      </h2>
      <div className="future-roadmap-grid mt-8">
        <article className="future-roadmap-card">
          <div className="future-roadmap-number font-hand">1</div>
          <div>
            <h3 className="font-hand text-2xl font-bold">Configurable Judge Groups</h3>
            <p className="mt-4 text-lg font-semibold leading-8">
              Allow teams to define and prioritize the evaluation criteria that matter most to their skills,
              making SkillForge assessments more flexible, targeted, and use-case specific.
            </p>
          </div>
        </article>
        <article className="future-roadmap-card">
          <div className="future-roadmap-number font-hand">2</div>
          <div>
            <h3 className="font-hand text-2xl font-bold">JPMC Skills Marketplace Integration</h3>
            <p className="mt-4 text-lg font-semibold leading-8">
              Connect SkillForge with the JPMC Skills Marketplace to establish a consistent quality evaluation
              and pruning framework for skills across the JPMC Agentic AI ecosystem.
            </p>
          </div>
        </article>
      </div>
    </section>
  );
}

export function RunPage({ navSlot }: { navSlot?: ReactNode }) {
  const [runId, setRunId] = useState<string | null>(null);
  const [live, setLive] = useState<RunLiveState>(initialRunState);
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [activeRequest, setActiveRequest] = useState<CreateRunRequest | null>(null);
  const [mockReport, setMockReport] = useState<ComparisonReport | null>(null);
  const [demoMode, setDemoMode] = useState(false);
  const unsubscribe = useRef<(() => void) | null>(null);

  const start = useCallback(async (req: CreateRunRequest) => {
    unsubscribe.current?.();
    setActiveRequest(req);
    setMockReport(null);
    setDemoMode(false);
    setRunStartedAt(Date.now());
    setSelectedNode(null);
    setLive(initialRunState());
    try {
      const summary = await api.createRun(req);
      setRunId(summary.run_id);
      unsubscribe.current = subscribeEvents(summary.run_id, (ev) =>
        setLive((s) => reduceEvent(s, ev)),
      );
    } catch {
      setRunId(null);
      setDemoMode(true);
      unsubscribe.current = subscribeMockRun(
        req,
        (ev) => setLive((s) => reduceEvent(s, ev)),
        (report) => setMockReport(report),
      );
    }
  }, []);

  const startAndShowReplay = useCallback(
    (req: CreateRunRequest) => {
      void start(req);
      window.setTimeout(() => {
        document.querySelector<HTMLElement>('[data-screen="replay"]')?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }, 180);
    },
    [start],
  );

  useEffect(() => () => unsubscribe.current?.(), []);

  // Fetch the typed report once the stream says the run completed.
  const detail = useQuery({
    queryKey: ["run", runId, live.runStatus],
    queryFn: () => api.runDetail(runId!),
    enabled: runId != null && live.runStatus === "completed",
  });

  const report = mockReport ?? detail.data?.report;

  return (
    <div className="space-y-4">
      {/* SCREEN 2: Eval setup. This is the second demo stop after the hero:
          show Eval Lab / Run History tabs, explain the experiment, then end
          this screen at the Run eval button inside RunForm. */}
      <section className="demo-screen demo-screen-panel space-y-4">
        {navSlot}
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="sketch-card bg-sketch-paper p-4">
            <div className="font-hand text-sm font-bold text-sketch-muted">Experiment question</div>
            <h2 className="font-hand mt-1 text-2xl font-bold leading-tight">
              Should this skill become a trusted default, or is it just more context debt?
            </h2>
            <p className="mt-2 text-sm font-semibold leading-6">
              Run a controlled skill experiment, then inspect the behavior path: questions asked,
              assumptions avoided, code changed, judges convinced.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div className="sticky-note rotate-[-1deg] bg-sketch-pink p-3">
              <div className="font-hand text-sm font-bold">Input</div>
              <div className="font-hand mt-2 text-3xl">✎</div>
              <p className="mt-2 text-xs font-semibold">Two skills, one task.</p>
            </div>
            <div className="sticky-note rotate-[1deg] bg-sketch-blue p-3">
              <div className="font-hand text-sm font-bold">Replay</div>
              <div className="font-hand mt-2 text-3xl">↝</div>
              <p className="mt-2 text-xs font-semibold">Live agent graph.</p>
            </div>
            <div className="sticky-note rotate-[-2deg] bg-sketch-green p-3">
              <div className="font-hand text-sm font-bold">Decision</div>
              <div className="font-hand mt-2 text-3xl">✓</div>
              <p className="mt-2 text-xs font-semibold">Keep, restrict, retest.</p>
            </div>
          </div>
        </div>

        <RunForm running={live.runStatus === "running"} onSubmit={startAndShowReplay} />

        {demoMode ? (
          <div className="sticky-note rotate-[-0.5deg] bg-sketch-blue p-3 text-sm font-semibold text-sketch-ink">
            Demo mode: frontend mock skills are driving this run because the API is unavailable.
          </div>
        ) : null}
      </section>

      {/* SCREEN 3: Milestones reached + behavior replay. Keep these together:
          first show milestone card flips, then immediately show the live process graph. */}
      <section className="demo-screen demo-screen-panel space-y-4" data-screen="replay">
        <LiveDiscoveryCards live={live} request={activeRequest} />
        <h2 className="font-hand mb-2 text-lg font-bold text-sketch-ink">
          Behavior replay{" "}
          <span className="text-sm font-semibold text-sketch-muted">
            — hover or click any node to inspect live evidence
          </span>
        </h2>
        <div className="behavior-replay-grid">
          <PipelineGraph state={live} runStartedAt={runStartedAt} onSelectNode={setSelectedNode} />
          <NodeThinkingCodeBlock nodeId={selectedNode} />
        </div>
      </section>

      {live.runStatus === "failed" && (
        <div className="sticky-note bg-sketch-pink p-3 text-sm font-semibold text-sketch-ink">Run failed: {live.error}</div>
      )}

      {/* SCREEN 4: Decision report is rendered by ResultsFunnel once a run completes. */}
      {report ? (
        <section className="demo-screen demo-screen-panel">
          <ResultsFunnel report={report} />
        </section>
      ) : null}

      {/* SCREEN 5: Onboarding and roadmap. This is the final demo stop after
          the decision report; keep it before the future roadmap screen. */}
      <OnboardingRoadmap />

      {/* SCREEN 6: Future roadmap. Keep this as the final demo stop so the
          presentation closes with what SkillForge can become next. */}
      <FutureRoadmapScreen />
    </div>
  );
}
