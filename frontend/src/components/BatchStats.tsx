// Aggregate stats for a batch: win summary, per-criterion averages,
// per-case totals, and token cost — plain Tailwind bars, one color per arm.
import type { BatchStats as BatchStatsT } from "../api/client";
import { ARM_COLORS } from "./charts";
import { Card } from "./ui";

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
      <div className="mb-0.5 flex justify-between text-xs text-slate-600">
        <span className="truncate pr-2">{label}</span>
        <span className="shrink-0 tabular-nums">
          {baseline.toLocaleString()} vs {challenger.toLocaleString()}
        </span>
      </div>
      <div className="space-y-0.5">
        <div className="h-2 rounded bg-slate-100">
          <div
            className="h-2 rounded"
            style={{ width: pct(baseline), background: ARM_COLORS.baseline }}
          />
        </div>
        <div className="h-2 rounded bg-slate-100">
          <div
            className="h-2 rounded"
            style={{ width: pct(challenger), background: ARM_COLORS.challenger }}
          />
        </div>
      </div>
    </div>
  );
}

function WinCard({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <Card className="flex-1 p-3 text-center">
      <div className="text-2xl font-bold" style={color ? { color } : undefined}>
        {value}
      </div>
      <div className="text-xs text-slate-500">{label}</div>
    </Card>
  );
}

export function BatchStats({ stats, partial }: { stats: BatchStatsT; partial: boolean }) {
  const ws = stats.win_summary as Record<string, number>;
  const maxTokens = Math.max(
    1,
    ...stats.tokens_per_case.flatMap((r) => [Number(r.baseline ?? 0), Number(r.challenger ?? 0)]),
  );

  return (
    <div className="space-y-4" data-testid="batch-stats">
      <div className="flex items-center gap-3">
        <h3 className="text-sm font-semibold text-slate-700">Batch stats</h3>
        {partial && (
          <span className="text-xs text-amber-600">partial — runs still in flight</span>
        )}
        <span className="ml-auto flex items-center gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full" style={{ background: ARM_COLORS.baseline }} />
            baseline
          </span>
          <span className="flex items-center gap-1">
            <span className="h-2 w-2 rounded-full" style={{ background: ARM_COLORS.challenger }} />
            challenger
          </span>
        </span>
      </div>

      <div className="flex gap-3">
        <WinCard label="challenger wins" value={ws.challenger ?? 0} color={ARM_COLORS.challenger} />
        <WinCard label="baseline wins" value={ws.baseline ?? 0} color={ARM_COLORS.baseline} />
        <WinCard label="ties" value={ws.tie ?? 0} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="p-4">
          <h4 className="mb-3 text-xs font-semibold uppercase text-slate-500">
            Avg score per criterion (0–20)
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
        </Card>

        <Card className="p-4">
          <h4 className="mb-3 text-xs font-semibold uppercase text-slate-500">
            Total score per case (0–120)
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
        </Card>

        <Card className="p-4 lg:col-span-2">
          <h4 className="mb-3 text-xs font-semibold uppercase text-slate-500">
            Tokens spent per case
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
        </Card>
      </div>
    </div>
  );
}
