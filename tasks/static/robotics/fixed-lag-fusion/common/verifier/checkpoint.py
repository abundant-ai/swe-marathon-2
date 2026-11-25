"""Execute private fixed-lag fusion missions in a separate verifier process."""

import argparse
import json
import os
import pwd
import shutil
import signal
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from probes import calibration_cases, durable_cases, fusion_cases, smoother_cases
from reference import Json

WEIGHTS = {"window": 1, "calibration": 1, "fusion": 2, "revision": 3, "network": 8}
POSITIVE = {
    "window": (
        "correlated_exact_marginal_after_eviction",
        "multi_tick_prediction_without_observations",
    ),
    "calibration": (
        "robust_wheel_calibration_signed_grid_offsets",
        "surveyed_range_bias_resists_outliers",
    ),
    "fusion": (
        "commissioned_sensor_units_and_covariance_on_mocap",
        "independent_fit_flows_into_heldout_replay",
    ),
    "revision": (
        "accept_and_restart_exact_latest_reply",
        "revision_downdate_and_expired_information_conservation",
    ),
    "network": (
        "measured_room_path_recommissioned",
        "swapped_radios_after_restart",
        "recover_from_non_line_of_sight_ranges",
        "share_binding_across_calibration_drives",
    ),
}


def read_regular(path: Path) -> bytes | None:
    """Read a bounded regular result without following a candidate-created link."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
            return None
        return path.read_bytes()
    except OSError:
        return None


@dataclass(frozen=True)
class Candidate:
    """Execute the staged CLI with no inherited secrets or private write access."""

    app: Path
    scratch: Path

    def __call__(
        self,
        command: str,
        spec: Json,
        *,
        state: Path | None = None,
        invalid: bool = False,
        lost_reply: bool = False,
    ) -> Json:
        """Run an independent request, simulating failed publication when specified."""
        with tempfile.TemporaryDirectory(
            prefix="request-", dir=self.scratch
        ) as directory:
            folder = Path(directory)
            folder.chmod(0o755)
            request = folder / "input.json"
            request.write_text(json.dumps(spec, allow_nan=False), encoding="utf-8")
            request.chmod(0o644)
            destination = folder / "reports"
            destination.mkdir()
            destination.chmod(0o777)
            output = destination / "report.json"
            marker = b'{"previous":true}\n'
            before = read_regular(state) if state is not None and invalid else None
            if invalid:
                output.write_bytes(marker)
                output.chmod(0o666)
            if lost_reply:
                output.mkdir()
            args = [
                sys.executable,
                "-B",
                "-m",
                "lagfusion",
                command,
                "--spec",
                str(request),
                "--output",
                str(output),
            ]
            if state is not None:
                args.extend(("--state", str(state)))
            credentials = {}
            if os.geteuid() == 0:
                user = pwd.getpwnam("candidate")
                credentials = {
                    "user": user.pw_uid,
                    "group": user.pw_gid,
                    "extra_groups": [],
                }
            env = {
                "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin",
                "HOME": str(destination),
                "TMPDIR": str(destination),
                "LANG": "C.UTF-8",
                "OPENBLAS_NUM_THREADS": "1",
                "OMP_NUM_THREADS": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            with subprocess.Popen(
                args,
                cwd=self.app,
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                **credentials,
            ) as process:
                try:
                    code = process.wait(timeout=25)
                except subprocess.TimeoutExpired:
                    code = 124
                finally:
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    process.wait(timeout=3)
            if lost_reply:
                return {"nonzero": code not in (0, 124)}
            data = read_regular(output)
            if invalid:
                unchanged = state is None or before == read_regular(state)
                return {"atomic": code not in (0, 124) and data == marker and unchanged}
            if code or data is None:
                return {}
            try:
                report = json.loads(data)
            except (UnicodeError, ValueError):
                return {}
            return report if isinstance(report, dict) else {}


def stage(source: Path, workspace: Path) -> bool:
    """Admit a regular bounded application artifact without exposing authoring files."""
    workspace.mkdir()
    if not source.is_dir() or source.is_symlink():
        return False
    for index, path in enumerate(source.rglob("*")):
        if index > 1024 or path.is_symlink() or not (path.is_dir() or path.is_file()):
            return False
        if path.is_file() and path.stat().st_size > 4_000_000:
            return False
    shutil.copytree(
        source, workspace / "lagfusion", ignore=shutil.ignore_patterns("__pycache__")
    )
    for path in workspace.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    return True


def verify(stage_number: int, artifact: Path, dataset: Path) -> Json:
    """Run cumulative mission groups and compute fixed-denominator evidence."""
    with tempfile.TemporaryDirectory(prefix="lagfusion-evaluation-") as temporary:
        root = Path(temporary)
        root.chmod(0o755)
        app = root / "app"
        portable = stage(artifact, app)
        run = Candidate(app, root)
        groups = {"window": smoother_cases(run)}
        if stage_number >= 2:
            groups["calibration"] = calibration_cases(run)
        if stage_number >= 3:
            groups["fusion"] = fusion_cases(run, dataset)
        if stage_number >= 4:
            journal = root / "state"
            journal.mkdir()
            journal.chmod(0o777)
            groups["revision"] = durable_cases(run, journal)
        if stage_number >= 5:
            from network_probes import network_cases

            groups["network"] = network_cases(run, dataset)
        if stage_number >= 6:
            from integrity_probes import integrity_cases

            integrity_state = root / "integrity"
            integrity_state.mkdir(mode=0o777)
            integrity_state.chmod(0o777)
            integrity = integrity_cases(run, integrity_state, dataset)
        if stage_number >= 7:
            from vision_probes import vision_cases

            vision_manifest = root / "vision"
            vision_manifest.mkdir(mode=0o755)
            vision, vision_evidence = vision_cases(app, vision_manifest)
    checks = {
        family: {name: bool(passed) for name, passed in group.items()}
        for family, group in groups.items()
    }
    scores = {
        family: sum(group.values()) / len(group)
        if portable and any(group[key] for key in POSITIVE[family])
        else 0.0
        for family, group in checks.items()
    }
    reward = sum(scores[key] * WEIGHTS[key] for key in scores) / sum(
        WEIGHTS[key] for key in scores
    )
    if stage_number >= 6:
        checks["integrity"] = integrity
        scores["integrity"] = (
            sum(integrity.values()) / len(integrity) if portable else 0.0
        )
        reward = 0.3 * reward + 0.7 * scores["integrity"]
    if stage_number >= 7:
        checks["vision"] = vision
        scores["vision"] = (
            sum(all(case.values()) for case in vision.values()) / len(vision)
            if portable
            else 0.0
        )
        reward = 0.2 * reward + 0.8 * scores["vision"]
    report = {
        "stage": stage_number,
        "groups": checks,
        "component_scores": scores,
        "reward": reward,
    }
    if stage_number >= 7:
        report["vision_observations"] = vision_evidence
    return report


def main() -> None:
    """Publish fresh evidence and the Harbor reward only after evaluation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=int, choices=range(1, 8), required=True)
    parser.add_argument("--artifact", type=Path, default=Path("/app/lagfusion"))
    parser.add_argument("--logs", type=Path, default=Path("/logs/verifier"))
    parser.add_argument(
        "--dataset", type=Path, default=Path(__file__).with_name("room1_xy.csv")
    )
    args = parser.parse_args()
    args.logs.mkdir(parents=True, exist_ok=True)
    args.logs.chmod(0o700)
    reward_path = args.logs / "reward.json"
    reward_path.unlink(missing_ok=True)
    report = verify(args.stage, args.artifact, args.dataset)
    (args.logs / "checkpoint.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    reward_path.write_text(
        json.dumps({"reward": report["reward"]}) + "\n", encoding="utf-8"
    )
