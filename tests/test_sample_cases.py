import subprocess

from skill_eval.sample_cases import build_sample_cases


def _commit_exists(repo: str, sha: str) -> bool:
    return subprocess.run(["git", "-C", repo, "cat-file", "-e", sha]).returncode == 0


def test_build_sample_cases_returns_10(tmp_path):
    cfgs = build_sample_cases(str(tmp_path))
    assert len(cfgs) == 10


def test_sample_cases_distinct_repos(tmp_path):
    cfgs = build_sample_cases(str(tmp_path))
    repo_paths = [c.repo_path for c in cfgs]
    assert len(set(repo_paths)) == 10


def test_sample_cases_before_after_differ(tmp_path):
    cfgs = build_sample_cases(str(tmp_path))
    for cfg in cfgs:
        assert cfg.before_hash != cfg.after_hash


def test_sample_cases_commits_exist(tmp_path):
    cfgs = build_sample_cases(str(tmp_path))
    for cfg in cfgs:
        assert _commit_exists(cfg.repo_path, cfg.before_hash)
        assert _commit_exists(cfg.repo_path, cfg.after_hash)


def test_sample_cases_task_brief_nonempty(tmp_path):
    cfgs = build_sample_cases(str(tmp_path))
    for cfg in cfgs:
        assert cfg.task_brief.strip()


def test_sample_cases_skill_dirs_exist(tmp_path):
    from pathlib import Path

    cfgs = build_sample_cases(str(tmp_path))
    for cfg in cfgs:
        assert Path(cfg.baseline_skill_path).is_dir()
        assert Path(cfg.challenger_skill_path).is_dir()


def test_sample_cases_skills_are_real_and_contrasting(tmp_path):
    """Batch arms must load DIFFERENT, substantive skills — a real batch run
    against two identical placeholder skills measures nothing."""
    from pathlib import Path

    cfgs = build_sample_cases(str(tmp_path))
    for cfg in cfgs:
        base = (Path(cfg.baseline_skill_path) / "SKILL.md").read_text()
        chal = (Path(cfg.challenger_skill_path) / "SKILL.md").read_text()
        assert base != chal
        assert "placeholder" not in base and "placeholder" not in chal
        # each must contain actual behavioural instruction beyond frontmatter
        assert len(base.split("---")[-1].strip()) > 40
        assert len(chal.split("---")[-1].strip()) > 40
