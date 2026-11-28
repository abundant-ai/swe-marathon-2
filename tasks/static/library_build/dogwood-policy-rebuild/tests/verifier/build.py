"""Copy the delivered project and build it offline as an unprivileged user.

The copy follows the brief (`listing.py` holds the rules): it takes regular files and
directories, and a link only when it leads to a regular file inside the project, whose content
it copies; cargo's build output, links to directories or out of the project, pipes, sockets,
devices, names that are not UTF-8, entries nested too deep and paths too long are left out. A
project over the file or size limit is not copied, so it builds nothing.

The build runs as `builder`, with no network, no read access to the private cases, its own
limits, and in its own process group; when it ends or times out, every process of `builder` is
ended, one that left the group included, and everything it left in the shared directories and
its home is removed.
"""

from __future__ import annotations

import os
import resource
import shutil
import stat
import subprocess
import tempfile
import time
from pathlib import Path

from . import listing
from .contracts import BuildResult, Limits
from .procs import (
    SHARED_DIRS,
    capture,
    clear_user,
    drop_to,
    end_group,
    end_user,
    expendable,
)

BUILDER = "builder"
CARGO_CONFIG = Path("/opt/verifier/cargo-config.toml")
BUILD_LOG_CAP = 16 << 20
BUILD_NPROC = 4096
BUILD_FSIZE = 4 << 30


def copy_project(src: Path, dst: Path, limits: Limits) -> str | None:
    """Copy `src` to `dst` under the brief's rules. Return a refusal reason, or None."""
    files = 0
    size = 0
    root = os.fsencode(src)
    real_root = os.path.realpath(root)
    dst_b = os.fsencode(dst)
    os.makedirs(dst_b, exist_ok=True)
    try:
        for item in listing.walk(root, limits.max_depth, limits.max_path):
            if isinstance(item, listing.LeftOut):
                continue
            target = dst_b + b"/" + item.rel.encode("utf-8")
            if item.kind == "d":
                os.makedirs(target, exist_ok=True)
                continue
            source = item.path
            if item.kind == "l":
                # os.path.realpath does not raise on a loop; the result is then no file.
                real = os.path.realpath(item.path)
                if not real.startswith(real_root + b"/"):
                    continue
                try:
                    if not stat.S_ISREG(os.stat(real).st_mode):
                        continue
                except OSError:
                    continue
                source = real
            try:
                fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            except OSError:
                continue
            with os.fdopen(fd, "rb") as data:
                info = os.fstat(data.fileno())
                if not stat.S_ISREG(info.st_mode):
                    continue
                files += 1
                size += info.st_size
                if files > limits.max_files or size > limits.max_bytes:
                    return f"project over the copy limits ({files} files, {size} bytes)"
                with open(target, "xb") as copy:
                    shutil.copyfileobj(data, copy)
            # The file's own permission bits, without set-id bits.
            os.chmod(target, stat.S_IMODE(info.st_mode) & 0o755 | 0o600)
    except OSError as exc:
        return f"the project could not be copied ({exc.__class__.__name__})"
    return None


def _limits() -> None:
    expendable()
    resource.setrlimit(resource.RLIMIT_NPROC, (BUILD_NPROC, BUILD_NPROC))
    resource.setrlimit(resource.RLIMIT_FSIZE, (BUILD_FSIZE, BUILD_FSIZE))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    drop_to(BUILDER)  # last: the score and the limits are set while still root


def build(submission: Path, work: Path, limits: Limits) -> BuildResult:
    """Build `submission` with `cargo build --release --offline`; never raises on a bad project.

    Once the build is over, its program is copied out, every process of `builder` is ended, and
    everything it owns in the shared directories and its home (the build's own folder included)
    is removed, so no run reads or writes what the build left there."""
    try:
        return _build(submission, work, limits)
    finally:
        clear_user(BUILDER, (*SHARED_DIRS, str(Path("~" + BUILDER).expanduser())))


def _build(submission: Path, work: Path, limits: Limits) -> BuildResult:
    start = time.monotonic()
    src = work / "src"
    home = work / "home"
    if not submission.is_dir() or submission.is_symlink():
        return BuildResult(False, None, "no project delivered", 0.0)
    reason = copy_project(submission, src, limits)
    if reason is not None:
        return BuildResult(False, None, reason, time.monotonic() - start)
    if not (src / "Cargo.toml").is_file():
        return BuildResult(
            False, None, "no Cargo.toml at the project root", time.monotonic() - start
        )
    cargo_home = home / ".cargo"
    cargo_home.mkdir(parents=True)
    shutil.copyfile(CARGO_CONFIG, cargo_home / "config.toml")
    listing.chown_tree(os.fsencode(work), BUILDER)
    env = {
        "PATH": "/usr/local/cargo/bin:/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "CARGO_HOME": str(cargo_home),
        "RUSTUP_HOME": "/usr/local/rustup",
        "CARGO_TARGET_DIR": str(work / "target"),
        "LANG": "C.UTF-8",
    }
    proc = subprocess.Popen(
        ["/usr/local/cargo/bin/cargo", "build", "--release", "--offline"],
        cwd=src,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        preexec_fn=_limits,  # noqa: PLW1509 - the grader is single-threaded
    )
    try:
        out, timed_out, overflow = capture(
            proc, limits.build_timeout_sec, BUILD_LOG_CAP
        )
    finally:
        end_group(proc)
        end_user(BUILDER)
    seconds = time.monotonic() - start
    if timed_out:
        return BuildResult(False, None, "build did not finish in time", seconds)
    if overflow:
        return BuildResult(False, None, "build printed more than 16 MB", seconds)
    binary = work / "target" / "release" / "dogwood"
    # The build's folder is `builder`'s: a link there could point at any file of this machine, so
    # the program must be a regular file inside that folder. No process of `builder` is left.
    real = Path(os.path.realpath(binary))
    inside = Path(os.path.realpath(work)) in real.parents
    if proc.returncode != 0 or binary.is_symlink() or not inside:
        tail = out.decode("utf-8", "replace").strip().splitlines()[-5:]
        return BuildResult(False, None, "build failed: " + " | ".join(tail), seconds)
    # Copy it from a descriptor opened without following a link, into a new folder of root's.
    try:
        fd = os.open(real, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        return BuildResult(False, None, f"build left no program ({exc})", seconds)
    with os.fdopen(fd, "rb") as program:
        if not stat.S_ISREG(os.fstat(program.fileno()).st_mode):
            return BuildResult(False, None, "build left no program", seconds)
        bindir = Path(tempfile.mkdtemp(prefix="dw-bin-"))
        bindir.chmod(0o755)
        installed = bindir / "dogwood"
        try:
            with open(installed, "xb") as copy:
                shutil.copyfileobj(program, copy)
        except OSError as exc:
            return BuildResult(
                False, None, f"the program could not be copied ({exc})", seconds
            )
    installed.chmod(0o755)
    return BuildResult(True, installed, "built", seconds)
