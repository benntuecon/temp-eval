"""Run one skill-eval against a testcases/<case> fixture.

Bridges the hackathon case format (plain before/ and after/ dirs acting as
fake commit hashes) onto the git-based harness: the case is materialised as
a real temp git repo with a before and an after commit, then fed to run_eval.

Usage (costs real API money):
    uv run python scripts/run_testcase_eval.py testcases/01-payment-api \
        [--model claude-haiku-4-5] [--max-turns 30] [--out runs/case01.json]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from skill_eval import git_ops
from skill_eval.contracts import RunConfig
from skill_eval.orchestrator import run_eval

BASELINE_SKILL = REPO_ROOT / "flagship" / "skills" / "logging-naive"
CHALLENGER_SKILL = REPO_ROOT / "flagship" / "skills" / "logging-best-practices"


def _copy_tree(src: Path, dest_root: Path) -> None:
    for f in sorted(src.rglob("*")):
        if f.is_file():
            dest = dest_root / f.relative_to(src)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)


def materialize_case_repo(case_dir: Path, work_dir: Path) -> tuple[str, str, str]:
    """Turn before/ and after/ dirs into two commits; return (brief, before, after)."""
    case = json.loads((case_dir / "case.json").read_text())

    git_ops.init(str(work_dir))
    git_ops.config(str(work_dir), "user.email", "eval@example.com")
    git_ops.config(str(work_dir), "user.name", "Eval Fixture")

    _copy_tree(REPO_ROOT / case["before"], work_dir)
    git_ops.add_all(str(work_dir))
    git_ops.commit(str(work_dir), f"before: {case_dir.name}")
    before = git_ops.rev_parse(str(work_dir))

    for f in work_dir.iterdir():
        if f.name == ".git":
            continue
        shutil.rmtree(f) if f.is_dir() else f.unlink()
    _copy_tree(REPO_ROOT / case["after"], work_dir)
    git_ops.add_all(str(work_dir))
    git_ops.commit(str(work_dir), f"after: {case_dir.name}")
    after = git_ops.rev_parse(str(work_dir))

    return case["description"], before, after


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("case_dir", type=Path)
    ap.add_argument("--model", default="claude-haiku-4-5")
    ap.add_argument("--max-turns", type=int, default=30)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    work_dir = Path(tempfile.mkdtemp(prefix=f"case_{args.case_dir.name}_"))
    brief, before, after = materialize_case_repo(args.case_dir, work_dir)

    cfg = RunConfig(
        before_hash=before,
        after_hash=after,
        repo_path=str(work_dir),
        task_brief=brief,
        baseline_skill_path=str(BASELINE_SKILL),
        challenger_skill_path=str(CHALLENGER_SKILL),
        models=(args.model,),
        max_turns=args.max_turns,
        thinking_budget=2048,
    )

    def on_event(ev: dict) -> None:
        stage = ev.get("stage", "?")
        arm = ev.get("arm", "")
        msg = ev.get("msg", "")
        print(f"[{stage}]{f' ({arm})' if arm else ''} {msg}", flush=True)

    report = run_eval(cfg, on_event=on_event)

    print("\n" + "=" * 72)
    print(f"case: {args.case_dir.name}   verdict: {report.pairwise_verdict}")
    for ar in report.arms:
        crit = ", ".join(f"{s.criterion.value}={s.score}" for s in ar.scores)
        print(
            f"  {ar.arm.value:<10} total={ar.total_score:>3}  "
            f"tokens={ar.metrics.total_tokens}  turns={ar.metrics.num_turns}  "
            f"questions={ar.metrics.num_questions}  stop={ar.stop_reason}"
        )
        print(f"             {crit}")

    out = args.out or Path("runs") / f"testcase-{args.case_dir.name}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.model_dump_json(indent=2))
    print(f"\nreport saved to {out}")


if __name__ == "__main__":
    main()
