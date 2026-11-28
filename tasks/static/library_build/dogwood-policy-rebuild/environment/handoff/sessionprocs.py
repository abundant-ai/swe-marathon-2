"""The processes of one user, found in /proc and ended by root.

/proc is read as bytes (a process may name itself anything), every thread of every process is
looked at whatever its state (a process whose first thread has exited still runs in the others),
and a task counts as the user's when any of its uids is the user's. Root sends the signals, so
the user's processes can neither block nor stop them; a child that has dropped to the user's uid
also sends each signal to all of them at once (kill(-1)), which a process that forks cannot
outrun.
"""

from __future__ import annotations

import os
import pwd
import signal
import time

GONE = (b"Z", b"X")
STOPPED = (b"T", b"t")


def ids(user: str) -> tuple[int, int]:
    entry = pwd.getpwnam(user)
    return entry.pw_uid, entry.pw_gid


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


def _state(fields: dict[bytes, bytes] | None, uid: int) -> bytes | None:
    if fields is None:
        return None
    try:
        uids = {int(x) for x in fields.get(b"Uid", b"").split()}
    except ValueError:
        return None
    if uid not in uids:
        return None
    return (fields.get(b"State", b"?").split() or [b"?"])[0]


def tasks(uid: int) -> list[tuple[int, int, bytes]]:
    """(process id, thread id, state) of every thread of `uid`, in any state."""
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
        if not tids:
            state = _state(_fields(base + b"/status"), uid)
            if state is not None:
                found.append((int(pid), int(pid), state))
            continue
        for tid in tids:
            state = _state(_fields(base + b"/task/" + tid + b"/status"), uid)
            if state is not None:
                found.append((int(pid), int(tid), state))
    return found


def live(uid: int) -> list[tuple[int, int, bytes]]:
    return [t for t in tasks(uid) if t[2] not in GONE]


def _send(found: list[tuple[int, int, bytes]], sig: int) -> None:
    for pid, tid, _ in found:
        for target in {pid, tid}:
            try:
                os.kill(target, sig)
            except (ProcessLookupError, PermissionError):
                pass


def _as_user(uid: int, gid: int, sig: int) -> None:
    """kill(-1, sig) from a child dropped to `uid`; root ends the child if it hangs."""
    try:
        child = os.fork()
    except OSError:
        return
    if child == 0:  # pragma: no cover
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
        if os.waitpid(child, os.WNOHANG)[0]:
            return
        time.sleep(0.002)
    try:
        os.kill(child, signal.SIGKILL)
    except ProcessLookupError:
        pass
    os.waitpid(child, 0)


def _reap() -> None:
    while True:
        try:
            if os.waitpid(-1, os.WNOHANG)[0] == 0:
                return
        except ChildProcessError:
            return


def stop(user: str, seconds: float) -> dict:
    """SIGSTOP every task of `user` until none runs, or `seconds` pass."""
    uid, gid = ids(user)
    passes = 0
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        running = [t for t in live(uid) if t[2] not in STOPPED]
        if not running:
            break
        passes += 1
        _send(running, signal.SIGSTOP)
        if passes == 1:
            _as_user(uid, gid, signal.SIGSTOP)
        time.sleep(0.01)
    running = [t for t in live(uid) if t[2] not in STOPPED]
    return {"stop_passes": passes, "still_running": len(running)}


def end(user: str, seconds: float) -> dict:
    """SIGKILL every task of `user` until none is alive, or `seconds` pass."""
    uid, gid = ids(user)
    passes = 0
    deadline = time.monotonic() + seconds
    if live(uid):
        _as_user(uid, gid, signal.SIGKILL)
    while time.monotonic() < deadline:
        left = live(uid)
        if not left:
            break
        passes += 1
        _send(left, signal.SIGKILL)
        _reap()
        time.sleep(0.02)
    _reap()
    return {"kill_passes": passes, "left_alive": len(live(uid))}


def describe(user: str, most: int = 500) -> list[dict]:
    """The processes of `user` as they stand: id, parent, state, name and command line."""
    uid, _ = ids(user)
    out: list[dict] = []
    for pid in sorted({pid for pid, _, _ in tasks(uid)}):
        base = b"/proc/%d" % pid
        fields = _fields(base + b"/status") or {}
        try:
            with open(base + b"/cmdline", "rb") as f:
                cmd = f.read(4096).replace(b"\0", b" ").strip()
        except OSError:
            cmd = b""
        try:
            threads = len(os.listdir(base + b"/task"))
        except OSError:
            threads = None
        out.append(
            {
                "pid": pid,
                "ppid": int((fields.get(b"PPid") or b"0").split()[0] or 0),
                "state": (fields.get(b"State", b"?").split() or [b"?"])[0].decode(
                    "ascii", "replace"
                ),
                "threads": threads,
                "name": fields.get(b"Name", b"").decode("utf-8", "backslashreplace"),
                "command": cmd.decode("utf-8", "backslashreplace")[:1000],
            }
        )
        if len(out) >= most:
            break
    return out
