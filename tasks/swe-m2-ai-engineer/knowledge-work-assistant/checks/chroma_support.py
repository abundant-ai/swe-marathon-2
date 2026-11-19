"""Local HTTP service fixture for real Chroma boundary tests."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import httpx

from task_paths import TASK_ROOT


@contextmanager
def chroma_service(directory: Path) -> Iterator[dict[str, str]]:
    """Start the production service on a local ephemeral port without credentials.

    Args:
        directory: Private temporary directory for this test's database and logs.

    Yields:
        Host and port settings usable by real HttpClient/application subprocesses.

    Raises:
        RuntimeError: The service fails to become healthy within twenty seconds.
    """
    directory.mkdir(parents=True, exist_ok=True)
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
        endpoint = {"ORANGE_CHROMA_HOST": "127.0.0.1", "ORANGE_CHROMA_PORT": str(port)}
        environment = {
            "PATH": os.environ.get("PATH", ""),
            "PYTHONPATH": str(TASK_ROOT / "common/chroma-service"),
            "CHROMA_MAX_READ_RECORDS": "100", "CHROMA_MAX_BODY_BYTES": "16777216",
            "CHROMA_PERSIST_DIRECTORY": str(directory / "db"),
            "ANONYMIZED_TELEMETRY": "False",
        }
        with (directory / "server.log").open("w+") as log:
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "orange_chroma.server:create_app", "--factory",
                 "--fd", str(listener.fileno()), "--log-level", "warning",
                 "--limit-concurrency", "32", "--timeout-keep-alive", "5"],
                env=environment, stdout=log, stderr=log, pass_fds=(listener.fileno(),),
            )
            try:
                deadline = time.monotonic() + 20
                with httpx.Client(trust_env=False, timeout=1) as client:
                    while time.monotonic() < deadline and process.poll() is None:
                        try:
                            if client.get(f"http://127.0.0.1:{port}/api/v2/heartbeat").is_success:
                                break
                        except httpx.HTTPError:
                            pass
                        time.sleep(0.05)
                    else:
                        log.seek(0)
                        raise RuntimeError(log.read())
                yield endpoint
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
