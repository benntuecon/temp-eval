// Batch eval: a retrieval query replaces the fixture dropdown — the
// retriever picks the K test cases, all of them run, stats aggregate live.
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api, type BatchCaseState, type RetrievedCase } from "../api/client";
import { BatchStats } from "../components/BatchStats";
import { Badge, Button, Card, Field, inputClass } from "../components/ui";

const STATUS_TONE: Record<string, "slate" | "blue" | "green" | "red"> = {
  queued: "slate",
  running: "blue",
  completed: "green",
  failed: "red",
};

function CaseRow({ c }: { c: BatchCaseState | RetrievedCase }) {
  const status = "status" in c ? c.status : null;
  const distance = c.distance == null ? null : Number(c.distance).toFixed(3);
  return (
    <div className="flex items-start gap-3 border-b border-slate-100 py-2 last:border-0">
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

export function BatchPage() {
  const [query, setQuery] = useState("");
  const [topK, setTopK] = useState(10);
  const [maxConcurrent, setMaxConcurrent] = useState(""); // "" = all at once
  const [wallClock, setWallClock] = useState(180);
  const [realAgents, setRealAgents] = useState(false);
  const [preview, setPreview] = useState<RetrievedCase[] | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [starting, setStarting] = useState(false);
  const [batchId, setBatchId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const detail = useQuery({
    queryKey: ["batch", batchId],
    queryFn: () => api.batchDetail(batchId!),
    enabled: !!batchId,
    refetchInterval: (q) => (q.state.data?.summary.status === "running" ? 2000 : false),
  });

  const running = detail.data?.summary.status === "running";

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
        max_turns: 16,
        thinking_budget: 2048,
        wall_clock_seconds: wallClock,
        judges_per_criterion: 1,
        real_agents: realAgents,
        max_concurrent: maxConcurrent === "" ? null : Number(maxConcurrent),
      });
      setPreview(null);
      setBatchId(batch_id);
    } catch (e) {
      setError(String(e));
    } finally {
      setStarting(false);
    }
  }

  return (
    <div className="space-y-4">
      <Card className="p-4">
        <Field label="Retrieval query — the retriever picks the test cases" className="mb-3">
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
              data-testid="batch-real-agents"
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
              {previewing ? "Retrieving…" : "Preview retrieval"}
            </Button>
            <Button
              disabled={!query.trim() || starting || running}
              onClick={start}
              data-testid="batch-run"
            >
              {starting ? "Starting…" : running ? "Running…" : "Run batch eval"}
            </Button>
          </div>
        </div>
        <p className="mt-2 text-xs text-slate-400">
          Skills: logging-naive (baseline) vs logging-best-practices (challenger) — server
          defaults.
        </p>
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
              <CaseRow key={c.case_id} c={c} />
            ))}
          </Card>

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
