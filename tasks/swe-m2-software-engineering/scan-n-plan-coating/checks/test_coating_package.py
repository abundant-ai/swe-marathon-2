"""Exercise the maintained coating package's candidate/verifier boundary."""

import json
from pathlib import Path
import subprocess
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_coating_registration_package_isolated_from_private_inputs(tmp_path: Path) -> None:
    """Build the configured release and inspect the isolated runtime trees."""
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / "scripts/package_task.py"), "--output", str(tmp_path)],
        check=True, capture_output=True, text=True, timeout=15,
    )
    bundle = Path(result.stdout.strip())
    assert bundle.parent == tmp_path
    assert {path.name for path in bundle.iterdir()} == {"task.toml", "environment", "steps"}
    steps = sorted((bundle / "steps").iterdir())
    step = steps[0]
    config = tomllib.loads((bundle / "task.toml").read_text(encoding="utf-8"))
    assert config["verifier"]["environment_mode"] == "separate"
    assert config["artifacts"] == ["/app/coating", "/app/coating_app"]
    assert step.name == config["steps"][0]["name"] == "01-register-the-part"
    assert {item.name for item in (step / "tests").iterdir()} == {
        "Dockerfile", "candidate.py", "registration_cases.py", "requirements.txt", "test.sh", "verify.py",
    }
    assert {item.name for item in (step / "solution").iterdir()} == {
        "coating", "coating_io.py", "coating_registration.py", "solve.sh",
    }
    assets = bundle / "environment/resources"
    assert json.loads((assets / "job.json").read_text())["part_mesh"]["triangles"]
    assert json.loads((assets / "scans.json").read_text())["captures"]
    assert (assets / "cell/arm.urdf").is_file()
    names = {item.name for item in assets.rglob("*") if item.is_file()}
    expected = {"README.md", "job.json", "scans.json", "ambiguous-job.json", "ambiguous-scans.json",
                "arm.urdf", "arm.srdf"}
    assert [item.name for item in steps] == [record["name"] for record in config["steps"]]
    if len(steps) > 1:
        expected |= {"motion-job.json", "motion-registration.json"}
    assert names == expected
    for level, item in enumerate(steps[1:], start=2):
        assert (item / "tests/offline_cases.py").is_file()
        assert (item / "tests/public_cell/arm.urdf").read_bytes() == (assets / "cell/arm.urdf").read_bytes()
        assert (item / "solution/coating_planner.py").is_file()
        assert (item / "tests/live_cases.py").exists() is (level == 4)
        assert (item / "solution/coating_supervisor.py").exists() is (level == 4)
        assert not (item / "tests/test_native_arm.py").exists()
