// SCREEN 2 form: a retrieval query replaces the old fixture dropdown and
// task-brief box — the vecDB retriever picks the K test cases, and each
// retrieved case carries its own task description. Styling follows the
// SkillForge sketch system (skill-card-strip, run-eval-button, sticky notes).
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import {
  api,
  type CreateBatchRequest,
  type FixtureInfo,
  type RetrievedCase,
} from "../api/client";
import { Field, inputClass } from "./ui";

export function RunForm({
  running,
  onSubmit,
}: {
  running: boolean;
  onSubmit: (req: CreateBatchRequest) => void;
}) {
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
  const [error, setError] = useState<string | null>(null);

  // Prefill the two skill cards once with the server's default pair.
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

  function removeCase(caseId: string) {
    setPreview((p) => (p ? p.filter((c) => c.case_id !== caseId) : p));
  }

  function submit() {
    onSubmit({
      query,
      top_k: topK,
      // After a preview the user may have dropped cases: run exactly the
      // surviving list instead of letting the server re-retrieve.
      case_ids: preview ? preview.map((c) => c.case_id) : undefined,
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
  }

  return (
    <div className="sketch-card bg-sketch-paper p-4">
      <Field
        label="What should we evaluate? — the retriever pulls the matching test cases from the vector DB; each case carries its own task description"
        className="mb-3"
      >
        <textarea
          className={`${inputClass} h-16 font-mono text-xs`}
          placeholder='e.g. "logging improvement for the payment api, banking team"'
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setPreview(null); // a new query invalidates the pruned selection
          }}
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
        <label className="flex items-end gap-2 pb-2 text-sm font-bold text-sketch-ink">
          <input
            type="checkbox"
            checked={realAgents}
            onChange={(e) => setRealAgents(e.target.checked)}
            data-testid="real-agents-toggle"
          />
          Real Haiku agents (~$0.40 × K)
        </label>
        <div className="flex items-end pb-1">
          <button
            type="button"
            className="font-hand rounded-[12px_9px_13px_8px] border-2 border-sketch-ink bg-sketch-paper px-4 py-2 text-sm font-bold shadow-[4px_4px_0_rgba(48,42,37,0.18)] transition-transform hover:-rotate-1 disabled:opacity-40"
            disabled={!query.trim() || previewing}
            onClick={doPreview}
            data-testid="batch-preview"
          >
            {previewing ? "Retrieving…" : "Preview retrieval"}
          </button>
        </div>
      </div>

      {preview ? (
        <div className="mt-3">
          <p className="font-hand text-xs font-bold text-sketch-muted">
            {preview.length === 0
              ? "All cases dropped — preview again or loosen the query."
              : `Running ${preview.length} case${preview.length === 1 ? "" : "s"} — drop any you don't want.`}
          </p>
          <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2" data-scroll-free>
            {preview.map((c, i) => (
              <div
                key={c.case_id}
                className={`sticky-note relative p-2 pr-8 text-xs font-semibold ${i % 2 === 0 ? "rotate-[-0.4deg] bg-sketch-yellow" : "rotate-[0.4deg] bg-sketch-blue"}`}
                data-testid={`preview-case-${c.case_id}`}
              >
                <button
                  type="button"
                  aria-label={`Drop ${c.case_id} from this batch`}
                  title="Drop this case from the batch"
                  className="remove-skill-button absolute right-1.5 top-1.5"
                  onClick={() => removeCase(c.case_id)}
                  data-testid={`drop-case-${c.case_id}`}
                >
                  ×
                </button>
                <span className="font-hand font-bold">case {i + 1} · {c.case_id}</span>
                {c.distance != null && (
                  <span className="ml-1 text-sketch-muted">d={Number(c.distance).toFixed(3)}</span>
                )}
                <p className="mt-1 line-clamp-2">{c.description}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* The two skills under test, as tinted hand-drawn cards. */}
      <div className="skill-card-strip mt-4" data-scroll-free>
        <div className="skill-input-card bg-sketch-pink">
          <span className="font-hand rounded-[12px_9px_13px_8px] border-2 border-sketch-ink bg-sketch-paper px-2 py-0.5 text-xs font-bold">
            skill 1 · baseline
          </span>
          <Field label="Name" className="mt-2">
            <input className={inputClass} value={baseName} onChange={(e) => setBaseName(e.target.value)} />
          </Field>
          <Field label="SKILL.md" className="mt-2">
            <textarea
              className={`${inputClass} h-44 font-mono text-xs`}
              value={baseMd}
              onChange={(e) => setBaseMd(e.target.value)}
            />
          </Field>
        </div>
        <div className="skill-input-card bg-sketch-blue">
          <span className="font-hand rounded-[12px_9px_13px_8px] border-2 border-sketch-ink bg-sketch-paper px-2 py-0.5 text-xs font-bold">
            skill 2 · challenger
          </span>
          <Field label="Name" className="mt-2">
            <input className={inputClass} value={chalName} onChange={(e) => setChalName(e.target.value)} />
          </Field>
          <Field label="SKILL.md" className="mt-2">
            <textarea
              className={`${inputClass} h-44 font-mono text-xs`}
              value={chalMd}
              onChange={(e) => setChalMd(e.target.value)}
            />
          </Field>
        </div>
      </div>

      {error && <p className="mt-2 text-xs font-bold text-sketch-red">{error}</p>}

      {/* SCREEN 2 ends at this button in the demo sequence. */}
      <div className="mt-4 flex justify-center">
        <button
          type="button"
          className="run-eval-button font-hand min-w-[280px] border-2 border-sketch-ink bg-sketch-yellow px-10 py-4 text-xl font-bold text-sketch-ink disabled:opacity-40"
          disabled={!query.trim() || running || (preview !== null && preview.length === 0)}
          onClick={submit}
          data-testid="run-button"
        >
          {running
            ? "Running…"
            : preview
              ? `Run eval (${preview.length} case${preview.length === 1 ? "" : "s"})`
              : "Run eval"}
        </button>
      </div>
    </div>
  );
}
