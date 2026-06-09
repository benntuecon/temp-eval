import subprocess

from skill_eval.flagship_case import build_flagship_case


def _commit_exists(repo: str, sha: str) -> bool:
    return subprocess.run(["git", "-C", repo, "cat-file", "-e", sha]).returncode == 0


def _show_file(repo: str, sha: str, filename: str) -> str | None:
    """Return file contents at a given commit, or None if the file doesn't exist."""
    result = subprocess.run(
        ["git", "-C", repo, "show", f"{sha}:{filename}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout


def test_build_flagship_case(tmp_path):
    cfg = build_flagship_case(str(tmp_path))

    # Basic RunConfig shape
    assert cfg.repo_path == str(tmp_path)
    assert cfg.before_hash and cfg.after_hash
    assert cfg.before_hash != cfg.after_hash

    # Both commits exist
    assert _commit_exists(cfg.repo_path, cfg.before_hash)
    assert _commit_exists(cfg.repo_path, cfg.after_hash)

    # task_brief is non-empty
    assert cfg.task_brief.strip()

    # --- before commit checks ---
    before_refund = _show_file(cfg.repo_path, cfg.before_hash, "refund.py")
    assert before_refund is not None, "refund.py must exist in before commit"
    assert "NotImplementedError" in before_refund, "before must have the stub"

    # test_refund.py must NOT be in the before commit
    before_test = _show_file(cfg.repo_path, cfg.before_hash, "test_refund.py")
    assert before_test is None, "test_refund.py must NOT exist in before commit"

    # --- after commit checks ---
    after_refund = _show_file(cfg.repo_path, cfg.after_hash, "refund.py")
    assert after_refund is not None, "refund.py must exist in after commit"
    assert "prorate_refund" in after_refund, "after must contain the implementation"
    assert "NotImplementedError" not in after_refund, "after must not be the stub"

    after_test = _show_file(cfg.repo_path, cfg.after_hash, "test_refund.py")
    assert after_test is not None, "test_refund.py must exist in after commit"
    assert "prorate_refund" in after_test

    # --- skill paths ---
    from pathlib import Path

    baseline = Path(cfg.baseline_skill_path)
    challenger = Path(cfg.challenger_skill_path)
    assert baseline.exists(), f"baseline_skill_path must exist: {baseline}"
    assert challenger.exists(), f"challenger_skill_path must exist: {challenger}"
    assert (baseline / "SKILL.md").exists(), "baseline must contain SKILL.md"
    assert (challenger / "SKILL.md").exists(), "challenger must contain SKILL.md"

    # --- skill identity sanity ---
    # baseline is ship-it-fast (bad), challenger is disciplined (good)
    assert "ship-it-fast" in str(baseline)
    assert "disciplined" in str(challenger)

    # --- thinking budget ---
    assert cfg.thinking_budget == 2048
