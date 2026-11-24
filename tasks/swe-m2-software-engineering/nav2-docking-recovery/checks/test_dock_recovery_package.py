"""Check the staged runtime boundary and verify a physical docking trace."""

import json
from pathlib import Path
import subprocess
import sys

TASK = Path(__file__).resolve().parents[1]


def test_packaged_dock_oracle_reaches_contact_without_private_environment_files(tmp_path: Path) -> None:
    """Exercise the packaged controller against the packaged closed-loop verifier."""
    bundle = tmp_path / "bundle"
    subprocess.run([sys.executable, str(TASK / "scripts" / "package_task.py"),
                    "--output", str(bundle)], check=True, capture_output=True)
    assert {p.relative_to(bundle / "environment").as_posix()
            for p in (bundle / "environment").rglob("*") if p.is_file()} == {
                "Dockerfile", ".dockerignore", "example/config.json", "example/native_dock.py", "install_jazzy.sh",
            }
    enhanced = bundle / "steps" / "05-stage-and-reacquire"
    assert (enhanced / "tests" / "staging_plant.py").is_file()
    assert (enhanced / "solution" / "dock_recovery" / "staging.py").is_file()
    assert not (enhanced / "solution" / "dock_recovery" / "compiler.py").exists()
    compiled = bundle / "steps" / "06-compile-curvature-routes"
    assert (compiled / "tests" / "compile_checks.py").is_file()
    assert (compiled / "solution" / "dock_recovery" / "compiler.py").is_file()
    final = bundle / "steps" / "07-confirm-native-seating"
    assert (final / "tests" / "native_cases.py").is_file()
    assert (final / "solution" / "dock_recovery" / "native.py").is_file()
    assert not (compiled / "solution" / "dock_recovery" / "native.py").exists()
    departure = bundle / "steps" / "08-release-powered-dock"
    assert (departure / "tests" / "departure_cases.py").is_file()
    assert (departure / "tests" / "departure_plant.py").is_file()
    assert (departure / "solution" / "dock_recovery" / "departure.py").is_file()
    assert (departure / "solution" / "dock_recovery" / "departure_gate.py").is_file()
    assert not (final / "tests" / "departure_cases.py").exists()
    assert not (departure / "solution" / "dock_recovery" / "departure_plant.py").exists()
    assert "native_cases" not in (bundle / "environment" / "example" / "native_dock.py").read_text()
    stage = bundle / "steps" / "01-reverse-approach"
    output = tmp_path / "result"
    subprocess.run([sys.executable, "-IB", str(stage / "tests" / "verify.py"), "--stage", "1",
                    "--artifact", str(stage / "solution" / "dock_recovery"), "--output", str(output)],
                   check=True, capture_output=True)
    report = json.loads((output / "checkpoint.json").read_text())
    assert report["reward"] == 1
    assert all(len(record["contacts"]) == 1 for record in report["observations"].values())


def test_stationary_handoff_can_omit_stage_edge() -> None:
    """Require edge reports in transit and accept an omitted edge after arrival."""
    witness = """
from plant import Violation
from staging_cases import cases
from staging_plant import StagingPlant

case = cases()[0]
nav = case["navigation"]
config = {"navigation": nav}
reply = {"v_mps": 0, "w_radps": 0, "status": "running"}
in_transit = StagingPlant(case | {"pose": nav["nodes"][nav["start"]]}, config)
try:
    in_transit.observe_command(reply, {})
except Violation as error:
    assert "missing staging edge report" in str(error)
else:
    raise AssertionError("The route requires a staging edge report")
at_goal = StagingPlant(case | {"pose": nav["nodes"][nav["staging"]]}, config)
at_goal.current = nav["staging"]
at_goal.observe_command(reply, {})
assert at_goal.handoff == at_goal.tick
"""
    subprocess.run(
        [sys.executable, "-B", "-c", witness],
        cwd=TASK / "common" / "verifier",
        check=True,
        capture_output=True,
    )


def test_power_acknowledgment_cannot_authorize_departure() -> None:
    """Only current-boot physical state can advance the isolation sample streak."""
    witness = """
from departure_gate import IsolationGate

gate = IsolationGate("depart")
stamp = 3_000_000_000
gate.observe({"kind": "ack", "transaction_id": "depart", "boot": 41,
              "stamp_ns": stamp, "accepted": True}, stamp)
assert not gate.qualified(stamp)
sample = {"kind": "state", "transaction_id": "depart", "boot": 41,
          "contactor_open": False, "current_amps": 1.45, "contact": True}
gate.observe({**sample, "stamp_ns": stamp, "seq": 1}, stamp)
gate.observe({**sample, "boot": 40, "stamp_ns": stamp+1, "seq": 2,
              "contactor_open": True, "current_amps": 0.0}, stamp+1)
assert not gate.qualified(stamp+1)
for i in range(1, 5):
    now = stamp + i*50_000_000
    gate.observe({**sample, "stamp_ns": now, "seq": i+1,
                  "contactor_open": True, "current_amps": .05}, now)
assert gate.qualified(now)
assert not gate.qualified(now+71_000_000)
"""
    subprocess.run(
        [sys.executable, "-B", "-c", witness],
        cwd=TASK / "common" / "oracle",
        check=True,
        capture_output=True,
    )
