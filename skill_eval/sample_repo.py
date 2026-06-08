from pathlib import Path

from skill_eval import git_ops
from skill_eval.contracts import RunConfig

TASK_BRIEF = (
    "The `add(a, b)` function in calculator.py returns the wrong result "
    "(it subtracts). Fix it so it returns the sum, and make the tests pass."
)


def build_sample_repo(path: str) -> RunConfig:
    repo = Path(path)
    repo.mkdir(parents=True, exist_ok=True)
    git_ops.init(path)
    git_ops.config(path, "user.email", "eval@example.com")
    git_ops.config(path, "user.name", "Eval Fixture")
    # placeholder skills so skill_path is a real dir (real loading is Phase B)
    for arm in ("baseline", "challenger"):
        sk = repo / ".claude/skills" / arm
        sk.mkdir(parents=True, exist_ok=True)
        (sk / "SKILL.md").write_text(
            f"---\nname: {arm}\ndescription: {arm} coding skill (placeholder)\n---\n"
        )
    (repo / "calculator.py").write_text("def add(a, b):\n    return a - b  # BUG\n")
    (repo / "test_calculator.py").write_text(
        "from calculator import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"
    )
    git_ops.add_all(path)
    git_ops.commit(path, "before: calculator with add bug")
    before = git_ops.rev_parse(path)
    (repo / "calculator.py").write_text("def add(a, b):\n    return a + b\n")
    git_ops.add_all(path)
    git_ops.commit(path, "after: fix add")
    after = git_ops.rev_parse(path)
    return RunConfig(
        before_hash=before,
        after_hash=after,
        repo_path=path,
        task_brief=TASK_BRIEF,
        baseline_skill_path=str(repo / ".claude/skills/baseline"),
        challenger_skill_path=str(repo / ".claude/skills/challenger"),
        models=("claude-haiku-4-5",),
    )
