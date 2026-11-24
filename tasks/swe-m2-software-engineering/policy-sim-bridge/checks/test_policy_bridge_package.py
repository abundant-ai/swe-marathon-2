"""Ensure the runtime includes a runnable frozen actor sample and private checks."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

TASK = Path(__file__).resolve().parents[1]


def test_policy_package_has_runnable_manifest_and_separate_native_verifier(tmp_path: Path) -> None:
    """Run the public observation example using the packaged reference."""
    bundle = tmp_path / "bundle"
    subprocess.run(
        [sys.executable, str(TASK / "scripts" / "package_task.py"), "--output", str(bundle)],
        check=True, capture_output=True,
    )
    env = bundle / "environment"
    locomotion_public = {"README.md", "policy.onnx", "go2-headless.xml", "manifest.json",
                         "starter.ndjson", "upstream-LICENSE", "menagerie-LICENSE", "course_example.py"}
    published = {f"example/locomotion/{name}" for name in locomotion_public}
    assert {p.relative_to(env).as_posix() for p in env.rglob("*") if p.is_file()} == published | {
        "Dockerfile", ".dockerignore", "example/manifest.json", "example/sample.json",
    }
    assert (bundle / "steps" / "04-compare-exports" / "tests" / "native.py").is_file()
    assert not (bundle / "steps" / "01-rebuild-observations" / "tests" / "native.py").exists()
    commissioning = bundle / "steps" / "05-commission-backend"
    assert (commissioning / "tests" / "commission.py").is_file()
    assert (commissioning / "solution" / "policy_bridge" / "calibration.py").is_file()
    dynamic = bundle / "steps" / "06-stabilize-deployment"
    assert not (commissioning / "tests" / "dynamics.py").exists()
    assert not (commissioning / "solution" / "policy_bridge" / "drive.py").exists()
    assert (dynamic / "tests" / "dynamics.py").is_file()
    assert (dynamic / "tests" / "commission.py").is_file()
    assert (dynamic / "solution" / "policy_bridge" / "drive.py").is_file()
    locomotion = bundle / "steps" / "07-supervise-free-base-locomotion"
    assert (locomotion / "solution" / "policy_bridge" / "locomotion.py").is_file()
    assert (locomotion / "tests" / "locomotion_native.py").is_file()
    assert (locomotion / "tests" / "dynamics.py").is_file()
    course = bundle / "steps" / "08-route-a-live-go2-course"
    assert (course / "solution" / "policy_bridge" / "course_planner.py").is_file()
    assert (course / "tests" / "course_checks.py").is_file()
    assert not (locomotion / "tests" / "course_checks.py").exists()
    scans = bundle / "steps" / "09-register-live-range-scans"
    assert (scans / "solution" / "policy_bridge" / "scan_nav.py").is_file()
    assert (scans / "tests" / "scan_checks.py").is_file()
    assert not (course / "tests" / "scan_checks.py").exists()
    assert not (course / "solution" / "policy_bridge" / "scan_nav.py").exists()
    public_actor = env / "example" / "locomotion" / "policy.onnx"
    actor_spec = json.loads(public_actor.with_name("manifest.json").read_text())
    private_actor = locomotion / "tests" / "locomotion-assets" / "policy.onnx"
    assert hashlib.sha256(public_actor.read_bytes()).hexdigest() == actor_spec["actor_sha256"]
    assert hashlib.sha256(private_actor.read_bytes()).hexdigest() == actor_spec["actor_sha256"]
    starter = [json.loads(line) for line in public_actor.with_name("starter.ndjson").read_text().splitlines()]
    assert [record["tick"] for record in starter] == list(range(13))
    sample = env / "example"
    output = tmp_path / "frame.json"
    subprocess.run([sys.executable, "-B", "-m", "policy_bridge", "observe",
                    "--spec", str(sample / "manifest.json"), "--input", str(sample / "sample.json"),
                    "--output", str(output)], cwd=bundle / "steps" / "01-rebuild-observations" / "solution",
                   check=True, capture_output=True)
    frame = json.loads(output.read_text())["observation"]
    assert len(frame) == 15 and any(abs(value) > 0.25 for value in frame)
