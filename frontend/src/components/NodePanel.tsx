// The hover/click panel: a node's live thinking buffer with scrollback.
// New entries append while the run streams — this is the "see what the
// underlying agent is thinking right now" feature.
import { useEffect, useRef } from "react";
import type { RunLiveState } from "../state/eventStore";
import { Badge, Card } from "./ui";

const KIND_TONE: Record<string, "slate" | "green" | "red" | "amber" | "blue"> = {
  thinking: "amber",
  text: "slate",
  tool: "blue",
  question: "blue",
  answer: "green",
  status: "slate",
  rationale: "green",
};

const NODE_DESCRIPTION: Record<string, string> = {
  "skill:baseline": "Input — the baseline skill, injected verbatim into its taker's system prompt.",
  "skill:challenger": "Input — the challenger skill; the only thing that differs between arms.",
  test_generator:
    "MOCK service. Thinking: design a test case that tells the two skills apart — a before-project to fix and a gold after-project to grade against. Input: the two skills + brief. Output: test cases (before/after project).",
  test_cases: "The eval payload: the before commit takers start from + the gold after commit judges compare against.",
  sandbox: "Creates one isolated git worktree per arm @before plus a shared read-only gold tree @after; computes the gold diff.",
  simulator:
    "The stakeholder. Knows the gold solution; answers only what is asked, at requirement level, temperature=0 — identical answers for both arms.",
  assemble: "Aggregates replicate judges per criterion (median), sums totals, derives the verdict.",
  report: "The comparison report — rendered in the results funnel below and archived to runs/.",
};

function describe(nodeId: string): string {
  if (NODE_DESCRIPTION[nodeId]) return NODE_DESCRIPTION[nodeId];
  if (nodeId.startsWith("taker:"))
    return `Coding agent running under the ${nodeId.split(":")[1]} skill. Its thinking, tool calls, and questions stream here live.`;
  if (nodeId.startsWith("judge:")) {
    const [, arm, criterion] = nodeId.split(":");
    return `Judge: scores the ${arm} arm on ${criterion} (0–20, anchored rubric, temperature=0). Rationale appears the moment it lands.`;
  }
  return "";
}

export function NodePanel({ state, nodeId }: { state: RunLiveState; nodeId: string | null }) {
  const scrollRef = useRef<HTMLDivElement>(null);
  const buffer = nodeId ? (state.buffers[nodeId] ?? []) : [];

  useEffect(() => {
    // Follow the live stream: keep the newest entry in view.
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [buffer.length, nodeId]);

  if (!nodeId) {
    return (
      <Card className="flex h-[560px] items-center justify-center p-4 text-sm text-slate-400">
        Hover or click a node to see what it's thinking.
      </Card>
    );
  }

  const status = state.nodeStatus[nodeId] ?? "pending";
  return (
    <Card className="flex h-[560px] flex-col p-4" data-testid="node-panel">
      <div className="mb-2 flex items-center gap-2">
        <h3 className="font-mono text-sm font-semibold text-slate-800">{nodeId}</h3>
        <Badge tone={status === "done" ? "green" : status === "running" ? "amber" : status === "failed" ? "red" : "slate"}>
          {status}
        </Badge>
      </div>
      <p className="mb-3 text-xs leading-relaxed text-slate-500">{describe(nodeId)}</p>
      <div ref={scrollRef} className="min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
        {buffer.length === 0 ? (
          <p className="text-xs text-slate-400">
            {status === "pending" ? "Nothing yet — waiting for the run to reach this node." : "No streamed entries for this node."}
          </p>
        ) : (
          buffer.map((entry, i) => (
            <div key={i} className="rounded-md bg-slate-50 p-2">
              <Badge tone={KIND_TONE[entry.kind] ?? "slate"} className="mb-1">
                {entry.kind}
              </Badge>
              <pre className="whitespace-pre-wrap break-words font-sans text-xs leading-relaxed text-slate-700">
                {entry.text}
              </pre>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}
