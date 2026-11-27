"""Child processes of the grader: bounded output capture, and ending a user's leftovers."""

from __future__ import annotations

import ctypes
import os
import pwd
import select
import signal
import subprocess
import time
from pathlib import Path

CHUNK = 1 << 16
PR_SET_CHILD_SUBREAPER = 36
SWEEPS = 100
# user -> how many of its processes were still alive, and ended, once a run or the build was over
LEFTOVERS: dict[str, int] = {}


def become_subreaper() -> bool:
    """Adopt every orphaned descendant instead of PID 1, so that reap() collects what a run or the
    build leaves behind wherever the grader runs (PID 1 of the grading machine may never reap,
    and unreaped processes still count against the user's process limit)."""
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        return libc.prctl(PR_SET_CHILD_SUBREAPER, 1, 0, 0, 0) == 0
    except (OSError, AttributeError):
        return False


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
    except ProcessLookupError:
        pass
    proc.wait()


def reap() -> None:
    """Collect every child that has exited, orphans this process adopted (as PID 1) included."""
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
        except ChildProcessError:
            return
        if pid == 0:
            return


def _live(uid: int) -> list[int]:
    """The processes of `uid` that have not exited."""
    pids: list[int] = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            fields = dict(
                line.split(":", 1)
                for line in (entry / "status").read_text().splitlines()
                if ":" in line
            )
        except OSError:
            continue
        state = fields.get("State", "").split()
        uids = fields.get("Uid", "").split()
        if uids and int(uids[0]) == uid and not (state and state[0] == "Z"):
            pids.append(int(entry.name))
    return pids


def end_user(user: str) -> int:
    """Kill every live process that runs as `user` (one that left its process group included),
    sweeping again until none is left, so one forked during a sweep is caught by the next.
    Return how many were signalled."""
    uid = pwd.getpwnam(user).pw_uid
    signalled: set[int] = set()
    for _ in range(SWEEPS):
        live = _live(uid)
        if not live:
            break
        for pid in live:
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        signalled.update(live)
        reap()
        time.sleep(0.005)
    reap()
    LEFTOVERS[user] = LEFTOVERS.get(user, 0) + len(signalled)
    return len(signalled)
