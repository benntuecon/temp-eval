"""Ten sample task repos for the skill-eval batch runner.

Each repo has two commits (before/buggy and after/fixed) plus a failing→passing
test file, matching the pattern of skill_eval.sample_repo.build_sample_repo.
"""

from pathlib import Path

from skill_eval import git_ops
from skill_eval.contracts import RunConfig


def _init_repo(path: Path) -> None:
    """Initialise a git repo with standard eval config."""
    path.mkdir(parents=True, exist_ok=True)
    git_ops.init(str(path))
    git_ops.config(str(path), "user.email", "eval@example.com")
    git_ops.config(str(path), "user.name", "Eval Fixture")


def _add_skills(repo: Path) -> tuple[str, str]:
    """Create placeholder skill dirs; return (baseline_path, challenger_path)."""
    for arm in ("baseline", "challenger"):
        sk = repo / ".claude/skills" / arm
        sk.mkdir(parents=True, exist_ok=True)
        (sk / "SKILL.md").write_text(
            f"---\nname: {arm}\ndescription: {arm} coding skill (placeholder)\n---\n"
        )
    return (
        str(repo / ".claude/skills/baseline"),
        str(repo / ".claude/skills/challenger"),
    )


def _make_case(
    base_dir: str,
    case_id: str,
    src_file: str,
    buggy_src: str,
    fixed_src: str,
    test_src: str,
    task_brief: str,
) -> RunConfig:
    """Build one case repo and return its RunConfig."""
    repo = Path(base_dir) / case_id
    _init_repo(repo)
    baseline_path, challenger_path = _add_skills(repo)

    # Before commit (buggy)
    (repo / src_file).write_text(buggy_src)
    (repo / f"test_{src_file}").write_text(test_src)
    git_ops.add_all(str(repo))
    git_ops.commit(str(repo), f"before: {case_id} with bug")
    before_hash = git_ops.rev_parse(str(repo))

    # After commit (fixed)
    (repo / src_file).write_text(fixed_src)
    git_ops.add_all(str(repo))
    git_ops.commit(str(repo), f"after: {case_id} fix")
    after_hash = git_ops.rev_parse(str(repo))

    return RunConfig(
        before_hash=before_hash,
        after_hash=after_hash,
        repo_path=str(repo),
        task_brief=task_brief,
        baseline_skill_path=baseline_path,
        challenger_skill_path=challenger_path,
        models=("claude-haiku-4-5",),
    )


def build_sample_cases(base_dir: str) -> list[RunConfig]:
    """Build 10 sample task repos under *base_dir*; return one RunConfig each."""
    cases: list[RunConfig] = []

    # Case 01: calculator add
    cases.append(
        _make_case(
            base_dir,
            "case_01",
            "calculator.py",
            buggy_src="def add(a, b):\n    return a - b  # BUG\n",
            fixed_src="def add(a, b):\n    return a + b\n",
            test_src=(
                "from calculator import add\n\n\n"
                "def test_add():\n    assert add(2, 3) == 5\n"
            ),
            task_brief=(
                "The `add(a, b)` function in calculator.py subtracts instead of adding. "
                "Fix it so it returns the sum and make the tests pass."
            ),
        )
    )

    # Case 02: string reversal
    cases.append(
        _make_case(
            base_dir,
            "case_02",
            "strings.py",
            buggy_src="def reverse_string(s):\n    return s  # BUG: should reverse\n",
            fixed_src="def reverse_string(s):\n    return s[::-1]\n",
            test_src=(
                "from strings import reverse_string\n\n\n"
                "def test_reverse_string():\n"
                '    assert reverse_string("abc") == "cba"\n'
            ),
            task_brief=(
                "The `reverse_string(s)` function in strings.py returns the string unchanged "
                "instead of reversed. Fix it so reverse_string('abc') returns 'cba'."
            ),
        )
    )

    # Case 03: is_even parity check
    cases.append(
        _make_case(
            base_dir,
            "case_03",
            "numbers.py",
            buggy_src="def is_even(n):\n    return n % 2 == 1  # BUG: inverted\n",
            fixed_src="def is_even(n):\n    return n % 2 == 0\n",
            test_src=(
                "from numbers import is_even\n\n\n"
                "def test_is_even():\n"
                "    assert is_even(4)\n"
                "    assert not is_even(3)\n"
            ),
            task_brief=(
                "The `is_even(n)` function in numbers.py has inverted logic (returns True for "
                "odd numbers). Fix it so is_even(4) is True and is_even(3) is False."
            ),
        )
    )

    # Case 04: factorial missing base case
    cases.append(
        _make_case(
            base_dir,
            "case_04",
            "recursion.py",
            buggy_src=(
                "def factorial(n):\n"
                "    return n * factorial(n - 1)  # BUG: missing base case\n"
            ),
            fixed_src=(
                "def factorial(n):\n"
                "    if n <= 1:\n"
                "        return 1\n"
                "    return n * factorial(n - 1)\n"
            ),
            test_src=(
                "from recursion import factorial\n\n\n"
                "def test_factorial():\n"
                "    assert factorial(5) == 120\n"
            ),
            task_brief=(
                "The `factorial(n)` function in recursion.py is missing a base case and causes "
                "infinite recursion. Add `if n <= 1: return 1` so factorial(5) returns 120."
            ),
        )
    )

    # Case 05: max_in_list uses min
    cases.append(
        _make_case(
            base_dir,
            "case_05",
            "lists.py",
            buggy_src="def max_in_list(xs):\n    return min(xs)  # BUG: should be max\n",
            fixed_src="def max_in_list(xs):\n    return max(xs)\n",
            test_src=(
                "from lists import max_in_list\n\n\n"
                "def test_max_in_list():\n"
                "    assert max_in_list([3, 7, 2]) == 7\n"
            ),
            task_brief=(
                "The `max_in_list(xs)` function in lists.py returns the minimum instead of "
                "the maximum. Fix it so max_in_list([3, 7, 2]) returns 7."
            ),
        )
    )

    # Case 06: count_vowels missing 'u'
    cases.append(
        _make_case(
            base_dir,
            "case_06",
            "text.py",
            buggy_src=(
                "def count_vowels(s):\n"
                '    vowels = "aeio"  # BUG: missing u\n'
                "    return sum(1 for c in s.lower() if c in vowels)\n"
            ),
            fixed_src=(
                "def count_vowels(s):\n"
                '    vowels = "aeiou"\n'
                "    return sum(1 for c in s.lower() if c in vowels)\n"
            ),
            test_src=(
                "from text import count_vowels\n\n\n"
                "def test_count_vowels():\n"
                '    assert count_vowels("queue") == 4\n'
            ),
            task_brief=(
                "The `count_vowels(s)` function in text.py uses vowels='aeio' (missing 'u'). "
                "Fix it so count_vowels('queue') returns 4."
            ),
        )
    )

    # Case 07: fizzbuzz wrong check order
    cases.append(
        _make_case(
            base_dir,
            "case_07",
            "fizzbuzz.py",
            buggy_src=(
                "def fizzbuzz(n):\n"
                "    if n % 3 == 0:\n"
                '        return "Fizz"  # BUG: checked before n%15\n'
                "    elif n % 5 == 0:\n"
                '        return "Buzz"\n'
                "    elif n % 15 == 0:\n"
                '        return "FizzBuzz"\n'
                "    return str(n)\n"
            ),
            fixed_src=(
                "def fizzbuzz(n):\n"
                "    if n % 15 == 0:\n"
                '        return "FizzBuzz"\n'
                "    elif n % 3 == 0:\n"
                '        return "Fizz"\n'
                "    elif n % 5 == 0:\n"
                '        return "Buzz"\n'
                "    return str(n)\n"
            ),
            test_src=(
                "from fizzbuzz import fizzbuzz\n\n\n"
                "def test_fizzbuzz_15():\n"
                '    assert fizzbuzz(15) == "FizzBuzz"\n'
            ),
            task_brief=(
                "The `fizzbuzz(n)` function in fizzbuzz.py checks n%3 and n%5 before n%15, "
                "so fizzbuzz(15) returns 'Fizz' instead of 'FizzBuzz'. Fix the check order."
            ),
        )
    )

    # Case 08: celsius to fahrenheit missing +32
    cases.append(
        _make_case(
            base_dir,
            "case_08",
            "temperature.py",
            buggy_src=("def c_to_f(c):\n" "    return c * 9 / 5  # BUG: missing + 32\n"),
            fixed_src=("def c_to_f(c):\n" "    return c * 9 / 5 + 32\n"),
            test_src=(
                "from temperature import c_to_f\n\n\n"
                "def test_c_to_f():\n"
                "    assert c_to_f(100) == 212\n"
            ),
            task_brief=(
                "The `c_to_f(c)` function in temperature.py is missing the +32 offset. "
                "Fix it so c_to_f(100) returns 212."
            ),
        )
    )

    # Case 09: dedupe doesn't preserve order
    cases.append(
        _make_case(
            base_dir,
            "case_09",
            "dedupe.py",
            buggy_src=("def dedupe(xs):\n" "    return list(set(xs))  # BUG: doesn't preserve order\n"),
            fixed_src=(
                "def dedupe(xs):\n"
                "    seen: set = set()\n"
                "    result = []\n"
                "    for x in xs:\n"
                "        if x not in seen:\n"
                "            seen.add(x)\n"
                "            result.append(x)\n"
                "    return result\n"
            ),
            test_src=(
                "from dedupe import dedupe\n\n\n"
                "def test_dedupe_preserves_order():\n"
                "    assert dedupe([3, 1, 3, 2, 1]) == [3, 1, 2]\n"
            ),
            task_brief=(
                "The `dedupe(xs)` function in dedupe.py uses set() which destroys ordering. "
                "Rewrite it to deduplicate while preserving first-occurrence order so "
                "dedupe([3, 1, 3, 2, 1]) returns [3, 1, 2]."
            ),
        )
    )

    # Case 10: gcd stub returns a
    cases.append(
        _make_case(
            base_dir,
            "case_10",
            "mathutils.py",
            buggy_src=("def gcd(a, b):\n" "    return a  # BUG: stub, should be Euclidean algorithm\n"),
            fixed_src=(
                "def gcd(a, b):\n"
                "    while b:\n"
                "        a, b = b, a % b\n"
                "    return a\n"
            ),
            test_src=(
                "from mathutils import gcd\n\n\n"
                "def test_gcd():\n"
                "    assert gcd(12, 18) == 6\n"
            ),
            task_brief=(
                "The `gcd(a, b)` function in mathutils.py is a stub that returns `a`. "
                "Implement the Euclidean algorithm so gcd(12, 18) returns 6."
            ),
        )
    )

    return cases
