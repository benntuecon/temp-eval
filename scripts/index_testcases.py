"""Index testcases/ into the skill-eval vector DB.

Bridges the hackathon case format (testcases/<id>/case.json with plain
before/ and after/ dirs) onto eval_vector_db's EvalCase records: each case
is materialised as a stable git repo with two commits under
.skill-eval-cases/testcases/<id>/, then indexed into Chroma with the
description as the embedded document.

Usage:
    uv run python scripts/index_testcases.py --reset
    uv run python -m skill_eval.eval_vector_db query "payment api logging" --top-k 3
    uv run python -m skill_eval.eval_vector_db run-query "payment api logging" --top-k 1
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from skill_eval import git_ops
from skill_eval.eval_vector_db import DEFAULT_DB_DIR, EvalCase, index_cases

BASELINE_SKILL = REPO_ROOT / "flagship" / "skills" / "logging-naive"
CHALLENGER_SKILL = REPO_ROOT / "flagship" / "skills" / "logging-best-practices"
CASES_ROOT = REPO_ROOT / ".skill-eval-cases" / "testcases"


def _copy_tree(src: Path, dest_root: Path) -> None:
    for f in sorted(src.rglob("*")):
        if f.is_file():
            dest = dest_root / f.relative_to(src)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)


def materialize(case_dir: Path) -> EvalCase:
    """Build a persistent two-commit git repo for one case; return its EvalCase."""
    meta = json.loads((case_dir / "case.json").read_text())
    work = CASES_ROOT / case_dir.name
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)

    git_ops.init(str(work))
    git_ops.config(str(work), "user.email", "eval@example.com")
    git_ops.config(str(work), "user.name", "Eval Fixture")

    _copy_tree(REPO_ROOT / meta["before"], work)
    git_ops.add_all(str(work))
    git_ops.commit(str(work), f"before: {case_dir.name}")
    before = git_ops.rev_parse(str(work))

    for f in work.iterdir():
        if f.name == ".git":
            continue
        shutil.rmtree(f) if f.is_dir() else f.unlink()
    _copy_tree(REPO_ROOT / meta["after"], work)
    git_ops.add_all(str(work))
    git_ops.commit(str(work), f"after: {case_dir.name}")
    after = git_ops.rev_parse(str(work))

    return EvalCase(
        case_id=case_dir.name,
        description=meta["description"],
        repo_path=str(work),
        before_hash=before,
        after_hash=after,
        baseline_skill_path=str(BASELINE_SKILL),
        challenger_skill_path=str(CHALLENGER_SKILL),
        max_turns=16,
        thinking_budget=2048,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db-dir", default=DEFAULT_DB_DIR)
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    case_dirs = sorted(d for d in (REPO_ROOT / "testcases").iterdir() if d.is_dir())
    cases = []
    for d in case_dirs:
        case = materialize(d)
        cases.append(case)
        print(f"{case.case_id}: before={case.before_hash[:8]} after={case.after_hash[:8]}")

    index_cases(cases, db_dir=args.db_dir, reset=args.reset)


if __name__ == "__main__":
    main()
