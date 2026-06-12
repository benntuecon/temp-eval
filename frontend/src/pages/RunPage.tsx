// Run page: form -> live architecture graph + node thinking panel -> results.
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, subscribeEvents, type ComparisonReport, type CreateRunRequest } from "../api/client";
import { NodePanel } from "../components/NodePanel";
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

function OnboardingRoadmap() {
  return (
    <section className="sketch-card bg-sketch-paper p-5" aria-label="Onboarding and roadmap">
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[0.95fr_1.05fr]">
        <div>
          <div className="font-hand sticky-note mb-3 inline-block rotate-[-1deg] bg-sketch-blue px-3 py-1 text-sm font-bold">
            Screen 5
          </div>
          <h2 className="font-hand text-3xl font-bold leading-tight text-sketch-ink">
            Onboarding to SkillForge
          </h2>
          <p className="mt-3 text-sm font-semibold leading-6 text-sketch-ink">
            We created an onboarding path so you can simply send your agent to the
            SkillForge skill. Your agent starts consolidating its skills and sends
            the evaluation flow to SkillForge.
          </p>
          <div className="sticky-note mt-4 bg-sketch-yellow p-3 font-mono text-xs font-bold">
            Onboarding-to-SkillForge.md
            <br />
            send your agents to SkillForge
          </div>
        </div>
        <div className="grid grid-cols-1 gap-3">
          <div className="sticky-note rotate-[1deg] bg-sketch-green p-4">
            <h3 className="font-hand text-lg font-bold">Roadmap</h3>
            <p className="mt-2 text-sm font-semibold leading-6">
              Configuration for judge groups — tell SkillForge what you care most about.
            </p>
          </div>
          <div className="sticky-note rotate-[-1deg] bg-sketch-pink p-4">
            <h3 className="font-hand text-lg font-bold">Marketplace Integration</h3>
            <p className="mt-2 text-sm font-semibold leading-6">
              Integrate with the JPMC Skills Marketplace so the JPMC Agentic AI
              ecosystem has an eval framework for skill quality and pruning.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

export function RunPage() {
  const [runId, setRunId] = useState<string | null>(null);
  const [live, setLive] = useState<RunLiveState>(initialRunState);
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
      <section className="grid grid-cols-1 gap-3 lg:grid-cols-[1.1fr_0.9fr]">
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
      </section>

      <RunForm running={live.runStatus === "running"} onSubmit={start} />

      {demoMode ? (
        <div className="sticky-note rotate-[-0.5deg] bg-sketch-blue p-3 text-sm font-semibold text-sketch-ink">
          Demo mode: frontend mock skills are driving this run because the API is unavailable.
        </div>
      ) : null}

      {/* SCREEN 3: Milestones reached + behavior replay. Keep these together:
          first show milestone card flips, then immediately show the live process graph. */}
      <LiveDiscoveryCards live={live} request={activeRequest} />

      <div>
        <h2 className="font-hand mb-2 text-lg font-bold text-sketch-ink">
          Behavior replay{" "}
          <span className="text-sm font-semibold text-sketch-muted">
            — hover or click any node to inspect live evidence
          </span>
        </h2>
        <div className="space-y-4">
          <PipelineGraph state={live} onSelectNode={setSelectedNode} />
          <NodePanel state={live} nodeId={selectedNode} className="h-[360px]" />
        </div>
      </div>

      {live.runStatus === "failed" && (
        <div className="sticky-note bg-sketch-pink p-3 text-sm font-semibold text-sketch-ink">Run failed: {live.error}</div>
      )}

      {/* SCREEN 4: Decision report is rendered by ResultsFunnel once a run completes. */}
      {report ? <ResultsFunnel report={report} /> : null}

      {/* SCREEN 5: Onboarding and roadmap. This is the final demo stop after
          the decision report; keep it at the bottom of the sequence. */}
      <OnboardingRoadmap />
    </div>
  );
}
