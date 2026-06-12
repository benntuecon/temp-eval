import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "./api/client";
import { cn } from "./components/ui";
import { BatchPage } from "./pages/BatchPage";
import { HistoryPage } from "./pages/HistoryPage";
import { RunPage } from "./pages/RunPage";

export default function App() {
  const [tab, setTab] = useState<"run" | "batch" | "history">("run");
  useQuery({ queryKey: ["health"], queryFn: api.health });

  return (
    <div className="min-h-screen bg-slate-50">
      <div className="mx-auto max-w-7xl px-4 py-6">
        <header className="mb-4">
          <h1 className="text-2xl font-bold text-slate-900">⚖️ Skill Eval</h1>
          <p className="mt-1 text-sm text-slate-500">
            Race two Claude Code skills on the same task and let a judge panel decide.
          </p>
        </header>

        <nav className="mb-4 flex gap-1 border-b border-slate-200">
          {(
            [
              ["run", "▶ Run eval"],
              ["batch", "⚡ Batch eval"],
              ["history", "📜 History"],
            ] as const
          ).map(([id, label]) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              data-testid={`tab-${id}`}
              className={cn(
                "rounded-t-md px-4 py-2 text-sm font-medium",
                tab === id
                  ? "border border-b-0 border-slate-200 bg-white text-slate-900"
                  : "text-slate-500 hover:text-slate-800",
              )}
            >
              {label}
            </button>
          ))}
        </nav>

        {/* BatchPage stays mounted so a running batch keeps polling (and its
            state survives) while the user looks at other tabs. */}
        <div className={tab === "batch" ? "" : "hidden"}>
          <BatchPage />
        </div>
        {tab === "run" ? <RunPage /> : tab === "history" ? <HistoryPage /> : null}
      </div>
    </div>
  );
}
