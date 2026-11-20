"""Check connection logs from a packaged Unreal listen host and remote player."""

from __future__ import annotations

import argparse
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import subprocess
import time
from typing import BinaryIO

from build_smoke import SmokeError, stop_process_group


@dataclass(frozen=True)
class RunningPlayer:
    """A foreground player process and an independent reader for its console."""

    process: subprocess.Popen[bytes]
    console: BinaryIO


@contextmanager
def launch_player(launcher: Path, arguments: list[str], state: Path) -> Iterator[RunningPlayer]:
    """Start one packaged process with private settings, temp files, and logs.

    Args:
        launcher: Absolute Linux executable or packaged shell launcher. The
            command must stay in the foreground while its player is connected.
        arguments: Project-specific host or join arguments in launch order.
        state: Fresh absolute directory for this player's saved state and logs.

    Yields:
        The live process and a reader positioned at the start of its output.
        Closing the context stops its process group and leaves logs on disk.
    """
    state.mkdir(mode=0o700)
    environment = {"PATH": "/usr/local/bin:/usr/bin:/bin"}
    for key, name in (
        ("HOME", "home"), ("TMPDIR", "tmp"), ("XDG_CONFIG_HOME", "config"),
        ("XDG_DATA_HOME", "data"), ("XDG_CACHE_HOME", "cache"), ("XDG_STATE_HOME", "state"),
    ):
        directory = state / name
        directory.mkdir()
        environment[key] = str(directory)
    user_dir = state / "unreal-user"
    user_dir.mkdir()
    command = ["/bin/bash", str(launcher)] if launcher.suffix == ".sh" else [str(launcher)]
    command += [
        *arguments, "-stdout", "-FullStdOutLogOutput", "-UTF8Output",
        f"-UserDir={user_dir}", f"-ABSLOG={state / 'unreal.log'}",
    ]

    console = state / "console.log"
    with console.open("wb") as writer, console.open("rb") as reader:
        process = subprocess.Popen(
            command, cwd=launcher.parent, env=environment, stdin=subprocess.DEVNULL,
            stdout=writer, stderr=subprocess.STDOUT, start_new_session=True,
        )
        try:
            yield RunningPlayer(process, reader)
        finally:
            stop_process_group(process)


def wait_for_markers(
    players: dict[str, RunningPlayer], markers: dict[str, str], observed: dict[str, str], timeout: float,
) -> None:
    """Read fresh console bytes until each selected role emits its marker.

    Args:
        players: Each process to monitor, keyed by role.
        markers: Case-sensitive literal text each selected role must emit.
        observed: Evidence dictionary updated as expected markers appear.
        timeout: Maximum seconds for this phase.

    Raises:
        SmokeError: A player exits during the phase or evidence is missing at
            the deadline.
    """
    pending = {role: marker.encode("utf-8") for role, marker in markers.items()}
    tails = dict.fromkeys(pending, b"")
    deadline = time.monotonic() + timeout
    while True:
        for role, player in players.items():
            code = player.process.poll()
            if code is not None:
                raise SmokeError(f"The {role} process exited with code {code}. See {role}/console.log.")
        if not pending:
            return
        if time.monotonic() >= deadline:
            roles = ", ".join(pending)
            raise SmokeError(f"Timed out after {timeout:g} seconds waiting for markers from {roles}.")

        for role, marker in list(pending.items()):
            recent = tails[role] + players[role].console.read(65536)
            if marker in recent:
                observed[role] = markers[role]
                del pending[role]
            else:
                # A marker can straddle two reads as the launcher writes it.
                tails[role] = recent[max(0, len(recent) - len(marker) + 1):]
        if pending:
            time.sleep(min(0.05, max(0, deadline - time.monotonic())))


def main() -> int:
    """Run the unprivileged connection probe and write its diagnostic report.

    Returns:
        Zero when both processes emitted the specified connection markers while
        running, otherwise a nonzero exit. The probe assigns no gameplay score.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-launcher", type=Path, required=True)
    parser.add_argument("--host-arg", action="append", default=[], help="Repeat using --host-arg=VALUE")
    parser.add_argument("--client-launcher", type=Path, required=True)
    parser.add_argument("--client-arg", action="append", default=[], help="Repeat using --client-arg=VALUE")
    parser.add_argument("--host-ready-marker", required=True, help="Literal text showing that the host accepts joins")
    parser.add_argument("--host-connected-marker", required=True, help="Literal host-side text for the remote join")
    parser.add_argument("--client-connected-marker", required=True, help="Literal client-side text for a completed join")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for reports and logs")
    parser.add_argument("--startup-timeout", type=float, default=60, help="Host readiness timeout, in seconds")
    parser.add_argument("--connect-timeout", type=float, default=60, help="Connection timeout, in seconds")
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("Run the probe as an unprivileged user in an isolated container")
    if any(not math.isfinite(timeout) or timeout <= 0 for timeout in (args.startup_timeout, args.connect_timeout)):
        parser.error("Timeouts must be finite and positive")
    readiness = {"host": args.host_ready_marker}
    connection = {"host": args.host_connected_marker, "client": args.client_connected_marker}
    if any(not marker.strip() for marker in (*readiness.values(), *connection.values())):
        parser.error("Log markers must contain non-whitespace text")

    host_path = args.host_launcher.resolve()
    client_path = args.client_launcher.resolve()
    if not host_path.is_file() or not client_path.is_file():
        parser.error("Both launcher paths must point to files")
    output = args.output_dir.resolve()
    try:
        output.mkdir(mode=0o700)
    except OSError as exc:
        parser.error(f"Cannot create a fresh output directory: {exc}")

    host_observed: dict[str, str] = {}
    connection_observed: dict[str, str] = {}
    report: dict[str, object] = {
        "status": "failed", "stage": "host_readiness",
        "expected": {"host_readiness": readiness, "connection": connection},
        "host_readiness": host_observed, "connection": connection_observed,
    }
    try:
        with launch_player(host_path, args.host_arg, output / "host") as host:
            wait_for_markers({"host": host}, readiness, host_observed, args.startup_timeout)
            report["stage"] = "connection"
            host.console.seek(0, os.SEEK_END)
            with launch_player(client_path, args.client_arg, output / "client") as client:
                wait_for_markers(
                    {"host": host, "client": client}, connection, connection_observed, args.connect_timeout,
                )
        report["status"] = "passed"
    except (OSError, SmokeError) as exc:
        report["error"] = str(exc)
    (output / "connection-smoke.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
