"""Grade reference tracking and coupled actuator authority on native Jazzy."""

import argparse
import json
import os
from pathlib import Path
import pwd
import subprocess
import sys
import tempfile

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
from checkpoint import stage
from verify_native import build
from verify_restart import evaluate as evaluate_retained


CASES = (("right_feedback_restart_under_asymmetric_load", False),
         ("mirrored_load_and_changed_coupling", True))


def case(installation, hardware, directory, mirrored):
    args = [sys.executable, "-B", str(TESTS / "lift_checks.py"), "witness",
            "--install", str(installation), "--hardware", str(hardware), "--output", str(directory)]
    if mirrored:
        args.append("--mirrored")
    trial = subprocess.run(args, text=True, capture_output=True, timeout=28)
    if trial.returncode:
        diagnostic = {"runner": (trial.stderr or trial.stdout)[-2000:]}
        for name in ("manager", "client"):
            log = directory / "private" / f"{name}.log"
            if log.is_file():
                diagnostic[name] = log.read_text(errors="replace")[-2700:]
        return False, diagnostic
    report = json.loads((directory / "private/report.json").read_text())
    checks = report["checks"]
    return all(checks.values()), report


def evaluate(artifact, retain=True):
    retained = evaluate_retained(artifact) if retain else {"reward": 0.0, "checks": {}}
    evidence, observations = {}, {}
    user = {}
    if os.geteuid() == 0:
        account = pwd.getpwnam("candidate")
        user = {"user": account.pw_uid, "group": account.pw_gid, "extra_groups": []}
    with tempfile.TemporaryDirectory(prefix="paired-lift-") as temporary:
        root = Path(temporary)
        root.chmod(0o711)
        if not stage(artifact, root / "upload"):
            return finish(retained, evidence, {"build_error": "Missing control_recovery artifact."})
        package = root / "upload/control_recovery/native/coupled_handover"
        if not (package / "CMakeLists.txt").is_file():
            return finish(retained, evidence, {"build_error": "Missing coupled_handover package."})
        build_path = root / "build"
        build_path.mkdir()
        try:
            installation, failure = build(package, build_path, user)
        except (OSError, subprocess.TimeoutExpired) as error:
            installation, failure = None, str(error)
        if failure or installation is None:
            return finish(retained, evidence, {"build_error": failure})
        fixture = os.environ.get("ROS_LIFT_DEVICE_PREFIX")
        if fixture is None:
            device_path = root / "fixture"
            device_path.mkdir()
            hardware, failure = build(TESTS / "lift_device", device_path, {})
            if failure:
                raise RuntimeError(f"trusted fixture build failed: {failure}")
        else:
            hardware = Path(fixture)
        for name, mirrored in CASES:
            try:
                evidence[name], observations[name] = case(
                    installation, hardware, root / name, mirrored)
            except (OSError, ValueError, subprocess.TimeoutExpired) as error:
                evidence[name], observations[name] = False, {"runner": str(error)}
    return finish(retained, evidence, observations)


def finish(retained, evidence, observations):
    coupled = sum(evidence.values()) / len(CASES)
    return {"stage": 8, "checks": {"retained": retained["checks"], "coupled": evidence},
            "coupled_observations": observations,
            "component_scores": {"retained": retained["reward"], "coupled": coupled},
            "reward": round(.20 * retained["reward"] + .80 * coupled, 12)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifact", type=Path, default=Path("/app/control_recovery"))
    parser.add_argument("--logs", type=Path, default=Path("/logs/verifier"))
    parser.add_argument("--lift-only", action="store_true", help="local paired-drive diagnostic")
    args = parser.parse_args()
    args.logs.mkdir(parents=True, exist_ok=True)
    args.logs.chmod(0o700)
    ros = Path(os.environ.get("ROS_JAZZY_PREFIX", "/opt/ros/jazzy"))
    sys.path.append(str(ros / "lib/python3.12/site-packages"))
    report = evaluate(args.artifact, retain=not args.lift_only)
    (args.logs / "checkpoint.json").write_text(json.dumps(report, indent=2) + "\n")
    (args.logs / "reward.txt").write_text(f"{report['reward']:.12g}\n")


if __name__ == "__main__":
    main()
