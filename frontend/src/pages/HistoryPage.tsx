// History: archived runs, full results funnel for any of them, and a
// run-over-run per-criterion delta table (Langfuse compare pattern).
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, type ComparisonReport } from "../api/client";
import { gapRows } from "../components/charts";
import { ResultsFunnel } from "../components/ResultsFunnel";
import { Badge, Card, cn, Field, inputClass } from "../components/ui";

function DeltaTable({ a, b }: { a: ComparisonReport; b: ComparisonReport }) {
  const rowsA = new Map(gapRows(a).map((r) => [r.criterion, r]));
  const rowsB = gapRows(b);
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b-2 border-dashed border-sketch-ink text-left font-hand text-xs font-bold text-sketch-muted">
          <th className="py-1.5">criterion</th>
          <th>baseline A→B</th>
          <th>Δ</th>
          <th>challenger A→B</th>
          <th>Δ</th>
        </tr>
      </thead>
      <tbody>
        {rowsB.map((rb) => {
          const ra = rowsA.get(rb.criterion);
          const db = rb.baseline - (ra?.baseline ?? 0);
          const dc = rb.challenger - (ra?.challenger ?? 0);
          const cell = (d: number) => (
            <td className={cn("font-semibold", d > 0 && "text-blue-700", d < 0 && "text-sketch-red", d === 0 && "text-sketch-muted")}>
              {d > 0 ? "+" : ""}
              {d}
            </td>
          );
          return (
            <tr key={rb.criterion} className="border-b border-sketch-ink/20">
              <td className="py-1.5 font-mono text-xs">{rb.criterion}</td>
              <td>
                {ra?.baseline ?? 0} → {rb.baseline}
              </td>
              {cell(db)}
              <td>
                {ra?.challenger ?? 0} → {rb.challenger}
              </td>
              {cell(dc)}
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function HistoryPage() {
  const runs = useQuery({ queryKey: ["runs"], queryFn: api.runs, refetchInterval: 5000 });
  const [selected, setSelected] = useState<string | null>(null);
  const [compareWith, setCompareWith] = useState<string>("");

  const completed = (runs.data ?? []).filter((r) => r.status === "completed");
  const selectedId = selected ?? completed[0]?.run_id ?? null;

  const detail = useQuery({
    queryKey: ["run", selectedId],
    queryFn: () => api.runDetail(selectedId!),
    enabled: selectedId != null,
  });
  const compareDetail = useQuery({
    queryKey: ["run", compareWith],
    queryFn: () => api.runDetail(compareWith),
    enabled: compareWith !== "",
  });

  if (runs.isLoading) return <p className="font-hand text-sm font-bold text-sketch-muted">Loading runs…</p>;
  if (completed.length === 0)
    return (
      <p className="sticky-note bg-sketch-yellow p-4 font-hand text-sm font-bold text-sketch-ink" data-testid="history-empty">
        No archived runs yet — finish a run on the Run tab first.
      </p>
    );

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <Field label="Run to view (B — candidate)">
            <select
              className={inputClass}
              value={selectedId ?? ""}
              onChange={(e) => setSelected(e.target.value)}
              data-testid="history-select"
            >
              {completed.map((r) => (
                <option key={r.run_id} value={r.run_id}>
                  {new Date(r.created_at * 1000).toLocaleString()} — {r.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Compare against (A — baseline run, optional)">
            <select className={inputClass} value={compareWith} onChange={(e) => setCompareWith(e.target.value)}>
              <option value="">(no comparison)</option>
              {completed
                .filter((r) => r.run_id !== selectedId)
                .map((r) => (
                  <option key={r.run_id} value={r.run_id}>
                    {new Date(r.created_at * 1000).toLocaleString()} — {r.label}
                  </option>
                ))}
            </select>
          </Field>
        </div>
        {detail.data?.summary.verdict ? (
          <p className="mt-2 text-xs font-semibold text-sketch-muted">
            <Badge tone="green">verdict</Badge> {detail.data.summary.verdict}
          </p>
        ) : null}
      </Card>

      {compareDetail.data?.report && detail.data?.report ? (
        <Card className="p-4">
          <h3 className="font-hand mb-2 text-lg font-bold text-sketch-ink">Run-over-run deltas (B − A)</h3>
          <DeltaTable a={compareDetail.data.report} b={detail.data.report} />
        </Card>
      ) : null}

      {detail.data?.report ? <ResultsFunnel report={detail.data.report} /> : null}
    </div>
  );
}
