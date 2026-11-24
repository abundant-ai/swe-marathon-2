"""Run protected, process-isolated checkpoint probes and publish reward evidence."""

from dataclasses import dataclass
import argparse
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import subprocess
import sys
import tempfile

from probes import checks


PACKAGE = "control_recovery"


@dataclass(frozen=True)
class Runner:
    """Give the candidate one request and a private writable response directory."""

    app: Path
    scratch: Path

    def __call__(self, command, spec, *, state=None, invalid=False, lost_reply=False):
        with tempfile.TemporaryDirectory(dir=self.scratch) as name:
            parent = Path(name)
            parent.chmod(0o755)
            request = parent / "request.json"
            request.write_text(json.dumps(spec, allow_nan=False), encoding="utf-8")
            request.chmod(0o644)
            results = parent / "output"
            results.mkdir()
            results.chmod(0o777)
            output = results / "result.json"
            sentinel = b'{"existing":true}\n'
            if lost_reply:
                output.mkdir()
            elif invalid:
                output.write_bytes(sentinel)
                output.chmod(0o666)
            args = [
                sys.executable, "-B", "-m", PACKAGE, command,
                "--spec", str(request), "--output", str(output),
            ]
            if state is not None:
                args.extend(("--state", str(state)))
            permissions = {}
            if os.geteuid() == 0:
                candidate = pwd.getpwnam("candidate")
                permissions = {"user": candidate.pw_uid, "group": candidate.pw_gid, "extra_groups": []}
            environment = {
                "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(results),
                "TMPDIR": str(results), "LANG": "C.UTF-8", "MUJOCO_GL": "disable",
                "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
            }
            with subprocess.Popen(
                args, cwd=self.app, env=environment, start_new_session=True,
                stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
                **permissions,
            ) as process:
                try:
                    status = process.wait(timeout=12)
                except subprocess.TimeoutExpired:
                    status = 124
                finally:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=3)
            if lost_reply:
                return status not in (0, 124) and output.is_dir()
            if output.is_symlink() or not output.is_file() or output.stat().st_size > 4_000_000:
                return False if invalid else None
            if invalid:
                return status not in (0, 124) and output.read_bytes() == sentinel
            if status != 0:
                return None
            try:
                result = json.loads(output.read_text(encoding="utf-8"))
            except (ValueError, UnicodeError):
                return None
            return result if isinstance(result, dict) else None


def stage(artifact: Path, app: Path) -> bool:
    """Copy a bounded regular-file tree into the verifier's unprivileged process area."""
    if artifact.is_symlink() or not artifact.is_dir():
        return False
    bytes_total = 0
    for index, entry in enumerate(artifact.rglob("*")):
        if index > 1024 or entry.is_symlink() or not (entry.is_file() or entry.is_dir()):
            return False
        if entry.is_file():
            bytes_total += entry.stat().st_size
            if bytes_total > 12_000_000:
                return False
    shutil.copytree(artifact, app / PACKAGE, ignore=shutil.ignore_patterns("__pycache__"))
    for entry in app.rglob("*"):
        entry.chmod(0o755 if entry.is_dir() else 0o644)
    return True


def grade(artifact, level):
    """Score named independent behaviors, with zero credit for a missing artifact."""
    with tempfile.TemporaryDirectory(prefix="trusted-robotics-") as location:
        directory = Path(location)
        directory.chmod(0o755)
        app = directory / "app"
        app.mkdir(mode=0o755)
        scratch = directory / "scratch"
        scratch.mkdir(mode=0o755)
        if not stage(artifact, app):
            return {"stage": level, "checks": {}, "reward": 0.0}
        run = Runner(app, scratch)
        if level >= 4:
            from handover_checks import checks_handover

            retained = checks(run, 3)
            extension = checks_handover(run)
            old_reward = sum(retained.values()) / len(retained)
            has_positive = any(passed for name, passed in extension.items()
                               if not name.startswith(("reject_", "blocked_")))
            new_reward = sum(extension.values()) / len(extension) if has_positive else 0.0
            report = {"stage": level, "checks": {"retained": retained, "handover": extension},
                      "component_scores": {"retained": old_reward, "handover": new_reward},
                      "reward": 0.35 * old_reward + 0.65 * new_reward}
            if level == 5:
                from servo_checks import checks_servo

                missions, observations = checks_servo(app, scratch)
                criteria = {"lease_and_maintenance": 0.17, "live_effort": 0.10,
                            "trajectory_and_settling": 0.69, "cycle_deadline": 0.04}
                control_scores = [
                    sum(criteria[key] for key, passed in outcomes.items() if passed)
                    for name, outcomes in missions.items() if name != "input"
                ]
                control = sum(control_scores) / len(control_scores)
                if any(control_scores) and all(missions["input"].values()):
                    control = 0.97 * control + 0.03
                else:
                    control *= 0.97
                report["checks"]["servo"] = missions
                report["servo_observations"] = observations
                report["component_scores"]["servo"] = control
                report["reward"] = 0.2 * report["reward"] + 0.8 * control
            return report
        evidence = checks(run, level)
    passed = sum(bool(item) for item in evidence.values())
    reward = passed / len(evidence) if evidence and passed else 0.0
    return {"stage": level, "checks": evidence, "reward": reward}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=int, choices=(1, 2, 3, 4, 5), required=True)
    parser.add_argument("--artifact", type=Path, default=Path("/app") / PACKAGE)
    parser.add_argument("--logs", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    args.logs.mkdir(parents=True, exist_ok=True)
    args.logs.chmod(0o700)
    reward = args.logs / "reward.txt"
    reward.unlink(missing_ok=True)
    report = grade(args.artifact, args.stage)
    (args.logs / "checkpoint.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    reward.write_text(f"{report['reward']:.12g}\n", encoding="utf-8")
