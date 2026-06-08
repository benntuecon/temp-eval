import os

from skill_eval.contracts import Arm
from skill_eval.sample_repo import build_sample_repo
from skill_eval.sandbox import cleanup_workspaces, prepare_workspaces


def test_prepare_workspaces(tmp_path):
    cfg = build_sample_repo(str(tmp_path / "repo"))
    spaces = prepare_workspaces(cfg)
    try:
        assert set(spaces) == {Arm.BASELINE, Arm.CHALLENGER}
        for arm, ws in spaces.items():
            assert ws.arm is arm
            assert os.path.isdir(ws.taker_dir)
            # taker dir is checked out at the BEFORE commit (still has the bug)
            calc = open(os.path.join(ws.taker_dir, "calculator.py")).read()
            assert "return a - b" in calc
            # after dir has the fix
            after_calc = open(os.path.join(ws.after_dir, "calculator.py")).read()
            assert "return a + b" in after_calc
            # gold diff goes bug -> fix
            assert "-    return a - b" in ws.gold_diff
            assert "+    return a + b" in ws.gold_diff
    finally:
        cleanup_workspaces(spaces)
