"""Tests for skill_eval/git_ops.py — no network calls required."""

from __future__ import annotations

import tempfile
import threading
from pathlib import Path

from skill_eval import git_ops

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_repo(path: str) -> None:
    """Initialise a repo with git identity configured."""
    git_ops.init(path)
    git_ops.config(path, "user.email", "test@example.com")
    git_ops.config(path, "user.name", "Test User")


# ---------------------------------------------------------------------------
# test_repo_roundtrip
# ---------------------------------------------------------------------------


def test_repo_roundtrip(tmp_path: Path) -> None:
    repo = str(tmp_path / "repo")
    Path(repo).mkdir()

    # init + config
    _make_repo(repo)

    # write + add + commit → sha1
    (Path(repo) / "hello.txt").write_text("hello\n")
    git_ops.add_all(repo)
    git_ops.commit(repo, "initial commit")
    sha1 = git_ops.rev_parse(repo)
    assert len(sha1) == 40, f"expected a 40-char SHA, got {sha1!r}"

    # edit + commit → sha2
    (Path(repo) / "hello.txt").write_text("hello world\n")
    git_ops.add_all(repo)
    git_ops.commit(repo, "second commit")
    sha2 = git_ops.rev_parse(repo)
    assert sha1 != sha2

    # diff between the two commits shows the change
    patch = git_ops.diff(repo, sha1, sha2)
    assert "hello world" in patch
    assert "hello" in patch

    # worktree_add at sha1 creates a dir with the first version
    wt_dir = str(tmp_path / "wt1")
    git_ops.worktree_add(repo, wt_dir, sha1)
    assert Path(wt_dir).is_dir()
    assert (Path(wt_dir) / "hello.txt").read_text() == "hello\n"

    # edit in the worktree → add_all + diff_cached shows it
    (Path(wt_dir) / "hello.txt").write_text("modified in worktree\n")
    git_ops.add_all(wt_dir)
    cached = git_ops.diff_cached(wt_dir)
    assert "modified in worktree" in cached

    # worktree_remove returns True
    result = git_ops.worktree_remove(repo, wt_dir)
    assert result is True

    # worktree_prune runs without error
    git_ops.worktree_prune(repo)


# ---------------------------------------------------------------------------
# test_concurrent_worktree_add
# ---------------------------------------------------------------------------


def test_concurrent_worktree_add(tmp_path: Path) -> None:
    """16 threads calling worktree_add concurrently must all succeed."""
    repo = str(tmp_path / "repo")
    Path(repo).mkdir()
    _make_repo(repo)

    # Commit one file so the worktrees have something to check out
    (Path(repo) / "data.txt").write_text("important data\n")
    git_ops.add_all(repo)
    git_ops.commit(repo, "base commit")
    head = git_ops.rev_parse(repo)

    num_threads = 16
    wt_dirs: list[str] = []
    errors: list[Exception] = []
    lock = threading.Lock()

    def add_worktree() -> None:
        wt = tempfile.mkdtemp(prefix="wt_", dir=tmp_path)
        try:
            git_ops.worktree_add(repo, wt, head)
            with lock:
                wt_dirs.append(wt)
        except Exception as exc:  # noqa: BLE001
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=add_worktree) for _ in range(num_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # All 16 must have succeeded — no errors, all dirs exist with the file
    assert errors == [], f"worktree_add failures: {errors}"
    assert len(wt_dirs) == num_threads
    for d in wt_dirs:
        assert Path(d).is_dir(), f"worktree dir missing: {d}"
        assert (Path(d) / "data.txt").read_text() == "important data\n"

    # Clean up
    for d in wt_dirs:
        git_ops.worktree_remove(repo, d)
    git_ops.worktree_prune(repo)
