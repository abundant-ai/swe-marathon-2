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
MARKER = Path(__file__).resolve().parent / "private" / "marker"   # the original's build marker
# Every build of BasedPL 0.1.95 upstream publishes (scripts/upstream_builds.py), and upstream's own
# usage text, which the hardened build lacks: a delivered file that is either is a fetched original.
UPSTREAM_BUILDS = Path(__file__).resolve().parent / "verifier" / "upstream_builds.json"
UNHARDENED_USAGE = b"--kernel -f CONNECTION_FILE"
# What the collect hook (environment/prepare-delivery) leaves in the delivery: its mark, whose first
# line is "delivered <entries> <bytes>" or "refused", and its record (egress, the agent's processes
# when the session ended, every entry), which goes to metrics.json and decides nothing.
DELIVERY_MARK = ".delivered"
DELIVERY_RECORD = ".delivery.json"
RECORD_LIMIT = 64 << 20  # bytes of the record read, at most
MISSING_MARK = ("the delivery arrived without the collect hook's mark (the hook did not run, or the copy was cut short); "
                "it was scored as it arrived")
MARKER_RE = re.compile(rb"BPL-BUILD-MARKER-[0-9a-f]{32}")
MARKER_LEN = len("BPL-BUILD-MARKER-") + 32
REWARD_FILES = ("reward.txt", "reward.json")
TOTAL_SEC = 4200  # the step verifier has 4,500 s; everything up to the reward file fits in this
MARGIN_SEC = 120  # no case starts when less than this is left of TOTAL_SEC
MAX_ENTRIES = 200_000  # files, directories and links in a submission, at most; more is not run
MAX_BYTES = 4 << 30    # bytes of a submission's regular files (each inode once), at most; more is not run
MAX_PROGRAM = 512 << 20  # bytes of /app/rebuild/bpl hashed for metrics.json, at most
RESERVE_BYTES = 512 << 20  # bytes kept free in /tmp and /logs/verifier: no case starts with less
CLEANUP_SEC = 60  # the cleanup after the last case, at most
RETRIED_LIMITS = ("memory limit", "disk limit", "file limit")  # a case stopped by one runs once more
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


def holds_original(top: Path, needles: dict[bytes, str], builds: dict[str, set[int]] | None = None) -> str | None:
    """Why the delivery under `top` holds the original, or None: the first regular file (links not
    followed, each inode once, `bpl` first) that contains one of `needles` (read in chunks that
    overlap by the longest needle's length), or whose sha256 is one of `builds` (sha256: sizes;
    only files of one of those sizes are hashed). seal() has bounded the bytes to read (MAX_BYTES)."""
    builds = builds or {}
    sizes = {size for found in builds.values() for size in found}
    overlap = max((len(needle) for needle in needles), default=1)
    paths, seen = [top / "bpl"], set()
    for root, directories, files in os.walk(top):
        directories.sort()
        paths += [Path(root, name) for name in sorted(files)]
    for path in paths:
        try:
            info = os.lstat(path)
            if not stat.S_ISREG(info.st_mode) or (info.st_dev, info.st_ino) in seen:
                continue
            seen.add((info.st_dev, info.st_ino))
            whole = hashlib.sha256() if info.st_size in sizes else None
            with open(path, "rb") as handle:
                tail = b""
                while chunk := handle.read(1 << 20):
                    for needle, what in needles.items():
                        if needle in tail + chunk:
                            return f"/app/rebuild/{path.relative_to(top)} holds {what}"
                    if whole is not None:
                        whole.update(chunk)
                    tail = chunk[-overlap:]
            if whole is not None and whole.hexdigest() in builds:
                return f"/app/rebuild/{path.relative_to(top)} is a build of BasedPL that upstream publishes"
        except OSError:
            continue
    return None


def upstream_builds(path: Path = UPSTREAM_BUILDS) -> dict[str, set[int]]:
    """The sha256 and sizes of upstream's published builds (verifier/upstream_builds.json).

    Raises:
        EvaluationError: The list is missing or unreadable.
    """
    try:
        builds: dict[str, set[int]] = {}
        for build in json.loads(path.read_text(encoding="utf-8"))["builds"]:
            builds.setdefault(build["sha256"], set()).add(int(build["size"]))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise EvaluationError("The list of upstream's builds is unreadable") from exc
    if not builds:
        raise EvaluationError("The list of upstream's builds is empty")
    return builds


def arrived(top: Path) -> tuple[int, int]:
    """Entries (files, directories and links; the collect hook's mark and record left out) under
    `top`, and bytes in its files (each file once, however many names it has), counted as the
    collect hook counts them."""
    entries = size = 0
    files: set[tuple[int, int]] = set()
    folders = [str(top)]
    while folders:
        folder = folders.pop()
        try:
            listing = os.scandir(folder)
        except OSError:
            continue
        with listing:
            for entry in listing:
                if folder == str(top) and entry.name in (DELIVERY_MARK, DELIVERY_RECORD):
                    continue
                try:
                    info = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                entries += 1
                if stat.S_ISDIR(info.st_mode):
                    folders.append(entry.path)
                elif stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) not in files:
                    files.add((info.st_dev, info.st_ino))
                    size += info.st_size
    return entries, size


def delivery_notes(top: Path) -> list[str]:
    """What the collect hook's mark and the copy that arrived say about the delivery.

    The hook marks every delivery before the copy, an empty one too, after bounding it and packing
    it once the way the copy packs it, so that nothing the agent leaves can make the copy fail. A
    delivery that arrived is graded as it arrived, with a note when the mark is missing or says it
    was refused.

    Raises:
        EvaluationError: Nothing arrived at all, so the copy never happened; or the mark counts
            more than arrived, so the copy was cut short, which only the platform can do.
    """
    try:
        empty = top.is_symlink() or not top.is_dir() or next(top.iterdir(), None) is None
    except OSError:
        empty = True
    if empty:
        raise EvaluationError("Nothing arrived: /app/rebuild is missing or empty, though the collect hook marks every delivery")
    mark = top / DELIVERY_MARK
    try:
        lines = mark.read_text(errors="replace").splitlines() if mark.is_file() and not mark.is_symlink() else None
    except OSError:
        lines = None
    if not lines:
        return [MISSING_MARK]
    head, notes = lines[0].split(), [f"collect hook: {line}" for line in lines[1:] if line.strip()]  # every note, no cap
    if head[:1] == ["refused"]:
        return notes or ["collect hook: the delivery was not copied"]
    if len(head) == 3 and head[0] == "delivered" and all(value.isascii() and value.isdigit() for value in head[1:]):
        entries, size = arrived(top)
        if (entries, size) != (int(head[1]), int(head[2])):
            raise EvaluationError(f"The copy arrived incomplete: {entries:,} of {int(head[1]):,} entries and {size:,} of "
                                  f"{int(head[2]):,} bytes")
        return notes
    return notes + ["the collect hook's mark could not be read; the delivery was graded as it arrived"]


def delivery_record(top: Path) -> dict:
    """The collect hook's record, cut to what metrics.json holds: whether public egress was open
    when the session ended, the agent's processes then, how many rounds of killing they took and
    how many were left, when the session and the hook started, every link the hook copied (with
    its source's path, owner, times and inode, and whether that source lies outside /app/rebuild or
    changed since the session started) or refused, every note, and a summary of the entries
    (count, latest change and modification times, `bpl`'s own entry). Never raising, and never part
    of the reward."""
    path = top / DELIVERY_RECORD
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode) or info.st_size > RECORD_LIMIT:
            return {"error": "missing, not a file, or too large"}
        record = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        listed = [item for item in record.get("entries", []) if isinstance(item, dict)]
        times = lambda key: max((item[key] for item in listed if isinstance(item.get(key), (int, float))), default=None)  # noqa: E731
        copies = [item for item in record.get("copies", []) if isinstance(item, dict)]
        return {"checked_at": record.get("checked_at"), "egress": record.get("egress"), "egress_open": record.get("egress_open"),
                "agent_process_count": record.get("agent_process_count"),
                "agent_processes": (record.get("agent_processes") or [])[:50],
                "kill_rounds": record.get("kill_rounds"), "agent_processes_left": record.get("agent_processes_left"),
                "turn_started": record.get("turn_started"), "hook_started": record.get("hook_started"),
                "delivered": record.get("delivered"), "listing_complete": record.get("listing_complete"),
                "copies": copies,
                "copies_outside_delivery": sum(1 for item in copies if item.get("outside_delivery")),
                "copies_changed_since_session_started": sum(1 for item in copies if item.get("changed_since_session_started")),
                "links": [item for item in record.get("links", []) if isinstance(item, dict)],
                "notes": [str(note) for note in record.get("notes", [])],
                "entries": len(listed), "latest_ctime": times("ctime"), "latest_mtime": times("mtime"),
                "bpl": next((item for item in listed if item.get("path") == "bpl"), None)}
    except Exception as exc:  # noqa: BLE001 - a record, never a reason to lose the reward
        return {"error": type(exc).__name__}


def identity(path: Path) -> dict:
    """A program's size, sha256, and sha256 with any build marker zeroed (as mark.py's build.txt
    gives them), read in 1 MB chunks; only for a regular file, not a link, of at most MAX_PROGRAM
    bytes, and never raising."""
    try:
        info = os.lstat(path)
        if not stat.S_ISREG(info.st_mode):
            return {"error": "not a regular file"}
        if info.st_size > MAX_PROGRAM:
            return {"size": info.st_size, "error": "too large to hash"}
        whole, zeroed, pending = hashlib.sha256(), hashlib.sha256(), b""
        with open(path, "rb") as handle:
            while chunk := handle.read(1 << 20):
                whole.update(chunk)
                pending = MARKER_RE.sub(b"BPL-BUILD-MARKER-" + b"0" * 32, pending + chunk)
                zeroed.update(pending[:-(MARKER_LEN - 1)])  # a marker cut by the chunk's end stays pending
                pending = pending[-(MARKER_LEN - 1):]
        zeroed.update(pending)
        return {"size": info.st_size, "sha256": whole.hexdigest(), "sha256_without_marker": zeroed.hexdigest()}
    except Exception as exc:  # noqa: BLE001 - metadata, never a reason to lose the reward
        return {"error": type(exc).__name__}


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


def grade(program: Path, private: Path, prefix: list[str], owner: tuple[int, int] | None,
          deadline: float | None = None) -> dict:
    """Run every private case through `prefix` (as `owner`) and count exact matches, starting no
    case, and no reset, within MARGIN_SEC of `deadline` (time.monotonic(); by default TOTAL_SEC
    from now): the cases left count as failed. The cleanup after the last case is the caller's.

    A case that cannot be set up or started, runs too long or prints too much counts as failed:
    what the submission does never makes the evaluation an error. A case stopped by the memory,
    disk or file limit runs once more after a cleanup (RETRIED_LIMITS), and the second run counts.

    Raises:
        EvaluationError: Private inputs are unreadable, or less than RESERVE_BYTES is free after a
            cleanup has removed everything the user held (the host's shortage, not the submission's).

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
               "limit_retries": 0, "setup_errors": 0, "seconds_total": 0.0, "reset_seconds": 0.0,
               "seconds_max": 0.0,
               "stopped": None, "notes": [], "by_kind": {}}
    try:
        metrics["recording"] = json.loads((private / "recording.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    kind = lambda case: case.get("kind", "?")  # noqa: E731
    for case in cases:
        metrics["by_kind"].setdefault(kind(case), {"total": 0, "run": 0, "passed": 0, "failed": 0})["total"] += 1
    failed, seconds = [], []
    if not program.is_file() or not os.access(program, os.X_OK):
        metrics["notes"].append("/app/rebuild/bpl is missing or not executable")
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
                    if low_on_disk():  # the cleanup took back all the user held: the host's shortage
                        raise EvaluationError(f"Less than {RESERVE_BYTES} bytes free after a cleanup, mid-evaluation: "
                                              f"{free_space()}")
                got = runcases.run_case([str(program)], case, prefix=prefix, owner=owner)
            except EvaluationError:  # the host's fault, found between runs: never a case's failure
                raise
            except Exception as exc:  # noqa: BLE001
                got = {"exit": None, "stdout": None, "error": f"run: {type(exc).__name__}", "seconds": 0.0}
            if attempt or got.get("error") not in RETRIED_LIMITS:
                break
            metrics["limit_retries"] += 1
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
        else:
            failed.append(case["id"])
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
    began = time.monotonic()
    deadline = began + TOTAL_SEC
    tests = Path(__file__).resolve().parent
    output = Path("/logs/verifier")
    output.mkdir(parents=True, exist_ok=True)
    for name in REWARD_FILES + ("metrics.json", ".reward.tmp"):
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
        # What arrived, before the sandbox seals it: an error when nothing did or the copy was cut
        # short; the hook's record goes to metrics.json.
        delivery, record = delivery_notes(SUBMISSION), delivery_record(SUBMISSION)
        builds = upstream_builds()
        prefix, owner, limits = sandbox()
        refused = None
        try:
            seal(SUBMISSION)
        except EvaluationError as exc:  # a submission that cannot be made safe to run is not run
            refused = f"{exc}: not graded"
        LEFTOVER_DIRS[:] = sorted(set(LEFTOVER_DIRS) | set(writable_dirs()))
        runcases.OWN_ROOTS[:] = LEFTOVER_DIRS  # where a run's own files are counted against its disk limits
        # The marker-free hash is no reason to refuse: the reference solution delivers the same
        # build with an all-zero marker, and matches it byte for byte.
        program = identity(SUBMISSION / "bpl")
        marker = MARKER.read_text(encoding="utf-8").strip() if MARKER.is_file() else ""
        if not re.fullmatch(r"[0-9a-f]{32}", marker) or marker == "0" * 32:
            raise EvaluationError("The original's build marker is missing or malformed")
        needles = {f"BPL-BUILD-MARKER-{marker}".encode(): "the original interpreter's build marker",
                   UNHARDENED_USAGE: "upstream's own usage text, which the hardened build lacks"}
        found = holds_original(SUBMISSION, needles, builds) if not refused else None
        if found:  # the original interpreter, delivered or fetched: nothing of it is the agent's work
            refused = f"{found}: not graded"
        if refused:
            metrics = {"cases_total": None, "cases_passed": 0, "reward": 0.0, "notes": [refused]}
        else:
            metrics = grade(SUBMISSION / "bpl", tests / "private", prefix, owner, deadline)
            final_cleanup(owner[0], min(deadline, time.monotonic() + CLEANUP_SEC))
        metrics["notes"] = delivery + metrics.get("notes", [])
        # The reward first, in its reserved place, then renamed (no new space): nothing after it
        # can cost it.
        write_in_place(output / ".reward.tmp", f"{metrics['reward']:.6f}".encode())
        os.replace(output / ".reward.tmp", output / "reward.txt")
        code = 0
        print(f"reward: {metrics['reward']:.6f} ({metrics['cases_passed']}/{metrics['cases_total']} cases)", flush=True)
        try:
            metrics.update(limits=limits, submission=program, host=recorder.host(), free_at_start=start_space,
                           free_at_end=free_space(), evaluation_seconds=round(time.monotonic() - began, 1),
                           delivery_record=record)
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
