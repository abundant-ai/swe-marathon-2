"""Harbor entry point: run the private cases against the submitted program and publish the result."""

from __future__ import annotations

import grp
import json
import os
import pwd
import shutil
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

# test.sh starts this file with Python -I; imports resolve only from this directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from verifier import runcases  # noqa: E402

SANDBOX_USER = "nobody"
SANDBOX_GROUP = "nogroup"
REWARD_FILES = ("reward.txt", "reward.json")
TOTAL_SEC = 3300  # the step verifier has 3,600 s; 1,500 runs at the per-run limit take at most 3,000 s
LEFTOVER_DIRS = ("/tmp", "/var/tmp", "/dev/shm")


class EvaluationError(Exception):
    """Evaluation could not be carried out; no valid reward may be published."""


def sandbox() -> tuple[list[str], tuple[int, int]]:
    """The command prefix that runs submitted code as the unprivileged user, and that user's ids.

    Raises:
        EvaluationError: The user is missing or privileges cannot be dropped.
    """
    try:
        owner = (pwd.getpwnam(SANDBOX_USER).pw_uid, grp.getgrnam(SANDBOX_GROUP).gr_gid)
    except KeyError as exc:
        raise EvaluationError("The unprivileged user is missing") from exc
    prefix = ["setpriv", "--reuid", SANDBOX_USER, "--regid", SANDBOX_GROUP, "--clear-groups"]
    if shutil.which("setpriv") is None or subprocess.run(prefix + ["true"], capture_output=True).returncode != 0:
        raise EvaluationError("Could not drop privileges; submitted code was not run")
    return prefix, owner


def kill_user(uid: int) -> None:
    """Kill every live process of the user, repeatedly until none is left, without starting one."""
    for _ in range(50):
        found = False
        try:
            entries = [entry.name for entry in os.scandir("/proc") if entry.name.isdigit()]
        except OSError:
            return
        for pid in entries:
            try:
                fields = dict(line.split(":", 1) for line in Path(f"/proc/{pid}/status").read_text().splitlines() if ":" in line)
                if int(fields["Uid"].split()[0]) != uid or fields["State"].split()[0] in ("Z", "X"):
                    continue
                os.kill(int(pid), signal.SIGKILL)
                found = True
            except (OSError, KeyError, ValueError, IndexError):
                continue
        if not found:
            return
        time.sleep(0.01)


def remove_leftovers(uid: int) -> None:
    """Remove what the user left at the top of the shared temporary directories, never following
    a link, so that the results can still be written."""
    for top in LEFTOVER_DIRS:
        try:
            entries = list(os.scandir(top))
        except OSError:
            continue
        for entry in entries:
            try:
                info = entry.stat(follow_symlinks=False)
                if info.st_uid != uid:
                    continue
                if stat.S_ISDIR(info.st_mode):
                    shutil.rmtree(entry.path)
                else:
                    os.unlink(entry.path)
            except OSError:
                continue


def grade(program: Path, private: Path, prefix: list[str], owner: tuple[int, int] | None, budget: float = TOTAL_SEC) -> dict:
    """Run every private case through `prefix` (as `owner`) and count exact matches.

    A case that cannot be set up or started, runs too long or prints too much counts as failed:
    what the submission does never makes the evaluation an error.

    Raises:
        EvaluationError: Private inputs are unreadable.
    """
    try:
        cases = json.loads((private / "cases.json").read_text(encoding="utf-8"))["cases"]
        expected = json.loads((private / "expected.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError) as exc:
        raise EvaluationError("Private cases are unreadable") from exc
    if not cases or any(case["id"] not in expected for case in cases):
        raise EvaluationError("Private cases and recorded answers do not match")
    metrics = {"cases_total": len(cases), "cases_run": 0, "cases_passed": 0, "reward": 0.0, "timeouts": 0, "errors": 0,
               "notes": [], "by_kind": {}}
    try:
        metrics["recording"] = json.loads((private / "recording.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    for case in cases:
        metrics["by_kind"].setdefault(case.get("kind", case["argv"][0]), {"total": 0, "passed": 0})["total"] += 1
    if not program.is_file() or not os.access(program, os.X_OK):
        metrics["notes"].append("/app/rebuild/goose is missing or not executable")
        return metrics
    subprocess.run(["chmod", "-R", "a+rX", str(program.parent)], check=False)
    failed = []
    started = time.monotonic()
    for case in cases:
        if time.monotonic() - started > budget:
            metrics["notes"].append(f"stopped after {budget} seconds of runs; the remaining cases count as failed")
            break
        if owner is not None:
            kill_user(owner[0])
        try:
            got = runcases.run_case([str(program)], case, prefix=prefix, owner=owner)
        except OSError as exc:  # whatever the submission did to this machine is its own case's failure
            got = {"exit": None, "stdout": None, "error": f"run: {type(exc).__name__}"}
        want = expected[case["id"]]
        metrics["cases_run"] += 1
        if got.get("error") == "timeout":
            metrics["timeouts"] += 1
        elif got.get("error"):
            metrics["errors"] += 1
        if got["exit"] == want["exit"] and got["stdout"] == want["stdout"]:
            metrics["cases_passed"] += 1
            metrics["by_kind"][case.get("kind", case["argv"][0])]["passed"] += 1
        else:
            failed.append(case["id"])
    if owner is not None:
        kill_user(owner[0])
        remove_leftovers(owner[0])
    try:
        runcases.clear_workspace()
    except OSError:
        pass
    metrics["reward"] = round(metrics["cases_passed"] / len(cases), 6)
    metrics["failed_sample"] = failed[:200]
    return metrics


def main() -> int:
    """Run one evaluation in this fresh container.

    Returns:
        Zero for a completed evaluation, including a failed submission; one for
        an evaluation error, which leaves no reward file.
    """
    tests = Path(__file__).resolve().parent
    output = Path("/logs/verifier")
    output.mkdir(parents=True, exist_ok=True)
    for name in REWARD_FILES + ("metrics.json",):
        (output / name).unlink(missing_ok=True)
    code = 1
    owner = None
    try:
        if os.geteuid() != 0:
            raise EvaluationError("Verifier must start as root to isolate submitted code")
        for closed in (tests, output):
            closed.chmod(0o700)
        prefix, owner = sandbox()
        metrics = grade(Path("/app/rebuild/goose"), tests / "private", prefix, owner)
        (output / "metrics.json").write_text(json.dumps(dict(metrics, status="completed"), indent=1, sort_keys=True) + "\n")
        (output / "reward.txt").write_text(f"{metrics['reward']:.6f}")
        print(f"reward: {metrics['reward']:.6f} ({metrics['cases_passed']}/{metrics['cases_total']} cases)", flush=True)
        code = 0
    except Exception as exc:  # noqa: BLE001 - every unexpected failure invalidates the evaluation
        message = str(exc) if isinstance(exc, EvaluationError) else f"Verifier error: {type(exc).__name__}"
        print(f"evaluation error: {message}", flush=True)
        for name in REWARD_FILES:
            (output / name).unlink(missing_ok=True)
        (output / "metrics.json").write_text(json.dumps({"status": "evaluation_error", "error": message}) + "\n")
    finally:
        if owner is not None:
            kill_user(owner[0])
        try:
            subprocess.run(["chmod", "-R", "a+rX", str(output)], check=False)
        except OSError:
            pass
    return code


if __name__ == "__main__":
    raise SystemExit(main())
