"""Game processes with resource limits, captured output and whole-tree kills.

A game process is started through a small launcher (a fresh Python interpreter with no
threads) that applies the resource limits and then executes the game, so the limits are
in place before any game code runs. Each process gets its own session and process
group. While it runs, a watchdog samples its memory, the size of its home folder and its
wall time, and kills the whole process tree when a limit is passed; its output goes
through a pipe of which only the first and last parts are kept.

Linux-only paths (a cgroup per process: memory, process count and CPU caps, and an
atomic kill of everything in it) are used when the caller passes a cgroup folder; on
macOS the limits are rlimits plus the watchdog, and the kill walks the process table.
"""

from __future__ import annotations

import collections
import ctypes
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

IS_LINUX = sys.platform.startswith("linux")
IS_MACOS = sys.platform == "darwin"

# The launcher: applies the limits in its own process, joins the cgroup when one is
# given, then replaces itself with the game. Runs with -I -S, so nothing from the
# current directory or site-packages is imported.
LAUNCHER = r"""
import json, os, resource, sys
spec = json.loads(sys.argv[1])
for name, soft, hard in spec["rlimits"]:
    which = getattr(resource, name, None)
    if which is None:
        continue
    try:
        resource.setrlimit(which, (soft, hard))
    except (ValueError, OSError):
        pass
if spec.get("cgroup"):
    with open(os.path.join(spec["cgroup"], "cgroup.procs"), "w") as f:
        f.write("0")
os.execve(spec["argv"][0], spec["argv"], spec["env"])
"""


@dataclass(frozen=True)
class Limits:
    """Resource limits for one game process. None means no limit of that kind.

    Attributes:
        cpu_s: CPU seconds (user + system) before the process is stopped (RLIMIT_CPU;
            the hard limit is 5 s higher).
        memory_mb: Largest memory footprint (macOS phys_footprint, Linux RSS or the
            cgroup's usage) before the watchdog kills the tree.
        wall_s: Seconds of wall time from start before the watchdog kills the tree.
        file_mb: Largest size of any one file the process writes (RLIMIT_FSIZE).
        disk_mb: Largest total size of the process's home folder (sampled).
        nofile: Most open file descriptors (RLIMIT_NOFILE).
        nproc: Most processes in the tree (Linux: the cgroup's pids.max).
        log_head_mb: Output kept from the start.
        log_tail_mb: Output kept from the end.
    """

    cpu_s: float | None = None
    memory_mb: float | None = None
    wall_s: float | None = None
    file_mb: float | None = 2048
    disk_mb: float | None = None
    nofile: int | None = 4096
    nproc: int | None = None
    log_head_mb: float = 8
    log_tail_mb: float = 2


@dataclass
class ExitInfo:
    """How a game process ended.

    Attributes:
        code: Exit status when it exited normally, else None.
        signal: Signal number when a signal ended it, else None.
        violation: The limit the kit enforced ("memory", "wall", "disk", "cpu",
            "file_size") or None. A kill requested by the caller is "killed".
        wall_s: Seconds from start to end.
        cpu_s: CPU seconds used (user + system), when known.
        peak_memory_mb: Largest memory sample seen by the watchdog.
        output_bytes: Bytes the process wrote to stdout and stderr in total.
        output_dropped: Bytes of output not kept in the log.
        stray_pids: Processes of the tree still found after the kill (should be empty).
    """

    code: int | None
    signal: int | None
    violation: str | None
    wall_s: float
    cpu_s: float | None
    peak_memory_mb: float
    output_bytes: int
    output_dropped: int
    stray_pids: list[int] = field(default_factory=list)


def footprint_mb(pid: int) -> float | None:
    """Current memory footprint of one process in MiB, or None when unknown.

    macOS: phys_footprint from proc_pid_rusage (what Activity Monitor calls memory;
    RSS shrinks under memory pressure and understates it). Linux: VmRSS.

    Args:
        pid: Process id.

    Returns:
        The footprint, or None when the process is gone or the platform gives none.
    """
    if IS_MACOS:
        return _macos_footprint(pid)
    try:
        for line in Path(f"/proc/{pid}/status").read_text().splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024.0
    except (OSError, ValueError, IndexError):
        return None
    return None


class _RusageInfoV2(ctypes.Structure):
    _fields_ = [  # the ctypes layout of rusage_info_v2
        ("ri_uuid", ctypes.c_uint8 * 16),
        ("ri_user_time", ctypes.c_uint64),
        ("ri_system_time", ctypes.c_uint64),
        ("ri_pkg_idle_wkups", ctypes.c_uint64),
        ("ri_interrupt_wkups", ctypes.c_uint64),
        ("ri_pageins", ctypes.c_uint64),
        ("ri_wired_size", ctypes.c_uint64),
        ("ri_resident_size", ctypes.c_uint64),
        ("ri_phys_footprint", ctypes.c_uint64),
        ("ri_proc_start_abstime", ctypes.c_uint64),
        ("ri_proc_exit_abstime", ctypes.c_uint64),
        ("ri_child_user_time", ctypes.c_uint64),
        ("ri_child_system_time", ctypes.c_uint64),
        ("ri_child_pkg_idle_wkups", ctypes.c_uint64),
        ("ri_child_interrupt_wkups", ctypes.c_uint64),
        ("ri_child_pageins", ctypes.c_uint64),
        ("ri_child_elapsed_abstime", ctypes.c_uint64),
        ("ri_diskio_bytesread", ctypes.c_uint64),
        ("ri_diskio_byteswritten", ctypes.c_uint64),
    ]


_LIBPROC = None


def _macos_footprint(pid: int) -> float | None:
    """phys_footprint of pid in MiB via libproc (see footprint_mb)."""
    global _LIBPROC
    if _LIBPROC is None:
        try:
            _LIBPROC = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        except OSError:
            _LIBPROC = False
    if not _LIBPROC:
        return None
    info = _RusageInfoV2()
    if _LIBPROC.proc_pid_rusage(pid, 2, ctypes.byref(info)) != 0:
        return None
    return info.ri_phys_footprint / (1024.0 * 1024.0)


def process_table() -> dict[int, int]:
    """Map every visible process id to its parent id.

    Used to find a game's descendants, including those that left its process group.

    Returns:
        {pid: ppid}; empty when the table cannot be read.
    """
    if IS_LINUX:
        table = {}
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            try:
                stat = Path(f"/proc/{entry}/stat").read_text()
                ppid = int(stat.rsplit(")", 1)[1].split()[1])
            except (OSError, ValueError, IndexError):
                continue
            table[int(entry)] = ppid
        return table
    try:
        out = subprocess.run(
            ["ps", "-A", "-o", "pid=,ppid="],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return {}
    table = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            table[int(parts[0])] = int(parts[1])
    return table


def descendants(root: int, table: dict[int, int]) -> set[int]:
    """All processes below root in a process table (not including root).

    Args:
        root: Process id whose descendants are wanted.
        table: {pid: ppid} as returned by process_table.

    Returns:
        The descendant pids.
    """
    children: dict[int, list[int]] = collections.defaultdict(list)
    for pid, ppid in table.items():
        children[ppid].append(pid)
    found: set[int] = set()
    stack = [root]
    while stack:
        for child in children.get(stack.pop(), []):
            if child not in found and child != root:
                found.add(child)
                stack.append(child)
    return found


def folder_mb(path: Path, stop_at_mb: float | None = None) -> float:
    """Total size of the regular files under path, in MiB (links not followed).

    Args:
        path: Folder to measure; a missing folder measures 0.
        stop_at_mb: Stop counting once this size is passed (the watchdog only needs to
            know that a cap is exceeded).

    Returns:
        The size in MiB (at least stop_at_mb when counting stopped early).
    """
    total = 0
    limit = None if stop_at_mb is None else stop_at_mb * 1024 * 1024
    for dirpath, _dirs, files in os.walk(path):
        for name in files:
            try:
                st = os.lstat(os.path.join(dirpath, name))
            except OSError:
                continue
            total += st.st_size
            if limit is not None and total > limit:
                return total / (1024.0 * 1024.0)
    return total / (1024.0 * 1024.0)


def rlimits_for(limits: Limits) -> list[tuple[str, int, int]]:
    """The rlimits the launcher applies for a set of limits.

    Args:
        limits: The process's limits.

    Returns:
        (resource name, soft, hard) triples; RLIMIT_CORE is always 0 so a crash or a
        limit signal never writes a core file.
    """
    out = [("RLIMIT_CORE", 0, 0)]
    if limits.cpu_s is not None:
        soft = max(1, int(limits.cpu_s))
        out.append(("RLIMIT_CPU", soft, soft + 5))
    if limits.file_mb is not None:
        size = int(limits.file_mb * 1024 * 1024)
        out.append(("RLIMIT_FSIZE", size, size))
    if limits.nofile is not None:
        out.append(("RLIMIT_NOFILE", limits.nofile, limits.nofile))
    return out


class Proc:
    """One game process (and everything it starts), with its limits enforced.

    Start it, talk to it (through the telemetry link, not this class), then call close()
    or kill(). Threads: one reads the output, one waits for the exit, one watches limits.
    """

    def __init__(
        self,
        argv: list[str],
        env: dict[str, str],
        cwd: Path,
        limits: Limits,
        log_path: Path | None,
        home: Path | None = None,
        cgroup: Path | None = None,
        user: str | int | None = None,
    ) -> None:
        """Start the process.

        Args:
            argv: Program and arguments; argv[0] must be an absolute path.
            env: The complete environment of the process (nothing is inherited).
            cwd: Working directory.
            limits: Resource limits.
            log_path: File for the kept output (head, then a note, then the tail);
                None discards it.
            home: The process's home folder, watched against limits.disk_mb.
            cgroup: Linux only: a prepared cgroup v2 folder the process joins before it
                executes the game; its pids.max, memory.max and cgroup.kill are used.
            user: Linux only, when running as root: the user to run the game as.

        Raises:
            OSError: The process could not be started.
        """
        self.limits = limits
        self.home = home
        self.cgroup = cgroup
        self.violation: str | None = None
        self.peak_mb = 0.0
        self.t_start = time.monotonic()
        self._seen: set[int] = set()
        self._exit: tuple[int, object] | None = None
        self._done = threading.Event()
        self._lock = threading.Lock()
        spec = {
            "argv": argv,
            "env": env,
            "rlimits": rlimits_for(limits),
            "cgroup": str(cgroup) if cgroup else None,
        }
        launcher = [sys.executable, "-I", "-S", "-c", LAUNCHER, json.dumps(spec)]
        self._log = open(log_path, "wb") if log_path else None  # noqa: SIM115 - closed by the reader thread
        self._popen = subprocess.Popen(
            launcher,
            cwd=cwd,
            env={},
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
            user=user if IS_LINUX else None,
        )
        self.pid = self._popen.pid
        self._head_left = int(limits.log_head_mb * 1024 * 1024)
        self._tail: collections.deque[bytes] = collections.deque()
        self._tail_bytes = 0
        self.output_bytes = 0
        self.output_dropped = 0
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._waiter = threading.Thread(target=self._wait_exit, daemon=True)
        self._watch = threading.Thread(target=self._watchdog, daemon=True)
        self._reader.start()
        self._waiter.start()
        self._watch.start()

    # ---------------------------------------------------------------- threads
    def _read_output(self) -> None:
        """Drain the output pipe: keep the head in the log, the tail in memory."""
        tail_cap = int(self.limits.log_tail_mb * 1024 * 1024)
        stream = self._popen.stdout
        while True:
            try:
                chunk = stream.read1(1 << 16) if stream else b""
            except (OSError, ValueError):
                break
            if not chunk:
                break
            self.output_bytes += len(chunk)
            if self._head_left > 0:
                keep = chunk[: self._head_left]
                self._head_left -= len(keep)
                if self._log:
                    self._log.write(keep)
                chunk = chunk[len(keep) :]
            if chunk:
                self._tail.append(chunk)
                self._tail_bytes += len(chunk)
                while self._tail_bytes > tail_cap and self._tail:
                    old = self._tail.popleft()
                    self._tail_bytes -= len(old)
                    self.output_dropped += len(old)
        if self._log:
            if self.output_dropped:
                note = f"\n[... {self.output_dropped} bytes of output not kept ...]\n"
                self._log.write(note.encode())
            for part in self._tail:
                self._log.write(part)
            self._log.close()

    def _wait_exit(self) -> None:
        """Reap the process and record its status and resource use."""
        try:
            _pid, status, usage = os.wait4(self.pid, 0)
        except ChildProcessError:
            status, usage = 0, None
        self._exit = (status, usage)
        self._popen.returncode = (
            os.waitstatus_to_exitcode(status) if usage is not None else 0
        )
        self._done.set()

    def _watchdog(self) -> None:
        """Sample memory, disk and wall time; track descendants; kill on a violation."""
        lim = self.limits
        last_tree = last_disk = 0.0
        while not self._done.wait(0.25):
            now = time.monotonic()
            mb = footprint_mb(self.pid)
            if mb is not None:
                self.peak_mb = max(self.peak_mb, mb)
            if lim.memory_mb is not None and mb is not None and mb > lim.memory_mb:
                self._violate("memory")
            if lim.wall_s is not None and now - self.t_start > lim.wall_s:
                self._violate("wall")
            if now - last_tree > 2.0:
                last_tree = now
                found = descendants(self.pid, process_table())
                with self._lock:
                    self._seen |= found
            if (
                self.home is not None
                and lim.disk_mb is not None
                and now - last_disk > 2.0
            ):
                last_disk = now
                if folder_mb(self.home, lim.disk_mb) > lim.disk_mb:
                    self._violate("disk")

    def _violate(self, kind: str) -> None:
        """Record the first violated limit and kill the tree."""
        with self._lock:
            if self.violation is None:
                self.violation = kind
        self.kill_tree()

    # ---------------------------------------------------------------- control
    def alive(self) -> bool:
        """Whether the game process has not ended yet."""
        return not self._done.is_set()

    def wait(self, timeout_s: float | None) -> bool:
        """Wait for the process to end; returns True when it has ended."""
        return self._done.wait(timeout_s)

    def kill_tree(self) -> list[int]:
        """Kill the process and every process it started; return pids still alive.

        Order: the cgroup (Linux, atomic), the process group, then every descendant
        seen during the run or found now. Safe to call more than once.

        Returns:
            Pids from the tree that still exist after the kill (should be empty).
        """
        if self.cgroup is not None:
            try:
                (self.cgroup / "cgroup.kill").write_text("1")
            except OSError:
                pass
        targets = self._tree_now()
        if self.alive() or targets:
            # The group id cannot have been reused while a member is alive.
            try:
                os.killpg(self.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        for pid in sorted(targets):
            try:
                os.kill(pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
        self._done.wait(10)
        alive = sorted(targets)
        for _ in range(20):
            alive = [pid for pid in alive if _exists(pid)]
            if not alive:
                break
            time.sleep(0.05)
        return alive

    def _tree_now(self) -> set[int]:
        """Processes of this game's tree that exist now.

        The descendants of the game process (while it is alive) plus processes seen
        earlier that are still in its process group. A process seen earlier that is in
        neither may be an unrelated process that reused the id, so it is left alone.
        """
        found = descendants(self.pid, process_table()) if self.alive() else set()
        with self._lock:
            seen = set(self._seen)
        for pid in seen - found:
            try:
                if os.getpgid(pid) == self.pid:
                    found.add(pid)
            except (ProcessLookupError, PermissionError):
                continue
        return found

    def kill(self) -> ExitInfo:
        """Kill the tree now (marking the end as "killed" unless a limit came first)."""
        with self._lock:
            if self.violation is None and self.alive():
                self.violation = "killed"
        stray = self.kill_tree()
        return self._finish(stray)

    def close(self, grace_s: float) -> ExitInfo:
        """Wait up to grace_s for the process to end by itself, then kill the tree.

        The tree is always killed at the end, so nothing the game started outlives it.

        Args:
            grace_s: Seconds to wait for a normal exit.

        Returns:
            How the process ended.
        """
        ended = self.wait(grace_s)
        if not ended:
            with self._lock:
                if self.violation is None:
                    self.violation = "killed"
        stray = self.kill_tree()
        return self._finish(stray)

    def _finish(self, stray: list[int]) -> ExitInfo:
        """Collect the exit status once the process has been reaped."""
        self._done.wait(10)
        self._reader.join(timeout=10)
        status, usage = self._exit if self._exit else (0, None)
        code = sig = None
        if usage is not None:
            if os.WIFEXITED(status):
                code = os.WEXITSTATUS(status)
            elif os.WIFSIGNALED(status):
                sig = os.WTERMSIG(status)
        violation = self.violation
        if violation in (None, "killed") and sig == signal.SIGXCPU:
            violation = "cpu"
        if violation in (None, "killed") and sig == signal.SIGXFSZ:
            violation = "file_size"
        cpu = (usage.ru_utime + usage.ru_stime) if usage is not None else None
        return ExitInfo(
            code=code,
            signal=sig,
            violation=violation,
            wall_s=round(time.monotonic() - self.t_start, 3),
            cpu_s=round(cpu, 3) if cpu is not None else None,
            peak_memory_mb=round(self.peak_mb, 1),
            output_bytes=self.output_bytes,
            output_dropped=self.output_dropped,
            stray_pids=stray,
        )


def _exists(pid: int) -> bool:
    """Whether a process id currently exists (a zombie counts as existing)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def which_godot(explicit: str | None = None) -> str:
    """Locate the Godot binary.

    Order: the explicit path, $QA_GODOT, /opt/godot/godot, then godot on PATH.

    Args:
        explicit: A path given by the caller, or None.

    Returns:
        An absolute path to an executable.

    Raises:
        FileNotFoundError: No Godot binary was found.
    """
    for cand in (explicit, os.environ.get("QA_GODOT"), "/opt/godot/godot"):
        if cand and os.path.isfile(cand) and os.access(cand, os.X_OK):
            return os.path.abspath(cand)
    found = shutil.which("godot")
    if found:
        return os.path.abspath(found)
    raise FileNotFoundError("no Godot binary: set QA_GODOT or install /opt/godot/godot")
