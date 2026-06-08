# Decision: Shell isolation + worktree concurrency

- **Date:** 2026-06-08
- **Status:** Accepted
- **Context:** Hackathon — captured from a design discussion.

## Problem

1. **Scattered inline shell.** Git is shelled out with duplicated `_git` helpers in `sandbox.py`, `sample_repo.py`, `taker.py`, and `simulated.py` — messy and hard to harden in one place.
2. **Concurrency hazard at scale.** Running N test cases concurrently means many `git worktree add`/`remove` against the same repo. For 6 test cases that's **18 worktrees** (each case = 2 taker worktrees @`before` + 1 gold worktree @`after`, *not* 12). Concurrent `git worktree add`/`remove` race on git's `index.lock` / `.git/worktrees` bookkeeping; the current code has **no lock, no retry, no prune**, so concurrent runs intermittently fail and leak stale worktrees.

## Decisions

### 1. Two shell categories → two tools
- **Dev/ops commands** (test, lint, fmt, run app, phoenix, graphify, eval) → a **`justfile`**. This is the human/CLI surface.
- **Runtime git** called by Python → a single module **`skill_eval/git_ops.py`**. This is the ONLY place git is shelled out.
- **Not** routed through `just`: `python → just → git` adds a process hop + hard `just` runtime dependency, and these calls consume git stdout (diff string, SHA) and need real exit-code handling. A typed Python module is cleaner and is where the concurrency lock must live.

### 2. Worktree concurrency hardening (in `git_ops.py`)
- A **process-wide lock** serializing only the brief `worktree add`/`remove` bookkeeping; the agents' actual *work* in their worktrees stays fully parallel.
- **Retry-with-backoff** on `index.lock` / "unable to create" / "cannot lock" errors (also covers cross-process contention).
- **`git worktree prune`** during cleanup to clear stale `.git/worktrees` registrations.

### 3. Worktrunk — not in the runtime path
[Worktrunk](https://github.com/max-sixty/worktrunk) is a human-facing, **branch-centric** CLI for parallel-agent worktrees. Our runtime is **programmatic, detached-commit, ephemeral (no merge)** — so shelling out to it reintroduces the indirection/dependency without solving our needs. Keep runtime on direct `git worktree` via `git_ops.py`. Worktrunk stays an **optional developer companion** for inspecting kept worktrees, and design inspiration (its per-worktree hooks).

## Deferred / future
- **Share one gold worktree per `(repo, after_hash)`** → cuts 18 → 12 worktrees (needs a small refcount registry).
- **Relocate worktrees out of `cfg.repo_path`.** Today `.worktrees/` is written *inside the repo under test*; a dedicated temp/scratch root is cleaner for real target repos. (`git worktree add` accepts any path.)
- **File-lock** (e.g. `flock`) if evals are ever run as separate processes rather than threads.

## Implementation
- `skill_eval/git_ops.py` — `init`, `config`, `add_all`, `commit`, `rev_parse`, `diff`, `diff_cached`, `worktree_add` (lock+retry), `worktree_remove` (lock+retry, best-effort), `worktree_prune`.
- Refactor `sandbox.py` / `sample_repo.py` / `taker.py` / `simulated.py` to use it; delete the duplicated `_git` helpers.
- `justfile` with dev/ops recipes.
- Tests: a functional round-trip for `git_ops`, plus a **concurrent `worktree_add` stress test** (N threads, all succeed) proving the lock/retry.
