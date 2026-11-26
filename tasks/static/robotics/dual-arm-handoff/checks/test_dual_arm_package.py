"""Check that the multi-step bundle ships isolated verification code."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_dual_arm_runtime_contains_only_the_enabled_reference_modules(
    tmp_path: Path,
) -> None:
    """Build the isolated bundle under tmp_path and inspect each release boundary."""
    subprocess.run(
        [
            sys.executable,
            "-B",
            str(ROOT / "scripts/package_task.py"),
            "--output",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
        timeout=15,
    )
    steps = tmp_path / "swe-m2_software-engineering_dual-arm-handoff" / "steps"
    first, middle, recovery, final, commission, synthesis, native, grasp = sorted(
        steps.iterdir()
    )
    assert not (first / "solution/dual_arm/planning.py").exists()
    assert not (middle / "solution/dual_arm/dispatch.py").exists()
    assert (recovery / "solution/dual_arm/dispatch.py").is_file()
    assert not (recovery / "solution/dual_arm/contingency.py").exists()
    assert (final / "solution/dual_arm/contingency.py").is_file()
    assert (final / "tests/contingency_checks.py").is_file()
    assert (final / "tests/plant.py").is_file()
    assert not (final / "solution/dual_arm/plant.py").exists()
    assert not (final / "tests/ur5e-headless.xml").exists()
    assert (commission / "solution/dual_arm/commission_native.py").is_file()
    assert (commission / "tests/UR5E-LICENSE.txt").is_file()
    assert (synthesis / "tests/native_scenarios.py").is_file()
    assert (synthesis / "tests/cell_truth.py").is_file()
    assert not (synthesis / "solution/dual_arm/drawn_cell.py").exists()
    assert (native / "solution/dual_arm/dispatch_native.py").is_file()
    assert (native / "solution/dual_arm/drawn_cell.py").is_file()
    environment = steps.parent / "environment"
    sheets = sorted(path.name for path in (environment / "resources/cell").iterdir())
    assert sheets == [f"cell-sheet-{n}.png" for n in range(1, 5)]
    assert not any(path.name == "cell_truth.py" for path in environment.rglob("*"))
    assert grasp.name == "08-recover-slipped-grasp"
    assert (grasp / "tests/requirements.txt").read_bytes() == (
        native / "tests/requirements.txt"
    ).read_bytes()
    assert (grasp / "tests/ur5e-headless.xml").read_bytes() == (
        native / "tests/ur5e-headless.xml"
    ).read_bytes()
    assert (grasp / "tests/grasp_recovery_checks.py").is_file()
    assert (grasp / "solution/dual_arm/dispatch_native.py").is_file()
    oracle_modules = ("grasp_recovery.py", "grasp_observations.py")
    for module in oracle_modules:
        assert (grasp / "solution/dual_arm" / module).is_file()
    for earlier in (first, middle, recovery, final, commission, synthesis, native):
        for module in oracle_modules:
            assert not (earlier / "solution/dual_arm" / module).exists()
        assert not (earlier / "tests/grasp_recovery_checks.py").exists()
    for step, recovery_available in ((native, False), (grasp, True)):
        candidate_help = subprocess.run(
            [sys.executable, "-B", "-m", "dual_arm", "--help"],
            cwd=step / "solution",
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert (
            "dispatch-grasp-recovery" in candidate_help.stdout
        ) == recovery_available
    help_result = subprocess.run(
        [sys.executable, "-IB", str(grasp / "tests/verify.py"), "--help"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert "--grasp-only" in help_result.stdout
