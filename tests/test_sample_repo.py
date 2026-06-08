import subprocess

from skill_eval.sample_repo import build_sample_repo


def _commit_exists(repo: str, sha: str) -> bool:
    return subprocess.run(["git", "-C", repo, "cat-file", "-e", sha]).returncode == 0


def test_build_sample_repo(tmp_path):
    cfg = build_sample_repo(str(tmp_path))
    assert cfg.repo_path == str(tmp_path)
    assert cfg.before_hash and cfg.after_hash
    assert cfg.before_hash != cfg.after_hash
    assert _commit_exists(cfg.repo_path, cfg.before_hash)
    assert _commit_exists(cfg.repo_path, cfg.after_hash)
    assert cfg.task_brief
    # before has the bug, after fixes it
    before = subprocess.run(
        ["git", "-C", cfg.repo_path, "show", f"{cfg.before_hash}:calculator.py"],
        capture_output=True,
        text=True,
    ).stdout
    after = subprocess.run(
        ["git", "-C", cfg.repo_path, "show", f"{cfg.after_hash}:calculator.py"],
        capture_output=True,
        text=True,
    ).stdout
    assert "return a - b" in before  # the bug
    assert "return a + b" in after  # the fix
