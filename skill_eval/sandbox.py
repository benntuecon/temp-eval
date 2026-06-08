import subprocess
import tempfile
from pathlib import Path

from skill_eval.contracts import Arm, RunConfig, Workspace


def _git(repo: str, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", repo, *args], check=True, capture_output=True, text=True
    ).stdout


def prepare_workspaces(cfg: RunConfig) -> dict[Arm, Workspace]:
    base = Path(cfg.repo_path) / ".worktrees"
    base.mkdir(exist_ok=True)
    after_dir = tempfile.mkdtemp(prefix="after_", dir=base)
    _git(cfg.repo_path, "worktree", "add", "--detach", "-f", after_dir, cfg.after_hash)
    gold_diff = _git(cfg.repo_path, "diff", f"{cfg.before_hash}..{cfg.after_hash}")
    spaces: dict[Arm, Workspace] = {}
    for arm in (Arm.BASELINE, Arm.CHALLENGER):
        taker_dir = tempfile.mkdtemp(prefix=f"{arm.value}_", dir=base)
        _git(cfg.repo_path, "worktree", "add", "--detach", "-f", taker_dir, cfg.before_hash)
        spaces[arm] = Workspace(
            arm=arm, taker_dir=taker_dir, after_dir=after_dir, gold_diff=gold_diff
        )
    return spaces


def cleanup_workspaces(spaces: dict[Arm, Workspace]) -> None:
    if not spaces:
        return
    repo: str | None = None
    dirs: set[str] = set()
    for ws in spaces.values():
        dirs.add(ws.taker_dir)
        dirs.add(ws.after_dir)
    for ws in spaces.values():
        # taker_dir lives at <repo>/.worktrees/<dir>
        repo = str(Path(ws.taker_dir).parent.parent)
        break
    for d in dirs:
        if repo:
            subprocess.run(["git", "-C", repo, "worktree", "remove", "--force", d])
