import type { ComparisonReport, CreateRunRequest, FixtureInfo, RunEvent } from "./api/client";
import { CRITERIA } from "./state/eventStore";

export const DEMO_FIXTURES: FixtureInfo[] = [
  {
    id: "flagship",
    label: "Flagship: refund policy ambiguity",
    brief:
      "Implement prorate_refund(amount_cents, days_used) for a subscription cancellation flow. The public brief is intentionally underspecified; evaluate whether the skill asks about billing denominator, same-day cancel behavior, rounding, and over-used cycles before coding.",
    default_baseline: {
      name: "ship-it-fast",
      markdown:
        "# Ship It Fast\n\nWhen asked to implement a change, move quickly. Prefer the obvious implementation from the task brief. Avoid slowing the user down with questions unless the task is impossible.",
    },
    default_challenger: {
      name: "ambiguity-hunter",
      markdown:
        "# Ambiguity Hunter\n\nBefore coding, identify hidden requirements that could change behavior. Ask concise clarifying questions about policy, edge cases, and acceptance criteria. Preserve public APIs and keep the implementation scoped.",
    },
  },
  {
    id: "calculator",
    label: "Small fixture: calculator bug",
    brief:
      "Fix add(a, b) so add(2, 3) returns 5. This fixture checks whether the skill adds useful discipline or unnecessary process overhead on an obvious bug.",
    default_baseline: {
      name: "direct-fix",
      markdown: "# Direct Fix\n\nMake the smallest obvious change and stop.",
    },
    default_challenger: {
      name: "careful-but-light",
      markdown:
        "# Careful But Light\n\nCheck the public contract, make the minimal semantic fix, and avoid unnecessary questions for trivial tasks.",
    },
  },
];

const metrics = (total: number, output: number, seconds: number, turns: number, questions: number) => ({
  total_tokens: total,
  input_tokens: total - output,
  output_tokens: output,
  wall_seconds: seconds,
  num_turns: turns,
  num_questions: questions,
});

export function createMockComparisonReport(req: CreateRunRequest): ComparisonReport {
  const scores = {
    baseline: [13, 12, 10, 14, 5, 11],
    challenger: [18, 18, 17, 16, 19, 18],
  };
  return {
    config: {
      before_hash: "mock-before",
      after_hash: "mock-after",
      repo_path: "frontend-demo/mock-fixture",
      task_brief: req.task_brief,
      baseline_skill_path: `${req.baseline.name}/SKILL.md`,
      challenger_skill_path: `${req.challenger.name}/SKILL.md`,
      models: ["baseline", "challenger"],
      max_turns: req.max_turns,
      max_tokens: null,
      wall_clock_seconds: 18,
      thinking_budget: req.thinking_budget,
      judge_model: req.judge_model,
      judges_per_criterion: req.judges_per_criterion,
    },
    arms: [
      {
        arm: "baseline",
        model: req.baseline.name,
        metrics: metrics(8150, 1350, 8.4, 5, 0),
        scores: CRITERIA.map((criterion, index) => ({
          criterion,
          score: scores.baseline[index],
          rationale:
            "Moved directly from brief to code. The implementation is plausible, but it silently assumes billing policy and misses several edge cases.",
        })),
        total_score: scores.baseline.reduce((a, b) => a + b, 0),
        questions: [],
        diff:
          "diff --git a/refunds.py b/refunds.py\n+def prorate_refund(amount_cents, days_used):\n+    remaining = 30 - days_used\n+    return int(amount_cents * remaining / 30)",
        stop_reason: "submitted",
        qa: [],
      },
      {
        arm: "challenger",
        model: req.challenger.name,
        metrics: metrics(10320, 1820, 11.9, 7, 4),
        scores: CRITERIA.map((criterion, index) => ({
          criterion,
          score: scores.challenger[index],
          rationale:
            "Surfaced hidden requirements before implementation, then produced a scoped fix with explicit rounding and boundary behavior.",
        })),
        total_score: scores.challenger.reduce((a, b) => a + b, 0),
        questions: [
          "Should the denominator always be 30 days?",
          "How should same-day cancellations be handled?",
          "Which cent rounding policy should we use?",
          "Should refunds clamp at zero after a full cycle?",
        ],
        diff:
          "diff --git a/refunds.py b/refunds.py\n+from decimal import Decimal, ROUND_HALF_UP\n+\n+def prorate_refund(amount_cents, days_used):\n+    used = min(max(days_used, 0), 30)\n+    remaining = Decimal(30 - used) / Decimal(30)\n+    return int((Decimal(amount_cents) * remaining).quantize(Decimal('1'), rounding=ROUND_HALF_UP))",
        stop_reason: "submitted",
        qa: [
          ["Should the denominator always be 30 days?", "Yes. Product policy uses a 30-day billing cycle for this function."],
          ["How should same-day cancellations be handled?", "days_used <= 0 should return the full amount."],
          ["Which cent rounding policy should we use?", "Round half up to the nearest cent."],
          ["Should refunds clamp at zero after a full cycle?", "Yes. days_used >= 30 returns 0."],
        ],
      },
    ],
    pairwise_verdict:
      "Promote challenger for ambiguous policy tasks: it spends a little more context to prevent expensive silent assumptions.",
    gold_diff:
      "diff --git a/refunds.py b/refunds.py\n+from decimal import Decimal, ROUND_HALF_UP\n+\n+def prorate_refund(amount_cents, days_used):\n+    used = min(max(days_used, 0), 30)\n+    remaining_ratio = Decimal(30 - used) / Decimal(30)\n+    return int((Decimal(amount_cents) * remaining_ratio).quantize(Decimal('1'), rounding=ROUND_HALF_UP))",
    session_id: "mock-session",
  };
}

export function subscribeMockRun(
  req: CreateRunRequest,
  onEvent: (ev: RunEvent) => void,
  onDone: (report: ComparisonReport) => void,
): () => void {
  const runId = `mock-${Date.now()}`;
  const event = (ev: Record<string, unknown>) => ev as RunEvent;
  const events: RunEvent[] = [
    event({ type: "run_started", run_id: runId, label: "Mock skill eval", node: "test_generator" }),
    event({ type: "thinking_delta", node: "test_generator", text: "Reading both skills. The challenger explicitly searches for hidden policy details." }),
    event({ type: "stage_changed", stage: "generator", status: "done", node: "test_generator" }),
    event({ type: "stage_changed", stage: "sandbox", status: "running", node: "sandbox" }),
    event({ type: "tool_call", node: "sandbox", tool: "git worktree", summary: "created baseline, challenger, and gold trees" }),
    event({ type: "stage_changed", stage: "sandbox", status: "done", node: "sandbox" }),
    event({ type: "taker_status", arm: "baseline", status: "running", node: "taker:baseline" }),
    event({ type: "thinking_delta", node: "taker:baseline", text: "The brief says prorate. I will assume a 30-day month and implement directly." }),
    event({ type: "tool_call", node: "taker:baseline", tool: "edit", summary: "adds prorate_refund with a simple 30-day formula" }),
    event({ type: "taker_status", arm: "baseline", status: "done", stop_reason: "submitted", metrics: metrics(8150, 1350, 8.4, 5, 0), node: "taker:baseline" }),
    event({ type: "taker_status", arm: "challenger", status: "running", node: "taker:challenger" }),
    event({ type: "thinking_delta", node: "taker:challenger", text: "This is a policy-shaped function. I should uncover denominator, rounding, and boundary behavior before coding." }),
    event({ type: "question_asked", question: "Should the denominator always be 30 days?", node: "simulator" }),
    event({ type: "question_answered", question: "Should the denominator always be 30 days?", answer: "Yes. Product policy uses a 30-day billing cycle for this function.", node: "simulator" }),
    event({ type: "question_asked", question: "How should same-day cancellations and over-used cycles behave?", node: "simulator" }),
    event({ type: "question_answered", question: "How should same-day cancellations and over-used cycles behave?", answer: "days_used <= 0 returns full amount; days_used >= 30 returns zero.", node: "simulator" }),
    event({ type: "question_asked", question: "Which cent rounding policy should money use?", node: "simulator" }),
    event({ type: "question_answered", question: "Which cent rounding policy should money use?", answer: "Round half up to the nearest cent.", node: "simulator" }),
    event({ type: "tool_call", node: "taker:challenger", tool: "edit", summary: "adds clamping and Decimal ROUND_HALF_UP" }),
    event({ type: "taker_status", arm: "challenger", status: "done", stop_reason: "submitted", metrics: metrics(10320, 1820, 11.9, 7, 4), node: "taker:challenger" }),
    event({ type: "stage_changed", stage: "takers", status: "done", node: "assemble" }),
    ...(["baseline", "challenger"] as const).flatMap((arm) =>
      CRITERIA.map((criterion, index) =>
        event({
          type: "judge_status",
          arm,
          criterion,
          status: "done",
          score: arm === "baseline" ? [13, 12, 10, 14, 5, 11][index] : [18, 18, 17, 16, 19, 18][index],
          rationale:
            arm === "baseline"
              ? "Direct implementation, but several hidden requirements remained implicit."
              : "Clarified requirement boundaries and implemented the policy-compatible behavior.",
          node: `judge:${arm}:${criterion}`,
        }),
      ),
    ),
    event({ type: "stage_changed", stage: "report", status: "done", node: "report" }),
    event({ type: "run_completed", run_id: runId, verdict: "promote challenger for ambiguous tasks", node: "report" }),
  ];

  const timers = events.map((ev, index) =>
    window.setTimeout(() => {
      onEvent({ ...ev, ts: Date.now() });
      if (index === events.length - 1) onDone(createMockComparisonReport(req));
    }, 260 + index * 520),
  );
  return () => timers.forEach((timer) => window.clearTimeout(timer));
}
