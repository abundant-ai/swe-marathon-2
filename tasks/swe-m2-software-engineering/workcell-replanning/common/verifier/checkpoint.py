"""Grade the staged workcell CLI with a trusted, independent verifier."""

import argparse
from collections.abc import Callable
from dataclasses import dataclass
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import subprocess
import sys
import tempfile

from geometry import Json
from probes import recovery_checks, scene_checks, sweep_checks

GROUPS: tuple[tuple[str, int, Callable], ...] = (
    ("scene", 2, scene_checks),
    ("motion", 3, sweep_checks),
    ("recovery", 5, recovery_checks),
)
POSITIVE = {
    "scene": ("exact_revision_and_ownership", "remove_preserves_other_object"),
    "motion": ("valid_loaded_and_unloaded_controls", "continuous_arm_sweeps", "rotating_load_sweep"),
    "recovery": ("replan_thin_obstacle_loaded", "recover_from_measured_pose",
                 "replan_variant_under_same_revision", "reuse_safe_path_on_revision_advance"),
}


@dataclass(frozen=True)
class CLI:
    """Run submissions without grader credentials or a writable code directory."""

    app: Path
    scratch: Path

    def __call__(
        self, command: str, spec: Json, invalid: bool = False, *,
        state: Path | None = None, lose_output: bool = False,
    ) -> Json | bool:
        """Run one probe and read bounded JSON, or verify that an invalid input was rejected."""
        with tempfile.TemporaryDirectory(prefix="probe-", dir=self.scratch) as location:
            directory = Path(location)
            directory.chmod(0o755)
            input_path = directory / "request.json"
            input_path.write_text(json.dumps(spec), encoding="utf-8")
            input_path.chmod(0o644)
            destination = directory / "output"
            destination.mkdir(mode=0o777)
            destination.chmod(0o777)
            output = destination / "result.json"
            sentinel = b'{"previous":true}\n'
            if lose_output:
                output.mkdir()
            if invalid:
                output.write_bytes(sentinel)
                output.chmod(0o666)
            args = [sys.executable, "-B", "-m", "workcell", command, "--spec", str(input_path), "--output", str(output)]
            if state is not None:
                args.extend(("--state", str(state)))
            credentials = {}
            if os.geteuid() == 0:
                candidate = pwd.getpwnam("candidate")
                credentials = {"user": candidate.pw_uid, "group": candidate.pw_gid, "extra_groups": []}
            env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(destination), "TMPDIR": str(destination),
                   "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}
            with subprocess.Popen(args, cwd=self.app, env=env, start_new_session=True,
                                  stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.DEVNULL, **credentials) as child:
                try:
                    status = child.wait(timeout=22 if command == "recover" else 8)
                except subprocess.TimeoutExpired:
                    status = 124
                finally:
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    child.wait(timeout=3)
            if lose_output:
                return status not in (0, 124) and output.is_dir()
            if output.is_symlink() or not output.is_file() or output.stat().st_size > 512_000:
                return False if invalid else {}
            if invalid:
                return status != 0 and status != 124 and output.read_bytes() == sentinel
            if status != 0:
                return {}
            try:
                body = json.loads(output.read_text(encoding="utf-8"))
            except (UnicodeError, ValueError):
                return {}
            return body if isinstance(body, dict) else {}


def stage(source: Path, app: Path) -> bool:
    """Copy the declared portable artifact, rejecting special paths and oversized trees."""
    app.mkdir(mode=0o755)
    if not source.is_dir() or source.is_symlink():
        return False
    for index, item in enumerate(source.rglob("*")):
        if index > 1024 or item.is_symlink() or not (item.is_dir() or item.is_file()):
            return False
        if item.is_file() and item.stat().st_size > 2_000_000:
            return False
    shutil.copytree(source, app / "workcell", ignore=shutil.ignore_patterns("__pycache__"))
    for item in app.rglob("*"):
        item.chmod(0o755 if item.is_dir() else 0o644)
    return True


def grade(level: int, artifact: Path) -> Json:
    """Record cumulative evidence, fixed component fractions and checkpoint reward."""
    with tempfile.TemporaryDirectory(prefix="trusted-workcell-") as location:
        workspace = Path(location)
        workspace.chmod(0o755)
        app = workspace / "app"
        portable = stage(artifact, app)
        scratch = workspace / "scratch"
        scratch.mkdir(mode=0o755)
        run = CLI(app, scratch)
        if level >= 4:
            return grade_moving(level, portable, run)
        evidence = {name: probes(run) for name, _, probes in GROUPS[:level]}
    scores = {
        group: sum(values.values()) / len(values)
        if portable and any(values[flag] for flag in POSITIVE[group]) else 0.0
        for group, values in evidence.items()
    }
    reward = sum(weight * scores.get(name, 0.0) for name, weight, _ in GROUPS[:level]) / sum(
        weight for _, weight, _ in GROUPS[:level])
    return {"stage": level, "portable_artifact": portable, "checks": evidence,
            "component_scores": scores, "reward": reward}



def grade_moving(level: int, portable: bool, run: CLI) -> Json:
    """Report planner diagnostics or closed-loop completion at the late checkpoints."""
    from missions import missions
    from timed_probes import window_checks

    if not portable:
        evidence = {case["id"]: False for case in missions()}
    elif level == 4:
        evidence = window_checks(run)
    else:
        from dispatch_probes import dispatch_checks

        evidence = dispatch_checks(run)
    group = "timed_windows" if level == 4 else "closed_loop_missions"
    reward = sum(evidence.values()) / len(evidence)
    return {"stage": level, "portable_artifact": portable, "checks": {group: evidence},
            "component_scores": {group: reward}, "reward": reward}


def main() -> None:
    """Publish scoring evidence and a reward only after successful evaluation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=int, choices=(1, 2, 3, 4, 5), required=True)
    parser.add_argument("--artifact", type=Path, default=Path("/app/workcell"))
    parser.add_argument("--logs", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    args.logs.mkdir(parents=True, exist_ok=True)
    args.logs.chmod(0o700)
    reward = args.logs / "reward.txt"
    reward.unlink(missing_ok=True)
    report = grade(args.stage, args.artifact)
    (args.logs / "checkpoint.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    reward.write_text(f"{report['reward']:.12g}\n", encoding="utf-8")
