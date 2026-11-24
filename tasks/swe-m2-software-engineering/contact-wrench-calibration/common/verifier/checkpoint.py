"""Execute private fixed-lag fusion missions in a separate verifier process."""

import argparse
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

from probes import checks
from typing import Any

Json = dict[str, Any]


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

    def __call__(self, command: str, spec: Json, *, state: Path | None = None,
                 invalid: bool = False, lost_reply: bool = False) -> Json:
        """Run an independent request, simulating failed publication when specified."""
        with tempfile.TemporaryDirectory(prefix="request-", dir=self.scratch) as directory:
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
            args = [sys.executable, "-B", "-m", "wrenchlab", command, "--spec", str(request), "--output", str(output)]
            if state is not None:
                args.extend(("--state", str(state)))
            credentials = {}
            if os.geteuid() == 0:
                user = pwd.getpwnam("candidate")
                credentials = {"user": user.pw_uid, "group": user.pw_gid, "extra_groups": []}
            env = {"PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin", "HOME": str(destination),
                   "TMPDIR": str(destination), "LANG": "C.UTF-8", "OPENBLAS_NUM_THREADS": "1",
                   "OMP_NUM_THREADS": "1", "MUJOCO_GL": "disable", "PYTHONDONTWRITEBYTECODE": "1"}
            with subprocess.Popen(args, cwd=self.app, env=env, stdin=subprocess.DEVNULL,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                  start_new_session=True, **credentials) as process:
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
    shutil.copytree(source, workspace / "wrenchlab", ignore=shutil.ignore_patterns("__pycache__"))
    for path in workspace.rglob("*"):
        path.chmod(0o755 if path.is_dir() else 0o644)
    return True


def verify(stage_number: int, artifact: Path, dataset: Path) -> Json:
    """Run cumulative mission groups and compute fixed-denominator evidence."""
    with tempfile.TemporaryDirectory(prefix="wrenchlab-evaluation-") as temporary:
        root = Path(temporary)
        root.chmod(0o755)
        app = root / "app"
        portable = stage(artifact, app)
        run = Candidate(app, root)
        if not portable:
            return {"stage": stage_number, "checks": {}, "reward": 0.0}
        observed = {name: bool(passed) for name, passed in checks(run, stage_number, dataset).items()}
    return {"stage": stage_number, "checks": observed, "reward": sum(observed.values()) / len(observed)}


def main() -> None:
    """Publish fresh evidence and the Harbor reward only after evaluation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=int, choices=range(1, 4), required=True)
    parser.add_argument("--artifact", type=Path, default=Path("/app/wrenchlab"))
    parser.add_argument("--logs", type=Path, default=Path("/logs/verifier"))
    parser.add_argument("--dataset", type=Path, default=Path(__file__).with_name("fixture"))
    args = parser.parse_args()
    args.logs.mkdir(parents=True, exist_ok=True)
    args.logs.chmod(0o700)
    reward_path = args.logs / "reward.json"
    reward_path.unlink(missing_ok=True)
    report = verify(args.stage, args.artifact, args.dataset)
    (args.logs / "checkpoint.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    reward_path.write_text(json.dumps({"reward": report["reward"]}) + "\n", encoding="utf-8")
