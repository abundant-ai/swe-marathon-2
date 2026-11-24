import json
import os
from pathlib import Path
import pwd
import select
import signal
import subprocess
import sys
from time import monotonic

from typing import Any

Record = dict[str, Any]


class Violation(Exception):
    """A response violated the observable experiment contract."""


def require(valid: bool, message: str) -> None:
    """Reject the scenario with a precise cause."""
    if not valid:
        raise Violation(message)


def identity() -> Record:
    """Select the unprivileged candidate account inside the verifier."""
    if os.geteuid() != 0:
        return {}
    try:
        account = pwd.getpwnam("candidate")
    except KeyError:
        account = pwd.getpwnam("nobody")
    return {"user": account.pw_uid, "group": account.pw_gid, "extra_groups": []}


class Driver:
    """Stream one observation per command to an isolated submission process."""

    def __init__(self, app: Path, config: Path, state: Path) -> None:
        """Store the command paths and start the candidate."""
        self.app = app
        self.config = config
        self.state = state
        self.start()

    def start(self) -> None:
        """Launch the package with the verifier's least-privilege identity."""
        permissions = identity()
        self.process = subprocess.Popen(
            [sys.executable, "-B", "-m", "barn_qualification", "stream", "--spec", str(self.config)],
            cwd=self.app, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            start_new_session=True,
            env={"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(self.state),
                 "LC_ALL": "C.UTF-8"},
            **permissions,
        )
        self.buffer = b""

    def exchange(self, observation: Record) -> Record:
        """Read one bounded, flushed JSON reply after a submitted observation."""
        fd = self.process.stdout.fileno()
        try:
            self.process.stdin.write(json.dumps(observation).encode() + b"\n")
            self.process.stdin.flush()
        except BrokenPipeError:
            raise Violation("navigation controller stopped before reading observation") from None
        stop = monotonic() + 2
        while b"\n" not in self.buffer:
            readable, _, _ = select.select([fd], [], [], max(0, stop - monotonic()))
            require(bool(readable), "no flushed response within two seconds")
            block = os.read(fd, 4096)
            require(bool(block), "navigation controller exited before responding")
            self.buffer += block
            require(len(self.buffer) < 65_536, "oversized response")
        line, self.buffer = self.buffer.split(b"\n", 1)
        try:
            result = json.loads(line)
        except (ValueError, UnicodeError):
            raise Violation("response is not valid JSON") from None
        require(isinstance(result, dict), "response must be a JSON object")
        return result

    def close(self) -> None:
        """Terminate the execution group, including stray children."""
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.process.wait()
        self.process.stdin.close()
        self.process.stdout.close()

    def restart(self) -> None:
        """Simulate unclean loss of the controller with state preserved."""
        self.close()
        self.start()
