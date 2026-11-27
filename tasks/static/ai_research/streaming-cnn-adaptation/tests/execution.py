"""A persistent updater with a one-frame input channel and a fixed numeric output channel."""

import contextlib
import itertools
import os
import select
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path


class CandidateFailure(Exception):
    pass


def receive(fd, size, deadline):
    chunks = bytearray()
    while len(chunks) < size:
        remaining = deadline - time.monotonic()
        if remaining <= 0 or not select.select([fd], [], [], remaining)[0]:
            raise CandidateFailure("Updater exceeded its response time")
        chunk = os.read(fd, size - len(chunks))
        if not chunk:
            raise CandidateFailure("Updater exited before returning its weights")
        chunks.extend(chunk)
    return bytes(chunks)


# Use a different numerical identity for each training run or deployment. The
# image reserves this range for disposable jobs and protects shared scratch mounts.
identities = itertools.count(41000)


@contextlib.contextmanager
def workspace(public):
    with tempfile.TemporaryDirectory(prefix="core50-work-") as directory:
        work = Path(directory)
        command = []
        identity = None
        if os.getuid() == 0:
            identity = next(identities)
            if identity >= 60000:
                raise RuntimeError("Disposable worker identity range exhausted")
            os.chown(work, identity, identity)
            command = [
                "setpriv",
                f"--reuid={identity}",
                f"--regid={identity}",
                "--clear-groups",
                "--no-new-privs",
            ]
        work.chmod(0o700)
        env = {
            "PATH": os.defpath + ":/usr/local/bin",
            "PILOT_PUBLIC": str(public),
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "HOME": str(work),
            "TMPDIR": str(work),
        }
        try:
            yield work, command, env
        finally:
            if identity is not None:
                remove_worker_processes(identity)


def remove_worker_processes(identity):
    """The dedicated verifier assigns each worker a private numerical user ID."""
    deadline = time.monotonic() + 5
    while True:
        live = []
        for proc in Path("/proc").iterdir():
            if not proc.name.isdigit():
                continue
            try:
                if proc.stat().st_uid != identity:
                    continue
                status = (proc / "status").read_text()
                if "State:\tZ" not in status:
                    live.append(int(proc.name))
            except (FileNotFoundError, ProcessLookupError):
                continue
        if not live:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError("Could not clean up the isolated worker identity")
        for pid in live:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        time.sleep(0.025)


def send(fd: int, payload: bytes, deadline: float) -> None:
    """Send the entire numeric message on a nonblocking pipe before a monotonic deadline."""
    remaining = memoryview(payload)
    while remaining:
        timeout = deadline - time.monotonic()
        if timeout <= 0 or not select.select([], [fd], [], timeout)[1]:
            raise CandidateFailure("Updater exceeded its input time")
        try:
            written = os.write(fd, remaining)
        except BlockingIOError:
            continue
        remaining = remaining[written:]


@contextlib.contextmanager
def updater(source, public, layout):
    with workspace(public) as (work, command, env):
        shutil.copyfile(source, work / "online.py")
        (work / "online.py").chmod(0o444)
        cmd = [*command, sys.executable, "-IB", str(public / "worker.py")]
        with tempfile.TemporaryFile() as log:
            proc = subprocess.Popen(
                cmd,
                cwd=work,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=log,
                env=env,
                start_new_session=True,
            )
            try:
                deadline = time.monotonic() + 35
                try:
                    ready = receive(proc.stdout.fileno(), 1, deadline)
                except CandidateFailure as error:
                    raise RuntimeError(
                        "Trusted worker failed before loading the submitted updater"
                    ) from error
                if ready != b"T":
                    raise RuntimeError(
                        "Unexpected trusted worker initialization message"
                    )
                input_fd = proc.stdin.fileno()
                os.set_blocking(input_fd, False)
                send(input_fd, layout.encode(), deadline)
                if receive(proc.stdout.fileno(), 1, deadline) != b"R":
                    raise CandidateFailure("Updater initialization failed")
                remaining = 145.0

                def step(frame):
                    nonlocal remaining
                    started = time.monotonic()
                    try:
                        send(input_fd, frame.tobytes(), started + min(remaining, 12))
                        raw = receive(
                            proc.stdout.fileno(),
                            layout.numel * 4,
                            started + min(remaining, 12),
                        )
                        remaining -= time.monotonic() - started
                        layout.restore(raw)
                    except (BrokenPipeError, ValueError) as exc:
                        raise CandidateFailure(str(exc)) from exc

                yield step
            except (CandidateFailure, BrokenPipeError) as exc:
                log.seek(0, 2)
                start = max(0, log.tell() - 1600)
                log.seek(start)
                raise CandidateFailure(
                    str(exc) + " " + log.read(1600).decode(errors="replace")
                ) from exc
            finally:
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                proc.wait(timeout=5)
                proc.stdin.close()
                proc.stdout.close()
