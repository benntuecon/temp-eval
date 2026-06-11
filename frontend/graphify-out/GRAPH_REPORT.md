# Graph Report - frontend  (2026-06-11)

## Corpus Check
- 18 files · ~7,339 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 124 nodes · 196 edges · 10 communities
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ac25e15f`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]

## God Nodes (most connected - your core abstractions)
1. `compilerOptions` - 13 edges
2. `cn()` - 11 edges
3. `ResultsFunnel()` - 7 edges
4. `scripts` - 6 edges
5. `Card()` - 6 edges
6. `api` - 5 edges
7. `gapRows()` - 5 edges
8. `Badge()` - 5 edges
9. `ComparisonReport` - 4 edges
10. `Field()` - 4 edges

## Surprising Connections (you probably didn't know these)
- `PipelineNode()` --calls--> `cn()`  [EXTRACTED]
  src/components/PipelineGraph.tsx → src/components/ui.tsx
- `MetricCard()` --calls--> `cn()`  [EXTRACTED]
  src/components/ResultsFunnel.tsx → src/components/ui.tsx
- `DeltaTable()` --calls--> `gapRows()`  [EXTRACTED]
  src/pages/HistoryPage.tsx → src/components/charts.ts
- `ResultsFunnel()` --calls--> `dumbbellSpec()`  [EXTRACTED]
  src/components/ResultsFunnel.tsx → src/components/charts.ts
- `ResultsFunnel()` --calls--> `gapRows()`  [EXTRACTED]
  src/components/ResultsFunnel.tsx → src/components/charts.ts

## Import Cycles
- None detected.

## Communities (10 total, 0 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.11
Nodes (17): RunEvent, nodeTypes, PipelineGraph(), PipelineNode(), PipelineNodeData, STATUS_BG, X, append() (+9 more)

### Community 1 - "Community 1"
Cohesion: 0.16
Nodes (13): api, ArmReport, CreateRunRequest, FixtureInfo, JudgeScore, RunDetail, RunSummary, SkillInput (+5 more)

### Community 2 - "Community 2"
Cohesion: 0.24
Nodes (16): ComparisonReport, ARM_COLORS, armScale, dumbbellSpec(), GapRow, gapRows(), qualityCostSpec(), byArm() (+8 more)

### Community 3 - "Community 3"
Cohesion: 0.11
Nodes (18): dependencies, react, react-dom, react-vega, @tanstack/react-query, vega, vega-lite, @xyflow/react (+10 more)

### Community 4 - "Community 4"
Cohesion: 0.13
Nodes (14): compilerOptions, isolatedModules, jsx, lib, module, moduleResolution, noEmit, noUnusedLocals (+6 more)

### Community 5 - "Community 5"
Cohesion: 0.15
Nodes (13): devDependencies, jsdom, openapi-typescript, tailwindcss, @tailwindcss/vite, @testing-library/jest-dom, @testing-library/react, @types/react (+5 more)

### Community 6 - "Community 6"
Cohesion: 0.33
Nodes (5): components, $defs, operations, paths, webhooks

### Community 7 - "Community 7"
Cohesion: 0.40
Nodes (5): describe(), KIND_TONE, NODE_DESCRIPTION, NodePanel(), RunLiveState

## Knowledge Gaps
- **63 isolated node(s):** `name`, `private`, `version`, `type`, `dev` (+58 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `devDependencies` connect `Community 5` to `Community 3`?**
  _High betweenness centrality (0.039) - this node is a cross-community bridge._
- **Why does `cn()` connect `Community 2` to `Community 0`, `Community 1`?**
  _High betweenness centrality (0.020) - this node is a cross-community bridge._
- **What connects `name`, `private`, `version` to the rest of the system?**
  _63 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 0` be split into smaller, more focused modules?**
  _Cohesion score 0.11462450592885376 - nodes in this community are weakly interconnected._
- **Should `Community 3` be split into smaller, more focused modules?**
  _Cohesion score 0.10526315789473684 - nodes in this community are weakly interconnected._
- **Should `Community 4` be split into smaller, more focused modules?**
  _Cohesion score 0.13333333333333333 - nodes in this community are weakly interconnected._