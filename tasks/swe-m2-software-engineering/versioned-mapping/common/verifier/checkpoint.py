"""Run the accumulated candidate CLI in an isolated checkpoint."""

import argparse
import json
import os
from pathlib import Path
import pwd
import shutil
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory

from probes import GROUPS


class Candidate:
    """Invoke the implementation without verifier permissions or import paths."""

    def __init__(self, workspace: Path, scratch: Path):
        self.workspace = workspace
        self.scratch = scratch
        self.user = pwd.getpwnam("candidate") if os.geteuid() == 0 else None

    def __call__(self, *args):
        command = (sys.executable, "-B", "-m", "versioned_mapping", *map(str, args))
        options = {}
        if self.user:
            options = dict(user=self.user.pw_uid, group=self.user.pw_gid, extra_groups=())
        with TemporaryDirectory(dir=self.scratch) as temporary:
            logs = Path(temporary)
            # Capture output in inherited descriptors. The candidate cannot access
            # the verifier's directories, inherited environment or other results.
            with (logs / "stdout").open("w+b") as stdout:
                with subprocess.Popen(
                    command, cwd=self.workspace,
                    env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": str(self.workspace), "LANG": "C.UTF-8"},
                    stdin=subprocess.DEVNULL, stdout=stdout, stderr=subprocess.DEVNULL,
                    start_new_session=True, **options,
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
                stdout.seek(0)
                output = stdout.read(65_536)
        return subprocess.CompletedProcess(command, code, stdout=output)


def stage_package(source: Path, workspace: Path) -> None:
    """Copy only the declared application artifact, excluding links and specials."""
    if source.is_symlink() or not source.is_dir():
        raise ValueError("Workspace does not contain the versioned_mapping package")
    workspace.mkdir(mode=0o755)
    target = workspace / "versioned_mapping"
    target.mkdir(mode=0o755)
    total = 0
    for path in sorted(source.rglob("*")):
        if "__pycache__" in path.relative_to(source).parts:
            continue
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise ValueError("Submission contains a symbolic link or special file")
        destination = target / path.relative_to(source)
        if path.is_dir():
            destination.mkdir(mode=0o755)
        else:
            total += path.stat().st_size
            if total > 100_000_000:
                raise ValueError("Submission exceeds the verifier's workspace allowance")
            shutil.copyfile(path, destination)
            destination.chmod(0o644)


def main(stage: int) -> None:
    """Evaluate each requested feature on private generated inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=Path("/app"))
    parser.add_argument("--logs", type=Path, default=Path("/logs/verifier"))
    args = parser.parse_args()
    args.logs.mkdir(parents=True, exist_ok=True)
    args.logs.chmod(0o700)
    (args.logs / "reward.json").unlink(missing_ok=True)
    definitions = GROUPS[:stage + (stage == 4)] if stage < 5 else GROUPS
    if stage == 5:
        from canary_checks import canary_fixture

        definitions = (*definitions, canary_fixture)
    expected_groups = len(definitions)
    groups = {}
    errors = {}
    with TemporaryDirectory(prefix="mapping-checkpoint-") as path:
        scratch = Path(path)
        scratch.chmod(0o711)
        workspace = scratch / "app"
        try:
            stage_package(args.app / "versioned_mapping", workspace)
            run = Candidate(workspace, scratch)
            for group in definitions:
                key = group.__name__.removesuffix("_fixture")
                inputs = scratch / key
                inputs.mkdir()
                inputs.chmod(0o1777)
                try:
                    groups[key] = group(run, inputs)
                except (ValueError, OSError, AttributeError, TypeError, KeyError, IndexError, OverflowError) as error:
                    groups[key] = {}
                    errors[key] = str(error)[:250]
        except (ValueError, OSError, KeyError) as error:
            errors["submission"] = str(error)[:250]

    fractions = {
        key: sum(checks.values()) / len(checks) if checks else 0.0 for key, checks in groups.items()
    }
    score = sum(fractions.values()) / expected_groups if groups.get("build", {}).get("geometry") else 0.0
    if stage == 5:
        canary = groups.get("canary", {})
        positive = any(result for key, result in canary.items() if key.startswith("promote_"))
        legacy = sum(fractions.get(group.__name__.removesuffix("_fixture"), 0.0) for group in GROUPS) / len(GROUPS)
        score = 0.3 * legacy + 0.7 * (fractions.get("canary", 0.0) if positive else 0.0)
    (args.logs / "reward.json").write_text(json.dumps({"reward": score}) + "\n")
    (args.logs / "checkpoint.json").write_text(json.dumps(
        {"stage": stage, "score": score, "groups": groups, "fractions": fractions, "errors": errors},
        sort_keys=True, indent=2,
    ) + "\n")
    print(f"Stage {stage} reward {score:.6f}")
