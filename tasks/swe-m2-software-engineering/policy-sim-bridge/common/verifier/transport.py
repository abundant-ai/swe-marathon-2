"""Run an unprivileged submitted CLI and actuator stream."""

import json
import os
from pathlib import Path
import pwd
import select
import signal
import subprocess
import sys
from time import monotonic

from fixtures import Record


class Rejected(Exception):
    """The submitted policy bridge violated an observed requirement."""


def require(condition: bool, message: str) -> None:
    """Fail the current scoped probe with an observable cause."""
    if not condition:
        raise Rejected(message)


def identity() -> Record:
    """Run as the candidate account in the root-owned verifier image."""
    if os.geteuid() != 0:
        return {}
    try:
        account = pwd.getpwnam("candidate")
    except KeyError:
        account = pwd.getpwnam("nobody")
    return {"user": account.pw_uid, "group": account.pw_gid, "extra_groups": []}


def env(home: Path) -> dict[str, str]:
    """Construct the minimal candidate subprocess environment."""
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": str(home),
            "LC_ALL": "C.UTF-8", "MUJOCO_GL": "disable", "OPENBLAS_NUM_THREADS": "1"}


def writable(path: Path) -> Path:
    """Create a private-case directory the candidate process may write into."""
    path.mkdir()
    path.chmod(0o777)
    return path


def dump(path: Path, data: object) -> Path:
    """Store one public request in a readable file."""
    path.write_text(json.dumps(data, allow_nan=False) + "\n")
    path.chmod(0o644)
    return path


def batch(app: Path, args: list[str], output: Path, *, invalid: bool = False) -> Record | None:
    """Run a CLI operation and check successful or atomic-invalid behavior."""
    if invalid:
        output.write_text('{"sentinel":true}\n')
        output.chmod(0o666)
    try:
        completed = subprocess.run(
            [sys.executable, "-B", "-m", "policy_bridge", *args, "--output", str(output)],
            cwd=app, env=env(output.parent), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, timeout=15, **identity(),
        )
    except subprocess.TimeoutExpired:
        raise Rejected("policy bridge command timed out") from None
    if invalid:
        require(completed.returncode != 0 and output.read_text() == '{"sentinel":true}\n',
                "invalid input changed the existing output")
        return None
    require(completed.returncode == 0 and output.is_file() and output.stat().st_size < 250_000,
            "policy bridge CLI did not produce a complete report")
    return parse(output.read_bytes())


def parse(payload: bytes) -> Record:
    """Decode a complete report without trusting submitted values."""
    try:
        report = json.loads(payload)
    except (UnicodeError, ValueError):
        raise Rejected("candidate output was not a JSON record") from None
    require(isinstance(report, dict), "candidate output was not an object")
    return report


class Stream:
    """Drive an actual candidate process with one parsed response per clock event."""

    def __init__(self, app: Path, root: Path, spec: Record, *, calibration: Path | None = None, command: str = "stream",
                 drive: Path | None = None, safety: Path | None = None) -> None:
        """Prepare readable metadata and durable writable state."""
        root.mkdir()
        self.app = app
        self.spec = dump(root / "manifest.json", spec)
        self.state = writable(root / "state")
        self.calibration = calibration
        self.command = command
        self.drive = drive
        self.safety = safety
        self.start()

    def start(self) -> None:
        """Spawn one fresh process with the same configuration and state directory."""
        command = [sys.executable, "-B", "-m", "policy_bridge", self.command, "--spec", str(self.spec),
                   "--state", str(self.state)]
        if self.calibration is not None:
            command.extend(("--calibration", str(self.calibration)))
        if self.drive is not None:
            command.extend(("--drive", str(self.drive)))
        if self.safety is not None:
            command.extend(("--safety", str(self.safety)))
        self.process = subprocess.Popen(
            command,
            cwd=self.app, env=env(self.state), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, start_new_session=True, **identity(),
        )
        self.buffer = b""

    def push(self, observation: Record) -> Record:
        """Submit one packet and wait for its flushed response."""
        expiry = monotonic() + 2
        try:
            self.process.stdin.write(json.dumps(observation, allow_nan=False).encode() + b"\n")
            self.process.stdin.flush()
        except BrokenPipeError:
            raise Rejected("actor process exited while receiving an observation") from None
        fd = self.process.stdout.fileno()
        while b"\n" not in self.buffer:
            require(bool(select.select([fd], [], [], max(0, expiry - monotonic()))[0]),
                    "stream did not flush a reply")
            portion = os.read(fd, 16_384)
            require(bool(portion), "stream exited before returning a reply")
            self.buffer += portion
            require(len(self.buffer) < 250_000, "stream response was oversized")
        first, self.buffer = self.buffer.split(b"\n", 1)
        return parse(first)

    def close(self) -> None:
        """Kill the process group before closing test communication."""
        try:
            os.killpg(self.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        self.process.wait()
        self.process.stdin.close()
        self.process.stdout.close()

    def restart(self) -> None:
        """Force unclean restart while holding the exact prior adapter state."""
        self.close()
        self.start()

    def __enter__(self) -> "Stream":
        """Make crash-safe cleanup explicit in each scenario."""
        return self

    def __exit__(self, *_: object) -> None:
        """Clean up the isolated candidate process regardless of check result."""
        self.close()
