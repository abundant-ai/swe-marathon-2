"""Copy the delivered project and build it offline as an unprivileged user.

The copy follows the brief: `target/`, links to directories, links that point outside the
directory or nowhere (loops included), and pipes, sockets and devices are left out, and a project
over the file or size limit is not copied (it then builds nothing). The build runs as `builder`, with no network and with no read access to the private
cases, in its own process group; when it ends or times out, every process of `builder` is killed,
one that left the group included.
"""

from __future__ import annotations

import os
import shutil
import stat
import subprocess
import tempfile
import time
from pathlib import Path

from .contracts import BuildResult, Limits
from .procs import SHARED_DIRS, capture, end_group, end_user, remove_files_of

BUILDER = "builder"
CARGO_CONFIG = Path("/opt/verifier/cargo-config.toml")
BUILD_LOG_CAP = 16 << 20


def copy_project(src: Path, dst: Path, limits: Limits) -> str | None:
    """Copy `src` to `dst` under the brief's rules. Return a refusal reason, or None."""
    files = 0
    size = 0
    root = src.resolve()
    for dirpath, dirnames, filenames in os.walk(src, followlinks=False):
        here = Path(dirpath)
        rel = here.relative_to(src)
        if rel.parts[:1] == ("target",):
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if not (rel == Path(".") and d == "target")]
        (dst / rel).mkdir(parents=True, exist_ok=True)
        for name in filenames:
            path = here / name
            if path.is_symlink():
                # os.path.realpath, unlike Path.resolve before Python 3.13, does not raise on a
                # loop; is_file() is then False for it.
                target = Path(os.path.realpath(path))
                if root not in target.parents or not target.is_file():
                    continue
            if not (path.is_file()):
                continue
            files += 1
            size += path.stat().st_size
            if files > limits.max_files or size > limits.max_bytes:
                return f"project over the copy limits ({files} files, {size} bytes)"
            shutil.copyfile(path, dst / rel / name)
    return None


def _chown_tree(path: Path, user: str) -> None:
    for dirpath, _, filenames in os.walk(path):
        shutil.chown(dirpath, user=user, group=user)
        for name in filenames:
            shutil.chown(Path(dirpath) / name, user=user, group=user)


def build(submission: Path, work: Path, limits: Limits) -> BuildResult:
    """Build `submission` with `cargo build --release --offline`; never raises on a bad project.

    Once the build is over, its program is copied out and everything `builder` owns in the shared
    directories and its home (the build's own folder included) is removed, so no run reads or
    writes what the build left there."""
    try:
        return _build(submission, work, limits)
    finally:
        remove_files_of(BUILDER, (*SHARED_DIRS, str(Path("~" + BUILDER).expanduser())))


def _build(submission: Path, work: Path, limits: Limits) -> BuildResult:
    start = time.monotonic()
    src = work / "src"
    home = work / "home"
    if not submission.is_dir():
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
    _chown_tree(work, BUILDER)
    env = {
        "PATH": "/usr/local/cargo/bin:/usr/local/bin:/usr/bin:/bin",
        "HOME": str(home),
        "CARGO_HOME": str(cargo_home),
        "RUSTUP_HOME": "/usr/local/rustup",
        "CARGO_TARGET_DIR": str(work / "target"),
        "LANG": "C.UTF-8",
    }
    proc = subprocess.Popen(
        ["cargo", "build", "--release", "--offline"],
        cwd=src,
        env=env,
        user=BUILDER,
        group=BUILDER,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        start_new_session=True,
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
    # the program must be a regular file inside that folder.
    real = Path(os.path.realpath(binary))
    inside = Path(os.path.realpath(work)) in real.parents
    if proc.returncode != 0 or binary.is_symlink() or not inside or not real.is_file():
        tail = out.decode("utf-8", "replace").strip().splitlines()[-5:]
        return BuildResult(False, None, "build failed: " + " | ".join(tail), seconds)
    # Copy it from a descriptor opened without following a link, into a new folder of root's.
    try:
        fd = os.open(real, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        return BuildResult(False, None, f"build left no program ({exc})", seconds)
    with os.fdopen(fd, "rb") as program:
        if not stat.S_ISREG(os.fstat(program.fileno()).st_mode):
            return BuildResult(False, None, "build left no program", seconds)
        bindir = Path(tempfile.mkdtemp(prefix="dw-bin-"))
        bindir.chmod(0o755)
        installed = bindir / "dogwood"
        with open(installed, "xb") as copy:
            shutil.copyfileobj(program, copy)
    installed.chmod(0o755)
    return BuildResult(True, installed, "built", seconds)
