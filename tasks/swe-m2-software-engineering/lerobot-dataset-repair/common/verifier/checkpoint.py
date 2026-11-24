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
        command = [sys.executable, "-B", "-m", "lerobot_repair", *map(str, args)]
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(self.home), "TMPDIR": str(self.home),
               "LANG": "C.UTF-8", "AV_LOG_FORCE_NOCOLOR": "1", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
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
    package = app / "lerobot_repair"
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
    asset = Path(__file__).with_name("so101-rows.parquet")
    with TemporaryDirectory(prefix="lerobot-checkpoint-") as temp:
        root = Path(temp)
        root.chmod(0o711)
        application = root / "app"
        workspace = root / "public"
        workspace.mkdir()
        workspace.chmod(0o1777)
        run = Run(application, workspace)
        evidence = verify(run, workspace, asset, min(milestone, 4)) if stage(
            options.app / "lerobot_repair", application) else {}
        if milestone >= 5 and evidence:
            from action_probes import action_cases
            evidence["actions"] = action_cases(run, workspace)
        if milestone >= 6 and evidence:
            from journal_probes import journal_cases
            evidence["journals"] = journal_cases(run, workspace)
    fractions = {key: sum(checks.values()) / len(checks) for key, checks in evidence.items()}
    if milestone >= 3:
        score = sum(fractions.get(key, 0.0) * weight for key, weight in (
            ("audit", 0.10), ("plan", 0.30), ("publish", 0.30), ("publish_shifted", 0.30)))
        if milestone >= 4:
            clocked = (fractions.get("clocked", 0) + fractions.get("clocked_restart", 0)) / 2
            score = 0.25 * score + 0.75 * clocked
        if milestone >= 5:
            score = .20*score + .80*fractions.get("actions", 0)
        if milestone >= 6:
            positive = any(passed for key,passed in evidence.get("journals",{}).items()
                           if key in ("recover_overlapping_chunks","reboot_before_takeover","mixed_global_shard"))
            score = .20*score + (.80*fractions.get("journals",0) if positive else 0.)
    else:
        score = sum(fractions.values()) / milestone
    if not evidence.get("audit", {}).get("exact_issues") and not evidence.get("plan", {}).get("verified_clips"):
        score = 0.0
    (options.logs / "reward.json").write_text(json.dumps({"reward": score}) + "\n")
    (options.logs / "checkpoint.json").write_text(json.dumps({"stage": milestone, "score": score,
          "groups": evidence, "fractions": fractions}, sort_keys=True, indent=2) + "\n")
    print(f"LeRobot stage {milestone} reward {score:.6f}")
