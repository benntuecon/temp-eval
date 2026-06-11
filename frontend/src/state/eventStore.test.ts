import { describe, expect, it } from "vitest";
import type { RunEvent } from "../api/client";
import { initialRunState, reduceEvents } from "./eventStore";

const ev = (e: Record<string, unknown>) => e as unknown as RunEvent;

describe("eventStore", () => {
  it("starts with skills ready and everything else pending", () => {
    const s = initialRunState();
    expect(s.nodeStatus["skill:baseline"]).toBe("done");
    expect(s.nodeStatus["taker:baseline"]).toBe("pending");
    expect(s.runStatus).toBe("idle");
  });

  it("lights the pipeline up as stages progress", () => {
    let s = initialRunState();
    s = reduceEvents(s, [
      ev({ type: "run_started", run_id: "r", label: "x", node: "", ts: 1 }),
      ev({ type: "stage_changed", stage: "generator", status: "done", node: "test_generator", ts: 2 }),
      ev({ type: "stage_changed", stage: "sandbox", status: "done", node: "sandbox", ts: 3 }),
      ev({ type: "taker_status", arm: "baseline", status: "running", node: "taker:baseline", ts: 4 }),
    ]);
    expect(s.runStatus).toBe("running");
    expect(s.nodeStatus["test_generator"]).toBe("done");
    expect(s.nodeStatus["test_cases"]).toBe("done");
    expect(s.nodeStatus["sandbox"]).toBe("done");
    expect(s.nodeStatus["taker:baseline"]).toBe("running");
    expect(s.nodeStatus["simulator"]).toBe("running");
  });

  it("accumulates per-node thinking buffers (hover-live-thinking)", () => {
    let s = initialRunState();
    s = reduceEvents(s, [
      ev({ type: "thinking_delta", node: "taker:baseline", text: "reading refund.py", ts: 1 }),
      ev({ type: "thinking_delta", node: "taker:baseline", text: "the brief omits rounding", ts: 2 }),
      ev({ type: "tool_call", node: "taker:baseline", tool: "Read", summary: "refund.py", ts: 3 }),
      ev({ type: "thinking_delta", node: "taker:challenger", text: "I should ask first", ts: 4 }),
    ]);
    const base = s.buffers["taker:baseline"];
    expect(base).toHaveLength(3);
    expect(base[0].text).toContain("reading refund.py");
    expect(base[2].kind).toBe("tool");
    expect(s.buffers["taker:challenger"]).toHaveLength(1);
  });

  it("routes Q&A to the simulator node and counts questions", () => {
    let s = initialRunState();
    s = reduceEvents(s, [
      ev({ type: "question_asked", node: "simulator", question: "What rounding?", ts: 1 }),
      ev({ type: "question_answered", node: "simulator", question: "What rounding?", answer: "Half-up.", ts: 2 }),
    ]);
    expect(s.questionCount).toBe(1);
    expect(s.buffers["simulator"].map((b) => b.kind)).toEqual(["question", "answer"]);
  });

  it("stores judge scores + rationales and completes the run", () => {
    let s = initialRunState();
    s = reduceEvents(s, [
      ev({
        type: "judge_status",
        node: "judge:baseline:correctness",
        arm: "baseline",
        criterion: "correctness",
        status: "done",
        score: 15,
        rationale: "close but misses an edge case",
        ts: 1,
      }),
      ev({ type: "run_completed", run_id: "r", verdict: "challenger wins by 10", node: "report", ts: 2 }),
    ]);
    expect(s.judges["baseline:correctness"]).toMatchObject({ status: "done", score: 15 });
    expect(s.buffers["judge:baseline:correctness"][0].text).toContain("15/20");
    expect(s.runStatus).toBe("completed");
    expect(s.verdict).toContain("challenger");
    expect(s.nodeStatus["report"]).toBe("done");
  });

  it("marks the run failed on run_failed", () => {
    let s = initialRunState();
    s = reduceEvents(s, [ev({ type: "run_failed", run_id: "r", error: "boom", node: "", ts: 1 })]);
    expect(s.runStatus).toBe("failed");
    expect(s.error).toBe("boom");
    expect(s.nodeStatus["report"]).toBe("failed");
  });
});
