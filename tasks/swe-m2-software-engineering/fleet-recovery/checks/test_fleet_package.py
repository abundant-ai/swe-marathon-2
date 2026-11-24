"""Keep the Oddish build context limited to declared runtime files."""

import os
from hashlib import sha256
from pathlib import Path
import subprocess
import sys
import tomllib


TASK = Path(__file__).resolve().parents[1]


def test_package_keeps_reference_and_verifier_out_of_agent_environment(tmp_path):
    bundle = tmp_path / "fleet-bundle"
    subprocess.run(
        [sys.executable, str(TASK / "scripts" / "package_task.py"), "--output", str(bundle)],
        check=True,
        capture_output=True,
    )

    config = tomllib.loads((bundle / "task.toml").read_text())
    assert config["verifier"]["environment_mode"] == "separate"
    expected = {
        "task.toml",
        "environment/.dockerignore",
        "environment/Dockerfile",
        "environment/example/PROVENANCE.md",
        "environment/example/site.json",
    }
    for step in config["steps"]:
        stage = bundle / "steps" / step["name"]
        expected.update(
            f"steps/{step['name']}/{name}"
            for name in (
                "instruction.md",
                "solution/solve.sh",
                "solution/fleet_recovery/__init__.py",
                "solution/fleet_recovery/__main__.py",
                "tests/Dockerfile",
                "tests/fleet_grader.py",
                "tests/fleet_world.py",
                "tests/scenarios.py",
                "tests/test.sh",
                "tests/verify.py",
            )
        )
        assert os.access(stage / "tests" / "test.sh", os.X_OK)
        assert os.access(stage / "solution" / "solve.sh", os.X_OK)

    expected.update({
        "steps/04-schedule-elevators/solution/fleet_recovery/elevators.py",
        "steps/04-schedule-elevators/tests/elevator_checks.py",
        "steps/05-reserve-lift-corridors/solution/fleet_recovery/elevators.py",
        "steps/05-reserve-lift-corridors/tests/elevator_checks.py",
        "steps/05-reserve-lift-corridors/solution/fleet_recovery/corridors.py",
        "steps/05-reserve-lift-corridors/tests/corridor_checks.py",
        "steps/06-route-energy-constrained-fleet/solution/fleet_recovery/elevators.py",
        "steps/06-route-energy-constrained-fleet/tests/elevator_checks.py",
        "steps/06-route-energy-constrained-fleet/solution/fleet_recovery/corridors.py",
        "steps/06-route-energy-constrained-fleet/tests/corridor_checks.py",
        "steps/06-route-energy-constrained-fleet/solution/fleet_recovery/network.py",
        "steps/06-route-energy-constrained-fleet/tests/network_checks.py",
    })
    native = "steps/07-reconcile-native-traffic"
    competition = "steps/08-negotiate-competing-traffic"
    contingent = "steps/09-commit-contingent-traffic"
    for step in (native, competition, contingent):
        expected.update(f"{step}/{path}" for path in (
            "solution/fleet_recovery/elevators.py", "solution/fleet_recovery/corridors.py",
            "solution/fleet_recovery/network.py", "solution/fleet_recovery/rmf_handover.py",
            "tests/elevator_checks.py", "tests/corridor_checks.py", "tests/network_checks.py",
            "tests/rmf_checks.py", "tests/rmf_native.cpp", "tests/build_rmf_native.sh", "tests/traffic_smoke.cpp",
        ))
    for step in (competition, contingent):
        expected.update(f"{step}/{path}" for path in (
            "solution/fleet_recovery/competition.py", "solution/fleet_recovery/competition_native.cpp",
            "tests/competition_checks.py",
        ))
    expected.update(f"{contingent}/{path}" for path in (
        "solution/fleet_recovery/contingent.py", "solution/fleet_recovery/contingent_native.cpp",
        "tests/contingent_checks.py",
    ))
    expected.update(f"environment/example/rmf/{name}" for name in (
        "rmf_native.cpp", "build_rmf_native.sh", "README.md", "manifest.json", "observations.ndjson",
        "competition-site.json", "competition-open.json", "contingent-site.json", "contingent-open.json",
    ))
    for name in ("traffic.deb", "utils.deb", "libccd2.deb", "SHA256SUMS", "SOURCES.md"):
        expected.update({f"environment/native-rmf/{name}", f"{native}/tests/native-rmf/{name}",
                         f"{competition}/tests/native-rmf/{name}", f"{contingent}/tests/native-rmf/{name}"})
    source = bundle / "environment" / "native-rmf"
    for line in (source / "SHA256SUMS").read_text().splitlines():
        expected_digest, name = line.split()
        for assets in (source, bundle / native / "tests" / "native-rmf",
                       bundle / competition / "tests" / "native-rmf",
                       bundle / contingent / "tests" / "native-rmf"):
            assert sha256((assets / name).read_bytes()).hexdigest() == expected_digest
    assert {entry.relative_to(bundle).as_posix() for entry in bundle.rglob("*") if entry.is_file()} == expected
    subprocess.run(
        [sys.executable, "-B", "-c",
         "from rmf_checks import Scene\n"
         "for direction, kind in ((1, 'gap'), (-1, 'restart')):\n"
         "    scene = Scene(direction, kind)\n"
         "    assert scene.carrier(15.75) == tuple(scene.poses(scene.xmin)[-1][:2])\n"],
        cwd=bundle / native / "tests",
        check=True,
        capture_output=True,
    )
