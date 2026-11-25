"""Exchange bounded JSON lines with the submitted supervisor across cold restarts."""

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
import errno
import json
import os
from pathlib import Path
import pwd
import selectors
import signal
import subprocess
import sys
import time
from typing import Any

from candidate import request_directory

MAX_REPLY_BYTES = 2_000_000


class LiveCandidate:
    """Own one process group and reuse only the candidate's declared mission state."""

    def __init__(
        self, app: Path, root: Path, response: Path, account: pwd.struct_passwd | None, timeout_s: float,
    ) -> None:
        self.app = app
        self.root = root
        self.response = response
        self.account = account
        self.timeout_s = timeout_s
        self.process: subprocess.Popen[bytes] | None = None
        self.broken = False

    def stop(self) -> None:
        """Discard the process group while leaving its durable state directory available."""
        process, self.process = self.process, None
        if process is None:
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for pipe in (process.stdin, process.stdout):
            if pipe is not None:
                pipe.close()
        process.wait(timeout=3)

    def _start(self) -> bool:
        """Start a fresh process with the same read-only inputs and mission state."""
        account = self.account
        group = account.pw_gid if account else None
        user = account.pw_uid if account else None
        env = {
            "PATH": f"{Path(sys.executable).parent}:/usr/local/bin:/usr/bin:/bin",
            "HOME": str(self.response),
            "TMPDIR": str(self.response),
            "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
        }
        try:
            process = subprocess.Popen(
                [str(self.app / "coating"), "supervise", "--job", str(self.root / "job.json"),
                 "--registration", str(self.root / "registration.json"),
                 "--state", str(self.response / "state")],
                cwd=self.app, user=user, group=group, extra_groups=[] if account else None, env=env,
                start_new_session=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, bufsize=0,
            )
        except OSError as error:
            if error.errno not in (errno.ENOENT, errno.ENOEXEC, errno.EACCES):
                raise
            return False
        assert process.stdin is not None and process.stdout is not None
        for pipe in (process.stdin, process.stdout):
            os.set_blocking(pipe.fileno(), False)
        self.process = process
        return True

    def _exchange(self, payload: bytes) -> bytes | None:
        """Send the request and collect exactly one bounded line before the deadline."""
        process = self.process
        assert process is not None and process.stdin is not None and process.stdout is not None
        sent = 0
        received = bytearray()
        end = time.monotonic() + self.timeout_s
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdin, selectors.EVENT_WRITE)
            selector.register(process.stdout, selectors.EVENT_READ)
            while True:
                remaining = end - time.monotonic()
                if remaining <= 0:
                    return None
                for key, _ in selector.select(remaining):
                    if key.fileobj is process.stdin:
                        try:
                            sent += os.write(key.fd, payload[sent:sent + 65536])
                        except BlockingIOError:
                            continue
                        except BrokenPipeError:
                            return None
                        if sent == len(payload):
                            selector.unregister(process.stdin)
                    else:
                        try:
                            chunk = os.read(key.fd, 65536)
                        except BlockingIOError:
                            continue
                        if not chunk:
                            return None
                        received.extend(chunk)
                        if len(received) > MAX_REPLY_BYTES:
                            return None
                        if b"\n" in received:
                            if sent != len(payload) or not received.endswith(b"\n") or received.count(b"\n") != 1:
                                return None
                            return bytes(received)

    def __call__(self, request: Mapping[str, Any], *, restart: bool = False) -> dict[str, Any] | None:
        """Run one request, optionally after killing the previous supervisor.

        Returns:
            The parsed reply, or None on candidate execution/protocol failure.
        """
        if restart:
            self.stop()
        if self.broken:
            return None
        if self.process is None and not self._start():
            self.broken = True
            return None
        payload = (json.dumps(request, allow_nan=False) + "\n").encode()
        line = self._exchange(payload)
        if line is not None:
            try:
                reply = json.loads(line)
            except (ValueError, UnicodeError):
                reply = None
            if isinstance(reply, dict):
                return reply
        self.broken = True
        self.stop()
        return None


@contextmanager
def supervisor(
    app: Path, job: Mapping[str, Any], registration: Mapping[str, Any], *, timeout_s: float = 90.0,
) -> Iterator[LiveCandidate]:
    """Set up one mission in an isolated state directory and close it afterward."""
    with request_directory() as (root, response, account):
        for name, data in (("job", job), ("registration", registration)):
            path = root / f"{name}.json"
            path.write_text(json.dumps(data, allow_nan=False), encoding="utf-8")
            path.chmod(0o644)
        runner = LiveCandidate(app, root, response, account, timeout_s)
        try:
            yield runner
        finally:
            runner.stop()
