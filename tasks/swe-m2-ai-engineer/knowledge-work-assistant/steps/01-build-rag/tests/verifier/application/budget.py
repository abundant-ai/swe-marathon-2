"""Parent-owned retrieval counters for one real single-question CLI command."""

from __future__ import annotations

import os
import socket
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from verifier.application.process import CommandResult, run_process
from verifier.contracts import CandidateFailure

if TYPE_CHECKING:
    from verifier.application.client import ApplicationClient


def run_bounded_cli(app: ApplicationClient, args: Sequence[str], *, limit: int,
                    timeout: int, stdin: str = "") -> CommandResult:
    """Run the executable while charging every observed retrieval to one budget.

    Args:
        app: Candidate workspace, user identity, and explicitly allowed environment.
        args: Real orange CLI arguments for a single question.
        limit: Maximum retrieval calls, shared across Python child processes.
        timeout: Command deadline in seconds, including answer generation.
        stdin: Optional JSON question input.

    Returns:
        Successful command output when startup instrumentation ran and the budget
        was respected. Counters stay in the verifier; no queries or traces are saved.

    Raises:
        CandidateFailure: Missing instrumentation, budget excess, or command failure.
    """
    if limit < 1:
        raise ValueError("Retrieval limit must be positive")
    source = (Path(__file__).resolve().parents[1] / "probes/test_retrieval_budget.py").read_text()
    with tempfile.TemporaryDirectory(prefix="orange-budget-", dir="/tmp") as temporary:
        directory = Path(temporary)
        directory.chmod(0o755)
        hook = directory / "sitecustomize.py"
        hook.write_text(source)
        hook.chmod(0o644)
        address = str(directory / "counter.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(address)
            os.chmod(address, 0o666)
            server.listen(128)
            server.settimeout(0.1)
            stopped = threading.Event()
            calls = 0
            startups = 0
            exceeded = False

            def serve() -> None:
                """Serialize child requests and retain a sticky budget violation."""
                nonlocal calls, startups, exceeded
                while not stopped.is_set():
                    try:
                        connection, _ = server.accept()
                    except TimeoutError:
                        continue
                    with connection:
                        connection.settimeout(1)
                        try:
                            kind = connection.recv(1)
                            if kind == b"S":
                                startups += 1
                            elif kind == b"R":
                                calls += 1
                                exceeded |= calls > limit
                            connection.sendall(b"1" if kind in (b"S", b"R") and not exceeded else b"0")
                        except OSError:
                            continue

            thread = threading.Thread(target=serve, daemon=True)
            thread.start()
            environment = {**app.environment,
                           "PYTHONPATH": os.pathsep.join((str(directory), str(app.root), app.environment.get("PYTHONPATH", ""))),
                           "ORANGE_RETRIEVAL_BUDGET_SOCKET": address}
            try:
                result = run_process([str(app.root / "orange"), *args], root=app.root,
                                     environment=environment, uid=app.uid, stdin=stdin,
                                     timeout=timeout, require_success=False)
            finally:
                stopped.set()
                thread.join()
            if exceeded:
                raise CandidateFailure(f"Question exceeded {limit} retrieve() calls")
            if not startups:
                raise CandidateFailure("CLI retrieval-budget instrumentation did not start")
            if result.code:
                raise CandidateFailure(f"Budgeted answer command exited with status {result.code}")
            return result
