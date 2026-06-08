import subprocess
from pathlib import Path

from skill_eval.contracts import RunConfig

TASK_BRIEF = (
    "The `add(a, b)` function in calculator.py returns the wrong result "
    "(it subtracts). Fix it so it returns the sum, and make the tests pass."
)


def _git(repo: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", repo, *args], check=True, capture_output=True, text=True
    ).stdout.strip()


def build_sample_repo(path: str) -> RunConfig:
    repo = Path(path)
    repo.mkdir(parents=True, exist_ok=True)
    _git(path, "init", "-q")
    _git(path, "config", "user.email", "eval@example.com")
    _git(path, "config", "user.name", "Eval Fixture")
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
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "before: calculator with add bug")
    before = _git(path, "rev-parse", "HEAD")
    (repo / "calculator.py").write_text("def add(a, b):\n    return a + b\n")
    _git(path, "add", "-A")
    _git(path, "commit", "-q", "-m", "after: fix add")
    after = _git(path, "rev-parse", "HEAD")
    return RunConfig(
        before_hash=before,
        after_hash=after,
        repo_path=path,
        task_brief=TASK_BRIEF,
        baseline_skill_path=str(repo / ".claude/skills/baseline"),
        challenger_skill_path=str(repo / ".claude/skills/challenger"),
        models=("claude-haiku-4-5",),
    )
