// The whole architecture as a live React Flow graph. Nodes light up
// grey -> gold(pulse) -> green as events stream in; clicking/hovering a node
// opens the side panel with that agent's live thinking buffer.
import {
  Background,
  Handle,
  Panel,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import { useEffect, useMemo, useRef, useState } from "react";
import { ARMS, CRITERIA, type NodeStatus, type RunLiveState } from "../state/eventStore";
import { Badge, cn } from "./ui";

const STATUS_BG: Record<NodeStatus, string> = {
  pending: "bg-sketch-paper border-sketch-muted text-sketch-muted",
  running: "bg-sketch-yellow border-sketch-ink text-sketch-ink node-running",
  done: "bg-sketch-green border-sketch-ink text-sketch-ink",
  failed: "bg-sketch-pink border-sketch-ink text-sketch-ink",
};

type PipelineNodeData = {
  label: string;
  sub?: string;
  status: NodeStatus;
  hint?: string;
  visible: boolean;
};

function PipelineNode({ data }: NodeProps<Node<PipelineNodeData>>) {
  return (
    <div
      title={data.hint}
      className={cn(
        "font-hand rounded-[14px_10px_15px_11px] border-2 px-3 py-1.5 text-center text-xs font-bold shadow-[4px_4px_0_rgba(48,42,37,0.15)] transition-transform hover:rotate-1",
        STATUS_BG[data.status],
        data.visible ? "pipeline-node-visible" : "pipeline-node-hidden",
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-sketch-ink" />
      <div>{data.label}</div>
      {data.sub ? <div className="text-[10px] opacity-75">{data.sub}</div> : null}
      <Handle type="source" position={Position.Right} className="!bg-sketch-ink" />
    </div>
  );
}

const nodeTypes: NodeTypes = { pipeline: PipelineNode };

// Fixed coordinates: a deterministic layout beats auto-layout for a known DAG.
const X = { skills: 0, generator: 190, cases: 390, sandbox: 600, taker: 760, judge: 950, junction: 1150, assemble: 1240, report: 1400 };

type VisualStep = {
  visibleAt: number;
  doneAt?: number;
};

const JUDGE_APPEAR_AT = 9.3;
const visualTimeline: Record<string, VisualStep> = {
  "skill:baseline": { visibleAt: 0, doneAt: 0.4 },
  "skill:challenger": { visibleAt: 0, doneAt: 0.4 },
  test_generator: { visibleAt: 1, doneAt: 2.8 },
  test_cases: { visibleAt: 3.1, doneAt: 4.3 },
  sandbox: { visibleAt: 4.6, doneAt: 6.1 },
  "taker:baseline": { visibleAt: 6.4, doneAt: 8.4 },
  "taker:challenger": { visibleAt: 6.8, doneAt: 9.1 },
  simulator: { visibleAt: JUDGE_APPEAR_AT, doneAt: 10.4 },
  assemble: { visibleAt: JUDGE_APPEAR_AT, doneAt: 18.5 },
  report: { visibleAt: JUDGE_APPEAR_AT, doneAt: 19.8 },
};

ARMS.forEach((arm, armIndex) => {
  CRITERIA.forEach((criterion, criterionIndex) => {
    visualTimeline[`judge:${arm}:${criterion}`] = {
      visibleAt: JUDGE_APPEAR_AT,
      doneAt: 11.1 + armIndex * 3.5 + criterionIndex * 0.5,
    };
  });
});

function judgeY(armIdx: number, ci: number): number {
  const base = armIdx === 0 ? -40 : 260; // baseline block above, challenger below
  return base + ci * 44;
}

function visualNodeState(
  id: string,
  actual: NodeStatus,
  elapsed: number | null,
): Pick<PipelineNodeData, "status" | "visible"> {
  if (elapsed == null) return { status: actual, visible: true };
  const step = visualTimeline[id] ?? { visibleAt: 0 };
  const visible = elapsed >= step.visibleAt;
  if (!visible) return { status: "pending", visible: false };
  if (step.doneAt != null && elapsed >= step.doneAt) return { status: "done", visible };
  if (actual === "failed") return { status: "failed", visible };
  if (id.startsWith("judge:") && step.doneAt != null && elapsed < step.doneAt - 0.45) {
    return { status: "pending", visible };
  }
  return { status: "running", visible };
}

function visualEdgeStyle(source: string, target: string, elapsed: number | null, style?: Edge["style"]): Edge["style"] {
  if (elapsed == null) return style;
  const sourceVisible = elapsed >= (visualTimeline[source]?.visibleAt ?? 0);
  const targetVisible = elapsed >= (visualTimeline[target]?.visibleAt ?? 0);
  return {
    ...style,
    opacity: sourceVisible && targetVisible ? (style?.opacity ?? 1) : 0,
  };
}

export function buildGraph(state: RunLiveState, elapsed: number | null = null): { nodes: Node<PipelineNodeData>[]; edges: Edge[] } {
  const s = state.nodeStatus;
  const nodeData = (id: string, data: Omit<PipelineNodeData, "status" | "visible">): PipelineNodeData => ({
    ...data,
    ...visualNodeState(id, s[id] ?? "pending", elapsed),
  });
  const isMovingTo = (source: string, target: string) => {
    if (elapsed != null) {
      const sourceStep = visualTimeline[source];
      const targetStep = visualTimeline[target];
      return Boolean(sourceStep && targetStep && elapsed >= sourceStep.visibleAt && elapsed < targetStep.doneAt!);
    }
    return s[target] === "running";
  };
  const isMovingFrom = (source: string, target: string) => {
    if (elapsed != null) {
      const sourceStep = visualTimeline[source];
      const targetStep = visualTimeline[target];
      return Boolean(sourceStep?.doneAt != null && targetStep && elapsed >= sourceStep.doneAt && elapsed < (targetStep.doneAt ?? 20));
    }
    return s[source] === "done" && (s[target] === "pending" || s[target] === "running");
  };
  const nodes: Node<PipelineNodeData>[] = [
    {
      id: "skill:baseline",
      type: "pipeline",
      position: { x: X.skills, y: 120 },
      data: nodeData("skill:baseline", { label: "baseline skill", hint: "Input #1 — injected into its taker's system prompt" }),
    },
    {
      id: "skill:challenger",
      type: "pipeline",
      position: { x: X.skills, y: 180 },
      data: nodeData("skill:challenger", { label: "challenger skill", hint: "Input #2 — the only thing that differs between arms" }),
    },
    {
      id: "test_generator",
      type: "pipeline",
      position: { x: X.generator, y: 150 },
      data: nodeData("test_generator", { label: "test generator", sub: "(mock service)", hint: "Designs a test case that can tell the two skills apart" }),
    },
    {
      id: "test_cases",
      type: "pipeline",
      position: { x: X.cases, y: 150 },
      data: nodeData("test_cases", { label: "test cases", sub: "before/after project", hint: "The eval payload: a before-project + a gold after-project" }),
    },
    {
      id: "sandbox",
      type: "pipeline",
      position: { x: X.sandbox, y: 150 },
      data: nodeData("sandbox", { label: "sandbox", hint: "Isolated git worktrees per arm + shared gold tree" }),
    },
    {
      id: "simulator",
      type: "pipeline",
      position: { x: X.sandbox + 60, y: 320 },
      data: nodeData("simulator", { label: "HITL simulator", hint: "Answers clarifying questions from the gold tree (temperature=0)" }),
    },
    {
      id: "assemble",
      type: "pipeline",
      position: { x: X.assemble, y: 150 },
      data: nodeData("assemble", { label: "assemble", hint: "Median of replicate judges, totals, verdict" }),
    },
    {
      id: "report",
      type: "pipeline",
      position: { x: X.report, y: 150 },
      data: nodeData("report", { label: "report", hint: "The comparison report — rendered below and archived" }),
    },
  ];

  const edges: Edge[] = [
    { id: "e-sb", source: "skill:baseline", target: "test_generator", animated: isMovingTo("skill:baseline", "test_generator"), style: visualEdgeStyle("skill:baseline", "test_generator", elapsed) },
    { id: "e-sc", source: "skill:challenger", target: "test_generator", animated: isMovingTo("skill:challenger", "test_generator"), style: visualEdgeStyle("skill:challenger", "test_generator", elapsed) },
    { id: "e-gc", source: "test_generator", target: "test_cases", animated: isMovingFrom("test_generator", "test_cases"), style: visualEdgeStyle("test_generator", "test_cases", elapsed) },
    { id: "e-cs", source: "test_cases", target: "sandbox", animated: isMovingTo("test_cases", "sandbox"), style: visualEdgeStyle("test_cases", "sandbox", elapsed) },
    { id: "e-ar", source: "assemble", target: "report", animated: isMovingFrom("assemble", "report") || isMovingTo("assemble", "report"), style: visualEdgeStyle("assemble", "report", elapsed) },
  ];

  ARMS.forEach((arm, ai) => {
    const takerId = `taker:${arm}`;
    nodes.push({
      id: takerId,
      type: "pipeline",
      position: { x: X.taker, y: ai === 0 ? 40 : 380 },
      data: {
        ...visualNodeState(takerId, s[takerId], elapsed),
        label: `${arm} taker`,
        sub: state.takers[arm]?.status ?? "pending",
        hint: "Coding agent under this arm's skill — click for its live thinking",
      },
    });
    edges.push({ id: `e-s-${arm}`, source: "sandbox", target: takerId, animated: isMovingTo("sandbox", takerId), style: visualEdgeStyle("sandbox", takerId, elapsed) });
    edges.push({
      id: `e-sim-${arm}`,
      source: takerId,
      target: "simulator",
      animated: elapsed != null ? elapsed >= visualTimeline[takerId].visibleAt && elapsed < 10.4 : s["simulator"] === "running" || s[takerId] === "running",
      style: visualEdgeStyle(takerId, "simulator", elapsed, { strokeDasharray: "4 3", opacity: 0.5 }),
    });

    CRITERIA.forEach((c, ci) => {
      const judgeId = `judge:${arm}:${c}`;
      const cell = state.judges[`${arm}:${c}`];
      nodes.push({
        id: judgeId,
        type: "pipeline",
        position: { x: X.judge, y: judgeY(ai, ci) },
        data: {
          ...visualNodeState(judgeId, s[judgeId], elapsed),
          label: c,
          sub: cell?.score != null ? `${cell.score}/20` : undefined,
          hint: "Click for the judge's rationale",
        },
      });
      edges.push({ id: `e-t-${arm}-${c}`, source: takerId, target: judgeId, animated: isMovingTo(takerId, judgeId), style: visualEdgeStyle(takerId, judgeId, elapsed) });
      edges.push({
        id: `e-j-${arm}-${c}`,
        source: judgeId,
        target: "assemble",
        animated: isMovingFrom(judgeId, "assemble") || isMovingTo(judgeId, "assemble"),
        style: visualEdgeStyle(judgeId, "assemble", elapsed, { opacity: 0.35 }),
      });
    });
  });

  return { nodes, edges };
}

export function PipelineGraph({
  state,
  runStartedAt,
  onSelectNode,
}: {
  state: RunLiveState;
  runStartedAt?: number | null;
  onSelectNode: (nodeId: string) => void;
}) {
  const [now, setNow] = useState(() => Date.now());
  const shellRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<{
    id: string;
    x: number;
    y: number;
    data: PipelineNodeData;
  } | null>(null);

  const moveHover = (clientX: number, clientY: number, node: Node<PipelineNodeData>) => {
    const rect = shellRef.current?.getBoundingClientRect();
    if (!rect) return;
    setHover({
      id: node.id,
      x: Math.min(Math.max(clientX - rect.left + 18, 12), rect.width - 300),
      y: Math.min(Math.max(clientY - rect.top + 18, 12), rect.height - 170),
      data: node.data,
    });
  };

  useEffect(() => {
    if (!runStartedAt) return;
    const timer = window.setInterval(() => setNow(Date.now()), 180);
    return () => window.clearInterval(timer);
  }, [runStartedAt]);

  const elapsed = runStartedAt ? Math.min(20, Math.max(0, (now - runStartedAt) / 1000)) : null;
  const { nodes, edges } = useMemo(() => buildGraph(state, elapsed), [state, elapsed]);
  const latest = hover ? state.buffers[hover.id]?.at(-1) : null;
  const phaseLabel =
    elapsed == null
      ? "ready"
      : elapsed < 6.4
        ? "growing eval path"
        : elapsed < JUDGE_APPEAR_AT
          ? "running both takers"
          : elapsed < 18.5
            ? "judges turning green"
            : "decision assembled";
  const progressPercent = elapsed == null ? 0 : Math.round((elapsed / 20) * 100);

  return (
    <div ref={shellRef} className="sketch-card h-[620px] w-full overflow-hidden bg-sketch-paper">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        panOnDrag={false}
        panOnScroll={false}
        zoomOnScroll={false}
        zoomOnPinch={false}
        zoomOnDoubleClick={false}
        preventScrolling={false}
        onNodeClick={(_, node) => onSelectNode(node.id)}
        onNodeMouseEnter={(event, node) => {
          moveHover(event.clientX, event.clientY, node);
        }}
        onNodeMouseMove={(event, node) => moveHover(event.clientX, event.clientY, node)}
        onNodeMouseLeave={() => setHover(null)}
      >
        <Panel position="top-right" className="graph-timeline-label" data-testid="graph-progress">
          <div className="sticky-note bg-sketch-yellow px-3 py-2 font-hand text-xs font-bold">
            <div className="flex items-center justify-between gap-3">
              <span>{phaseLabel}</span>
              <span className="text-sketch-muted">{progressPercent}%</span>
            </div>
            <div className="graph-progress-track mt-1">
              <i style={{ width: `${progressPercent}%` }} />
            </div>
          </div>
        </Panel>
        <Background gap={24} color="#d8cfbf" />
      </ReactFlow>
      {hover ? (
        <div
          className="progress-popover pointer-events-none absolute z-20 w-[280px] bg-sketch-paper p-3"
          style={{ left: hover.x, top: hover.y }}
        >
          <div className="mb-1 flex items-center justify-between gap-2">
            <h3 className="font-hand text-sm font-bold text-sketch-ink">{hover.data.label}</h3>
            <Badge tone={hover.data.status === "done" ? "green" : hover.data.status === "running" ? "amber" : hover.data.status === "failed" ? "red" : "slate"}>
              {hover.data.status}
            </Badge>
          </div>
          {hover.data.sub ? <div className="font-hand text-xs font-bold text-sketch-muted">{hover.data.sub}</div> : null}
          <p className="mt-2 text-xs font-semibold leading-5 text-sketch-ink">{hover.data.hint}</p>
          <div className="mt-2 border-t-2 border-dashed border-sketch-ink/30 pt-2">
            <div className="font-hand text-[11px] font-bold text-sketch-muted">latest evidence</div>
            <p className="mt-1 text-xs font-semibold leading-5 text-sketch-ink">
              {latest?.text ?? "Waiting for this node to produce evidence."}
            </p>
          </div>
        </div>
      ) : null}
    </div>
  );
}
