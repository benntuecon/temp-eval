// Run configuration: two skills in, everything else sensible defaults.
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, type CreateRunRequest, type FixtureInfo } from "../api/client";
import { DEMO_FIXTURES } from "../mockRun";
import { Button, Field, inputClass } from "./ui";

type ExtraSkillCard = {
  id: number;
  name: string;
  markdown: string;
};

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
  const [maxTurns, setMaxTurns] = useState(5);
  const [thinking, setThinking] = useState(2048);
  const [judgeModel, setJudgeModel] = useState("gpt-4.1-mini");
  const [realAgents, setRealAgents] = useState(false);
  const [extraSkills, setExtraSkills] = useState<ExtraSkillCard[]>([]);
  const fixtureOptions = fixtures.data?.length ? fixtures.data : DEMO_FIXTURES;
  const judgeCostWeight: Record<string, number> = {
    "gpt-4.1-nano": 0.65,
    "gpt-4.1-mini": 1,
    "gpt-4.1": 1.8,
    "gpt-4o-mini": 0.9,
  };
  const thinkingCostWeight = thinking <= 0 ? 0.85 : 1 + (thinking - 2048) / 20480;
  const mockCost = Math.max(
    1,
    3 * (maxTurns / 5) * (judgeCostWeight[judgeModel] ?? 1) * thinkingCostWeight,
  );

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
  const addSkillCard = () => {
    setExtraSkills((cards) => [
      ...cards,
      { id: Date.now(), name: "", markdown: "" },
    ]);
  };

  const updateExtraSkill = (id: number, patch: Partial<ExtraSkillCard>) => {
    setExtraSkills((cards) =>
      cards.map((card) => (card.id === id ? { ...card, ...patch } : card)),
    );
  };

  const removeExtraSkill = (id: number) => {
    setExtraSkills((cards) => cards.filter((card) => card.id !== id));
  };

  return (
    <div className="space-y-3">
      <div className="sketch-card bg-sketch-paper p-4">
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
        </div>
      </div>

      <div className="skill-card-strip" data-scroll-free>
        <div className="skill-input-card bg-sketch-pink">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="font-hand text-lg font-bold text-sketch-ink">Baseline skill</h3>
            <span className="font-hand rounded-[12px_9px_13px_8px] border-2 border-sketch-ink bg-sketch-paper px-2 py-0.5 text-xs font-bold">
              skill 1
            </span>
          </div>
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

        <div className="skill-input-card bg-sketch-blue">
          <div className="mb-3 flex items-center justify-between gap-2">
            <h3 className="font-hand text-lg font-bold text-sketch-ink">Challenger skill</h3>
            <span className="font-hand rounded-[12px_9px_13px_8px] border-2 border-sketch-ink bg-sketch-paper px-2 py-0.5 text-xs font-bold">
              skill 2
            </span>
          </div>
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

        {extraSkills.map((skill, index) => (
          <div key={skill.id} className="skill-input-card bg-sketch-green">
            <div className="mb-3 flex items-center justify-between gap-2">
              <h3 className="font-hand text-lg font-bold text-sketch-ink">Skill card</h3>
              <div className="flex items-center gap-2">
                <span className="font-hand rounded-[12px_9px_13px_8px] border-2 border-sketch-ink bg-sketch-paper px-2 py-0.5 text-xs font-bold">
                  skill {index + 3}
                </span>
                <button
                  type="button"
                  className="remove-skill-button"
                  onClick={() => removeExtraSkill(skill.id)}
                  aria-label={`Remove skill ${index + 3}`}
                  title={`Remove skill ${index + 3}`}
                >
                  ×
                </button>
              </div>
            </div>
            <Field label={`Skill ${index + 3} name`}>
              <input
                className={inputClass}
                value={skill.name}
                onChange={(e) => updateExtraSkill(skill.id, { name: e.target.value })}
              />
            </Field>
            <Field label={`Skill ${index + 3} SKILL.md`} className="mt-2">
              <textarea
                className={`${inputClass} h-44 font-mono text-xs`}
                value={skill.markdown}
                onChange={(e) => updateExtraSkill(skill.id, { markdown: e.target.value })}
              />
            </Field>
          </div>
        ))}

        <button
          type="button"
          className="add-skill-button"
          onClick={addSkillCard}
          aria-label="Add skill card"
          title="Add skill card"
        >
          +
        </button>
      </div>

      <div className="sketch-card bg-sketch-paper p-4">
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
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
          <select
            className={inputClass}
            value={judgeModel}
            onChange={(e) => setJudgeModel(e.target.value)}
          >
            <option value="gpt-4.1-mini">gpt-4.1-mini</option>
            <option value="gpt-4.1">gpt-4.1</option>
            <option value="gpt-4.1-nano">gpt-4.1-nano</option>
            <option value="gpt-4o-mini">gpt-4o-mini</option>
          </select>
        </Field>
          <div className="sketch-card bg-sketch-blue/35 px-3 py-2">
            <div className="font-hand text-xs font-bold text-sketch-muted">Mock cost estimate</div>
            <div className="mt-1 font-hand text-3xl font-bold text-sketch-ink">
              {mockCost.toLocaleString(undefined, { currency: "USD", style: "currency" })}
            </div>
            <div className="mt-1 text-[11px] font-semibold leading-4 text-sketch-muted">
              Demo only; updates with turns, model, and thinking budget.
            </div>
          </div>
          <label className="flex items-end gap-2 pb-2 text-sm font-semibold text-sketch-ink">
            <input
              type="checkbox"
              checked={realAgents}
              onChange={(e) => setRealAgents(e.target.checked)}
              data-testid="real-agents-toggle"
            />
            Run real agents
          </label>
        </div>
      </div>

      <div className="mt-6 flex justify-center">
        {/* SCREEN 2 ends at this button in the demo sequence. Keep the setup
            controls above it and do not move downstream replay/results here. */}
        <Button
          disabled={!valid || running}
          data-testid="run-button"
          className="run-eval-button min-w-[280px] rounded-[10px] px-10 py-4 text-xl"
          onClick={() =>
            onSubmit({
              fixture: fixtureId,
              task_brief: brief,
              baseline: { name: baseName, markdown: baseMd },
              challenger: { name: chalName, markdown: chalMd },
              max_turns: maxTurns,
              thinking_budget: thinking,
              judge_model: judgeModel,
              judges_per_criterion: 1,
              real_agents: realAgents,
            })
          }
        >
          {running ? "Running…" : "Run eval"}
        </Button>
      </div>
    </div>
  );
}
