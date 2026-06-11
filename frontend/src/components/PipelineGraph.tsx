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
import { useMemo } from "react";
import { ARMS, CRITERIA, type NodeStatus, type RunLiveState } from "../state/eventStore";
import { cn } from "./ui";

const STATUS_BG: Record<NodeStatus, string> = {
  pending: "bg-slate-200 border-slate-300 text-slate-700",
  running: "bg-amber-300 border-amber-500 text-amber-950 node-running",
  done: "bg-green-300 border-green-600 text-green-950",
  failed: "bg-red-300 border-red-600 text-red-950",
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
        "rounded-lg border px-3 py-1.5 text-center text-xs font-medium shadow-sm",
        STATUS_BG[data.status],
      )}
    >
      <Handle type="target" position={Position.Left} className="!bg-slate-400" />
      <div>{data.label}</div>
      {data.sub ? <div className="text-[10px] opacity-75">{data.sub}</div> : null}
      <Handle type="source" position={Position.Right} className="!bg-slate-400" />
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
    { id: "e-sb", source: "skill:baseline", target: "test_generator" },
    { id: "e-sc", source: "skill:challenger", target: "test_generator" },
    { id: "e-gc", source: "test_generator", target: "test_cases" },
    { id: "e-cs", source: "test_cases", target: "sandbox" },
    { id: "e-ar", source: "assemble", target: "report" },
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
    edges.push({ id: `e-s-${arm}`, source: "sandbox", target: takerId });
    edges.push({
      id: `e-sim-${arm}`,
      source: takerId,
      target: "simulator",
      animated: s["simulator"] === "running",
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
      edges.push({ id: `e-t-${arm}-${c}`, source: takerId, target: judgeId });
      edges.push({ id: `e-j-${arm}-${c}`, source: judgeId, target: "assemble", style: { opacity: 0.35 } });
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
  return (
    <div className="h-[560px] w-full rounded-xl border border-slate-200 bg-white">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        onNodeClick={(_, node) => onSelectNode(node.id)}
        onNodeMouseEnter={(_, node) => onSelectNode(node.id)}
      >
        <Background gap={24} />
      </ReactFlow>
    </div>
  );
}
