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
from time import monotonic

from probes import verify


def incident_fraction(checks: dict[str, bool]) -> float:
    """Prioritize reconstructed timelines and downstream transform decisions."""
    weights = {"wire_reconciliation_and_tight_causal_timeline": 28,
               "known_poses_and_inverse_with_correct_authority": 18,
               "time_and_dynamic_age_uncertainty": 14,
               "restart_before_first_new_transform": 16}
    if "overlapping_authorities_remain_ambiguous" in checks:
        weights["overlapping_authorities_remain_ambiguous"] = 6
    diagnostics = checks.keys() - weights.keys()
    return (sum(weight for name, weight in weights.items() if checks[name])
            + (100 - sum(weights.values())) * sum(checks[name] for name in diagnostics) / len(diagnostics)) / 100


class Run:
    """Invoke the candidate workspace under its own OS credentials."""

    def __init__(self, app: Path, home: Path):
        self.app = app
        self.home = home

    def options(self) -> dict:
        """Use the dedicated unprivileged verifier account in the task image."""
        if os.geteuid() == 0:
            user = pwd.getpwnam("candidate")
            return dict(user=user.pw_uid, group=user.pw_gid, extra_groups=())
        return {}

    def environment(self) -> dict:
        """Preserve only runtime-specific ROS, loopback and Python path configuration."""
        env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(self.home), "TMPDIR": str(self.home),
               "LANG": "C.UTF-8", "AV_LOG_FORCE_NOCOLOR": "1", "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
               "ROS_LOG_DIR": str(self.home / "candidate-ros-logs")}
        if "ROS_JAZZY_PREFIX" in os.environ:
            for key in ("ROS_JAZZY_PREFIX", "PYTHONPATH", "LD_LIBRARY_PATH", "AMENT_PREFIX_PATH",
                        "ROS_DOMAIN_ID", "ROS_AUTOMATIC_DISCOVERY_RANGE", "CYCLONEDDS_URI", "RMW_IMPLEMENTATION"):
                if key in os.environ:
                    env[key] = os.environ[key]
        return env

    def __call__(self, *args: object, memory_mib: int | None = None) -> int:
        """Run the public CLI with time-limited subprocess isolation."""
        command = [sys.executable, "-B", "-m", "bag_conformance", *map(str, args)]
        with subprocess.Popen(command, cwd=self.app, env=self.environment(), stdin=subprocess.DEVNULL,
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True,
                              **self.options()) as child:
            try:
                if memory_mib is None:
                    return child.wait(timeout=30)
                limit = monotonic() + 60
                status = Path(f"/proc/{child.pid}/status")
                while child.poll() is None and monotonic() < limit:
                    try:
                        rss = next((int(line.split()[1]) for line in status.read_text().splitlines()
                                    if line.startswith("VmHWM:")), 0)
                    except FileNotFoundError:
                        break
                    if rss > memory_mib * 1024:
                        return 125
                    try:
                        return child.wait(timeout=.015)
                    except subprocess.TimeoutExpired:
                        continue
                return child.wait(timeout=.05)
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
    package = app / "bag_conformance"
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
    with TemporaryDirectory(prefix="bag-conformance-") as temp:
        root = Path(temp)
        root.chmod(0o711)
        application = root / "app"
        workspace = root / "public"
        workspace.mkdir()
        workspace.chmod(0o1777)
        if milestone >= 6:
            os.environ["ROS_DOMAIN_ID"] = str(41 + os.getpid() % 100)
            os.environ["ROS_LOG_DIR"] = str(root / "trusted-ros-logs")
        run = Run(application, workspace)
        evidence = verify(run, workspace, milestone) if stage(options.app / "bag_conformance", application) else {}
        if evidence and milestone >= 4:
            from incident_probes import incident_probe

            evidence["incident"] = incident_probe(run, workspace / "incident", 0)
            evidence["incident_swapped"] = incident_probe(run, workspace / "incident-swapped", 7)
        if evidence and milestone >= 5:
            from service_probes import service_checks

            evidence["snapshots"] = service_checks(run, workspace)
        if evidence and milestone >= 6:
            from live_probes import live_checks

            evidence["live"] = live_checks(run, workspace)
    fractions = {key: sum(checks.values()) / len(checks) for key, checks in evidence.items()}
    if "incident" in evidence:
        for key in ("incident", "incident_swapped"):
            fractions[key] = incident_fraction(evidence[key])
    score = 0.0
    if evidence.get("index", {}).get("mixed_bag_exact_bytes_and_epochs"):
        if milestone >= 4:
            prior = sum(fractions[key] for key in ("index", "replay", "poses", "storage_swap")) / 4
            score = prior / 4 + (fractions["incident"] + fractions["incident_swapped"]) * 3 / 8
            if milestone >= 5:
                new = evidence["snapshots"]
                score = 0.2 * score + (0.8 * fractions["snapshots"] if new["pinned_history_and_restart"] else 0.0)
        else:
            score = sum(fractions.values()) / (milestone + (milestone == 3))
    if milestone >= 6 and evidence:
        score = .20 * score + .80 * fractions["live"]
    options.logs.mkdir(parents=True, exist_ok=True)
    (options.logs / "reward.json").write_text(json.dumps({"reward": score}) + "\n")
    (options.logs / "checkpoint.json").write_text(json.dumps({"stage": milestone, "score": score,
          "groups": evidence, "fractions": fractions}, sort_keys=True, indent=2) + "\n")
    print(f"Multi-bag Replay stage {milestone} reward {score:.6f}")
