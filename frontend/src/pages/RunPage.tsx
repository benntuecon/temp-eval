// Run eval: a retrieval query drives everything — the vecDB picks the K test
// cases (each carrying its own task description), every case runs as a child
// eval, stats aggregate live, and any case on the board can be opened to
// watch its pipeline in real time.
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  api,
  subscribeEvents,
  type BatchCaseState,
  type FixtureInfo,
  type RetrievedCase,
} from "../api/client";
import { BatchStats } from "../components/BatchStats";
import { NodePanel } from "../components/NodePanel";
import { PipelineGraph } from "../components/PipelineGraph";
import { ResultsFunnel } from "../components/ResultsFunnel";
import { Badge, Button, Card, Field, cn, inputClass } from "../components/ui";
import { initialRunState, reduceEvent, type RunLiveState } from "../state/eventStore";

const STATUS_TONE: Record<string, "slate" | "blue" | "green" | "red"> = {
  queued: "slate",
  running: "blue",
  completed: "green",
  failed: "red",
};

/** Live pipeline + results for one child run (SSE replays history, so this
 *  works for already-finished cases too). */
function CaseLiveView({ runId }: { runId: string }) {
  const [live, setLive] = useState<RunLiveState>(initialRunState);
  const [selectedNode, setSelectedNode] = useState<string | null>(null);

  useEffect(() => {
    setLive(initialRunState());
    return subscribeEvents(runId, (ev) => setLive((s) => reduceEvent(s, ev)));
  }, [runId]);

  const detail = useQuery({
    queryKey: ["run", runId, live.runStatus],
    queryFn: () => api.runDetail(runId),
    enabled: live.runStatus === "completed",
  });

  return (
    <div className="space-y-4">
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
        <div className="rounded-lg bg-red-50 p-3 text-sm text-red-800">
          Run failed: {live.error}
        </div>
      )}

      {detail.data?.report ? <ResultsFunnel report={detail.data.report} /> : null}
    </div>
  );
}

function CaseRow({
  c,
  selected,
  onSelect,
}: {
  c: BatchCaseState | RetrievedCase;
  selected?: boolean;
  onSelect?: () => void;
}) {
  const status = "status" in c ? c.status : null;
  const distance = c.distance == null ? null : Number(c.distance).toFixed(3);
  const clickable = Boolean(onSelect && "run_id" in c && c.run_id);
  return (
    <div
      className={cn(
        "flex items-start gap-3 border-b border-slate-100 py-2 last:border-0",
        clickable && "cursor-pointer hover:bg-slate-50",
        selected && "bg-blue-50/60",
      )}
      onClick={clickable ? onSelect : undefined}
    >
      {status ? (
        <Badge tone={STATUS_TONE[status] ?? "slate"}>{status}</Badge>
      ) : (
        <Badge tone="slate">retrieved</Badge>
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span className="text-sm font-medium text-slate-800">{c.case_id}</span>
          {distance && <span className="text-xs text-slate-400">distance {distance}</span>}
          {"baseline_total" in c && c.baseline_total != null && c.challenger_total != null && (
            <span className="text-xs tabular-nums text-slate-600">
              baseline {c.baseline_total} · challenger {c.challenger_total}
            </span>
          )}
          {clickable && (
            <span className="ml-auto shrink-0 text-xs text-blue-600">
              {selected ? "watching" : "watch →"}
            </span>
          )}
        </div>
        <p className="truncate text-xs text-slate-500" title={c.description}>
          {c.description}
        </p>
        {"verdict" in c && c.verdict && (
          <p className="text-xs font-medium text-slate-700">{c.verdict}</p>
        )}
      </div>
    </div>
  );
}

export function RunPage() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(10);
  const [wallClock, setWallClock] = useState(180);
  const [maxConcurrent, setMaxConcurrent] = useState(""); // "" = all at once
  const [realAgents, setRealAgents] = useState(false);
  const [baseName, setBaseName] = useState("");
  const [baseMd, setBaseMd] = useState("");
  const [chalName, setChalName] = useState("");
  const [chalMd, setChalMd] = useState("");
  const [preview, setPreview] = useState<RetrievedCase[] | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [starting, setStarting] = useState(false);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [selectedCase, setSelectedCase] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Prefill the skill editors once with the server's default pair.
  const fixtures = useQuery({ queryKey: ["fixtures"], queryFn: api.fixtures });
  const prefilled = useRef(false);
  useEffect(() => {
    const fx: FixtureInfo | undefined = fixtures.data?.[0];
    if (!fx || prefilled.current) return;
    prefilled.current = true;
    setBaseName(fx.default_baseline.name);
    setBaseMd(fx.default_baseline.markdown);
    setChalName(fx.default_challenger.name);
    setChalMd(fx.default_challenger.markdown);
  }, [fixtures.data]);

  const detail = useQuery({
    queryKey: ["batch", batchId],
    queryFn: () => api.batchDetail(batchId!),
    enabled: !!batchId,
    refetchInterval: (q) => (q.state.data?.summary.status === "running" ? 2000 : false),
  });

  const running = detail.data?.summary.status === "running";

  // Auto-open the first launched case so the pipeline lights up immediately.
  useEffect(() => {
    if (selectedCase || !detail.data) return;
    const first = detail.data.cases.find((c) => c.run_id);
    if (first) setSelectedCase(first.case_id);
  }, [detail.data, selectedCase]);

  async function doPreview() {
    setPreviewing(true);
    setError(null);
    try {
      setPreview(await api.retrieve(query, topK));
    } catch (e) {
      setError(String(e));
    } finally {
      setPreviewing(false);
    }
  }

  async function start() {
    setStarting(true);
    setError(null);
    try {
      const { batch_id } = await api.createBatch({
        query,
        top_k: topK,
        baseline: baseMd.trim()
          ? { name: baseName.trim() || "baseline", markdown: baseMd }
          : undefined,
        challenger: chalMd.trim()
          ? { name: chalName.trim() || "challenger", markdown: chalMd }
          : undefined,
        max_turns: 16,
        thinking_budget: 2048,
        wall_clock_seconds: wallClock,
        judges_per_criterion: 1,
        real_agents: realAgents,
        max_concurrent: maxConcurrent === "" ? null : Number(maxConcurrent),
      });
      setPreview(null);
      setSelectedCase(null);
      setBatchId(batch_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setStarting(false);
    }
  }

  const selected = detail.data?.cases.find((c) => c.case_id === selectedCase);

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <Field
          label="What should we evaluate? — the retriever picks matching test cases from the vector DB; each case carries its own task description"
          className="mb-3"
        >
          <textarea
            className={`${inputClass} h-16 font-mono text-xs`}
            placeholder='e.g. "logging improvement for the payment api, banking team"'
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            data-testid="batch-query"
          />
        </Field>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
          <Field label="Top K cases">
            <input
              type="number"
              min={1}
              max={50}
              className={inputClass}
              value={topK}
              onChange={(e) => setTopK(Number(e.target.value))}
              data-testid="batch-topk"
            />
          </Field>
          <Field label="Wall clock per run (s)">
            <input
              type="number"
              min={10}
              max={3600}
              step={30}
              className={inputClass}
              value={wallClock}
              onChange={(e) => setWallClock(Number(e.target.value))}
            />
          </Field>
          <Field label="Max concurrent (blank = all)">
            <input
              type="number"
              min={1}
              max={50}
              placeholder="all"
              className={inputClass}
              value={maxConcurrent}
              onChange={(e) => setMaxConcurrent(e.target.value)}
            />
          </Field>
          <label className="flex items-end gap-2 pb-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={realAgents}
              onChange={(e) => setRealAgents(e.target.checked)}
              data-testid="real-agents-toggle"
            />
            Real Haiku agents (~$0.40 × K)
          </label>
          <div className="flex items-end gap-2 pb-0.5">
            <Button
              variant="outline"
              disabled={!query.trim() || previewing}
              onClick={doPreview}
              data-testid="batch-preview"
            >
              {previewing ? "Retrieving…" : "Preview"}
            </Button>
            <Button
              disabled={!query.trim() || starting || running}
              onClick={start}
              data-testid="run-button"
            >
              {starting ? "Starting…" : running ? "Running…" : "Run eval"}
            </Button>
          </div>
        </div>

        <details className="mt-3">
          <summary className="cursor-pointer text-xs text-slate-500">
            Skills under test: {baseName || "logging-naive"} (baseline) vs{" "}
            {chalName || "logging-best-practices"} (challenger) — click to edit
          </summary>
          <div className="mt-2 grid grid-cols-1 gap-3 lg:grid-cols-2">
            <div>
              <Field label="Baseline skill name">
                <input
                  className={inputClass}
                  value={baseName}
                  onChange={(e) => setBaseName(e.target.value)}
                />
              </Field>
              <Field label="Baseline SKILL.md" className="mt-2">
                <textarea
                  className={`${inputClass} h-44 font-mono text-xs`}
                  value={baseMd}
                  onChange={(e) => setBaseMd(e.target.value)}
                />
              </Field>
            </div>
            <div>
              <Field label="Challenger skill name">
                <input
                  className={inputClass}
                  value={chalName}
                  onChange={(e) => setChalName(e.target.value)}
                />
              </Field>
              <Field label="Challenger SKILL.md" className="mt-2">
                <textarea
                  className={`${inputClass} h-44 font-mono text-xs`}
                  value={chalMd}
                  onChange={(e) => setChalMd(e.target.value)}
                />
              </Field>
            </div>
          </div>
        </details>

        {error && <p className="mt-2 text-xs text-red-600">{error}</p>}
        {detail.error != null && (
          <p className="mt-2 text-xs text-red-600">
            batch status fetch failing: {String(detail.error)}
          </p>
        )}
      </Card>

      {preview && (
        <Card className="p-4">
          <h3 className="mb-2 text-sm font-semibold text-slate-700">
            Retriever picked {preview.length} case{preview.length === 1 ? "" : "s"}
          </h3>
          {preview.map((c) => (
            <CaseRow key={c.case_id} c={c} />
          ))}
        </Card>
      )}

      {detail.data && (
        <>
          <Card className="p-4" data-testid="batch-board">
            <div className="mb-2 flex items-center gap-3">
              <h3 className="text-sm font-semibold text-slate-700">
                Batch {detail.data.summary.batch_id}
              </h3>
              <Badge
                tone={
                  detail.data.summary.status === "completed"
                    ? "green"
                    : detail.data.summary.status === "running"
                      ? "blue"
                      : "amber"
                }
              >
                {detail.data.summary.status}
              </Badge>
              <span className="text-xs text-slate-500">
                {detail.data.summary.completed}/{detail.data.summary.total} completed
                {detail.data.summary.failed > 0 && ` · ${detail.data.summary.failed} failed`}
              </span>
            </div>
            {detail.data.cases.map((c) => (
              <CaseRow
                key={c.case_id}
                c={c}
                selected={c.case_id === selectedCase}
                onSelect={() => setSelectedCase(c.case_id)}
              />
            ))}
          </Card>

          {selected?.run_id && <CaseLiveView key={selected.run_id} runId={selected.run_id} />}

          {detail.data.stats && (
            <BatchStats
              stats={detail.data.stats}
              partial={detail.data.summary.status === "running"}
            />
          )}
        </>
      )}
    </div>
  );
}
