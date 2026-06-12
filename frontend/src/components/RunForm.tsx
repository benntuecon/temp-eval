// Run configuration: two skills in, everything else sensible defaults.
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, type CreateRunRequest, type FixtureInfo } from "../api/client";
import { DEMO_FIXTURES } from "../mockRun";
import { Button, Card, Field, inputClass } from "./ui";

export function RunForm({
  running,
  onSubmit,
}: {
  running: boolean;
  onSubmit: (req: CreateRunRequest) => void;
}) {
  const fixtures = useQuery({ queryKey: ["fixtures"], queryFn: api.fixtures });

  const [fixtureId, setFixtureId] = useState("flagship");
  const [brief, setBrief] = useState("");
  const [baseName, setBaseName] = useState("ship-it-fast");
  const [baseMd, setBaseMd] = useState("");
  const [chalName, setChalName] = useState("disciplined");
  const [chalMd, setChalMd] = useState("");
  const [maxTurns, setMaxTurns] = useState(30);
  const [thinking, setThinking] = useState(2048);
  const [judgeModel, setJudgeModel] = useState("claude-haiku-4-5");
  const [judgesK, setJudgesK] = useState(1);
  const [realAgents, setRealAgents] = useState(false);
  const fixtureOptions = fixtures.data?.length ? fixtures.data : DEMO_FIXTURES;

  // Prefill from the selected fixture once fixtures arrive.
  useEffect(() => {
    const fx = fixtureOptions.find((f: FixtureInfo) => f.id === fixtureId);
    if (!fx) return;
    setBrief(fx.brief);
    setBaseName(fx.default_baseline.name);
    setBaseMd(fx.default_baseline.markdown);
    setChalName(fx.default_challenger.name);
    setChalMd(fx.default_challenger.markdown);
  }, [fixtureOptions, fixtureId]);

  const valid = brief.trim() && baseMd.trim() && chalMd.trim();

  return (
    <Card className="p-4">
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <Field label="Task fixture" className="lg:col-span-2">
          <select
            className={inputClass}
            value={fixtureId}
            onChange={(e) => setFixtureId(e.target.value)}
            data-testid="fixture-select"
          >
            {fixtureOptions.map((f: FixtureInfo) => (
              <option key={f.id} value={f.id}>
                {f.label}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Task brief" className="lg:col-span-2">
          <textarea
            className={`${inputClass} h-20 font-mono text-xs`}
            value={brief}
            onChange={(e) => setBrief(e.target.value)}
          />
        </Field>

        <div>
          <Field label="Baseline skill name">
            <input className={inputClass} value={baseName} onChange={(e) => setBaseName(e.target.value)} />
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
            <input className={inputClass} value={chalName} onChange={(e) => setChalName(e.target.value)} />
          </Field>
          <Field label="Challenger SKILL.md" className="mt-2">
            <textarea
              className={`${inputClass} h-44 font-mono text-xs`}
              value={chalMd}
              onChange={(e) => setChalMd(e.target.value)}
            />
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-3 lg:col-span-2 lg:grid-cols-5">
          <Field label="max_turns">
            <input
              type="number"
              min={1}
              max={100}
              className={inputClass}
              value={maxTurns}
              onChange={(e) => setMaxTurns(Number(e.target.value))}
            />
          </Field>
          <Field label="Thinking budget (0 = off)">
            <input
              type="number"
              min={0}
              max={32000}
              step={512}
              className={inputClass}
              value={thinking}
              onChange={(e) => setThinking(Number(e.target.value))}
            />
          </Field>
          <Field label="Judge model">
            <select className={inputClass} value={judgeModel} onChange={(e) => setJudgeModel(e.target.value)}>
              <option value="claude-haiku-4-5">claude-haiku-4-5</option>
              <option value="claude-sonnet-4-6">claude-sonnet-4-6</option>
            </select>
          </Field>
          <Field label="Judges per criterion (k)">
            <input
              type="number"
              min={1}
              max={5}
              className={inputClass}
              value={judgesK}
              onChange={(e) => setJudgesK(Number(e.target.value))}
            />
          </Field>
          <label className="flex items-end gap-2 pb-2 text-sm font-semibold text-sketch-ink">
            <input
              type="checkbox"
              checked={realAgents}
              onChange={(e) => setRealAgents(e.target.checked)}
              data-testid="real-agents-toggle"
            />
            Real Haiku agents (~$0.40)
          </label>
        </div>
      </div>

      <div className="mt-4">
        {/* SCREEN 2 ends at this button in the demo sequence. Keep the setup
            controls above it and do not move downstream replay/results here. */}
        <Button
          disabled={!valid || running}
          data-testid="run-button"
          onClick={() =>
            onSubmit({
              fixture: fixtureId,
              task_brief: brief,
              baseline: { name: baseName, markdown: baseMd },
              challenger: { name: chalName, markdown: chalMd },
              max_turns: maxTurns,
              thinking_budget: thinking,
              judge_model: judgeModel,
              judges_per_criterion: judgesK,
              real_agents: realAgents,
            })
          }
        >
          {running ? "Running…" : "Run eval"}
        </Button>
      </div>
    </Card>
  );
}
