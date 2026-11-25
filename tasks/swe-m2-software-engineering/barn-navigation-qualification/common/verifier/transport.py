"""Isolated candidate processes and strict JSON exchange.

Every candidate process runs as the unprivileged candidate account (``nobody``
as a fallback) in its own session, with a private HOME and TMPDIR and a fixed
search path, and its whole process group is killed once the verifier is done
with it. Replies and reports must be strict JSON objects: NaN, Infinity,
unbounded integers and runaway nesting are contract violations, never verifier
faults.
"""

import json
from math import isfinite
import os
from pathlib import Path
import pwd
import select
import signal
import stat
import subprocess
import sys
from time import monotonic
from typing import Any

Record = dict[str, Any]

PACKAGE = "barn_qualification"
CLI_TIMEOUT_S = 15.0
FIRST_REPLY_S, REPLY_S, PACE_GRACE_S = 5.0, 1.0, 3.0
REPLY_BYTES = 65_536
RESULT_BYTES = 4_000_000
SEARCH_PATH = "/usr/local/bin:/usr/bin:/bin"


class Violation(Exception):
    """A response violated the observable experiment contract."""


def require(valid: bool, message: str) -> None:
    """Reject the scenario with a precise cause."""
    if not valid:
        raise Violation(message)


def finite(text: str) -> float:
    """Decode a JSON number that must stay finite as a float."""
    number = float(text)
    if not isfinite(number):
        raise ValueError("number overflows a float")
    return number


def refuse(text: str) -> None:
    """Reject the NaN and Infinity extensions of Python's JSON decoder."""
    raise ValueError(f"{text} is not JSON")


def parse(data: bytes, what: str) -> Record:
    """Decode one strict JSON object written by the candidate."""
    try:
        value = json.loads(data, parse_float=finite, parse_constant=refuse)
    except (ValueError, RecursionError):
        raise Violation(f"{what} is not strict JSON") from None
    require(isinstance(value, dict), f"{what} must be a JSON object")
    return value


def identity() -> Record:
    """Select the unprivileged candidate account when the verifier runs as root."""
    if os.geteuid() != 0:
        return {}
    try:
        account = pwd.getpwnam("candidate")
    except KeyError:
        account = pwd.getpwnam("nobody")
    return {"user": account.pw_uid, "group": account.pw_gid, "extra_groups": []}


def environment(home: Path) -> dict:
    """A minimal environment whose only writable locations are the case's own."""
    return {"PATH": SEARCH_PATH, "HOME": str(home), "TMPDIR": str(home), "LANG": "C.UTF-8"}


def writable(path: Path) -> Path:
    """Create a directory the candidate account may write to."""
    path.mkdir(mode=0o777)
    path.chmod(0o777)
    return path


def command(mode: str, spec: Path, *extra: str) -> list:
    """Command line for one mode of the submitted package."""
    return [sys.executable, "-B", "-m", PACKAGE, mode, "--spec", str(spec), *extra]


def stop(process: subprocess.Popen) -> None:
    """Kill the process group, including any children it left behind, and reap it."""
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run(argv: list, app: Path, home: Path, timeout: float = CLI_TIMEOUT_S):
    """Run one candidate command to completion; None when it outlives the timeout."""
    process = subprocess.Popen(argv, cwd=app, env=environment(home), stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               start_new_session=True, **identity())
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        return None
    finally:
        stop(process)


def contents(path: Path):
    """Bytes of a regular file, or None for a link, FIFO, device, missing or oversized file."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            return None
        data = b""
        while len(data) <= RESULT_BYTES:
            block = os.read(descriptor, RESULT_BYTES + 1 - len(data))
            if not block:
                return data
            data += block
        return None
    finally:
        os.close(descriptor)


def report(path: Path) -> Record:
    """The strict JSON object a finished command left at its output path."""
    data = contents(path)
    require(data is not None, "qualification CLI produced no complete output")
    return parse(data, "output")


class Driver:
    """Stream one observation per reply to a single isolated navigator process."""

    def __init__(self, app: Path, spec: Path, home: Path) -> None:
        """Start the navigator with the verifier's least-privilege identity."""
        self.process = subprocess.Popen(command("stream", spec), cwd=app, env=environment(home),
                                        stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.DEVNULL, start_new_session=True,
                                        **identity())
        os.set_blocking(self.process.stdin.fileno(), False)
        self.buffer = b""
        self.elapsed = self.spent = self.slowest = 0.0

    def exchange(self, observation: Record, timeout: float) -> Record:
        """Send one observation and read one bounded, flushed JSON reply.

        Writes never block: a navigator that stops reading its input fails at
        the same deadline as one that stops answering. The time from the
        start of the write to the end of the reply is kept in ``elapsed``.
        """
        data = memoryview(json.dumps(observation, allow_nan=False).encode() + b"\n")
        sink, source = self.process.stdin.fileno(), self.process.stdout.fileno()
        begin = monotonic()
        deadline = begin + timeout
        while data:
            _, ready, _ = select.select([], [sink], [], max(0.0, deadline - monotonic()))
            require(bool(ready), "navigator stopped reading observations")
            try:
                data = data[os.write(sink, data):]
            except BlockingIOError:
                continue
            except BrokenPipeError:
                raise Violation("navigator exited before reading an observation") from None
        while b"\n" not in self.buffer:
            ready, _, _ = select.select([source], [], [], max(0.0, deadline - monotonic()))
            require(bool(ready), f"no flushed reply within {timeout:g} s")
            block = os.read(source, 4096)
            require(bool(block), "navigator exited before replying")
            self.buffer += block
            require(len(self.buffer) <= REPLY_BYTES, "oversized reply")
        self.elapsed = monotonic() - begin
        line, self.buffer = self.buffer.split(b"\n", 1)
        return parse(line, "reply")

    def paced(self, observation: Record, tick: int, dt: float) -> Record:
        """Exchange one tick while holding the navigator to the control period.

        The reply to tick 0 may take FIRST_REPLY_S. Every later reply must
        arrive within REPLY_S, and the replies to ticks 1..t together may take
        at most t*dt + PACE_GRACE_S.
        """
        reply = self.exchange(observation, FIRST_REPLY_S if tick == 0 else REPLY_S)
        if tick:
            self.spent += self.elapsed
            self.slowest = max(self.slowest, self.elapsed)
            require(self.spent <= tick * dt + PACE_GRACE_S, "navigator fell behind the control period")
        return reply

    def close(self) -> None:
        """Kill the navigator's process group and release the pipes."""
        stop(self.process)
        self.process.stdin.close()
        self.process.stdout.close()
