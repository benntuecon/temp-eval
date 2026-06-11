// Vega-Lite specs ported 1:1 from the Altair charts the Streamlit app used.
// One colour per arm everywhere; grouped encodings, never stacked.
import type { TopLevelSpec } from "vega-lite";
import type { ComparisonReport } from "../api/client";

export const ARM_COLORS: Record<string, string> = {
  baseline: "#E45756",
  challenger: "#4C78A8",
};

const armScale = {
  domain: ["baseline", "challenger"],
  range: [ARM_COLORS.baseline, ARM_COLORS.challenger],
};

export interface GapRow {
  criterion: string;
  baseline: number;
  challenger: number;
  gap: number;
}

export function gapRows(report: ComparisonReport): GapRow[] {
  const score = new Map<string, number>();
  for (const arm of report.arms) {
    for (const s of arm.scores) score.set(`${arm.arm}:${s.criterion}`, s.score);
  }
  const criteria = report.arms[0]?.scores.map((s) => s.criterion) ?? [];
  const rows = criteria.map((c) => {
    const b = score.get(`baseline:${c}`) ?? 0;
    const ch = score.get(`challenger:${c}`) ?? 0;
    return { criterion: c, baseline: b, challenger: ch, gap: ch - b };
  });
  rows.sort((a, b) => b.gap - a.gap);
  return rows;
}

/** Dumbbell: per-criterion scores connected, sorted by gap. */
export function dumbbellSpec(rows: GapRow[]): TopLevelSpec {
  const order = rows.map((r) => r.criterion);
  const long = rows.flatMap((r) => [
    { criterion: r.criterion, arm: "baseline", score: r.baseline, gap: r.gap },
    { criterion: r.criterion, arm: "challenger", score: r.challenger, gap: r.gap },
  ]);
  return {
    width: "container",
    height: 240,
    layer: [
      {
        data: { values: rows },
        mark: { type: "rule", color: "#bbbbbb", strokeWidth: 2 },
        encoding: {
          y: { field: "criterion", type: "nominal", sort: order, title: null },
          x: { field: "baseline", type: "quantitative", scale: { domain: [0, 20] }, title: "Score (0–20)" },
          x2: { field: "challenger" },
        },
      },
      {
        data: { values: long },
        mark: { type: "circle", size: 170, opacity: 1 },
        encoding: {
          y: { field: "criterion", type: "nominal", sort: order, title: null },
          x: { field: "score", type: "quantitative", scale: { domain: [0, 20] } },
          color: { field: "arm", type: "nominal", scale: armScale, title: "Arm" },
          tooltip: [
            { field: "criterion", type: "nominal" },
            { field: "arm", type: "nominal" },
            { field: "score", type: "quantitative" },
            { field: "gap", type: "quantitative" },
          ],
        },
      },
    ],
  };
}

/** Quality vs cost: total score against total tokens, one dot per arm. */
export function qualityCostSpec(report: ComparisonReport): TopLevelSpec {
  const rows = report.arms.map((a) => ({
    arm: a.arm,
    total_score: a.total_score,
    total_tokens: a.metrics.total_tokens,
    wall_seconds: a.metrics.wall_seconds,
    num_questions: a.metrics.num_questions,
  }));
  return {
    width: "container",
    height: 260,
    data: { values: rows },
    layer: [
      {
        mark: { type: "circle", size: 400, opacity: 0.85 },
        encoding: {
          x: { field: "total_tokens", type: "quantitative", title: "Cost — total tokens" },
          y: {
            field: "total_score",
            type: "quantitative",
            title: "Quality — total score",
            scale: { domain: [0, 120] },
          },
          color: { field: "arm", type: "nominal", scale: armScale, title: "Arm" },
          tooltip: [
            { field: "arm", type: "nominal" },
            { field: "total_score", type: "quantitative" },
            { field: "total_tokens", type: "quantitative" },
            { field: "wall_seconds", type: "quantitative" },
            { field: "num_questions", type: "quantitative" },
          ],
        },
      },
      {
        mark: { type: "text", align: "left", dx: 14, fontWeight: "bold" },
        encoding: {
          x: { field: "total_tokens", type: "quantitative" },
          y: { field: "total_score", type: "quantitative" },
          text: { field: "arm" },
          color: { field: "arm", type: "nominal", scale: armScale, legend: null },
        },
      },
    ],
  };
}
