"""Testcase fixtures: expose testcases/<id>/ as selectable eval fixtures.

Each testcases/<id>/ holds case.json (description doubling as task brief and
vector-DB embedding text) plus plain repo/before and repo/after trees.
``build_testcase`` materialises those trees as a real two-commit git repo
under *base_dir* so the sandbox can cut worktrees from genuine hashes.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from skill_eval import git_ops
from skill_eval.contracts import RunConfig

_REPO_ROOT = Path(__file__).resolve().parents[1]
TESTCASES_DIR = _REPO_ROOT / "testcases"
BASELINE_SKILL = _REPO_ROOT / "flagship" / "skills" / "logging-naive"
CHALLENGER_SKILL = _REPO_ROOT / "flagship" / "skills" / "logging-best-practices"


def list_testcase_ids() -> list[str]:
    if not TESTCASES_DIR.is_dir():
        return []
    return sorted(d.name for d in TESTCASES_DIR.iterdir() if (d / "case.json").is_file())


def load_case(case_id: str) -> dict:
    return json.loads((TESTCASES_DIR / case_id / "case.json").read_text())


def _copy_tree(src: Path, dest_root: Path) -> None:
    for f in sorted(src.rglob("*")):
        if f.is_file():
            dest = dest_root / f.relative_to(src)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)


def build_testcase(case_id: str, base_dir: str) -> RunConfig:
    """Materialise testcases/<case_id> into *base_dir*; return its RunConfig."""
    meta = load_case(case_id)
    work = Path(base_dir) / "case_repo"
    work.mkdir(parents=True, exist_ok=True)

    git_ops.init(str(work))
    git_ops.config(str(work), "user.email", "eval@example.com")
    git_ops.config(str(work), "user.name", "Eval Fixture")

    _copy_tree(_REPO_ROOT / meta["before"], work)
    git_ops.add_all(str(work))
    git_ops.commit(str(work), f"before: {case_id}")
    before = git_ops.rev_parse(str(work))

    for f in work.iterdir():
        if f.name == ".git":
            continue
        shutil.rmtree(f) if f.is_dir() else f.unlink()
    _copy_tree(_REPO_ROOT / meta["after"], work)
    git_ops.add_all(str(work))
    git_ops.commit(str(work), f"after: {case_id}")
    after = git_ops.rev_parse(str(work))

    return RunConfig(
        before_hash=before,
        after_hash=after,
        repo_path=str(work),
        task_brief=meta["description"],
        baseline_skill_path=str(BASELINE_SKILL),
        challenger_skill_path=str(CHALLENGER_SKILL),
        models=("claude-haiku-4-5",),
        max_turns=16,
        thinking_budget=2048,
    )
