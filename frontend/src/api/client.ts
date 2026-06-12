// Thin typed wrapper over the generated OpenAPI schema (src/api/schema.d.ts).
// Regenerate with `just gen-client` — the types cannot drift from the backend.
import type { components, paths } from "./schema";

export type RunSummary = components["schemas"]["RunSummary"];
export type RunDetail = components["schemas"]["RunDetail"];
export type FixtureInfo = components["schemas"]["FixtureInfo"];
export type CreateRunRequest = components["schemas"]["CreateRunRequest"];
export type ComparisonReport = components["schemas"]["ComparisonReport"];
export type ArmReport = components["schemas"]["ArmReport"];
export type JudgeScore = components["schemas"]["JudgeScore"];
export type SkillInput = components["schemas"]["SkillInput"];
export type RetrievedCase = components["schemas"]["RetrievedCase"];
export type CreateBatchRequest = components["schemas"]["CreateBatchRequest"];
export type BatchSummary = components["schemas"]["BatchSummary"];
export type BatchDetail = components["schemas"]["BatchDetail"];
export type BatchCaseState = components["schemas"]["BatchCaseState"];
export type BatchStats = components["schemas"]["BatchStats"];

// The SSE payload union, lifted from the documentation-only endpoint.
export type RunEvent =
  paths["/api/schema/event-types"]["get"]["responses"]["200"]["content"]["application/json"][number];

const BASE = ""; // same-origin; vite dev proxies /api -> :8600

async function json<T>(resp: Response): Promise<T> {
  if (!resp.ok) {
    const body = await resp.text().catch(() => "");
    throw new Error(`${resp.status} ${resp.statusText}: ${body.slice(0, 300)}`);
  }
  return (await resp.json()) as T;
}

export const api = {
  health: () => fetch(`${BASE}/api/health`).then((r) => json<components["schemas"]["HealthInfo"]>(r)),
  fixtures: () => fetch(`${BASE}/api/fixtures`).then((r) => json<FixtureInfo[]>(r)),
  runs: () => fetch(`${BASE}/api/runs`).then((r) => json<RunSummary[]>(r)),
  runDetail: (runId: string) =>
    fetch(`${BASE}/api/runs/${runId}`).then((r) => json<RunDetail>(r)),
  createRun: (req: CreateRunRequest) =>
    fetch(`${BASE}/api/runs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    }).then((r) => json<RunSummary>(r)),
  retrieve: (query: string, k: number) =>
    fetch(`${BASE}/api/retrieve?query=${encodeURIComponent(query)}&k=${k}`).then((r) =>
      json<RetrievedCase[]>(r),
    ),
  createBatch: (req: CreateBatchRequest) =>
    fetch(`${BASE}/api/batches`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    }).then((r) => json<{ batch_id: string }>(r)),
  batches: () => fetch(`${BASE}/api/batches`).then((r) => json<BatchSummary[]>(r)),
  batchDetail: (batchId: string) =>
    fetch(`${BASE}/api/batches/${batchId}`).then((r) => json<BatchDetail>(r)),
};

/** Subscribe to a run's live event stream. Returns an unsubscribe fn. */
export function subscribeEvents(
  runId: string,
  onEvent: (ev: RunEvent) => void,
  onError?: (err: Event) => void,
): () => void {
  const source = new EventSource(`${BASE}/api/runs/${runId}/events`);
  source.onmessage = (msg) => {
    try {
      const ev = JSON.parse(msg.data) as RunEvent;
      onEvent(ev);
      // The stream is finite: close after the terminal event so EventSource
      // doesn't auto-reconnect and replay forever.
      if (ev.type === "run_completed" || ev.type === "run_failed") {
        source.close();
      }
    } catch {
      // ignore malformed frames (heartbeats arrive as comments, not messages)
    }
  };
  if (onError) source.onerror = onError;
  return () => source.close();
}
