import { useState } from "react";
import { cn } from "./components/ui";
import { HistoryPage } from "./pages/HistoryPage";
import { RunPage } from "./pages/RunPage";

function SkillPruneAnimation() {
  return (
    <div className="skill-prune-stage" aria-label="Animated skill comparison">
      <div className="diagram-label font-hand">observe / compare / prune</div>
      <div className="skill-prune-frame">
        <div className="skill-pile" aria-hidden="true">
          {Array.from({ length: 10 }, (_, index) => (
            <span key={index} className={`pile-block pile-block-${index + 1}`} />
          ))}
        </div>
        <div className="skill-card-demo skill-card-one">
          <span className="font-hand text-xs font-bold">skill 1</span>
          <strong className="font-hand text-lg">fast guesser</strong>
          <small>assumes policy</small>
        </div>
        <div className="skill-card-demo skill-card-two">
          <span className="font-hand text-xs font-bold">skill 2</span>
          <strong className="font-hand text-lg">asks first</strong>
          <small>unlocks hidden rules</small>
          <div className="winner-badge font-hand text-xs font-bold">kept</div>
        </div>
      </div>
      <div className="compare-box">
        <span className="font-hand text-xs font-bold">
          <i>select</i>
          <i>compare</i>
          <i>prune</i>
          <i>keep</i>
        </span>
        <div className="compare-meter">
          <i />
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState<"run" | "history">("run");

  return (
    <div className="min-h-screen bg-sketch-paper text-sketch-ink">
      <div className="mx-auto max-w-[1600px] px-4 py-6">
        {/* SCREEN 1: Demo opening hero. Keep this exact story beat together:
            ForgeSkill positioning on the left + 1:1 sketchboard animation on the right. */}
        <header className="sketch-card mb-6 min-h-[calc(100vh-3rem)] overflow-hidden bg-sketch-paper">
          <div className="sketch-hero-grid">
            <div className="flex flex-col justify-center p-6 md:p-10 lg:p-14">
              <div className="font-hand sticky-note mb-4 inline-block rotate-[-1deg] bg-sketch-yellow px-3 py-1 text-sm font-bold">
                Evidence-based skill decisions
              </div>
              <h1 className="font-hand max-w-5xl text-4xl font-bold leading-[0.95] tracking-normal md:text-7xl xl:text-8xl">
                ForgeSkill
                <span className="mt-3 block text-2xl leading-tight text-sketch-muted md:text-4xl xl:text-5xl">
                  Evidence-Based Agent Skill Observatory
                </span>
              </h1>
              <p className="mt-6 max-w-3xl text-base font-semibold leading-7 md:text-lg">
                Your team keeps adding skills, rules, and workflows. This lab tests which
                instructions actually change agent behavior, which ones create risk, and
                which ones deserve to stay.
              </p>
              <p className="font-hand mt-5 text-base font-bold text-sketch-muted md:text-lg">
                Controlled evals · live behavior replay · evidence-backed decisions
              </p>
            </div>
            <div className="relative min-h-[430px] border-t-2 border-dashed border-sketch-ink p-5 md:min-h-0 md:border-l-2 md:border-t-0">
              <SkillPruneAnimation />
            </div>
          </div>
        </header>

        {/* SCREEN 2 begins here with the demo tabs, then continues in RunPage
            through the eval setup form and Run eval button. Do not move this
            nav below the setup form; the demo sequence depends on it. */}
        <nav className="mb-4 flex gap-2 border-b-2 border-dashed border-sketch-ink">
          {(
            [
              ["run", "Eval Lab"],
              ["history", "Run History"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              data-testid={`tab-${id}`}
              className={cn(
                "font-hand rounded-t-[15px] border-2 border-b-0 border-sketch-ink px-4 py-2 text-sm font-bold shadow-[3px_0_0_rgba(48,42,37,0.12)] transition-transform hover:-rotate-1",
                tab === id
                  ? "bg-sketch-yellow text-sketch-ink"
                  : "bg-sketch-paper text-sketch-ink hover:bg-sketch-blue",
              )}
            >
              {label}
            </button>
          ))}
        </nav>

        {tab === "run" ? <RunPage /> : <HistoryPage />}
      </div>
    </div>
  );
}
