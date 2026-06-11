// Pure reducer: a stream of node-addressed RunEvents -> live pipeline state.
// Every event appends to its node's buffer, so hovering a graph node shows
// "what is this agent thinking right now", growing live during a run.
import type { RunEvent } from "../api/client";

export type NodeStatus = "pending" | "running" | "done" | "failed";

export interface BufferEntry {
  kind: "thinking" | "text" | "tool" | "question" | "answer" | "status" | "rationale";
  text: string;
  ts: number;
}

export interface JudgeCell {
  status: NodeStatus;
  score?: number | null;
  rationale?: string | null;
}

export interface TakerInfo {
  status: NodeStatus;
  stopReason?: string | null;
  totalTokens?: number;
  numTurns?: number;
  numQuestions?: number;
  wallSeconds?: number;
}

export interface RunLiveState {
  runStatus: "idle" | "running" | "completed" | "failed";
  verdict: string;
  error: string;
  nodeStatus: Record<string, NodeStatus>;
  buffers: Record<string, BufferEntry[]>;
  judges: Record<string, JudgeCell>; // key: `${arm}:${criterion}`
  takers: Record<string, TakerInfo>; // key: arm
  questionCount: number;
}

export const ARMS = ["baseline", "challenger"] as const;
export const CRITERIA = [
  "correctness",
  "completeness",
  "distance_to_gold",
  "code_quality",
  "question_quality",
  "approach",
] as const;

export function initialRunState(): RunLiveState {
  const nodeStatus: Record<string, NodeStatus> = {
    "skill:baseline": "done",
    "skill:challenger": "done",
    test_generator: "pending",
    test_cases: "pending",
    sandbox: "pending",
    simulator: "pending",
    assemble: "pending",
    report: "pending",
  };
  const judges: Record<string, JudgeCell> = {};
  for (const arm of ARMS) {
    nodeStatus[`taker:${arm}`] = "pending";
    for (const c of CRITERIA) {
      nodeStatus[`judge:${arm}:${c}`] = "pending";
      judges[`${arm}:${c}`] = { status: "pending" };
    }
  }
  return {
    runStatus: "idle",
    verdict: "",
    error: "",
    nodeStatus,
    buffers: {},
    judges,
    takers: {
      baseline: { status: "pending" },
      challenger: { status: "pending" },
    },
    questionCount: 0,
  };
}

function append(
  buffers: Record<string, BufferEntry[]>,
  node: string,
  entry: BufferEntry,
): Record<string, BufferEntry[]> {
  return { ...buffers, [node]: [...(buffers[node] ?? []), entry] };
}

export function reduceEvent(state: RunLiveState, ev: RunEvent): RunLiveState {
  const next: RunLiveState = {
    ...state,
    nodeStatus: { ...state.nodeStatus },
    judges: { ...state.judges },
    takers: { ...state.takers },
  };

  switch (ev.type) {
    case "run_started":
      next.runStatus = "running";
      next.nodeStatus["test_generator"] = "running";
      break;

    case "stage_changed": {
      if (ev.stage === "generator") {
        next.nodeStatus["test_generator"] = ev.status as NodeStatus;
        if (ev.status === "done") {
          next.nodeStatus["test_cases"] = "done";
          next.nodeStatus["sandbox"] = "running";
        }
      } else if (ev.stage === "sandbox") {
        next.nodeStatus["sandbox"] = ev.status as NodeStatus;
      } else if (ev.stage === "takers" && ev.status === "done") {
        next.nodeStatus["simulator"] = "done";
        next.nodeStatus["assemble"] = "running";
      } else if (ev.stage === "report" && ev.status === "done") {
        next.nodeStatus["assemble"] = "done";
        next.nodeStatus["report"] = "done";
      }
      break;
    }

    case "taker_status": {
      const node = `taker:${ev.arm}`;
      const status = (ev.status === "done" ? "done" : "running") as NodeStatus;
      next.nodeStatus[node] = status;
      if (status === "running") next.nodeStatus["simulator"] = "running";
      next.takers[ev.arm] = {
        status,
        stopReason: ev.stop_reason,
        totalTokens: ev.metrics?.total_tokens,
        numTurns: ev.metrics?.num_turns,
        numQuestions: ev.metrics?.num_questions,
        wallSeconds: ev.metrics?.wall_seconds,
      };
      next.buffers = append(next.buffers, node, {
        kind: "status",
        text: status === "done" ? `done — stop: ${ev.stop_reason ?? "?"}` : "started",
        ts: ev.ts ?? 0,
      });
      break;
    }

    case "thinking_delta":
      next.buffers = append(next.buffers, ev.node ?? "", {
        kind: "thinking",
        text: ev.text,
        ts: ev.ts ?? 0,
      });
      break;

    case "tool_call":
      next.buffers = append(next.buffers, ev.node ?? "", {
        kind: "tool",
        text: `${ev.tool} ${ev.summary ?? ""}`.trim(),
        ts: ev.ts ?? 0,
      });
      break;

    case "question_asked":
      next.questionCount = state.questionCount + 1;
      next.nodeStatus["simulator"] = "running";
      next.buffers = append(next.buffers, "simulator", {
        kind: "question",
        text: ev.question,
        ts: ev.ts ?? 0,
      });
      break;

    case "question_answered":
      next.buffers = append(next.buffers, "simulator", {
        kind: "answer",
        text: ev.answer,
        ts: ev.ts ?? 0,
      });
      break;

    case "judge_status": {
      const key = `${ev.arm}:${ev.criterion}`;
      const node = `judge:${key}`;
      const status = (ev.status === "done" ? "done" : "running") as NodeStatus;
      next.nodeStatus[node] = status;
      next.judges[key] = { status, score: ev.score, rationale: ev.rationale };
      if (ev.rationale) {
        next.buffers = append(next.buffers, node, {
          kind: "rationale",
          text: `${ev.score}/20 — ${ev.rationale}`,
          ts: ev.ts ?? 0,
        });
      }
      break;
    }

    case "run_completed":
      next.runStatus = "completed";
      next.verdict = ev.verdict;
      next.nodeStatus["assemble"] = "done";
      next.nodeStatus["report"] = "done";
      next.nodeStatus["simulator"] = "done";
      break;

    case "run_failed":
      next.runStatus = "failed";
      next.error = ev.error;
      next.nodeStatus["report"] = "failed";
      break;
  }
  return next;
}

export function reduceEvents(state: RunLiveState, events: RunEvent[]): RunLiveState {
  return events.reduce(reduceEvent, state);
}
