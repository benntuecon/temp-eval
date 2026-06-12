import { useEffect, useState } from "react";
import { cn } from "./components/ui";
import { HistoryPage } from "./pages/HistoryPage";
import { RunPage } from "./pages/RunPage";

const TEAM_MEMBERS = [
  {
    name: "Kuanpin Chen",
    role: "Software Engineer",
    contribution: "Built the AI backend prototype and database foundation for SkillForge.",
  },
  {
    name: "Chin-Lun Fu",
    role: "ML Scientist",
    contribution: "Built the evaluation framework, especially the Agentic AI methodology behind the system.",
  },
  {
    name: "Prajwal Manjunath",
    role: "Software Engineer",
    contribution: "Provided key technical support and system integration across the prototype.",
  },
  {
    name: "Luciana Ma",
    role: "Product Manager",
    contribution: "Built the frontend, refined the problem framing, and created the demo material.",
  },
];

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
  const [heroTab, setHeroTab] = useState<"problem" | "team" | "product">("problem");

  useEffect(() => {
    let locked = false;

    // Demo scroll controller: each screen is a presentation beat. A wheel or
    // trackpad gesture snaps to the next/previous `.demo-screen`, while form
    // fields keep normal editing behavior.
    const onWheel = (event: WheelEvent) => {
      const target = event.target as HTMLElement | null;
      if (
        locked ||
        Math.abs(event.deltaY) < 35 ||
        event.metaKey ||
        event.ctrlKey ||
        target?.closest("input, textarea, select, [data-scroll-free]")
      ) {
        return;
      }

      const screens = Array.from(document.querySelectorAll<HTMLElement>(".demo-screen"));
      if (screens.length < 2) return;

      const currentY = window.scrollY;
      const currentIndex = screens.reduce((bestIndex, screen, index) => {
        const bestDistance = Math.abs(screens[bestIndex].offsetTop - currentY);
        const distance = Math.abs(screen.offsetTop - currentY);
        return distance < bestDistance ? index : bestIndex;
      }, 0);
      const nextIndex =
        event.deltaY > 0
          ? Math.min(currentIndex + 1, screens.length - 1)
          : Math.max(currentIndex - 1, 0);

      if (nextIndex === currentIndex) return;
      event.preventDefault();
      locked = true;
      screens[nextIndex].scrollIntoView({ behavior: "smooth", block: "start" });
      window.setTimeout(() => {
        locked = false;
      }, 720);
    };

    window.addEventListener("wheel", onWheel, { passive: false });
    return () => window.removeEventListener("wheel", onWheel);
  }, []);

  const demoNav = (
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
  );

  return (
    <div className="min-h-screen bg-sketch-paper text-sketch-ink">
      <div className="mx-auto max-w-[1600px] px-4 py-6">
        {/* SCREEN 1: Demo opening hero. Keep this exact story beat together:
            its local tabs only affect Screen 1 and never change downstream screens. */}
        <header className="demo-screen sketch-card mb-6 min-h-[calc(100vh-3rem)] overflow-hidden bg-sketch-paper">
          <nav className="screen-one-tabs">
            {(
              [
                ["problem", "The Problem"],
                ["team", "Our Team"],
                ["product", "Our Product"],
              ] as const
            ).map(([id, label]) => (
              <button
                key={id}
                type="button"
                className={cn(
                  "font-hand rounded-t-[15px] border-2 border-b-0 border-sketch-ink px-4 py-2 text-sm font-bold shadow-[3px_0_0_rgba(48,42,37,0.12)] transition-transform hover:-rotate-1",
                  heroTab === id
                    ? "bg-sketch-yellow text-sketch-ink"
                    : "bg-sketch-paper text-sketch-ink hover:bg-sketch-blue",
                )}
                onClick={() => setHeroTab(id)}
              >
                {label}
              </button>
            ))}
          </nav>

          {heroTab === "product" ? (
            <div className="sketch-hero-grid">
              <div className="flex flex-col justify-center p-6 md:p-10 lg:p-14">
                <div className="font-hand sticky-note mb-4 inline-block rotate-[-1deg] bg-sketch-yellow px-3 py-1 text-sm font-bold">
                  Evidence-based skill decisions
                </div>
                <h1 className="font-hand max-w-5xl text-4xl font-bold leading-[0.95] tracking-normal md:text-7xl xl:text-8xl">
                  SkillForge
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
          ) : null}

          {heroTab === "problem" ? (
            <div className="screen-one-panel problem-slide">
              <h2 className="problem-title font-hand">
                More skills make agents dumber — and we only ever add more
              </h2>

              <div className="problem-grid mt-6">
                <section className="problem-block">
                  <div>
                    <h3 className="font-hand text-xl font-bold">What the research proves — the mechanism</h3>
                    <ul className="mt-3 space-y-2 text-sm font-semibold leading-6">
                      <li>
                        Big skill pile → agents pick the right skill just <strong>13%</strong> of the time;
                        filtering lifts it to <strong>43%</strong> <span className="text-sketch-muted">(RAG-MCP, 2025)</span>.
                      </li>
                      <li>
                        Every added skill drags accuracy down — losses up to <strong>85%</strong> as catalogues grow
                        <span className="text-sketch-muted"> (Kate et al., LongFuncEval)</span>.
                      </li>
                      <li>
                        Prompt & skill config is the <strong>#1 source</strong> of LLM technical debt
                        <span className="text-sketch-muted"> (PromptDebt, EASE 2025 — 93K files)</span>.
                      </li>
                    </ul>
                  </div>
                </section>

                <div className="problem-reasoning-arrow font-hand" aria-hidden="true">
                  →
                </div>

                <section className="problem-block">
                  <div>
                    <h3 className="font-hand text-xl font-bold">What that means in production — every mis-selection becomes a bill</h3>
                    <ul className="mt-3 space-y-2 text-sm font-semibold leading-6">
                      <li>Every skill rides in context on every call → token carrying cost. <span className="problem-cost-pill">tokens ~$7K</span></li>
                      <li>Wrong skill picked → engineers dig through transcripts to find which rule misfired → debugging hours. <span className="problem-cost-pill">debugging ~$22K</span></li>
                      <li>Wrong skill ships → rework & incidents. <span className="problem-cost-pill">incidents ~$12K</span></li>
                    </ul>
                  </div>
                </section>
              </div>

              <div className="problem-conclusion font-hand mt-5">
                <span className="problem-conclusion-text">
                  300,000 developers · ~500 teams having AI agents today → <span className="problem-money-box">~$20M/year</span>
                </span>
              </div>
            </div>
          ) : null}

          {heroTab === "team" ? (
            <div className="screen-one-panel">
              <div className="team-member-grid">
                {TEAM_MEMBERS.map((member) => (
                  <div key={member.name} className="team-member-card sticky-note bg-sketch-paper p-5">
                    <div className="flex items-start gap-4">
                      <div className="team-avatar font-hand">{member.name.split(" ").map((part) => part[0]).join("")}</div>
                      <div>
                        <h3 className="font-hand text-xl font-bold">{member.name}</h3>
                        <p className="mt-1 text-sm font-bold text-sketch-muted">{member.role}</p>
                      </div>
                    </div>
                    <p className="mt-5 text-base font-semibold leading-7">{member.contribution}</p>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </header>

        {/* SCREEN 2 begins here with the demo tabs, then continues in RunPage
            through the eval setup form and Run eval button. Do not move this
            nav below the setup form; the demo sequence depends on it. */}
        {tab === "run" ? (
          <RunPage navSlot={demoNav} />
        ) : (
          <section className="demo-screen demo-screen-panel">
            {demoNav}
            <HistoryPage />
          </section>
        )}
      </div>
    </div>
  );
}
