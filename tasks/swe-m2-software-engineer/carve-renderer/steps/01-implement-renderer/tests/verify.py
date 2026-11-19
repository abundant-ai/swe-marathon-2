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
import tempfile
import time
from pathlib import Path

# test.sh starts this file with Python -I; imports resolve only from this directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from verifier import recorder, runcases  # noqa: E402

SUBMISSION = Path("/app/rebuild")
PROGRAM = SUBMISSION / "carve"
DELIVERY_MARK = ".delivered"  # written into /app/rebuild by the collect hook (environment/prepare-delivery)
DELIVERY_RECORD = ".delivery.json"  # the hook's record: egress, the agent's processes, every entry; never scored
RECORD_LIMIT = 64 << 20  # bytes of the record read, at most
# Public hosts the original can be fetched from; the verifier refuses to grade if it can reach one.
NETWORK_HOSTS = (("github.com", 443), ("pypi.org", 443), ("proxy.golang.org", 443), ("registry.npmjs.org", 443))
# Every build of the original that upstream publishes ready to run, and text they all hold that a
# renderer written from the specification does not (scripts/upstream_builds.py): a delivered file
# that is one of them, or holds enough of that text, is a fetched original.
UPSTREAM_BUILDS = Path(__file__).resolve().parent / "verifier" / "upstream_builds.json"
REWARD_FILES = ("reward.txt", "reward.json")
TOTAL_SEC = 5400  # the step verifier has 6,000 s; everything up to the reward file fits in this, even every run at 2 s
MARGIN_SEC = 120  # no case starts when less than this is left of TOTAL_SEC
MAX_ENTRIES = 200_003  # entries in a submission, at most (the instruction's 200,000, its top, the mark and the record); more is not run
MAX_BYTES = 2 << 30    # bytes of a submission's regular files (each inode once), at most; more is not run
MAX_PROGRAM = 512 << 20  # bytes of /app/rebuild/carve hashed for metrics.json, at most
RESERVE_BYTES = 512 << 20  # bytes kept free in /tmp and /logs/verifier: no case starts with less
CLEANUP_SEC = 60  # the cleanup after the last case, at most
RETRIED_LIMITS = ("memory limit", "disk limit", "file limit")  # a case stopped by one runs once more
STALL_CPU = 1.0   # a timeout or a failed start that used under this much CPU is a stall: run it once more
METRICS_SPACE = 1 << 18  # bytes metrics.json holds from the start, so that writing it needs no new space
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


def pick_id(maps: tuple[str, ...] = ("/proc/self/uid_map", "/proc/self/gid_map")) -> int:
    """An id for submitted code's user and group: inside every id map of this user namespace (a
    rootless or remapped container maps only 65,536 ids), drawn at random from 20000-60000 so that
    no other container is likely to share it, and no user or group of the image's; 65534 where none
    fits."""
    ranges = []
    for path in maps:
        try:
            rows = [tuple(map(int, line.split()[:3])) for line in Path(path).read_text().splitlines() if line.strip()]
        except (OSError, ValueError):
            rows = [(0, 0, 1 << 32)]  # no map: every id
        ranges.append(rows)
    taken = set()
    for table in ("/etc/passwd", "/etc/group"):
        try:
            taken |= {int(line.split(":")[2]) for line in Path(table).read_text().splitlines() if line.count(":") >= 2
                      and line.split(":")[2].isdigit()}
        except OSError:
            pass
    for _ in range(500):
        candidate = 20000 + secrets.randbelow(40000)
        if candidate not in taken and all(any(start <= candidate < start + length for start, _, length in rows)
                                          for rows in ranges):
            return candidate
    return 65534


def sandbox() -> tuple[list[str], tuple[int, int], dict]:
    """The command prefix that runs submitted code as an unprivileged user of this evaluation's own
    (a random uid and gid no other container shares, so that its process limit counts only its
    own runs), those ids, and the limits such a process has. A process started the same way must
    have dropped every privilege, and a set-user-id root file started that way must gain nothing.

    Raises:
        EvaluationError: Privileges cannot be dropped or the drop does not hold.
    """
    uid = pick_id()
    owner = (uid, uid)
    if shutil.which("setpriv") is None:
        raise EvaluationError("setpriv is missing; submitted code was not run")
    scratch = Path(tempfile.mkdtemp())
    try:  # the workspaces will be chowned to the id: a filesystem that refuses it grades nothing
        os.chown(scratch, uid, uid)
    except OSError as exc:
        raise EvaluationError(f"Files cannot be given to uid {uid}: {type(exc).__name__}") from exc
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
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
    Links are left as they are and never followed; devices, pipes and sockets are removed. Entries
    are counted as they are read, and the walk stops at MAX_ENTRIES.

    Raises:
        EvaluationError: The submission holds more than MAX_ENTRIES entries or MAX_BYTES bytes of
            files, or an entry can be neither sealed nor removed.
    """
    if not top.is_dir() or top.is_symlink():
        return
    entries, size, seen, todo = [top], 0, set(), [top]
    while todo:
        try:
            listing = os.scandir(todo.pop())
        except OSError:
            continue
        with listing:
            for entry in listing:
                entries.append(Path(entry.path))
                if len(entries) > MAX_ENTRIES:
                    raise EvaluationError(f"The submission holds more than {MAX_ENTRIES} entries")
                try:
                    info = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if stat.S_ISDIR(info.st_mode):
                    todo.append(Path(entry.path))
                elif stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) not in seen:
                    seen.add((info.st_dev, info.st_ino))
                    size += info.st_size
                    if size > MAX_BYTES:
                        raise EvaluationError(f"The submission's files hold more than {MAX_BYTES} bytes")
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


def as_user(uid: int, argv: list[str], timeout: float) -> None:
    """Run a command as `uid` (and its group), only where root can drop to it and it is not this
    process's own uid (a kill -1 as oneself would end the evaluation)."""
    if os.geteuid() != 0 or uid == os.geteuid() or shutil.which("setpriv") is None:
        return
    try:
        subprocess.run(["setpriv", "--reuid", str(uid), "--regid", str(uid), "--clear-groups", "--", *argv],
                       capture_output=True, check=False, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        pass


def kill_user(uid: int) -> None:
    """End every process of the user: kill -KILL -1 run as the user itself, which reaches all of
    them at once (a fork cannot race it), repeated, with a walk of /proc that signals any pid the
    user owns, whatever its state (a leader that exited with threads left reads Z), as the
    backstop and the test that none is left. Reaps what this process is left to reap."""
    for _ in range(50):
        as_user(uid, ["kill", "-KILL", "-1"], 10)
        found = False
        try:
            entries = [entry.name for entry in os.scandir("/proc") if entry.name.isdigit()]
        except OSError:
            return
        for pid in entries:
            try:
                if os.stat(f"/proc/{pid}").st_uid != uid:
                    continue
            except OSError:
                continue
            try:
                os.kill(int(pid), signal.SIGKILL)
            except OSError:
                continue
            try:
                found = found or any(Path(f"/proc/{pid}/task/{task.name}/stat").read_bytes().rsplit(b")", 1)[1].split()[0]
                                     not in (b"Z", b"X") for task in os.scandir(f"/proc/{pid}/task"))
            except (OSError, IndexError):
                found = True  # a task that vanished while read: look again
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
        if top == root:  # the kernel's trees, and /logs, which holds the agent's own artifacts
            directories[:] = [d for d in directories if d not in ("proc", "sys", "dev", "logs")]
        if os.path.realpath(top) == str(SUBMISSION):  # sealed: nothing in it is writable
            directories[:] = []
            continue
        try:
            if os.lstat(top).st_mode & stat.S_IWOTH:
                found.append(top)
        except OSError:
            continue
    return found


def remove_ipc(uid: int, root: Path = Path("/proc/sysvipc")) -> None:
    """Remove the System V shared memory, semaphores and message queues the user owns or made:
    they outlive the processes that made them. First as the user itself (ipcrm --all, which any
    owner may do and which finds them without /proc/sysvipc), then as root, which may lack the
    capability to."""
    as_user(uid, ["ipcrm", "--all"], 60)
    for name, flag in SYSV_IPC:
        try:
            header, *rows = (root / name).read_text().splitlines()
        except (OSError, ValueError):
            continue
        columns = header.split()
        ids = []
        for row in rows:
            values = dict(zip(columns, row.split()))
            if str(uid) in (values.get("uid"), values.get("cuid")) and values.get(columns[1], "").isdigit():
                ids.append(values[columns[1]])
        for at in range(0, len(ids), 2000):  # one ipcrm for many objects
            try:
                subprocess.run(["ipcrm", *(arg for i in ids[at:at + 2000] for arg in (flag, i))], capture_output=True,
                               check=False, timeout=60)
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
    link: every run starts with nothing of an earlier run's there. One find for each directory,
    which hands every entry it owns to as few rm -rf runs as their names need, however many."""
    for top in LEFTOVER_DIRS:
        if not os.path.isdir(top) or os.path.islink(top):
            continue
        try:
            subprocess.run(["find", top, "-xdev", "-mindepth", "1", "-maxdepth", "1", "-user", str(uid),
                            "-exec", "rm", "-rf", "--", "{}", "+"], capture_output=True, check=False, timeout=300)
        except (OSError, subprocess.SubprocessError):
            continue


def identity(path: Path) -> dict:
    """A program's size and sha256, read in 1 MB chunks; only for a regular file, not a link, of
    at most MAX_PROGRAM bytes, and never raising."""
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode):
            return {"error": "not a regular file"}
        if info.st_size > MAX_PROGRAM:
            return {"size": info.st_size, "error": "too large to hash"}
        whole = hashlib.sha256()
        with open(path, "rb") as handle:
            while chunk := handle.read(1 << 20):
                whole.update(chunk)
        return {"size": info.st_size, "sha256": whole.hexdigest()}
    except Exception as exc:  # noqa: BLE001 - metadata, never a reason to lose the reward
        return {"error": type(exc).__name__}


def arrived(top: Path) -> tuple[int, int]:
    """The entries below `top` (files, directories and links, the mark aside) and the bytes of its
    regular files, each inode once, counted the way the collect hook counts them; never following
    a link, and stopping once past MAX_ENTRIES (the count is then only a bound)."""
    entries, size, files, folders = 0, 0, set(), [str(top)]
    skipped = {str(top / DELIVERY_MARK), str(top / DELIVERY_RECORD)}
    while folders and entries <= MAX_ENTRIES:
        with os.scandir(folders.pop()) as listing:
            for entry in listing:
                if entry.path in skipped:
                    continue
                info = entry.stat(follow_symlinks=False)
                entries += 1
                if stat.S_ISDIR(info.st_mode):
                    folders.append(entry.path)
                elif stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) not in files:
                    files.add((info.st_dev, info.st_ino))
                    size += info.st_size
    return entries, size


def delivery(top: Path) -> tuple[list[str], bool]:
    """What the collect hook's mark and the copy that arrived say about the delivery: notes, and
    whether it was refused (over the stated limits: reward 0). The hook marks every delivery
    before it is copied, an empty one too, so an arrival with no mark, or with fewer entries or
    bytes than the mark counts, is the copy failing, not the submission.

    Raises:
        EvaluationError: Nothing arrived at all, or the copy arrived cut short.
    """
    try:
        empty = top.is_symlink() or not top.is_dir() or next(top.iterdir(), None) is None
    except OSError:
        empty = True
    if empty:
        raise EvaluationError("Nothing arrived: /app/rebuild is missing or empty, though the collect hook marks every delivery")
    mark = top / DELIVERY_MARK
    try:
        lines = mark.read_text(errors="replace").splitlines()[:40] if mark.is_file() and not mark.is_symlink() \
            and mark.stat().st_size < (1 << 20) else None
    except OSError:
        lines = None
    if not lines:
        raise EvaluationError("The delivery arrived without the collect hook's mark")
    head, notes = lines[0].split(), [f"collect hook: {line}" for line in lines[1:] if line.strip()][:20]
    if head[:1] == ["refused"]:
        return (notes or ["collect hook: the delivery was not copied"]), True
    if len(head) == 3 and head[0] == "delivered" and all(value.isascii() and value.isdigit() for value in head[1:]):
        try:
            entries, size = arrived(top)
        except OSError as exc:
            raise EvaluationError(f"The delivery could not be measured: {type(exc).__name__}") from exc
        if entries < int(head[1]) or size < int(head[2]):
            raise EvaluationError(f"The copy arrived cut short: {entries:,} of {int(head[1]):,} entries and {size:,} of "
                                  f"{int(head[2]):,} bytes")
        return notes, False
    raise EvaluationError("The collect hook's mark cannot be read")


def delivery_record(top: Path) -> dict:
    """What the collect hook's record says, for metrics.json and the audit of a trial: whether the
    public internet answered when the session ended, the agent's processes then alive, how many
    rounds of killing ended them, and the delivery's entries (their number and the twenty with the
    latest change times). Read in a bounded way; never raising, never scored."""
    try:
        path = top / DELIVERY_RECORD
        if not path.is_file() or path.is_symlink() or path.stat().st_size > RECORD_LIMIT:
            return {"error": "no readable record"}
        record = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        entries = record.get("entries") or []
        latest = sorted((item for item in entries if isinstance(item, dict)), key=lambda item: -float(item.get("ctime") or 0))
        summary = {key: record.get(key) for key in ("egress", "egress_open", "agent_process_count", "kill_rounds",
                                                    "agent_processes_left", "delivered", "listing_complete", "turn_ended_at",
                                                    "turn_end_from", "hook_started_at", "late_entries")}
        summary |= {"agent_processes": (record.get("agent_processes") or [])[:50], "entries_listed": len(entries),
                    "copies": record.get("copies", []), "refused_copies": record.get("refused_copies", []),
                    "watchdog": record.get("watchdog"), "restored": record.get("restored"),
                    "precap_watchdog": (record.get("precap_watchdog") or [])[-20:],
                    "ended_by_watchdog": bool(record.get("ended_by_watchdog")),
                    "latest_changes": [{key: item.get(key) for key in ("path", "type", "size", "ctime", "sha256")} for item in latest[:20]]}
        flags = []
        if record.get("ended_by_watchdog"):
            flags.append("the pre-cap watchdog ended the session before the platform's cap")
        if record.get("egress_open"):
            flags.append("the public internet answered when the session ended")
        if record.get("agent_processes_left"):
            flags.append(f"{record.get('agent_processes_left')} of the agent's processes survived the kill")
        if record.get("late_entries"):
            flags.append(f"{record.get('late_entries')} delivered entries changed after the turn ended")
        if record.get("copies"):
            flags.append(f"{len(record['copies'])} files were copied in from links out of /app/rebuild")
        if not (record.get("restored") or {}).get("restored_at"):
            flags.append("the egress watcher did not see the turn end; the turn-end time is the hook's start")
        summary["flags"] = flags
        return summary
    except Exception as exc:  # noqa: BLE001 - metadata, never a reason to lose the reward
        return {"error": type(exc).__name__}


def upstream_builds(path: Path = UPSTREAM_BUILDS) -> dict:
    """The sha256 of upstream's published builds and of the other engines, the carve-rs text that
    marks a build, the markers of foreign language runtimes, and how many of each make a delivered
    file a fetched engine (verifier/upstream_builds.json).

    Raises:
        EvaluationError: The list is unreadable or empty.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        builds = {"hashes": set(data["sha256"]), "strings": [text.encode() for text in data["strings"]],
                  "strings_needed": int(data["strings_needed"]),
                  "runtimes": {name: [marker.encode() for marker in markers] for name, markers in data.get("runtimes", {}).items()},
                  "runtime_needed": int(data.get("runtime_markers_needed", 2))}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise EvaluationError("The list of upstream's builds is unreadable") from exc
    if not builds["hashes"] or not builds["strings"] or builds["strings_needed"] < 1:
        raise EvaluationError("The list of upstream's builds is empty")
    return builds


def fetched_build(top: Path, builds: dict) -> str | None:
    """The first regular file under `top` (links not followed, each inode once) that is a fetched
    engine: one of upstream's builds by its sha256, a file holding `strings_needed` of carve-rs's
    strings, or a program holding `runtime_needed` markers of one foreign language runtime (which
    the instruction's stdlib-only rule forbids). Read in chunks that overlap by the longest needle;
    None where none does. The top-level mark and record are skipped; seal() has bounded the bytes
    (MAX_BYTES)."""
    strings, hashes, needed = builds["strings"], builds["hashes"], builds["strings_needed"]
    runtimes, runtime_needed = builds["runtimes"], builds["runtime_needed"]
    markers = [(name, marker) for name, group in runtimes.items() for marker in group]
    overlap = max((len(text) for text in strings + [marker for _, marker in markers]), default=1)
    skip = {str(top / DELIVERY_MARK), str(top / DELIVERY_RECORD)}
    seen = set()
    for root, directories, files in os.walk(top):
        directories.sort()
        for name in sorted(files):
            path = Path(root, name)
            try:
                info = os.lstat(path)
                if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) in seen or str(path) in skip:
                    continue
                seen.add((info.st_dev, info.st_ino))
                whole, found, runtime_hits, tail = hashlib.sha256(), set(), {}, b""
                with open(path, "rb") as handle:
                    while chunk := handle.read(1 << 20):
                        whole.update(chunk)
                        window = tail + chunk
                        found.update(index for index, text in enumerate(strings) if text in window)
                        for rname, marker in markers:
                            if marker in window:
                                runtime_hits.setdefault(rname, set()).add(marker)
                        tail = window[-overlap:]
                if whole.hexdigest() in hashes:
                    return f"/app/rebuild/{path.relative_to(top)} is a build of the original or another engine that upstream publishes"
                if len(found) >= needed:
                    return f"/app/rebuild/{path.relative_to(top)} holds the text of a build of the original"
                for rname, hits in runtime_hits.items():
                    if len(hits) >= runtime_needed:
                        return f"/app/rebuild/{path.relative_to(top)} embeds a {rname} runtime, which the instruction does not allow"
            except OSError:
                continue
    return None


def network_open() -> str | None:
    """A public host the verifier can reach, or None: the separate verifier must have no network,
    and a provider that left it open would let a case fetch the original. Each host is tried once,
    half a second."""
    import socket  # noqa: PLC0415
    for host, port in NETWORK_HOSTS:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return f"{host}:{port}"
        except OSError:
            continue
    return None


def free_space() -> dict:
    """The bytes free in /tmp and /logs/verifier, -1 where a filesystem reports no size."""
    return {str(place): runcases.disk_free(place)[0] for place in (runcases.WORKSPACE.parent, Path("/logs/verifier"))}


def low_on_disk() -> bool:
    """Whether /tmp or /logs/verifier has less than RESERVE_BYTES free (what Harbor needs to fetch
    the results, and the results themselves); a filesystem that reports no size never is."""
    return any(0 <= free < RESERVE_BYTES for free in free_space().values())


def write_in_place(path: Path, data: bytes) -> None:
    """Overwrite a file reserved at the start without truncating it first, so that no new space is
    needed where it already held as much, then cut it to length."""
    try:
        with open(path, "r+b") as handle:
            handle.write(data)
            handle.truncate(len(data))
    except FileNotFoundError:
        path.write_bytes(data)


NEAR_MISS = ("exit_right_stdout_wrong", "equal_collapsing_whitespace", "equal_sorting_attributes", "equal_text_only")
TAG = re.compile(rb"<[^>]+>")
ATTR = re.compile(rb'(\w[\w:-]*)="[^"]*"|(\w[\w:-]*)')


def collapse_ws(html: bytes) -> bytes:
    """`html` with the whitespace between tags removed and every other run made one space."""
    return re.sub(rb"\s+", b" ", re.sub(rb">\s+<", b"><", html)).strip()


def sort_attrs(html: bytes) -> bytes:
    """`collapse_ws`, with each tag's attributes sorted and `<x />` written `<x>`: equal here means
    the structure and the attribute values are right and only their order or spacing differs."""
    def one(match):
        inner = match.group(0)[1:-1].rstrip(b"/").strip()
        if inner.startswith(b"/") or b" " not in inner:
            return b"<" + inner + b">"
        name, rest = inner.split(b" ", 1)
        return b"<" + name + b" " + b" ".join(sorted(rest.split())) + b">"
    return TAG.sub(one, collapse_ws(html))


def near_miss(got: dict, want: dict, counts: dict) -> None:
    """Record, without scoring, how close a failed answer is to the expected one (QA 19 F2)."""
    if got.get("stdout") is None:
        return
    mine = got["stdout"]
    theirs = want["stdout"].encode("utf-8", "surrogateescape")
    if got.get("exit") == want["exit"]:
        counts["exit_right_stdout_wrong"] += 1
        if collapse_ws(mine) == collapse_ws(theirs):
            counts["equal_collapsing_whitespace"] += 1
        if sort_attrs(mine) == sort_attrs(theirs):
            counts["equal_sorting_attributes"] += 1
        if TAG.sub(b"", collapse_ws(mine)) == TAG.sub(b"", collapse_ws(theirs)):
            counts["equal_text_only"] += 1


def fingerprint(program: Path, private: Path, prefix: list[str], owner: tuple[int, int] | None, deadline: float) -> dict:
    """Run the delivered program on the fingerprint probes and count how many match the original's
    answer (QA 04 F3): documents where the original and the spec model disagree, and the original's
    own out-of-scope commands. A renderer written from the specification matches few; the original,
    however re-encoded, matches all. Never scored. Private inputs missing is no error."""
    try:
        probes = json.loads((private / "probes.json").read_text(encoding="utf-8"))["probes"]
        answers = json.loads((private / "probes_expected.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError):
        return {}
    result = {"total": 0, "matches_original": 0, "by_kind": {}}
    for probe in probes:
        if probe["id"] not in answers or time.monotonic() > deadline - MARGIN_SEC:
            continue
        kind = probe.get("kind", "?").split(":", 1)[0]
        tally = result["by_kind"].setdefault(kind, {"total": 0, "matches": 0})
        try:
            if owner is not None:
                reset(owner[0])
            got = runcases.run_case([str(program)], probe, prefix=prefix, owner=owner)
        except Exception:  # noqa: BLE001
            continue
        result["total"] += 1
        tally["total"] += 1
        if runcases.matches(got, answers[probe["id"]]):
            result["matches_original"] += 1
            tally["matches"] += 1
    return result


def grade(program: Path, private: Path, prefix: list[str], owner: tuple[int, int] | None,
          deadline: float | None = None) -> dict:
    """Run every private case through `prefix` (as `owner`) and count exact matches, starting no
    case, and no reset, within MARGIN_SEC of `deadline` (time.monotonic(); by default TOTAL_SEC
    from now): the cases left count as failed. The cleanup after the last case is the caller's.

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
               "timeouts": 0, "output_limits": 0, "memory_limits": 0, "disk_limits": 0, "file_limits": 0,
               "setup_errors": 0, "limit_retries": 0, "stall_retries": 0, "seconds_total": 0.0, "reset_seconds": 0.0,
               "seconds_max": 0.0,
               "stopped": None, "notes": [], "by_kind": {}, "diagnostics": dict.fromkeys(NEAR_MISS, 0)}
    try:
        metrics["recording"] = json.loads((private / "recording.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    kind = lambda case: case.get("kind", "?")  # noqa: E731
    area = lambda case: case.get("area", "cli")  # noqa: E731
    metrics["by_area"] = {}
    for case in cases:
        metrics["by_kind"].setdefault(kind(case), {"total": 0, "run": 0, "passed": 0, "failed": 0})["total"] += 1
        metrics["by_area"].setdefault(area(case), {"total": 0, "passed": 0})["total"] += 1
    failed, seconds = [], []
    if not program.is_file() or not os.access(program, os.X_OK):
        metrics["notes"].append("/app/rebuild/carve is missing or not executable")
        cases = []
    deadline = time.monotonic() + TOTAL_SEC if deadline is None else deadline
    for case in cases:
        if time.monotonic() > deadline - MARGIN_SEC:
            metrics["stopped"] = "out of time; the remaining cases count as failed"
            break
        stop = None
        for attempt in range(2):
            try:  # whatever the submission did to this machine is its own case's failure, never an error
                if owner is not None:
                    began = time.monotonic()
                    reset(owner[0])
                    metrics["reset_seconds"] = round(metrics["reset_seconds"] + time.monotonic() - began, 3)
                    if time.monotonic() > deadline - MARGIN_SEC:
                        stop = "out of time after a cleanup; the remaining cases count as failed"
                        break
                    if low_on_disk():  # the host's or the log mount's disk, not the submission's: an error
                        if runcases.own_use(owner[0]) == (0, 0):
                            raise EvaluationError("Less than the reserved space free during grading, and the submission holds nothing")
                        stop = "out of disk space after a cleanup; the remaining cases count as failed"
                        break
                got = runcases.run_case([str(program)], case, prefix=prefix, owner=owner)
            except EvaluationError:
                raise
            except Exception as exc:  # noqa: BLE001
                got = {"exit": None, "stdout": None, "error": f"run: {type(exc).__name__}", "seconds": 0.0, "cpu": 0.0}
            if attempt:
                break
            if got.get("error") in RETRIED_LIMITS:
                metrics["limit_retries"] += 1
                continue
            if got.get("error") in ("timeout", "could not start", None) and got.get("cpu", 0.0) < STALL_CPU \
                    and not runcases.matches(got, expected[case["id"]]) and got.get("error"):
                metrics["stall_retries"] += 1
                continue
            break
        if stop is not None:
            metrics["stopped"] = stop
            break
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
        elif error in ("disk limit", "file limit"):
            metrics[error.replace(" ", "_") + "s"] += 1
        elif error:
            metrics["setup_errors"] += 1
        if runcases.matches(got, expected[case["id"]]):
            metrics["cases_passed"] += 1
            tally["passed"] += 1
            metrics["by_area"][area(case)]["passed"] += 1
        else:
            failed.append(case["id"])
            near_miss(got, expected[case["id"]], metrics["diagnostics"])
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


def final_cleanup(uid: int, until: float) -> None:
    """After the last case, before the results: end the user's processes, then sweep what it left
    and its IPC objects, best effort and only while time is left (`until`, time.monotonic())."""
    try:
        kill_user(uid)
        if time.monotonic() < until:
            remove_leftovers(uid)
        if time.monotonic() < until:
            remove_ipc(uid)
        runcases.clear_workspace()
    except Exception:  # noqa: BLE001 - the results are written whatever is left
        pass


def main() -> int:
    """Run one evaluation in this fresh container.

    Returns:
        Zero for a completed evaluation, including a failed submission; one for
        an evaluation error, which leaves no reward file.
    """
    deadline = time.monotonic() + TOTAL_SEC
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
        for closed in (tests, output, Path("/logs/artifacts")):  # the agent's artifacts: never read, never written
            if closed.is_dir() and not closed.is_symlink():
                closed.chmod(0o700)
        # The results' space, taken before any submitted code runs: written in place at the end,
        # they need no new space, however full a run leaves the disk. The reward's is a file of its
        # own, renamed onto reward.txt only at the real end: until then no reward exists, so an
        # evaluation that ends early is an error, never a 0.
        (output / ".reward.tmp").write_text("--------")
        (output / "metrics.json").write_text(json.dumps({"status": "running"}).ljust(METRICS_SPACE) + "\n")
        start_space = free_space()
        if low_on_disk():  # the environment's fault, before any submitted code: no reward at all
            raise EvaluationError(f"Less than {RESERVE_BYTES} bytes free before grading: {start_space}")
        try:  # the out-of-memory killer takes a submission's process, never this one
            Path("/proc/self/oom_score_adj").write_text("-1000")
        except OSError:
            pass
        try:  # orphans of submitted code are reparented here and reaped (kill_user)
            ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0)
        except (OSError, AttributeError):
            pass
        # What arrived, read before anything of it runs: nothing, or less than the collect hook
        # counted, is the copy failing (an error); a delivery the hook refused scores 0.
        notes, refused_delivery = delivery(SUBMISSION)
        record = delivery_record(SUBMISSION)
        notes = notes + [f"delivery: {flag}" for flag in record.get("flags", [])]
        builds = upstream_builds()
        reachable = network_open()
        if reachable is not None:  # the verifier must have no network; a provider that left it open grades nothing
            raise EvaluationError(f"The verifier can reach {reachable}; it must grade with no network")
        prefix, owner, limits = sandbox()
        refused = "the delivery was over the stated limits: not graded" if refused_delivery else None
        if refused is None:
            try:
                seal(SUBMISSION)
            except EvaluationError as exc:  # a submission that cannot be made safe to run is not run
                refused = f"{exc}: not graded"
        if refused is None:  # the original or another engine, fetched after the session: nothing of it is the agent's work
            found = fetched_build(SUBMISSION, builds)
            refused = f"{found}: not graded" if found else None
        LEFTOVER_DIRS[:] = sorted(set(LEFTOVER_DIRS) | set(writable_dirs()))
        program = identity(PROGRAM)
        if refused:
            metrics = {"cases_total": None, "cases_passed": 0, "reward": 0.0, "notes": [refused]}
        else:
            metrics = grade(PROGRAM, tests / "private", prefix, owner, deadline)
            metrics["fingerprint"] = fingerprint(PROGRAM, tests / "private", prefix, owner, deadline)
            final_cleanup(owner[0], min(deadline, time.monotonic() + CLEANUP_SEC))
        metrics["notes"] = notes + metrics["notes"]
        # Whether the pre-cap watchdog ended the session (the collect hook's record): for the audit
        # and the run log only, never a term of the reward.
        metrics["ended_by_watchdog"] = bool(record.get("ended_by_watchdog"))
        # The reward first, in its reserved place, then renamed (no new space): nothing after it
        # can cost it.
        write_in_place(output / ".reward.tmp", f"{metrics['reward']:.6f}".encode())
        os.replace(output / ".reward.tmp", output / "reward.txt")
        code = 0
        print(f"reward: {metrics['reward']:.6f} ({metrics['cases_passed']}/{metrics['cases_total']} cases)", flush=True)
        try:
            metrics.update(limits=limits, submission=program, host=recorder.host(), free_at_start=start_space,
                           free_at_end=free_space(), delivery_record=record)
            write_in_place(output / "metrics.json",
                           (json.dumps(dict(metrics, status="completed"), indent=1, sort_keys=True) + "\n").encode())
        except Exception:  # noqa: BLE001 - metadata only
            pass
    except Exception as exc:  # noqa: BLE001 - every unexpected failure invalidates the evaluation
        message = str(exc) if isinstance(exc, EvaluationError) else f"Verifier error: {type(exc).__name__}"
        print(f"evaluation error: {message}", flush=True)
        if code != 0:
            for name in REWARD_FILES + (".reward.tmp",):
                (output / name).unlink(missing_ok=True)
            try:
                write_in_place(output / "metrics.json", (json.dumps({"status": "evaluation_error", "error": message}) + "\n").encode())
            except OSError:
                pass
    finally:
        if owner is not None:  # nothing running or left behind while Harbor packs the results
            final_cleanup(owner[0], time.monotonic() + CLEANUP_SEC)
        try:
            subprocess.run(["chmod", "-R", "a+rX", str(output)], check=False)
        except OSError:
            pass
    return code


if __name__ == "__main__":
    raise SystemExit(main())
