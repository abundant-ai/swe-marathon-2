"""Run a case against a `carve` executable and compare what it prints with an expected answer.

Each case is written into the same fixed directory, so that paths in an output are the same for every
run, and each run gets new empty directories as its HOME and TMPDIR, a fixed set of environment
variables, and the same resource limits: an 8 MB stack, bounds on processes, file size and data, at
most MEMORY_LIMIT bytes of memory in use, and at most DISK_LIMIT bytes and FILES_LIMIT files and
directories of its own on disk.

The disk and file limits count only what the run itself holds: the files, directories and links its
user owns under OWN_ROOTS (the directories it can write to), and the files its processes still
hold open after deleting them; without a user of its own (recording), its workspace, HOME and
TMPDIR. That count is taken whenever the free figures (statvfs) of /tmp's or /dev/shm's
filesystem drop by more than a limit since the last count, so other writers on a shared
filesystem never stop a run; the per-file size limit (RLIMIT_FSIZE) holds everywhere.

A case is {"argv": [...], "files": {path: text}, "stdin": text or null}; its texts, like the
recorded answers, hold any byte that is not UTF-8 as a surrogate escape. A run passes when the
program's exit code and the bytes of its standard output equal the expected ones.

`confine` is `limit` plus a seccomp filter that denies the network to the process and to
everything it starts: socket() and socketpair() fail with EACCES for every address family but
AF_UNIX, io_uring cannot be set up, and every system call made through another ABI (32-bit x86,
x32) fails the same way. So a run has no network whatever the machine's own network allows.
"""

from __future__ import annotations

import ctypes
import os
import resource
import selectors
import signal
import stat
import struct
import subprocess
import tempfile
import time
from pathlib import Path

WORKSPACE = Path("/tmp/carve-case")
HOME = Path("/tmp/carve-home")  # HOME and TMPDIR of a run, new and empty for each
TEMP = Path("/tmp/carve-tmp")
CASE_SEC = 2
OUTPUT_LIMIT = 1_000_000  # bytes of standard output read at most; more fails the run
MEMORY_LIMIT = (
    4 << 30
)  # bytes of memory in use (resident, and shared memory) by a run's processes at most
DISK_LIMIT = 1 << 30  # bytes of files of its own a run holds on disk, at most
FILES_LIMIT = 100_000  # files, directories and links of its own, at most
# Where a run's user can leave files; verify.py adds every world-writable directory it finds.
OWN_ROOTS = ["/tmp", "/var/tmp", "/dev/shm"]
WATCHED_FILESYSTEMS = (
    "/tmp",
    "/dev/shm",
)  # whose free figures prompt a count of the run's own files
LIMITS = {
    resource.RLIMIT_STACK: 8 << 20,
    resource.RLIMIT_NPROC: 512,  # processes and threads of the user running the case
    resource.RLIMIT_FSIZE: 256 << 20,
    # Writable private mappings: high on purpose, since runtimes (Go's, a JIT's) reserve address
    # space they never touch; memory in use is bounded by MEMORY_LIMIT instead.
    resource.RLIMIT_DATA: 256 << 30,
    resource.RLIMIT_CORE: 0,
}
ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin",
    "LC_ALL": "C.UTF-8",
    "LANG": "C.UTF-8",
    "NO_COLOR": "1",
    "TERM": "dumb",
}
ENCODING = ("utf-8", "surrogateescape")
PAGE = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096

# The seccomp filter of `confine`: for each architecture it runs on, the audit architecture the
# kernel reports, the numbers of socket() and socketpair(), and those of io_uring_setup(),
# io_uring_enter() and io_uring_register(). Any other architecture value (a 32-bit ABI) is denied
# every system call.
FILTER_ARCHES = {
    "x86_64": (0xC000003E, (41, 53), (425, 426, 427)),
    "aarch64": (0xC00000B7, (198, 199), (425, 426, 427)),
}
X32_BIT = 0x40000000  # x86_64 system call numbers at or above this are the x32 ABI's
AF_UNIX = 1
EACCES = 13
SECCOMP_RET_ALLOW = 0x7FFF0000
SECCOMP_RET_DENY = 0x00050000 | EACCES  # SECCOMP_RET_ERRNO with EACCES
PR_SET_NO_NEW_PRIVS = 38
PR_SET_SECCOMP = 22
SECCOMP_MODE_FILTER = 2
# Classic BPF opcodes: load a 32-bit word of seccomp_data, compare, return.
BPF_LD_W_ABS = 0x20
BPF_JEQ_K = 0x15
BPF_JGE_K = 0x35
BPF_RET_K = 0x06
SECCOMP_NR, SECCOMP_ARCH, SECCOMP_ARG0 = (
    0,
    4,
    16,
)  # offsets in seccomp_data (arg0's low word)


def filter_program() -> list[tuple]:
    """The filter as classic BPF with symbolic jumps: (opcode, jump if true, jump if false, k),
    where a jump is a label (a string) or 0 for the next instruction, and labels stand alone."""
    program: list = [(BPF_LD_W_ABS, 0, 0, SECCOMP_ARCH)]
    for machine, (arch, _, _) in FILTER_ARCHES.items():
        program.append((BPF_JEQ_K, machine, 0, arch))
    program.append((BPF_RET_K, 0, 0, SECCOMP_RET_DENY))
    for machine, (_, sockets, uring) in FILTER_ARCHES.items():
        program += [machine, (BPF_LD_W_ABS, 0, 0, SECCOMP_NR)]
        if machine == "x86_64":
            program.append((BPF_JGE_K, "deny", 0, X32_BIT))
        program += [(BPF_JEQ_K, "family", 0, number) for number in sockets]
        program += [(BPF_JEQ_K, "deny", 0, number) for number in uring]
        program.append((BPF_RET_K, 0, 0, SECCOMP_RET_ALLOW))
    program += [
        "family",
        (BPF_LD_W_ABS, 0, 0, SECCOMP_ARG0),
        (BPF_JEQ_K, "allow", "deny", AF_UNIX),
        "allow",
        (BPF_RET_K, 0, 0, SECCOMP_RET_ALLOW),
        "deny",
        (BPF_RET_K, 0, 0, SECCOMP_RET_DENY),
    ]
    return program


def assemble(program: list) -> bytes:
    """The struct sock_filter array of a program from `filter_program`, its labels resolved to
    the relative jumps classic BPF takes.

    Raises:
        ValueError: A jump goes backwards or further than 255 instructions.
    """
    labels, index = {}, 0
    for item in program:
        if isinstance(item, str):
            labels[item] = index
        else:
            index += 1
    code, index = [], 0
    for item in program:
        if isinstance(item, str):
            continue
        opcode, true, false, k = item
        jumps = [
            labels[jump] - index - 1 if isinstance(jump, str) else jump
            for jump in (true, false)
        ]
        if not all(0 <= jump <= 255 for jump in jumps):
            raise ValueError(f"jump out of range at instruction {index}")
        code.append(struct.pack("=HBBI", opcode, jumps[0], jumps[1], k))
        index += 1
    return b"".join(code)


class SockFprog(ctypes.Structure):
    _fields_ = [("len", ctypes.c_ushort), ("filter", ctypes.c_void_p)]


FILTER = assemble(filter_program())


def deny_network() -> None:
    """Install the seccomp filter on this process (after no_new_privs, which the kernel requires of
    a process without CAP_SYS_ADMIN); it holds for every process this one starts.

    Raises:
        OSError: The kernel refused it, or this is not Linux on x86_64 or aarch64.
    """
    if os.uname().sysname != "Linux" or os.uname().machine not in FILTER_ARCHES:
        raise OSError(
            f"no seccomp filter for {os.uname().sysname} {os.uname().machine}"
        )
    prctl = ctypes.CDLL(None, use_errno=True).prctl
    prctl.argtypes = [ctypes.c_int] + [ctypes.c_ulong] * 4
    prctl.restype = ctypes.c_int
    buffer = ctypes.create_string_buffer(FILTER, len(FILTER))
    program = SockFprog(len(FILTER) // 8, ctypes.addressof(buffer))
    if prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_NO_NEW_PRIVS) failed")
    if prctl(PR_SET_SECCOMP, SECCOMP_MODE_FILTER, ctypes.addressof(program), 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl(PR_SET_SECCOMP) failed")


def confine() -> None:
    """In a child about to run the program: `limit`, then the network denied (`deny_network`)."""
    limit()
    deny_network()


def limit() -> None:
    """In a child about to run a case: the resource limits, the same for every run, and the first
    claim on the out-of-memory killer. The process count only bounds runs that root starts: in a
    user's own shell the user's other processes count too."""
    for which, value in LIMITS.items():
        if which == resource.RLIMIT_NPROC and os.geteuid() != 0:
            continue
        try:
            resource.setrlimit(which, (value, value))
        except (
            ValueError,
            OSError,
        ):  # a hard limit below the value, or an OS maximum (macOS's data size)
            _, hard = resource.getrlimit(which)
            try:
                resource.setrlimit(
                    which,
                    (
                        hard
                        if hard != resource.RLIM_INFINITY and 0 <= hard < value
                        else value,
                        hard,
                    ),
                )
            except (ValueError, OSError):
                pass
    try:
        Path("/proc/self/oom_score_adj").write_text("1000")
    except OSError:
        pass


def remove_path(path: Path) -> None:
    """Remove whatever is at `path` without following a symbolic link: a directory with everything
    under it, however deep (rm -rf), anything else by itself.

    Raises:
        OSError: It is still there.
    """
    try:
        mode = os.lstat(path).st_mode
    except FileNotFoundError:
        return
    if not stat.S_ISDIR(mode):
        os.unlink(path)
        return
    try:
        subprocess.run(
            ["rm", "-rf", "--", str(path)],
            capture_output=True,
            timeout=120,
            check=False,
        )
    except subprocess.SubprocessError as exc:
        raise OSError(f"rm: {type(exc).__name__}") from exc
    if os.path.lexists(path):
        raise OSError(f"{path} could not be removed")


def clear_workspace() -> None:
    """Remove whatever is at the workspace, HOME and TMPDIR paths."""
    for path in (WORKSPACE, HOME, TEMP):
        remove_path(path)


def prepare(case: dict, ids: tuple[int, int] | None) -> None:
    """A new workspace holding the case's files and a new empty HOME and TMPDIR, all owned by
    `ids` (user and group ids) where given."""
    clear_workspace()
    for path in (WORKSPACE, HOME, TEMP):
        path.mkdir(parents=True)
    for name, text in case["files"].items():
        target = WORKSPACE / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(text.encode(*ENCODING))
    if ids:
        for top in (WORKSPACE, HOME, TEMP):
            for root, directories, files in os.walk(top):
                for name in directories + files:
                    os.lchown(os.path.join(root, name), *ids)
            os.lchown(top, *ids)


def disk_free(path: Path = WORKSPACE.parent) -> tuple[int, int, int]:
    """The bytes and the files (inodes) free on the filesystem holding `path`, and its total of
    files; -1 for a figure it does not report (no size, no inode table)."""
    try:
        info = os.statvfs(path)
    except (OSError, AttributeError):
        return -1, -1, -1
    return (
        info.f_bavail * info.f_frsize if info.f_blocks else -1,
        info.f_favail if info.f_files else -1,
        info.f_files if info.f_files else -1,
    )


def disk_baseline() -> dict[str, tuple[int, int, int]]:
    """The free figures of each watched filesystem now, the point a run's disk use is measured from."""
    return {place: disk_free(Path(place)) for place in WATCHED_FILESYSTEMS}


def own_use(
    uid: int | None, most_bytes: int = DISK_LIMIT, most_files: int = FILES_LIMIT
) -> tuple[int, int]:
    """The bytes allocated to, and the number of, the files, directories and links a run holds of
    its own: with a user of its own, those it owns under OWN_ROOTS (descending only into directories
    it owns or anyone may write to) and the files its processes hold open after deleting them;
    without one, everything under the workspace, HOME and TMPDIR. The count stops once either figure
    passes its limit. Links are never followed."""
    used = entries = 0
    seen: set[tuple[int, int]] = set()
    roots = OWN_ROOTS if uid is not None else [str(WORKSPACE), str(HOME), str(TEMP)]
    folders = [
        root
        for root in dict.fromkeys(roots)
        if os.path.isdir(root) and not os.path.islink(root)
    ]
    while folders and used <= most_bytes and entries <= most_files:
        folder = folders.pop()
        try:
            listing = os.scandir(folder)
        except OSError:
            continue
        with listing:
            for entry in listing:
                try:
                    info = entry.stat(follow_symlinks=False)
                except OSError:
                    continue
                mine = uid is None or info.st_uid == uid
                if mine and (info.st_dev, info.st_ino) not in seen:
                    seen.add((info.st_dev, info.st_ino))
                    entries += 1
                    if stat.S_ISREG(info.st_mode):
                        used += info.st_blocks * 512
                if stat.S_ISDIR(info.st_mode) and (mine or info.st_mode & stat.S_IWOTH):
                    folders.append(entry.path)
    if uid is not None:
        for pid in (name for name in _listdir("/proc") if name.isdigit()):
            try:
                if os.stat(f"/proc/{pid}").st_uid != uid:
                    continue
                for fd in _listdir(f"/proc/{pid}/fd"):
                    info = os.stat(
                        f"/proc/{pid}/fd/{fd}"
                    )  # the open file itself, deleted or not
                    if (
                        stat.S_ISREG(info.st_mode)
                        and info.st_nlink == 0
                        and (info.st_dev, info.st_ino) not in seen
                    ):
                        seen.add((info.st_dev, info.st_ino))
                        used += info.st_blocks * 512
            except OSError:
                continue
    return used, entries


def _listdir(path: str) -> list[str]:
    """The names in a directory, or none where it cannot be read."""
    try:
        return os.listdir(path)
    except OSError:
        return []


def over_limit(
    group: int, uid: int | None, baseline: dict[str, tuple[int, int, int]]
) -> str | None:
    """What limit a run is past. Memory is read every time. The disk and file limits are checked by
    counting the run's own files (own_use) only when a watched filesystem's free bytes or files have
    dropped by more than a limit since `baseline`; when the run's own files are within the limits,
    others wrote the difference, and `baseline` (changed in place) starts from the figures now."""
    if memory_in_use(group, uid) > MEMORY_LIMIT:
        return "memory limit"
    now = disk_baseline()
    dropped = any(
        before[0] >= 0
        and after[0] >= 0
        and before[0] - after[0] > DISK_LIMIT
        or before[1] >= 0
        and after[1] >= 0
        and before[1] - after[1] > FILES_LIMIT
        for before, after in (
            (baseline.get(place, after), after) for place, after in now.items()
        )
    )
    if not dropped:
        return None
    used, entries = own_use(uid)
    if used > DISK_LIMIT:
        return "disk limit"
    if entries > FILES_LIMIT:
        return "file limit"
    baseline.update(now)
    return None


def memory_in_use(group: int, uid: int | None) -> int:
    """The memory a run's processes use: the resident memory of those of user `uid` where given,
    with the shared memory segments that user owns or created, else of those of process group
    `group`; 0 where /proc cannot tell."""
    total = 0
    if uid is not None:
        try:
            header, *rows = Path("/proc/sysvipc/shm").read_text().splitlines()
            columns = header.split()
            for row in rows:
                values = dict(zip(columns, row.split()))
                if str(uid) in (
                    values.get("uid"),
                    values.get("cuid"),
                ):  # cuid: no IPC_SET changes it
                    total += int(values.get("rss", values.get("size", "0")))
        except (OSError, ValueError):
            pass
    try:
        entries = [entry for entry in os.listdir("/proc") if entry.isdigit()]
    except OSError:
        return total
    for pid in entries:
        try:
            fields = Path(f"/proc/{pid}/stat").read_bytes().rsplit(b")", 1)[1].split()
            if (
                (os.stat(f"/proc/{pid}").st_uid != uid)
                if uid is not None
                else int(fields[2]) != group
            ):
                continue
            total += int(fields[21]) * PAGE
        except (OSError, IndexError, ValueError):
            continue
    return total


def read_output(
    proc: subprocess.Popen,
    data: bytes,
    cutoff_at: float,
    uid: int | None,
    free: dict[str, tuple[int, int, int]],
) -> tuple[bytes, str | None]:
    """Feed `data` to the program's standard input and read its standard output until it closes
    it. Returns what was read and None, or what stopped the reading: "timeout" at the cutoff_at,
    "output limit" past OUTPUT_LIMIT bytes, or a limit `over_limit` names."""
    chunks, size = [], 0
    pending = memoryview(data)
    with selectors.DefaultSelector() as selector:
        selector.register(proc.stdout, selectors.EVENT_READ)
        if pending:
            os.set_blocking(proc.stdin.fileno(), False)
            selector.register(proc.stdin, selectors.EVENT_WRITE)
        else:
            proc.stdin.close()
        while selector.get_map():
            left = cutoff_at - time.monotonic()
            if left <= 0:
                return b"", "timeout"
            problem = over_limit(proc.pid, uid, free)
            if problem:
                return b"", problem
            for key, _ in selector.select(min(left, 0.05)):
                if key.fileobj is proc.stdin:
                    try:
                        pending = pending[
                            os.write(proc.stdin.fileno(), pending[:65536]) :
                        ]
                    except BlockingIOError:
                        continue
                    except OSError:  # the program closed its input
                        pending = pending[:0]
                    if not pending:
                        selector.unregister(proc.stdin)
                        proc.stdin.close()
                    continue
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    selector.unregister(proc.stdout)
                    continue
                size += len(chunk)
                if size > OUTPUT_LIMIT:
                    return b"", "output limit"
                chunks.append(chunk)
    return b"".join(chunks), None


def stop(proc: subprocess.Popen) -> None:
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    proc.wait()


def run_case(
    program: list[str],
    case: dict,
    prefix: list[str] | None = None,
    ids: tuple[int, int] | None = None,
    keep_stderr: bool = False,
    env: dict | None = None,
    preexec=None,
) -> dict:
    """Run one case: its exit code, its standard output as bytes, how long it took and the CPU time
    it used, and with `keep_stderr` the first 64 KB of its standard error. `env` adds environment
    variables and `preexec` replaces `limit` in the child (the verifier passes `confine`). A case
    that cannot be set up or started,
    runs past CASE_SEC, prints more than OUTPUT_LIMIT bytes or passes a limit of `over_limit` has
    no exit code and an "error" instead."""
    try:
        prepare(case, ids)
    except OSError as exc:
        return {
            "exit": None,
            "stdout": None,
            "error": f"workspace: {type(exc).__name__}",
            "seconds": 0.0,
            "cpu": 0.0,
        }
    errors = tempfile.TemporaryFile() if keep_stderr else None  # noqa: SIM115 - The stream stays open for the owning process.
    free = disk_baseline()
    before = resource.getrusage(resource.RUSAGE_CHILDREN)
    started = time.monotonic()
    try:
        proc = subprocess.Popen(
            (prefix or []) + program + case["argv"],
            cwd=WORKSPACE,
            env=dict(ENV, HOME=str(HOME), TMPDIR=str(TEMP), **(env or {})),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=errors or subprocess.DEVNULL,
            start_new_session=True,
            preexec_fn=preexec or limit,  # noqa: PLW1509 - Install child limits before the command starts.
        )
    except (OSError, subprocess.SubprocessError):
        if errors:
            errors.close()
        return {
            "exit": None,
            "stdout": None,
            "error": "could not start",
            "seconds": 0.0,
            "cpu": 0.0,
        }
    cutoff_at = started + CASE_SEC
    try:
        uid = ids[0] if ids else None
        out, problem = read_output(
            proc, (case.get("stdin") or "").encode(*ENCODING), cutoff_at, uid, free
        )
        while (
            problem is None and proc.poll() is None
        ):  # output closed: the limits hold to the end
            problem = (
                "timeout"
                if time.monotonic() > cutoff_at
                else over_limit(proc.pid, uid, free)
            )
            if problem is None:
                time.sleep(0.02)
    finally:
        if proc.returncode is None:
            stop(proc)
        for stream in (proc.stdin, proc.stdout):
            if not stream.closed:
                stream.close()
    seconds = round(time.monotonic() - started, 4)
    after = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = round(after.ru_utime + after.ru_stime - before.ru_utime - before.ru_stime, 4)
    stderr = b""
    if errors:
        errors.seek(0)
        stderr = errors.read(1 << 16)
        errors.close()
    if problem:
        return {
            "exit": None,
            "stdout": None,
            "error": problem,
            "seconds": seconds,
            "cpu": cpu,
            "stderr": stderr,
        }
    return {
        "exit": proc.returncode,
        "stdout": out,
        "seconds": seconds,
        "cpu": cpu,
        "stderr": stderr,
    }


def matches(got: dict, want: dict) -> bool:
    """A run printed the expected answer: the same exit code and the same bytes on standard output."""
    return (
        got["exit"] is not None
        and got["exit"] == want["exit"]
        and got["stdout"] == want["stdout"].encode(*ENCODING)
    )
