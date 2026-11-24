"""Run candidate commands in a separate verifier and record cumulative evidence."""

from argparse import ArgumentParser
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import pwd
import shutil
import signal
import subprocess
import sys

from probes import verify


class Run:
    """Invoke the candidate workspace under its own OS credentials."""

    def __init__(self, app: Path, home: Path):
        self.app = app
        self.home = home

    def __call__(self, *args: object) -> int:
        """Run the public CLI with time-limited subprocess isolation."""
        options = {}
        if os.geteuid() == 0:
            user = pwd.getpwnam("candidate")
            options.update(user=user.pw_uid, group=user.pw_gid, extra_groups=())
        command = [sys.executable, "-B", "-m", "rollout_qualification", *map(str, args)]
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(self.home), "TMPDIR": str(self.home),
               "LANG": "C.UTF-8", "MUJOCO_GL": "disable", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
        with subprocess.Popen(command, cwd=self.app, env=env, stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                              **options) as child:
            try:
                return child.wait(timeout=30)
            except subprocess.TimeoutExpired:
                return 124
            finally:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


def stage(source: Path, app: Path) -> bool:
    """Copy the declared submission artifact without following links or special paths."""
    if source.is_symlink() or not source.is_dir():
        return False
    package = app / "rollout_qualification"
    package.mkdir(parents=True)
    for index, item in enumerate(sorted(source.rglob("*"))):
        relative = item.relative_to(source)
        if index > 1000 or item.is_symlink() or not (item.is_file() or item.is_dir()):
            return False
        if "__pycache__" in relative.parts:
            continue
        target = package / relative
        if item.is_dir():
            target.mkdir()
        else:
            if item.stat().st_size > 5_000_000:
                return False
            shutil.copyfile(item, target)
            target.chmod(0o644)
    return True


def main(milestone: int) -> None:
    """Score native oracle-independent outcomes and save a machine-readable report."""
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=Path("/app"))
    parser.add_argument("--logs", type=Path, default=Path("/logs/verifier"))
    options = parser.parse_args()
    options.logs.mkdir(parents=True, exist_ok=True)
    options.logs.chmod(0o700)
    (options.logs / "reward.json").unlink(missing_ok=True)
    with TemporaryDirectory(prefix="rollout-qual-") as temp:
        root = Path(temp)
        root.chmod(0o711)
        application = root / "app"
        workspace = root / "public"
        workspace.mkdir()
        workspace.chmod(0o1777)
        evidence = verify(Run(application, workspace), workspace, milestone) if stage(
            options.app / "rollout_qualification", application) else {}
    fractions = {key: sum(checks.values()) / len(checks) for key, checks in evidence.items()}
    score = (sum(fractions.values()) / (milestone + (milestone == 3))) if fractions else 0.0
    if not evidence.get("inspect", {}).get("native_pair_index"):
        score = 0.0
    options.logs.mkdir(parents=True, exist_ok=True)
    (options.logs / "reward.json").write_text(json.dumps({"reward": score}) + "\n")
    (options.logs / "checkpoint.json").write_text(json.dumps({"stage": milestone, "score": score,
          "groups": evidence, "fractions": fractions}, sort_keys=True, indent=2) + "\n")
    print(f"Robomimic Rollout stage {milestone} reward {score:.6f}")
