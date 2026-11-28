"""Child processes of the grader: bounded output capture, and ending what a user leaves behind.

/proc is read as bytes, since a process may give itself any name, and every thread of every
process is looked at whatever its state: a process whose first thread has exited still runs in
its other threads. A user's processes are stopped, then killed, by root, which they can neither
block nor outrun; a child that has dropped to the user's uid also sends the stop and the kill to
all of them in one system call, which a process that forks cannot race. Trees are removed by GNU
`rm`, which walks by directory descriptor and so has no depth limit.
"""

from __future__ import annotations

import ctypes
import os
import pwd
import select
import signal
import subprocess
import time

from .contracts import EvaluationError

CHUNK = 1 << 16
PR_SET_CHILD_SUBREAPER = 36
IPC_RMID = 0
# The directories every user may write to, besides a run's own.
SHARED_DIRS = ("/tmp", "/var/tmp", "/dev/shm", "/run/lock", "/dev/mqueue")
SWEEP_SECONDS = 10.0
REMOVE_SECONDS = 300
GONE = (
    b"Z",
    b"X",
)  # a zombie holds nothing and runs nothing; a dead task is on its way out
STOPPED = (b"T", b"t")
# user -> how many of its processes were still alive, and ended, once a run or the build was over
LEFTOVERS: dict[str, int] = {}


def uid_gid(user: str) -> tuple[int, int]:
    entry = pwd.getpwnam(user)
    return entry.pw_uid, entry.pw_gid


def become_subreaper() -> bool:
    """Adopt every orphaned descendant instead of PID 1, so that reap() collects what a run or the
    build leaves behind wherever the grader runs (PID 1 of the grading machine may never reap,
    and unreaped processes still count against the user's process limit)."""
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        return libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) == 0
    except (OSError, AttributeError):
        return False


def protect_self() -> bool:
    """Make this process the kernel's last choice when memory runs out, so a flood of the
    submission's processes is ended before the grader is (they start at the other end)."""
    try:
        with open("/proc/self/oom_score_adj", "w") as f:
            f.write("-1000")
        return True
    except OSError:
        return False


def expendable() -> None:
    """In a child, before it runs submitted code and while it is still root: the kernel's first
    choice when memory runs out. (After the uid changes the process is no longer dumpable, so
    its /proc files are root's and it could not write its own score; the drop comes after.)"""
    try:
        with open("/proc/self/oom_score_adj", "w") as f:
            f.write("1000")
    except OSError:
        pass


def drop_to(user: str) -> None:
    """In a child, last before exec: become `user`, with no supplementary groups."""
    uid, gid = uid_gid(user)
    os.setgroups([])
    os.setgid(gid)
    os.setuid(uid)


def capture(
    proc: subprocess.Popen, timeout: float, cap: int
) -> tuple[bytes, bool, bool]:
    """Read `proc`'s standard output until it closes, the timeout passes, or more than `cap`
    bytes arrive. Return (the first `cap` bytes at most, timed out, over the cap)."""
    assert proc.stdout is not None
    fd = proc.stdout.fileno()
    deadline = time.monotonic() + timeout
    parts: list[bytes] = []
    size = 0
    while True:
        left = deadline - time.monotonic()
        if left <= 0:
            return b"".join(parts), True, False
        ready, _, _ = select.select([fd], [], [], min(left, 1.0))
        if not ready:
            continue
        data = os.read(fd, CHUNK)
        if not data:
            break
        size += len(data)
        if size > cap:
            return b"".join(parts), False, True
        parts.append(data)
    remaining = max(0.0, deadline - time.monotonic())
    try:
        proc.wait(timeout=remaining)
    except subprocess.TimeoutExpired:
        return b"".join(parts), True, False
    return b"".join(parts), False, False


def end_group(proc: subprocess.Popen) -> None:
    """Kill the process group `proc` leads, then reap it."""
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    try:
        proc.wait(timeout=60)
    except subprocess.TimeoutExpired as exc:
        raise EvaluationError(f"killed process {proc.pid} did not exit") from exc


def reap() -> None:
    """Collect every child that has exited, orphans this process adopted included."""
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return


def _fields(path: bytes) -> dict[bytes, bytes] | None:
    try:
        with open(path, "rb") as f:
            data = f.read(16384)
    except OSError:
        return None
    out: dict[bytes, bytes] = {}
    for line in data.split(b"\n"):
        key, sep, value = line.partition(b":")
        if sep and key not in out:
            out[key] = value.strip()
    return out


def _owned(fields: dict[bytes, bytes] | None, uid: int) -> bytes | None:
    """The task's state when any of its real, effective, saved or filesystem uids is `uid`."""
    if fields is None:
        return None
    try:
        uids = {int(x) for x in fields.get(b"Uid", b"").split()}
    except ValueError:
        return None
    if uid not in uids:
        return None
    return (fields.get(b"State", b"?").split() or [b"?"])[0]


def tasks_of(uid: int) -> list[tuple[int, int, bytes]]:
    """(process id, thread id, state) of every thread in /proc that runs as `uid`, in any
    state."""
    found: list[tuple[int, int, bytes]] = []
    try:
        pids = os.listdir(b"/proc")
    except OSError:
        return found
    for pid in pids:
        if not pid.isdigit():
            continue
        base = b"/proc/" + pid
        try:
            tids = [t for t in os.listdir(base + b"/task") if t.isdigit()]
        except OSError:
            tids = []
        if not tids:  # no thread listing here: the process as a whole
            state = _owned(_fields(base + b"/status"), uid)
            if state is not None:
                found.append((int(pid), int(pid), state))
            continue
        for tid in tids:
            state = _owned(_fields(base + b"/task/" + tid + b"/status"), uid)
            if state is not None:
                found.append((int(pid), int(tid), state))
    return found


def live_tasks(uid: int) -> list[tuple[int, int, bytes]]:
    return [t for t in tasks_of(uid) if t[2] not in GONE]


def _signal(tasks: list[tuple[int, int, bytes]], sig: int) -> set[int]:
    pids = {pid for pid, _, _ in tasks}
    for pid, tid, _ in tasks:
        for target in {pid, tid}:  # a thread's id reaches its whole process too
            try:
                os.kill(target, sig)
            except (ProcessLookupError, PermissionError):
                pass
    return pids


def _as_user(uid: int, gid: int, sig: int) -> None:
    """kill(-1, sig) from a child that has dropped to `uid`: every process of that uid gets the
    signal in one system call (the child itself excepted). Root ends the child if it does not
    finish at once, since a process of the user may stop it first."""
    try:
        child = os.fork()
    except OSError:
        return
    if child == 0:  # pragma: no cover - the child only signals and exits
        try:
            os.setgroups([])
            os.setgid(gid)
            os.setuid(uid)
            os.kill(-1, sig)
        except BaseException:  # noqa: BLE001, S110
            pass
        os._exit(0)
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        done, _ = os.waitpid(child, os.WNOHANG)
        if done:
            return
        time.sleep(0.002)
    try:
        os.kill(child, signal.SIGKILL)
    except ProcessLookupError:
        pass
    os.waitpid(child, 0)


def end_user(user: str, seconds: float = SWEEP_SECONDS) -> int:
    """Stop, then kill, every process of `user` (one that left its process group, renamed itself
    or lost its first thread included), sweeping until none is left alive. Return how many tasks
    are still alive at the end: none, unless the machine itself fails to end them."""
    uid, gid = uid_gid(user)
    signalled: set[int] = set()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:  # a stopped process cannot fork
        running = [t for t in live_tasks(uid) if t[2] not in STOPPED]
        if not running:
            break
        signalled |= _signal(running, signal.SIGSTOP)
    if signalled:
        _as_user(uid, gid, signal.SIGSTOP)
        _as_user(uid, gid, signal.SIGKILL)
    while time.monotonic() < deadline:
        left = live_tasks(uid)
        if not left:
            break
        signalled |= _signal(left, signal.SIGKILL)
        reap()
        time.sleep(0.005)
    reap()
    if signalled:
        LEFTOVERS[user] = LEFTOVERS.get(user, 0) + len(signalled)
    return len(live_tasks(uid))


def remove_tree(*paths: str | bytes, seconds: float = REMOVE_SECONDS) -> bool:
    """Remove files or whole trees at any depth, without following links or leaving the
    filesystem. Only call it once no process of the trees' owner is left. Return whether none of
    the paths is left."""
    if not paths:
        return True
    try:
        subprocess.run(
            ["/bin/rm", "-rf", "--one-file-system", "--", *paths],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=seconds,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        pass
    return not any(os.path.lexists(p) for p in paths)


def remove_files_of(user: str, dirs: tuple[str, ...] = SHARED_DIRS) -> int:
    """Remove what `user` left at the top of `dirs` (files, links and whole trees), so nothing
    one run writes reaches the next. Return how many entries were found."""
    uid, _ = uid_gid(user)
    found = 0
    for top in dirs:
        try:
            with os.scandir(os.fsencode(top)) as listing:
                entries = [e.path for e in listing if _owner(e) == uid]
        except OSError:
            continue
        found += len(entries)
        for start in range(0, len(entries), 500):
            remove_tree(*entries[start : start + 500])
    return found


def _owner(entry: os.DirEntry) -> int | None:
    try:
        return entry.stat(follow_symlinks=False).st_uid
    except OSError:
        return None


def remove_ipc_of(user: str) -> int:
    """Remove the System V shared memory, message queues and semaphores `user` owns or made,
    which outlive the process that made them. Return how many were removed."""
    uid, gid = uid_gid(user)
    try:
        libc = ctypes.CDLL(None, use_errno=True)
    except OSError:
        return 0
    mine: list[tuple[str, int]] = []
    calls = {
        "shm": ("shmid", lambda i: libc.shmctl(i, IPC_RMID, None)),
        "msg": ("msqid", lambda i: libc.msgctl(i, IPC_RMID, None)),
        "sem": ("semid", lambda i: libc.semctl(i, 0, IPC_RMID)),
    }
    removed = 0
    for kind, (column, rmid) in calls.items():
        try:
            with open(f"/proc/sysvipc/{kind}", "rb") as f:
                lines = f.read().decode("ascii", "replace").splitlines()
        except OSError:
            continue
        if not lines:
            continue
        head = lines[0].split()
        try:
            at_id, at_uid, at_cuid = (head.index(k) for k in (column, "uid", "cuid"))
        except ValueError:
            continue
        for row in lines[1:]:
            cols = row.split()
            try:
                if uid in (int(cols[at_uid]), int(cols[at_cuid])):
                    if rmid(int(cols[at_id])) == 0:
                        removed += 1
                    else:  # root without CAP_IPC_OWNER (a container's default) may not
                        mine.append((kind, int(cols[at_id])))
            except (IndexError, ValueError):
                continue
    if mine:
        removed += _rmid_as(uid, gid, mine)
    return removed


def _rmid_as(uid: int, gid: int, objects: list[tuple[str, int]]) -> int:
    """Remove System V objects from a child that has dropped to `uid`: their owner or creator may
    always remove them. Root ends the child if it does not finish at once."""
    read, write = os.pipe()
    try:
        child = os.fork()
    except OSError:
        os.close(read)
        os.close(write)
        return 0
    if child == 0:  # pragma: no cover - the child only removes and exits
        done = 0
        try:
            os.close(read)
            libc = ctypes.CDLL(None, use_errno=True)
            os.setgroups([])
            os.setgid(gid)
            os.setuid(uid)
            for kind, ident in objects:
                if kind == "shm":
                    ok = libc.shmctl(ident, IPC_RMID, None) == 0
                elif kind == "msg":
                    ok = libc.msgctl(ident, IPC_RMID, None) == 0
                else:
                    ok = libc.semctl(ident, 0, IPC_RMID) == 0
                done += ok
            os.write(write, str(done).encode())
        except BaseException:  # noqa: BLE001, S110
            pass
        os._exit(0)
    os.close(write)
    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        finished, _ = os.waitpid(child, os.WNOHANG)
        if finished:
            break
        time.sleep(0.002)
    else:
        try:
            os.kill(child, signal.SIGKILL)
        except ProcessLookupError:
            pass
        os.waitpid(child, 0)
    with os.fdopen(read, "rb") as f:
        text = f.read(32)
    return int(text) if text.isdigit() else 0


def clear_user(user: str, dirs: tuple[str, ...] = SHARED_DIRS) -> None:
    """End every process of `user`, then remove what it left in `dirs` and its System V objects.
    Raise EvaluationError when a process of the user is still alive afterwards: nothing the
    submission started may outlive this, since what the grader does next must not be reachable
    by it."""
    for _ in range(2):
        left = end_user(user)
        if left:
            raise EvaluationError(f"{left} task(s) of {user} could not be ended")
        remove_files_of(user, dirs)
        remove_ipc_of(user)
