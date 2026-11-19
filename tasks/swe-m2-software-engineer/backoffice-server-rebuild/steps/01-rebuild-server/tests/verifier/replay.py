"""Start the submitted server as an unprivileged user and replay recorded scenarios against it.

A scenario is a list of requests made in one fresh workspace, with the status and
the answer the reference server gave for each: a JSON body, or for a file its type,
length and SHA-256. The reward is the share of units that match. A scenario is one
unit, or, for a month of trading, one unit per trading day and per client screen
opened after it; a unit matches when every one of its answers is the same. The
total is fixed, so a server that does not start, dies, hangs or is too slow loses
the units it did not answer and nothing else.

- Time: a request has REQUEST_SEC of wall clock and the whole replay DEADLINE_SEC;
  a request still running past either has its connection shut down. Scenarios not
  played to the end by the deadline count as not matched.
- Order: every scenario is played once, WORKERS at a time, in a fixed shuffled
  order, so a server too slow to finish loses scenarios of every kind. A scenario
  with a planned restart, or with an upload heavy enough to hold the database's
  write lock for long (a long PDF, a file of tens of megabytes), runs with nothing
  beside it, at a fixed place spread through that order.
- Restarts: a server that has died, or has left its health check unanswered for
  HEALTH_SEC, is restarted before the next attempt, as often as needed while the
  deadline holds; after START_FAILURES starts in a row that never answer it is given
  up. Every start uses the same DATA_DIR.
- Second tries: a scenario in flight when the server stopped (it died, or hung and
  was stopped) is played once more after the others, alone, while the units they
  decide stay within RETRY_SHARE of all units. A wrong answer, or a request the live
  server left unanswered, is final. Second tries start from nothing: the server
  stopped, every process of its user ended, DATA_DIR set aside and every file its user
  owns removed with its shared memory and message queues, and a fresh server started.
  A second try decides only the units the first try left unanswered.
- Planned restarts: after a step marked `restart` the server is stopped (SIGTERM, or
  SIGKILL straight after the answer) and started again on the same DATA_DIR, and the
  scenario goes on in the same workspace: what a workspace holds must survive.
- Nothing the server sends or does makes the evaluation fail: a reply that is not
  HTTP, not JSON, too large in any transfer encoding or nested too deeply is an answer
  that matches nothing. The server runs as an unprivileged user under limits on
  threads, file size and memory, cannot write its own files, is the first process
  ended when memory runs out, writes its output into a pipe the evaluation reads
  (keeping the first and last LOG_KEEP bytes), and is stopped for good, its remaining
  scenarios failed, when the disk runs low.
"""

from __future__ import annotations

import base64
import collections
import contextlib
import grp
import gzip
import hashlib
import heapq
import http.client
import io
import json
import os
import pwd
import re
import select
import shutil
import signal
import socket
import stat
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

RUN_AS, RUN_GROUP = "nobody", "nogroup"
# threads the server's user may run at once: plenty for any server, too few to fill the process table. The count is per
# user across a shared kernel, so it is set well above what one server needs.
THREAD_LIMIT = 4096
FILE_LIMIT = 4 << 30  # bytes in any one file it writes
MEMORY_LIMIT = 6 << 30  # address space of each of its processes, on a machine with 8 GB; the same for the whole group in a cgroup
# Run as root before the drop: puts the server first in line for the OOM killer (the evaluation raises it again every
# GUARD_SEC, since without CAP_SYS_RESOURCE the server could lower it), and into its cgroup when there is one ($1, or -).
OOM_FIRST = ["sh", "-c", '{ echo 1000 > /proc/self/oom_score_adj; } 2>/dev/null; [ "$1" = - ] || { echo $$ > "$1"; } 2>/dev/null; '
             'shift; exec "$@"', "sh"]
LIMITS = ["prlimit", f"--nproc={THREAD_LIMIT}", f"--fsize={FILE_LIMIT}", f"--as={MEMORY_LIMIT}", "--"]
# no_new_privs: executing a set-user-id or set-group-id file, or one with file capabilities, grants nothing
DROP = ["setpriv", "--reuid", RUN_AS, "--regid", RUN_GROUP, "--clear-groups", "--no-new-privs"]
SANDBOX = OOM_FIRST + ["-"] + LIMITS + DROP
# where any user can create files, besides the root filesystem: swept before the second tries
SCRATCH = ("/tmp", "/var/tmp", "/dev/shm", "/dev/mqueue", "/run/lock", "/var/lock", "/run/shm")
PROC = "/proc"
START_SEC = 60
REQUEST_SEC = 30  # wall clock for one request: a big upload or a 200-page PDF needs more than a JSON call
# the whole replay; the step allows 6,000 s for everything. The reference replays the corpus in about 520 s on the author's
# machine: a server three times slower than it (the pace the instruction asks for), on a machine three times slower, finishes
DEADLINE_SEC = 5400
HEALTH_SEC = 30  # how long a live server may leave its health check unanswered before it is restarted
STOP_SEC = 30  # how long a server stopped with SIGTERM may take to exit before it is killed
START_FAILURES = 3  # starts in a row that never answer before the server is given up
WORKERS = 8
RETRY_SHARE = 0.02  # the units second tries may decide, as a share of all units
RETRY_MARGIN_SEC = 300  # no clean slate and no second try with less time than this left
SWEEP_SEC = 120  # the longest the clean slate spends finding the server's files
ANSWER_LIMIT = 80 << 20  # bytes read of one answer, hashed as they arrive; the largest recorded file is under the 64 MiB upload limit
HEADER_ROOM = 8 << 20  # bytes allowed besides the answer itself: status line, headers, chunk sizes and trailers
JSON_LIMIT = 4_000_000  # a longer JSON answer is not parsed; the longest recorded one is about 65 KB
HEAVY_PDF = 1 << 20  # an uploaded PDF this large is read in full while the write lock is held
HEAVY_FILE = 16 << 20  # so is any upload this large while it is stored
LOG_KEEP = 1 << 20  # bytes of the server's output kept from its start and from its end
GUARD_SEC = 0.05  # how often the server's OOM priority and its memory are checked; the disk every DISK_EVERY of these
DISK_EVERY = 20
DISK_RESERVE = 512 << 20  # free bytes below which the server is stopped for good
SERVER_MEMORY = 6 << 30  # resident bytes the server's processes may hold in all before it is stopped for good
BALLAST = 256 << 20  # set aside before the server starts and given back for the results
MEDIA_CACHE = 192 << 20  # bytes of uploads kept in memory between uses
WORKSPACE_ID = re.compile(r"[A-Za-z0-9_]{1,40}")
CHUNK_SIZE = re.compile(rb"[0-9A-Fa-f]{1,15}")
NOT_JSON, TOO_LARGE = {"__not_json__": True}, {"__too_large__": True}
LATE = "not played to the end before the time limit"
NO_ANSWER = "no answer from the server"
CRASHED = "the server stopped while the scenario was played"
DOWN = "server not running"
DISK = "the server was stopped when the disk ran low"
MEMORY = "the server was stopped when its processes held more than 6 GiB of memory"


class EvaluationError(Exception):
    """Evaluation could not be carried out; no valid reward may be published."""


class NoAnswer(Exception):
    """No complete reply came: the server died, dropped the connection, sent something that is not HTTP or ran out of time."""


class AnswerTooLarge(Exception):
    """The server sent more than one answer may hold."""


class Clock:
    """The replay's time limits.

    A socket timeout starts again with every byte that arrives, so it cannot bound a request on its
    own: a watcher thread shuts down the socket of any request still running past its limit or past
    the deadline, which ends a read or a send that is waiting.
    """

    def __init__(self, seconds: float) -> None:
        self.deadline = time.monotonic() + seconds
        self.lock = threading.Lock()
        self.running: dict[int, tuple[http.client.HTTPConnection, float]] = {}
        self.done = threading.Event()
        self.watcher = threading.Thread(target=self._watch, daemon=True)
        self.watcher.start()

    def expired(self) -> bool:
        return time.monotonic() >= self.deadline

    def left(self) -> float:
        return self.deadline - time.monotonic()

    @contextlib.contextmanager
    def limit(self, connection: http.client.HTTPConnection, seconds: float) -> Iterator[None]:
        """Bound what happens on `connection` inside this block by `seconds` and by the deadline: the watcher shuts the
        socket down at the end, and on a `WatchedConnection` every read of the answer stops there too (QA 07d M1)."""
        end = min(time.monotonic() + seconds, self.deadline)
        if isinstance(connection, WatchedConnection):
            connection.end = end
        with self.lock:
            self.running[id(connection)] = (connection, end)
        try:
            yield
        finally:
            with self.lock:
                self.running.pop(id(connection), None)

    def _watch(self) -> None:
        while not self.done.wait(0.2):
            now = time.monotonic()
            with self.lock:
                for connection, end in self.running.values():
                    # http.client lets go of `connection.sock` once an answer will close the connection (Connection:
                    # close, HTTP/1.0, no length) and reads it through the answer: `watched` keeps the socket in reach
                    sock = getattr(connection, "watched", None) or connection.sock
                    if now >= end and sock is not None:
                        with contextlib.suppress(OSError):
                            sock.shutdown(socket.SHUT_RDWR)

    def stop(self) -> None:
        self.done.set()
        self.watcher.join(timeout=5)


# ------------------------------------------------------------------ reading answers

class Bounded(io.RawIOBase):
    """A socket's byte stream that refuses to deliver more than `limit` bytes in all, or anything after `end` (a
    time.monotonic() value): every byte of an answer counts, its status line, headers, chunk sizes and trailers
    included, whatever its transfer encoding (QA 07c F1), and no drip of bytes, however framed, keeps a read going
    past its end (QA 07d M1)."""

    def __init__(self, raw: io.RawIOBase, limit: int, sock: socket.socket | None = None, end: float = float("inf")) -> None:
        super().__init__()
        self.raw, self.left, self.sock, self.end = raw, limit, sock, end
        self.timeout = sock.gettimeout() if sock is not None else None

    def readable(self) -> bool:
        return True

    def readinto(self, buffer: Any) -> int:
        if self.left <= 0:
            raise AnswerTooLarge()
        view = memoryview(buffer)[:self.left]
        if self.sock is None or self.end == float("inf"):
            count = self.raw.readinto(view) or 0
        else:
            remaining = self.end - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("the answer did not end in time")
            self.sock.settimeout(remaining if self.timeout is None else min(remaining, self.timeout))
            try:
                count = self.raw.readinto(view) or 0
            finally:  # the connection's own timeout again, for whatever is sent on it next
                with contextlib.suppress(OSError):
                    self.sock.settimeout(self.timeout)
        self.left -= count
        return count

    def close(self) -> None:
        with contextlib.suppress(OSError):
            self.raw.close()
        super().close()


class BoundedResponse(http.client.HTTPResponse):
    """http.client's response read through `Bounded`, with chunk sizes parsed strictly: a size that is negative, signed,
    prefixed or not hexadecimal is a broken answer, not a request to read to the end of the stream."""

    def __init__(self, sock: socket.socket, debuglevel: int = 0, method: str | None = None, url: str | None = None, *,
                 limit: int = ANSWER_LIMIT + HEADER_ROOM, end: float = float("inf")) -> None:
        super().__init__(sock, debuglevel, method, url)
        self.fp.close()  # the reader the base class made; nothing has been read from it yet
        self.fp = io.BufferedReader(Bounded(sock.makefile("rb", buffering=0), limit, sock, end), 1 << 16)

    def _read_next_chunk_size(self) -> int:
        line = self.fp.readline(http.client._MAXLINE + 1)  # type: ignore[attr-defined]
        if len(line) > http.client._MAXLINE:  # type: ignore[attr-defined]
            raise http.client.LineTooLong("chunk size")
        size = line.split(b";", 1)[0].strip(b" \t\r\n")
        if not CHUNK_SIZE.fullmatch(size):
            raise ValueError("not a chunk size")  # http.client turns this into IncompleteRead
        return int(size, 16)


class WatchedConnection(http.client.HTTPConnection):
    """A connection whose socket the watcher can always shut down (`watched`, which http.client never lets go of), and
    whose answers are read through `BoundedResponse`, up to `limit` bytes and no later than `end`."""

    def __init__(self, port: int, timeout: float, limit: int = ANSWER_LIMIT + HEADER_ROOM) -> None:
        super().__init__("127.0.0.1", port, timeout=timeout)
        self.limit, self.end = limit, float("inf")
        self.watched: socket.socket | None = None
        self.response_class = lambda sock, *args, **options: BoundedResponse(sock, *args, limit=self.limit, end=self.end, **options)

    def connect(self) -> None:
        super().connect()
        self.watched = self.sock


def connect(port: int, timeout: float, limit: int = ANSWER_LIMIT + HEADER_ROOM) -> WatchedConnection:
    return WatchedConnection(port, timeout, limit)


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def healthy(port: int, clock: Clock, seconds: float = 5) -> bool:
    """Whether the server answers GET /api/health with 200 in time; any other reply, or none, is no."""
    connection = connect(port, seconds, 1 << 20)
    try:
        with clock.limit(connection, seconds):
            connection.request("GET", "/api/health")
            response = connection.getresponse()
            response.read(1_000_000)
            return response.status == 200
    except Exception:  # noqa: BLE001 - whatever the server sends, it is not a healthy answer
        return False
    finally:
        connection.close()


# ------------------------------------------------------------------ the server's processes and files

def proc_fields(pid: str) -> dict[str, str]:
    with open(f"{PROC}/{pid}/status", encoding="latin-1") as status:
        return dict(line.split(":", 1) for line in status if ":" in line)


def user_processes(uid: int) -> list[int]:
    """Processes of real user `uid` with anything still running, read from /proc: that needs no new process, even with a
    full process table. A process whose main thread has exited shows as a zombie while its other threads run (QA 07c
    F2); it counts as alive while it has more than one thread or any thread that is not a zombie."""
    found = []
    with contextlib.suppress(OSError):
        with os.scandir(PROC) as entries:
            for entry in entries:
                if not entry.name.isdigit():
                    continue
                try:
                    fields = proc_fields(entry.name)
                except (OSError, ValueError):
                    continue
                if fields.get("Uid", "").split()[:1] != [str(uid)]:
                    continue
                if not fields.get("State", "").strip().startswith(("Z", "X")) or live_threads(entry.name, fields):
                    found.append(int(entry.name))
    return found


def live_threads(pid: str, fields: dict[str, str]) -> bool:
    with contextlib.suppress(ValueError):
        if int(fields.get("Threads", "1").strip() or 1) > 1:
            return True
    with contextlib.suppress(OSError):
        for task in os.scandir(f"{PROC}/{pid}/task"):
            with contextlib.suppress(OSError, ValueError):
                with open(f"{task.path}/stat", encoding="latin-1") as stat_file:
                    state = stat_file.read().rsplit(")", 1)[1].split()[0]
                if state not in ("Z", "X"):
                    return True
    return False


def kill_as_user(uid: int) -> None:
    """`kill -9 -1` run as the user itself: the kernel signals every process the user owns in one call, except the caller,
    so nothing can fork its way out of it. Needs one new process; the /proc sweep works without one."""
    if uid < 0:
        return
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        subprocess.run(DROP + ["kill", "-9", "-1"], check=False, capture_output=True, timeout=10)


def end_user_processes(uid: int, seconds: float = 20, group: Cgroup | None = None) -> bool:
    """Stop every process of `uid`, then kill them all; True when none is left.

    A sweep that lists processes and then kills them can be outrun by one that forks fast enough
    (QA 07 F4). A stopped process cannot fork: once every process listed is stopped and a new listing
    finds no other, none can appear, and all are killed. Each round also kills the user's processes
    from inside (`kill_as_user`) and the server's cgroup when there is one. Never raises.
    """
    end = time.monotonic() + seconds
    stopped: set[int] = set()
    while time.monotonic() < end:
        alive = set(user_processes(uid))
        if not alive:
            return True
        fresh = alive - stopped
        for pid in fresh or alive:
            with contextlib.suppress(OSError):
                os.kill(pid, signal.SIGSTOP if fresh else signal.SIGKILL)
        stopped |= fresh
        if not fresh:
            if group is not None:
                group.kill()
            kill_as_user(uid)
            time.sleep(0.05)
    return not user_processes(uid)


def server_memory(uid: int, raise_priority: bool = False) -> int:
    """Bytes resident in memory across every process of `uid` (VmRSS of each, from /proc); with `raise_priority`, also
    put each of them back at the front of the OOM killer's line, which needs no capability. One walk of /proc does both,
    so the guard can afford to run every 50 ms."""
    total = 0
    with contextlib.suppress(OSError):
        with os.scandir(PROC) as entries:
            for entry in entries:
                if not entry.name.isdigit():
                    continue
                with contextlib.suppress(OSError, ValueError, IndexError):
                    fields = proc_fields(entry.name)
                    if fields.get("Uid", "").split()[:1] != [str(uid)]:
                        continue
                    total += int(fields.get("VmRSS", "0 kB").split()[0]) << 10
                    if not raise_priority:
                        continue
                    path = f"{PROC}/{entry.name}/oom_score_adj"
                    with open(path) as current:
                        if current.read().strip() == "1000":
                            continue
                    with open(path, "w") as adjust:
                        adjust.write("1000")
    return total


def reap_orphans() -> None:
    """Collect the exit status of every finished child, so the server's killed helpers do not linger as zombies (they
    would count against its thread limit). The evaluation is their reaper (PR_SET_CHILD_SUBREAPER) when sandboxed."""
    with contextlib.suppress(ChildProcessError, OSError):
        while os.waitpid(-1, os.WNOHANG)[0] > 0:
            pass


def remove_tree(path: Path | str, seconds: float = 600) -> None:
    """Remove a directory tree, however deep or wide, within `seconds`: one `rm -rf` killed at its time limit. An
    in-process rmtree lists each directory whole before deleting it and has no time limit (QA 07d M2)."""
    if os.path.lexists(path):
        with contextlib.suppress(OSError, subprocess.SubprocessError):
            subprocess.run(["rm", "-rf", "--", str(path)], check=False, capture_output=True, timeout=max(1.0, seconds))


def remove_user_files(uid: int, roots: tuple[str, ...] = ("/",) + SCRATCH, until: float | None = None,
                      aside: Path | None = None, skip: tuple[str, ...] = ()) -> int:
    """Take away every file and directory `uid` owns under `roots` (each walked on its own filesystem, links never
    followed), and in the scratch places every hard link, which can only be one made to another user's file; returns
    how many. A directory is moved into `aside` (a root-only directory: constant time, however big it is), or, on
    another filesystem, removed by `remove_tree` within the time left. The walk stops at `until` (a time.monotonic()
    value) and never enters `skip` (the evaluation's own folders)."""
    removed = 0
    skipped = {os.path.realpath(path) for path in skip}

    def late() -> bool:
        return until is not None and time.monotonic() >= until

    def take(path: str, directory: bool) -> None:
        nonlocal removed
        removed += 1
        if not directory:
            with contextlib.suppress(OSError):
                os.unlink(path)
            return
        if aside is not None:
            with contextlib.suppress(OSError):
                os.rename(path, aside / f"swept-{removed}")
                return
        remove_tree(path, until - time.monotonic() if until is not None else 600)

    def sweep(folder: str, device: int, scratch: bool) -> None:
        try:
            with os.scandir(folder) as entries:
                for entry in entries:
                    if late():
                        return
                    try:
                        info = entry.stat(follow_symlinks=False)
                    except OSError:
                        continue
                    directory = stat.S_ISDIR(info.st_mode)
                    if info.st_uid == uid or (scratch and not directory and info.st_nlink > 1):
                        take(entry.path, directory)
                    elif directory and info.st_dev == device and entry.path not in skipped:  # never a link: canonical
                        sweep(entry.path, device, scratch)
        except (OSError, RecursionError):
            pass

    for root in roots:
        try:
            top = os.lstat(root)
        except OSError:
            continue
        if stat.S_ISDIR(top.st_mode) and not late() and os.path.realpath(root) not in skipped:
            sweep(root, top.st_dev, root in SCRATCH)
    return removed


class Cgroup:
    """A cgroup v2 group of the server's own, where this machine lets the evaluation make one: memory and processes capped
    for the whole group, its processes killed as one. Where it cannot (a read-only /sys/fs/cgroup, as on Docker's
    defaults), the per-process limits and the /proc sweep stand alone."""

    ROOT = Path("/sys/fs/cgroup")

    def __init__(self) -> None:
        self.path: Path | None = None
        with contextlib.suppress(OSError):
            if not (self.ROOT / "cgroup.controllers").is_file():
                return
            with contextlib.suppress(OSError):
                (self.ROOT / "cgroup.subtree_control").write_text("+memory +pids")
            path = self.ROOT / f"stockwell-server-{os.getpid()}"
            path.mkdir()
            for name, value in (("memory.max", str(MEMORY_LIMIT)), ("memory.swap.max", "0"), ("pids.max", str(THREAD_LIMIT)),
                                ("memory.oom.group", "1")):
                with contextlib.suppress(OSError):
                    (path / name).write_text(value)
            if (path / "cgroup.procs").exists():
                self.path = path

    @property
    def procs(self) -> str:
        return str(self.path / "cgroup.procs") if self.path else "-"

    def kill(self) -> None:
        if self.path is not None:
            with contextlib.suppress(OSError):
                (self.path / "cgroup.kill").write_text("1")

    def remove(self) -> None:
        if self.path is not None:
            self.kill()
            with contextlib.suppress(OSError):
                self.path.rmdir()


class LogCapture:
    """The server's standard output and error: a pipe a thread drains, keeping the first and the last LOG_KEEP bytes.

    The server never holds a file of the evaluation's, so it cannot fill the disk through its output, read it back, see
    its size, or keep writing to it after the evaluation ends (QA 07c F3, F5).
    """

    def __init__(self) -> None:
        self.read_end, self.fd = os.pipe()
        os.set_blocking(self.read_end, False)
        self.head, self.tail, self.total = bytearray(), collections.deque(), 0
        self.tail_bytes = 0
        self.lock, self.done = threading.Lock(), threading.Event()
        self.thread = threading.Thread(target=self._drain, daemon=True)
        self.thread.start()

    def note(self, text: str) -> None:
        self._keep(text.encode())

    def _keep(self, data: bytes) -> None:
        with self.lock:
            self.total += len(data)
            room = LOG_KEEP - len(self.head)
            if room > 0:
                self.head += data[:room]
                data = data[room:]
            if data:
                self.tail.append(data)
                self.tail_bytes += len(data)
                while self.tail and self.tail_bytes - len(self.tail[0]) >= LOG_KEEP:
                    self.tail_bytes -= len(self.tail.popleft())

    def _drain(self) -> None:
        while not self.done.is_set():
            with contextlib.suppress(OSError, ValueError):
                ready, _, _ = select.select([self.read_end], [], [], 0.2)
                if ready:
                    data = os.read(self.read_end, 1 << 16)
                    if data:
                        self._keep(data)

    def close(self, path: Path | None = None) -> None:
        """Stop reading, close the pipe (a process still writing gets EPIPE), and write what was kept to `path`."""
        self.done.set()
        self.thread.join(timeout=5)
        for descriptor in (self.fd, self.read_end):
            with contextlib.suppress(OSError):
                os.close(descriptor)
        if path is None:
            return
        with self.lock:
            tail = b"".join(self.tail)[-LOG_KEEP:]
            left_out = self.total - len(self.head) - len(tail)
            text = bytes(self.head) + (f"\n[... {left_out} bytes left out ...]\n".encode() if left_out > 0 else b"") + tail
        with contextlib.suppress(OSError):
            path.write_bytes(text)


class Ballast:
    """Space set aside on the evaluation's disk before the server starts and given back for the results: however full the
    server leaves the disk, the reward, the summary and the archive Harbor makes of them have room (QA 07c F3)."""

    def __init__(self, path: Path, size: int = BALLAST) -> None:
        self.path: Path | None = None
        with contextlib.suppress(OSError):
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            try:
                try:
                    os.posix_fallocate(descriptor, 0, size)
                except (AttributeError, OSError):
                    block = bytes(1 << 20)
                    for _ in range(size >> 20):
                        os.write(descriptor, block)
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
            self.path = path

    def release(self) -> None:
        if self.path is not None:
            with contextlib.suppress(OSError):
                self.path.unlink()
            self.path = None


def free_bytes(path: Path | str) -> int | None:
    """Free bytes on the filesystem of `path`, or None when it reports no size (a tmpfs without a limit reports no
    blocks at all, QA 07d S1): such a filesystem cannot be watched."""
    try:
        info = os.statvfs(path)
    except OSError:
        return None
    if info.f_blocks == 0:
        return None
    return info.f_bavail * info.f_frsize


# ------------------------------------------------------------------ the server

class Candidate:
    """The submitted server process and the means to restart it."""

    def __init__(self, source: Path, work: Path, log: LogCapture, sandbox: bool, clock: Clock) -> None:
        self.source, self.work, self.log, self.sandbox, self.clock = source, work, log, sandbox, clock
        self.data = work / "data"  # one DATA_DIR for every start, planned or after a crash: what a workspace holds must survive
        self.lock = threading.Lock()
        self.proc: subprocess.Popen[bytes] | None = None
        self.port = 0
        self.generation = 0
        self.restarts = 0
        self.planned = 0
        self.failed_starts = 0
        self.halted: str | None = None  # why the server was stopped for good (DISK or MEMORY), if it was
        self.peak_memory = 0  # the largest VmPeak seen of the server's main process, in kB
        self.uid = pwd.getpwnam(RUN_AS).pw_uid if sandbox else -1
        self.group = Cgroup() if sandbox else None

    def command(self) -> list[str]:
        if not self.sandbox:
            return [str(self.source / "run")]
        return OOM_FIRST + [self.group.procs if self.group else "-"] + LIMITS + DROP + [str(self.source / "run")]

    def note_memory(self) -> None:
        proc = self.proc
        if proc is None:
            return
        with contextlib.suppress(OSError, ValueError, IndexError):
            peak = proc_fields(str(proc.pid)).get("VmPeak", "0 kB").split()[0]
            self.peak_memory = max(self.peak_memory, int(peak))

    def kill_all(self) -> None:
        """Kill the server's process group and, when sandboxed, every process its user still runs. Never raises; the disk
        guard calls it from its own thread."""
        proc = self.proc
        if proc is not None:
            with contextlib.suppress(OSError):
                os.killpg(proc.pid, signal.SIGKILL)
        if self.sandbox:
            end_user_processes(self.uid, group=self.group)  # children that left the group, and any that hide (QA 07c F2)

    def stop(self) -> None:
        """Stop the server for good or before a start. Never raises: a server that has exhausted processes, memory or disk
        must not turn a finished evaluation into an error (QA 07 F2)."""
        self.note_memory()
        self.kill_all()
        if self.proc is not None:
            with contextlib.suppress(subprocess.TimeoutExpired, OSError):
                self.proc.wait(timeout=10)
        if self.sandbox:
            reap_orphans()
        self.proc = None

    def clean_slate(self) -> None:
        """Before the second tries: stop the server and take away everything it could have kept from the first pass, its
        data, its user's processes and files anywhere, shared memory and message queues; then start it afresh.

        DATA_DIR and every directory the user owns are moved aside into a directory only root can enter (constant time,
        however much they hold; nothing is deleted), the search for the user's files stops after SWEEP_SEC and never
        enters the evaluation's own folders (QA 07d M2). The submission is read-only to the server, so it starts again
        exactly as delivered.
        """
        with self.lock:
            self.stop()
            aside = self.work / "set-aside"
            with contextlib.suppress(OSError):
                aside.mkdir(mode=0o700, exist_ok=True)
                os.chmod(aside, 0o700)
                os.rename(self.data, aside / f"data-{self.generation}")
            budget = min(SWEEP_SEC, max(1.0, self.clock.left() - RETRY_MARGIN_SEC))
            if os.path.lexists(self.data):
                remove_tree(self.data, budget)
            if self.sandbox:
                remove_user_files(self.uid, until=time.monotonic() + budget, aside=aside, skip=(str(self.work), str(self.source)))
                with contextlib.suppress(OSError, subprocess.SubprocessError):  # run as the user, who owns its objects
                    subprocess.run(DROP + ["ipcrm", "--all"], check=False, capture_output=True, timeout=60)
            if not self.clock.expired() and not self.halted and self.start():
                self.failed_starts = 0
            else:
                self.failed_starts += 1  # the next attempt tries again, as after a crash

    def start(self) -> bool:
        """Start the server on the shared data directory and wait for its health check; False if it does not come up."""
        self.stop()
        if self.halted:
            return False
        self.generation += 1
        try:
            self.port = free_port()
            data = self.data
            data.mkdir(parents=True, exist_ok=True)
            os.chmod(data, 0o777)
            env = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/usr/local/go/bin", "HOME": str(data),
                   "PORT": str(self.port), "DATA_DIR": str(data), "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8",
                   "PYTHONDONTWRITEBYTECODE": "1", "GOCACHE": str(data / "gocache"), "GOFLAGS": "-mod=mod"}
            self.log.note(f"\n==== start {self.generation} on port {self.port} ====\n")
            self.proc = subprocess.Popen(self.command(), cwd=self.source, env=env, stdout=self.log.fd, stderr=subprocess.STDOUT,
                                         stdin=subprocess.DEVNULL, start_new_session=True)
        except OSError:  # no free port, a full disk, or a `run` that cannot be executed
            self.proc = None
            return False
        end = min(time.monotonic() + START_SEC, self.clock.deadline)
        while time.monotonic() < end and self.proc.poll() is None and not self.halted:
            if healthy(self.port, self.clock):
                return True
            time.sleep(0.25)
        self.stop()
        return False

    def current(self) -> tuple[int, int] | None:
        """Generation and port of the running server, restarted first if it is down; None if it cannot run."""
        with self.lock:
            if self.proc is not None and self.proc.poll() is None and not self.halted:
                return self.generation, self.port
            self.stop()
            if self.clock.expired() or self.failed_starts >= START_FAILURES or self.halted:
                return None
            self.restarts += 1
            if not self.start():
                self.failed_starts += 1
                return None
            self.failed_starts = 0
            return self.generation, self.port

    def planned_restart(self, how: str) -> tuple[int, int] | None:
        """Stop the server as an operator ("term": SIGTERM, then SIGKILL after STOP_SEC) or a power cut ("kill": SIGKILL
        straight after the answer just read) would, and start it again on the same data; None if it does not come back."""
        with self.lock:
            self.planned += 1
            if self.proc is not None:
                self.note_memory()
                with contextlib.suppress(OSError):
                    os.killpg(self.proc.pid, signal.SIGTERM if how == "term" else signal.SIGKILL)
                if how == "term":
                    with contextlib.suppress(subprocess.TimeoutExpired):
                        self.proc.wait(timeout=STOP_SEC)
            self.stop()
            if self.clock.expired() or not self.start():
                self.failed_starts += 1
                return None
            self.failed_starts = 0
            return self.generation, self.port

    def recover(self, seen: int) -> bool:
        """After a request got no answer: stop the server if it has died or no longer answers its health check. True when
        the server had stopped or is stopped here, False when it is alive and answers.

        A live server has HEALTH_SEC to answer, so one busy with a long request is left alone. The next
        attempt restarts a stopped server.
        """
        with self.lock:
            if self.generation != seen or self.proc is None:
                return True
            end = min(time.monotonic() + HEALTH_SEC, self.clock.deadline)
            while self.proc.poll() is None:
                if healthy(self.port, self.clock):
                    return False
                if time.monotonic() >= end:
                    break
                time.sleep(1)
            self.stop()
            return True


class Guard:
    """While the server may run, every GUARD_SEC (50 ms): put its processes back at the front of the OOM killer's line,
    and stop it for good when they hold more than SERVER_MEMORY in all, so memory it takes cannot end the evaluation
    (QA 07c F1, 07d M3); every DISK_EVERY ticks, stop it for good when a disk the evaluation needs has run low while it
    ran (QA 07c F3). Only a filesystem that reports its size and had room when the server started is watched (QA 07d
    S1): a server cannot be blamed for a disk the machine gave it full. `start_free` has what each path had."""

    def __init__(self, candidate: Candidate, paths: list[Path]) -> None:
        self.candidate = candidate
        self.start_free = {str(path): free_bytes(path) for path in paths}
        self.paths = [path for path in paths if (self.start_free[str(path)] or 0) >= DISK_RESERVE]
        self.done = threading.Event()
        self.thread = threading.Thread(target=self._watch, daemon=True)
        self.thread.start()

    def halt(self, reason: str) -> None:
        candidate = self.candidate
        if not candidate.halted:
            candidate.halted = reason
            candidate.kill_all()

    def _watch(self) -> None:
        candidate, tick = self.candidate, 0
        while not self.done.wait(GUARD_SEC):
            tick += 1
            if candidate.halted:
                continue
            if server_memory(candidate.uid, candidate.sandbox) > SERVER_MEMORY:
                self.halt(MEMORY)
                continue
            if tick % DISK_EVERY == 0 and any((free := free_bytes(path)) is not None and free < DISK_RESERVE for path in self.paths):
                self.halt(DISK)  # a path whose size cannot be read this time is not taken for full

    def free_now(self) -> dict[str, list[int | None]]:
        """Free MiB on each path, when the server started and now."""
        found: dict[str, list[int | None]] = {}
        for path, start in self.start_free.items():
            now = free_bytes(path)
            found[path] = [start >> 20 if start is not None else None, now >> 20 if now is not None else None]
        return found

    def stop(self) -> None:
        self.done.set()
        self.thread.join(timeout=5)


def protect_grader() -> str:
    """Ask the kernel to end the evaluation last when memory runs out. Lowering the value needs CAP_SYS_RESOURCE, which
    Docker's defaults do not give, so this may not take; the server's own value is kept at 1000 either way."""
    for value in ("-1000", "-900", "-500"):
        with contextlib.suppress(OSError):
            with open("/proc/self/oom_score_adj", "w") as adjust:
                adjust.write(value)
            return value
    return "0"


# ------------------------------------------------------------------ requests

def closed_by_peer(sock: socket.socket) -> bool:
    """Whether the server has closed this idle kept-alive connection; bytes it sent unasked are left for the next answer."""
    try:
        poller = select.poll()
        poller.register(sock, select.POLLIN)
        if not poller.poll(0):
            return False
        return sock.recv(1, socket.MSG_PEEK) == b""
    except BlockingIOError:
        return False
    except (OSError, ValueError):
        return True


def json_bytes(value: Any) -> bytes:
    """A JSON request body, written as clients write it: UTF-8, not \\u escapes."""
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def inserted_body(step: dict[str, Any], data: bytes) -> bytes:
    """A JSON body with a file's content in one of its fields, as base64 or as UTF-8 text.

    Lets a body of megabytes (a photo sent as base64, a large CSV import) be recorded as a reference to
    a file in the media folder instead of inside the scenarios; recorder and replay build the same bytes.
    """
    insert = step["body_insert"]
    body = dict(step["body"])
    body[insert["field"]] = base64.b64encode(data).decode("ascii") if insert["as"] == "base64" else data.decode("utf-8")
    return json_bytes(body)


def exchange(connection: http.client.HTTPConnection, method: str, path: str, headers: dict[str, str], body: Any,
             raw: bytes | None = None) -> tuple[int, Any]:
    """Send one request on an open connection and read the answer.

    `raw` is a file sent as the request body as it is, with the content type the step names;
    otherwise `body` is sent as JSON. A JSON answer that cannot be parsed (not JSON, too long,
    nested too deeply) becomes a value no recorded answer equals; a file is compared by its
    type, its length and its SHA-256. On a connection made by `connect`, no answer can make the
    evaluation read more than ANSWER_LIMIT and HEADER_ROOM bytes.
    """
    sent = dict(headers)
    if raw is not None:
        payload: bytes | None = raw
    else:
        payload = None if body is None else json_bytes(body)
        if payload is not None:
            sent["Content-Type"] = "application/json"
    for second_try in (False, True):
        # a server may close a kept-alive connection without announcing it: notice that before sending, and if a
        # reused connection still fails before any answer arrives, the request never reached it: send it once more
        if connection.sock is not None and closed_by_peer(connection.sock):
            connection.close()
        reused, refused_early = connection.sock is not None, False
        try:
            connection.request(method, path, body=payload, headers=sent)
        except (BrokenPipeError, ConnectionResetError):
            if raw is not None:
                refused_early = True  # an oversized upload answered (413) and closed before it was read: the answer is there
            elif reused and not second_try:
                connection.close()
                continue
            else:
                raise
        try:
            response = connection.getresponse()
        except (http.client.RemoteDisconnected, ConnectionResetError, BrokenPipeError):
            if reused and not second_try:  # no answer at all, not even an early 413: the connection was closed before we sent
                connection.close()
                continue
            raise
        except AnswerTooLarge:
            connection.close()
            return 0, TOO_LARGE
        break
    # read in chunks: a file answer is hashed as it arrives, only a JSON answer is kept, so memory stays small
    kind = (response.getheader("Content-Type") or "").split(";")[0].strip().lower()
    digest, kept, size = hashlib.sha256(), bytearray(), 0
    try:
        while size <= ANSWER_LIMIT:
            chunk = response.read(min(1 << 20, ANSWER_LIMIT + 1 - size))
            if not chunk:
                break
            size += len(chunk)
            digest.update(chunk)
            if kind == "application/json" and len(kept) <= JSON_LIMIT:
                kept += chunk
    except AnswerTooLarge:
        size = ANSWER_LIMIT + 1
    if size <= ANSWER_LIMIT and response.length:
        # the connection ended before the length the server announced: a cut answer is no answer (http.client does not raise)
        raise http.client.IncompleteRead(bytes(kept), response.length)
    if refused_early or size > ANSWER_LIMIT:
        connection.close()  # the connection still holds the rest of the upload or of the answer
    if size > ANSWER_LIMIT:
        return response.status, TOO_LARGE
    if kind != "application/json":
        return response.status, {"binary": {"content_type": kind, "bytes": size, "sha256": digest.hexdigest()}}
    if size > JSON_LIMIT:
        return response.status, TOO_LARGE
    try:
        return response.status, json.loads(kept.decode("utf-8"))
    except (ValueError, UnicodeDecodeError, RecursionError, MemoryError):
        return response.status, NOT_JSON


def ask(clock: Clock, connection: http.client.HTTPConnection, method: str, path: str, headers: dict[str, str], body: Any,
        raw: bytes | None = None) -> tuple[int, Any]:
    """One request within REQUEST_SEC and the deadline; NoAnswer if no complete reply came."""
    with clock.limit(connection, REQUEST_SEC):
        try:
            return exchange(connection, method, path, headers, body, raw)
        except (OSError, http.client.HTTPException) as exc:
            raise NoAnswer(type(exc).__name__) from exc


class Media:
    """The files the scenarios upload, kept in memory between uses up to MEDIA_CACHE bytes, the least recent let go."""

    def __init__(self, folder: Path) -> None:
        self.folder, self.lock = folder, threading.Lock()
        self.cache: collections.OrderedDict[str, bytes] = collections.OrderedDict()
        self.cached = 0
        self.sizes: dict[str, int] = {}

    def path(self, name: str) -> Path:
        path = (self.folder / name).resolve()
        if self.folder.resolve() not in path.parents or not path.is_file():
            raise EvaluationError(f"a scenario names a missing upload: {name}")
        return path

    def size(self, name: str) -> int:
        if name not in self.sizes:
            try:
                self.sizes[name] = self.path(name).stat().st_size
            except (EvaluationError, OSError):
                self.sizes[name] = 0
        return self.sizes[name]

    def read(self, name: str) -> bytes:
        with self.lock:
            if name in self.cache:
                self.cache.move_to_end(name)
                return self.cache[name]
        data = self.path(name).read_bytes()
        if len(data) <= MEDIA_CACHE // 2:
            with self.lock:
                if name not in self.cache:
                    self.cache[name] = data
                    self.cached += len(data)
                    while self.cached > MEDIA_CACHE:
                        self.cached -= len(self.cache.popitem(last=False)[1])
        return data

    def body(self, step: dict[str, Any]) -> bytes | None:
        """The raw body a step sends: a named file, a JSON body built around a named file, N zero bytes, or None for a
        JSON body the step holds."""
        if "body_size" in step:
            return bytes(int(step["body_size"]))
        insert = step.get("body_insert")
        name = insert["file"] if insert else step.get("body_file")
        if name is None:
            return None
        data = self.read(name)
        return inserted_body(step, data) if insert else data


def expand(value: Any, workspace: str) -> Any:
    """The recorded answer with this workspace's id put back where the recorder wrote {ws}.

    The recorder wrote {ws} for the reference's own workspace id wherever it appeared in the answer
    (a random `ws_` and 16 hex digits, so never by chance), and braces cannot occur in an id the
    instruction allows. Putting the candidate's id back in the same places is the exact inverse; the
    candidate's answer itself is never rewritten.
    """
    if isinstance(value, str):
        return value.replace("{ws}", workspace) if "{ws}" in value else value
    if isinstance(value, list):
        return [expand(item, workspace) for item in value]
    if isinstance(value, dict):
        return {expand(key, workspace): expand(item, workspace) for key, item in value.items()}
    return value


def identical(answer: Any, expected: Any) -> bool:
    """Equal as JSON documents: the same types throughout, so `true` is not `1` and `100` is not `100.0`."""
    if type(answer) is not type(expected):
        return False
    if isinstance(expected, dict):
        return answer.keys() == expected.keys() and all(identical(answer[key], expected[key]) for key in expected)
    if isinstance(expected, list):
        return len(answer) == len(expected) and all(identical(a, e) for a, e in zip(answer, expected))
    return answer == expected


def same(answer: Any, expected: Any, workspace: str) -> bool:
    """Whether an answer equals the recorded one; a recorded file's name is not compared."""
    if isinstance(expected, dict) and set(expected) == {"binary"}:
        expected = {"binary": {key: value for key, value in expected["binary"].items() if key != "filename"}}
    try:
        return identical(answer, expand(expected, workspace))
    except RecursionError:  # nested deeper than any recorded answer
        return False


def encode_query(query: dict[str, str]) -> str:
    return ("?" + urlencode(query)) if query else ""


# ------------------------------------------------------------------ scenarios

def unit_count(scenario: dict[str, Any]) -> int:
    """A scenario is one unit, or as many as it lists in `units` (the days and screens of a trading run)."""
    return len(scenario["units"]) if scenario.get("units") else 1


def unit_themes(scenario: dict[str, Any]) -> list[str]:
    """The theme each unit of a scenario counts under.

    Raises:
        EvaluationError: A step names a unit the scenario does not have, or a unit has no step.
    """
    count = unit_count(scenario)
    used = {step.get("unit", 0) for step in scenario["steps"]}
    if not used <= set(range(count)) or (scenario.get("units") and len(used) != count):
        raise EvaluationError(f"Private scenarios are malformed: units of {scenario.get('id')}")
    return [unit["theme"] for unit in scenario["units"]] if scenario.get("units") else [scenario["theme"]]


def durable(scenario: dict[str, Any]) -> bool:
    """A scenario with a planned restart in it; such scenarios run one at a time, so the restart disturbs no other."""
    return any("restart" in step for step in scenario["steps"])


def heavy(scenario: dict[str, Any], media: Media) -> bool:
    """A scenario that uploads a PDF of HEAVY_PDF bytes or more, or any file of HEAVY_FILE or more: the reference reads such
    a file in full, or stores it, while it holds the database's write lock, and a request queued behind it for longer
    than SQLite's 15 s wait would fail (QA 11 S1). Such scenarios run alone."""
    for step in scenario["steps"]:
        name = step.get("body_file") or (step.get("body_insert") or {}).get("file")
        if name:
            size = media.size(name)
            if size >= HEAVY_FILE or (size >= HEAVY_PDF and name.lower().endswith(".pdf")):
                return True
    return False


def iter_scenarios(text: str) -> Iterator[dict[str, Any]]:
    """The scenarios of a corpus document, decoded one at a time; the whole list would need many times the memory."""
    decoder, whitespace = json.JSONDecoder(), json.decoder.WHITESPACE

    def skip(index: int) -> int:
        return whitespace.match(text, index).end()

    def expect(index: int, char: str) -> int:
        index = skip(index)
        if text[index:index + 1] != char:
            raise ValueError(f"expected {char!r} at offset {index}")
        return skip(index + 1)

    index = expect(0, "{")
    while text[index:index + 1] != "}":
        key, index = decoder.raw_decode(text, index)
        index = expect(index, ":")
        if key != "scenarios":
            _, index = decoder.raw_decode(text, index)
        else:
            index = expect(index, "[")
            while text[index:index + 1] != "]":
                scenario, index = decoder.raw_decode(text, index)
                yield scenario
                index = skip(index)
                if text[index:index + 1] == ",":
                    index = skip(index + 1)
            index += 1
        index = skip(index)
        if text[index:index + 1] == ",":
            index = skip(index + 1)


class Corpus:
    """The private scenarios, each held as compact JSON text and decoded only when it is played: the decoded corpus takes
    several times the memory, and a small evaluation is a small target when memory runs out (QA 07c F1)."""

    def __init__(self, path: Path, media: Media) -> None:
        self.blobs: list[bytes] = []
        self.ids: list[str] = []
        self.themes: list[list[str]] = []
        self.alone: list[bool] = []
        self.restarting: list[bool] = []
        try:
            raw = path.read_bytes()
            text = (gzip.decompress(raw) if path.suffix == ".gz" else raw).decode("utf-8")
            del raw
            for scenario in iter_scenarios(text):
                self.themes.append(unit_themes(scenario))  # also checks that every unit has steps
                self.ids.append(str(scenario["id"]))
                self.restarting.append(durable(scenario))
                self.alone.append(self.restarting[-1] or heavy(scenario, media))
                self.blobs.append(json.dumps(scenario, separators=(",", ":")).encode())
            del text
        except (OSError, ValueError, KeyError, TypeError, EOFError) as exc:
            raise EvaluationError("Private scenarios are unreadable") from exc
        if not self.blobs:
            raise EvaluationError("Private scenarios are empty")

    def __len__(self) -> int:
        return len(self.blobs)

    def scenario(self, index: int) -> dict[str, Any]:
        return json.loads(self.blobs[index])


class Stats:
    """What makes a short baseline readable without the server's log (QA 11 S1): the slowest requests, and the answers of
    500 or above by theme."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.slowest: list[tuple[float, str, int, str]] = []
        self.server_errors: collections.Counter[str] = collections.Counter()

    def note(self, seconds: float, scenario: str, step: int, request: str, status: int, theme: str) -> None:
        with self.lock:
            entry = (round(seconds, 3), scenario, step, request)
            if len(self.slowest) < 20:
                heapq.heappush(self.slowest, entry)
            elif entry > self.slowest[0]:
                heapq.heapreplace(self.slowest, entry)
            if status >= 500:
                self.server_errors[theme] += 1

    def report(self) -> dict[str, Any]:
        return {"slowest_requests": [{"seconds": s, "scenario": i, "step": n, "request": r} for s, i, n, r in sorted(self.slowest, reverse=True)],
                "server_errors_by_theme": dict(sorted(self.server_errors.items()))}


def attempt(candidate: Candidate, scenario: dict[str, Any], media: Media, clock: Clock, stats: Stats | None = None) -> dict[str, Any]:
    """Play a scenario once in a fresh workspace.

    A scenario without units is one unit and stops at its first difference. A scenario with units goes on
    after a difference, so each unit is judged on its own answers: a unit matches when every one of its
    answers does. Either stops when an answer never comes. After a step marked `restart` the server is
    stopped and started again on the same data, and the scenario goes on in the same workspace.
    """
    steps, multi = scenario["steps"], bool(scenario.get("units"))
    count = unit_count(scenario)
    themes = unit_themes(scenario)
    needed, answered, wrong = [0] * count, [0] * count, [False] * count
    for step in steps:
        needed[step.get("unit", 0)] += 1
    difference: tuple[int, str] | None = None

    def result(failed_step: int | None, reason: str | None) -> dict[str, Any]:
        verdicts = [not wrong[unit] and answered[unit] == needed[unit] for unit in range(count)]
        # a unit with a wrong answer, or with every answer in, is settled: a second try cannot change its verdict
        settled = [wrong[unit] or answered[unit] == needed[unit] for unit in range(count)]
        return {"id": scenario["id"], "matched": all(verdicts), "units": verdicts, "settled": settled, "failed_step": failed_step,
                "reason": reason}

    def stopped() -> str:
        return LATE if clock.expired() else candidate.halted or DOWN

    if clock.expired():
        return result(0, LATE)
    running = candidate.current()
    if running is None:
        return result(0, stopped())
    generation, port = running
    connection = connect(port, REQUEST_SEC)
    index = 0
    try:
        status, created = ask(clock, connection, "POST", "/api/workspaces", {}, None)
        workspace = created.get("id") if isinstance(created, dict) else None
        if status != 201 or not isinstance(workspace, str) or not WORKSPACE_ID.fullmatch(workspace):
            if candidate.generation != generation:  # the server was restarted under this scenario
                raise NoAnswer("restarted")
            return result(0, "could not create a workspace")
        for index, step in enumerate(steps, start=1):
            unit = step.get("unit", 0)
            # most paths are the workspace's own; a step marked scoped: false names its full path (the client's /api/version)
            path = step["path"] if step.get("scoped", True) is False else f"/api/ws/{workspace}{step['path']}"
            began = time.monotonic()
            status, answer = ask(clock, connection, step["method"], path + encode_query(step["query"]), step["headers"], step.get("body"),
                                 media.body(step))
            if stats is not None:
                stats.note(time.monotonic() - began, str(scenario["id"]), index, f"{step['method']} {step['path']}", status, themes[unit])
            reason = (f"status {status}, expected {step['status']}" if status != step["status"]
                      else None if same(answer, step["json"], workspace) else "body differs")
            if reason is not None:
                if candidate.generation != generation:
                    raise NoAnswer("restarted")
                wrong[unit] = True
                difference = difference or (index, reason)
                if not multi:
                    return result(index, reason)
            answered[unit] += 1
            if step.get("restart"):
                connection.close()
                running = candidate.planned_restart(step["restart"])
                if running is None:
                    return result(index, stopped())
                generation, port = running
                connection = connect(port, REQUEST_SEC)
        return result(*(difference or (None, None)))
    except NoAnswer:
        connection.close()  # before waiting on the server: a server that serves one connection at a time may be waiting on this one
        if clock.expired():
            return result(index, LATE)
        if candidate.halted:
            return result(index, candidate.halted)
        # the server stopped (it died, or hung and was stopped): CRASHED, which may earn a second try; a live server that
        # left the request unanswered: NO_ANSWER, final
        return result(index, CRASHED if candidate.recover(generation) else NO_ANSWER)
    finally:
        connection.close()


def not_played(themes: list[str], scenario_id: str, reason: str) -> dict[str, Any]:
    count = len(themes)
    return {"id": scenario_id, "matched": False, "units": [False] * count, "settled": [False] * count, "failed_step": 0, "reason": reason}


def merge_retry(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    """The verdict after a second try: it decides only the units the first try left unsettled (QA 07 F1).

    A month goes on after a wrong answer, and later requests echo many earlier answers, so a server could
    read a whole month on the first try, give no answer at the end to earn a second, and replay what it
    learned. The units it answered on the first try keep the first try's verdicts.
    """
    units = [old if settled else new for old, new, settled in zip(first["units"], second["units"], first["settled"])]
    settled = [old or new for old, new in zip(first["settled"], second["settled"])]
    reason = second["reason"] or (None if all(units) else "answered differently on the first try")
    return dict(second, matched=all(units), units=units, settled=settled, reason=reason,
                failed_step=second["failed_step"] if second["reason"] else None)


def play_order(scenarios: list[dict[str, Any]], alone: list[bool] | None = None) -> list[int]:
    """The order scenarios are started in: a fixed shuffle, so a server too slow to finish loses some of every kind rather
    than the kinds that come last, with the scenarios that run alone (`alone`, by default those that restart the server)
    spread evenly through it."""
    alone = alone if alone is not None else [durable(scenario) for scenario in scenarios]

    def mixed(indexes: list[int]) -> list[int]:
        return sorted(indexes, key=lambda index: hashlib.sha256(str(scenarios[index]["id"]).encode()).digest())

    shared = mixed([index for index in range(len(scenarios)) if not alone[index]])
    single = mixed([index for index in range(len(scenarios)) if alone[index]])
    order: list[int] = []
    taken = 0
    for number, index in enumerate(single, start=1):
        upto = len(shared) * number // (len(single) + 1)
        order += shared[taken:upto] + [index]
        taken = upto
    return order + shared[taken:]


class Gate:
    """Lets scenarios run side by side, except one that runs alone (a planned restart, a heavy upload), which waits until
    it is alone and holds back those after it until it is done."""

    def __init__(self) -> None:
        self.condition = threading.Condition()
        self.running = 0
        self.alone = False
        self.waiting = 0

    @contextlib.contextmanager
    def enter(self, exclusive: bool) -> Iterator[None]:
        with self.condition:
            if exclusive:
                self.waiting += 1
                self.condition.wait_for(lambda: not self.alone and self.running == 0)
                self.waiting -= 1
                self.alone = True
            else:
                self.condition.wait_for(lambda: not self.alone and self.waiting == 0)
                self.running += 1
        try:
            yield
        finally:
            with self.condition:
                if exclusive:
                    self.alone = False
                else:
                    self.running -= 1
                self.condition.notify_all()


def play_all(candidate: Candidate, corpus: Corpus, media: Media, clock: Clock, metrics: dict[str, Any],
             stats: Stats | None = None, results: list[dict[str, Any] | None] | None = None) -> list[dict[str, Any]]:
    """Play every scenario, then give the scenarios the server's stops interrupted one more try, alone, on a clean slate,
    while time and the retry share remain.

    Scenarios run WORKERS at a time in `play_order`; one that runs alone has nothing beside it. A second try is only for
    a scenario in flight when the server stopped, never for a wrong answer, and the units second tries decide stay within
    RETRY_SHARE of all units, so they rescue a server that stops now and then, not one that fails under load (QA 20).
    Each result goes into `results` as soon as it is decided, where a caller can read it if the evaluation overruns.
    """
    results = results if results is not None else [None] * len(corpus)
    gate = Gate()

    def play(index: int) -> dict[str, Any]:
        with gate.enter(corpus.alone[index]):
            if clock.expired():
                found = not_played(corpus.themes[index], corpus.ids[index], LATE)
            else:
                found = attempt(candidate, corpus.scenario(index), media, clock, stats)
        results[index] = found
        return found

    order = play_order([{"id": scenario_id} for scenario_id in corpus.ids], corpus.alone)
    pool = ThreadPoolExecutor(WORKERS)
    try:
        for _ in pool.map(play, order):
            pass
    finally:
        pool.shutdown(cancel_futures=True)
    budget = int(RETRY_SHARE * sum(len(themes) for themes in corpus.themes))
    metrics["retry_budget_units"] = budget
    # a second try only where it can decide something (QA 07d N7)
    again = [index for index in order if results[index]["reason"] in (CRASHED, DOWN) and results[index]["settled"].count(False)]
    if again and not candidate.halted and clock.left() > RETRY_MARGIN_SEC:
        candidate.clean_slate()
        for index in again:
            open_units = results[index]["settled"].count(False)
            if open_units > budget:
                continue
            if clock.left() <= 0 or candidate.halted:
                break
            budget -= open_units
            metrics["retried"] += 1
            metrics["retried_units"] += open_units
            results[index] = merge_retry(results[index], attempt(candidate, corpus.scenario(index), media, clock, stats))
    return results  # type: ignore[return-value]


def strip_set_id(root: Path) -> int:
    """Clear the set-user-id and set-group-id bits of every file under `root`; returns how many had one.

    Symbolic links are neither followed nor changed, so nothing outside the submission is touched; a file that cannot be
    read or changed is passed over (QA 07c N4).
    """
    count = 0
    for folder, _, names in os.walk(root):
        for name in names:
            with contextlib.suppress(OSError):
                path = os.path.join(folder, name)
                mode = os.lstat(path).st_mode
                if stat.S_ISREG(mode) and mode & (stat.S_ISUID | stat.S_ISGID):
                    os.chmod(path, stat.S_IMODE(mode) & ~(stat.S_ISUID | stat.S_ISGID))
                    count += 1
    return count


# Run under the drop: prints /proc/self/status, then what prctl(PR_GET_NO_NEW_PRIVS) says, since some
# kernels (gVisor among them, possibly) do not list NoNewPrivs in the status file, then the limits, then
# whether the process could lower its own OOM priority (it may, without CAP_SYS_RESOURCE).
NNP_PROBE = (
    "import ctypes, resource, sys\n"
    "sys.stdout.write(open('/proc/self/status').read())\n"
    "try:\n"
    "    value = ctypes.CDLL(None, use_errno=True).prctl(39, 0, 0, 0, 0)\n"
    "except Exception:\n"
    "    value = -1\n"
    "sys.stdout.write('PrctlNoNewPrivs:\\t%d\\n' % value)\n"
    "for name in ('NPROC', 'FSIZE', 'AS'):\n"
    "    sys.stdout.write('Rlimit%s:\\t%d %d\\n' % ((name,) + resource.getrlimit(getattr(resource, 'RLIMIT_' + name))))\n"
    "try:\n"
    "    open('/proc/self/oom_score_adj', 'w').write('0')\n"
    "    lowered = 1\n"
    "except Exception:\n"
    "    lowered = 0\n"
    "sys.stdout.write('OomLowered:\\t%d\\n' % lowered)\n"
)
LIMIT_LINES = {"NPROC": ("Max processes", THREAD_LIMIT), "FSIZE": ("Max file size", FILE_LIMIT), "AS": ("Max address space", MEMORY_LIMIT)}


def limits_applied(report: str) -> bool:
    """Whether a process's report shows the server's limits, soft and hard: `Rlimit*` lines from `NNP_PROBE`, or the
    lines of /proc/self/limits."""
    found: dict[str, list[str]] = {}
    for line in report.splitlines():
        for name, (title, _) in LIMIT_LINES.items():
            if line.startswith(f"Rlimit{name}:"):
                found[name] = line.split(":", 1)[1].split()
            elif line.startswith(title + " ") and name not in found:
                found[name] = line[len(title):].split()[:2]
    return all(found.get(name) == [str(value)] * 2 for name, (_, value) in LIMIT_LINES.items())


def privileges_dropped(status: str, uid: int, gid: int) -> bool:
    """Whether a process's status shows only `uid` and `gid`, no capabilities and no_new_privs.

    `status` is /proc/self/status, optionally followed by a `PrctlNoNewPrivs:` line from `NNP_PROBE`;
    no_new_privs counts as set when either source says so.
    """
    fields = dict(line.split(":", 1) for line in status.splitlines() if ":" in line)
    if fields.get("Uid", "").split() != [str(uid)] * 4 or fields.get("Gid", "").split() != [str(gid)] * 4:
        return False
    no_new_privs = "1" in (fields.get("NoNewPrivs", "").strip(), fields.get("PrctlNoNewPrivs", "").strip())
    if fields.get("Groups", "").split() not in ([], [str(gid)]) or not no_new_privs:
        return False  # neither the status file nor prctl shows no_new_privs: fail closed
    return all(int(fields.get(name, "0"), 16) == 0 for name in ("CapPrm", "CapEff", "CapAmb"))


def check_sandbox() -> list[str]:
    """Prove the privilege drop before any submitted code runs, with a process started exactly as the server will be.

    Returns:
        Notes for metrics.json: a machine where the server's user can lower its own OOM priority.

    Raises:
        EvaluationError: The unprivileged user is missing, or a process started through the drop keeps
            privileges or could gain them back, or does not run under the server's limits.
    """
    try:
        uid, gid = pwd.getpwnam(RUN_AS).pw_uid, grp.getgrnam(RUN_GROUP).gr_gid
        done = subprocess.run(SANDBOX + [sys.executable, "-I", "-c", NNP_PROBE],
                              capture_output=True, text=True, timeout=60)
        if done.returncode != 0:  # this interpreter is not runnable by the user: the status and limits files alone
            done = subprocess.run(SANDBOX + ["cat", "/proc/self/status", "/proc/self/limits"], capture_output=True, text=True, timeout=60)
    except (KeyError, OSError, subprocess.SubprocessError) as exc:
        raise EvaluationError("Could not drop privileges; submitted code was not run") from exc
    if done.returncode != 0 or not privileges_dropped(done.stdout, uid, gid):
        raise EvaluationError("Could not drop privileges; submitted code was not run")
    if not limits_applied(done.stdout):
        raise EvaluationError("Could not limit the server's threads, file size and memory; submitted code was not run")
    if "OomLowered:\t1" in done.stdout:
        return ["the server's user can lower its own OOM priority on this machine; the evaluation raises it again every second"]
    return []


def seal_submission(source: Path) -> None:
    """Make the submission root's and read-only to the server's user: it cannot keep anything in its own files, and every
    start runs exactly what was delivered. Links are not followed."""
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        subprocess.run(["chown", "-R", "root:root", str(source)], check=False, capture_output=True, timeout=600)
        subprocess.run(["chmod", "-R", "a+rX,go-w", str(source)], check=False, capture_output=True, timeout=600)


def become_reaper() -> None:
    """Adopt the server's orphaned helpers (PR_SET_CHILD_SUBREAPER), so they can be reaped after they are killed."""
    with contextlib.suppress(Exception):
        import ctypes

        ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0)


class Progress:
    """What the evaluation has decided so far, shared with its caller: if the evaluation itself overruns (QA 07d M1), the
    caller publishes the reward from here, with a note, and the scenarios not yet decided count as not matched."""

    def __init__(self) -> None:
        self.started = time.monotonic()
        self.metrics: dict[str, Any] | None = None
        self.themes: list[list[str]] = []
        self.ids: list[str] = []
        self.results: list[dict[str, Any] | None] = []

    def summary(self, note: str) -> dict[str, Any] | None:
        """The reward and its breakdown from what is decided now, with `note`; None when the scenarios were never read."""
        if self.metrics is None:
            return None
        decided = list(self.results)
        results = [found or not_played(themes, scenario_id, LATE) for found, themes, scenario_id in zip(decided, self.themes, self.ids)]
        return tally(dict(self.metrics, notes=list(self.metrics["notes"]) + [note]), self.themes, results, self.started)


def tally(metrics: dict[str, Any], themes: list[list[str]], results: list[dict[str, Any]], started: float) -> dict[str, Any]:
    """The reward and its breakdown from the results: matched units over all units, by theme."""
    metrics = dict(metrics, notes=list(metrics["notes"]))
    metrics["by_theme"] = {name: {"total": value["total"], "matched": 0} for name, value in metrics["by_theme"].items()}
    metrics["scenarios_matched"] = metrics["units_matched"] = 0
    for names, result in zip(themes, results):
        metrics["scenarios_matched"] += result["matched"]
        for name, verdict in zip(names, result["units"]):
            metrics["units_matched"] += verdict
            metrics["by_theme"][name]["matched"] += verdict
    metrics["unfinished"] = sum(1 for result in results if result["reason"] == LATE)
    if metrics["unfinished"]:
        metrics["notes"].append(f"the replay reached its time limit of {DEADLINE_SEC} seconds; "
                                f"{metrics['unfinished']} scenarios were not played to the end")
    metrics["reward"] = round(metrics["units_matched"] / metrics["units_total"], 6)
    metrics["elapsed_sec"] = round(time.monotonic() - started, 1)
    metrics["results"] = results  # per-scenario diagnostics, written by the caller after the reward
    return metrics


def evaluate(source: Path, scenario_path: Path, work: Path, output: Path, sandbox: bool = True,
             media_dir: Path | None = None, progress: Progress | None = None) -> dict[str, Any]:
    """Grade the server in `source` against the scenarios in `scenario_path`.

    Args:
        source: The submitted /app/server directory.
        scenario_path: Private scenarios with the reference answers.
        work: Scratch directory.
        output: Directory for diagnostic files.
        sandbox: Run the server as the unprivileged user (off only in development checks).
        media_dir: The files the scenarios upload (default: `media` beside the scenarios).
        progress: Where the results go as they are decided, for a caller that may have to stop waiting.

    Returns:
        The reward and its breakdown. Nothing is deleted before it is returned: the container is discarded after the
        run, and a deletion the server made long would only delay the reward (QA 07d M2).

    Raises:
        EvaluationError: The private scenarios are unreadable, privileges cannot be dropped, or the machine has too
            little disk before the server starts.
    """
    progress = progress or Progress()
    clock = Clock(DEADLINE_SEC)
    candidate: Candidate | None = None
    log: LogCapture | None = None
    ballast: Ballast | None = None
    guard: Guard | None = None
    stats = Stats()
    try:
        media = Media(media_dir or scenario_path.parent / "media")
        corpus = Corpus(scenario_path, media)
        themes = corpus.themes
        total = sum(len(names) for names in themes)
        by_theme = {name: {"total": sum(names.count(name) for names in themes), "matched": 0} for name in sorted({n for ns in themes for n in ns})}
        metrics: dict[str, Any] = {"units_total": total, "units_matched": 0, "reward": 0.0, "scenarios_total": len(corpus),
                                   "scenarios_matched": 0, "restarts": 0, "planned_restarts": 0, "retried": 0, "retried_units": 0,
                                   "unfinished": 0, "notes": [], "by_theme": by_theme, "alone": sum(corpus.alone)}
        progress.themes, progress.ids, progress.results = themes, corpus.ids, [None] * len(corpus)
        progress.metrics = metrics
        if sandbox:
            metrics["notes"] += check_sandbox()
            become_reaper()
            metrics["grader_oom_score_adj"] = protect_grader()
        runner = source / "run"
        if source.is_symlink() or not source.is_dir():
            # an /app/server that could not be copied out of the agent's machine (QA 07 F3) arrives as nothing at all
            metrics["notes"].append("/app/server did not arrive: it is missing, or it could not be copied from the machine it was built on")
            results = [not_played(themes[index], corpus.ids[index], "no server to run") for index in range(len(corpus))]
        elif not runner.is_file() or not os.access(runner, os.X_OK):
            metrics["notes"].append("/app/server/run is missing or not executable")
            results = [not_played(themes[index], corpus.ids[index], "no server to run") for index in range(len(corpus))]
        else:
            stripped = strip_set_id(source)
            if stripped:
                metrics["notes"].append(f"set-user-id or set-group-id bits were removed from {stripped} submitted files")
            work.mkdir(parents=True, exist_ok=True)
            os.chmod(work, 0o755)
            if sandbox:
                seal_submission(source)
                ballast = Ballast(work / "ballast")
            for path in (work, output):  # the evaluation needs room here: a machine that has none is not the server's fault
                free = free_bytes(path)
                if free is not None and free < DISK_RESERVE:
                    raise EvaluationError(f"The machine has less than {DISK_RESERVE >> 20} MiB free on {path} before the server starts")
            log = LogCapture()
            candidate = Candidate(source, work, log, sandbox, clock)
            guard = Guard(candidate, [work, output, Path("/tmp")])
            for path, free in guard.start_free.items():
                if free is None:
                    metrics["notes"].append(f"{path} reports no size, so its free space is not watched")
                elif free < DISK_RESERVE:
                    metrics["notes"].append(f"{path} had {free >> 20} MiB free before the server started, so it is not watched")
            if candidate.start():
                results = play_all(candidate, corpus, media, clock, metrics, stats, progress.results)
            else:
                metrics["notes"].append(f"the server did not answer GET /api/health within {START_SEC} seconds")
                results = [not_played(themes[index], corpus.ids[index], "the server did not start") for index in range(len(corpus))]
    finally:
        clock.stop()
        if guard is not None:
            guard.stop()
        if candidate is not None:
            candidate.stop()
            if candidate.group is not None:
                candidate.group.remove()
        if log is not None:
            log.close(output / "server.log")
        if ballast is not None:
            ballast.release()  # room for the results however full the server left the disk
    if candidate is not None:
        metrics["restarts"], metrics["planned_restarts"] = candidate.restarts, candidate.planned
        metrics["server_peak_memory_kb"] = candidate.peak_memory
        if candidate.failed_starts >= START_FAILURES:
            metrics["notes"].append(f"the server stopped and did not come back after {START_FAILURES} restarts in a row")
        if candidate.halted:
            stopped = sum(1 for result in results if result["reason"] == candidate.halted)
            metrics["notes"].append(f"{candidate.halted}; {stopped} scenarios were not played to the end")
    if guard is not None:
        metrics["free_space_mib"] = guard.free_now()  # each watched path when the server started, and at the end
    metrics.update(stats.report())
    return tally(metrics, themes, results, progress.started)
