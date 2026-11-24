"""Verify pinned native dependencies and package boundaries in a fresh bundle."""

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = "swe-m2_software-engineering_mujoco-branch-replay"


def test_mujoco_package_keeps_native_inputs_and_verifier_separate(tmp_path):
    subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/package_task.py"), "--output", str(tmp_path)],
        check=True, timeout=12, capture_output=True,
    )
    bundle = tmp_path / BUNDLE
    assert {path.name for path in bundle.iterdir()} == {"task.toml", "environment", "steps"}
    requirements = (bundle / "environment/requirements.txt").read_bytes()
    assert b"mujoco==3.3.7" in requirements
    for step in (bundle / "steps").iterdir():
        assert (step / "tests/requirements.txt").read_bytes() == requirements
        assert not (step / "solution/simbranch/probes.py").exists()
    step = bundle / "steps/04-rebase-checkpoint"
    assert (step / "tests" / "rebase_checks.py").is_file()
    assert not (step / "solution" / "simbranch" / "rebase_checks.py").exists()
    assert not (bundle / "steps/03-branch-study/tests/rebase_checks.py").exists()
    chart = bundle / "steps/05-rechart-contact-fork"
    assert (chart / "tests/chart_checks.py").is_file()
    assert (chart / "tests/rebase_checks.py").is_file()
    assert (chart / "solution/simbranch/rechart.py").is_file()
    assert not (chart / "solution/simbranch/chart_checks.py").exists()
    assert not (step / "solution/simbranch/rechart.py").exists()
    handoff = bundle / "steps/06-transfer-rigid-payload"
    assert (handoff / "tests/latch_checks.py").is_file()
    assert (handoff / "tests/chart_checks.py").is_file()
    assert (handoff / "solution/simbranch/handoff.py").is_file()
    assert (handoff / "solution/simbranch/handoff_model.py").is_file()
    assert not (handoff / "solution/simbranch/latch_checks.py").exists()
    assert not (chart / "tests/latch_checks.py").exists()
    assert not (chart / "solution/simbranch/handoff.py").exists()
    if importlib.util.find_spec("mujoco") is not None:
        arena_probe = """
import sys
sys.path.insert(0, sys.argv[1])
from latch_checks import _bounded_arena
assert all(_bounded_arena(value) for value in ('32M', '+32M', '032M', ' 32M ', '-1', '256M'))
assert not any(_bounded_arena(value) for value in ('1G', '257M', '-2', 'unlimited'))
"""
        subprocess.run(
            [sys.executable, "-BI", "-c", arena_probe, str(handoff / "tests")],
            check=True, timeout=12, capture_output=True,
        )
        logs = tmp_path / "logs"
        subprocess.run(
            [sys.executable, "-BI", str(handoff / "tests/verify.py"), "--stage", "6",
             "--artifact", str(handoff / "solution/simbranch"), "--logs", str(logs)],
            check=True, timeout=90, capture_output=True,
        )
        assert (logs / "reward.txt").read_text().strip() == "1"
