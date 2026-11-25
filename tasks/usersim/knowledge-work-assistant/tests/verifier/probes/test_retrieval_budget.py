"""Observe retrieval entry points in the real CLI without saving trajectories."""

from __future__ import annotations

import importlib
import os
import socket
import sys
import threading
from types import FrameType

__test__ = False


def install() -> None:
    """Count coroutine entries through a trusted parent-owned budget socket.

    Python children inherit the hook and share the same question budget. Retained
    frames distinguish a fresh call from coroutine resume events and prevent ID
    reuse. This is behavioral instrumentation, not a tamper-proof Python sandbox.
    """
    address = os.environ["ORANGE_RETRIEVAL_BUDGET_SOCKET"]

    def request(kind: bytes) -> bool:
        """Ask the verifier to register startup or authorize one retrieval call.

        Args:
            kind: S for process startup, R for a new retrieve invocation.

        Returns:
            Whether the parent permits execution; failures deny permission.
        """
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(5)
                connection.connect(address)
                connection.sendall(kind)
                return connection.recv(1) == b"1"
        except OSError:
            return False

    try:
        module = importlib.import_module("main")
        code = module.retrieve.__code__
    except Exception:  # noqa: BLE001
        os._exit(86)
    frames: dict[int, FrameType] = {}
    lock = threading.Lock()

    def count_call(frame: FrameType, event: str, arg: object) -> None:
        """Charge a retrieval attempt before its body starts executing.

        Args:
            frame: Python execution frame, including async resume events.
            event: Profiling event; only new call frames consume budget.
            arg: Unused profiler payload.
        """
        if event != "call" or frame.f_code is not code:
            return
        with lock:
            if id(frame) in frames:
                return
            frames[id(frame)] = frame
            if not request(b"R"):
                os._exit(86)

    if not request(b"S"):
        os._exit(86)
    threading.setprofile(count_call)
    sys.setprofile(count_call)


if "ORANGE_RETRIEVAL_BUDGET_SOCKET" in os.environ:
    install()
