"""Build the delivered tree with the product's commands, run every case batch, and publish the reward.

The release to check comes from the verifier environment (`RELEASE`), never from the tree. The tree's own build
scripts and library code run only as the unprivileged `builder` user, without new privileges and under process and
file-size limits (and an address-space limit for the case programs). That user owns only four folders under
/tmp/hbv: the copy of the tree, the build, the case programs and its home. Every file root reads or writes is in
the root-only folder /var/lib/hbv or in /logs/verifier, is opened without following links (and is created only if
nothing of that name exists), and reaches a case program only as an open file on its standard input or output.
After every step run as `builder`, every process of that user is killed, round after round until none is left. At
the end they are killed once more, any reward file that exists is removed, metrics.json is written, and reward.txt
last.

One deadline covers the copy, the build and every batch: a step or batch that has not run by then is skipped and
its cases fail, and a reward is still written. Reads of a case program's output and of a step's log are capped by
the number of bytes read, so an output flood fails only its own batch. The case programs run with glibc's FMA and
AVX2 code paths turned off, so libm returns the same results on every x86-64 machine.

A delivered tree that carries upstream's 15.x release is not built, and scores 0 under the formula below: its
meson.build, src/hb-version.h or NEWS gives a 15.x version, or it holds one of the unit-test sources that only 15.x
has, byte for byte as upstream ships them. metrics.json says what was found.

Reward: D x G. D is the mean over the graded changes of each change's pass fraction. G is the held-fixed gate:
h_d x (1 - 0.10 x (1 - h_b)), where h_d is the mean over the changes of the pass fraction of each change's
neighbouring cases (inputs one stated condition away, on which the library must behave as 14.3.0 does) and h_b the
pass fraction of the other unchanged cases. metrics.json also lists every case's result, by kind and unit.

With RECORD=1 the outputs of every case are written to /logs/verifier/outputs.tsv and nothing is scored; the release
check is skipped there, since the outputs are recorded on upstream's release tree. A fault of the check itself
leaves no reward file.
"""

from __future__ import annotations

import contextlib
import ctypes
import errno
import json
import os
import pwd
import re
import shutil
import signal
import stat
import subprocess
import sys
import time
from collections import defaultdict
from hashlib import sha256
from pathlib import Path

TESTS = Path("/tests")
PRIVATE = TESTS / "private"
FONTS = TESTS / "inputs" / "fonts"
DRIVERS = TESTS / "driver"
TREE = Path("/app/harfbuzz")
# root's own; `builder` owns only the four folders below it
WORK = Path("/tmp/hbv")
SRC = WORK / "tree"
BUILD = WORK / "b"
BIN = WORK / "drv"
HOME = WORK / "home"
# root-only: batch inputs and outputs, step logs, the disk reserve, the result files
IO = Path("/var/lib/hbv")
LOGS = Path("/logs/verifier")
USER = "builder"
RELEASES = ("15.0.0", "15.1.0", "15.2.0")
W_BROAD = 0.10
# Case driver per case kind. hbdrv, hbapi and hbmeta use API that every release has; each hbapiNN probes one function
# the notes add, so a tree without that function fails only that function's cases.
PROGRAMS = {
    "shape": "hbdrv",
    "api": "hbapi",
    "meta": "hbmeta",
    "api48": "hbapi48",
    "api49": "hbapi49",
    "api51": "hbapi51",
}
MESON = [
    "meson", "setup", str(BUILD), "--buildtype=release", "--wrap-mode=nodownload", "-Ddefault_library=static",
    "-Dglib=disabled", "-Dgobject=disabled", "-Dcairo=disabled", "-Dchafa=disabled", "-Dicu=disabled",
    "-Dfreetype=disabled", "-Dpng=disabled", "-Dzlib=disabled", "-Dgraphite2=disabled",
    "-Draster=disabled", "-Dvector=disabled", "-Dgpu=disabled", "-Dsubset=disabled",
    "-Dtests=disabled", "-Dintrospection=disabled", "-Ddocs=disabled", "-Dutilities=disabled",
]  # fmt: skip
ENV = {
    "PATH": "/opt/py/bin:/usr/local/bin:/usr/bin:/bin",
    "HOME": str(HOME),
    "LC_ALL": "C.UTF-8",
    "LANG": "C.UTF-8",
}
# The case programs only. glibc picks libm's code paths by CPU feature; with its FMA and AVX2 paths turned off,
# every x86-64 machine takes the SSE2 paths, as an emulator or an older CPU does (glibc 2.33 and later spell the
# features this way; other architectures ignore the setting).
DRIVER_ENV = {**ENV, "GLIBC_TUNABLES": "glibc.cpu.hwcaps=-AVX2,-FMA,-FMA4"}

# Seconds from the start for the copy, the build and every batch (task.toml gives the verifier 2,400). ALARM is the
# last resort: whatever root itself is still doing then stops, and the reward is written.
DEADLINE = 1800
ALARM = DEADLINE + 300
# Each step's own limit, within what is left of the deadline: setup, build, each compile and each link of a case
# program, one case program over one font's cases. Past a step's own `timeout`, root stops it after GRACE.
SETUP_CAP = 900
BUILD_CAP = 1500
COMPILE_CAP = 300
BATCH_CAP = 120
GRACE = 20
# Killing the processes of `builder`, at most, each time.
SWEEP_SECONDS = 30
NPROC = 1024
# The largest file a build step may write (no file of a HarfBuzz build comes near it), the largest output a case
# program may write, and a case program's address space.
BUILD_FSIZE = 512 << 20
DRIVER_FSIZE = 64 << 20
DRIVER_AS = 4 << 30
# Bytes read from one batch's output (the largest real batch prints about 110 kB), and from a failed step's log.
MAX_OUTPUT = 16 << 20
LOG_TAIL = 4000
# The copy of the delivered tree: a larger file is left out; past the others the tree is not built. HarfBuzz
# 14.3.0 has 3,955 entries, about 100 MB, and is 7 folders deep.
MAX_FILE = 64 << 20
MAX_TREE_BYTES = 4 << 30
MAX_ENTRIES = 300_000
MAX_DEPTH = 64
# Room set aside in IO, and the result files made there at the start, filled and moved into place at the end, so
# that a tree that fills the disk cannot stop the reward.
RESERVE = 8 << 20
RESULT_SLOTS = ("result-1", "result-2")
RESULT_FILES = ("reward.txt", "reward.json", "metrics.json", "outputs.tsv")

# Upstream's unit-test sources that 15.0.0, 15.1.0 or 15.2.0 adds and 14.3.0 does not have, by sha256 of each
# release's copy. src/meson.build builds them only with -Dtests=enabled, which no build we ship uses, and no note
# needs them, so a tree holds one of them byte for byte only when upstream's release tree was copied into it.
RELEASE_ONLY = {
    "src/test-aat.cc": (
        "ac74dd8cd2bbbe61a7b17f32abe0deac77e0aafd6c899ec783a890c74e5c7a16",
        "bb71039cfde990faec13772b70ff72ff10e76f731734c0c8f741d586aa1c1249",
    ),
    "src/test-bit-vector.cc": (
        "cc494153903c71df4b72b249d40e064fbf84ed7c0d7d51adead22c624b66614e",
    ),
    "src/test-buffer.cc": (
        "88df5b44dc0f98c410c0058d5ef2f5ac0e6ac3089389c5d602f6df20cc6984c7",
    ),
    "src/test-cache.cc": (
        "859becb0e241e3a21a47abdbf23549f4930ae863ca786136d52ecfeb6f5f5c2f",
    ),
    "src/test-cbdt-cache.cc": (
        "c0b3449fd75c8678f914d343816237283c60d68990a4c0df7d8be7af60ae93d4",
        "cff82b02df15d705f70dade0f8bb6a48b25be0d79b902cf6a84f6327adf7754f",
    ),
    "src/test-checksum.cc": (
        "a0568997c55b8ac4160458999ac7dd83707608db4beba7e99c03cacd85745ec5",
    ),
    "src/test-colr.cc": (
        "3fe3fac5547c73bb8bd6b7602d2f362aad2bbb070d2efcd994c36a1454e94322",
    ),
    "src/test-gdef-cache.cc": (
        "40e6f10cc10f72e0ff536b0152d9d8944bd53be8fea7f453af0f8e9fe9e08540",
    ),
    "src/test-graphite2-buffer.cc": (
        "6ed44394fc28d4e48cf6a32791d5ef9dd8409986a004f66bef4906fbbd970a62",
        "bc005aec36b47fe7d04fb07cd39e486182e38cfd588d3b5d086277de501bec79",
    ),
    "src/test-jstf.cc": (
        "57edddc8781cb65f28d7d705301917c55fe10777b0bb7e69e6803447f6519d81",
        "fa24549269b972d1ecd9cc6989e53ac41449f2c1f3860e833c132da7689ee58c",
    ),
    "src/test-paint-extents.cc": (
        "f87834535eec9d2523f72d47980b40210ad9ee91ead7df94a64f1dec62585b6d",
    ),
    "src/test-raster-paint.cc": (
        "0120b746eed1412cf0735b57ce66769814a43ea77b3c8bb7ff1bcbad3bfd3fa3",
        "67c62c6645e3edbd1b4aaad42254fdd52a98f0c915b84d5cdaf51595654f645e",
    ),
    "src/test-result.cc": (
        "41afd2feeda00fe18c388ee8efb171023e965406ee2fc57f60682200179d8184",
    ),
    "src/test-subset-glyf-budget.cc": (
        "2ab9a221e1e833913138b7d7e9e42b180d763298fae6be56a132f781d5b7cb95",
    ),
    "src/test-uniscribe.cc": (
        "ac91f2c829dfed36bbde7f9fc23c90b2da72fcae320b582af3170e7d1645e8c5",
    ),
}
MAX_MARKER = 1 << 20  # the largest of those sources is 20 kB


class CheckFault(Exception):
    """The check itself could not be carried out; no reward may be published."""


class OutOfTime(BaseException):
    """Raised by the last-resort alarm; a BaseException, so that no handler for ordinary errors swallows it."""


class TreeRefused(Exception):
    """The delivered tree cannot be copied within the limits; it scores as a tree that does not build."""


def _out_of_time(signum, frame):
    raise OutOfTime()


def become_subreaper() -> None:
    """Orphaned processes of `builder` are handed to this process (PR_SET_CHILD_SUBREAPER), so they can be reaped."""
    try:
        ctypes.CDLL(None, use_errno=True).prctl(36, 1, 0, 0, 0)
    except (OSError, AttributeError):
        pass


def write_all(fd: int, data: bytes) -> None:
    view = memoryview(data)
    while view:
        view = view[os.write(fd, view) :]


def read_capped(fd: int, cap: int) -> bytes | None:
    """At most cap bytes from fd, counted as they are read; None if there are more."""
    chunks, total = [], 0
    while total <= cap:
        chunk = os.read(fd, min(1 << 20, cap + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return None if total > cap else b"".join(chunks)


def read_head(fd: int, cap: int) -> bytes:
    """The first cap bytes from fd (fewer at its end)."""
    chunks, total = [], 0
    while total < cap:
        chunk = os.read(fd, min(1 << 20, cap - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    return b"".join(chunks)


def read_member(root: Path, rel: str, cap: int, whole: bool) -> bytes | None:
    """A regular file of a tree, reached without following any link; None if there is none.

    With whole, a file larger than cap counts as none; else its first cap bytes are returned."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC
    try:
        fd = os.open(root, flags | os.O_DIRECTORY)
    except OSError:
        return None
    try:
        parts = rel.split("/")
        for part in parts[:-1]:
            sub = os.open(part, flags | os.O_DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = sub
        member = os.open(parts[-1], flags | os.O_NONBLOCK, dir_fd=fd)
        try:
            if not stat.S_ISREG(os.fstat(member).st_mode):
                return None
            return read_capped(member, cap) if whole else read_head(member, cap)
        finally:
            os.close(member)
    except OSError:
        return None
    finally:
        os.close(fd)


def release_markers(tree: Path) -> list[str]:
    """What in a tree comes from one of upstream's 15.x release trees; empty for our tree, however it was changed."""
    found = []
    text = read_member(tree, "meson.build", 1 << 18, whole=False) or b""
    head = re.search(rb"\bproject\s*\(", text)
    version = head and re.search(
        rb"\bversion\s*:\s*'([^']*)'", text[head.end() : head.end() + 4000]
    )
    if version and version.group(1).startswith(b"15."):
        found.append(
            f"meson.build: project version {version.group(1).decode(errors='replace')}"
        )
    text = read_member(tree, "src/hb-version.h", 1 << 18, whole=False) or b""
    major = re.search(rb"#define\s+HB_VERSION_MAJOR\s+(\d+)", text)
    string = re.search(rb'#define\s+HB_VERSION_STRING\s+"([^"]*)"', text)
    if (major and major.group(1) == b"15") or (
        string and string.group(1).startswith(b"15.")
    ):
        found.append("src/hb-version.h: version 15")
    text = read_member(tree, "NEWS", 1 << 16, whole=False) or b""
    news = re.search(rb"^Overview of changes leading to (\S+)", text, re.MULTILINE)
    if news and news.group(1).startswith(b"15."):
        found.append(f"NEWS: newest entry {news.group(1).decode(errors='replace')}")
    for rel, digests in sorted(RELEASE_ONLY.items()):
        data = read_member(tree, rel, MAX_MARKER, whole=True)
        if data is not None and sha256(data).hexdigest() in digests:
            found.append(f"{rel}: upstream's 15.x file")
    return found


def remove_entry(dir_fd: int, name: str) -> None:
    """Remove whatever has this name in the folder (a file, a link or a whole folder), never following a link."""
    try:
        os.unlink(name, dir_fd=dir_fd)
    except FileNotFoundError:
        pass
    except (IsADirectoryError, PermissionError):
        shutil.rmtree(
            name, dir_fd=dir_fd
        )  # the descriptor-based walk: links inside are removed, not followed


def write_new(dir_fd: int, name: str, data: bytes) -> None:
    """Create a file that must not exist yet (a link of that name is refused, not followed) and write it."""
    fd = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o644,
        dir_fd=dir_fd,
    )
    try:
        os.fchmod(fd, 0o644)
        write_all(fd, data)
    finally:
        os.close(fd)


class Folder:
    """A folder root keeps to itself: made fresh with mode 0700, used only through its descriptor."""

    def __init__(self, path: Path):
        try:
            os.mkdir(path, 0o700)
        except OSError as exc:
            raise CheckFault(f"{path} cannot be made: {exc.strerror}") from exc
        self.fd = os.open(
            path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        os.fchmod(self.fd, 0o700)
        st = os.fstat(self.fd)
        if st.st_uid != 0 or stat.S_IMODE(st.st_mode) != 0o700:
            raise CheckFault(f"{path} is not root's alone")
        self.reserved = False

    def create(self, name: str) -> int:
        return os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=self.fd,
        )

    def open(self, name: str) -> int:
        return os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=self.fd)

    def remove(self, name: str) -> None:
        try:
            os.unlink(name, dir_fd=self.fd)
        except FileNotFoundError:
            pass

    def tail(self, name: str, size: int) -> str:
        """The last `size` bytes of a file here, read as text."""
        fd = self.open(name)
        try:
            end = os.fstat(fd).st_size
            return os.pread(fd, size, max(0, end - size)).decode(
                "utf-8", errors="replace"
            )
        finally:
            os.close(fd)

    def reserve(self) -> None:
        """Set aside room and files for the results, so that a tree that fills the disk cannot stop them."""
        fd = self.create("reserve")
        try:
            block = bytes(1 << 20)
            for _ in range(RESERVE >> 20):
                write_all(fd, block)
        finally:
            os.close(fd)
        for slot in RESULT_SLOTS:
            os.close(self.create(slot))
        self.reserved = True

    def release(self) -> None:
        if self.reserved:
            self.remove("reserve")
            self.reserved = False

    def publish(self, logs: int, files: list[tuple[str, bytes]]) -> None:
        """Remove every result file that exists in /logs/verifier, then put the given ones there in order (the
        reward last): each is written into a file set aside here and renamed into place, or written there afresh
        where /logs/verifier is another file system."""
        for name in RESULT_FILES:
            remove_entry(logs, name)
        for slot, (name, data) in zip(RESULT_SLOTS, files):
            fd = os.open(
                slot,
                os.O_WRONLY | os.O_TRUNC | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=self.fd,
            )
            try:
                os.fchmod(fd, 0o644)
                write_all(fd, data)
            finally:
                os.close(fd)
            try:
                os.rename(slot, name, src_dir_fd=self.fd, dst_dir_fd=logs)
            except OSError as exc:
                if exc.errno != errno.EXDEV:
                    raise
                write_new(logs, name, data)


class Clock:
    """The one deadline for the copy, the build and every batch."""

    def __init__(self, seconds: int):
        self.deadline = time.monotonic() + seconds

    def left(self) -> float:
        return self.deadline - time.monotonic()

    def limit(self, cap: int) -> int:
        return int(min(cap, self.left()))


class Sweeper:
    """Kills every process of `builder`, round after round until none is left."""

    def __init__(self, uid: int, gid: int, notes: list[str]):
        self.uid, self.gid, self.notes = uid, gid, notes

    def _kill_all(self) -> None:
        # kill(-1) from a process of that user reaches every process the user may signal in one system call, so a
        # process that forks cannot outrun it (the kernel also cancels a fork it interrupts).
        pid = os.fork()
        if pid == 0:
            try:
                os.setgroups([])
                os.setresgid(self.gid, self.gid, self.gid)
                os.setresuid(self.uid, self.uid, self.uid)
                os.kill(-1, signal.SIGKILL)
            finally:
                os._exit(0)  # whatever happened, this child goes no further
        try:
            os.waitpid(pid, 0)
        except ChildProcessError:
            pass

    def alive(self) -> list[int]:
        """Processes whose real, effective or saved user is `builder` and that have not yet exited."""
        found = []
        try:
            names = os.listdir("/proc")
        except OSError:
            return found
        for name in names:
            if not name.isdigit():
                continue
            try:
                with open(f"/proc/{name}/status", "rb") as fh:
                    status = fh.read(1 << 16)
            except OSError:
                continue
            state = re.search(rb"^State:\s*(\S)", status, re.MULTILINE)
            uids = re.search(rb"^Uid:\s*(\d+)\s+(\d+)\s+(\d+)", status, re.MULTILINE)
            if (
                uids
                and self.uid in {int(u) for u in uids.groups()}
                and not (state and state.group(1) in (b"Z", b"X"))
            ):
                found.append(int(name))
        return found

    @staticmethod
    def _reap() -> None:
        """Collect the exit status of every child that has ended (only while no step of ours is waiting)."""
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return
            if pid == 0:
                return

    def sweep(self, after: str) -> int:
        """Kill every process of `builder`; return how many are still there when the time runs out (0 normally)."""
        left = len(self.alive())
        if left:
            self.notes.append(
                f"{after}: {left} processes of {USER} left running; killed"
            )
        end = time.monotonic() + SWEEP_SECONDS
        while True:
            self._kill_all()
            alive = self.alive()
            for pid in alive:
                try:
                    os.kill(pid, signal.SIGKILL)
                except OSError:
                    pass
            self._reap()
            if not alive:
                return 0
            if time.monotonic() >= end:
                self.notes.append(
                    f"{after}: {len(alive)} processes of {USER} could not be stopped"
                )
                return len(alive)
            time.sleep(0.05)


class Context:
    def __init__(
        self, notes: list[str], uid: int, gid: int, sweeper: Sweeper, clock: Clock
    ):
        self.notes, self.uid, self.gid, self.sweeper, self.clock = (
            notes,
            uid,
            gid,
            sweeper,
            clock,
        )
        self.io = Folder(IO)
        try:
            self.io.reserve()
        except OSError as exc:
            raise CheckFault(
                f"no room for the check's own files: {exc.strerror}"
            ) from exc
        self.step_logs: dict[str, str] = {}
        self.batches = {"run": 0, "failed": 0, "not_run": 0}


def builder_ids() -> tuple[int, int]:
    try:
        entry = pwd.getpwnam(USER)
    except KeyError as exc:
        raise CheckFault(f"user {USER} is missing") from exc
    if entry.pw_uid == 0 or entry.pw_gid == 0:
        raise CheckFault(f"user {USER} is privileged")
    return entry.pw_uid, entry.pw_gid


def open_logs(notes: list[str], uid: int) -> int:
    """/logs/verifier, made 0755 so that only its owner (root, or the host user it is mounted from) can write there.

    Harbor makes it 0777 for verifiers that run as other users. Where the mount does not allow the change, nothing
    else depends on it: every process of `builder` is killed, and any reward file removed, before root writes."""
    LOGS.mkdir(parents=True, exist_ok=True)
    fd = os.open(LOGS, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        if os.fstat(fd).st_uid == uid:
            os.fchown(fd, 0, 0)
        os.fchmod(fd, 0o755)
    except OSError as exc:
        notes.append(f"/logs/verifier stays as mounted ({exc.strerror})")
    st = os.fstat(fd)
    if st.st_uid == uid or st.st_mode & 0o022:
        notes.append(
            f"/logs/verifier is mode {stat.S_IMODE(st.st_mode):o}, owner {st.st_uid}"
        )
    return fd


def as_builder(
    cmd: list[str],
    *,
    cwd: Path,
    limit: int,
    stdin: int,
    stdout: int,
    stderr: int,
    env: dict[str, str],
    fsize: int,
    memory: int = 0,
) -> int | None:
    """Run a command as `builder` with a clean environment and limits; None if root had to stop it.

    Its standard streams are root's open files or /dev/null, never a pipe, so a process it leaves behind cannot
    hold this call; `timeout` ends the command, and root ends `timeout` if that does not return in time."""
    limits = [
        f"--nproc={NPROC}",
        f"--fsize={fsize}",
        "--core=0",
        *([f"--as={memory}"] if memory else []),
    ]
    wrapped = [
        "prlimit", *limits, "--",
        "setpriv", f"--reuid={USER}", f"--regid={USER}", "--clear-groups", "--no-new-privs", "--",
        "timeout", "--kill-after=5", str(limit), *cmd,
    ]  # fmt: skip
    try:
        return subprocess.run(
            wrapped,
            cwd=cwd,
            env=env,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            timeout=limit + GRACE,
            check=False,
        ).returncode
    except subprocess.TimeoutExpired:
        return None


def prepare(record: bool) -> tuple[list[dict], dict[str, str]]:
    if os.geteuid() != 0:
        raise CheckFault("the check must run as root")
    release = os.environ.get("RELEASE", "")
    if release not in RELEASES:
        raise CheckFault(f"unknown RELEASE {release!r}")
    for tool in ("setpriv", "prlimit", "timeout", "meson", "ninja", "cc", "c++"):
        if shutil.which(tool, path=ENV["PATH"]) is None:
            raise CheckFault(f"{tool} is missing")
    try:
        cases = [
            json.loads(line)
            for line in (PRIVATE / "cases.jsonl").read_text().splitlines()
            if line
        ]
        expected = (
            {}
            if record
            else json.loads((PRIVATE / "expected.json").read_text())[release]
        )
    except (OSError, ValueError, KeyError) as exc:
        raise CheckFault(f"private inputs unreadable: {exc}") from exc
    if not cases or (not record and any(c["id"] not in expected for c in cases)):
        raise CheckFault("private inputs incomplete")
    for kind in {c.get("drv", "shape") for c in cases}:
        if kind not in PROGRAMS or not (DRIVERS / f"{PROGRAMS[kind]}.c").is_file():
            raise CheckFault(f"driver for {kind!r} missing")
    return cases, expected


def make_work(ctx: Context) -> None:
    """/tmp/hbv as root's (0755), with the folders `builder` may write: the build, the case programs, its home."""
    try:
        os.mkdir(WORK, 0o755)
    except OSError as exc:
        raise CheckFault(f"{WORK} cannot be made: {exc.strerror}") from exc
    st = os.lstat(WORK)
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0:
        raise CheckFault(f"{WORK} is not root's")
    os.chmod(WORK, 0o755)
    for folder in (BUILD, BIN, HOME):
        os.mkdir(folder, 0o755)
        os.lchown(folder, ctx.uid, ctx.gid)


def copy_file(src: str, dst: str, st: os.stat_result, uid: int, gid: int) -> None:
    sfd = os.open(src, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        if not stat.S_ISREG(os.fstat(sfd).st_mode):
            return
        dfd = os.open(
            dst,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
        )
        try:
            left = st.st_size
            while left > 0:
                chunk = os.read(sfd, min(1 << 20, left))
                if not chunk:
                    break
                write_all(dfd, chunk)
                left -= len(chunk)
            os.fchown(dfd, uid, gid)
            os.fchmod(dfd, stat.S_IMODE(st.st_mode) & 0o777)
            os.utime(dfd, ns=(st.st_atime_ns, st.st_mtime_ns))
        finally:
            os.close(dfd)
    finally:
        os.close(sfd)


def copy_tree(ctx: Context) -> bool:
    """Copy the delivered tree for `builder`: links as links, without special files, build folders or huge files.

    No process of `builder` exists yet and nothing else writes the tree, so every folder this walk enters was seen
    as a real folder (not a link) a moment before; files are opened without following links all the same."""
    try:
        top = os.lstat(TREE)
    except OSError:
        top = None
    if top is None or not stat.S_ISDIR(top.st_mode):
        ctx.notes.append("/app/harfbuzz is missing")
        return False
    os.mkdir(SRC, 0o700)
    os.chmod(SRC, 0o755)
    os.lchown(SRC, ctx.uid, ctx.gid)
    pending = [(str(TREE), str(SRC), 0)]
    entries = size = left_out = 0
    started = time.monotonic()
    try:
        while pending:
            src_dir, dst_dir, depth = pending.pop()
            for name in sorted(os.listdir(src_dir)):
                entries += 1
                if entries > MAX_ENTRIES:
                    raise TreeRefused(f"more than {MAX_ENTRIES} entries")
                if entries % 256 == 0 and ctx.clock.left() <= 0:
                    raise TreeRefused("the time was up")
                src, dst = os.path.join(src_dir, name), os.path.join(dst_dir, name)
                st = os.lstat(src)
                if stat.S_ISLNK(st.st_mode):
                    os.symlink(os.readlink(src), dst)
                    os.lchown(dst, ctx.uid, ctx.gid)
                elif stat.S_ISDIR(st.st_mode):
                    try:
                        build_dir = stat.S_ISDIR(
                            os.lstat(os.path.join(src, "meson-private")).st_mode
                        )
                    except OSError:
                        build_dir = False
                    if build_dir or depth + 1 > MAX_DEPTH:
                        left_out += 1
                        continue
                    os.mkdir(dst, 0o700)
                    os.chmod(dst, (stat.S_IMODE(st.st_mode) & 0o755) | 0o700)
                    os.lchown(dst, ctx.uid, ctx.gid)
                    pending.append((src, dst, depth + 1))
                elif stat.S_ISREG(st.st_mode) and st.st_size <= MAX_FILE:
                    size += st.st_size
                    if size > MAX_TREE_BYTES:
                        raise TreeRefused(
                            f"more than {MAX_TREE_BYTES >> 30} GiB of files"
                        )
                    copy_file(src, dst, st, ctx.uid, ctx.gid)
                else:
                    left_out += 1  # pipes, sockets, devices, files over MAX_FILE
    except TreeRefused as exc:
        ctx.notes.append(f"copy: tree not built, {exc}")
        return False
    except OSError as exc:
        ctx.notes.append(f"copy: tree not built, {exc.strerror} ({exc.filename})")
        return False
    ctx.notes.append(
        f"copy: {entries} entries, {left_out} left out (build folders, special and huge files), "
        f"{size >> 20} MiB in {time.monotonic() - started:.0f}s"
    )
    return True


def step(ctx: Context, name: str, cmd: list[str], cwd: Path, cap: int) -> bool:
    """One build step as `builder`, its output in a root-only log; every process of `builder` killed afterwards."""
    limit = ctx.clock.limit(cap)
    if limit < 1:
        ctx.notes.append(f"{name}: not run, the time was up")
        return False
    log_name = f"{name}.log"
    try:
        log = ctx.io.create(log_name)
    except OSError as exc:
        ctx.notes.append(f"{name}: not run, its log cannot be made ({exc.strerror})")
        return False
    started = time.monotonic()
    try:
        code = as_builder(
            cmd,
            cwd=cwd,
            limit=limit,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=ENV,
            fsize=BUILD_FSIZE,
        )
    finally:
        os.close(log)
        ctx.sweeper.sweep(name)
    took = time.monotonic() - started
    if timed_out(code, took, limit):
        ctx.notes.append(
            f"{name}: stopped at its time limit ({limit}s) after {took:.0f}s"
        )
    else:
        ctx.notes.append(f"{name}: exit {code} in {took:.0f}s")
    if code != 0:
        try:
            ctx.step_logs[name] = ctx.io.tail(log_name, LOG_TAIL)
        except OSError:
            pass
    ctx.io.remove(log_name)
    return code == 0


def build(ctx: Context, kinds: set[str]) -> dict[str, Path]:
    """Copy and build the delivered tree as `builder`; return the case programs that compiled and linked."""
    make_work(ctx)
    if not copy_tree(ctx):
        return {}
    # Build out of tree, as `builder`.
    if not (
        step(ctx, "setup", MESON, SRC, SETUP_CAP)
        and step(ctx, "build", ["ninja", "-C", str(BUILD), "-j", "4"], SRC, BUILD_CAP)
    ):
        return {}
    drivers: dict[str, Path] = {}
    for kind in sorted(kinds):
        name = PROGRAMS[kind]
        obj, exe = BIN / f"{name}.o", BIN / name
        compiled = step(
            ctx,
            f"{name}-compile",
            [
                "cc", "-O2", "-Werror=implicit-function-declaration", "-c",
                "-Isrc", f"-I{BUILD / 'src'}", "-o", str(obj), str(DRIVERS / f"{name}.c"),
            ],
            SRC,
            COMPILE_CAP,
        ) and step(
            ctx,
            f"{name}-link",
            ["c++", "-o", str(exe), str(obj), str(BUILD / "src" / "libharfbuzz.a"), "-lm"],
            SRC,
            COMPILE_CAP,
        )  # fmt: skip
        if compiled:
            drivers[kind] = exe
    return drivers


def in_fonts(opts: str) -> str:
    """Option values that name a second font (noto/... or synth/...) point into the font folder."""
    return re.sub(
        r"(^|=)((?:noto|synth)/)", lambda m: f"{m.group(1)}{FONTS}/{m.group(2)}", opts
    )


def run_batch(
    ctx: Context,
    n: int,
    kind: str,
    font: str,
    items: list[dict],
    exe: Path,
    limit: int,
    outputs: dict[str, str],
) -> None:
    """One case program over one font's cases: its input and output are root's files, handed over as open files."""
    label = f"batch {n} ({kind} {font}, {len(items)} cases)"
    in_name, out_name = f"batch-{n}.in", f"batch-{n}.out"
    data = "".join(
        f"{c['id']}\t{FONTS / font}\t{c['idx']}\t{in_fonts(c['opts'])}\t{c['text']}\n"
        for c in items
    ).encode()
    fin = fout = -1
    try:
        fd = ctx.io.create(in_name)
        try:
            write_all(fd, data)
        finally:
            os.close(fd)
        fin = ctx.io.open(in_name)
        fout = ctx.io.create(out_name)
    except OSError as exc:
        for opened in (fin, fout):
            if opened >= 0:
                os.close(opened)
        ctx.io.remove(in_name)
        ctx.io.remove(out_name)
        ctx.batches["failed"] += 1
        ctx.notes.append(f"{label}: not run, its files cannot be made ({exc.strerror})")
        return
    started = time.monotonic()
    try:
        code = as_builder(
            [str(exe)],
            cwd=Path("/"),
            limit=limit,
            stdin=fin,
            stdout=fout,
            stderr=subprocess.DEVNULL,
            env=DRIVER_ENV,
            fsize=DRIVER_FSIZE,
            memory=DRIVER_AS,
        )
    finally:
        os.close(fin)
        os.close(fout)
        ctx.sweeper.sweep(label)
    ctx.batches["run"] += 1
    # Read only now that no process of `builder` is left to write it, and no more than MAX_OUTPUT + 1 bytes.
    raw = None
    try:
        fd = ctx.io.open(out_name)
        try:
            raw = read_capped(fd, MAX_OUTPUT)
        finally:
            os.close(fd)
    except OSError:
        pass
    ctx.io.remove(in_name)
    ctx.io.remove(out_name)
    if raw is None:
        ctx.batches["failed"] += 1
        ctx.notes.append(
            f"{label}: output over {MAX_OUTPUT >> 20} MiB or unreadable; its cases fail"
        )
        return
    ids = {c["id"] for c in items}
    for line in raw.decode("utf-8", errors="replace").splitlines():
        cid, _, result = line.partition("\t")
        if cid in ids:  # a batch answers only for its own cases
            outputs[cid] = result
    if code != 0:
        ctx.batches["failed"] += 1
        took = time.monotonic() - started
        how = (
            f"stopped at its time limit ({limit}s)"
            if timed_out(code, took, limit)
            else f"exit {code}"
        )
        ctx.notes.append(f"{label}: {how}; the cases it had not printed fail")


def run_batches(
    ctx: Context, drivers: dict[str, Path], cases: list[dict], outputs: dict[str, str]
) -> None:
    """One case program per driver and font, so a hang, crash or flood costs only that batch's cases."""
    batches: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in cases:
        batches[(c.get("drv", "shape"), c["font"])].append(c)
    not_run = 0
    for n, ((kind, font), items) in enumerate(sorted(batches.items())):
        if kind not in drivers:
            continue  # its cases fail: the case program did not compile or link
        limit = ctx.clock.limit(BATCH_CAP)
        if limit < 1:
            ctx.batches["not_run"] += 1
            not_run += len(items)
            continue
        run_batch(ctx, n, kind, font, items, drivers[kind], limit, outputs)
    if not_run:
        ctx.notes.append(
            f"{ctx.batches['not_run']} batches ({not_run} cases) not run: the time was up"
        )


def score(cases: list[dict], expected: dict[str, str], outputs: dict[str, str]) -> dict:
    units: dict[str, list[bool]] = defaultdict(list)
    duals: dict[str, list[bool]] = defaultdict(list)
    broad: list[bool] = []
    families: dict[str, list[bool]] = defaultdict(list)
    case_pass: dict[str, dict[str, dict[str, int]]] = {
        "changed": {},
        "dual": {},
        "broad": {},
    }
    for c in cases:
        ok = outputs.get(c["id"]) == expected[c["id"]]
        kind = c["kind"] if c["kind"] in ("changed", "dual") else "broad"
        case_pass[kind].setdefault(str(c.get("unit", kind)), {})[c["id"]] = int(ok)
        if kind == "changed":
            units[c["unit"]].append(ok)
            families[c["family"]].append(ok)
        elif kind == "dual":
            duals[c["unit"]].append(ok)
        else:
            broad.append(ok)
    per_unit = {u: sum(v) / len(v) for u, v in sorted(units.items())}
    per_dual = {u: sum(v) / len(v) for u, v in sorted(duals.items())}
    d = sum(per_unit.values()) / len(per_unit) if per_unit else 0.0
    h_d = sum(per_dual.values()) / len(per_dual) if per_dual else 1.0
    h_b = sum(broad) / len(broad) if broad else 1.0
    gate = h_d * (1 - W_BROAD * (1 - h_b))
    return {
        "reward": round(d * gate, 6),
        "D": round(d, 6),
        "h_dual": round(h_d, 6),
        "h_broad": round(h_b, 6),
        "gate": round(gate, 6),
        "units": {
            u: {"pass": round(p, 4), "cases": len(units[u])}
            for u, p in per_unit.items()
        },
        "neighbours": {
            u: {"pass": round(p, 4), "cases": len(duals[u])}
            for u, p in per_dual.items()
        },
        "families": {
            f: {"pass": round(sum(v) / len(v), 4), "cases": len(v)}
            for f, v in sorted(families.items())
        },
        "broad": {
            "pass": round(h_b, 4) if broad else None,
            "cases": len(broad),
        },
        # Every case's result (1 pass, 0 fail) by kind and unit, under its opaque id.
        "case_pass": case_pass,
    }


def timed_out(code: int | None, took: float, limit: int) -> bool:
    """`timeout` exits 124 when it stopped the command, 137 when it had to kill it; None: root stopped it."""
    return code is None or code == 124 or (code == 137 and took >= limit)


def main() -> int:
    become_subreaper()
    signal.signal(signal.SIGALRM, _out_of_time)
    signal.alarm(ALARM)
    record = os.environ.get("RECORD") == "1"
    notes: list[str] = []
    logs = sweeper = None
    published = False
    try:
        clock = Clock(DEADLINE)
        uid, gid = builder_ids()
        sweeper = Sweeper(uid, gid, notes)
        logs = open_logs(notes, uid)
        for name in RESULT_FILES:
            remove_entry(logs, name)
        cases, expected = prepare(record)
        ctx = Context(notes, uid, gid, sweeper, clock)
        outputs: dict[str, str] = {}
        drivers: dict[str, Path] = {}
        markers: list[str] = []
        try:
            markers = [] if record else release_markers(TREE)
            if markers:
                notes.append(
                    "not built: the tree carries upstream's 15.x release files"
                )
            else:
                drivers = build(ctx, {c.get("drv", "shape") for c in cases})
                run_batches(ctx, drivers, cases, outputs)
        except OutOfTime:
            notes.append(
                "stopped at the last-resort time limit; what had not run fails"
            )
        signal.alarm(0)
        sweeper.sweep("the last batch")
        ctx.io.release()
        if record:
            if "shape" not in drivers:
                raise CheckFault("the reference tree did not build")
            files = [
                (
                    "outputs.tsv",
                    "".join(
                        f"{c['id']}\t{outputs.get(c['id'], '!missing')}\n"
                        for c in cases
                    ).encode(),
                )
            ]
            summary = {
                "recorded": len(cases),
                "drivers": sorted(drivers),
                "notes": notes,
            }
        else:
            metrics = score(cases, expected, outputs)
            metrics |= {
                "release": os.environ["RELEASE"],
                "release_markers": markers,
                "notes": notes,
                "step_logs": ctx.step_logs,
                "batches": ctx.batches,
                "drivers": sorted(drivers),
                "cases": len(cases),
                "outputs": len(outputs),
            }
            files = [
                (
                    "metrics.json",
                    (json.dumps(metrics, indent=1, sort_keys=True) + "\n").encode(),
                ),
                ("reward.txt", f"{metrics['reward']}\n".encode()),
            ]
            summary = {
                k: metrics[k]
                for k in ("reward", "D", "h_dual", "h_broad", "cases", "outputs")
            }
        ctx.io.publish(logs, files)
        published = True
        print(json.dumps(summary))
        return 0
    except CheckFault as exc:
        print(f"check fault: {exc}", file=sys.stderr)
        return 1
    finally:
        signal.alarm(0)
        if not published:
            # No reward of ours: make sure none from anywhere else is left either.
            with contextlib.suppress(OSError):
                if sweeper is not None:
                    sweeper.sweep("a fault")
                if logs is not None:
                    for name in ("reward.txt", "reward.json"):
                        remove_entry(logs, name)


if __name__ == "__main__":
    sys.exit(main())
