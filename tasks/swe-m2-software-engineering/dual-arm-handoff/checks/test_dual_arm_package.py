"""Check that the multi-step bundle ships isolated verification code."""

from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def test_dual_arm_runtime_contains_only_the_enabled_reference_modules(tmp_path):
    subprocess.run([sys.executable, "-B", str(ROOT/"scripts/package_task.py"), "--output", str(tmp_path)],
                   check=True, capture_output=True, timeout=15)
    steps = tmp_path/"swe-m2_software-engineering_dual-arm-handoff"/"steps"
    first, middle, recovery, final, commission, synthesis, native = sorted(steps.iterdir())
    assert not (first/"solution/dual_arm/planning.py").exists()
    assert not (middle/"solution/dual_arm/dispatch.py").exists()
    assert (recovery/"solution/dual_arm/dispatch.py").is_file()
    assert not (recovery/"solution/dual_arm/contingency.py").exists()
    assert (final/"solution/dual_arm/contingency.py").is_file()
    assert (final/"tests/contingency_checks.py").is_file()
    assert (final/"tests/plant.py").is_file()
    assert not (final/"solution/dual_arm/plant.py").exists()
    assert not (final/"tests/ur5e-headless.xml").exists()
    assert (commission/"solution/dual_arm/commission_native.py").is_file()
    assert (commission/"tests/UR5E-LICENSE.txt").is_file()
    assert (synthesis/"tests/native_scenarios.py").is_file()
    assert (native/"solution/dual_arm/dispatch_native.py").is_file()
