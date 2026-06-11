// The results funnel (promptfoo/Langfuse pattern): aggregate delta metrics ->
// per-criterion matrix with green/red deltas -> drill-down (rationales,
// diffs, Q&A, raw JSON).
import { useState } from "react";
import { VegaLite } from "react-vega";
import type { ArmReport, ComparisonReport } from "../api/client";
import { dumbbellSpec, gapRows, qualityCostSpec } from "./charts";
import { Badge, Card, cn } from "./ui";

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
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-xl font-semibold text-slate-900">{value}</div>
      {delta != null && (
        <div className={cn("text-xs font-medium", good && "text-green-600", bad && "text-red-600", !good && !bad && "text-slate-500")}>
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
      <h2 className="text-lg font-semibold text-slate-900">Results: Baseline vs Challenger</h2>

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

      <div className="rounded-lg bg-green-50 p-3 text-sm font-medium text-green-900">
        Verdict: {report.pairwise_verdict}
      </div>

      {/* 2. Charts */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <h3 className="mb-1 text-sm font-semibold text-slate-800">Where the skills differ</h3>
          <p className="mb-2 text-xs text-slate-500">Per-criterion gap, biggest first.</p>
          <VegaLite spec={dumbbellSpec(rows)} actions={false} style={{ width: "100%" }} />
        </Card>
        <Card className="p-4">
          <h3 className="mb-1 text-sm font-semibold text-slate-800">Quality vs cost</h3>
          <p className="mb-2 text-xs text-slate-500">Up-and-to-the-left is better.</p>
          <VegaLite spec={qualityCostSpec(report)} actions={false} style={{ width: "100%" }} />
        </Card>
      </div>

      {/* 3. Score matrix + rationale drill-down */}
      <Card className="p-4">
        <h3 className="mb-2 text-sm font-semibold text-slate-800">Judge scores &amp; rationales</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-left text-xs text-slate-500">
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
                <tr key={r.criterion} className="border-b border-slate-100">
                  <td className="py-1.5 font-mono text-xs">{r.criterion}</td>
                  <td>{r.baseline}/20</td>
                  <td>{r.challenger}/20</td>
                  <td
                    className={cn(
                      "font-semibold",
                      r.gap > 0 && "text-green-600",
                      r.gap < 0 && "text-red-600",
                      r.gap === 0 && "text-slate-400",
                    )}
                  >
                    {r.gap > 0 ? "+" : ""}
                    {r.gap}
                  </td>
                  <td className="text-right">
                    <button
                      className="text-xs text-blue-600 hover:underline"
                      onClick={() => setOpenCriterion(open ? null : r.criterion)}
                    >
                      {open ? "hide why" : "why?"}
                    </button>
                  </td>
                </tr>,
                open ? (
                  <tr key={`${r.criterion}-detail`}>
                    <td colSpan={5} className="bg-slate-50 p-3">
                      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
                        <div>
                          <Badge tone="red">baseline — {bScore?.score}/20</Badge>
                          <p className="mt-1 text-xs leading-relaxed text-slate-700">{bScore?.rationale}</p>
                        </div>
                        <div>
                          <Badge tone="blue">challenger — {cScore?.score}/20</Badge>
                          <p className="mt-1 text-xs leading-relaxed text-slate-700">{cScore?.rationale}</p>
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
            <h3 className="mb-2 text-sm font-semibold text-slate-800">
              {arm.arm} — what it changed{" "}
              <Badge tone={arm.arm === "baseline" ? "red" : "blue"}>{arm.stop_reason || "?"}</Badge>
            </h3>
            <pre className="max-h-56 overflow-auto rounded-md bg-slate-900 p-3 text-[11px] leading-relaxed text-slate-100">
              {arm.diff || "(no diff captured)"}
            </pre>
            <h4 className="mt-3 text-xs font-semibold text-slate-600">Clarifying Q&amp;A</h4>
            {arm.qa.length === 0 ? (
              <p className="text-xs text-slate-400">(no clarifying questions asked)</p>
            ) : (
              <ol className="mt-1 list-decimal space-y-1 pl-4 text-xs text-slate-700">
                {arm.qa.map(([q, a], i) => (
                  <li key={i}>
                    <span className="font-medium">{q}</span>
                    <br />
                    <span className="text-slate-500">↳ {a}</span>
                  </li>
                ))}
              </ol>
            )}
          </Card>
        ))}
      </div>

      {report.gold_diff ? (
        <details className="rounded-xl border border-slate-200 bg-white p-4">
          <summary className="cursor-pointer text-sm font-semibold text-slate-800">
            Gold reference diff (what the judges compare against)
          </summary>
          <pre className="mt-2 max-h-56 overflow-auto rounded-md bg-slate-900 p-3 text-[11px] text-slate-100">
            {report.gold_diff}
          </pre>
        </details>
      ) : null}

      <button className="text-xs text-blue-600 hover:underline" onClick={download}>
        Download report (JSON)
      </button>
    </div>
  );
}
