"""Exercise graph recovery and a journaled failed switch from the packaged oracle."""

import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
BUNDLE = "swe-m2_software-engineering_ros2-control-recovery"


def test_packaged_controller_recovery(tmp_path):
    subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/package_task.py"), "--output", str(tmp_path)],
        check=True, timeout=15, capture_output=True,
    )
    step = tmp_path / BUNDLE / "steps/04-schedule-handover"
    logs = tmp_path / "logs"
    subprocess.run(
        [sys.executable, "-BI", str(step / "tests/verify.py"), "--stage", "4",
         "--artifact", str(step / "solution/control_recovery"), "--logs", str(logs)],
        check=True, timeout=75, capture_output=True,
    )
    assert (logs / "reward.txt").read_text().strip() == "1"
    assert not (tmp_path / BUNDLE / "checks").exists()
    assert not (step / "solution/control_recovery/servo.py").exists()
    assert not (step / "tests/servo_checks.py").exists()
    final = tmp_path / BUNDLE / "steps/05-run-protected-servo"
    subprocess.run(
        [sys.executable, "-BI", str(final / "tests/verify.py"), "--stage", "5",
         "--artifact", str(final / "solution/control_recovery"), "--logs", str(tmp_path / "servo-logs")],
        check=True, timeout=75, capture_output=True,
    )
    result = json.loads((tmp_path / "servo-logs/checkpoint.json").read_text())
    assert result["reward"] == 1.0
    assert result["servo_observations"]["pending_reset"]["restart_in_pending_transfer"]


def test_packaged_restart_keeps_the_native_predecessor(tmp_path):
    subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/package_task.py"), "--output", str(tmp_path)],
        check=True, timeout=15, capture_output=True,
    )
    steps = tmp_path / BUNDLE / "steps"
    previous = steps / "06-recover-native-controller-manager"
    current = steps / "07-restore-native-manager"
    source = Path("solution/native/fenced_drive")
    driver = source / "src/system.cpp"
    assert "generation_file" not in (previous / driver).read_text()
    assert "generation_file" in (current / driver).read_text()
    assert (current / source / "src/generation_ledger.hpp").is_file()
    assert (current / "tests/verify_native.py").read_bytes() == (previous / "tests/verify.py").read_bytes()
    assert not (previous / "tests/restart_checks.py").exists()


def test_loaded_lift_keeps_plant_and_reference_separate(tmp_path):
    subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/package_task.py"), "--output", str(tmp_path)],
        check=True, timeout=15, capture_output=True,
    )
    bundle = tmp_path / BUNDLE
    step = bundle / "steps/08-transfer-loaded-chain"
    oracle = step / "solution/native/coupled_handover"
    assert (oracle / "src/controllers.cpp").is_file()
    assert (oracle / "scripts/recover_pair").stat().st_mode & 0o111
    assert (step / "tests/lift_device/src/device.cpp").is_file()
    assert (step / "tests/verify_restart.py").read_bytes() == (
        bundle / "steps/07-restore-native-manager/tests/verify.py").read_bytes()
    assert not (bundle / "environment/lift_device").exists()
    assert not (step / "solution/native/lift_device").exists()
