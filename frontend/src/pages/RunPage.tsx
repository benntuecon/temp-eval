// Run page: form -> live architecture graph + node thinking panel -> results.
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, subscribeEvents, type CreateRunRequest } from "../api/client";
import { NodePanel } from "../components/NodePanel";
import { PipelineGraph } from "../components/PipelineGraph";
import { ResultsFunnel } from "../components/ResultsFunnel";
import { RunForm } from "../components/RunForm";
import { initialRunState, reduceEvent, type RunLiveState } from "../state/eventStore";

export function RunPage() {
  const [runId, setRunId] = useState<string | null>(null);
  const [live, setLive] = useState<RunLiveState>(initialRunState);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const unsubscribe = useRef<(() => void) | null>(null);

  const start = useCallback(async (req: CreateRunRequest) => {
    unsubscribe.current?.();
    setLive(initialRunState());
    const summary = await api.createRun(req);
    setRunId(summary.run_id);
    unsubscribe.current = subscribeEvents(summary.run_id, (ev) =>
      setLive((s) => reduceEvent(s, ev)),
    );
  }, []);

  useEffect(() => () => unsubscribe.current?.(), []);

  // Fetch the typed report once the stream says the run completed.
  const detail = useQuery({
    queryKey: ["run", runId, live.runStatus],
    queryFn: () => api.runDetail(runId!),
    enabled: runId != null && live.runStatus === "completed",
  });

  return (
    <div className="space-y-4">
      <RunForm running={live.runStatus === "running"} onSubmit={start} />

      <div>
        <h2 className="mb-1 text-sm font-semibold text-slate-800">
          Pipeline{" "}
          <span className="font-normal text-slate-500">
            — hover or click any node to see what it's thinking
          </span>
        </h2>
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[2fr_1fr]">
          <PipelineGraph state={live} onSelectNode={setSelectedNode} />
          <NodePanel state={live} nodeId={selectedNode} />
        </div>
      </div>

      {live.runStatus === "failed" && (
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-800">Run failed: {live.error}</div>
      )}

      {detail.data?.report ? <ResultsFunnel report={detail.data.report} /> : null}
    </div>
  );
}
