// The whole architecture as a live React Flow graph. One full pipeline band
// (sandbox -> takers -> simulator -> judges -> assemble -> report) renders
// PER RETRIEVED CASE, so a K-case batch is K bands tall. The selected case's
// band gets fine-grained live statuses from its SSE stream; other bands
// animate coarsely from the polled batch status. Clicking anywhere in a band
// attaches the live stream to that case.
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
import type { BatchCaseState } from "../api/client";
import { ARMS, CRITERIA, type NodeStatus, type RunLiveState } from "../state/eventStore";
import { cn } from "./ui";

/** Batch context: the retrieved cases become first-class graph bands. */
export type BatchGraphContext = {
  query: string;
  cases: BatchCaseState[];
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
};

const CASE_STATUS: Record<string, NodeStatus> = {
  queued: "pending",
  running: "running",
  completed: "done",
  failed: "failed",
};

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
const X = { skills: 0, retriever: 190, cases: 390, sandbox: 600, taker: 760, judge: 950, assemble: 1240, report: 1400 };
// Vertical size of one case's pipeline band (judges span -40..480 within it).
const BAND_H = 600;

function judgeY(armIdx: number, ci: number): number {
  const base = armIdx === 0 ? -40 : 260; // baseline block above, challenger below
  return base + ci * 44;
}

/** Node status for a NON-selected band, inferred from the case's batch status. */
function coarseNode(caseStatus: string, inner: string): NodeStatus {
  if (caseStatus === "completed") return "done";
  if (caseStatus === "failed") return "failed";
  if (caseStatus === "queued") return "pending";
  // running: the repo is materialised, agents are working, judges pending
  if (inner === "sandbox") return "done";
  if (inner.startsWith("taker:") || inner === "simulator") return "running";
  return "pending";
}

export function buildGraph(
  state: RunLiveState,
  batch: BatchGraphContext,
): { nodes: Node<PipelineNodeData>[]; edges: Edge[] } {
  const n = batch.cases.length;
  const midY = ((n - 1) * BAND_H) / 2 + 150;

  const nodes: Node<PipelineNodeData>[] = [
    {
      id: "skill:baseline",
      type: "pipeline",
      position: { x: X.skills, y: midY - 30 },
      data: { label: "baseline skill", status: "done", hint: "Input #1 — injected into its taker's system prompt" },
    },
    {
      id: "skill:challenger",
      type: "pipeline",
      position: { x: X.skills, y: midY + 30 },
      data: { label: "challenger skill", status: "done", hint: "Input #2 — the only thing that differs between arms" },
    },
    {
      id: "retriever",
      type: "pipeline",
      position: { x: X.retriever, y: midY },
      data: {
        label: "vecDB retriever",
        sub: `${n} case${n === 1 ? "" : "s"}`,
        status: "done",
        hint: `Embedded your query and pulled the top-K matching test cases: "${batch.query}"`,
      },
    },
  ];
  const edges: Edge[] = [
    { id: "e-sb", source: "skill:baseline", target: "retriever" },
    { id: "e-sc", source: "skill:challenger", target: "retriever" },
  ];

  batch.cases.forEach((c, i) => {
    const off = i * BAND_H;
    const p = (inner: string) => `${c.case_id}/${inner}`;
    const isSelected = c.case_id === batch.selectedCaseId;
    const st = (inner: string): NodeStatus =>
      isSelected ? (state.nodeStatus[inner] ?? "pending") : coarseNode(c.status, inner);

    nodes.push({
      id: `case:${c.case_id}`,
      type: "pipeline",
      position: { x: X.cases, y: 150 + off },
      data: {
        label: `case ${i + 1}`,
        sub:
          c.baseline_total != null && c.challenger_total != null
            ? `B ${c.baseline_total} · C ${c.challenger_total}`
            : c.case_id,
        status: CASE_STATUS[c.status] ?? "pending",
        hint: `${c.description}${isSelected ? "" : "\n\nClick to attach the live stream to this case."}`,
      },
      className: isSelected ? "case-selected" : undefined,
    });
    edges.push({
      id: `e-r-${c.case_id}`,
      source: "retriever",
      target: `case:${c.case_id}`,
      style: { opacity: 0.45 },
    });
    edges.push({
      id: `e-c-${c.case_id}`,
      source: `case:${c.case_id}`,
      target: p("sandbox"),
      animated: c.status === "running",
    });

    nodes.push(
      {
        id: p("sandbox"),
        type: "pipeline",
        position: { x: X.sandbox, y: 150 + off },
        data: { label: "sandbox", status: st("sandbox"), hint: "Isolated git worktrees per arm + shared gold tree" },
      },
      {
        id: p("simulator"),
        type: "pipeline",
        position: { x: X.sandbox + 60, y: 320 + off },
        data: { label: "HITL simulator", status: st("simulator"), hint: "Answers clarifying questions from the gold tree (temperature=0)" },
      },
      {
        id: p("assemble"),
        type: "pipeline",
        position: { x: X.assemble, y: 150 + off },
        data: { label: "assemble", status: st("assemble"), hint: "Median of replicate judges, totals, verdict" },
      },
      {
        id: p("report"),
        type: "pipeline",
        position: { x: X.report, y: 150 + off },
        data: { label: "report", status: st("report"), hint: "The comparison report — archived to runs/" },
      },
    );
    edges.push({ id: `e-ar-${c.case_id}`, source: p("assemble"), target: p("report") });

    ARMS.forEach((arm, ai) => {
      const takerId = p(`taker:${arm}`);
      nodes.push({
        id: takerId,
        type: "pipeline",
        position: { x: X.taker, y: (ai === 0 ? 40 : 380) + off },
        data: {
          label: `${arm} taker`,
          sub: isSelected ? (state.takers[arm]?.status ?? "pending") : c.status,
          status: st(`taker:${arm}`),
          hint: "Coding agent under this arm's skill — click for its live thinking",
        },
      });
      edges.push({ id: `e-s-${arm}-${c.case_id}`, source: p("sandbox"), target: takerId });
      edges.push({
        id: `e-sim-${arm}-${c.case_id}`,
        source: takerId,
        target: p("simulator"),
        animated: st("simulator") === "running",
        style: { strokeDasharray: "4 3", opacity: 0.5 },
      });

      CRITERIA.forEach((cr, ci) => {
        const judgeId = p(`judge:${arm}:${cr}`);
        const cell = isSelected ? state.judges[`${arm}:${cr}`] : undefined;
        nodes.push({
          id: judgeId,
          type: "pipeline",
          position: { x: X.judge, y: judgeY(ai, ci) + off },
          data: {
            label: cr,
            sub: cell?.score != null ? `${cell.score}/20` : undefined,
            status: st(`judge:${arm}:${cr}`),
            hint: "Click for the judge's rationale",
          },
        });
        edges.push({ id: `e-t-${arm}-${cr}-${c.case_id}`, source: takerId, target: judgeId });
        edges.push({
          id: `e-j-${arm}-${cr}-${c.case_id}`,
          source: judgeId,
          target: p("assemble"),
          style: { opacity: 0.35 },
        });
      });
    });
  });

  return { nodes, edges };
}

/** Case id for any clickable graph node: "case:<id>" tiles or "<id>/inner" band nodes. */
function caseIdOf(nodeId: string): string | null {
  if (nodeId.startsWith("case:")) return nodeId.slice("case:".length);
  const slash = nodeId.indexOf("/");
  return slash > 0 ? nodeId.slice(0, slash) : null;
}

export function PipelineGraph({
  state,
  onSelectNode,
  batch,
}: {
  state: RunLiveState;
  onSelectNode: (nodeId: string) => void;
  batch: BatchGraphContext;
}) {
  const { nodes, edges } = useMemo(() => buildGraph(state, batch), [state, batch]);
  return (
    <div className="h-[560px] w-full rounded-xl border border-slate-200 bg-white">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        // K bands stack to several thousand px; fitView must be allowed to
        // zoom far out or it crops the graph.
        minZoom={0.04}
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        onNodeClick={(_, node) => {
          onSelectNode(node.id);
          // Clicking anywhere in a band switches which case is being watched.
          const cid = caseIdOf(node.id);
          if (cid) batch.onSelectCase(cid);
        }}
        onNodeMouseEnter={(_, node) => onSelectNode(node.id)}
      >
        <Background gap={24} />
      </ReactFlow>
    </div>
  );
}
