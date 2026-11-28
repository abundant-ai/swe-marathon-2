"""Entry point: run the private cases against the program in /app/rebuild and write the result."""

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

from verifier import recorder, runcases

REBUILD = Path("/app/rebuild")
PROGRAM = REBUILD / "carve"
MARK = ".fsmaint"  # written into /app/rebuild by the sweep (environment/fsmaint-sweep) once the work has ended
RECORD = ".fsmaint.json"  # the sweep's record: the processes found, every entry; never scored
RECORD_LIMIT = 64 << 20  # bytes of the record read, at most
MARK_PREFIX = (
    1 << 16
)  # bytes of the mark read from its start, whatever its size: its first line decides
# Where the sweep got to, copied beside the tree as an artifact of its own from a directory only
# root could write in the agent's container: "started" from its first step, "done" once its mark,
# record and tree are in place, "stopped" when it ended itself with entries left unmeasured.
SWEEP_STATE = Path("/var/lib/fsmaint/out/sweep.json")
SWEEP_STATE_LIMIT = 8192  # bytes of it read, at most
# How every process that runs the program starts: the resource limits, then the network denied to
# it and to everything it starts (runcases.confine), whatever the machine's own network allows.
PREEXEC = runcases.confine
# Run as the program is: which socket families it may open (errno 0 where it could, else the
# errno), and whether io_uring can be set up; the network must be denied before any case runs.
NETWORK_PROBE = (
    "import ctypes, json, socket\n"
    "seen = {}\n"
    "for name in ('AF_INET', 'AF_INET6', 'AF_UNIX'):\n"
    "    try:\n"
    "        socket.socket(getattr(socket, name), socket.SOCK_STREAM).close()\n"
    "        seen[name] = 0\n"
    "    except OSError as exc:\n"
    "        seen[name] = exc.errno or -1\n"
    "params = ctypes.create_string_buffer(120)\n"
    "libc = ctypes.CDLL(None, use_errno=True)\n"
    "seen['io_uring_setup'] = 0 if libc.syscall(425, 1, params) >= 0 else ctypes.get_errno()\n"
    "print(json.dumps(seen))\n"
)
# Every build of the original that upstream publishes ready to run, and text they all hold that a
# renderer written from the specification does not (scripts/upstream_builds.py): a file in the tree
# that is one of them, or holds enough of that text, is a fetched original.
UPSTREAM_BUILDS = Path(__file__).resolve().parent / "verifier" / "upstream_builds.json"
REWARD_FILES = ("reward.txt", "reward.json")
# A tree that matches the original on at least this many fingerprint probes of one kind is the
# original, however re-encoded or wrapped, and is refused (reward 0). Of the 38 documents on which
# the original departs from the specification, renderers written from the specification match
# 2 to 9 and the original all 38; of its 11 commands outside the brief, which a renderer that
# follows the brief answers with status 2, they match none and the original nine or more.
FINGERPRINT_REFUSAL = {"disagreement": 24, "command": 5}
FINGERPRINT_KINDS = {
    "disagreement": "documents where it departs from the specification",
    "command": "commands of its own outside the brief",
}
TOTAL_SEC = 5400  # the step verifier has 6,000 s; everything up to the reward file fits in this, even every run at 2 s
MARGIN_SEC = 120  # no case starts when less than this is left of TOTAL_SEC
MAX_ENTRIES = 200_000  # entries in the tree, at most (the instruction's 200,000; its top, the mark and the record not counted); more is not run
MAX_BYTES = (
    2 << 30
)  # bytes of the tree's regular files (each inode once), at most; more is not run
MAX_PROGRAM = 512 << 20  # bytes of /app/rebuild/carve hashed for metrics.json, at most
RESERVE_BYTES = (
    512 << 20
)  # bytes kept free in /tmp and /logs/verifier: no case starts with less
CLEANUP_SEC = 60  # the cleanup after the last case, at most
RETRIED_LIMITS = (
    "memory limit",
    "disk limit",
    "file limit",
)  # a case stopped by one runs once more
STALL_CPU = 1.0  # a timeout or a failed start that used under this much CPU is a stall: run it once more
METRICS_SPACE = (
    1 << 18
)  # bytes metrics.json holds from the start, so that writing it needs no new space
# Where the unprivileged user can leave files: these, and every other world-writable directory
# that writable_dirs() finds when the evaluation starts.
LEFTOVER_DIRS = ["/tmp", "/var/tmp", "/dev/shm", "/dev/mqueue"]
SYSV_IPC = (
    ("shm", "-m"),
    ("sem", "-s"),
    ("msg", "-q"),
)  # /proc/sysvipc/<name> and ipcrm's flag for it
LIMIT_NAMES = {
    "Max stack size": resource.RLIMIT_STACK,
    "Max processes": resource.RLIMIT_NPROC,
    "Max file size": resource.RLIMIT_FSIZE,
    "Max data size": resource.RLIMIT_DATA,
    "Max core file size": resource.RLIMIT_CORE,
}
STRICT_LIMITS = ("Max processes", "Max file size", "Max core file size")
# Run as the program is: /proc/self/status, then no_new_privs as prctl(PR_GET_NO_NEW_PRIVS)
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


def sandbox_problems(
    status: str, limits: str, ids: tuple[int, int]
) -> tuple[list[str], dict]:
    """What is wrong with a process meant to run the program, from its /proc/self/status (which
    NNP_PROBE follows with a PrctlNoNewPrivs line) and /proc/self/limits, and the limits it has
    (soft values). no_new_privs holds where either the status file or prctl shows it."""
    fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    uid, gid = (str(ids[0]), str(ids[1]))
    problems = []
    if "1" not in (
        fields.get("NoNewPrivs", "").strip(),
        fields.get("PrctlNoNewPrivs", "").strip(),
    ):
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
                found[name] = line[len(name) :].split()[0]
    for name, which in LIMIT_NAMES.items():
        value = found.get(name)
        wanted = runcases.LIMITS[which]
        if name in STRICT_LIMITS and not (
            value and value.isdigit() and int(value) <= wanted
        ):
            problems.append(f"{name.lower()} is {value}, not at most {wanted}")
    return problems, found


def probe(prefix: list[str], argv: list[str], fallback: list[str] | None = None) -> str:
    """What a command prints when started exactly as the program is (PREEXEC, then `prefix`);
    where it fails and a `fallback` command is given, what that prints.

    Raises:
        EvaluationError: The command could not be started that way, or it and the fallback failed.
    """
    for command in (argv, fallback):
        if command is None:
            break
        try:
            done = subprocess.run(
                prefix + command,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
                preexec_fn=PREEXEC,
                env={"PATH": "/usr/local/bin:/usr/bin:/bin"},
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise EvaluationError(
                f"The program's sandbox could not be set up: {type(exc).__name__}: {exc}"
            ) from exc
        if done.returncode == 0:
            return done.stdout
    raise EvaluationError(
        f"Could not drop privileges: {(fallback or argv)[0]} exited {done.returncode}"
    )


def network_denied(prefix: list[str]) -> dict:
    """What a process started exactly as the program is may open (NETWORK_PROBE), which must be no
    socket but AF_UNIX's and no io_uring: the network is denied to every run whatever the machine's
    network allows, and this is the test that the denial holds.

    Raises:
        EvaluationError: The denial does not hold or could not be checked.
    """
    output = probe(prefix, [sys.executable, "-I", "-c", NETWORK_PROBE])
    try:
        seen = json.loads(output.strip().splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise EvaluationError("The network denial could not be checked") from exc
    if not isinstance(seen, dict) or not (
        seen.get("AF_INET") == runcases.EACCES
        and seen.get("AF_INET6") == runcases.EACCES
        and seen.get("AF_UNIX") == 0
        and seen.get("io_uring_setup") not in (0, None)
    ):
        raise EvaluationError(
            f"The network is not denied to the program's runs: {seen}"
        )
    return seen


def pick_id(
    maps: tuple[str, ...] = ("/proc/self/uid_map", "/proc/self/gid_map"),
) -> int:
    """An id for the program's user and group: inside every id map of this user namespace (a
    rootless or remapped container maps only 65,536 ids), drawn at random from 20000-60000 so that
    no other container is likely to share it, and no user or group of the image's; 65534 where none
    fits."""
    ranges = []
    for path in maps:
        try:
            rows = [
                tuple(map(int, line.split()[:3]))
                for line in Path(path).read_text().splitlines()
                if line.strip()
            ]
        except (OSError, ValueError):
            rows = [(0, 0, 1 << 32)]  # no map: every id
        ranges.append(rows)
    taken = set()
    for table in ("/etc/passwd", "/etc/group"):
        try:
            taken |= {
                int(line.split(":")[2])
                for line in Path(table).read_text().splitlines()
                if line.count(":") >= 2 and line.split(":")[2].isdigit()
            }
        except OSError:
            pass
    for _ in range(500):
        candidate = 20000 + secrets.randbelow(40000)
        if candidate not in taken and all(
            any(start <= candidate < start + length for start, _, length in rows)
            for rows in ranges
        ):
            return candidate
    return 65534


def sandbox() -> tuple[list[str], tuple[int, int], dict]:
    """The command prefix that runs the program as an unprivileged user of this evaluation's own
    (a random uid and gid no other container shares, so that its process limit counts only its
    own runs), those ids, and the limits such a process has. A process started the same way must
    have dropped every privilege, and a set-user-id root file started that way must gain nothing.

    Raises:
        EvaluationError: Privileges cannot be dropped or the drop does not hold.
    """
    uid = pick_id()
    ids = (uid, uid)
    if shutil.which("setpriv") is None:
        raise EvaluationError("setpriv is missing; the program was not run")
    scratch = Path(tempfile.mkdtemp())
    try:  # the workspaces will be chowned to the id: a filesystem that refuses it runs nothing
        os.chown(scratch, uid, uid)
    except OSError as exc:
        raise EvaluationError(
            f"Files cannot be given to uid {uid}: {type(exc).__name__}"
        ) from exc
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    prefix = [
        "setpriv",
        "--reuid",
        str(uid),
        "--regid",
        str(uid),
        "--clear-groups",
        "--no-new-privs",
    ]
    status = probe(
        prefix,
        [sys.executable, "-I", "-c", NNP_PROBE],
        fallback=["cat", "/proc/self/status"],
    )
    problems, found = sandbox_problems(
        status, probe(prefix, ["cat", "/proc/self/limits"]), ids
    )
    # A set-user-id and set-group-id copy of id(1), owned by root, beside the tree.
    place = REBUILD.parent / ".setid-probe"
    shutil.rmtree(place, ignore_errors=True)
    try:
        place.mkdir(mode=0o755)
        os.chmod(place, 0o755)
        shutil.copy(shutil.which("id") or "/usr/bin/id", place / "id")
        os.chown(place / "id", 0, 0)
        os.chmod(place / "id", 0o6755)
        seen = (
            probe(prefix, [str(place / "id"), "-u"]).strip(),
            probe(prefix, [str(place / "id"), "-g"]).strip(),
        )
    finally:
        shutil.rmtree(place, ignore_errors=True)
    if seen != (str(uid), str(uid)):
        problems.append(f"a set-id root file ran with user and group {seen}")
    if problems:
        raise EvaluationError(
            "The unprivileged run does not hold: " + "; ".join(problems)
        )
    return prefix, ids, found


def seal(top: Path, ids: tuple[int, int] = (0, 0)) -> None:
    """Make the tree `ids`'s and read-only for anyone else, before any of it runs: no
    set-user-id, set-group-id or sticky bit, executables 0755, other files 0644, directories 0755.
    Links are left as they are and never followed; devices, pipes and sockets are removed. Entries
    are counted as they are read, the sweep's mark and record aside, and the walk stops at
    MAX_ENTRIES. The sweep refuses a tree over its limits before the copy, counting the same way,
    so a tree over them here is one the copy changed.

    Raises:
        EvaluationError: The tree holds more than MAX_ENTRIES entries or MAX_BYTES bytes of
            files, or an entry can be neither sealed nor removed.
    """
    if not top.is_dir() or top.is_symlink():
        return
    own = {str(top / MARK), str(top / RECORD)}
    entries, size, seen, todo, counted = [top], 0, set(), [top], 0
    while todo:
        try:
            listing = os.scandir(todo.pop())
        except OSError:
            continue
        with listing:
            for entry in listing:
                entries.append(Path(entry.path))
                if entry.path in own:
                    continue
                counted += 1
                if counted > MAX_ENTRIES:
                    raise EvaluationError(
                        f"The tree holds more than {MAX_ENTRIES} entries"
                    )
                try:
                    info = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                if stat.S_ISDIR(info.st_mode):
                    todo.append(Path(entry.path))
                elif (
                    stat.S_ISREG(info.st_mode)
                    and (info.st_dev, info.st_ino) not in seen
                ):
                    seen.add((info.st_dev, info.st_ino))
                    size += info.st_size
                    if size > MAX_BYTES:
                        raise EvaluationError(
                            f"The tree's files hold more than {MAX_BYTES} bytes"
                        )
    for path in entries:
        try:
            info = os.lstat(path)
            if stat.S_ISLNK(info.st_mode):
                os.lchown(path, *ids)
            elif stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode):
                os.lchown(path, *ids)
                os.chmod(
                    path,
                    0o755
                    if stat.S_ISDIR(info.st_mode) or info.st_mode & 0o111
                    else 0o644,
                )
            else:
                os.unlink(path)
        except OSError as exc:
            try:
                runcases.remove_path(path)
            except OSError:
                raise EvaluationError(
                    f"Could not seal the tree: {type(exc).__name__}"
                ) from exc


def as_user(uid: int, argv: list[str], timeout: float) -> None:
    """Run a command as `uid` (and its group), only where root can drop to it and it is not this
    process's own uid (a kill -1 as oneself would end the evaluation)."""
    if os.geteuid() != 0 or uid == os.geteuid() or shutil.which("setpriv") is None:
        return
    try:
        subprocess.run(
            [
                "setpriv",
                "--reuid",
                str(uid),
                "--regid",
                str(uid),
                "--clear-groups",
                "--",
                *argv,
            ],
            capture_output=True,
            check=False,
            timeout=timeout,
        )
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
            entries = [
                entry.name for entry in os.scandir("/proc") if entry.name.isdigit()
            ]
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
                found = found or any(
                    Path(f"/proc/{pid}/task/{task.name}/stat")
                    .read_bytes()
                    .rsplit(b")", 1)[1]
                    .split()[0]
                    not in (b"Z", b"X")
                    for task in os.scandir(f"/proc/{pid}/task")
                )
            except (OSError, IndexError):
                found = True  # a task that vanished while read: look again
        reap()
        if not found:
            return
        time.sleep(0.01)


def reap() -> None:
    """Reap the exit of every child this process has (orphans included, as their subreaper)."""
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return


def writable_dirs(root: str = "/") -> list[str]:
    """Every directory under `root` that anyone may write to, not following links and leaving out
    the kernel's own trees: where a tree could leave a file for a later case."""
    found = []
    for top, directories, _ in os.walk(root):
        if (
            top == root
        ):  # the kernel's trees, and /logs, which holds the session's own files
            directories[:] = [
                d for d in directories if d not in ("proc", "sys", "dev", "logs")
            ]
        if os.path.realpath(top) == str(REBUILD):  # sealed: nothing in it is writable
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
    ids may do and which finds them without /proc/sysvipc), then as root, which may lack the
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
            if (
                str(uid) in (values.get("uid"), values.get("cuid"))
                and values.get(columns[1], "").isdigit()
            ):
                ids.append(values[columns[1]])
        for at in range(0, len(ids), 2000):  # one ipcrm for many objects
            try:
                subprocess.run(
                    ["ipcrm", *(arg for i in ids[at : at + 2000] for arg in (flag, i))],
                    capture_output=True,
                    check=False,
                    timeout=60,
                )
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
            subprocess.run(
                [
                    "find",
                    top,
                    "-xdev",
                    "-mindepth",
                    "1",
                    "-maxdepth",
                    "1",
                    "-user",
                    str(uid),
                    "-exec",
                    "rm",
                    "-rf",
                    "--",
                    "{}",
                    "+",
                ],
                capture_output=True,
                check=False,
                timeout=300,
            )
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
    except Exception as exc:  # noqa: BLE001 - Handle failures at the task boundary.
        return {"error": type(exc).__name__}


def arrived(top: Path) -> tuple[int, int]:
    """The entries below `top` (files, directories and links, the mark aside) and the bytes of its
    regular files, each inode once, counted the way the sweep counts them; never following
    a link, and stopping once past MAX_ENTRIES (the count is then only a bound)."""
    entries, size, files, folders = 0, 0, set(), [str(top)]
    skipped = {str(top / MARK), str(top / RECORD)}
    while folders and entries <= MAX_ENTRIES:
        with os.scandir(folders.pop()) as listing:
            for entry in listing:
                if entry.path in skipped:
                    continue
                info = entry.stat(follow_symlinks=False)
                entries += 1
                if stat.S_ISDIR(info.st_mode):
                    folders.append(entry.path)
                elif (
                    stat.S_ISREG(info.st_mode)
                    and (info.st_dev, info.st_ino) not in files
                ):
                    files.add((info.st_dev, info.st_ino))
                    size += info.st_size
    return entries, size


def sweep_state(path: Path | None = None) -> dict | None:
    """Where the sweep got to (SWEEP_STATE): a JSON object, or None where none arrived or it cannot
    be read. Read in a bounded way; never raising."""
    path = SWEEP_STATE if path is None else path
    try:
        if not path.is_file() or path.is_symlink():
            return None
        with open(path, "rb") as handle:
            state = json.loads(handle.read(SWEEP_STATE_LIMIT).decode("utf-8"))
        return state if isinstance(state, dict) else None
    except (OSError, ValueError):
        return None


def manifest(top: Path) -> tuple[list[str], bool]:
    """What the sweep's mark, the copy that arrived and where the sweep got to say about the tree:
    notes, and whether it was refused (reward 0). The mark is read from its start, MARK_PREFIX bytes
    at most, whatever its size.

    The sweep writes that it has begun (SWEEP_STATE) before anything else, puts a mark that says
    `refused` into /app/rebuild once the session's processes are frozen, moves the tree out to
    measure it, takes out what a copy cannot carry (devices, pipes, sockets, paths over 2,048 bytes,
    links that do not lead to a file or a directory inside it; every link kept is a relative path
    that stays inside), puts back, under a mark that counts it, only a tree within the limits that
    the disk has room to pack, and only then writes that it is done. So:
    - a sweep that began and did not say it was done, or said it stopped, left a tree it had not
      measured, whose copy may stop on what the sweep would have taken out: whatever arrived is
      refused, with a note;
    - after a sweep that was done, a missing or short arrival is the copy or the machine failing,
      an error, unless processes of the session were still alive when it finished (then refused);
    - with no word from the sweep at all (it never ran, or its file was not copied), the mark alone
      decides, and a missing or short arrival is an error.

    Raises:
        EvaluationError: Nothing arrived at all, the copy arrived cut short or cannot be measured,
            or there is no mark the sweep wrote, and the sweep had finished or said nothing.
    """
    state = sweep_state()
    stage = state.get("stage") if state else None
    if stage in ("started", "stopped"):
        return [
            (
                f"sweep: the sweep {'began' if stage == 'started' else 'stopped'} and did not finish: "
                "what arrived was not measured"
            )
        ], True
    try:
        return mark_says(top)
    except EvaluationError as exc:
        if stage == "done" and state.get("processes_left") != 0:
            return [
                (
                    f"sweep: {exc}, and processes of the session were alive when the sweep finished "
                    f"({state.get('processes_left')})"
                )
            ], True
        raise


def mark_says(top: Path) -> tuple[list[str], bool]:
    """What the sweep's mark and the copy that arrived say about the tree (manifest() without where
    the sweep got to).

    Raises:
        EvaluationError: Nothing arrived at all, the copy arrived cut short or cannot be measured,
            or there is no mark the sweep wrote.
    """
    try:
        empty = (
            top.is_symlink() or not top.is_dir() or next(top.iterdir(), None) is None
        )
    except OSError:
        empty = True
    if empty:
        raise EvaluationError(
            "Nothing arrived: /app/rebuild is missing or empty, though the sweep marks every tree"
        )
    mark = top / MARK
    lines = None
    try:
        if mark.is_file() and not mark.is_symlink():
            with open(mark, "rb") as handle:
                lines = (
                    handle.read(MARK_PREFIX)
                    .decode("utf-8", "replace")
                    .splitlines()[:40]
                )
    except OSError:
        lines = None
    if not lines:
        raise EvaluationError("The tree arrived without the sweep's mark")
    head, notes = (
        lines[0].split(),
        [f"sweep: {line}" for line in lines[1:] if line.strip()][:20],
    )
    if head[:1] == ["refused"]:
        return (notes or ["sweep: the tree was not copied"]), True
    if (
        len(head) == 3
        and head[0] == "listed"
        and all(value.isascii() and value.isdigit() for value in head[1:])
    ):
        try:
            entries, size = arrived(top)
        except OSError as exc:
            raise EvaluationError(
                f"The tree could not be measured: {type(exc).__name__}"
            ) from exc
        if entries < int(head[1]) or size < int(head[2]):
            raise EvaluationError(
                f"The copy arrived cut short: {entries:,} of {int(head[1]):,} entries and {size:,} of "
                f"{int(head[2]):,} bytes"
            )
        return notes, False
    raise EvaluationError("The sweep's mark cannot be read")


def manifest_record(top: Path) -> dict:
    """What the sweep's record says, for metrics.json and review: the processes alive when the
    session ended, how many passes of ending ended them, the entries changed after the end of the
    work (kept, and flagged here), and the tree's entries (their number and the twenty with the
    latest change times). Read in a bounded way; never raising, never scored."""
    try:
        path = top / RECORD
        if (
            not path.is_file()
            or path.is_symlink()
            or path.stat().st_size > RECORD_LIMIT
        ):
            return {"error": "no readable record"}
        record = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        entries = record.get("entries") or []
        latest = sorted(
            (item for item in entries if isinstance(item, dict)),
            key=lambda item: -float(item.get("ctime") or 0),
        )
        summary = {
            key: record.get(key)
            for key in (
                "process_count",
                "kill_passes",
                "processes_left",
                "threads_left",
                "listed",
                "listing_complete",
                "end_bound",
                "end_from",
                "sweep_started_at",
                "late_entries",
                "late_paths",
                "ending",
                "logs_artifacts",
            )
        }
        summary |= {
            "processes": (record.get("processes") or [])[:50],
            "entries_listed": len(entries),
            "copies": record.get("copies", []),
            "refused_copies": record.get("refused_copies", []),
            "latest_changes": [
                {
                    key: item.get(key)
                    for key in ("path", "type", "size", "ctime", "sha256")
                }
                for item in latest[:20]
            ],
        }
        flags = []
        if record.get("processes_left"):
            flags.append(
                f"{record.get('processes_left')} threads of the session survived the kill"
            )
        if record.get("threads_left"):
            flags.append(
                f"{record.get('threads_left')} threads of the session were alive when the tree was to be listed"
            )
        if record.get("late_entries"):
            flags.append(
                f"{record.get('late_entries')} entries changed after the end of the work ({record.get('end_from')}); "
                "kept: review them"
            )
        if record.get("copies"):
            flags.append(
                f"{len(record['copies'])} files were copied in from links out of /app/rebuild"
            )
        flagged = [
            copy
            for copy in (record.get("copies") or [])
            if isinstance(copy, dict) and copy.get("flagged")
        ]
        if flagged:
            flags.append(
                f"{len(flagged)} copies hold files changed after the end of the work; kept: review them"
            )
        if record.get("end_from") == "limit":
            flags.append(
                "the work ran to its time limit; the end bound is its start plus that limit"
            )
        ending = record.get("ending") if isinstance(record.get("ending"), dict) else {}
        if "processes_left" in record and record.get("processes_left") is None:
            flags.append(
                "how many threads were left alive is unknown: a listing did not answer"
            )
        if ending.get("freeze_ran_out") is True or ending.get("kill_ran_out") is True:
            flags.append(
                "the freezing or the ending of the processes ran out of time: review the processes"
            )
        left_behind = (
            record.get("logs_artifacts")
            if isinstance(record.get("logs_artifacts"), dict)
            else {}
        )
        if left_behind.get("entries"):
            flags.append(
                f"{left_behind.get('entries')} entries in /logs/artifacts were set aside before the copy"
            )
        summary["flags"] = flags
        return summary
    except Exception as exc:  # noqa: BLE001 - Handle failures at the task boundary.
        return {"error": type(exc).__name__}


def upstream_builds(path: Path = UPSTREAM_BUILDS) -> dict:
    """The sha256 of upstream's published builds and of the other engines, the carve-rs text that
    marks a build, the markers of foreign language runtimes, and how many of each make a file
    in the tree a fetched engine (verifier/upstream_builds.json).

    Raises:
        EvaluationError: The list is unreadable or empty.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        builds = {
            "hashes": set(data["sha256"]),
            "strings": [text.encode() for text in data["strings"]],
            "strings_needed": int(data["strings_needed"]),
            "runtimes": {
                name: [marker.encode() for marker in markers]
                for name, markers in data.get("runtimes", {}).items()
            },
            "runtime_needed": int(data.get("runtime_markers_needed", 2)),
        }
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
    strings, hashes, needed = (
        builds["strings"],
        builds["hashes"],
        builds["strings_needed"],
    )
    runtimes, runtime_needed = builds["runtimes"], builds["runtime_needed"]
    markers = [(name, marker) for name, group in runtimes.items() for marker in group]
    overlap = max(
        (len(text) for text in strings + [marker for _, marker in markers]), default=1
    )
    skip = {str(top / MARK), str(top / RECORD)}
    seen = set()
    for root, directories, files in os.walk(top):
        directories.sort()
        for name in sorted(files):
            path = Path(root, name)
            try:
                info = os.lstat(path)
                if (
                    not stat.S_ISREG(info.st_mode)
                    or (info.st_dev, info.st_ino) in seen
                    or str(path) in skip
                ):
                    continue
                seen.add((info.st_dev, info.st_ino))
                whole, found, runtime_hits, tail = hashlib.sha256(), set(), {}, b""
                with open(path, "rb") as handle:
                    while chunk := handle.read(1 << 20):
                        whole.update(chunk)
                        window = tail + chunk
                        found.update(
                            index
                            for index, text in enumerate(strings)
                            if text in window
                        )
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


def free_space() -> dict:
    """The bytes free in /tmp and /logs/verifier, -1 where a filesystem reports no size."""
    return {
        str(place): runcases.disk_free(place)[0]
        for place in (runcases.WORKSPACE.parent, Path("/logs/verifier"))
    }


def low_on_disk() -> bool:
    """Whether /tmp or /logs/verifier has less than RESERVE_BYTES free (what is needed to fetch
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


NEAR_MISS = (
    "exit_right_stdout_wrong",
    "equal_collapsing_whitespace",
    "equal_sorting_attributes",
    "equal_text_only",
)
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
    """Record, without scoring, how close a failed answer is to the expected one."""
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


def fingerprint(
    program: Path,
    private: Path,
    prefix: list[str],
    ids: tuple[int, int] | None,
) -> dict:
    """Run the program on every fingerprint probe and count, by kind, how many match the
    original's answer: `disagreement` probes are documents on which the original departs from the
    specification, `command` probes are the original's own commands outside the brief. A renderer
    written from the specification matches few of either; the original, however re-encoded or
    wrapped, matches nearly all of the documents. Every probe runs, whatever the time: there are
    few, and each has the 2 s of a case. A probe the program cannot run matches nothing.

    Raises:
        EvaluationError: The probes or their recorded answers are unreadable or do not match.
    """
    try:
        probes = json.loads((private / "probes.json").read_text(encoding="utf-8"))[
            "probes"
        ]
        answers = json.loads(
            (private / "probes_expected.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise EvaluationError("The fingerprint probes are unreadable") from exc
    if not probes or any(probe["id"] not in answers for probe in probes):
        raise EvaluationError(
            "The fingerprint probes and their recorded answers do not match"
        )
    result = {"total": 0, "matches_original": 0, "by_kind": {}}
    for probe in probes:
        kind = probe.get("kind", "?").split(":", 1)[0]
        tally = result["by_kind"].setdefault(kind, {"total": 0, "matches": 0})
        result["total"] += 1
        tally["total"] += 1
        try:
            if ids is not None:
                reset(ids[0])
            got = runcases.run_case(
                [str(program)], probe, prefix=prefix, ids=ids, preexec=PREEXEC
            )
        except Exception:  # noqa: BLE001, S112 - A probe that cannot run matches nothing.
            continue
        if runcases.matches(got, answers[probe["id"]]):
            result["matches_original"] += 1
            tally["matches"] += 1
    return result


def fingerprint_refusal(result: dict) -> str | None:
    """Why a tree is refused as the original by its fingerprint (`fingerprint`): it matches the
    original on at least FINGERPRINT_REFUSAL of the probes of one kind; None otherwise."""
    by_kind = result.get("by_kind", {})
    matched = {
        kind: by_kind.get(kind, {}).get("matches", 0) for kind in FINGERPRINT_REFUSAL
    }
    if all(matched[kind] < most for kind, most in FINGERPRINT_REFUSAL.items()):
        return None
    counts = ", ".join(
        f"{matched[kind]} of the {by_kind.get(kind, {}).get('total', 0)} {FINGERPRINT_KINDS[kind]}"
        for kind in FINGERPRINT_REFUSAL
    )
    return (
        f"the tree matches carve-rs 0.1.14 on {result.get('matches_original', 0)} of "
        f"{result.get('total', 0)} probes ({counts}): not run"
    )


def run_cases(
    program: Path,
    private: Path,
    prefix: list[str],
    ids: tuple[int, int] | None,
    cutoff_at: float | None = None,
) -> dict:
    """Run every private case through `prefix` (as `ids`) and count exact matches, starting no
    case, and no reset, within MARGIN_SEC of `cutoff_at` (time.monotonic(); by default TOTAL_SEC
    from now): the cases left count as failed. The cleanup after the last case is the caller's.

    A case that cannot be set up or started, runs too long or prints too much counts as failed:
    what the tree does never makes the evaluation an error.

    Raises:
        EvaluationError: Private inputs are unreadable.
    """
    try:
        cases = json.loads((private / "cases.json").read_text(encoding="utf-8"))[
            "cases"
        ]
        expected = json.loads((private / "expected.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, KeyError) as exc:
        raise EvaluationError("Private cases are unreadable") from exc
    if not cases or any(case["id"] not in expected for case in cases):
        raise EvaluationError("Private cases and recorded answers do not match")
    metrics = {
        "cases_total": len(cases),
        "cases_run": 0,
        "cases_passed": 0,
        "cases_failed": 0,
        "reward": 0.0,
        "timeouts": 0,
        "output_limits": 0,
        "memory_limits": 0,
        "disk_limits": 0,
        "file_limits": 0,
        "setup_errors": 0,
        "limit_retries": 0,
        "stall_retries": 0,
        "seconds_total": 0.0,
        "reset_seconds": 0.0,
        "seconds_max": 0.0,
        "stopped": None,
        "notes": [],
        "by_kind": {},
        "diagnostics": dict.fromkeys(NEAR_MISS, 0),
    }
    try:
        metrics["recording"] = json.loads(
            (private / "recording.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        pass
    kind = lambda case: case.get("kind", "?")
    area = lambda case: case.get("area", "cli")
    metrics["by_area"] = {}
    for case in cases:
        metrics["by_kind"].setdefault(
            kind(case), {"total": 0, "run": 0, "passed": 0, "failed": 0}
        )["total"] += 1
        metrics["by_area"].setdefault(area(case), {"total": 0, "passed": 0})[
            "total"
        ] += 1
    failed, seconds = [], []
    if not program.is_file() or not os.access(program, os.X_OK):
        metrics["notes"].append("/app/rebuild/carve is missing or not executable")
        cases = []
    cutoff_at = time.monotonic() + TOTAL_SEC if cutoff_at is None else cutoff_at
    for case in cases:
        if time.monotonic() > cutoff_at - MARGIN_SEC:
            metrics["stopped"] = "out of time; the remaining cases count as failed"
            break
        stop = None
        for retry in range(2):
            try:  # whatever the tree did to this machine is its own case's failure, never an error
                if ids is not None:
                    began = time.monotonic()
                    reset(ids[0])
                    metrics["reset_seconds"] = round(
                        metrics["reset_seconds"] + time.monotonic() - began, 3
                    )
                    if time.monotonic() > cutoff_at - MARGIN_SEC:
                        stop = "out of time after a cleanup; the remaining cases count as failed"
                        break
                    if (
                        low_on_disk()
                    ):  # the host's or the log mount's disk, not the tree's: an error
                        if runcases.own_use(ids[0]) == (0, 0):
                            raise EvaluationError(
                                "Less than the reserved space free during the run, and the tree holds nothing"
                            )
                        stop = "out of disk space after a cleanup; the remaining cases count as failed"
                        break
                got = runcases.run_case(
                    [str(program)], case, prefix=prefix, ids=ids, preexec=PREEXEC
                )
            except EvaluationError:
                raise
            except Exception as exc:  # noqa: BLE001 - Handle failures at the task boundary.
                got = {
                    "exit": None,
                    "stdout": None,
                    "error": f"run: {type(exc).__name__}",
                    "seconds": 0.0,
                    "cpu": 0.0,
                }
            if retry:
                break
            if got.get("error") in RETRIED_LIMITS:
                metrics["limit_retries"] += 1
                continue
            if (
                got.get("error") in ("timeout", "could not start", None)
                and got.get("cpu", 0.0) < STALL_CPU
                and not runcases.matches(got, expected[case["id"]])
                and got.get("error")
            ):
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
    except Exception:  # noqa: BLE001, S110 - Best-effort cleanup or optional evidence.
        pass


def main() -> int:
    """Run one evaluation in this fresh container.

    Returns:
        Zero for a completed evaluation, including a failed tree; one for
        an evaluation error, which leaves no reward file.
    """
    cutoff_at = time.monotonic() + TOTAL_SEC
    tests = Path(__file__).resolve().parent
    output = Path("/logs/verifier")
    output.mkdir(parents=True, exist_ok=True)
    for name in REWARD_FILES + ("metrics.json",):
        (output / name).unlink(missing_ok=True)
    code = 1
    ids = None
    try:
        if os.geteuid() != 0:
            raise EvaluationError("Verifier must start as root to isolate the program")
        for closed in (
            tests,
            output,
            Path("/logs/artifacts"),
            SWEEP_STATE.parent,
        ):  # /logs/artifacts: never read, never written
            if closed.is_dir() and not closed.is_symlink():
                closed.chmod(0o700)
        # The results' space, taken before any the program runs: written in place at the end,
        # they need no new space, however full a run leaves the disk. The reward's is a file of its
        # own, renamed onto reward.txt only at the real end: until then no reward exists, so an
        # evaluation that ends early is an error, never a 0.
        (output / ".reward.tmp").write_text("--------")
        (output / "metrics.json").write_text(
            json.dumps({"status": "running"}).ljust(METRICS_SPACE) + "\n"
        )
        start_space = free_space()
        if (
            low_on_disk()
        ):  # the environment's fault, before any the program: no reward at all
            raise EvaluationError(
                f"Less than {RESERVE_BYTES} bytes free before the run: {start_space}"
            )
        try:  # the out-of-memory killer takes a tree's process, never this one
            Path("/proc/self/oom_score_adj").write_text("-1000")
        except OSError:
            pass
        try:  # orphans of the program are reparented here and reaped (kill_user)
            ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0)
        except (OSError, AttributeError):
            pass
        # What arrived, read before anything of it runs: nothing, or less than the sweep
        # counted, is the copy or the machine failing (an error); a tree the sweep refused scores 0.
        notes, refused_tree = manifest(REBUILD)
        record = manifest_record(REBUILD)
        notes = notes + [f"sweep: {flag}" for flag in record.get("flags", [])]
        builds = upstream_builds()
        prefix, ids, limits = sandbox()
        # Every run of the program is denied the network (PREEXEC); a denial that does not hold is
        # an error before anything of the tree runs, whatever the machine's own network is.
        network = network_denied(prefix)
        refused = "the sweep refused the tree: not run" if refused_tree else None
        if refused is None:
            try:
                seal(REBUILD)
            except (
                EvaluationError
            ) as exc:  # a tree that cannot be made safe to run is not run
                refused = f"{exc}: not run"
        if (
            refused is None
        ):  # a published build of the original or another engine, or a runtime
            found = fetched_build(REBUILD, builds)
            refused = f"{found}: not run" if found else None
        LEFTOVER_DIRS[:] = sorted(set(LEFTOVER_DIRS) | set(writable_dirs()))
        program = identity(PROGRAM)
        probes = None
        if (
            refused is None
        ):  # the original however re-encoded or wrapped, by how it behaves
            probes = fingerprint(PROGRAM, tests / "private", prefix, ids)
            refused = fingerprint_refusal(probes)
        if refused:
            metrics = {
                "cases_total": None,
                "cases_passed": 0,
                "reward": 0.0,
                "notes": [refused],
            }
        else:
            metrics = run_cases(PROGRAM, tests / "private", prefix, ids, cutoff_at)
        if probes is not None:
            metrics["fingerprint"] = probes
            final_cleanup(ids[0], min(cutoff_at, time.monotonic() + CLEANUP_SEC))
        metrics["notes"] = notes + metrics["notes"]
        # The reward first, in its reserved place, then renamed (no new space): nothing after it
        # can cost it.
        write_in_place(output / ".reward.tmp", f"{metrics['reward']:.6f}".encode())
        os.replace(output / ".reward.tmp", output / "reward.txt")
        code = 0
        print(
            f"reward: {metrics['reward']:.6f} ({metrics['cases_passed']}/{metrics['cases_total']} cases)",
            flush=True,
        )
        try:
            metrics.update(
                limits=limits,
                network=network,
                program=program,
                host=recorder.host(),
                free_at_start=start_space,
                free_at_end=free_space(),
                manifest_record=record,
                sweep_state=sweep_state(),
            )
            write_in_place(
                output / "metrics.json",
                (
                    json.dumps(
                        dict(metrics, status="completed"), indent=1, sort_keys=True
                    )
                    + "\n"
                ).encode(),
            )
        except Exception:  # noqa: BLE001, S110 - Best-effort cleanup or optional evidence.
            pass
    except Exception as exc:  # noqa: BLE001 - Handle failures at the task boundary.
        message = (
            str(exc)
            if isinstance(exc, EvaluationError)
            else f"Verifier error: {type(exc).__name__}"
        )
        print(f"evaluation error: {message}", flush=True)
        if code != 0:
            for name in REWARD_FILES + (".reward.tmp",):
                (output / name).unlink(missing_ok=True)
            try:
                write_in_place(
                    output / "metrics.json",
                    (
                        json.dumps({"status": "evaluation_error", "error": message})
                        + "\n"
                    ).encode(),
                )
            except OSError:
                pass
    finally:
        if (
            ids is not None
        ):  # nothing running or left behind while the results are packed
            final_cleanup(ids[0], time.monotonic() + CLEANUP_SEC)
        try:
            subprocess.run(["chmod", "-R", "a+rX", str(output)], check=False)
        except OSError:
            pass
    return code


if __name__ == "__main__":
    raise SystemExit(main())
