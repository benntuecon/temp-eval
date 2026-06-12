// The whole architecture as a live React Flow graph. Nodes light up
// grey -> gold(pulse) -> green as events stream in; clicking/hovering a node
// opens the side panel with that agent's live thinking buffer.
import {
  Background,
  Handle,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
} from "@xyflow/react";
import { useMemo, useRef, useState } from "react";
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
};

function PipelineNode({ data }: NodeProps<Node<PipelineNodeData>>) {
  return (
    <div
      title={data.hint}
      className={cn(
        "font-hand rounded-[14px_10px_15px_11px] border-2 px-3 py-1.5 text-center text-xs font-bold shadow-[4px_4px_0_rgba(48,42,37,0.15)] transition-transform hover:rotate-1",
        STATUS_BG[data.status],
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

function judgeY(armIdx: number, ci: number): number {
  const base = armIdx === 0 ? -40 : 260; // baseline block above, challenger below
  return base + ci * 44;
}

export function buildGraph(state: RunLiveState): { nodes: Node<PipelineNodeData>[]; edges: Edge[] } {
  const s = state.nodeStatus;
  const isMovingTo = (target: string) => s[target] === "running";
  const isMovingFrom = (source: string, target: string) =>
    s[source] === "done" && (s[target] === "pending" || s[target] === "running");
  const nodes: Node<PipelineNodeData>[] = [
    {
      id: "skill:baseline",
      type: "pipeline",
      position: { x: X.skills, y: 120 },
      data: { label: "baseline skill", status: s["skill:baseline"], hint: "Input #1 — injected into its taker's system prompt" },
    },
    {
      id: "skill:challenger",
      type: "pipeline",
      position: { x: X.skills, y: 180 },
      data: { label: "challenger skill", status: s["skill:challenger"], hint: "Input #2 — the only thing that differs between arms" },
    },
    {
      id: "test_generator",
      type: "pipeline",
      position: { x: X.generator, y: 150 },
      data: { label: "test generator", sub: "(mock service)", status: s["test_generator"], hint: "Designs a test case that can tell the two skills apart" },
    },
    {
      id: "test_cases",
      type: "pipeline",
      position: { x: X.cases, y: 150 },
      data: { label: "test cases", sub: "before/after project", status: s["test_cases"], hint: "The eval payload: a before-project + a gold after-project" },
    },
    {
      id: "sandbox",
      type: "pipeline",
      position: { x: X.sandbox, y: 150 },
      data: { label: "sandbox", status: s["sandbox"], hint: "Isolated git worktrees per arm + shared gold tree" },
    },
    {
      id: "simulator",
      type: "pipeline",
      position: { x: X.sandbox + 60, y: 320 },
      data: { label: "HITL simulator", status: s["simulator"], hint: "Answers clarifying questions from the gold tree (temperature=0)" },
    },
    {
      id: "assemble",
      type: "pipeline",
      position: { x: X.assemble, y: 150 },
      data: { label: "assemble", status: s["assemble"], hint: "Median of replicate judges, totals, verdict" },
    },
    {
      id: "report",
      type: "pipeline",
      position: { x: X.report, y: 150 },
      data: { label: "report", status: s["report"], hint: "The comparison report — rendered below and archived" },
    },
  ];

  const edges: Edge[] = [
    { id: "e-sb", source: "skill:baseline", target: "test_generator", animated: isMovingTo("test_generator") },
    { id: "e-sc", source: "skill:challenger", target: "test_generator", animated: isMovingTo("test_generator") },
    { id: "e-gc", source: "test_generator", target: "test_cases", animated: isMovingFrom("test_generator", "test_cases") },
    { id: "e-cs", source: "test_cases", target: "sandbox", animated: isMovingTo("sandbox") },
    { id: "e-ar", source: "assemble", target: "report", animated: isMovingFrom("assemble", "report") || isMovingTo("report") },
  ];

  ARMS.forEach((arm, ai) => {
    const takerId = `taker:${arm}`;
    nodes.push({
      id: takerId,
      type: "pipeline",
      position: { x: X.taker, y: ai === 0 ? 40 : 380 },
      data: {
        label: `${arm} taker`,
        sub: state.takers[arm]?.status ?? "pending",
        status: s[takerId],
        hint: "Coding agent under this arm's skill — click for its live thinking",
      },
    });
    edges.push({ id: `e-s-${arm}`, source: "sandbox", target: takerId, animated: isMovingTo(takerId) });
    edges.push({
      id: `e-sim-${arm}`,
      source: takerId,
      target: "simulator",
      animated: s["simulator"] === "running" || s[takerId] === "running",
      style: { strokeDasharray: "4 3", opacity: 0.5 },
    });

    CRITERIA.forEach((c, ci) => {
      const judgeId = `judge:${arm}:${c}`;
      const cell = state.judges[`${arm}:${c}`];
      nodes.push({
        id: judgeId,
        type: "pipeline",
        position: { x: X.judge, y: judgeY(ai, ci) },
        data: {
          label: c,
          sub: cell?.score != null ? `${cell.score}/20` : undefined,
          status: s[judgeId],
          hint: "Click for the judge's rationale",
        },
      });
      edges.push({ id: `e-t-${arm}-${c}`, source: takerId, target: judgeId, animated: isMovingTo(judgeId) });
      edges.push({
        id: `e-j-${arm}-${c}`,
        source: judgeId,
        target: "assemble",
        animated: isMovingFrom(judgeId, "assemble") || isMovingTo("assemble"),
        style: { opacity: 0.35 },
      });
    });
  });

  return { nodes, edges };
}

export function PipelineGraph({
  state,
  onSelectNode,
}: {
  state: RunLiveState;
  onSelectNode: (nodeId: string) => void;
}) {
  const { nodes, edges } = useMemo(() => buildGraph(state), [state]);
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

  const latest = hover ? state.buffers[hover.id]?.at(-1) : null;

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
        onNodeClick={(_, node) => onSelectNode(node.id)}
        onNodeMouseEnter={(event, node) => {
          onSelectNode(node.id);
          moveHover(event.clientX, event.clientY, node);
        }}
        onNodeMouseMove={(event, node) => moveHover(event.clientX, event.clientY, node)}
        onNodeMouseLeave={() => setHover(null)}
      >
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
