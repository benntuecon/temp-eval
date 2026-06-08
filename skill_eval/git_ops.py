"""git_ops — the sole git shell-out point for skill-eval.

All functions accept a *repo* path (passed as ``git -C <repo>``) so callers
never need to change their working directory.  Concurrency hardening for
``worktree_add``/``worktree_remove`` is achieved via:

1. A module-level threading.Lock that serialises the brief git bookkeeping
   calls while leaving the actual work inside worktrees fully parallel.
2. A retry-with-exponential-backoff helper that handles cross-process
   ``index.lock`` / "unable to create" / "cannot lock" races.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import time
from collections.abc import Callable

# ---------------------------------------------------------------------------
# Concurrency primitives
# ---------------------------------------------------------------------------

_WORKTREE_LOCK = threading.Lock()

# Patterns that indicate a transient git lock collision
_LOCK_PATTERNS = (
    "index.lock",
    "Unable to create",
    "cannot lock",
    "another git process",
)

_MAX_RETRIES = 6


def _is_lock_error(exc: subprocess.CalledProcessError) -> bool:
    stderr = exc.stderr or ""
    return any(p.lower() in stderr.lower() for p in _LOCK_PATTERNS)


def _retry_git(fn: Callable[[], str]) -> str:
    """Call *fn* up to _MAX_RETRIES+1 times, backing off on lock errors."""
    for attempt in range(_MAX_RETRIES + 1):
        try:
            return fn()
        except subprocess.CalledProcessError as exc:
            if attempt < _MAX_RETRIES and _is_lock_error(exc):
                delay = min(0.05 * (2**attempt), 1.0)
                time.sleep(delay)
            else:
                raise
    # unreachable, but satisfies type checker
    raise RuntimeError("unreachable")  # pragma: no cover


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _run(repo: str, *args: str, check: bool = True) -> str:
    """Run ``git -C <repo> <args>`` and return stdout as a string."""
    result = subprocess.run(
        ["git", "-C", repo, *args],
        check=check,
        capture_output=True,
        text=True,
    )
    return result.stdout


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def init(repo: str) -> None:
    """Initialise a git repository at *repo* (quiet)."""
    _run(repo, "init", "-q")


def config(repo: str, key: str, value: str) -> None:
    """Set a git config *key* to *value* in the repository at *repo*."""
    _run(repo, "config", key, value)


def add_all(repo: str) -> None:
    """Stage all changes (``git add -A``) in the repository at *repo*."""
    _run(repo, "add", "-A")


def commit(repo: str, message: str) -> None:
    """Create a commit with *message* in the repository at *repo* (quiet)."""
    _run(repo, "commit", "-q", "-m", message)


def rev_parse(repo: str, ref: str = "HEAD") -> str:
    """Return the resolved SHA for *ref* (stripped of whitespace)."""
    return _run(repo, "rev-parse", ref).strip()


def diff(repo: str, a: str, b: str) -> str:
    """Return the diff between refs *a* and *b* (``git diff a..b``)."""
    return _run(repo, "diff", f"{a}..{b}")


def diff_workdir(repo: str) -> str:
    """Return the working-tree diff for the repository at *repo*."""
    return _run(repo, "diff")


def diff_cached(repo: str, ref: str = "HEAD") -> str:
    """Return the cached (staged) diff against *ref* for the repository at *repo*."""
    return _run(repo, "diff", "--cached", ref)


def worktree_add(repo: str, path: str, ref: str) -> None:
    """Add a detached worktree at *path* checked out at *ref*.

    The bookkeeping git call is serialised via ``_WORKTREE_LOCK`` and retried
    on transient lock errors so concurrent callers do not collide.
    """
    with _WORKTREE_LOCK:
        _retry_git(lambda: _run(repo, "worktree", "add", "--detach", "-f", path, ref))


def worktree_remove(repo: str, path: str) -> bool:
    """Remove the worktree at *path* (best-effort).

    Returns True on success.  On failure, prints a one-line warning to stderr
    and returns False — never raises.
    """
    try:
        with _WORKTREE_LOCK:
            _retry_git(lambda: _run(repo, "worktree", "remove", "--force", path))
        return True
    except Exception as exc:  # noqa: BLE001
        stderr_text = getattr(exc, "stderr", "") or ""
        print(
            f"warn: worktree remove failed for {path}: {stderr_text.strip() or exc}",
            file=sys.stderr,
        )
        return False


def worktree_prune(repo: str) -> None:
    """Prune stale worktree registrations (best-effort; swallows errors)."""
    try:
        _run(repo, "worktree", "prune")
    except Exception:  # noqa: BLE001
        pass
