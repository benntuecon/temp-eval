from pathlib import Path

from skill_eval import git_ops
from skill_eval.contracts import RunConfig

# Absolute paths to the real skill directories (relative to repo root)
_REPO_ROOT = Path(__file__).resolve().parents[1]
_DISCIPLINED_SKILL = _REPO_ROOT / "flagship" / "skills" / "disciplined"
_SHIP_IT_FAST_SKILL = _REPO_ROOT / "flagship" / "skills" / "ship-it-fast"

TASK_BRIEF = (
    "A customer cancels their monthly subscription partway through the month. "
    "Implement `prorate_refund(monthly_price_cents, days_used)` in `refund.py` "
    "so it returns, in **cents**, how much to refund for the unused portion of "
    "the month. `days_used` is the number of whole days they've had it this "
    "cycle. Make it production-ready; the stub currently raises NotImplementedError."
)

_REFUND_STUB = '''\
def prorate_refund(monthly_price_cents: int, days_used: int) -> int:
    """Refund (in cents) the unused portion of a 30-day monthly subscription."""
    raise NotImplementedError
'''

_REFUND_GOLD = '''\
from decimal import ROUND_HALF_UP, Decimal


def prorate_refund(monthly_price_cents: int, days_used: int) -> int:
    """Refund (in cents) the unused portion of a 30-day monthly subscription."""
    if days_used <= 0:  # same-day / invalid -> full refund
        return monthly_price_cents
    unused_days = max(0, 30 - days_used)
    raw = Decimal(monthly_price_cents) * Decimal(unused_days) / Decimal(30)
    refund = int(raw.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return min(monthly_price_cents, max(0, refund))
'''

_TEST_REFUND = """\
import pytest

from refund import prorate_refund


@pytest.mark.parametrize("price,days,expected", [
    (3000, 0, 3000),   # same-day cancel -> full refund
    (3000, 30, 0),     # used the full month -> no refund
    (3000, 45, 0),     # over-used (clamp) -> no refund
    (3000, 15, 1500),  # half month used -> half refund
    (3001, 10, 2001),  # odd cents, half-up rounding
    (3000, -3, 3000),  # negative days_used -> full refund (clamp)
])
def test_prorate_refund(price, days, expected):
    assert prorate_refund(price, days) == expected
"""


def build_flagship_case(base_dir: str) -> RunConfig:
    repo = Path(base_dir)
    repo.mkdir(parents=True, exist_ok=True)
    git_ops.init(base_dir)
    git_ops.config(base_dir, "user.email", "eval@example.com")
    git_ops.config(base_dir, "user.name", "Eval Fixture")

    # --- before commit: stub only, NO test file ---
    (repo / "refund.py").write_text(_REFUND_STUB)
    git_ops.add_all(base_dir)
    git_ops.commit(base_dir, "before: prorate_refund stub")
    before = git_ops.rev_parse(base_dir)

    # --- after commit: gold implementation + tests ---
    (repo / "refund.py").write_text(_REFUND_GOLD)
    (repo / "test_refund.py").write_text(_TEST_REFUND)
    git_ops.add_all(base_dir)
    git_ops.commit(base_dir, "after: prorate_refund gold impl + tests")
    after = git_ops.rev_parse(base_dir)

    return RunConfig(
        before_hash=before,
        after_hash=after,
        repo_path=base_dir,
        task_brief=TASK_BRIEF,
        baseline_skill_path=str(_SHIP_IT_FAST_SKILL),
        challenger_skill_path=str(_DISCIPLINED_SKILL),
        models=("claude-haiku-4-5",),
    )
