"""Harbor entry point: run the private cases against the submitted program and publish the result."""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import re
import resource
import secrets
import shutil
import signal
import stat
import subprocess
import sys
import time
from pathlib import Path

# test.sh starts this file with Python -I; imports resolve only from this directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from verifier import recorder, runcases  # noqa: E402

SUBMISSION = Path("/app/rebuild")
MARKER = Path(__file__).resolve().parent / "private" / "marker"   # the original's build marker
SCAN_BYTES = 4 << 30  # bytes of the submission searched for the marker, at most
REWARD_FILES = ("reward.txt", "reward.json")
TOTAL_SEC = 3300  # the step verifier has 3,600 s; 1,500 runs at the per-run limit take at most 3,000 s
# Where the unprivileged user can leave files: these, and every other world-writable directory
# that writable_dirs() finds when the evaluation starts.
LEFTOVER_DIRS = ["/tmp", "/var/tmp", "/dev/shm", "/dev/mqueue"]
SYSV_IPC = (("shm", "-m"), ("sem", "-s"), ("msg", "-q"))  # /proc/sysvipc/<name> and ipcrm's flag for it
LIMIT_NAMES = {"Max stack size": resource.RLIMIT_STACK, "Max processes": resource.RLIMIT_NPROC,
               "Max file size": resource.RLIMIT_FSIZE, "Max data size": resource.RLIMIT_DATA,
               "Max core file size": resource.RLIMIT_CORE}
STRICT_LIMITS = ("Max processes", "Max file size", "Max core file size")
# Run as submitted code is: /proc/self/status, then no_new_privs as prctl(PR_GET_NO_NEW_PRIVS)
# reports it, for kernels (gVisor's among them) whose status file may not list NoNewPrivs.
NNP_PROBE = (
    "import ctypes, sys\n"
    "sys.stdout.write(open('/proc/self/status').read())\n"
    "try:\n"
    "    value = ctypes.CDLL(None, use_errno=True).prctl(39, 0, 0, 0, 0)\n"
    "except Exception:\n"
    "    value = -1\n"
    "sys.stdout.write('PrctlNoNewPrivs:\\t%d\\n' % value)\n"
)


class EvaluationError(Exception):
    """Evaluation could not be carried out; no valid reward may be published."""


def sandbox_problems(status: str, limits: str, owner: tuple[int, int]) -> tuple[list[str], dict]:
    """What is wrong with a process meant to run submitted code, from its /proc/self/status (which
    NNP_PROBE follows with a PrctlNoNewPrivs line) and /proc/self/limits, and the limits it has
    (soft values). no_new_privs holds where either the status file or prctl shows it."""
    fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    uid, gid = (str(owner[0]), str(owner[1]))
    problems = []
    if "1" not in (fields.get("NoNewPrivs", "").strip(), fields.get("PrctlNoNewPrivs", "").strip()):
        problems.append("no_new_privs is not set")
    if fields.get("Uid", "").split() != [uid] * 4:
        problems.append("its user ids are not all the unprivileged user's")
    if fields.get("Gid", "").split() != [gid] * 4:
        problems.append("its group ids are not all the unprivileged group's")
    if fields.get("Groups", "").split():
        problems.append("it keeps supplementary groups")
    for name in ("CapPrm", "CapEff", "CapAmb"):
        try:  # ambient capabilities are a subset of the permitted ones: a kernel may not list them
            if int(fields.get(name, "0" if name == "CapAmb" else "").strip(), 16):
                problems.append(f"it holds capabilities ({name})")
        except ValueError:
            problems.append(f"no {name} in its status")
    found = {}
    for line in limits.splitlines():
        for name in LIMIT_NAMES:
            if line.startswith(name + " "):
                found[name] = line[len(name):].split()[0]
    for name, which in LIMIT_NAMES.items():
        value = found.get(name)
        wanted = runcases.LIMITS[which]
        if name in STRICT_LIMITS and not (value and value.isdigit() and int(value) <= wanted):
            problems.append(f"{name.lower()} is {value}, not at most {wanted}")
    return problems, found


def probe(prefix: list[str], argv: list[str], fallback: list[str] | None = None) -> str:
    """What a command prints when started exactly as submitted code is; where it fails and a
    `fallback` command is given, what that prints."""
    for command in (argv, fallback):
        if command is None:
            break
        done = subprocess.run(prefix + command, capture_output=True, text=True, timeout=30, preexec_fn=runcases.limit,
                              env={"PATH": "/usr/local/bin:/usr/bin:/bin"})
        if done.returncode == 0:
            return done.stdout
    raise EvaluationError(f"Could not drop privileges: {(fallback or argv)[0]} exited {done.returncode}")


def sandbox() -> tuple[list[str], tuple[int, int], dict]:
    """The command prefix that runs submitted code as an unprivileged user of this evaluation's own
    (a random uid and gid no other container shares, so that its process limit counts only its
    own runs), those ids, and the limits such a process has. A process started the same way must
    have dropped every privilege, and a set-user-id root file started that way must gain nothing.

    Raises:
        EvaluationError: Privileges cannot be dropped or the drop does not hold.
    """
    uid = (1 << 20) + secrets.randbelow(1 << 29)
    owner = (uid, uid)
    if shutil.which("setpriv") is None:
        raise EvaluationError("setpriv is missing; submitted code was not run")
    prefix = ["setpriv", "--reuid", str(uid), "--regid", str(uid), "--clear-groups", "--no-new-privs"]
    status = probe(prefix, [sys.executable, "-I", "-c", NNP_PROBE], fallback=["cat", "/proc/self/status"])
    problems, found = sandbox_problems(status, probe(prefix, ["cat", "/proc/self/limits"]), owner)
    # A set-user-id and set-group-id copy of id(1), owned by root, beside the submission.
    place = SUBMISSION.parent / ".setid-probe"
    shutil.rmtree(place, ignore_errors=True)
    try:
        place.mkdir(mode=0o755)
        os.chmod(place, 0o755)
        shutil.copy(shutil.which("id") or "/usr/bin/id", place / "id")
        os.chown(place / "id", 0, 0)
        os.chmod(place / "id", 0o6755)
        ids = (probe(prefix, [str(place / "id"), "-u"]).strip(), probe(prefix, [str(place / "id"), "-g"]).strip())
    finally:
        shutil.rmtree(place, ignore_errors=True)
    if ids != (str(owner[0]), str(owner[1])):
        problems.append(f"a set-id root file ran with user and group {ids}")
    if problems:
        raise EvaluationError("The unprivileged run does not hold: " + "; ".join(problems))
    return prefix, owner, found


def seal(top: Path, owner: tuple[int, int] = (0, 0)) -> None:
    """Make the submission `owner`'s and read-only for anyone else, before any of it runs: no
    set-user-id, set-group-id or sticky bit, executables 0755, other files 0644, directories 0755.
    Links are left as they are and never followed; devices, pipes and sockets are removed.

    Raises:
        EvaluationError: An entry can be neither sealed nor removed.
    """
    if not top.is_dir() or top.is_symlink():
        return
    entries = [top]
    for root, directories, files in os.walk(top):
        entries += [Path(root) / name for name in directories + files]
    for path in entries:
        try:
            info = os.lstat(path)
            if stat.S_ISLNK(info.st_mode):
                os.lchown(path, *owner)
            elif stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode):
                os.lchown(path, *owner)
                os.chmod(path, 0o755 if stat.S_ISDIR(info.st_mode) or info.st_mode & 0o111 else 0o644)
            else:
                os.unlink(path)
        except OSError as exc:
            try:
                runcases.remove_path(path)
            except OSError:
                raise EvaluationError(f"Could not seal the submission: {type(exc).__name__}") from exc


def kill_user(uid: int) -> None:
    """Kill every process of the user (owner of its /proc entry), repeatedly until none is left,
    without starting one, and reap what this process is left to reap."""
    for _ in range(50):
        found = False
        try:
            entries = [entry.name for entry in os.scandir("/proc") if entry.name.isdigit()]
        except OSError:
            return
        for pid in entries:
            try:
                if os.stat(f"/proc/{pid}").st_uid != uid:
                    continue
                state = Path(f"/proc/{pid}/stat").read_bytes().rsplit(b")", 1)[1].split()[0]
                if state in (b"Z", b"X"):
                    continue
                os.kill(int(pid), signal.SIGKILL)
                found = True
            except (FileNotFoundError, ProcessLookupError):
                continue
            except (OSError, IndexError, ValueError):
                try:
                    os.kill(int(pid), signal.SIGKILL)
                    found = True
                except OSError:
                    continue
        reap()
        if not found:
            return
        time.sleep(0.01)


def reap() -> None:
    """Collect the exit of every child this process has (orphans included, as their subreaper)."""
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return


def writable_dirs(root: str = "/") -> list[str]:
    """Every directory under `root` that anyone may write to, not following links and leaving out
    the kernel's own trees: where a submission could leave a file for a later case."""
    found = []
    for top, directories, _ in os.walk(root):
        if top == root:
            directories[:] = [d for d in directories if d not in ("proc", "sys", "dev")]
        try:
            if os.lstat(top).st_mode & stat.S_IWOTH:
                found.append(top)
        except OSError:
            continue
    return found


def remove_ipc(uid: int, root: Path = Path("/proc/sysvipc")) -> None:
    """Remove the System V shared memory, semaphores and message queues the user owns or made:
    they outlive the processes that made them."""
    for name, flag in SYSV_IPC:
        try:
            header, *rows = (root / name).read_text().splitlines()
        except (OSError, ValueError):
            continue
        columns = header.split()
        for row in rows:
            values = dict(zip(columns, row.split()))
            if str(uid) in (values.get("uid"), values.get("cuid")) and values.get(columns[1], "").isdigit():
                try:
                    subprocess.run(["ipcrm", flag, values[columns[1]]], capture_output=True, check=False, timeout=10)
                except (OSError, subprocess.SubprocessError):
                    continue


def reset(uid: int) -> None:
    """Before and after every case: none of the user's processes left, nothing of its files in a
    directory it can write to, and none of its System V IPC objects."""
    kill_user(uid)
    remove_leftovers(uid)
    remove_ipc(uid)


def remove_leftovers(uid: int) -> None:
    """Remove what the user left at the top of the directories it can write to, never following a
    link: every run starts with nothing of an earlier run's there."""
    for top in LEFTOVER_DIRS:
        try:
            entries = list(os.scandir(top))
        except OSError:
            continue
        for entry in entries:
            try:
                if entry.stat(follow_symlinks=False).st_uid == uid:
                    runcases.remove_path(Path(entry.path))
            except Exception:  # noqa: BLE001 - a leftover that cannot go fails the next case, not grading
                continue


def holds_marker(top: Path, marker: bytes) -> str | None:
    """The first regular file under `top` (links not followed) that holds `marker`, searching at
    most SCAN_BYTES bytes in all."""
    left = SCAN_BYTES
    for root, directories, files in os.walk(top):
        for name in sorted(files):
            path = Path(root, name)
            try:
                if not stat.S_ISREG(os.lstat(path).st_mode):
                    continue
                with open(path, "rb") as handle:
                    tail = b""
                    while left > 0:
                        chunk = handle.read(min(1 << 20, left))
                        if not chunk:
                            break
                        left -= len(chunk)
                        if marker in tail + chunk:
                            return str(path.relative_to(top))
                        tail = chunk[-len(marker):]
            except OSError:
                continue
    return None


def identity(path: Path) -> dict:
    """A program's sha256, and its sha256 with any build marker zeroed (build.sh's build.txt)."""
    try:
        data = path.read_bytes()
    except OSError:
        return {}
    zeroed = re.sub(rb"GOOSE-BUILD-MARKER-[0-9a-f]{32}", b"GOOSE-BUILD-MARKER-" + b"0" * 32, data)
    return {"sha256": hashlib.sha256(data).hexdigest(), "sha256_without_marker": hashlib.sha256(zeroed).hexdigest()}


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
    metrics = {"cases_total": len(cases), "cases_run": 0, "cases_passed": 0, "cases_failed": 0, "reward": 0.0,
               "timeouts": 0, "output_limits": 0, "memory_limits": 0, "setup_errors": 0, "seconds_total": 0.0,
               "seconds_max": 0.0,
               "stopped": None, "notes": [], "by_kind": {}}
    try:
        metrics["recording"] = json.loads((private / "recording.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    kind = lambda case: case.get("kind", case["argv"][0])  # noqa: E731
    for case in cases:
        metrics["by_kind"].setdefault(kind(case), {"total": 0, "run": 0, "passed": 0, "failed": 0})["total"] += 1
    failed, seconds = [], []
    if not program.is_file() or not os.access(program, os.X_OK):
        metrics["notes"].append("/app/rebuild/goose is missing or not executable")
        cases = []
    started = time.monotonic()
    for case in cases:
        if time.monotonic() - started > budget:
            metrics["stopped"] = f"after {budget} seconds of runs; the remaining cases count as failed"
            break
        try:  # whatever the submission did to this machine is its own case's failure, never an error
            if owner is not None:
                reset(owner[0])
            got = runcases.run_case([str(program)], case, prefix=prefix, owner=owner)
        except Exception as exc:  # noqa: BLE001
            got = {"exit": None, "stdout": None, "error": f"run: {type(exc).__name__}", "seconds": 0.0}
        tally = metrics["by_kind"][kind(case)]
        metrics["cases_run"] += 1
        tally["run"] += 1
        metrics["seconds_total"] = round(metrics["seconds_total"] + got["seconds"], 3)
        metrics["seconds_max"] = max(metrics["seconds_max"], got["seconds"])
        error = got.get("error")
        seconds.append(got["seconds"])
        if error == "timeout":
            metrics["timeouts"] += 1
        elif error == "output limit":
            metrics["output_limits"] += 1
        elif error == "memory limit":
            metrics["memory_limits"] += 1
        elif error:
            metrics["setup_errors"] += 1
        if runcases.matches(got, expected[case["id"]]):
            metrics["cases_passed"] += 1
            tally["passed"] += 1
        else:
            failed.append(case["id"])
    try:
        if owner is not None:
            reset(owner[0])
        runcases.clear_workspace()
    except Exception:  # noqa: BLE001
        pass
    seconds.sort()
    metrics["seconds_p99"] = seconds[int(0.99 * (len(seconds) - 1))] if seconds else 0.0
    metrics["runs_over_half_a_second"] = sum(value > 0.5 for value in seconds)
    metrics["runs_over_a_second"] = sum(value > 1.0 for value in seconds)
    metrics["cases_failed"] = metrics["cases_total"] - metrics["cases_passed"]
    for tally in metrics["by_kind"].values():
        tally["failed"] = tally["total"] - tally["passed"]
    metrics["reward"] = round(metrics["cases_passed"] / metrics["cases_total"], 6)
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
        try:  # the out-of-memory killer takes a submission's process, never this one
            Path("/proc/self/oom_score_adj").write_text("-1000")
        except OSError:
            pass
        try:  # orphans of submitted code are reparented here and reaped (kill_user)
            ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0)
        except (OSError, AttributeError):
            pass
        prefix, owner, limits = sandbox()
        refused = None
        try:
            seal(SUBMISSION)
        except EvaluationError as exc:  # a submission that cannot be made safe to run is not run
            refused = f"{exc}: not graded"
        LEFTOVER_DIRS.extend(top for top in writable_dirs() if top not in LEFTOVER_DIRS)
        marker = MARKER.read_text(encoding="utf-8").strip() if MARKER.is_file() else ""
        found = holds_marker(SUBMISSION, f"GOOSE-BUILD-MARKER-{marker}".encode()) if marker and not refused else None
        if found:  # the original compiler itself, delivered: nothing of it is the agent's work
            refused = f"/app/rebuild/{found} holds the original compiler's build marker: not graded"
        if refused:
            metrics = {"cases_total": None, "cases_passed": 0, "reward": 0.0, "notes": [refused]}
        else:
            metrics = grade(SUBMISSION / "goose", tests / "private", prefix, owner)
        metrics["limits"] = limits
        metrics["submission"] = identity(SUBMISSION / "goose")
        metrics["host"] = recorder.host()
        (output / "reward.txt").write_text(f"{metrics['reward']:.6f}")
        code = 0
        print(f"reward: {metrics['reward']:.6f} ({metrics['cases_passed']}/{metrics['cases_total']} cases)", flush=True)
        try:
            (output / "metrics.json").write_text(json.dumps(dict(metrics, status="completed"), indent=1, sort_keys=True) + "\n")
        except OSError:
            pass
    except Exception as exc:  # noqa: BLE001 - every unexpected failure invalidates the evaluation
        message = str(exc) if isinstance(exc, EvaluationError) else f"Verifier error: {type(exc).__name__}"
        print(f"evaluation error: {message}", flush=True)
        if code != 0:
            for name in REWARD_FILES:
                (output / name).unlink(missing_ok=True)
            try:
                (output / "metrics.json").write_text(json.dumps({"status": "evaluation_error", "error": message}) + "\n")
            except OSError:
                pass
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
