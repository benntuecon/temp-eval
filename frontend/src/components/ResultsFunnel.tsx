// The results funnel (promptfoo/Langfuse pattern): aggregate delta metrics ->
// per-criterion matrix with green/red deltas -> drill-down (rationales,
// diffs, Q&A, raw JSON).
import { useState } from "react";
import { VegaLite } from "react-vega";
import type { ArmReport, ComparisonReport } from "../api/client";
import { dumbbellSpec, gapRows, qualityCostSpec } from "./charts";
import { Badge, Card, cn } from "./ui";

type DecisionAction = "promote" | "restrict" | "retest";

interface RequirementUnlock {
  requirement: string;
  baseline: "missed" | "unlocked";
  challenger: "missed" | "unlocked";
  evidence: string;
}

interface BehaviorInsight {
  label: string;
  value: string;
  note: string;
  tone: "red" | "blue" | "yellow" | "black";
}

function scoreFor(arm: ArmReport, criterion: string): number {
  return arm.scores.find((s) => s.criterion === criterion)?.score ?? 0;
}

function inferDecision(base: ArmReport, chal: ArmReport): {
  action: DecisionAction;
  title: string;
  summary: string;
  confidence: string;
} {
  const delta = chal.total_score - base.total_score;
  const questionDelta = chal.metrics.num_questions - base.metrics.num_questions;
  if (delta >= 20 && questionDelta >= 1) {
    return {
      action: "promote",
      title: "Promote challenger for ambiguous implementation tasks",
      summary:
        "The challenger produced a meaningful quality lift and changed the behavior pattern: more clarification before code, better edge-case coverage, and stronger judge evidence.",
      confidence: "Demo-level confidence; validate across a larger task suite before org-wide default.",
    };
  }
  if (delta < 0) {
    return {
      action: "restrict",
      title: "Restrict challenger; baseline is safer in this run",
      summary:
        "The challenger did not earn its extra context. Keep it scoped until more runs show a reliable gain.",
      confidence: "Single-run signal; retest with adjacent fixtures before pruning.",
    };
  }
  return {
    action: "retest",
    title: "Retest before changing defaults",
    summary:
      "The result is close enough that the decision should depend on more tasks, cost, and latency evidence.",
    confidence: "Low confidence; increase judges per criterion or run a batch.",
  };
}

function mockTaskKind(report: ComparisonReport): "refund" | "calculator" | "generic" {
  const brief = report.config.task_brief.toLowerCase();
  const gold = report.gold_diff.toLowerCase();
  if (brief.includes("prorate_refund") || gold.includes("prorate_refund")) return "refund";
  if (brief.includes("add(a, b)") || gold.includes("return a + b")) return "calculator";
  return "generic";
}

function mockedRequirementUnlocks(report: ComparisonReport, base: ArmReport, chal: ArmReport): RequirementUnlock[] {
  const challengerAsked = chal.qa.length > base.qa.length || scoreFor(chal, "question_quality") > scoreFor(base, "question_quality");
  const challengerStatus = challengerAsked ? "unlocked" : "missed";
  const taskKind = mockTaskKind(report);

  if (taskKind === "refund") {
    return [
      {
        requirement: "30-day billing denominator",
        baseline: "missed",
        challenger: challengerStatus,
        evidence: "Relevant to the prorate_refund flagship: the brief implies a month but hides policy details.",
      },
      {
        requirement: "Same-day cancellation",
        baseline: "missed",
        challenger: challengerStatus,
        evidence: "Relevant edge case: days_used <= 0 should not be guessed silently.",
      },
      {
        requirement: "Half-up cent rounding",
        baseline: "missed",
        challenger: challengerStatus,
        evidence: "Relevant money rule: Python defaults can be wrong for product policy.",
      },
      {
        requirement: "Clamp overused days",
        baseline: "missed",
        challenger: challengerStatus,
        evidence: "Relevant boundary rule: over-used cycles should not produce negative refunds.",
      },
    ];
  }

  if (taskKind === "calculator") {
    return [
      {
        requirement: "Preserve function signature",
        baseline: "unlocked",
        challenger: "unlocked",
        evidence: "Relevant to the sample fixture: keep add(a, b) stable while fixing behavior.",
      },
      {
        requirement: "Minimal semantic fix",
        baseline: "unlocked",
        challenger: "unlocked",
        evidence: "The gold diff changes subtraction to addition; no hidden domain policy is needed.",
      },
      {
        requirement: "Passing test expectation",
        baseline: "unlocked",
        challenger: "unlocked",
        evidence: "The task directly states add(2, 3) should return 5.",
      },
      {
        requirement: "Avoid over-engineering",
        baseline: "unlocked",
        challenger: challengerAsked ? "missed" : "unlocked",
        evidence: "For a trivial fixture, extra ambiguity hunting can become process overhead.",
      },
    ];
  }

  return [
    {
      requirement: "Preserve public API",
      baseline: "missed",
      challenger: challengerStatus,
      evidence: "Generic mock: keep the existing contract unless the brief says otherwise.",
    },
    {
      requirement: "Match stated acceptance behavior",
      baseline: "missed",
      challenger: challengerStatus,
      evidence: "Generic mock: the implementation should satisfy the observable task requirement.",
    },
    {
      requirement: "Handle obvious boundary inputs",
      baseline: "missed",
      challenger: challengerStatus,
      evidence: "Generic mock until backend emits structured hiddenRequirementUnlocks.",
    },
    {
      requirement: "Avoid unrelated refactors",
      baseline: "missed",
      challenger: challengerStatus,
      evidence: "Generic mock: minimize behavioral blast radius.",
    },
  ];
}

function mockedBehaviorInsights(base: ArmReport, chal: ArmReport): BehaviorInsight[] {
  const questionDelta = chal.metrics.num_questions - base.metrics.num_questions;
  const tokenDelta = chal.metrics.total_tokens - base.metrics.total_tokens;
  const qualityDelta = chal.total_score - base.total_score;
  const approachDelta = scoreFor(chal, "approach") - scoreFor(base, "approach");
  return [
    {
      label: "Quality lift",
      value: `${qualityDelta > 0 ? "+" : ""}${qualityDelta}`,
      note: "Total judge score delta.",
      tone: qualityDelta >= 0 ? "blue" : "red",
    },
    {
      label: "Clarification shift",
      value: `${questionDelta > 0 ? "+" : ""}${questionDelta}`,
      note: "Extra questions before implementation.",
      tone: questionDelta > 0 ? "yellow" : "red",
    },
    {
      label: "Approach change",
      value: `${approachDelta > 0 ? "+" : ""}${approachDelta}`,
      note: "Judge signal for planning and efficiency.",
      tone: approachDelta >= 0 ? "blue" : "red",
    },
    {
      label: "Cost tradeoff",
      value: `${tokenDelta > 0 ? "+" : ""}${tokenDelta.toLocaleString()}`,
      note: "Token delta; lower is better.",
      tone: tokenDelta <= 0 ? "blue" : "black",
    },
  ];
}

function mockedAssumptionsAndMisses(report: ComparisonReport, base: ArmReport, chal: ArmReport) {
  const challengerAsked = chal.qa.length > base.qa.length;
  const taskKind = mockTaskKind(report);
  const missedCriticalAmbiguities =
    taskKind === "refund"
      ? [
          "Month length definition",
          "Same-day or negative days_used behavior",
          "Cent rounding mode",
          "Refund clamping after full or over-used cycles",
        ]
      : taskKind === "calculator"
        ? [
            "No major hidden ambiguity; this fixture is intentionally trivial.",
            "The relevant check is whether the skill adds process overhead to an obvious fix.",
            "A good skill should preserve add(a, b) and change only the broken operator.",
          ]
        : [
            "Expected public contract",
            "Boundary behavior",
            "Minimal change scope",
            "Acceptance-test expectation",
          ];
  return {
    assumptions: [
      {
        arm: "baseline",
        text:
          taskKind === "refund"
            ? "Likely assumed the refund policy from the brief without surfacing hidden edge cases."
            : taskKind === "calculator"
              ? "Likely treated the task as a direct operator bug; that is appropriate for this trivial sample if the diff stays minimal."
              : "Likely moved from the stated brief to implementation without producing explicit ambiguity evidence.",
      },
      {
        arm: "challenger",
        text: challengerAsked
          ? taskKind === "calculator"
            ? "Asked more questions than the sample likely requires; useful to measure process overhead."
            : "Converted ambiguous policy details into explicit stakeholder questions before shipping."
          : "Did not show a strong clarification advantage in this run.",
      },
    ],
    missedCriticalAmbiguities,
  };
}

function MetricCard({
  label,
  value,
  delta,
  invert,
}: {
  label: string;
  value: string;
  delta?: number;
  invert?: boolean;
}) {
  const good = delta != null && (invert ? delta < 0 : delta > 0);
  const bad = delta != null && (invert ? delta > 0 : delta < 0);
  return (
    <Card className="p-3">
      <div className="text-xs font-hand font-bold text-sketch-muted">{label}</div>
      <div className="font-hand text-xl font-bold text-sketch-ink">{value}</div>
      {delta != null && (
        <div className={cn("font-hand text-xs font-bold", good && "text-blue-700", bad && "text-sketch-red", !good && !bad && "text-sketch-muted")}>
          {delta > 0 ? "+" : ""}
          {delta.toLocaleString()}
        </div>
      )}
    </Card>
  );
}

function byArm(report: ComparisonReport): Record<string, ArmReport> {
  return Object.fromEntries(report.arms.map((a) => [a.arm, a]));
}

export function ResultsFunnel({ report }: { report: ComparisonReport }) {
  const arms = byArm(report);
  const base = arms["baseline"];
  const chal = arms["challenger"];
  const rows = gapRows(report);
  const [openCriterion, setOpenCriterion] = useState<string | null>(null);

  if (!base || !chal) return null;

  const decision = inferDecision(base, chal);
  const requirements = mockedRequirementUnlocks(report, base, chal);
  const behaviorInsights = mockedBehaviorInsights(base, chal);
  const behaviorNotes = mockedAssumptionsAndMisses(report, base, chal);

  const download = () => {
    const blob = new Blob([JSON.stringify(report, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "skill_eval_report.json";
    a.click();
    URL.revokeObjectURL(a.href);
  };

  return (
    <div className="space-y-6" data-testid="results-funnel">
      {/* SCREEN 4: Decision report. This is the demo's decision moment; keep
          the verdict, score cards, and evidence funnel ordered after Screen 3. */}
      <section className="sketch-card bg-sketch-paper">
        <div className="grid grid-cols-1 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="p-5">
            <Badge tone={decision.action === "promote" ? "blue" : decision.action === "restrict" ? "red" : "yellow"}>
              decision report
            </Badge>
            <h2 className="mt-3 text-3xl font-hand font-bold leading-tight">{decision.title}</h2>
            <p className="mt-3 text-sm font-semibold leading-6">{decision.summary}</p>
            <p className="mt-3 border-l-8 border-sketch-yellow pl-3 text-xs font-semibold text-sketch-muted">
              {decision.confidence}
            </p>
          </div>
          <div className="grid grid-cols-3 gap-3 border-t-2 border-dashed border-sketch-ink p-4 lg:border-l-2 lg:border-t-0">
            <div className="sticky-note rotate-[-1deg] bg-sketch-pink p-4">
              <div className="font-hand text-sm font-bold">Baseline</div>
              <div className="font-hand mt-2 text-3xl font-bold">{base.total_score}</div>
              <div className="text-xs font-semibold">/120</div>
            </div>
            <div className="sticky-note rotate-[1deg] bg-sketch-yellow p-4">
              <div className="font-hand text-sm font-bold">Delta</div>
              <div className="font-hand mt-2 text-3xl font-bold">
                {chal.total_score - base.total_score > 0 ? "+" : ""}
                {chal.total_score - base.total_score}
              </div>
              <div className="text-xs font-semibold">score movement</div>
            </div>
            <div className="sticky-note rotate-[-2deg] bg-sketch-blue p-4">
              <div className="font-hand text-sm font-bold">Challenger</div>
              <div className="font-hand mt-2 text-3xl font-bold">{chal.total_score}</div>
              <div className="text-xs font-semibold">/120</div>
            </div>
          </div>
        </div>
      </section>

      {/* 1. Aggregate delta metrics */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard
          label="Challenger total"
          value={`${chal.total_score}/120`}
          delta={chal.total_score - base.total_score}
        />
        <MetricCard label="Baseline total" value={`${base.total_score}/120`} />
        <MetricCard
          label="Questions asked"
          value={String(chal.metrics.num_questions)}
          delta={chal.metrics.num_questions - base.metrics.num_questions}
        />
        <MetricCard
          label="Tokens"
          value={chal.metrics.total_tokens.toLocaleString()}
          delta={chal.metrics.total_tokens - base.metrics.total_tokens}
          invert
        />
      </div>

      <div className="sticky-note rotate-[-0.5deg] bg-sketch-yellow p-3 font-hand text-sm font-bold text-sketch-ink">
        Verdict: {report.pairwise_verdict}
      </div>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_0.9fr]">
        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <h3 className="font-hand text-lg font-bold text-sketch-ink">Hidden requirement unlocks</h3>
            <Badge tone="yellow">mocked insight layer</Badge>
          </div>
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b-2 border-dashed border-sketch-ink text-left text-xs font-hand font-bold">
                  <th className="py-2">critical ambiguity</th>
                  <th>baseline</th>
                  <th>challenger</th>
                </tr>
              </thead>
              <tbody>
                {requirements.map((r) => (
                  <tr key={r.requirement} className="border-b border-sketch-ink/20">
                    <td className="py-2 pr-3">
                      <div className="font-bold">{r.requirement}</div>
                      <div className="text-[11px] text-sketch-muted">{r.evidence}</div>
                    </td>
                    <td>
                      <Badge tone={r.baseline === "unlocked" ? "blue" : "red"}>{r.baseline}</Badge>
                    </td>
                    <td>
                      <Badge tone={r.challenger === "unlocked" ? "blue" : "red"}>{r.challenger}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="p-4">
          <h3 className="mb-3 font-hand text-lg font-bold text-sketch-ink">Behavior changed by skill</h3>
          <div className="grid grid-cols-2 gap-3">
            {behaviorInsights.map((item) => (
              <div key={item.label} className="sticky-note bg-sketch-paper p-3 odd:rotate-[-1deg] even:rotate-[1deg]">
                <div className="text-[11px] font-hand font-bold text-sketch-muted">{item.label}</div>
                <div
                  className={cn(
                    "mt-1 font-hand text-2xl font-bold",
                    item.tone === "red" && "text-sketch-red",
                    item.tone === "blue" && "text-blue-700",
                    item.tone === "yellow" && "text-sketch-ink",
                    item.tone === "black" && "text-sketch-ink",
                  )}
                >
                  {item.value}
                </div>
                <div className="text-xs font-semibold">{item.note}</div>
              </div>
            ))}
          </div>
        </Card>
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <h3 className="mb-3 font-hand text-lg font-bold text-sketch-ink">Assumptions surfaced</h3>
          <div className="space-y-2">
            {behaviorNotes.assumptions.map((item) => (
              <div key={item.arm} className="sticky-note bg-sketch-paper p-3">
                <Badge tone={item.arm === "baseline" ? "red" : "blue"}>{item.arm}</Badge>
                <p className="mt-2 text-sm font-semibold leading-6">{item.text}</p>
              </div>
            ))}
          </div>
        </Card>
        <Card className="p-4">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-hand text-lg font-bold text-sketch-ink">Missed critical ambiguities</h3>
            <Badge tone="yellow">mock</Badge>
          </div>
          <ul className="space-y-2">
            {behaviorNotes.missedCriticalAmbiguities.map((item) => (
              <li key={item} className="flex items-center gap-3 border-b border-sketch-ink/20 pb-2 text-sm font-semibold">
                <span className="font-hand text-lg font-bold text-sketch-red">✕</span>
                {item}
              </li>
            ))}
          </ul>
        </Card>
      </section>

      {/* 2. Charts */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <h3 className="mb-1 font-hand text-lg font-bold text-sketch-ink">Where the skills differ</h3>
          <p className="mb-2 text-xs font-semibold text-sketch-muted">Per-criterion gap, biggest first.</p>
          <VegaLite spec={dumbbellSpec(rows)} actions={false} style={{ width: "100%" }} />
        </Card>
        <Card className="p-4">
          <h3 className="mb-1 font-hand text-lg font-bold text-sketch-ink">Quality vs cost</h3>
          <p className="mb-2 text-xs font-semibold text-sketch-muted">Up-and-to-the-left is better.</p>
          <VegaLite spec={qualityCostSpec(report)} actions={false} style={{ width: "100%" }} />
        </Card>
      </div>

      {/* 3. Score matrix + rationale drill-down */}
      <Card className="p-4">
        <h3 className="mb-2 font-hand text-lg font-bold text-sketch-ink">Judge council: scores &amp; rationales</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b-2 border-dashed border-sketch-ink text-left text-xs font-hand font-bold text-sketch-ink">
              <th className="py-1.5">criterion</th>
              <th>baseline</th>
              <th>challenger</th>
              <th>Δ</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const open = openCriterion === r.criterion;
              const bScore = base.scores.find((s) => s.criterion === r.criterion);
              const cScore = chal.scores.find((s) => s.criterion === r.criterion);
              return [
                <tr key={r.criterion} className="border-b border-sketch-ink/20">
                  <td className="py-1.5 font-mono text-xs">{r.criterion}</td>
                  <td>{r.baseline}/20</td>
                  <td>{r.challenger}/20</td>
                  <td
                    className={cn(
                      "font-semibold",
                      r.gap > 0 && "text-blue-700",
                      r.gap < 0 && "text-sketch-red",
                      r.gap === 0 && "text-sketch-muted",
                    )}
                  >
                    {r.gap > 0 ? "+" : ""}
                    {r.gap}
                  </td>
                  <td className="text-right">
                    <button
                      className="text-xs font-hand font-bold text-blue-700 underline"
                      onClick={() => setOpenCriterion(open ? null : r.criterion)}
                    >
                      {open ? "hide why" : "why?"}
                    </button>
                  </td>
                </tr>,
                open ? (
                  <tr key={`${r.criterion}-detail`}>
                    <td colSpan={5} className="bg-sketch-paper p-3">
                      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                        <div>
                          <Badge tone="red">baseline — {bScore?.score}/20</Badge>
                          <p className="mt-1 text-xs font-semibold leading-relaxed text-sketch-ink">{bScore?.rationale}</p>
                        </div>
                        <div>
                          <Badge tone="blue">challenger — {cScore?.score}/20</Badge>
                          <p className="mt-1 text-xs font-semibold leading-relaxed text-sketch-ink">{cScore?.rationale}</p>
                        </div>
                      </div>
                    </td>
                  </tr>
                ) : null,
              ];
            })}
          </tbody>
        </table>
      </Card>

      {/* 4. Evidence: diffs + Q&A */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {report.arms.map((arm) => (
          <Card key={arm.arm} className="p-4">
            <h3 className="mb-2 font-hand text-lg font-bold text-sketch-ink">
              {arm.arm} — what it changed{" "}
              <Badge tone={arm.arm === "baseline" ? "red" : "blue"}>{arm.stop_reason || "?"}</Badge>
            </h3>
              <pre className="max-h-56 overflow-auto rounded-[14px_9px_16px_11px] border-2 border-sketch-ink bg-sketch-ink p-3 text-[11px] leading-relaxed text-sketch-paper">
              {arm.diff || "(no diff captured)"}
            </pre>
            <h4 className="mt-3 text-xs font-hand font-bold text-sketch-muted">Clarifying Q&amp;A</h4>
            {arm.qa.length === 0 ? (
              <p className="text-xs font-semibold text-sketch-muted">(no clarifying questions asked)</p>
            ) : (
              <ol className="mt-1 list-decimal space-y-1 pl-4 text-xs font-semibold text-sketch-ink">
                {arm.qa.map(([q, a], i) => (
                  <li key={i}>
                    <span className="font-medium">{q}</span>
                    <br />
                    <span className="text-sketch-muted">↳ {a}</span>
                  </li>
                ))}
              </ol>
            )}
          </Card>
        ))}
      </div>

      {report.gold_diff ? (
        <details className="sketch-card bg-sketch-paper p-4">
          <summary className="cursor-pointer text-sm font-hand font-bold text-sketch-ink">
            Gold reference diff (what the judges compare against)
          </summary>
          <pre className="mt-2 max-h-56 overflow-auto rounded-[14px_10px_16px_12px] bg-sketch-ink p-3 text-[11px] text-sketch-paper">
            {report.gold_diff}
          </pre>
        </details>
      ) : null}

      <button className="text-xs font-hand font-bold text-blue-700 underline" onClick={download}>
        Download report (JSON)
      </button>
    </div>
  );
}
