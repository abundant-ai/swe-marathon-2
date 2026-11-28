"""Build the delivered tree with the product's commands, run every case batch, and publish the reward.

The release to check comes from the verifier environment (`RELEASE`), never from the tree. The tree's own build
scripts and library code run only as a user of their own (`builder`, with fresh numeric ids for each run), without new
privileges, under process, file-size and address-space limits, and first in line for the kernel's out-of-memory
killer. That user owns only five folders under /var/lib/hbv-work, on the disk: the copy of the tree, the build, the
case programs, its home and its temporary files. Every file root reads or writes is in the root-only folder
/var/lib/hbv or in /logs/verifier, is opened without following links (and is created only if nothing of that name
exists), and reaches a case program only as an open file on its standard input or output. Before any of the tree's
code runs, a child of root with `builder`'s ids must fail to create a file in /logs/verifier; if it succeeds, the
check stops with no reward.

After every step run as `builder`, every process of that user is killed, round after round until none is left, by a
child of root whose effective user is `builder` and whose real and saved user is a spare one, which no process of
`builder` may signal; every wait for it is bounded, and if root cannot fork it kills the processes one by one. A sweep
that leaves processes running fails the tree: it scores 0 and nothing more of it runs. At the end they are killed once
more, everything `builder` made in the folders every user may write is removed, any reward file that exists is
removed, case_pass.json and metrics.json are written, and reward.txt last.

One deadline covers the copy, the build and every batch: a step or batch that has not run by then is skipped and its
cases fail, each batch leaves time for the batches after it, and a reward is still written. An alarm stays armed to
the end; when it fires, what has been scored is published. Reads of a case program's output and of a step's log are
capped by the number of bytes read, and a result longer than MAX_RESULT characters fails its case. Outside RECORD=1
root keeps of each case only whether it passed and a short digest of its output, so a flood fails only its own batch.
The case programs run with glibc's FMA and AVX2 code paths turned off, so libm returns the same results on every
x86-64 machine.

Before any process of `builder` exists, root reads the delivered tree. A tree that the post-session sweep refused
(/tests/sweep_check.py, where it is shipped), that holds DROPIN_QUORUM or more of the unit-test sources only
upstream's 15.x releases have, byte for byte as upstream ships them, or whose meson.build, NEWS, src or
src/hb-version.h is a link, is not built, and scores 0. A tree whose version is not 14.3.0 (meson.build's project
version, src/hb-version.h's four values, the newest heading of NEWS) is built and scored, and its reward is scaled by
VERSION_FACTOR. A new function that is not declared in the header its note names fails that unit's cases. metrics.json
says what was found.

Reward: D x G, times VERSION_FACTOR for a version that is not 14.3.0. D is the mean over the graded changes of each
change's pass fraction. G is the held-fixed gate: h_d x (1 - 0.10 x (1 - h_b)), where h_d is the mean over the changes
of the pass fraction of each change's neighbouring cases (inputs one stated condition away, on which the library must
behave as 14.3.0 does) and h_b the pass fraction of the other unchanged cases. case_pass.json lists every case's
result, by kind and unit, with the first 8 hex digits of sha256(salt, the output as printed, in UTF-8); the salt is
sha256 of DIGEST_TAG and the bytes of /tests/private/expected.json, so only its holder can match the digests.

With RECORD=1 the outputs of every case are written to /logs/verifier/outputs.tsv and nothing is scored; the release
check, the sweep's word and the declarations are skipped there, since the outputs are recorded on upstream's release
tree. A fault of the check itself leaves no reward file.
"""

from __future__ import annotations

import contextlib
import ctypes
import errno
import grp
import importlib.util
import json
import os
import pwd
import random
import re
import resource
import secrets
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
# The reader of the post-session sweep's mark and record, and where the sweep's own folder arrives.
SWEEP_READER = TESTS / "sweep_check.py"
SWEEP_OUT = Path("/var/lib/fsmaint/out")
TREE = Path("/app/harfbuzz")
# On the disk (/tmp may be memory): root's own, 0755; `builder` owns only the five folders below it.
WORK = Path("/var/lib/hbv-work")
SRC = WORK / "tree"
BUILD = WORK / "b"
BIN = WORK / "drv"
HOME = WORK / "home"
TMP = WORK / "tmp"
# root-only: batch inputs and outputs, step logs, the disk reserve, the result files
IO = Path("/var/lib/hbv")
LOGS = Path("/logs/verifier")
# The image's user. Each run picks fresh ids in ID_RANGE that no account has, so verifiers sharing one kernel never
# share a process count; below 65,536, so that a user namespace of the usual size maps them. Where they cannot be
# used, the image's user is.
USER = "builder"
ID_RANGE = (20_000, 60_000)
# Folders every user may write, cleared of what `builder` made: after every sweep the memory-backed one, at the end
# all of them, and then the delivered tree's folder (all the way down), which may be writable in the verifier's
# environment.
SHARED_MEMORY = (Path("/dev/shm"),)
SHARED = (Path("/tmp"), Path("/var/tmp"), Path("/dev/shm"), Path("/run/lock"))
DELIVERED = Path("/app")
RELEASES = ("15.0.0", "15.1.0", "15.2.0")
W_BROAD = 0.10
# Case driver per case kind. hbdrv, hbapi and hbmeta use API that every release has; each hbapiNN probes what one note
# adds (a function, or hbapi33 the three new script values), so a tree without it fails only that probe's cases.
PROGRAMS = {
    "shape": "hbdrv",
    "api": "hbapi",
    "meta": "hbmeta",
    "api48": "hbapi48",
    "api49": "hbapi49",
    "api51": "hbapi51",
    "api33": "hbapi33",
}
# The new functions, by unit, and the header each one's note says declares it.
DECLARED_IN = {
    "48": ("src/hb-font.h", ("hb_font_create_without_funcs_or_fail",)),
    "49": ("src/hb-ot-layout.h", ("hb_ot_layout_get_extender_glyphs",)),
    "51": (
        "src/hb-buffer.h",
        ("hb_buffer_deserialize_glyphs2", "hb_buffer_deserialize_unicode2"),
    ),
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
    "TMPDIR": str(TMP),
    "LC_ALL": "C.UTF-8",
    "LANG": "C.UTF-8",
}
# The case programs only. glibc picks libm's code paths by CPU feature; with its FMA and AVX2 paths turned off,
# every x86-64 machine takes the SSE2 paths, as an emulator or an older CPU does (glibc 2.33 and later spell the
# features this way; other architectures ignore the setting).
DRIVER_ENV = {**ENV, "GLIBC_TUNABLES": "glibc.cpu.hwcaps=-AVX2,-FMA,-FMA4"}
LOADERS = ("/lib64/ld-linux-x86-64.so.2", "/lib/ld-linux-aarch64.so.1")

# Seconds from the start for the copy, the build and every batch (task.toml gives the verifier 2,400). ALARM is the
# last resort for root's own work; then the final sweep and the clean-up get FINAL_SECONDS and the publishing
# PUBLISH_SECONDS, each under an alarm of its own, so a reward is written by about 2,100 s at the latest.
DEADLINE = 1800
ALARM = DEADLINE + 180
FINAL_SECONDS = 90
CLEANUP_SECONDS = 45
PUBLISH_SECONDS = 30
# Each step's own limit, within what is left of the deadline: setup, build, each compile and each link of a case
# program. Past a step's own `timeout` (and its kill-after), root stops it after GRACE.
SETUP_CAP = 900
BUILD_CAP = 1500
COMPILE_CAP = 300
STEP_KILL_AFTER = 5
GRACE = 20
# One case program over one font's cases (the real ones take about 0.1 s): at most BATCH_CAP, leaving BATCH_RESERVE
# for every batch still to run, so a few hanging batches cost only their own cases.
BATCH_CAP = 15
BATCH_RESERVE = 2
BATCH_KILL_AFTER = 2
BATCH_GRACE = 4
# Killing the processes of `builder`, at most, each time; waiting for root's own child, at most, each time.
SWEEP_SECONDS = 30
CHILD_WAIT = 2.0
# Per process: build steps may run NPROC processes of `builder` and map BUILD_AS each; a case program never needs
# more than a few processes or more than DRIVER_AS. The largest file a build step may write (no file of a HarfBuzz
# build comes near it), and the largest output a case program may write.
NPROC = 1024
BUILD_AS = 4 << 30
DRIVER_NPROC = 8
DRIVER_AS = 1 << 30
BUILD_FSIZE = 512 << 20
DRIVER_FSIZE = 64 << 20
OOM_ADJ = "1000"
# Bytes read from one batch's output (the largest real batch prints about 110 kB) and from a failed step's log. A
# result (the text after the case's id) of more than MAX_RESULT characters fails its case (the longest expected one
# has 540); what is read of one batch is gone once it is scored.
MAX_OUTPUT = 16 << 20
MAX_RESULT = 4096
LOG_TAIL = 1500
# The copy of the delivered tree: a larger file is left out; past the others the tree is not built. Sizes count the
# larger of a file's length and its blocks on the disk. HarfBuzz 14.3.0 has 3,955 entries, about 100 MB, and is 7
# folders deep.
MAX_FILE = 64 << 20
MAX_TREE_BYTES = 1 << 30
MAX_ENTRIES = 300_000
MAX_DEPTH = 64
# Room set aside in IO, and the result files made there at the start, filled and moved into place at the end, so
# that a tree that fills the disk cannot stop the reward.
RESERVE = 8 << 20
RESULT_SLOTS = ("result-1", "result-2", "result-3")
RESULT_FILES = (
    "reward.txt",
    "reward.json",
    "metrics.json",
    "case_pass.json",
    "outputs.tsv",
)
# metrics.json stays under what the platform keeps (64 KiB); notes, step logs and the sweep's record are cut to fit.
METRICS_MAX = 60 << 10
NOTES_MAX = 16 << 10
NOTE_CHARS = 300
STEP_LOGS_MAX = 8 << 10
SWEEP_RECORD_MAX = 12 << 10
SWEEP_NOTES = 30
DIGEST_TAG = b"hbfp case digest\0"

# Upstream's unit-test sources that 15.0.0, 15.1.0 or 15.2.0 adds and 14.3.0 does not have, by sha256 of each
# release's copy. src/meson.build builds them only with -Dtests=enabled, which no build we ship uses, and no note
# needs them, so a tree holds one of them byte for byte only when upstream's release tree was copied into it. Every
# 15.x release carries at least 5 of them (15.0.0 5, 15.1.0 10, 15.2.0 15): DROPIN_QUORUM of them mark a copied
# release, and fewer leave room for a match nobody foresaw.
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
DROPIN_QUORUM = 3
# The tree stays version 14.3.0. Another version costs a tenth of the reward: the formula's own ceiling for a
# held-fixed loss outside the neighbours, since the version is something the notes do not change.
VERSION = "14.3.0"
VERSION_FACTOR = 0.9
# Read the way the build reads the tree: these may not be links (a link would hide what the build compiles).
NO_LINKS = ("meson.build", "NEWS", "src", "src/hb-version.h")


class CheckFault(Exception):
    """The check itself could not be carried out; no reward may be published."""


class OutOfTime(BaseException):
    """Raised by an alarm; a BaseException, so that no handler for ordinary errors swallows it."""


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


def protect_root(notes: list[str]) -> str:
    """Keep the out-of-memory killer away from this process: -1000, where root may lower its own score (that takes
    CAP_SYS_RESOURCE). Returns the score in effect."""
    try:
        fd = os.open("/proc/self/oom_score_adj", os.O_WRONLY | os.O_CLOEXEC)
        try:
            os.write(fd, b"-1000")
        finally:
            os.close(fd)
    except OSError as exc:
        notes.append(
            f"oom_score_adj: the check's own stays as it was ({exc.strerror}); builder's processes get {OOM_ADJ}"
        )
    try:
        with open("/proc/self/oom_score_adj", "rb") as fh:
            return fh.read(16).decode(errors="replace").strip()
    except OSError:
        return "unknown"


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


def is_link(root: Path, rel: str) -> bool:
    """Whether rel, or a folder on the way to it, is a link in the tree (nothing followed)."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_DIRECTORY
    try:
        fd = os.open(root, flags)
    except OSError:
        return False
    try:
        parts = rel.split("/")
        for i, part in enumerate(parts):
            try:
                st = os.stat(part, dir_fd=fd, follow_symlinks=False)
            except OSError:
                return False
            if stat.S_ISLNK(st.st_mode):
                return True
            if i == len(parts) - 1 or not stat.S_ISDIR(st.st_mode):
                return False
            sub = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = sub
        return False
    except OSError:
        return False
    finally:
        os.close(fd)


def release_test_sources(tree: Path) -> list[str]:
    """Which of upstream's 15.x-only unit-test sources the tree holds, byte for byte."""
    found = []
    for rel, digests in sorted(RELEASE_ONLY.items()):
        data = read_member(tree, rel, MAX_MARKER, whole=True)
        if data is not None and sha256(data).hexdigest() in digests:
            found.append(rel)
    return found


def _shown(value: bytes) -> str:
    return repr(value.decode("utf-8", errors="replace")[:40])


def version_off(tree: Path) -> list[str]:
    """Where the tree does not say version 14.3.0: meson.build's project version, src/hb-version.h's major, minor,
    micro and string, and the first token of NEWS's newest "Overview of changes leading to" line."""
    off = []
    text = read_member(tree, "meson.build", 1 << 18, whole=False)
    head = text and re.search(rb"\bproject\s*\(", text)
    found = head and re.search(
        rb"\bversion\s*:\s*'([^']*)'", text[head.end() : head.end() + 4000]
    )
    if text is None:
        off.append("meson.build is missing")
    elif not found:
        off.append("meson.build gives no project version")
    elif found.group(1) != VERSION.encode():
        off.append(f"meson.build gives project version {_shown(found.group(1))}")
    text = read_member(tree, "src/hb-version.h", 1 << 18, whole=False)
    if text is None:
        off.append("src/hb-version.h is missing")
    else:
        major, minor, micro = VERSION.split(".")
        for macro, want in (("MAJOR", major), ("MINOR", minor), ("MICRO", micro)):
            found = re.search(
                rb"#define\s+HB_VERSION_" + macro.encode() + rb"\s+(\S+)", text
            )
            if not found or found.group(1) != want.encode():
                given = _shown(found.group(1)) if found else "nothing"
                off.append(f"src/hb-version.h gives HB_VERSION_{macro} {given}")
        found = re.search(rb'#define\s+HB_VERSION_STRING\s+"([^"]*)"', text)
        if not found or found.group(1) != VERSION.encode():
            given = _shown(found.group(1)) if found else "nothing"
            off.append(f"src/hb-version.h gives HB_VERSION_STRING {given}")
    text = read_member(tree, "NEWS", 1 << 16, whole=False)
    found = text and re.search(
        rb"^Overview of changes leading to (\S+)", text, re.MULTILINE
    )
    if text is None:
        off.append("NEWS is missing")
    elif not found:
        off.append("NEWS has no 'Overview of changes leading to' line")
    elif found.group(1) != VERSION.encode():
        off.append(f"NEWS's newest entry is {_shown(found.group(1))}")
    return off


def tripwire(tree: Path) -> dict:
    """What in the tree comes from upstream's 15.x release trees, or keeps the build from reading what root read."""
    return {
        "test_sources": release_test_sources(tree),
        "links": [rel for rel in NO_LINKS if is_link(tree, rel)],
        "version": version_off(tree),
    }


def release_markers(tree: Path) -> list[str]:
    """Everything the release check finds in a tree, one line each; empty for a tree that keeps our version and holds
    none of upstream's 15.x-only unit-test sources (scripts/make_solution.py checks the reference tree with it)."""
    found = tripwire(tree)
    return (
        [f"{rel}: upstream's 15.x file" for rel in found["test_sources"]]
        + [f"{rel}: a link" for rel in found["links"]]
        + found["version"]
    )


def undeclared(tree: Path) -> dict[str, str]:
    """The units whose new functions are not declared in the header their notes name (comments do not count)."""
    out = {}
    for unit, (header, names) in sorted(DECLARED_IN.items()):
        text = read_member(tree, header, 1 << 20, whole=False)
        if text is None:
            out[unit] = f"{header} is missing"
            continue
        code = re.sub(rb"/\*.*?\*/", b" ", text, flags=re.DOTALL)
        code = re.sub(rb"//[^\n]*", b" ", code)
        missing = [
            name
            for name in names
            if not re.search(rb"\b" + name.encode() + rb"\s*\(", code)
        ]
        if missing:
            out[unit] = f"{', '.join(missing)} not declared in {header}"
    return out


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
        for slot, (name, data) in zip(RESULT_SLOTS, files, strict=False):
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
        self.started = time.monotonic()
        self.deadline = self.started + seconds

    def left(self) -> float:
        return self.deadline - time.monotonic()

    def limit(self, cap: int) -> int:
        return int(min(cap, self.left()))


class Ids:
    """The user the tree runs as, by number, and the spare user root's sweeping child keeps as its real and saved
    user, so that no process of `builder` may signal it. `fresh` is False for the image's own `builder`."""

    def __init__(self, uid: int, gid: int, spare: int, fresh: bool):
        self.uid, self.gid, self.spare, self.fresh = uid, gid, spare, fresh

    @staticmethod
    def image() -> Ids:
        try:
            entry = pwd.getpwnam(USER)
        except KeyError as exc:
            raise CheckFault(f"user {USER} is missing") from exc
        if entry.pw_uid == 0 or entry.pw_gid == 0:
            raise CheckFault(f"user {USER} is privileged")
        taken = {e.pw_uid for e in pwd.getpwall()} | {e.pw_gid for e in pwd.getpwall()}
        spare = next(n for n in range(entry.pw_uid + 1, 1 << 31) if n not in taken)
        return Ids(entry.pw_uid, entry.pw_gid, spare, fresh=False)

    @staticmethod
    def pick() -> Ids:
        """Fresh ids that no account and no group has; the image's `builder` stays as the fallback."""
        Ids.image()
        taken = {e.gr_gid for e in grp.getgrall()}
        taken |= {e.pw_uid for e in pwd.getpwall()} | {e.pw_gid for e in pwd.getpwall()}
        rng = random.SystemRandom()
        while True:
            uid, spare = rng.randrange(*ID_RANGE), rng.randrange(*ID_RANGE)
            if uid != spare and not {uid, spare} & taken:
                return Ids(uid, uid, spare, fresh=True)


def wait_child(pid: int, seconds: float) -> int | None:
    """The status of a child of root, waited for at most `seconds`. If it stops, or is still running then, root kills
    it (SIGKILL reaches a stopped process too) and reaps it, again for at most `seconds`; None then."""
    end = time.monotonic() + seconds
    pause = 0.0005
    while True:
        try:
            got, status = os.waitpid(pid, os.WNOHANG | os.WUNTRACED)
        except ChildProcessError:
            return None
        if got == pid and not os.WIFSTOPPED(status):
            return status
        if got == pid or time.monotonic() >= end:
            break
        time.sleep(pause)
        pause = min(pause * 2, 0.02)
    with contextlib.suppress(OSError):
        os.kill(pid, signal.SIGKILL)
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        try:
            got, _ = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            return None
        if got == pid:
            return None
        time.sleep(0.005)
    return None  # still not reaped: the subreaper's sweeps collect it later


def take_ids(ids: Ids) -> None:
    """In a child of root: effective user `builder`, real and saved user the spare one, no other group."""
    os.setgroups([])
    os.setresgid(ids.spare, ids.gid, ids.spare)
    os.setresuid(ids.spare, ids.uid, ids.spare)


def _status(proc: str) -> bytes | None:
    try:
        with open(f"/proc/{proc}/status", "rb") as fh:
            return fh.read(1 << 16)
    except OSError:
        return None


def _state(status: bytes) -> bytes:
    """A task's state letter (the last State: line, so that a name holding a line break cannot pose as one)."""
    found = re.findall(rb"^State:\s*(\S)", status, re.MULTILINE)
    return found[-1] if found else b"?"


class Sweeper:
    """Kills every process of `builder`, round after round until none is left."""

    def __init__(self, ids: Ids, notes: list[str]):
        self.ids, self.notes = ids, notes
        # Where a sweep first left processes it could not stop, and why root last could not fork.
        self.failed: str | None = None
        self.fork_error: str | None = None

    def _kill_all(self) -> None:
        """kill(-1) from a process with `builder`'s effective user reaches every process of that user in one system
        call, so a process that forks cannot outrun it (the kernel also cancels a fork it interrupts). That child's
        real and saved user is the spare one, so no process of `builder` may stop it; root waits for it at most
        CHILD_WAIT all the same. If root cannot fork, the per-process kills in sweep() do the work."""
        try:
            pid = os.fork()
        except OSError as exc:
            self.fork_error = self.fork_error or (exc.strerror or type(exc).__name__)
            return
        if pid == 0:
            try:
                take_ids(self.ids)
                os.kill(-1, signal.SIGKILL)
            finally:
                os._exit(0)  # whatever happened, this child goes no further
        wait_child(pid, CHILD_WAIT)

    def _alive_task(self, proc: str) -> bool:
        """Whether any thread of a process whose first thread has ended is still running."""
        try:
            tasks = os.listdir(f"/proc/{proc}/task")
        except OSError:
            return False
        for tid in tasks[:4096]:
            try:
                with open(f"/proc/{proc}/task/{tid}/status", "rb") as fh:
                    status = fh.read(1 << 16)
            except OSError:
                continue
            if _state(status) not in (b"Z", b"X"):
                return True
        return False

    def alive(self) -> list[int]:
        """Processes whose real, effective or saved user is `builder` and of which some thread has not yet exited."""
        found = []
        try:
            names = os.listdir("/proc")
        except OSError:
            return found
        for name in names:
            if not name.isdigit():
                continue
            status = _status(name)
            if status is None:
                continue
            uids = re.findall(rb"^Uid:\s*(\d+)\s+(\d+)\s+(\d+)", status, re.MULTILINE)
            if not uids or self.ids.uid not in {int(u) for u in uids[-1]}:
                continue
            if _state(status) not in (b"Z", b"X") or self._alive_task(name):
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
        """Kill every process of `builder`; return how many are still there when SWEEP_SECONDS run out (0 normally).
        Processes left fail the tree. Then what `builder` keeps in memory without a process goes too."""
        left = len(self.alive())
        if left:
            self.notes.append(
                f"{after}: {left} processes of {USER} left running; killed"
            )
        end = time.monotonic() + SWEEP_SECONDS
        while True:
            self._kill_all()
            alive = self.alive()
            # A stopped process cannot fork: stop them all, then kill them all.
            for sig in (signal.SIGSTOP, signal.SIGKILL):
                for pid in alive:
                    with contextlib.suppress(OSError):
                        os.kill(pid, sig)
            self._reap()
            if not alive:
                if self.fork_error:
                    self.notes.append(
                        f"{after}: root could not fork ({self.fork_error}); {USER}'s processes were killed one by one"
                    )
                    self.fork_error = None
                release_memory(self.ids)
                return 0
            if time.monotonic() >= end:
                self.notes.append(
                    f"{after}: {len(alive)} processes of {USER} could not be stopped; the tree fails"
                )
                self.failed = self.failed or after
                return len(alive)
            time.sleep(0.05)


def remove_ipc(ids: Ids) -> None:
    """Remove the System V shared memory, semaphores and message queues `builder` made: they outlive its processes.
    Only their owner may remove them where root lacks CAP_IPC_OWNER (Docker's default), so a child of root with
    `builder`'s effective user does it, as the sweeping child does its work."""
    # (table, column of the id, columns of the owner and the creator, its ctl function, the argument after IPC_RMID)
    tables = (
        ("shm", 1, (7, 9), "shmctl", None),
        ("sem", 1, (4, 6), "semctl", 0),
        ("msg", 1, (7, 9), "msgctl", None),
    )
    found = []
    for table, at, owners, ctl, last in tables:
        try:
            with open(f"/proc/sysvipc/{table}", "rb") as fh:
                rows = fh.read(1 << 22).splitlines()[1:]
        except OSError:
            continue
        for row in rows:
            cols = row.split()
            try:
                if any(int(cols[c]) == ids.uid for c in owners):
                    found.append((ctl, int(cols[at]), last))
            except (IndexError, ValueError):
                continue
    if not found:
        return
    try:
        pid = os.fork()
    except OSError:
        return
    if pid == 0:
        try:
            take_ids(ids)
            libc = ctypes.CDLL(None, use_errno=True)
            for ctl, key, last in found:
                getattr(libc, ctl)(key, 0, last)  # IPC_RMID
        finally:
            os._exit(0)
    wait_child(pid, CHILD_WAIT)


def remove_owned(top: Path, uid: int, until: float, deep: bool) -> int:
    """Remove every entry under `top` that `uid` owns (a folder with all it holds), never following a link; with deep,
    look inside the folders it does not own as well. Stops at `until` (time.monotonic()). Returns how many went."""
    removed = 0
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_DIRECTORY
    try:
        fd = os.open(top, flags)
    except OSError:
        return 0
    pending = [(fd, 0)]
    try:
        while pending:
            fd, depth = pending.pop()
            try:
                names = os.listdir(fd)
            except OSError:
                names = []
            for name in names:
                if time.monotonic() >= until:
                    return removed
                try:
                    st = os.stat(name, dir_fd=fd, follow_symlinks=False)
                except OSError:
                    continue
                if st.st_uid == uid:
                    with contextlib.suppress(OSError):
                        remove_entry(fd, name)
                        removed += 1
                elif deep and stat.S_ISDIR(st.st_mode) and depth < MAX_DEPTH:
                    with contextlib.suppress(OSError):
                        pending.append((os.open(name, flags, dir_fd=fd), depth + 1))
            os.close(fd)
    finally:
        for fd, _ in pending:
            os.close(fd)
    return removed


def release_memory(ids: Ids) -> None:
    """What `builder` holds in memory without a process: files in the memory-backed folders and System V objects."""
    until = time.monotonic() + 5
    for top in SHARED_MEMORY:
        remove_owned(top, ids.uid, until, deep=False)
    remove_ipc(ids)


class Context:
    def __init__(self, notes: list[str], ids: Ids, sweeper: Sweeper, clock: Clock):
        self.notes, self.ids, self.sweeper, self.clock = notes, ids, sweeper, clock
        self.io = Folder(IO)
        try:
            self.io.reserve()
        except OSError as exc:
            raise CheckFault(
                f"no room for the check's own files: {exc.strerror}"
            ) from exc
        self.step_logs: dict[str, str] = {}
        self.batches = {"run": 0, "failed": 0, "not_run": 0}
        self.choom = ["choom", "-n", OOM_ADJ, "--"]
        self.built = False
        # What root read of the tree before building it.
        self.sweep: dict = {"reader": "not read"}
        self.found: dict[str, list[str]] = {
            "test_sources": [],
            "links": [],
            "version": [],
        }
        self.undeclared: dict[str, str] = {}
        self.refused: list[str] = []
        self.drivers: dict[str, Path] = {}
        self.oom = "unknown"

    def halted(self, what: str) -> bool:
        """Whether nothing more of the tree may run, because a sweep left processes it could not stop."""
        if self.sweeper.failed is None:
            return False
        self.notes.append(f"{what}: not run, processes of {USER} survived a sweep")
        return True


def probe_logs(fd: int, ids: Ids) -> str:
    """Whether a process with `builder`'s ids can create a file in /logs/verifier, tried by a child of root:
    "refused", "created", "ids" (the ids cannot be taken here) or what went wrong."""
    name = f".probe-{secrets.token_hex(8)}"
    try:
        pid = os.fork()
    except OSError as exc:
        raise CheckFault(f"cannot fork: {exc.strerror}") from exc
    if pid == 0:
        code = 4
        try:
            try:
                take_ids(ids)
            except OSError:
                code = 2
                raise
            try:
                made = os.open(
                    name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                    0o600,
                    dir_fd=fd,
                )
            except OSError as exc:
                code = 0 if exc.errno in (errno.EACCES, errno.EPERM, errno.EROFS) else 3
            else:
                os.close(made)
                with contextlib.suppress(OSError):
                    os.unlink(name, dir_fd=fd)
                code = 1
        finally:
            os._exit(code)
    status = wait_child(pid, 10)
    with contextlib.suppress(OSError):
        remove_entry(fd, name)
    code = (
        os.WEXITSTATUS(status) if status is not None and os.WIFEXITED(status) else None
    )
    return {0: "refused", 1: "created", 2: "ids"}.get(
        code, f"the probe ended with {code}"
    )


def open_logs(notes: list[str], ids: Ids) -> tuple[int, Ids]:
    """/logs/verifier, made 0755 so that only its owner (root, or the host user it is mounted from) can write there,
    and proved so: a child with `builder`'s ids must fail to create a file in it, or the check stops (Harbor makes the
    folder 0777 for verifiers that run as other users, and some mounts ignore modes). The ids come back, the image's
    `builder` in place of fresh ones that cannot be taken here."""
    LOGS.mkdir(parents=True, exist_ok=True)
    fd = os.open(LOGS, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        try:
            if os.fstat(fd).st_uid in (ids.uid, Ids.image().uid):
                os.fchown(fd, 0, 0)
            os.fchmod(fd, 0o755)
        except OSError as exc:
            notes.append(f"/logs/verifier stays as mounted ({exc.strerror})")
        verdict = probe_logs(fd, ids)
        if verdict == "ids" and ids.fresh:
            notes.append(f"fresh ids cannot be taken here; the image's {USER} is used")
            ids = Ids.image()
            verdict = probe_logs(fd, ids)
        if verdict == "created":
            raise CheckFault(
                f"/logs/verifier can be written by {USER}: a tree's process could forge the reward"
            )
        if verdict != "refused":
            raise CheckFault(
                f"cannot tell whether {USER} can write /logs/verifier: {verdict}"
            )
    except BaseException:
        os.close(fd)
        raise
    return fd, ids


def as_builder(
    ctx: Context,
    cmd: list[str],
    *,
    cwd: Path,
    limit: int,
    stdin: int,
    stdout: int,
    stderr: int,
    env: dict[str, str],
    fsize: int,
    memory: int,
    nproc: int,
    kill_after: int,
    grace: int,
) -> tuple[int | None, str | None]:
    """Run a command as `builder` with a clean environment and limits: its exit code, or None if root had to stop it
    (or it could not be started, and then why).

    Its standard streams are root's open files or /dev/null, never a pipe, so a process it leaves behind cannot
    hold this call; `timeout` ends the command, and root ends `timeout` if that does not return in time."""
    wrapped = [
        "prlimit", f"--nproc={nproc}", f"--fsize={fsize}", "--core=0", f"--as={memory}", "--",
        *ctx.choom,
        "setpriv", f"--reuid={ctx.ids.uid}", f"--regid={ctx.ids.gid}", "--clear-groups", "--no-new-privs", "--",
        "timeout", f"--kill-after={kill_after}", str(limit), *cmd,
    ]  # fmt: skip
    try:
        return (
            subprocess.run(
                wrapped,
                cwd=cwd,
                env=env,
                stdin=stdin,
                stdout=stdout,
                stderr=stderr,
                timeout=limit + grace,
                check=False,
            ).returncode,
            None,
        )
    except subprocess.TimeoutExpired:
        return None, None
    except OSError as exc:
        return None, exc.strerror or type(exc).__name__


def prepare(record: bool) -> tuple[list[dict], dict[str, str], bytes]:
    if os.geteuid() != 0:
        raise CheckFault("the check must run as root")
    release = os.environ.get("RELEASE", "")
    if release not in RELEASES:
        raise CheckFault(f"unknown RELEASE {release!r}")
    for tool in (
        "setpriv",
        "prlimit",
        "choom",
        "timeout",
        "meson",
        "ninja",
        "cc",
        "c++",
    ):
        if shutil.which(tool, path=ENV["PATH"]) is None:
            raise CheckFault(f"{tool} is missing")
    try:
        cases = [
            json.loads(line)
            for line in (PRIVATE / "cases.jsonl").read_text().splitlines()
            if line
        ]
        if record:
            expected, salt = {}, b""
        else:
            raw = (PRIVATE / "expected.json").read_bytes()
            expected = json.loads(raw)[release]
            salt = sha256(DIGEST_TAG + raw).digest()
    except (OSError, ValueError, KeyError) as exc:
        raise CheckFault(f"private inputs unreadable: {exc}") from exc
    if not cases or (not record and any(c["id"] not in expected for c in cases)):
        raise CheckFault("private inputs incomplete")
    for kind in {c.get("drv", "shape") for c in cases}:
        if kind not in PROGRAMS or not (DRIVERS / f"{PROGRAMS[kind]}.c").is_file():
            raise CheckFault(f"driver for {kind!r} missing")
    return cases, expected, salt


def check_choom(ctx: Context) -> None:
    """Builder's processes go first to the out-of-memory killer (`choom`, raising a score needs no privilege), where
    that works here."""
    try:
        code = subprocess.run(
            [*ctx.choom, "true"],
            env=ENV,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
            check=False,
        ).returncode
    except (OSError, subprocess.TimeoutExpired):
        code = None
    if code != 0:
        ctx.choom = []
        ctx.notes.append(
            f"choom does not work here ({code}); builder's processes keep their score"
        )


def tunables_note() -> str:
    """One line on the glibc tunables the case programs get, as the loader itself reads them, and the CPU's FMA and
    AVX2 flags."""
    loader = next((p for p in LOADERS if os.path.exists(p)), None)
    if loader is None:
        return "glibc tunables: no dynamic loader found"
    try:
        out = subprocess.run(
            [loader, "--list-tunables"],
            env=DRIVER_ENV,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=10,
            check=False,
        ).stdout[: 1 << 16]
        lines = [
            line.strip()
            for line in out.decode(errors="replace").splitlines()
            if "hwcaps" in line
        ]
    except (OSError, subprocess.TimeoutExpired) as exc:
        lines = [f"not listed ({type(exc).__name__})"]
    flags: set[str] = set()
    with contextlib.suppress(OSError), open("/proc/cpuinfo", "rb") as fh:
        found = re.search(rb"^flags\s*:\s*(.*)$", fh.read(1 << 16), re.MULTILINE)
        flags = set(found.group(1).decode(errors="replace").split()) if found else set()
    cpu = ", ".join(
        f"{f} {'yes' if f in flags else 'no'}" for f in ("avx2", "fma", "fma4")
    )
    return f"glibc tunables for the case programs ({loader}): {'; '.join(lines) or 'no hwcaps line'}; CPU: {cpu}"


def read_sweep(notes: list[str]) -> dict:
    """What the post-session sweep says of the delivered tree, from /tests/sweep_check.py where it is shipped (loaded
    by its path: this runs under -I). Its check(tree, out) returns a dict whose "fault" (the sweep's word or the tree
    did not arrive whole) stops the check with no reward, whose "refused" means the tree is not built and scores 0,
    with its "notes", and whose "record" is kept, cut to SWEEP_RECORD_MAX, in metrics.json. Without the reader the
    tree is scored as it arrived."""
    try:
        st = os.lstat(SWEEP_READER)
    except FileNotFoundError:
        return {"reader": "absent"}
    except OSError as exc:
        raise CheckFault(f"{SWEEP_READER}: {exc.strerror}") from exc
    if not stat.S_ISREG(st.st_mode):
        raise CheckFault(f"{SWEEP_READER} is not a regular file")
    try:
        spec = importlib.util.spec_from_file_location("hbv_sweep_check", SWEEP_READER)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        said = module.check(TREE, SWEEP_OUT)
    except Exception as exc:  # our own reader failing is the check failing
        raise CheckFault(
            f"the sweep's reader failed: {type(exc).__name__}: {exc}"
        ) from exc
    if not isinstance(said, dict):
        raise CheckFault("the sweep's reader did not return a dict")
    if said.get("fault"):
        raise CheckFault(f"sweep: {str(said['fault'])[:NOTE_CHARS]}")
    refused = bool(said.get("refused"))
    said_notes = said.get("notes") or []
    if isinstance(said_notes, str):
        said_notes = [said_notes]
    for note in list(said_notes)[:SWEEP_NOTES]:
        note = str(note)[:NOTE_CHARS]
        notes.append(note if note.startswith("sweep:") else f"sweep: {note}")
    return {
        "reader": "shipped",
        "refused": refused,
        "record": clip_json(said.get("record"), SWEEP_RECORD_MAX),
    }


def clip_json(value, limit: int):
    """A JSON value no larger than `limit` bytes: as it is if it fits; else the keys or items that fit, in order,
    with what was left out counted; anything else as the start of its JSON text."""
    try:
        text = json.dumps(value, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return {"unreadable": True}
    if len(text) <= limit:
        return json.loads(text)
    value = json.loads(text)
    if isinstance(value, dict):
        kept, size, left_out = {}, 64, []
        for key in sorted(value):
            item = json.dumps({key: value[key]})
            if size + len(item) <= limit:
                kept[key] = value[key]
                size += len(item)
            else:
                left_out.append(key)
        kept["left_out"] = left_out[:50]
        return kept
    if isinstance(value, list):
        kept, size = [], 64
        for item in value:
            size += len(json.dumps(item)) + 2
            if size > limit:
                break
            kept.append(item)
        return {"items": kept, "of": len(value)}
    return {"start": text[: limit // 2], "bytes": len(text)}


def make_work(ctx: Context) -> None:
    """/var/lib/hbv-work as root's (0755), with the folders `builder` may write: the build, the case programs, its home
    and its temporary files."""
    try:
        os.mkdir(WORK, 0o755)
        st = os.lstat(WORK)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != 0:
            raise CheckFault(f"{WORK} is not root's")
        os.chmod(WORK, 0o755)
        for folder in (BUILD, BIN, HOME, TMP):
            os.mkdir(folder, 0o755)
            os.lchown(folder, ctx.ids.uid, ctx.ids.gid)
    except OSError as exc:
        raise CheckFault(f"{WORK} cannot be made: {exc.strerror}") from exc


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
    os.lchown(SRC, ctx.ids.uid, ctx.ids.gid)
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
                    os.lchown(dst, ctx.ids.uid, ctx.ids.gid)
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
                    os.lchown(dst, ctx.ids.uid, ctx.ids.gid)
                    pending.append((src, dst, depth + 1))
                elif stat.S_ISREG(st.st_mode) and st.st_size <= MAX_FILE:
                    size += max(st.st_size, st.st_blocks * 512)
                    if size > MAX_TREE_BYTES:
                        raise TreeRefused(
                            f"more than {MAX_TREE_BYTES >> 30} GiB of files"
                        )
                    copy_file(src, dst, st, ctx.ids.uid, ctx.ids.gid)
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


def timed_out(code: int | None, took: float, limit: int) -> bool:
    """`timeout` exits 124 when it stopped the command and 137 when it had to kill it; it is killed itself (-9) when
    its kill-after fires; None: root stopped it."""
    return code is None or code == 124 or (code in (-9, 137) and took >= limit)


def step(ctx: Context, name: str, cmd: list[str], cwd: Path, cap: int) -> bool:
    """One build step as `builder`, its output in a root-only log; every process of `builder` killed afterwards."""
    if ctx.halted(name):
        return False
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
        code, error = as_builder(
            ctx,
            cmd,
            cwd=cwd,
            limit=limit,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            env=ENV,
            fsize=BUILD_FSIZE,
            memory=BUILD_AS,
            nproc=NPROC,
            kill_after=STEP_KILL_AFTER,
            grace=GRACE,
        )
    finally:
        os.close(log)
        ctx.sweeper.sweep(name)
    took = time.monotonic() - started
    if error:
        ctx.notes.append(f"{name}: could not be started ({error})")
    elif timed_out(code, took, limit):
        ctx.notes.append(
            f"{name}: stopped at its time limit ({limit}s) after {took:.0f}s"
        )
    else:
        ctx.notes.append(f"{name}: exit {code} in {took:.0f}s")
    if code != 0 and not error:
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
    ctx.built = True
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


class Results:
    """What the case programs printed. Outside RECORD=1 root keeps of each case only whether its output equals the
    expected one and a short digest of it, so what it holds stays small whatever a tree prints; with RECORD=1, the
    output itself (MAX_RESULT characters at most)."""

    def __init__(self, expected: dict[str, str], salt: bytes, record: bool):
        self.expected, self.salt, self.record = expected, salt, record
        self.passed: dict[str, bool] = {}
        self.digests: dict[str, str] = {}
        self.texts: dict[str, str] = {}
        self.too_long: set[str] = set()

    def digest(self, data) -> str:
        h = sha256(self.salt)
        h.update(data)
        return h.hexdigest()[:8]

    def put(self, cid: str, result: str) -> None:
        self.digests[cid] = self.digest(result.encode("utf-8", errors="surrogatepass"))
        if self.record:
            self.texts[cid] = result
        else:
            self.passed[cid] = result == self.expected[cid]

    def put_long(self, cid: str, data) -> None:
        """A result over MAX_RESULT characters: it fails its case, whatever else is printed for it."""
        self.too_long.add(cid)
        self.digests[cid] = self.digest(data)
        if self.record:
            self.texts[cid] = "!too-long"
        else:
            self.passed[cid] = False

    def take(self, raw: bytes, ids: set[str]) -> int:
        """One batch's output, read as round 1 read it (UTF-8 with replacement, then str.splitlines()): a line
        `id<TAB>result` per case. Only the batch's own ids count, and a later line for an id replaces an earlier one;
        nothing of a line is kept but its pass bit and digest. Returns how many results were too long."""
        # The decoded text is gone once split; a line too long to hold a short enough result is neither split nor
        # compared, and its digest is taken through a view of its bytes.
        lines = raw.decode("utf-8", errors="replace").splitlines()
        long = 0
        for line in lines:
            if len(line) > MAX_RESULT + 64:
                cid = line[:64].partition("\t")[0]
                if cid in ids:
                    data = line.encode("utf-8", errors="surrogatepass")
                    self.put_long(cid, memoryview(data)[len(cid.encode()) + 1 :])
                    long += 1
                continue
            cid, _, result = line.partition("\t")
            if cid not in ids:  # a batch answers only for its own cases
                continue
            if len(result) > MAX_RESULT:
                self.put_long(cid, result.encode("utf-8", errors="surrogatepass"))
                long += 1
            else:
                self.put(cid, result)
        return long

    def ok(self, cid: str) -> bool:
        return self.passed.get(cid, False) and cid not in self.too_long


def run_batch(
    ctx: Context,
    n: int,
    kind: str,
    font: str,
    items: list[dict],
    exe: Path,
    limit: int,
    results: Results,
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
        code, error = as_builder(
            ctx,
            [str(exe)],
            cwd=Path("/"),
            limit=limit,
            stdin=fin,
            stdout=fout,
            stderr=subprocess.DEVNULL,
            env=DRIVER_ENV,
            fsize=DRIVER_FSIZE,
            memory=DRIVER_AS,
            nproc=DRIVER_NPROC,
            kill_after=BATCH_KILL_AFTER,
            grace=BATCH_GRACE,
        )
    finally:
        os.close(fin)
        os.close(fout)
        ctx.sweeper.sweep(label)
    took = time.monotonic() - started
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
    long = results.take(raw, {c["id"] for c in items})
    del raw
    if long:
        ctx.notes.append(
            f"{label}: {long} result{'s' if long > 1 else ''} over {MAX_RESULT} characters; "
            f"{'those cases fail' if long > 1 else 'its case fails'}"
        )
    if error or code != 0:
        ctx.batches["failed"] += 1
        if error:
            how = f"could not be started ({error})"
        elif timed_out(code, took, limit):
            how = f"stopped at its time limit ({limit}s)"
        else:
            how = f"exit {code}"
        ctx.notes.append(f"{label}: {how}; the cases it had not printed fail")


def run_batches(
    ctx: Context, drivers: dict[str, Path], cases: list[dict], results: Results
) -> None:
    """One case program per driver and font, so a hang, crash or flood costs only that batch's cases. Each batch gets
    at most BATCH_CAP, keeping BATCH_RESERVE for every batch after it."""
    batches: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in cases:
        batches[(c.get("drv", "shape"), c["font"])].append(c)
    # A batch whose case program did not compile or link is not run: its cases fail.
    runnable = [
        (n, kind, font, items)
        for n, ((kind, font), items) in enumerate(sorted(batches.items()))
        if kind in drivers
    ]
    not_run = 0
    for i, (n, kind, font, items) in enumerate(runnable):
        if ctx.sweeper.failed is not None:
            ctx.batches["not_run"] += 1
            not_run += len(items)
            continue
        left = ctx.clock.left()
        after = len(runnable) - i - 1
        limit = int(
            min(BATCH_CAP, max(BATCH_RESERVE, left - BATCH_RESERVE * after), left)
        )
        if limit < 1:
            ctx.batches["not_run"] += 1
            not_run += len(items)
            continue
        run_batch(ctx, n, kind, font, items, drivers[kind], limit, results)
    if not_run:
        why = (
            "processes of builder survived a sweep"
            if ctx.sweeper.failed
            else "the time was up"
        )
        ctx.notes.append(
            f"{ctx.batches['not_run']} batches ({not_run} cases) not run: {why}"
        )


def score(
    cases: list[dict], results: Results, failed_units: set[str], factor: float = 1.0
) -> tuple[dict, dict]:
    """The reward's parts (the reward times `factor`), and every case's result (pass, digest) by kind and unit."""
    units: dict[str, list[bool]] = defaultdict(list)
    duals: dict[str, list[bool]] = defaultdict(list)
    broad: list[bool] = []
    families: dict[str, list[bool]] = defaultdict(list)
    case_pass: dict[str, dict[str, dict[str, list]]] = {
        "changed": {},
        "dual": {},
        "broad": {},
    }
    for c in cases:
        ok = results.ok(c["id"]) and str(c.get("unit")) not in failed_units
        kind = c["kind"] if c["kind"] in ("changed", "dual") else "broad"
        case_pass[kind].setdefault(str(c.get("unit", kind)), {})[c["id"]] = [
            int(ok),
            results.digests.get(c["id"]),
        ]
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
        "reward": round(d * gate * factor, 6),
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
    }, case_pass


def clip_notes(notes: list[str]) -> list[str]:
    """The notes, each cut to NOTE_CHARS; past NOTES_MAX bytes, the first ones (three quarters of the room) and the
    last ones, with how many were left out between them."""
    cut = [n if len(n) <= NOTE_CHARS else n[: NOTE_CHARS - 3] + "..." for n in notes]
    if len(json.dumps(cut)) <= NOTES_MAX:
        return cut
    head, size = [], 64
    for note in cut:
        cost = len(json.dumps(note)) + 2
        if size + cost > NOTES_MAX * 3 // 4:
            break
        head.append(note)
        size += cost
    tail = []
    for note in reversed(cut[len(head) :]):
        cost = len(json.dumps(note)) + 2
        if size + cost > NOTES_MAX:
            break
        tail.append(note)
        size += cost
    left_out = len(cut) - len(head) - len(tail)
    return [*head, f"... {left_out} notes left out ...", *reversed(tail)]


def clip_logs(logs: dict[str, str]) -> dict[str, str]:
    """The step logs' tails, the earliest steps first, within STEP_LOGS_MAX bytes."""
    kept, size = {}, 0
    for name, text in logs.items():
        room = STEP_LOGS_MAX - size
        if room < 200:
            break
        kept[name] = text[-room:]
        size += len(json.dumps(kept[name]))
    return kept


def metrics_bytes(metrics: dict) -> bytes:
    """metrics.json's text, cut to fit METRICS_MAX should the parts above it not suffice."""
    data = (json.dumps(metrics, indent=1, sort_keys=True) + "\n").encode()
    for key, smaller in (
        ("step_logs", {}),
        ("notes", metrics.get("notes", [])[:20]),
        ("sweep", {"cut": True}),
    ):
        if len(data) <= METRICS_MAX:
            break
        metrics[key] = smaller
        data = (json.dumps(metrics, indent=1, sort_keys=True) + "\n").encode()
    return data


def finish(ctx: Context) -> bool:
    """The final sweep, then the clean-up, under an alarm of their own: whether the sweep was done. When the alarm
    fires, what has been scored is published all the same."""
    swept = False
    try:
        signal.alarm(FINAL_SECONDS)
        ctx.sweeper.sweep("the end")
        swept = True
        # The shared folders first (quick), then the work folder (the most room), then the delivered tree.
        until = time.monotonic() + CLEANUP_SECONDS
        removed = sum(
            remove_owned(top, ctx.ids.uid, until, deep=False) for top in SHARED
        )
        with contextlib.suppress(OSError):
            shutil.rmtree(WORK)
        removed += remove_owned(DELIVERED, ctx.ids.uid, until, deep=True)
        if removed:
            ctx.notes.append(
                f"the end: {removed} entries {USER} made outside its folders removed"
            )
        remove_ipc(ctx.ids)
    except OutOfTime:
        ctx.notes.append(
            "the end: the final sweep or the clean-up was cut short at its time limit"
        )
    return swept


def examine(ctx: Context) -> None:
    """Before any process of `builder` exists: what the sweep says of the tree, the release check and the
    declarations; ctx.refused says why the tree is not built, if it is not."""
    notes = ctx.notes
    ctx.sweep = read_sweep(notes)
    ctx.found = found = tripwire(TREE)
    ctx.undeclared = undeclared(TREE)
    if ctx.sweep.get("refused"):
        ctx.refused.append("the post-session sweep refused the tree")
    hits = found["test_sources"]
    if len(hits) >= DROPIN_QUORUM:
        names = ", ".join(Path(h).name for h in hits[:4]) + (
            ", ..." if len(hits) > 4 else ""
        )
        ctx.refused.append(
            f"it carries {len(hits)} of the {len(RELEASE_ONLY)} unit-test sources only upstream's 15.x releases "
            f"have ({names})"
        )
    elif hits:
        notes.append(
            f"{len(hits)} of upstream's 15.x-only unit-test sources in the tree ({', '.join(hits)}): fewer than "
            f"{DROPIN_QUORUM}, so it is built"
        )
    if found["links"]:
        links = found["links"]
        ctx.refused.append(
            f"{', '.join(links)} {'is a link' if len(links) == 1 else 'are links'}"
        )
    for why in ctx.refused:
        notes.append(f"not built: {why}")
    if found["version"] and not ctx.refused:
        notes.append(
            f"the tree's version is not {VERSION} ({'; '.join(found['version'])}): its reward is scaled by "
            f"{VERSION_FACTOR}"
        )
    for unit, why in ctx.undeclared.items():
        notes.append(f"unit {unit}: {why}; its cases fail")


def outputs_file(cases: list[dict], results: Results) -> bytes:
    """RECORD=1: every case's output, one line each."""
    return "".join(
        f"{c['id']}\t{results.texts.get(c['id'], '!missing')}\n" for c in cases
    ).encode()


def scored_files(
    ctx: Context, cases: list[dict], results: Results, survivors: str | None
) -> tuple[list[tuple[str, bytes]], dict]:
    """case_pass.json, metrics.json and reward.txt, in that order, and the summary line."""
    factor = VERSION_FACTOR if ctx.found["version"] and not ctx.refused else 1.0
    metrics, case_pass = score(cases, results, set(ctx.undeclared), factor)
    if survivors:
        ctx.notes.append(
            f"processes of {USER} could not be stopped ({survivors}): the tree fails, reward 0"
        )
        metrics["reward"] = 0.0
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    metrics |= {
        "release": os.environ["RELEASE"],
        "release_markers": ctx.found,
        "version_factor": factor,
        "refused": ctx.refused,
        "built": ctx.built,
        "survivors": survivors,
        "undeclared": ctx.undeclared,
        "sweep": ctx.sweep,
        "notes_total": len(ctx.notes),
        "notes": clip_notes(ctx.notes),
        "step_logs": clip_logs(ctx.step_logs),
        "batches": ctx.batches,
        "drivers": sorted(ctx.drivers),
        "cases": len(cases),
        "outputs": len(results.digests),
        "results_too_long": len(results.too_long),
        "case_pass": "case_pass.json",
        "builder": {"uid": ctx.ids.uid, "fresh": ctx.ids.fresh},
        "oom_score_adj": {
            "check": ctx.oom,
            "builder": OOM_ADJ if ctx.choom else "unchanged",
        },
        "peak_rss_mib": peak >> 10,
        "seconds": round(time.monotonic() - ctx.clock.started, 1),
    }
    passes = {
        "digest": "first 8 hex digits of sha256(salt, the output as printed, in UTF-8)",
        "cases": case_pass,
    }
    files = [
        (
            "case_pass.json",
            (json.dumps(passes, sort_keys=True, separators=(",", ":")) + "\n").encode(),
        ),
        ("metrics.json", metrics_bytes(metrics)),
        ("reward.txt", f"{metrics['reward']}\n".encode()),
    ]
    summary = {
        k: metrics[k] for k in ("reward", "D", "h_dual", "h_broad", "cases", "outputs")
    } | {
        "release_test_sources": len(ctx.found["test_sources"]),
        "version_off": len(ctx.found["version"]),
    }
    return files, summary


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
        oom = protect_root(notes)
        logs, ids = open_logs(notes, Ids.pick())
        sweeper = Sweeper(ids, notes)
        for name in RESULT_FILES:
            remove_entry(logs, name)
        cases, expected, salt = prepare(record)
        ctx = Context(notes, ids, sweeper, clock)
        ctx.oom = oom
        check_choom(ctx)
        notes.append(tunables_note())
        results = Results(expected, salt, record)
        try:
            if not record:
                examine(ctx)
            if not ctx.refused:
                ctx.drivers = build(ctx, {c.get("drv", "shape") for c in cases})
                run_batches(ctx, ctx.drivers, cases, results)
        except OutOfTime:
            notes.append(
                "stopped at the last-resort time limit; what had not run fails"
            )
        swept = finish(ctx)
        survivors = ctx.sweeper.failed or (None if swept else "the end, not finished")
        signal.alarm(PUBLISH_SECONDS)
        ctx.io.release()
        if record:
            if "shape" not in ctx.drivers:
                raise CheckFault("the reference tree did not build")
            files = [("outputs.tsv", outputs_file(cases, results))]
            summary = {
                "recorded": len(cases),
                "drivers": sorted(ctx.drivers),
                "notes": notes,
            }
        else:
            files, summary = scored_files(ctx, cases, results, survivors)
        ctx.io.publish(logs, files)
        published = True
        signal.alarm(0)
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
