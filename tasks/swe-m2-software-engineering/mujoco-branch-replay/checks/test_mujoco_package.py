"""Verify pinned native dependencies and package boundaries in a fresh bundle."""

import importlib.util
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = "swe-m2_software-engineering_mujoco-branch-replay"


def test_mujoco_package_keeps_native_inputs_and_verifier_separate(tmp_path):
    subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/package_task.py"), "--output", str(tmp_path)],
        check=True, timeout=12, capture_output=True,
    )
    bundle = tmp_path / BUNDLE
    assert set(path.name for path in bundle.iterdir()) == {"task.toml", "environment", "steps"}
    requirements = (bundle / "environment/requirements.txt").read_bytes()
    assert b"mujoco==3.3.7" in requirements
    for step in (bundle / "steps").iterdir():
        assert (step / "tests/requirements.txt").read_bytes() == requirements
        assert not (step / "solution/simbranch/probes.py").exists()
    step = bundle / "steps/04-rebase-checkpoint"
    assert (step / "tests" / "rebase_checks.py").is_file()
    assert not (step / "solution" / "simbranch" / "rebase_checks.py").exists()
    assert not (bundle / "steps/03-branch-study/tests/rebase_checks.py").exists()
    final = bundle / "steps/05-rechart-contact-fork"
    assert (final / "tests/chart_checks.py").is_file()
    assert (final / "tests/rebase_checks.py").is_file()
    assert (final / "solution/simbranch/rechart.py").is_file()
    assert not (final / "solution/simbranch/chart_checks.py").exists()
    assert not (step / "solution/simbranch/rechart.py").exists()
    if importlib.util.find_spec("mujoco") is not None:
        logs = tmp_path / "logs"
        subprocess.run(
            [sys.executable, "-BI", str(final / "tests/verify.py"), "--stage", "5",
             "--artifact", str(final / "solution/simbranch"), "--logs", str(logs)],
            check=True, timeout=90, capture_output=True,
        )
        assert (logs / "reward.txt").read_text().strip() == "1"
