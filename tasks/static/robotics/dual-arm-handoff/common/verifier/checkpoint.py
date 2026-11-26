"""Run protected, process-isolated checkpoint probes and publish reward evidence."""

import argparse
import json
import os
import pwd
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from probes import checks

PACKAGE = "dual_arm"
POSITIVE_GRASP_CHECKS = (
    "native_relocalize_giver_grasp",
    "native_relocalize_receiver_grasp",
)
GRASP_CHECKS = (*POSITIVE_GRASP_CHECKS, "native_hold_unconfirmed_grasp")


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
                sys.executable,
                "-B",
                "-m",
                PACKAGE,
                command,
                "--spec",
                str(request),
                "--output",
                str(output),
            ]
            if state is not None:
                args.extend(("--state", str(state)))
            permissions = {}
            if os.geteuid() == 0:
                candidate = pwd.getpwnam("candidate")
                permissions = {
                    "user": candidate.pw_uid,
                    "group": candidate.pw_gid,
                    "extra_groups": [],
                }
            environment = {
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "HOME": str(results),
                "TMPDIR": str(results),
                "LANG": "C.UTF-8",
                "MUJOCO_GL": "disable",
                "OPENBLAS_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
            }
            with subprocess.Popen(
                args,
                cwd=self.app,
                env=environment,
                start_new_session=True,
                stderr=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
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
            if (
                output.is_symlink()
                or not output.is_file()
                or output.stat().st_size > 4_000_000
            ):
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
        if (
            index > 1024
            or entry.is_symlink()
            or not (entry.is_file() or entry.is_dir())
        ):
            return False
        if entry.is_file():
            bytes_total += entry.stat().st_size
            if bytes_total > 12_000_000:
                return False
    shutil.copytree(
        artifact, app / PACKAGE, ignore=shutil.ignore_patterns("__pycache__")
    )
    for entry in app.rglob("*"):
        entry.chmod(0o755 if entry.is_dir() else 0o644)
    return True


def grasp_credit(grasp: Mapping[str, bool]) -> float:
    """Score the three Stage 8 missions once an actual delivery succeeds.

    Args:
        grasp: Pass flags keyed by the registered grasp recovery scenarios.

    Returns:
        Fraction passed, or zero when neither positive mission delivered.
    """
    registered = [grasp[name] for name in GRASP_CHECKS]
    if not any(grasp[name] for name in POSITIVE_GRASP_CHECKS):
        return 0.0
    return sum(registered) / len(GRASP_CHECKS)


def grade(
    artifact: Path, level: int, robot_asset: Path, *, grasp_only: bool = False
) -> dict[str, object]:
    """Score the checkpoint's candidate behavior in its isolated process area.

    Args:
        artifact: Submitted dual_arm Python package directory.
        level: Configured checkpoint number from one through eight.
        robot_asset: Verifier's trusted collision-only UR5e asset.
        grasp_only: At Stage 8, execute only the new recovery missions.

    Returns:
        Checkpoint number, individual pass flags, and normalized reward.
        Stage 8 reports measurements from the native grasp recovery missions.
        A missing or unusable submission earns zero.
    """
    if grasp_only and level != 8:
        raise ValueError("grasp-only grading requires stage 8")
    retained_level = 0 if grasp_only else min(level, 7)
    grasp = {}
    observations: dict[str, object] = {}
    with tempfile.TemporaryDirectory(prefix="trusted-robotics-") as location:
        directory = Path(location)
        directory.chmod(0o755)
        app = directory / "app"
        app.mkdir(mode=0o755)
        scratch = directory / "scratch"
        scratch.mkdir(mode=0o755)
        if not stage(artifact, app):
            return {"stage": level, "checks": {}, "reward": 0.0}
        runner = Runner(app, scratch)
        evidence = checks(runner, min(retained_level, 4)) if retained_level else {}
        if level >= 5:
            xml = robot_asset.read_text(encoding="utf-8")
        if retained_level >= 5:
            from commission_native_checks import commission_native_checks

            evidence.update(
                {
                    "survey_" + key: value
                    for key, value in commission_native_checks(runner, xml).items()
                }
            )
        if level >= 6:
            from native_scenarios import withholding

            # Stages 7 and 8 read the staging cell from its sheets.
            drawn = withholding(runner)
        if retained_level >= 6:
            from native_plan_checks import native_plan_checks

            evidence.update(
                {
                    "synth_" + key: value
                    for key, value in native_plan_checks(
                        drawn, xml, drawn=retained_level >= 7
                    ).items()
                }
            )
        if retained_level >= 7:
            from native_plan_checks import native_dispatch_checks

            journal = directory / "native_state"
            journal.mkdir()
            journal.chmod(0o777)
            evidence.update(
                {
                    "live_" + key: value
                    for key, value in native_dispatch_checks(
                        drawn, journal, xml
                    ).items()
                }
            )
        if level == 8:
            from grasp_recovery_checks import grasp_recovery_checks

            journal = directory / "grasp_state"
            journal.mkdir()
            journal.chmod(0o777)
            grasp = grasp_recovery_checks(
                drawn, journal, xml, observations=observations
            )
    grasp_evidence = {"grasp_" + key: value for key, value in grasp.items()}
    if grasp_only:
        return {
            "stage": level,
            "checks": grasp_evidence,
            "reward": grasp_credit(grasp),
            "observations": observations,
        }
    first_four = {
        key: flag
        for key, flag in evidence.items()
        if not key.startswith(("survey_", "synth_", "live_"))
    }
    passed = sum(bool(item) for item in first_four.values())
    reward = passed / len(first_four) if first_four and passed else 0.0
    if level >= 3:
        terminal = {
            key: flag for key, flag in first_four.items() if key.startswith("dispatch_")
        }
        earlier = [
            flag for key, flag in first_four.items() if not key.startswith("dispatch_")
        ]
        positive = terminal.get("dispatch_lost_reply") or terminal.get(
            "dispatch_interrupted_motion"
        )
        reward = 0.25 * sum(earlier) / len(earlier) + (
            0.75 * sum(terminal.values()) / len(terminal) if positive else 0.0
        )
    if level >= 4:
        scenarios = {
            key: flag
            for key, flag in first_four.items()
            if key.startswith("contingency_")
        }
        retained = [flag for key, flag in first_four.items() if key not in scenarios]
        ready = any(
            flag
            for key, flag in scenarios.items()
            if key.startswith("contingency_ready_")
        )
        reward = 0.2 * sum(retained) / len(retained) + (
            0.8 * sum(scenarios.values()) / len(scenarios) if ready else 0.0
        )
    fit = {key: flag for key, flag in evidence.items() if key.startswith("survey_")}
    synthesis = {
        key: flag for key, flag in evidence.items() if key.startswith("synth_")
    }
    native = {key: flag for key, flag in evidence.items() if key.startswith("live_")}
    fraction = lambda group: sum(group.values()) / len(group) if group else 0.0
    fit_fraction = (
        fraction(fit)
        if any(
            v for k, v in fit.items() if "malformed" not in k and "abstention" not in k
        )
        else 0.0
    )
    synthesis_fraction = (
        fraction(synthesis)
        if any(
            v
            for k, v in synthesis.items()
            if k.startswith("synth_native_") and "block_outside" not in k
        )
        else 0.0
    )
    if level == 5:
        reward = 0.25 * reward + 0.75 * fit_fraction
    if level == 6:
        reward = 0.15 * reward + 0.22 * fit_fraction + 0.63 * synthesis_fraction
    if retained_level == 7:
        live_positive = any(
            flag
            for name, flag in native.items()
            if name != "live_native_reject_forged_payload_owner"
        )
        reward = (
            0.12 * reward
            + 0.12 * fit_fraction
            + 0.21 * synthesis_fraction
            + (0.55 * fraction(native) if live_positive else 0.0)
        )
    if level == 8:
        reward = 0.20 * reward + 0.80 * grasp_credit(grasp)
        evidence.update(grasp_evidence)
    report: dict[str, object] = {"stage": level, "checks": evidence, "reward": reward}
    if level == 8:
        report["observations"] = observations
    return report


def main() -> None:
    """Run the verifier on a staged submission and write logs for the runner."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=int, choices=range(1, 9), required=True)
    parser.add_argument(
        "--grasp-only",
        action="store_true",
        help="run only the Stage 8 grasp recovery missions",
    )
    parser.add_argument("--artifact", type=Path, default=Path("/app") / PACKAGE)
    parser.add_argument("--logs", type=Path, default=Path("/logs/verifier"))
    parser.add_argument(
        "--robot-model",
        type=Path,
        default=Path(__file__).with_name("ur5e-headless.xml"),
    )
    args = parser.parse_args()
    if args.grasp_only and args.stage != 8:
        parser.error("--grasp-only requires --stage 8")
    args.logs.mkdir(parents=True, exist_ok=True)
    args.logs.chmod(0o700)
    reward = args.logs / "reward.txt"
    reward.unlink(missing_ok=True)
    report = grade(
        args.artifact, args.stage, args.robot_model, grasp_only=args.grasp_only
    )
    (args.logs / "checkpoint.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    reward.write_text(f"{report['reward']:.12g}\n", encoding="utf-8")
